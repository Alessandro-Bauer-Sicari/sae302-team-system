"""Connexion au serveur dans un thread, sans bloquer la fenêtre PyQt6.

Le thread utilise le client TCP existant. Il transmet les résultats à la
fenêtre par des signaux : il ne modifie jamais directement les widgets.
Cette étape lit l'état des connexions, sans commander la simulation.
"""

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from .client import Client


class ClientReseauQt(QThread):
    """Connecte le régulateur et demande l'état du serveur toutes les 2 s."""

    connecte = pyqtSignal()
    etat_recu = pyqtSignal(dict)
    erreur = pyqtSignal(str)

    def __init__(self, hote, port, parent=None):
        super().__init__(parent)
        self.hote = hote
        self.port = port
        self.arret = threading.Event()

    def run(self):
        """Exécute tous les échanges TCP dans le thread réseau."""
        client = Client("regulateur", self.hote, self.port)
        try:
            if self.arret.is_set():
                return
            client.connecter()
            if self.arret.is_set():
                return
            self.connecte.emit()
            while not self.arret.is_set():
                etat = client.obtenir_etat()
                if not self.arret.is_set():
                    self.etat_recu.emit(etat)
                # Event.wait permet un arrêt immédiat entre deux échanges.
                if self.arret.wait(2):
                    break
        except (OSError, ValueError) as erreur:
            if not self.arret.is_set():
                self.erreur.emit(str(erreur))
        finally:
            client.fermer()

    def arreter(self):
        """Demande l'arrêt ; un échange en cours finit ou atteint son timeout."""
        self.arret.set()
