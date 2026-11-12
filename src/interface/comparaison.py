"""Expérience reproductible et export CSV des mesures."""

import csv
from uuid import uuid4
from PyQt6.QtCore import (
    QTimer,
)
from PyQt6.QtWidgets import (
    QLabel, QPushButton, QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QProgressBar,
)


class Comparaison(QDialog):
    """Rejoue deux fois un scénario reproductible avec le moteur de la maquette.

    Seule l'option de priorité change. Les tentatives d'arrivée sont identiques,
    mais leur admission peut varier selon les files ; on expose cette différence.
    QTimer fait avancer le calcul par petits lots pour garder la fenêtre réactive.
    """

    def __init__(self, parent, densite, direction, classe_fenetre):
        super().__init__(parent)
        self.setWindowTitle("Expérience — avec et sans priorité")
        self.resize(820, 610)
        self.densite = densite
        self.direction = direction
        self.graine = 2026
        self.tour = 0
        self.nombre_tours = 3000  # 120 secondes de simulation à 40 ms.
        self.resultats = []
        self.identifiant_bilan = str(uuid4())
        self.sauvegarde_en_cours = False
        self.bilan_sauve = False
        self.client_bdd = getattr(parent, "client_reseau", None)
        if self.client_bdd is not None and getattr(parent, "reseau_pret", False):
            self.client_bdd.reponse_bdd.connect(self.recevoir_bdd)
            self.client_bdd.erreur.connect(self.erreur_bdd)
            self.client_bdd.finished.connect(self.bdd_deconnectee)
        else:
            self.client_bdd = None
        self.lignes = []
        disposition = QVBoxLayout(self)
        titre = QLabel("La priorité fait-elle gagner du temps ?")
        titre.setStyleSheet("font-size: 22px; font-weight: bold; color: #176691")
        disposition.addWidget(titre)
        contexte = QLabel(
            f"Scénario : 120 s • Densité {densite} % • Ambulance depuis {direction}\n"
            "Ambulance demandée à 12 s • Piétons demandés à 24 s\n"
            "Même demande de trafic (graine 2026). Accidents désactivés dans ce test."
        )
        contexte.setWordWrap(True)
        disposition.addWidget(contexte)
        self.progression = QProgressBar()
        self.progression.setRange(0, self.nombre_tours)
        disposition.addWidget(self.progression)
        self.conclusion = QLabel("Calcul des deux simulations…")
        self.conclusion.setWordWrap(True)
        disposition.addWidget(self.conclusion)
        self.tableau = QTableWidget(0, 4)
        self.tableau.setHorizontalHeaderLabels(("Mesure", "Sans priorité", "Avec priorité", "Avec − sans"))
        self.tableau.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tableau.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        disposition.addWidget(self.tableau)
        note = QLabel(
            "L'attente automobile est le temps complètement arrêté, cumulé sur 120 s. "
            "Sa moyenne inclut toutes les voitures entrées, même encore présentes à la fin. "
            "Les arrivées refusées ne sont pas mises en file hors écran. "
            "Ces résultats décrivent ce scénario, pas une garantie pour un carrefour réel."
        )
        note.setWordWrap(True)
        disposition.addWidget(note)
        self.export = QPushButton("Exporter le bilan CSV")
        self.export.setEnabled(False)
        self.export.clicked.connect(self.exporter)
        disposition.addWidget(self.export)
        self.bouton_sauver = QPushButton("Enregistrer dans MariaDB")
        self.bouton_sauver.setEnabled(False)
        self.bouton_sauver.clicked.connect(self.sauver_bdd)
        disposition.addWidget(self.bouton_sauver)
        self.etat_bdd = QLabel("Connecter la maquette au serveur avant la comparaison pour sauvegarder." if self.client_bdd is None else "Sauvegarde automatique à la fin du calcul.")
        self.etat_bdd.setWordWrap(True)
        disposition.addWidget(self.etat_bdd)
        fermer = QPushButton("Fermer et reprendre la simulation")
        fermer.clicked.connect(self.reject)
        disposition.addWidget(fermer)

        self.simulations = []
        for priorite in (False, True):
            simulation = classe_fenetre(densite, self.graine, mode_comparaison=True)
            simulation.option_priorite.setChecked(priorite)
            simulation.accidents_aleatoires.setChecked(False)
            simulation.choix_direction.setCurrentIndex(
                simulation.choix_direction.findData(direction)
            )
            self.simulations.append(simulation)
        self.calcul = QTimer(self)
        self.calcul.timeout.connect(self.calculer_lot)
        self.calcul.start(1)

    def calculer_lot(self):
        """Avance les deux expériences d'une seconde simulée à chaque lot."""
        for _ in range(25):
            if self.tour >= self.nombre_tours:
                self.calcul.stop()
                self.terminer()
                return
            for simulation in self.simulations:
                if self.tour == 300:  # 12 secondes.
                    simulation.demander_ambulance()
                if self.tour == 600:  # 24 secondes.
                    simulation.demander_pietons()
                simulation.pas_local()
            self.tour += 1
        self.progression.setValue(self.tour)

    def terminer(self):
        """Calcule les résultats sans imposer qu'une priorité soit bénéfique."""
        for simulation in self.simulations:
            self.resultats.append({
                "mission": simulation.duree_mission,
                "attente": simulation.attente_voitures,
                "moyenne": simulation.attente_voitures / max(1, simulation.voitures_entrees),
                "pietons": simulation.attente_pietons,
                "demandes": simulation.nombre_demandes,
                "entrees": simulation.voitures_entrees,
                "sorties": simulation.voitures_sorties,
                "refusees": simulation.arrivees_refusees,
            })
        sans, avec = self.resultats
        mesures = (
            ("Ambulance : demande → sortie", "mission", "s"),
            ("Attente cumulée des voitures", "attente", "s"),
            ("Attente moyenne par voiture entrée", "moyenne", "s"),
            ("Piétons : demande → début", "pietons", "s"),
            ("Demandes d'arrivée de voitures", "demandes", ""),
            ("Voitures entrées", "entrees", ""),
            ("Voitures sorties de l'écran", "sorties", ""),
            ("Arrivées refusées (entrée occupée)", "refusees", ""),
        )
        self.tableau.setRowCount(len(mesures))
        for ligne, (nom, cle, unite) in enumerate(mesures):
            a, b = sans[cle], avec[cle]
            difference = None if a is None or b is None else b - a
            self.lignes.append((nom, a, b, difference, unite))
            valeurs = [nom]
            for valeur in (a, b, difference):
                if valeur is None:
                    valeurs.append("Non terminé")
                elif unite:
                    valeurs.append(f"{valeur:.2f} {unite}")
                else:
                    valeurs.append(str(int(valeur)))
            for colonne, texte in enumerate(valeurs):
                self.tableau.setItem(ligne, colonne, QTableWidgetItem(texte))
        if sans["mission"] is None or avec["mission"] is None:
            bilan = "Au moins une mission n'est pas terminée en 120 s : gain non calculable."
        else:
            gain = sans["mission"] - avec["mission"]
            pourcentage = 100 * gain / sans["mission"]
            if gain > 0.01:
                bilan = f"Ambulance : {gain:.2f} s gagnées ({pourcentage:.1f} %) avec la priorité."
            elif gain < -0.01:
                bilan = f"Dans ce scénario, la priorité prend {-gain:.2f} s de plus."
            else:
                bilan = "Dans ce scénario, la priorité ne change pas le temps de l'ambulance."
        self.conclusion.setText(bilan)
        self.export.setEnabled(True)
        self.progression.setValue(self.nombre_tours)
        self.liberer_simulations()
        if self.client_bdd is not None:
            self.sauver_bdd()

    def sauver_bdd(self):
        """Le même UUID évite les doublons lors d'une nouvelle tentative."""
        if self.client_bdd is None or self.sauvegarde_en_cours or self.bilan_sauve:
            return
        bilan = {"identifiant": self.identifiant_bilan, "densite": self.densite,
                 "direction": self.direction, "graine": self.graine, "duree_s": 120,
                 "version_modele": "carrefour-40ms-v1", "resultats": self.resultats}
        self.sauvegarde_en_cours = True
        self.bouton_sauver.setEnabled(False)
        self.etat_bdd.setText("Enregistrement dans MariaDB…")
        try:
            self.client_bdd.demander_bdd({"type": "sauver_comparaison", "bilan": bilan})
        except ValueError as erreur:
            self.erreur_bdd(str(erreur))

    def recevoir_bdd(self, reponse):
        if reponse.get("operation") != "sauver_comparaison" or not self.sauvegarde_en_cours:
            return
        if reponse["type"] == "comparaison_sauvee":
            self.sauvegarde_en_cours = False
            self.bilan_sauve = True
            self.etat_bdd.setText(f"Comparaison n°{reponse['id']} enregistrée dans MariaDB.")
        else:
            self.erreur_bdd(reponse.get("message", "Enregistrement non confirmé"))

    def erreur_bdd(self, message):
        if self.bilan_sauve:
            return
        self.sauvegarde_en_cours = False
        self.etat_bdd.setText(f"Sauvegarde non confirmée : {message}. Le CSV reste disponible.")
        self.bouton_sauver.setEnabled(self.client_bdd is not None and len(self.resultats) == 2)

    def bdd_deconnectee(self):
        self.client_bdd = None
        if not self.bilan_sauve:
            self.erreur_bdd("serveur déconnecté")
        self.bouton_sauver.setEnabled(False)

    def enregistrer_csv(self, chemin):
        """Écrit les paramètres et les mesures, sans dépendance supplémentaire."""
        with open(chemin, "w", encoding="utf-8-sig", newline="") as fichier:
            writer = csv.writer(fichier, delimiter=";")
            writer.writerow(("Paramètre", "Valeur"))
            for ligne in (("Densité (%)", self.densite), ("Direction", self.direction),
                          ("Graine", self.graine), ("Durée (s)", 120),
                          ("Demande ambulance (s)", 12), ("Demande piétons (s)", 24),
                          ("Accidents", "Désactivés"),
                          ("Attente voitures", "Temps arrêté des véhicules admis, sur 120 s"),
                          ("Arrivées refusées", "Non mises en file hors écran")):
                writer.writerow(ligne)
            writer.writerow(())
            writer.writerow(("Mesure", "Sans priorité", "Avec priorité", "Avec moins sans", "Unité"))
            for ligne in self.lignes:
                writer.writerow(["Non terminé" if v is None else round(v, 3)
                                 if isinstance(v, float) else v for v in ligne])

    def exporter(self):
        """Laisse choisir où sauvegarder le bilan pour le rapport du projet."""
        chemin, _ = QFileDialog.getSaveFileName(self, "Exporter le bilan", "comparaison.csv", "CSV (*.csv)")
        if not chemin:
            return
        try:
            self.enregistrer_csv(chemin)
        except OSError as erreur:
            QMessageBox.warning(self, "Export impossible", str(erreur))
        else:
            QMessageBox.information(self, "Export terminé", "Le bilan a été enregistré.")

    def liberer_simulations(self):
        """Ferme les deux fenêtres de calcul non affichées."""
        for simulation in self.simulations:
            simulation.close()
            simulation.deleteLater()
        self.simulations.clear()

    def done(self, resultat):
        """Interrompt aussi le calcul si l'utilisateur ferme avant la fin."""
        if self.sauvegarde_en_cours:
            self.etat_bdd.setText("Attendre la réponse du serveur avant de fermer…")
            return
        self.calcul.stop()
        self.liberer_simulations()
        # Le dialogue reste parfois vivant après exec : retirer les abonnements.
        if self.client_bdd is not None:
            self.client_bdd.reponse_bdd.disconnect(self.recevoir_bdd)
            self.client_bdd.erreur.disconnect(self.erreur_bdd)
            self.client_bdd.finished.disconnect(self.bdd_deconnectee)
            self.client_bdd = None
        super().done(resultat)


