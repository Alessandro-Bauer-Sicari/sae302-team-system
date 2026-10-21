"""Client feux : applique et affiche les commandes reçues du serveur.

Lancement : python -m src.clients.feux [--hote IP_DU_SERVEUR]
Le client capteur doit déclarer libre pour autoriser le cycle.
Ce terminal représente les feux réseau ; il ne pilote pas encore le dessin Qt.
"""

import argparse
import time

if __package__:
    from .client import Client
    from ..reseau import PORT_SERVEUR
else:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.clients.client import Client
    from src.reseau import PORT_SERVEUR


class Feux(Client):
    """Reçoit les quatre couleurs ; revient au rouge sur erreur de connexion."""

    def __init__(self, hote="127.0.0.1", port=PORT_SERVEUR):
        super().__init__("feux", hote, port)
        self.couleurs = dict.fromkeys(("N", "S", "E", "O"), "rouge")

    def actualiser(self):
        """Valide les couleurs avant de les appliquer au client simulé."""
        try:
            reponse = self.echanger({"type": "lire_feux"})
            couleurs = reponse.get("feux")
            if (reponse["type"] != "commande_feux" or not isinstance(couleurs, dict)
                    or set(couleurs) != {"N", "S", "E", "O"}
                    or any(c not in ("rouge", "orange", "vert") for c in couleurs.values())
                    or couleurs["N"] != couleurs["S"] or couleurs["E"] != couleurs["O"]
                    or (couleurs["N"] != "rouge" and couleurs["E"] != "rouge")):
                raise ValueError("Commande de feux incohérente.")
            self.couleurs = couleurs.copy()
            return reponse
        except BaseException:
            self.couleurs = dict.fromkeys(("N", "S", "E", "O"), "rouge")
            self.fermer()
            raise


def lancer_feux(hote, port):
    """Actualise les feux cinq fois par seconde et affiche les changements."""
    client = Feux(hote, port)
    try:
        client.connecter()
        print("Feux connectés. Arrêt : Ctrl+C. En attente du capteur…", flush=True)
        dernier_affichage = None
        while True:
            commande = client.actualiser()
            affichage = (tuple(client.couleurs.values()), commande.get("raison"))
            if affichage != dernier_affichage:
                print(" | ".join(f"{d} : {c}" for d, c in client.couleurs.items()),
                      "—", commande.get("raison", ""), flush=True)
                dernier_affichage = affichage
            time.sleep(0.2)
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError) as erreur:
        print(f"Erreur réseau : {erreur}", flush=True)
        return 1
    finally:
        client.couleurs = dict.fromkeys(("N", "S", "E", "O"), "rouge")
        client.fermer()
        print("Client arrêté : tous ses feux sont rouges.", flush=True)


if __name__ == "__main__":
    arguments = argparse.ArgumentParser(description="Client feux du carrefour")
    arguments.add_argument("--hote", default="127.0.0.1")
    arguments.add_argument("--port", type=int, default=PORT_SERVEUR)
    options = arguments.parse_args()
    if not 1 <= options.port <= 65535:
        arguments.error("Le port doit être compris entre 1 et 65535.")
    raise SystemExit(lancer_feux(options.hote, options.port))
