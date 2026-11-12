"""Point d'entrée et commandes de la fenêtre.

Depuis la racine du dépôt : python src/interface/main.py
Les deux classes DessinCarrefour et SimulationCarrefour regroupent les
méthodes qui utilisent cette même fenêtre (self).
"""

import sys
import random
import time
import math
from PyQt6.QtCore import (
    Qt, QTimer,
)
from PyQt6.QtGui import (
    QPainter,
)
from PyQt6.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QMainWindow, QLabel, QSlider, QToolBar, QPushButton, QComboBox, QCheckBox, QDockWidget, QPlainTextEdit, QLineEdit, QSpinBox, QMessageBox,
)
if __package__:
    from .parametres import (PAS_TEMPS, PHASES, TAILLE, DISTANCE_SORTIE)
else:
    from parametres import (PAS_TEMPS, PHASES, TAILLE, DISTANCE_SORTIE)


if __package__:
    from .dessin import DessinCarrefour
    from .simulation import SimulationCarrefour
    from .comparaison import Comparaison
    from .historique import Historique
    from ..clients.client_qt import ClientReseauQt
    from ..controleur import Controleur, verifier_commande
else:
    from dessin import DessinCarrefour
    from simulation import SimulationCarrefour
    from comparaison import Comparaison
    from historique import Historique
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.clients.client_qt import ClientReseauQt
    from src.controleur import Controleur, verifier_commande


class FenetrePrincipale(DessinCarrefour, SimulationCarrefour, QMainWindow):
    """Assemble le dessin, la simulation et les commandes utilisateur."""

    def __init__(self, densite=45, graine=None, mode_comparaison=False):
        super().__init__()
        self.mode_comparaison = mode_comparaison
        self.client_reseau = None
        self.controleur = Controleur()
        self.mode_reseau = False
        self.reseau_pret = False
        self.en_attente = False
        self.pause = False
        self.compteur_pas = 0
        self.commande_differee = None
        self.fermeture_demandee = False
        self.derniere_erreur_reseau = None
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
        if not self.mode_comparaison:
            self.creer_commandes_reseau()

        # On démarre avec une seconde de rouge pour les quatre directions.
        self.phase = len(PHASES) - 1
        self.temps_restant = PHASES[self.phase][3]
        self.appliquer_phase()
        self.afficher_etat()

        # Une seule horloge : 40 ms simulées par étape effectivement terminée.
        self.animation = QTimer(self)
        self.animation.setTimerType(Qt.TimerType.PreciseTimer)
        self.animation.timeout.connect(self.pas_animation)
        self.animation.start(int(PAS_TEMPS * 1000))
        self.ajouter_voitures()
        if self.mode_comparaison:
            self.animation.stop()
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
        historique = QPushButton("Historique MariaDB")
        historique.clicked.connect(self.ouvrir_historique)
        barre.addWidget(historique)

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
        """Suspend la maquette ; la comparaison utilise le même contrôleur."""
        self.pause = True
        dialogue = Comparaison(self, self.densite, self.choix_direction.currentData(), FenetrePrincipale)
        dialogue.exec()
        self.pause = False
        if self.commande_differee is not None:
            commande = self.commande_differee
            self.commande_differee = None
            self.recevoir_etat_reseau(commande)

    def ouvrir_historique(self):
        if not self.reseau_pret or self.client_reseau is None:
            QMessageBox.information(self, "Historique", "Connecte d'abord la maquette au serveur.")
            return
        self.pause = True
        dialogue = Historique(self, self.client_reseau)
        dialogue.exec()
        self.pause = False
        if self.commande_differee is not None:
            commande = self.commande_differee
            self.commande_differee = None
            self.recevoir_etat_reseau(commande)

    def relever_capteurs(self):
        """Détecte automatiquement l'ambulance jusqu'à sa sortie complète."""
        direction = self.demande_ambulance
        if self.ambulance is not None and self.ambulance["distance"] < DISTANCE_SORTIE:
            direction = self.ambulance["direction"]
        return {"occupe": self.carrefour_occupe(), "ambulance": direction,
                "priorite": self.priorite_mission, "pietons": bool(self.pietons),
                "demande_pietons": self.demande_pietons}

    def appliquer_commande(self, commande):
        """Applique ensemble les feux et l'autorisation de traversée."""
        verifier_commande(commande)
        ancienne_phase = self.phase
        self.phase = commande["phase"]
        self.temps_restant = math.ceil(commande["restant"])
        if ancienne_phase != self.phase:
            self.appliquer_phase()
        if commande["traverser"] and self.demande_pietons and not self.pietons:
            self.commencer_traversee()
        self.avancer_voitures()
        self.compteur_pas += 1
        if self.compteur_pas % 20 == 0:
            self.ajouter_voitures()

    def pas_local(self):
        """Même décision qu'au serveur, sans transport TCP."""
        self.appliquer_commande(self.controleur.avancer(self.relever_capteurs()))

    def pas_animation(self):
        if self.pause:
            return
        if not self.mode_reseau:
            self.pas_local()
        elif self.en_attente:
            if time.monotonic() - self.debut_requete > 1.0:
                self.signaler_erreur_reseau("Réponse trop lente : simulation suspendue, reconnecter.")
                self.client_reseau.arreter()
        elif self.reseau_pret and self.client_reseau is not None:
            self.en_attente = True
            self.debut_requete = time.monotonic()
            self.client_reseau.proposer(self.relever_capteurs())

    def mettre_au_rouge(self):
        self.phase = 5
        self.temps_restant = 1
        self.appliquer_phase()
        self.afficher_etat()

    def reprendre_local(self):
        if self.client_reseau is not None:
            return
        self.mode_reseau = False
        self.controleur = Controleur()
        self.mettre_au_rouge()
        self.etat_reseau.setText("  Mode local — serveur non utilisé")
        self.journaliser("Reprise locale demandée par l'utilisateur")

    def creer_commandes_reseau(self):
        """Ajoute l'adresse du serveur et les commandes de connexion."""
        self.addToolBarBreak()
        barre = QToolBar("Réseau", self)
        barre.setMovable(False)
        self.addToolBar(barre)
        barre.addWidget(QLabel(" Serveur : "))
        self.adresse_serveur = QLineEdit("127.0.0.1")
        self.adresse_serveur.setMaximumWidth(160)
        self.adresse_serveur.setToolTip("Sur une autre machine, saisir l'adresse IP de la VM serveur.")
        barre.addWidget(self.adresse_serveur)
        self.port_serveur = QSpinBox()
        self.port_serveur.setRange(1, 65535)
        self.port_serveur.setValue(5000)
        barre.addWidget(self.port_serveur)
        self.bouton_connexion = QPushButton("Connecter")
        self.bouton_connexion.clicked.connect(self.basculer_connexion)
        barre.addWidget(self.bouton_connexion)
        self.bouton_local = QPushButton("Reprendre en local")
        self.bouton_local.clicked.connect(self.reprendre_local)
        barre.addWidget(self.bouton_local)
        self.etat_reseau = QLabel("  Hors ligne — simulation locale")
        barre.addWidget(self.etat_reseau)

    def basculer_connexion(self):
        """Démarre ou arrête le thread réseau sans attendre dans l'interface."""
        if self.client_reseau is not None:
            self.reseau_pret = False
            self.en_attente = False
            self.mettre_au_rouge()
            self.client_reseau.arreter()
            self.bouton_connexion.setEnabled(False)
            self.etat_reseau.setText("  Déconnexion en cours…")
            return
        hote = self.adresse_serveur.text().strip()
        if not hote:
            self.etat_reseau.setText("  Saisis l'adresse du serveur.")
            return
        self.derniere_erreur_reseau = None
        self.mode_reseau = True
        self.reseau_pret = False
        self.en_attente = False
        self.commande_differee = None
        self.mettre_au_rouge()
        self.bouton_local.setEnabled(False)
        self.adresse_serveur.setEnabled(False)
        self.port_serveur.setEnabled(False)
        self.bouton_connexion.setText("Annuler")
        self.etat_reseau.setText("  Connexion en cours…")
        self.client_reseau = ClientReseauQt(hote, self.port_serveur.value(), self)
        self.client_reseau.connecte.connect(self.connexion_etablie)
        self.client_reseau.etat_recu.connect(self.recevoir_etat_reseau)
        self.client_reseau.erreur.connect(self.signaler_erreur_reseau)
        self.client_reseau.finished.connect(self.connexion_terminee)
        self.client_reseau.start()

    def connexion_etablie(self):
        if self.client_reseau.arret.is_set():
            return
        self.reseau_pret = True
        self.bouton_connexion.setText("Déconnecter")
        self.etat_reseau.setText("  Connecté — capteur, régulateur, feux")
        self.journaliser("Trois clients TCP connectés : le serveur commande les feux")

    def recevoir_etat_reseau(self, commande):
        if self.client_reseau is None or self.client_reseau.arret.is_set():
            return
        if self.pause:
            self.commande_differee = commande
            return
        self.en_attente = False
        self.appliquer_commande(commande)
        self.etat_reseau.setText(f"  Serveur actif — étape {commande['revision']}")

    def signaler_erreur_reseau(self, message):
        self.derniere_erreur_reseau = message
        self.reseau_pret = False
        self.en_attente = False
        self.mettre_au_rouge()
        self.etat_reseau.setText("  Incident réseau — simulation suspendue")
        self.journaliser(f"Erreur réseau : {message}")

    def connexion_terminee(self):
        """Libère le thread une fois arrêté et réactive les commandes."""
        self.client_reseau.deleteLater()
        self.client_reseau = None
        self.reseau_pret = False
        self.en_attente = False
        self.commande_differee = None
        self.mettre_au_rouge()
        self.bouton_local.setEnabled(True)
        self.adresse_serveur.setEnabled(True)
        self.port_serveur.setEnabled(True)
        self.bouton_connexion.setText("Connecter")
        self.bouton_connexion.setEnabled(True)
        if self.derniere_erreur_reseau:
            self.etat_reseau.setText("  Échec réseau — voir le journal")
        else:
            self.etat_reseau.setText("  Déconnecté — simulation suspendue")
        self.journaliser("Connexion réseau terminée")
        if self.fermeture_demandee:
            self.close()

    def closeEvent(self, evenement):
        """Attend la fin du thread sans bloquer Qt avant de fermer la fenêtre."""
        if self.client_reseau is not None:
            self.fermeture_demandee = True
            self.reseau_pret = False
            self.en_attente = False
            self.client_reseau.arreter()
            self.bouton_connexion.setEnabled(False)
            self.etat_reseau.setText("  Fermeture de la connexion…")
            evenement.ignore()
            return
        self.animation.stop()
        super().closeEvent(evenement)

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


