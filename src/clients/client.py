"""Client de test TCP pour le serveur du carrefour connecté.

À placer dans src/clients/client.py.
Depuis la racine du projet, après avoir lancé le serveur :
    python -m src.clients.client --role regulateur
    python -m src.clients.client --role capteur
    python -m src.clients.client --role feux

Sur un autre ordinateur, ajouter --hote ADRESSE_IP_DU_SERVEUR.
Les commandes disponibles sont ping, etat, aide et quitter.
Cette étape teste le réseau ; elle ne commande pas encore la maquette.
"""

import argparse
import socket

if __package__:
    from ..reseau import ConnexionJSON, PORT_SERVEUR
else:
    # Permet aussi : python src/clients/client.py --role regulateur
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from reseau import ConnexionJSON, PORT_SERVEUR


ROLES = ("regulateur", "capteur", "feux")
DELAI_REPONSE = 5  # Secondes avant de signaler un serveur qui ne répond pas.


class Client:
    """Une connexion et des échanges demande/réponse, utilisés par un seul thread.

    Ces méthodes sont bloquantes. Pour la future interface Qt, elles devront
    être appelées dans un thread réseau, pas dans le thread de la fenêtre.
    """

    def __init__(self, role, hote="127.0.0.1", port=PORT_SERVEUR):
        if role not in ROLES:
            raise ValueError("Rôle inconnu : choisir regulateur, capteur ou feux.")
        self.role = role
        self.hote = hote
        self.port = port
        self.canal = None

    def connecter(self):
        """Ouvre la connexion puis attend que le serveur accepte le rôle."""
        if self.canal is not None:
            raise RuntimeError("Ce client est déjà connecté.")
        connexion = socket.create_connection(
            (self.hote, self.port), timeout=DELAI_REPONSE
        )
        self.canal = ConnexionJSON(connexion)
        try:
            reponse = self.echanger({"type": "bonjour", "role": self.role})
            if reponse["type"] == "erreur":
                raise ConnectionError(reponse.get("message", "Connexion refusée."))
            if reponse["type"] != "bienvenue" or reponse.get("role") != self.role:
                raise ConnectionError("Réponse d'identification inattendue.")
        except BaseException:
            self.fermer()
            raise

    def echanger(self, message):
        """Envoie une demande et attend sa réponse complète."""
        if self.canal is None:
            raise ConnectionError("Le client n'est pas connecté.")
        try:
            self.canal.envoyer(message)
            reponse = self.canal.recevoir()
            if reponse is None:
                raise ConnectionError("Le serveur a fermé la connexion.")
            return reponse
        except BaseException:
            # Après une interruption, une réponse tardive ne doit pas être
            # confondue avec la réponse à une nouvelle demande.
            self.fermer()
            raise

    def ping(self):
        """Vérifie que le serveur répond au message de test."""
        reponse = self.echanger({"type": "ping"})
        if reponse["type"] != "pong":
            self.fermer()
            raise ConnectionError("Le serveur n'a pas répondu pong.")
        return reponse

    def obtenir_etat(self):
        """Demande les rôles connectés et l'état du raccordement à la maquette."""
        reponse = self.echanger({"type": "etat"})
        if (reponse["type"] != "etat"
                or not isinstance(reponse.get("clients"), list)
                or any(role not in ROLES for role in reponse["clients"])
                or type(reponse.get("nombre_clients")) is not int
                or reponse["nombre_clients"] != len(reponse["clients"])
                or type(reponse.get("simulation_connectee")) is not bool):
            self.fermer()
            raise ConnectionError("État reçu invalide.")
        return reponse

    def fermer(self):
        """Ferme la socket ; le serveur libère alors le rôle de ce client."""
        if self.canal is not None:
            self.canal.fermer()
            self.canal = None


def afficher_etat(etat):
    """Présente la réponse du serveur dans le terminal."""
    print(f"Clients connectés : {etat['nombre_clients']}")
    for role in etat["clients"]:
        print(f"  - {role}")
    if etat["simulation_connectee"]:
        print("Maquette reliée au serveur.")
    else:
        print("Réseau disponible ; maquette pas encore reliée au serveur.")


def lancer_client(role, hote, port):
    """Ouvre une session interactive et ferme proprement la connexion."""
    client = Client(role, hote, port)
    try:
        client.connecter()
        print(f"Connecté à {hote}:{port} avec le rôle {role}.")
        print("Commandes : ping, etat, aide, quitter.")
        while True:
            commande = input(f"{role}> ").strip().lower()
            if commande == "quitter":
                break
            if commande == "ping":
                client.ping()
                print("Pong reçu : le serveur répond.")
            elif commande == "etat":
                afficher_etat(client.obtenir_etat())
            elif commande == "aide":
                print("ping : tester la connexion ; etat : voir les clients ; quitter : fermer.")
            elif commande:
                print("Commande inconnue. Tape aide pour voir les commandes.")
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nFermeture du client.")
        return 0
    except (OSError, ValueError) as erreur:
        print(f"Erreur réseau : {erreur}")
        print("Vérifie le serveur, son adresse IP et le port, puis relance le client.")
        return 1
    finally:
        client.fermer()


if __name__ == "__main__":
    arguments = argparse.ArgumentParser(description="Client TCP du carrefour connecté")
    arguments.add_argument("--role", required=True, choices=ROLES)
    arguments.add_argument("--hote", default="127.0.0.1")
    arguments.add_argument("--port", type=int, default=PORT_SERVEUR)
    options = arguments.parse_args()
    if not 1 <= options.port <= 65535:
        arguments.error("Le port doit être compris entre 1 et 65535.")
    raise SystemExit(lancer_client(options.role, options.hote, options.port))
