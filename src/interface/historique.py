"""Consultation des résultats conservés dans MariaDB, via le serveur TCP."""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                            QTableWidget, QTableWidgetItem, QHeaderView)


class Historique(QDialog):
    def __init__(self, parent, client):
        super().__init__(parent)
        self.client = client
        self.en_cours = False
        self.setWindowTitle("Historique MariaDB — 50 dernières comparaisons")
        self.resize(1100, 600)
        disposition = QVBoxLayout(self)
        self.etat = QLabel("Chargement…")
        self.etat.setWordWrap(True)
        disposition.addWidget(self.etat)
        self.colonnes = (("id", "N°"), ("date_utc", "Date UTC"),
                         ("densite", "Densité %"), ("direction", "Direction"),
                         ("priorite", "Priorité"), ("mission_s", "Mission s"),
                         ("attente_s", "Attente cumulée s"), ("moyenne_s", "Moyenne s"),
                         ("pietons_s", "Attente piétons s"), ("demandes", "Demandes"),
                         ("entrees", "Entrées"), ("sorties", "Sorties"),
                         ("refusees", "Refusées"), ("graine", "Graine"),
                         ("duree_s", "Durée s"), ("version_modele", "Modèle"))
        self.tableau = QTableWidget(0, len(self.colonnes))
        self.tableau.setHorizontalHeaderLabels([nom for _, nom in self.colonnes])
        self.tableau.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tableau.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        disposition.addWidget(self.tableau)
        self.actualiser = QPushButton("Actualiser")
        self.actualiser.clicked.connect(self.charger)
        disposition.addWidget(self.actualiser)
        fermer = QPushButton("Fermer")
        fermer.clicked.connect(self.reject)
        disposition.addWidget(fermer)
        self.client.reponse_bdd.connect(self.recevoir)
        self.client.erreur.connect(self.erreur)
        self.client.finished.connect(self.deconnecte)
        self.charger()

    def charger(self):
        if self.client is None or self.en_cours:
            return
        self.en_cours = True
        self.actualiser.setEnabled(False)
        self.etat.setText("Lecture de MariaDB…")
        try:
            self.client.demander_bdd({"type": "historique"})
        except ValueError as erreur:
            self.erreur(str(erreur))

    def recevoir(self, reponse):
        if reponse.get("operation") != "historique" or not self.en_cours:
            return
        if reponse["type"] != "historique":
            self.erreur(reponse.get("message", "Réponse invalide"))
            return
        self.en_cours = False
        self.actualiser.setEnabled(True)
        lignes = reponse["lignes"]
        self.tableau.setRowCount(len(lignes))
        for i, ligne in enumerate(lignes):
            for j, (cle, _) in enumerate(self.colonnes):
                valeur = ligne[cle]
                if cle == "priorite":
                    texte = "Avec" if valeur else "Sans"
                elif valeur is None:
                    texte = "Non terminé"
                elif isinstance(valeur, float):
                    texte = f"{valeur:.2f}"
                else:
                    texte = str(valeur)
                self.tableau.setItem(i, j, QTableWidgetItem(texte))
        self.etat.setText(f"{len(lignes) // 2} comparaison(s) enregistrée(s). Deux lignes par comparaison ; dates UTC.")

    def erreur(self, message):
        self.en_cours = False
        self.etat.setText(f"Historique indisponible : {message}")
        self.actualiser.setEnabled(self.client is not None)

    def deconnecte(self):
        self.client = None
        self.erreur("serveur déconnecté")

    def done(self, resultat):
        if self.en_cours:
            self.etat.setText("Attendre la réponse du serveur avant de fermer…")
            return
        if self.client is not None:
            self.client.reponse_bdd.disconnect(self.recevoir)
            self.client.erreur.disconnect(self.erreur)
            self.client.finished.disconnect(self.deconnecte)
            self.client = None
        super().done(resultat)
