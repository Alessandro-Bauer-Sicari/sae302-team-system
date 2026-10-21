"""Client capteur : simulation manuelle des signaux d'arrivée et de sortie.

Depuis la racine : python -m src.clients.capteur
Sur une autre machine : ajouter --hote ADRESSE_IP_DU_SERVEUR.
Le client générique client.py et le module reseau.py sont nécessaires.

Cette étape vérifie la transmission des détections. Les commandes saisies
ne font pas apparaître de véhicule dans la maquette. Elles influencent
le client feux par le serveur ; la maquette graphique reste indépendante.
Les détections seront ensuite produites automatiquement par la simulation.
"""

import argparse

if __package__:
    from .client import Client
    from ..reseau import PORT_SERVEUR
else:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.clients.client import Client
    from src.reseau import PORT_SERVEUR


class Capteur(Client):
    """Envoie les informations d'une ambulance à la fois."""

    def __init__(self, hote="127.0.0.1", port=PORT_SERVEUR):
        super().__init__("capteur", hote, port)

    def signaler(self, direction, arrivee=True):
        """Transmet une arrivée ou une sortie et vérifie son accusé de réception."""
        if direction not in ("N", "S", "E", "O"):
            raise ValueError("Direction attendue : N, S, E ou O.")
        type_message = "detection_ambulance" if arrivee else "sortie_ambulance"
        reponse = self.echanger({"type": type_message, "direction": direction})
        if reponse["type"] == "erreur":
            raise ValueError(reponse.get("message", "Détection refusée."))
        evenement = "arrivée" if arrivee else "sortie"
        if (reponse["type"] != "accuse_detection"
                or reponse.get("direction") != direction
                or reponse.get("evenement") != evenement
                or type(reponse.get("revision")) is not int):
            self.fermer()
            raise ConnectionError("Accusé de réception inattendu.")
        return reponse


    def signaler_occupation(self, occupe):
        """Indique si des usagers sont encore dans la zone de traversée."""
        if type(occupe) is not bool:
            raise ValueError("L'occupation doit être un booléen.")
        reponse = self.echanger({"type": "occupation", "occupe": occupe})
        if reponse.get("type") != "accuse_occupation" or reponse.get("occupe") != occupe:
            raise ValueError(reponse.get("message", "Occupation refusée."))
        return reponse


def afficher_detection(etat):
    """Distingue une absence confirmée d'une information indisponible."""
    detection = etat.get("detection")
    if not isinstance(detection, dict):
        print("Le serveur doit être mis à jour pour recevoir les détections.")
    elif not detection.get("valide"):
        print("Détection non confirmée. Dernière direction connue :", detection.get("direction"))
    elif detection.get("direction") is None:
        print("Sortie confirmée : aucune ambulance signalée.")
    else:
        print("Ambulance signalée depuis :", detection["direction"])


def lancer_capteur(hote, port):
    """Permet de tester le capteur depuis un terminal."""
    capteur = Capteur(hote, port)
    try:
        capteur.connecter()
        print("Capteur connecté. Commandes : libre, occupe, arrivee N, sortie N, etat, quitter.")
        print("Directions disponibles : N, S, E, O. Détections manuelles pour ce test.")
        while True:
            mots = input("capteur> ").strip().lower().split()
            if mots == ["quitter"]:
                return 0
            if mots in (["libre"], ["occupe"]):
                capteur.signaler_occupation(mots == ["occupe"])
                print("Occupation confirmée par le serveur.")
            elif mots == ["etat"]:
                afficher_detection(capteur.obtenir_etat())
            elif len(mots) == 2 and mots[0] in ("arrivee", "sortie"):
                try:
                    reponse = capteur.signaler(mots[1].upper(), mots[0] == "arrivee")
                    print(f"Serveur : {reponse['evenement']} confirmée, direction {reponse['direction']}.")
                except ValueError as erreur:
                    print(f"Signal refusé : {erreur}")
                    if capteur.canal is None:
                        return 1
            elif mots:
                print("Utilise libre, occupe, arrivee N, sortie N, etat ou quitter (N/S/E/O).")
    except (KeyboardInterrupt, EOFError):
        print("\nFermeture du capteur.")
        return 0
    except (OSError, ValueError) as erreur:
        print(f"Erreur : {erreur}")
        return 1
    finally:
        capteur.fermer()


if __name__ == "__main__":
    arguments = argparse.ArgumentParser(description="Capteur TCP du carrefour")
    arguments.add_argument("--hote", default="127.0.0.1")
    arguments.add_argument("--port", type=int, default=PORT_SERVEUR)
    options = arguments.parse_args()
    if not 1 <= options.port <= 65535:
        arguments.error("Le port doit être compris entre 1 et 65535.")
    raise SystemExit(lancer_capteur(options.hote, options.port))
