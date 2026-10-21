"""Serveur TCP : connexions et réception des détections du capteur.

Depuis la racine du projet : python -m src.serveur.serveur
Pour accepter des clients du réseau local : ajouter --hote 0.0.0.0
Arrêt : Ctrl+C. Bibliothèque standard uniquement.

Premier message : {"type": "bonjour", "role": "regulateur"}
Rôles possibles : regulateur, capteur, feux (une connexion par rôle).
Messages communs : ping, etat, quitter.
Capteur uniquement : detection_ambulance et sortie_ambulance, avec direction N/S/E/O.

Le serveur pilote le client feux ; le raccordement à la maquette reste à faire.
Les rôles identifient les clients ; ce n'est pas une authentification.
"""

import argparse
import socket
import threading
import time

# Accepte aussi le lancement direct : python src/serveur/serveur.py
if __package__:
    from ..reseau import ConnexionJSON, PORT_SERVEUR
else:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from reseau import ConnexionJSON, PORT_SERVEUR


ROLES = ("regulateur", "capteur", "feux")
PHASES = [("vert", "rouge", 10), ("orange", "rouge", 2),
          ("rouge", "rouge", 1), ("rouge", "vert", 10),
          ("rouge", "orange", 2), ("rouge", "rouge", 1)]


class Serveur:
    """Un thread par client, avec un verrou pour les collections partagées."""

    def __init__(self, hote="127.0.0.1", port=PORT_SERVEUR):
        self.hote = hote
        self.port = port
        self.arret = threading.Event()
        self.pret = threading.Event()
        self.verrou = threading.Lock()
        self.clients = {}  # rôle -> ConnexionJSON
        self.connexions = set()  # Inclut les clients pas encore identifiés.
        self.threads = set()
        self.ecoute = None
        self.direction_ambulance = None
        self.detection_valide = False
        self.revision_detection = 0
        self.carrefour_occupe = None  # Inconnu jusqu'au premier signal capteur.
        self.phase_feux = 5
        self.fin_phase = time.monotonic() + 1

    def demarrer(self):
        """Écoute les connexions jusqu'à Ctrl+C ou à un appel à arreter()."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ecoute:
                self.ecoute = ecoute
                ecoute.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                ecoute.bind((self.hote, self.port))
                self.port = ecoute.getsockname()[1]
                ecoute.listen(5)
                ecoute.settimeout(0.5)
                print(f"Serveur prêt sur {self.hote}:{self.port}", flush=True)
                self.pret.set()
                while not self.arret.is_set():
                    try:
                        connexion, adresse = ecoute.accept()
                    except socket.timeout:
                        continue
                    connexion.settimeout(0.5)
                    canal = ConnexionJSON(connexion)
                    thread = threading.Thread(
                        target=self.gerer_client, args=(canal, adresse), daemon=True
                    )
                    with self.verrou:
                        self.connexions.add(canal)
                        self.threads.add(thread)
                    thread.start()
        except KeyboardInterrupt:
            print("\nArrêt demandé.", flush=True)
        finally:
            self.arreter()
            with self.verrou:
                threads = list(self.threads)
            for thread in threads:
                thread.join(timeout=1)
            self.ecoute = None

    def recevoir(self, canal, limite=None):
        """Attend un message en vérifiant régulièrement si le serveur s'arrête."""
        while not self.arret.is_set():
            if limite is not None and time.monotonic() >= limite:
                raise TimeoutError("Identification non reçue dans les cinq secondes.")
            try:
                return canal.recevoir()
            except socket.timeout:
                continue
        return None

    def gerer_client(self, canal, adresse):
        """Identifie un client, traite ses messages, puis libère sa connexion."""
        role = None
        try:
            message = self.recevoir(canal, time.monotonic() + 5)
            if message is None:
                return
            candidat = message.get("role")
            if message["type"] != "bonjour" or candidat not in ROLES:
                canal.envoyer({"type": "erreur", "message": "Envoyer bonjour avec un rôle valide."})
                return
            with self.verrou:
                disponible = candidat not in self.clients
                if disponible:
                    self.clients[candidat] = canal
                    role = candidat
            if not disponible:
                canal.envoyer({"type": "erreur", "message": "Ce rôle est déjà connecté."})
                return
            canal.envoyer({"type": "bienvenue", "role": role})
            print(f"Client {role} connecté : {adresse[0]}:{adresse[1]}", flush=True)
            while not self.arret.is_set():
                message = self.recevoir(canal)
                if message is None:
                    break
                if message["type"] == "ping":
                    canal.envoyer({"type": "pong"})
                elif message["type"] == "etat":
                    canal.envoyer(self.obtenir_etat())
                elif message["type"] in ("detection_ambulance", "sortie_ambulance"):
                    canal.envoyer(self.traiter_detection(role, message))
                elif message["type"] == "occupation":
                    canal.envoyer(self.traiter_occupation(role, message))
                elif message["type"] == "lire_feux":
                    canal.envoyer(self.obtenir_feux())
                elif message["type"] == "quitter":
                    break
                else:
                    canal.envoyer({
                        "type": "erreur",
                        "message": "Commande non disponible : utilisez ping, etat ou quitter.",
                    })
        except (OSError, ValueError) as erreur:
            if not self.arret.is_set():
                print(f"Connexion {role or adresse} interrompue : {erreur}", flush=True)
        finally:
            with self.verrou:
                if role is not None and self.clients.get(role) is canal:
                    del self.clients[role]
                    if role == "capteur":
                        # Une perte du capteur ne prouve pas que l'ambulance est sortie.
                        self.detection_valide = False
                        self.carrefour_occupe = None
                        self.phase_feux = 5
                        self.fin_phase = time.monotonic() + 1
                self.connexions.discard(canal)
                self.threads.discard(threading.current_thread())
            canal.fermer()
            if role is not None:
                print(f"Client {role} déconnecté.", flush=True)

    def obtenir_etat(self):
        """Renvoie une copie de la liste des rôles connectés."""
        with self.verrou:
            connectes = sorted(self.clients)
            detection = {
                "direction": self.direction_ambulance,
                "valide": self.detection_valide,
                "revision": self.revision_detection,
            }
        return {
            "type": "etat",
            "clients": connectes,
            "nombre_clients": len(connectes),
            "simulation_connectee": False,
            "detection": detection,
        }

    def traiter_detection(self, role, message):
        """Valide un signal du capteur et conserve la direction de l'ambulance."""
        if role != "capteur":
            return {"type": "erreur", "message": "Seul le capteur peut signaler une détection."}
        direction = message.get("direction")
        if direction not in ("N", "S", "E", "O"):
            return {"type": "erreur", "message": "Direction attendue : N, S, E ou O."}
        arrivee = message["type"] == "detection_ambulance"
        with self.verrou:
            if arrivee:
                if self.direction_ambulance not in (None, direction):
                    return {"type": "erreur", "message": "Une autre ambulance est déjà signalée."}
                self.direction_ambulance = direction
            else:
                if self.direction_ambulance != direction:
                    return {"type": "erreur", "message": "Aucune ambulance signalée dans cette direction."}
                self.direction_ambulance = None
            self.detection_valide = True
            self.revision_detection += 1
            revision = self.revision_detection
        evenement = "arrivée" if arrivee else "sortie"
        print(f"Capteur : {evenement} ambulance depuis {direction}", flush=True)
        return {
            "type": "accuse_detection", "evenement": evenement,
            "direction": direction, "revision": revision,
        }

    def traiter_occupation(self, role, message):
        """Reçoit l'occupation ; un carrefour inconnu reste au rouge."""
        if role != "capteur" or type(message.get("occupe")) is not bool:
            return {"type": "erreur", "message": "Le capteur doit fournir occupe=true ou false."}
        with self.verrou:
            self.carrefour_occupe = message["occupe"]
        return {"type": "accuse_occupation", "occupe": message["occupe"]}

    def obtenir_feux(self, maintenant=None):
        """Calcule les feux. L'horloge peut être fournie pour les tests.

        Une transition au plus par appel évite de sauter l'orange après un
        retard. La zone occupée interdit de libérer l'autre axe.
        Pour cette étape, l'occupation est déclarée manuellement par le capteur.
        """
        maintenant = time.monotonic() if maintenant is None else maintenant
        with self.verrou:
            inconnu = ("capteur" not in self.clients or self.carrefour_occupe is None
                       or (self.direction_ambulance is not None and not self.detection_valide))
            direction = self.direction_ambulance
            cible = None if direction is None else (0 if direction in ("N", "S") else 3)
            raison = "Cycle normal"
            if inconnu:
                self.phase_feux = 5
                self.fin_phase = maintenant + 1
                raison = "Tout rouge : informations capteur indisponibles"
            elif cible is not None and self.phase_feux == cible:
                self.fin_phase = maintenant + 3
                raison = "Priorité maintenue jusqu'au signal de sortie"
            else:
                if cible is not None and self.phase_feux in (0, 3):
                    self.fin_phase = min(self.fin_phase, maintenant + 3)
                if maintenant >= self.fin_phase:
                    if self.phase_feux in (2, 5) and self.carrefour_occupe:
                        raison = "Tout rouge : carrefour encore occupé"
                    else:
                        if self.phase_feux in (2, 5) and cible is not None:
                            self.phase_feux = cible
                        else:
                            self.phase_feux = (self.phase_feux + 1) % len(PHASES)
                        self.fin_phase = maintenant + PHASES[self.phase_feux][2]
                if cible is not None and self.phase_feux != cible:
                    raison += " — préparation de la priorité ambulance"
            ns, eo, duree = PHASES[self.phase_feux]
            return {
                "type": "commande_feux",
                "feux": {"N": ns, "S": ns, "E": eo, "O": eo},
                "phase": self.phase_feux,
                "raison": raison,
                "carrefour_occupe": self.carrefour_occupe,
                "direction_ambulance": direction,
            }

    def arreter(self):
        """Signale l'arrêt et débloque les réceptions des clients."""
        self.arret.set()
        with self.verrou:
            connexions = list(self.connexions)
        for canal in connexions:
            canal.fermer()
        # accept() se termine au plus tard au prochain timeout de 0,5 seconde.


if __name__ == "__main__":
    arguments = argparse.ArgumentParser(description="Serveur TCP du carrefour")
    arguments.add_argument("--hote", default="127.0.0.1")
    arguments.add_argument("--port", type=int, default=PORT_SERVEUR)
    options = arguments.parse_args()
    try:
        Serveur(options.hote, options.port).demarrer()
    except OSError as erreur:
        raise SystemExit(f"Démarrage impossible : {erreur}")
