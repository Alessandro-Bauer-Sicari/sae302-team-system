"""Deuxième étape : cycle des feux et dessin d'un carrefour unique avec PyQt6.

Lancement : python src/interface/main.py
Les axes nord-sud et est-ouest passent au vert à tour de rôle.
"""

import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QMainWindow,
)


TAILLE = 800
CENTRE = TAILLE // 2
DEMI_ROUTE = 90


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

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Team System — Carrefour connecté")
        self.resize(900, 900)

        self.scene = QGraphicsScene(0, 0, TAILLE, TAILLE)
        self.vue = QGraphicsView(self.scene)
        self.vue.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setCentralWidget(self.vue)

        # Chaque direction possède un feu, stocké pour les prochaines étapes.
        self.feux = {}
        self.dessiner_carrefour()

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

        self.texte("NORD", 416, 25)
        self.texte("SUD", 326, 737)
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

        # Tout passer au rouge avant d'allumer les lampes du nouvel état.
        for direction in self.feux:
            self.changer_feu(direction, "rouge")
        for direction in ("N", "S"):
            self.changer_feu(direction, couleur_ns)
        for direction in ("E", "O"):
            self.changer_feu(direction, couleur_eo)

    def avancer_cycle(self):
        """Décompte une seconde et change de phase lorsque le délai expire."""
        self.temps_restant -= 1
        if self.temps_restant <= 0:
            # Le modulo permet de revenir au début après la dernière phase.
            self.phase = (self.phase + 1) % len(PHASES)
            self.temps_restant = PHASES[self.phase][3]
            self.appliquer_phase()
        self.afficher_etat()

    def afficher_etat(self):
        """Affiche la phase et son temps restant en bas de la fenêtre."""
        description = PHASES[self.phase][0]
        self.statusBar().showMessage(
            f"{description} | Temps restant : {self.temps_restant} s"
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
