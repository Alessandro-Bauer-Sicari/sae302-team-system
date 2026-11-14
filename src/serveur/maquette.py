"""Échanges ordonnés capteur → régulateur → feux.

Le serveur reçoit une photographie, calcule une seule étape, puis fournit
la commande. La photographie suivante confirme implicitement son application.
Aucun véhicule n'avance dans l'attente d'une réponse : pas de mesure périmée.
Toutes les méthodes sont appelées sous le verrou du serveur.
"""
from ..controleur import Controleur, verifier_mesure


class Maquette:
    """Coordonne les étapes mesure, calcul et commande d'une session réseau."""
    def __init__(self):
        """Crée le contrôleur et attend la première mesure de la session."""
        self.controleur = Controleur()
        self.revision = 0
        self.etape = "mesure"
        self.mesure = None
        self.commande = None

    def traiter(self, role, message):
        """Traite un message en vérifiant le rôle et l'ordre des étapes.

        Args:
            role (str): Rôle du client qui envoie le message.
            message (dict): Message de mesure, de calcul ou de commande
                contenant un numéro de révision.

        Returns:
            dict: Accusé de réception ou commande des feux pour cette révision.

        Raises:
            ValueError: Si le rôle, la révision ou l'ordre des étapes est invalide.
        """
        revision = message.get("revision")
        if type(revision) is not int:
            raise ValueError("Révision entière obligatoire")
        if message["type"] == "mesure":
            if role != "capteur" or self.etape != "mesure" or revision != self.revision + 1:
                raise ValueError("Mesure désordonnée ou rôle incorrect")
            verifier_mesure(message.get("mesure"))
            self.mesure = message["mesure"].copy()
            self.revision = revision
            self.etape = "calcul"
            return {"type": "mesure_recue", "revision": revision}
        if revision != self.revision:
            raise ValueError("Révision périmée")
        if message["type"] == "calculer":
            if role != "regulateur" or self.etape != "calcul":
                raise ValueError("Calcul désordonné ou rôle incorrect")
            self.commande = self.controleur.avancer(self.mesure)
            self.etape = "feux"
            return {"type": "calcul_termine", "revision": revision}
        if message["type"] == "commande":
            if role != "feux" or self.etape != "feux":
                raise ValueError("Lecture désordonnée ou rôle incorrect")
            self.etape = "mesure"
            return {"type": "commande", "revision": revision, **self.commande}
        raise ValueError("Message inconnu")
