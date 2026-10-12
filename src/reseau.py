"""Échanges JSON sur une connexion TCP déjà établie.

À placer dans src/reseau.py. Aucune bibliothèque à installer.
Un message est un dictionnaire avec un champ « type » non vide.
Chaque message JSON se termine par un saut de ligne.

Exemples de messages :
    {"type": "bonjour", "role": "regulateur"}
    {"type": "demande_ambulance", "direction": "N"}

Ce module transporte les messages. Le serveur vérifiera les commandes.
Les appels réseau sont bloquants : ils devront être utilisés dans un thread,
jamais directement dans la boucle d'affichage de la fenêtre Qt.
"""

import json
import socket
import threading


PORT_SERVEUR = 5000
TAILLE_MAX_MESSAGE = 65536  # Nombre maximal d'octets, hors saut de ligne.


def verifier_message(message):
    """Vérifie la structure commune des messages avant leur utilisation."""
    if not isinstance(message, dict):
        raise ValueError("Le message doit être un dictionnaire JSON.")
    if not isinstance(message.get("type"), str) or not message["type"].strip():
        raise ValueError("Le message doit contenir un champ 'type' non vide.")


def refuser_constante(valeur):
    """Refuse NaN et Infinity, qui ne font pas partie du JSON standard."""
    raise ValueError(f"Constante JSON interdite : {valeur}")


class ConnexionJSON:
    """Envoie et reçoit des messages sur une socket connectée.

    Conserver une instance par connexion : son tampon garde les morceaux
    reçus en avance. Un seul thread doit appeler recevoir(). Plusieurs
    threads peuvent appeler envoyer(), grâce au verrou d'envoi.

    Après une erreur de protocole ou d'envoi, fermer cette connexion.
    Un socket.timeout pendant recevoir() conserve le tampon : on peut réessayer.
    """

    def __init__(self, connexion):
        self.connexion = connexion
        self.tampon = bytearray()
        self.verrou_envoi = threading.Lock()

    def envoyer(self, message):
        """Encode un dictionnaire en UTF-8 et envoie la totalité du message."""
        verifier_message(message)
        texte = json.dumps(message, ensure_ascii=False, allow_nan=False)
        donnees = texte.encode("utf-8")
        if len(donnees) > TAILLE_MAX_MESSAGE:
            raise ValueError("Message trop volumineux.")
        with self.verrou_envoi:
            self.connexion.sendall(donnees + b"\n")

    def recevoir(self):
        """Attend un message complet ; renvoie None si l'autre côté ferme.

        TCP peut couper un message ou en regrouper plusieurs. On accumule
        donc les octets jusqu'au premier saut de ligne et on garde la suite.
        """
        while True:
            fin = self.tampon.find(b"\n")
            if fin >= 0:
                if fin > TAILLE_MAX_MESSAGE:
                    raise ValueError("Message reçu trop volumineux.")
                donnees = bytes(self.tampon[:fin])
                del self.tampon[:fin + 1]
                try:
                    message = json.loads(
                        donnees.decode("utf-8"), parse_constant=refuser_constante
                    )
                except (UnicodeDecodeError, ValueError, RecursionError) as erreur:
                    raise ValueError("Message JSON invalide.") from erreur
                verifier_message(message)
                return message

            if len(self.tampon) > TAILLE_MAX_MESSAGE:
                raise ValueError("Message reçu trop volumineux.")
            morceau = self.connexion.recv(4096)
            if not morceau:
                if self.tampon:
                    raise ConnectionError("Connexion fermée au milieu d'un message.")
                return None
            self.tampon.extend(morceau)

    def fermer(self):
        """Ferme la connexion et réveille une éventuelle réception en attente."""
        try:
            self.connexion.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass  # L'autre côté peut déjà avoir fermé la connexion.
        self.connexion.close()


if __name__ == "__main__":
    print("Module réseau prêt : il sera importé par le serveur et les clients.")
