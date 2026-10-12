"""Comparaison mesurée avec/sans priorité, journal et simulation du carrefour d'un carrefour unique avec PyQt6.

Lancement : python src/interface/main.py
Les axes nord-sud et est-ouest passent au vert à tour de rôle.
"""

import sys
import random
import csv

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QMainWindow,
    QLabel, QSlider, QToolBar, QPushButton, QComboBox, QCheckBox,
    QDockWidget, QPlainTextEdit, QDialog, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QProgressBar,
)


TAILLE = 800
CENTRE = TAILLE // 2
DEMI_ROUTE = 90
LONGUEUR_VOITURE = 32
LARGEUR_VOITURE = 18
DISTANCE_ARRET = 235  # Distance du centre de la voiture depuis son entrée.
DISTANCE_SORTIE = 565  # La voiture entière a quitté la zone de traversée.
ESPACEMENT = 48  # Distance minimale entre les centres de deux voitures.
PAS_TEMPS = 0.04  # Une étape de simulation toutes les 40 ms.
VITESSE = 60  # Pixels par seconde de simulation.


# Chaque phase : (description, couleur nord-sud, couleur est-ouest, durée).
# Les durées sont exprimées en secondes dans la simulation.
PHASES = [
    ("Nord-sud : vert", "vert", "rouge", 10),
    ("Nord-sud : orange", "orange", "rouge", 2),
    ("Tous les feux rouges", "rouge", "rouge", 1),
    ("Est-ouest : vert", "rouge", "vert", 10),
    ("Est-ouest : orange", "rouge", "orange", 2),
    ("Tous les feux rouges", "rouge", "rouge", 1),
]

COULEURS_FEUX = {
    "rouge": "#f05252",
    "orange": "#ffb547",
    "vert": "#45d483",
}


class FenetrePrincipale(QMainWindow):
    """Affiche les quatre branches du carrefour."""

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

    def demander_pietons(self):
        """Mémorise une demande sans interrompre une traversée automobile."""
        if self.demande_pietons or self.pietons:
            return
        self.demande_pietons = True
        self.debut_attente_pietons = self.temps_simule
        self.journaliser("Demande piétonne enregistrée")
        self.bouton_pietons.setEnabled(False)
        self.etat_pietons.setText("  Demande enregistrée : attendez le vert piéton")

    def commencer_traversee(self):
        """Fait traverser un piéton par passage, uniquement lorsque tout est rouge."""
        self.demande_pietons = False
        self.attente_pietons = self.temps_simule - self.debut_attente_pietons
        self.journaliser(f"Piétons autorisés après {self.attente_pietons:.1f} s d'attente")
        for direction in ("N", "S", "E", "O"):
            dessin = self.scene.addEllipse(
                -5, -5, 10, 10, QPen(QColor("#ffffff"), 1),
                QBrush(QColor("#f7a840")),
            )
            dessin.setZValue(3)
            pieton = {"direction": direction, "distance": 0.0, "dessin": dessin}
            self.pietons.append(pieton)
            self.placer_pieton(pieton)
        self.etat_pietons.setText("  Vert piéton : traversée en cours")

    def placer_pieton(self, pieton):
        """Place le piéton sur les bandes blanches de son passage."""
        position = 298 + pieton["distance"]
        direction = pieton["direction"]
        if direction in ("N", "S"):
            x, y = position, 286 if direction == "N" else 514
        else:
            x, y = 514 if direction == "E" else 286, position
        pieton["dessin"].setPos(x, y)

    def avancer_pietons(self):
        """Traverse à 30 pixels par seconde ; les feux restent rouges jusqu'au bout."""
        if not self.pietons:
            return
        for pieton in self.pietons[:]:
            pieton["distance"] += 30 * PAS_TEMPS
            self.placer_pieton(pieton)
            if pieton["distance"] >= 204:
                self.scene.removeItem(pieton["dessin"])
                self.pietons.remove(pieton)
        if not self.pietons:
            self.journaliser("Piétons sur le trottoir : le trafic peut reprendre")
            self.etat_pietons.setText("  Traversée terminée — piétons sur le trottoir")
            self.bouton_pietons.setEnabled(True)

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

    def provoquer_accident(self):
        """Immobilise une voiture hors des passages piétons et du centre."""
        if self.accident is not None:
            return
        candidats = [
            v for v in self.voitures
            if not v["prioritaire"]
            and (80 < v["distance"] < 200 or 580 < v["distance"] < 740)
        ]
        if not candidats:
            self.etat_accident.setText("  Aucun véhicule éligible pour le moment")
            return
        self.accident = random.choice(candidats)
        self.temps_accident = 20.0
        self.journaliser(f"Accident sur la voie depuis {self.accident['direction']}")
        self.accident["dessin"].setBrush(QBrush(QColor("#ed4747")))
        self.bouton_degager.setEnabled(True)
        self.afficher_accident()

    def afficher_accident(self):
        """Indique la voie touchée et le délai de dégagement automatique."""
        if self.accident is None:
            return
        secondes = max(1, int(self.temps_accident + 0.999))
        direction = self.accident["direction"]
        self.etat_accident.setText(
            f"  Voie depuis {direction} bloquée — dégagement dans {secondes} s"
        )

    def degager_accident(self):
        """Rend au véhicule sa couleur et lui permet de repartir."""
        if self.accident is None:
            return
        self.journaliser("Accident dégagé : la file peut repartir")
        self.accident["dessin"].setBrush(QBrush(QColor(self.accident["couleur"])))
        self.accident = None
        self.temps_accident = 0.0
        self.bouton_degager.setEnabled(False)
        self.etat_accident.setText("  Voie dégagée")

    def actualiser_accident(self):
        """Décompte le dépannage ou tente un nouvel accident aléatoire."""
        if self.accident is not None:
            self.temps_accident -= PAS_TEMPS
            if self.temps_accident <= 0:
                self.degager_accident()
            else:
                self.afficher_accident()
        elif self.accidents_aleatoires.isChecked():
            # En moyenne une tentative toutes les 55 secondes de simulation.
            # Elle peut échouer si aucune voiture n'est dans une zone éligible.
            if random.random() < PAS_TEMPS / 55:
                self.provoquer_accident()

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
        dialogue = Comparaison(self, self.densite, self.choix_direction.currentData())
        dialogue.exec()
        self.minuteur.start()
        self.animation.start()
        self.arrivees.start()

    def changer_densite(self, valeur):
        """Applique le réglage aux prochaines arrivées de voitures."""
        self.densite = valeur
        self.etiquette_densite.setText(f" Densité : {valeur} %  ")

    def rectangle(self, x, y, largeur, hauteur, couleur):
        """Ajoute un rectangle sans contour dans la scène."""
        return self.scene.addRect(
            x, y, largeur, hauteur,
            QPen(Qt.PenStyle.NoPen), QBrush(QColor(couleur)),
        )

    def texte(self, contenu, x, y, taille=12, couleur="#25364a"):
        """Place une inscription sur la maquette."""
        texte = self.scene.addText(contenu, QFont("Arial", taille))
        texte.setDefaultTextColor(QColor(couleur))
        texte.setPos(x, y)
        return texte

    def dessiner_carrefour(self):
        """Dessine le décor, les routes, les passages et les feux."""
        self.scene.setBackgroundBrush(QBrush(QColor("#dcebdc")))
        bord = CENTRE - DEMI_ROUTE
        largeur = 2 * DEMI_ROUTE

        # Les trottoirs dépassent de chaque côté de la chaussée.
        self.rectangle(bord - 24, 0, largeur + 48, TAILLE, "#bcc6cc")
        self.rectangle(0, bord - 24, TAILLE, largeur + 48, "#bcc6cc")
        self.rectangle(bord, 0, largeur, TAILLE, "#354354")
        self.rectangle(0, bord, TAILLE, largeur, "#354354")

        # Séparation des deux sens, en laissant le centre dégagé.
        stylo = QPen(QColor("#edf1f5"), 3, Qt.PenStyle.DashLine)
        for debut, fin in [(0, 265), (535, TAILLE)]:
            self.scene.addLine(CENTRE, debut, CENTRE, fin, stylo)
            self.scene.addLine(debut, CENTRE, fin, CENTRE, stylo)

        self.dessiner_passages_pietons()

        # Lignes d'arrêt sur les voies entrantes (circulation à droite).
        self.rectangle(315, 253, 80, 5, "#ffffff")  # Depuis le nord
        self.rectangle(405, 542, 80, 5, "#ffffff")  # Depuis le sud
        self.rectangle(253, 405, 5, 80, "#ffffff")  # Depuis l'ouest
        self.rectangle(542, 315, 5, 80, "#ffffff")  # Depuis l'est

        self.dessiner_feu("N", 276, 211)
        self.dessiner_feu("S", 500, 526)
        self.dessiner_feu("O", 215, 500)
        self.dessiner_feu("E", 558, 237)

        self.texte("NORD", 416, 25, couleur="#ffffff")
        self.texte("SUD", 326, 737, couleur="#ffffff")
        self.texte("OUEST", 25, 352, couleur="#ffffff")
        self.texte("EST", 715, 412, couleur="#ffffff")
        self.texte("TEAM SYSTEM", 30, 25, 20)
        self.texte("Carrefour connecté", 30, 65)

        for x, y in [(85, 170), (180, 170), (620, 100),
                     (710, 170), (100, 625), (185, 705),
                     (615, 660), (715, 710)]:
            self.scene.addEllipse(
                x, y, 42, 42,
                QPen(QColor("#478064"), 2), QBrush(QColor("#79ac83")),
            )

    def dessiner_passages_pietons(self):
        """Dessine un passage piéton sur chaque branche."""
        for position in range(317, 485, 18):
            for distance in (274, 502):
                self.rectangle(position, distance, 10, 24, "#ffffff")
                self.rectangle(distance, position, 24, 10, "#ffffff")

    def dessiner_feu(self, direction, x, y):
        """Crée les trois lampes d'un feu ; seule la rouge est allumée."""
        self.rectangle(x, y, 24, 63, "#17212e")
        lampes = {}
        for index, nom in enumerate(("rouge", "orange", "vert")):
            couleur = "#f05252" if nom == "rouge" else "#46505c"
            lampes[nom] = self.scene.addEllipse(
                x + 5, y + 5 + index * 19, 14, 14,
                QPen(Qt.PenStyle.NoPen), QBrush(QColor(couleur)),
            )
        self.feux[direction] = lampes

    def changer_feu(self, direction, couleur):
        """Allume une seule lampe et éteint les deux autres."""
        for nom, lampe in self.feux[direction].items():
            teinte = COULEURS_FEUX[nom] if nom == couleur else "#46505c"
            lampe.setBrush(QBrush(QColor(teinte)))

    def appliquer_phase(self):
        """Met les quatre feux dans l'état prévu par la phase actuelle."""
        description, couleur_ns, couleur_eo, duree = PHASES[self.phase]
        self.journaliser(description)

        # Tout passer au rouge avant d'allumer les lampes du nouvel état.
        for direction in self.feux:
            self.changer_feu(direction, "rouge")
        for direction in ("N", "S"):
            self.changer_feu(direction, couleur_ns)
        for direction in ("E", "O"):
            self.changer_feu(direction, couleur_eo)

    def avancer_cycle(self):
        """Respecte les transitions et maintient le vert pendant la priorité."""
        # Une traversée commencée se termine, même en cas d'alerte ambulance.
        if self.pietons:
            self.afficher_etat()
            return
        cible = self.phase_prioritaire()
        if cible is not None and self.phase == cible:
            # Aucun compte à rebours ne peut couper le vert à l'ambulance.
            self.temps_restant = PHASES[self.phase][3]
            self.afficher_etat()
            return
        if cible is not None and self.phase in (0, 3):
            # Abréger le vert opposé, puis respecter l'orange et le tout rouge.
            self.temps_restant = min(self.temps_restant, 3)

        self.temps_restant -= 1
        if self.temps_restant <= 0:
            if self.phase in (2, 5) and self.carrefour_occupe():
                self.temps_restant = 0
                self.afficher_etat()
                return
            if self.phase in (2, 5) and self.demande_pietons and cible is None:
                self.temps_restant = 0
                self.commencer_traversee()
                self.afficher_etat()
                return
            if self.phase in (2, 5) and cible is not None:
                self.phase = cible
            else:
                self.phase = (self.phase + 1) % len(PHASES)
            self.temps_restant = PHASES[self.phase][3]
            self.appliquer_phase()
        self.afficher_etat()

    def phase_prioritaire(self):
        """Renvoie le vert demandé (0 ou 3), ou None sans priorité."""
        if not self.priorite_mission:
            return None
        direction = self.demande_ambulance
        if self.ambulance is not None:
            if self.ambulance["distance"] >= DISTANCE_SORTIE:
                return None
            direction = self.ambulance["direction"]
        if direction is None:
            return None
        return 0 if direction in ("N", "S") else 3

    def demander_ambulance(self):
        """Réserve une mission ; l'ambulance attend si l'entrée est occupée."""
        if self.ambulance is not None or self.demande_ambulance is not None:
            return
        self.demande_ambulance = self.choix_direction.currentData()
        self.priorite_mission = self.option_priorite.isChecked()
        self.debut_mission = self.temps_simule
        self.duree_mission = None
        mode = "avec priorité" if self.priorite_mission else "sans priorité"
        self.journaliser(f"Ambulance demandée depuis {self.demande_ambulance}, {mode}")
        self.mesure_mission.setText("  Mission en cours…")
        self.bouton_ambulance.setEnabled(False)
        # L'alerte est envoyée dès la demande, même si la file est longue.
        self.essayer_creer_ambulance()
        self.afficher_etat()

    def essayer_creer_ambulance(self):
        """Fait entrer l'ambulance sans la superposer à une voiture."""
        direction = self.demande_ambulance
        if direction is None:
            return
        if any(v["direction"] == direction and v["distance"] < ESPACEMENT
               for v in self.voitures):
            return
        self.ambulance = self.creer_voiture(direction, "#ffffff", True)
        self.demande_ambulance = None

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

    def ajouter_voitures(self):
        """Tente une arrivée par entrée selon la densité et la place libre.

        Toutes les 800 ms, un tirage de 0 à 99 est comparé à la densité.
        À 0 %, aucune arrivée ; à 100 %, chaque entrée libre est alimentée.
        Ce réglage représente la demande, pas le taux d'occupation mesuré.
        """
        for direction in ("N", "S", "E", "O"):
            # Un tirage par direction à chaque appel, même si l'entrée est bloquée.
            # Cela conserve la même demande dans les deux expériences.
            if self.hasard_arrivees.randrange(100) >= self.densite:
                continue
            self.nombre_demandes += 1
            if direction == self.demande_ambulance:
                self.arrivees_refusees += 1
                continue
            entree_occupee = any(
                voiture["direction"] == direction
                and voiture["distance"] < ESPACEMENT
                for voiture in self.voitures
            )
            if entree_occupee:
                self.arrivees_refusees += 1
                continue

            couleur = random.choice(("#63b3ed", "#f6c568", "#e58c99", "#b4a1e5"))
            self.creer_voiture(direction, couleur)

    def creer_voiture(self, direction, couleur, prioritaire=False):
        """Crée un véhicule ; le même déplacement sert aussi à l'ambulance."""
        if direction in ("N", "S"):
            largeur, hauteur = LARGEUR_VOITURE, LONGUEUR_VOITURE
        else:
            largeur, hauteur = LONGUEUR_VOITURE, LARGEUR_VOITURE
        dessin = self.rectangle(-largeur / 2, -hauteur / 2,
                                largeur, hauteur, couleur)
        dessin.setZValue(2)
        if prioritaire:
            # Le repère bleu est enfant du véhicule et suit ses déplacements.
            repere = self.rectangle(-5, -5, 10, 10, "#1687ee")
            repere.setParentItem(dessin)
        voiture = {"direction": direction, "distance": 0.0,
                   "dessin": dessin, "prioritaire": prioritaire,
                   "couleur": couleur}
        self.voitures.append(voiture)
        if not prioritaire:
            self.voitures_entrees += 1
        self.placer_voiture(voiture)
        return voiture

    def placer_voiture(self, voiture):
        """Convertit la distance parcourue en coordonnées dans la scène."""
        distance = voiture["distance"]
        direction = voiture["direction"]
        if direction == "N":
            x, y = 355, distance
        elif direction == "S":
            x, y = 445, TAILLE - distance
        elif direction == "O":
            x, y = distance, 445
        else:
            x, y = TAILLE - distance, 355
        voiture["dessin"].setPos(x, y)

    def carrefour_occupe(self):
        """Indique si une voiture doit encore terminer sa traversée."""
        return any(
            DISTANCE_ARRET < voiture["distance"] < DISTANCE_SORTIE
            for voiture in self.voitures
        )

    def avancer_voitures(self):
        """Avance les files en respectant les feux et les voitures devant."""
        self.temps_simule += PAS_TEMPS
        self.actualiser_accident()
        self.avancer_pietons()
        self.essayer_creer_ambulance()
        for direction in ("N", "S", "E", "O"):
            # Traiter la première voiture avant celles qui la suivent.
            file = sorted(
                (v for v in self.voitures if v["direction"] == direction),
                key=lambda v: v["distance"], reverse=True,
            )
            couleur = PHASES[self.phase][1 if direction in ("N", "S") else 2]
            voiture_devant = None
            for voiture in file:
                distance = voiture["distance"]
                vitesse = 80 if voiture["prioritaire"] else VITESSE
                if voiture is self.accident:
                    vitesse = 0
                nouvelle_distance = distance + vitesse * PAS_TEMPS

                # Une voiture déjà engagée continue, même si le feu change.
                if distance <= DISTANCE_ARRET and couleur != "vert":
                    nouvelle_distance = min(nouvelle_distance, DISTANCE_ARRET)
                if voiture_devant is not None:
                    nouvelle_distance = min(
                        nouvelle_distance, voiture_devant["distance"] - ESPACEMENT
                    )

                voiture["distance"] = max(distance, nouvelle_distance)
                self.placer_voiture(voiture)
                if not voiture["prioritaire"] and voiture["distance"] - distance < 0.000001:
                    self.attente_voitures += PAS_TEMPS
                if (voiture["prioritaire"]
                        and distance < DISTANCE_SORTIE <= voiture["distance"]):
                    self.duree_mission = self.temps_simule - self.debut_mission
                    self.journaliser(f"Ambulance sortie après {self.duree_mission:.1f} s")
                    self.mesure_mission.setText(f"  Dernière mission : {self.duree_mission:.1f} s")
                    # Sans priorité, le cycle normal ne doit pas être modifié.
                    if self.priorite_mission:
                        self.temps_restant = min(self.temps_restant, 3)
                voiture_devant = voiture

        # Retirer uniquement les voitures entièrement sorties de l'écran.
        for voiture in self.voitures[:]:
            if voiture["distance"] > TAILLE + LONGUEUR_VOITURE:
                self.scene.removeItem(voiture["dessin"])
                self.voitures.remove(voiture)
                if not voiture["prioritaire"]:
                    self.voitures_sorties += 1
                if voiture is self.ambulance:
                    self.ambulance = None
                    self.bouton_ambulance.setEnabled(True)
        self.afficher_etat()

    def resizeEvent(self, evenement):
        """Garde le carrefour entier visible lors du redimensionnement."""
        super().resizeEvent(evenement)
        if hasattr(self, "vue"):
            self.vue.fitInView(
                self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )


class Comparaison(QDialog):
    """Rejoue deux fois un scénario reproductible avec le moteur de la maquette.

    Seule l'option de priorité change. Les tentatives d'arrivée sont identiques,
    mais leur admission peut varier selon les files ; on expose cette différence.
    QTimer fait avancer le calcul par petits lots pour garder la fenêtre réactive.
    """

    def __init__(self, parent, densite, direction):
        super().__init__(parent)
        self.setWindowTitle("Expérience — avec et sans priorité")
        self.resize(820, 610)
        self.densite = densite
        self.direction = direction
        self.graine = 2026
        self.tour = 0
        self.nombre_tours = 3000  # 120 secondes de simulation à 40 ms.
        self.resultats = []
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
        fermer = QPushButton("Fermer et reprendre la simulation")
        fermer.clicked.connect(self.reject)
        disposition.addWidget(fermer)

        self.simulations = []
        for priorite in (False, True):
            simulation = FenetrePrincipale(densite, self.graine, mode_comparaison=True)
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
                if self.tour > 0 and self.tour % 20 == 0:
                    simulation.ajouter_voitures()
                if self.tour > 0 and self.tour % 25 == 0:
                    simulation.avancer_cycle()
                simulation.avancer_voitures()
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
        self.calcul.stop()
        self.liberer_simulations()
        super().done(resultat)


if __name__ == "__main__":
    application = QApplication(sys.argv)
    fenetre = FenetrePrincipale()
    fenetre.show()
    sys.exit(application.exec())
