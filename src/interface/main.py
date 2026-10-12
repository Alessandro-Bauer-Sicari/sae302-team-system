"""Point d'entrée et commandes de la fenêtre.

Depuis la racine du dépôt : python src/interface/main.py
Les deux classes DessinCarrefour et SimulationCarrefour regroupent les
méthodes qui utilisent cette même fenêtre (self).
"""

import sys
import random
from PyQt6.QtCore import (
    Qt, QTimer,
)
from PyQt6.QtGui import (
    QPainter,
)
from PyQt6.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QMainWindow, QLabel, QSlider, QToolBar, QPushButton, QComboBox, QCheckBox, QDockWidget, QPlainTextEdit,
)
if __package__:
    from .parametres import (PAS_TEMPS, PHASES, TAILLE)
else:
    from parametres import (PAS_TEMPS, PHASES, TAILLE)


if __package__:
    from .dessin import DessinCarrefour
    from .simulation import SimulationCarrefour
    from .comparaison import Comparaison
else:
    from dessin import DessinCarrefour
    from simulation import SimulationCarrefour
    from comparaison import Comparaison


class FenetrePrincipale(DessinCarrefour, SimulationCarrefour, QMainWindow):
    """Assemble le dessin, la simulation et les commandes utilisateur."""

    def __init__(self, densite=45, graine=None, mode_comparaison=False):
        super().__init__()
        self.mode_comparaison = mode_comparaison
        # Séparer les tirages d'arrivées des couleurs et des accidents.
        self.hasard_arrivees = random.Random(graine)
        self.temps_simule = 0.0
        self.debut_mission = None
        self.duree_mission = None
        self.debut_attente_pietons = None
        self.attente_pietons = None
        self.priorite_mission = True
        self.attente_voitures = 0.0
        self.voitures_entrees = 0
        self.voitures_sorties = 0
        self.arrivees_refusees = 0
        self.nombre_demandes = 0
        self.setWindowTitle("Team System — Carrefour connecté")
        self.resize(900, 900)

        self.scene = QGraphicsScene(0, 0, TAILLE, TAILLE)
        self.vue = QGraphicsView(self.scene)
        self.vue.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setCentralWidget(self.vue)

        # Chaque direction possède un feu, stocké pour les prochaines étapes.
        self.feux = {}
        self.voitures = []
        self.ambulance = None
        self.demande_ambulance = None
        self.demande_pietons = False
        self.pietons = []
        self.accident = None
        self.temps_accident = 0.0
        self.densite = densite  # Intensité des arrivées, en pourcentage.
        self.dessiner_carrefour()
        self.creer_reglage_densite()
        self.creer_commande_pietons()
        self.creer_commandes_accident()
        self.creer_outils_analyse()

        # On démarre avec une seconde de rouge pour les quatre directions.
        self.phase = len(PHASES) - 1
        self.temps_restant = PHASES[self.phase][3]
        self.appliquer_phase()
        self.afficher_etat()

        # Qt appelle avancer_cycle une fois par seconde, sans bloquer la fenêtre.
        self.minuteur = QTimer(self)
        self.minuteur.setTimerType(Qt.TimerType.PreciseTimer)
        self.minuteur.timeout.connect(self.avancer_cycle)
        self.minuteur.start(1000)

        # Le dessin des voitures est actualisé plus souvent que les feux.
        self.animation = QTimer(self)
        self.animation.timeout.connect(self.avancer_voitures)
        self.animation.start(int(PAS_TEMPS * 1000))

        self.arrivees = QTimer(self)
        self.arrivees.timeout.connect(self.ajouter_voitures)
        self.arrivees.start(800)
        self.ajouter_voitures()
        if self.mode_comparaison:
            self.minuteur.stop()
            self.animation.stop()
            self.arrivees.stop()
        self.journaliser("Simulation démarrée")

    def creer_reglage_densite(self):
        """Ajoute un curseur pour régler la fréquence des arrivées."""
        barre = QToolBar("Circulation", self)
        barre.setMovable(False)
        self.addToolBar(barre)

        self.etiquette_densite = QLabel(f" Densité : {self.densite} %  ")
        barre.addWidget(self.etiquette_densite)

        self.curseur_densite = QSlider(Qt.Orientation.Horizontal)
        self.curseur_densite.setRange(0, 100)
        self.curseur_densite.setValue(self.densite)
        self.curseur_densite.setFixedWidth(240)
        self.curseur_densite.setAccessibleName("Densité de circulation")
        self.curseur_densite.setToolTip(
            "0 % : aucune arrivée ; 100 % : demande maximale. "
            "Les voitures déjà présentes continuent leur trajet."
        )
        self.curseur_densite.valueChanged.connect(self.changer_densite)
        barre.addWidget(self.curseur_densite)
        barre.addSeparator()
        self.choix_direction = QComboBox()
        for nom, direction in (("Nord", "N"), ("Sud", "S"),
                               ("Est", "E"), ("Ouest", "O")):
            self.choix_direction.addItem(nom, direction)
        barre.addWidget(self.choix_direction)
        self.bouton_ambulance = QPushButton("Envoyer une ambulance")
        self.bouton_ambulance.clicked.connect(self.demander_ambulance)
        barre.addWidget(self.bouton_ambulance)

    def creer_commande_pietons(self):
        """Ajoute une commande de traversée et son état visible."""
        self.addToolBarBreak()
        barre = QToolBar("Piétons", self)
        barre.setMovable(False)
        self.addToolBar(barre)
        self.bouton_pietons = QPushButton("Demander une traversée piétonne")
        self.bouton_pietons.clicked.connect(self.demander_pietons)
        barre.addWidget(self.bouton_pietons)
        self.etat_pietons = QLabel("  Piétons : en attente d'une demande")
        barre.addWidget(self.etat_pietons)

    def creer_commandes_accident(self):
        """Ajoute les commandes et le suivi du dégagement d'une voie."""
        self.addToolBarBreak()
        barre = QToolBar("Accidents", self)
        barre.setMovable(False)
        self.addToolBar(barre)
        self.accidents_aleatoires = QCheckBox("Accidents aléatoires")
        self.accidents_aleatoires.setChecked(True)
        barre.addWidget(self.accidents_aleatoires)
        bouton = QPushButton("Provoquer un accident")
        bouton.clicked.connect(self.provoquer_accident)
        barre.addWidget(bouton)
        self.bouton_degager = QPushButton("Dégager la voie")
        self.bouton_degager.setEnabled(False)
        self.bouton_degager.clicked.connect(self.degager_accident)
        barre.addWidget(self.bouton_degager)
        self.etat_accident = QLabel("  Aucun accident")
        barre.addWidget(self.etat_accident)

    def afficher_accident(self):
        """Indique la voie touchée et le délai de dégagement automatique."""
        if self.accident is None:
            return
        secondes = max(1, int(self.temps_accident + 0.999))
        direction = self.accident["direction"]
        self.etat_accident.setText(
            f"  Voie depuis {direction} bloquée — dégagement dans {secondes} s"
        )

    def creer_outils_analyse(self):
        """Ajoute l'expérience comparative et un journal lisible des décisions."""
        self.addToolBarBreak()
        barre = QToolBar("Analyse", self)
        barre.setMovable(False)
        self.addToolBar(barre)
        self.option_priorite = QCheckBox("Priorité ambulance")
        self.option_priorite.setChecked(True)
        self.option_priorite.setToolTip("Ce réglage s'applique à la prochaine mission.")
        barre.addWidget(self.option_priorite)
        bouton = QPushButton("Comparer avec / sans priorité")
        bouton.clicked.connect(self.ouvrir_comparaison)
        barre.addWidget(bouton)
        self.mesure_mission = QLabel("  Aucun trajet mesuré")
        barre.addWidget(self.mesure_mission)

        dock = QDockWidget("Journal des décisions", self)
        self.journal = QPlainTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setMaximumBlockCount(120)
        dock.setWidget(self.journal)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setMinimumHeight(100)
        self.resizeDocks([dock], [120], Qt.Orientation.Vertical)

    def journaliser(self, message):
        """Enregistre les événements avec le temps écoulé dans la simulation."""
        if not self.mode_comparaison:
            self.journal.appendPlainText(f"[{self.temps_simule:6.1f} s] {message}")

    def ouvrir_comparaison(self):
        """Met la démonstration en pause pendant une expérience indépendante."""
        self.minuteur.stop()
        self.animation.stop()
        self.arrivees.stop()
        dialogue = Comparaison(self, self.densite, self.choix_direction.currentData(), FenetrePrincipale)
        dialogue.exec()
        self.minuteur.start()
        self.animation.start()
        self.arrivees.start()

    def changer_densite(self, valeur):
        """Applique le réglage aux prochaines arrivées de voitures."""
        self.densite = valeur
        self.etiquette_densite.setText(f" Densité : {valeur} %  ")

    def afficher_etat(self):
        """Affiche la phase et son temps restant en bas de la fenêtre."""
        description = PHASES[self.phase][0]
        if self.phase in (2, 5) and self.temps_restant == 0:
            description = "Tous rouges : attente de la fin des traversées"
        cible = self.phase_prioritaire()
        temps = f"Temps restant : {self.temps_restant} s"
        if cible is not None:
            description += " | Priorité ambulance"
            if self.phase == cible:
                temps = "Vert maintenu jusqu'à la sortie de l'ambulance"
            if self.demande_ambulance is not None:
                description += " (attente à l'entrée)"
        if self.pietons:
            description = "Tous rouges : traversée des piétons"
            temps = "Attente de la fin de traversée"
            if cible is not None:
                temps += " — ambulance en attente"
        self.statusBar().showMessage(
            f"{description} | {temps} | Véhicules : {len(self.voitures)}"
        )

    def resizeEvent(self, evenement):
        """Garde le carrefour entier visible lors du redimensionnement."""
        super().resizeEvent(evenement)
        if hasattr(self, "vue"):
            self.vue.fitInView(
                self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )


if __name__ == "__main__":
    application = QApplication(sys.argv)
    fenetre = FenetrePrincipale()
    fenetre.show()
    sys.exit(application.exec())

