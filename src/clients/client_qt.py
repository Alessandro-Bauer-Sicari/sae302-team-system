"""Trois clients TCP, sans accès aux widgets depuis le thread réseau."""
import queue
import threading
from PyQt6.QtCore import QThread, pyqtSignal
from .client import Client
from ..controleur import verifier_commande


class ClientReseauQt(QThread):
    connecte = pyqtSignal()
    etat_recu = pyqtSignal(dict)
    erreur = pyqtSignal(str)
    reponse_bdd = pyqtSignal(dict)

    def __init__(self, hote, port, parent=None):
        super().__init__(parent)
        self.hote, self.port = hote, port
        self.arret = threading.Event()
        self.demandes = queue.Queue(maxsize=4)

    def proposer(self, mesure):
        """La fenêtre n'envoie qu'une mesure à la fois."""
        self.demandes.put_nowait({"type": "mesure", "mesure": mesure})

    def demander_bdd(self, message):
        """Appel non bloquant, depuis un dialogue qui suspend la simulation."""
        if self.arret.is_set() or not self.isRunning():
            raise ValueError("Connexion au serveur interrompue")
        try:
            self.demandes.put_nowait(message)
        except queue.Full:
            raise ValueError("Une demande est déjà en attente") from None

    def run(self):
        clients = {role: Client(role, self.hote, self.port)
                   for role in ("regulateur", "capteur", "feux")}
        def demander(role, message, attendu):
            reponse = clients[role].echanger(message)
            if reponse["type"] != attendu:
                raise ValueError(reponse.get("message", "Réponse réseau inattendue"))
            if "revision" in message and reponse.get("revision") != message["revision"]:
                raise ValueError("Réponse périmée")
            return reponse
        try:
            for client in clients.values():
                if self.arret.is_set():
                    return
                client.connecter()
            demander("regulateur", {"type": "initialiser"}, "initialise")
            self.connecte.emit()
            revision = 0
            while not self.arret.is_set():
                try:
                    demande = self.demandes.get(timeout=0.1)
                except queue.Empty:
                    continue
                if demande["type"] != "mesure":
                    reponse = clients["regulateur"].echanger(demande)
                    if reponse["type"] not in ("comparaison_sauvee", "historique", "erreur_bdd"):
                        reponse = {"type": "erreur_bdd", "message": "Version du serveur incompatible : installer la version BDD"}
                    reponse["operation"] = demande["type"]
                    if not self.arret.is_set():
                        self.reponse_bdd.emit(reponse)
                    continue
                mesure = demande["mesure"]
                revision += 1
                demander("capteur", {"type": "mesure", "revision": revision,
                                     "mesure": mesure}, "mesure_recue")
                demander("regulateur", {"type": "calculer", "revision": revision}, "calcul_termine")
                commande = demander("feux", {"type": "commande", "revision": revision}, "commande")
                verifier_commande(commande)
                if not self.arret.is_set():
                    self.etat_recu.emit(commande)
        except (OSError, ValueError) as erreur:
            if not self.arret.is_set():
                self.erreur.emit(str(erreur))
        finally:
            for client in clients.values():
                client.fermer()

    def arreter(self):
        """Les sockets ont un délai maximal de réponse de cinq secondes."""
        self.arret.set()
