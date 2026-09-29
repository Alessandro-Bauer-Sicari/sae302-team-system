import sys
import math
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QMainWindow,
)


POINTS = {
    "A": (80, 300),
    "C1": (300, 160),
    "C2": (300, 440),
    "C3": (600, 160),
    "C4": (600, 440),
    "B": (820, 300),
}


# Les nombres représentent le temps de trajet en secondes.
# Ils seront ensuite modifiés selon la circulation.
ROUTES = [
    ("A", "C1", 15),
    ("A", "C2", 45),
    ("C1", "C2", 20),
    ("C1", "C3", 30),
    ("C2", "C3", 20),
    ("C2", "C4", 35),
    ("C3", "C4", 25),
    ("C3", "B", 15),
    ("C4", "B", 25),
]


def calculer_chemin(depart, arrivee):
    """Retourne le chemin le plus rapide avec Dijkstra."""

    distances = {nom: float("inf") for nom in POINTS}
    precedents = {}
    non_visites = set(POINTS)

    distances[depart] = 0

    while non_visites:
        actuel = min(non_visites, key=lambda nom: distances[nom])
        non_visites.remove(actuel)

        if actuel == arrivee:
            break

        for route_depart, route_arrivee, temps in ROUTES:
            voisin = None

            if route_depart == actuel:
                voisin = route_arrivee
            elif route_arrivee == actuel:
                voisin = route_depart

            if voisin in non_visites:
                nouvelle_distance = distances[actuel] + temps

                if nouvelle_distance < distances[voisin]:
                    distances[voisin] = nouvelle_distance
                    precedents[voisin] = actuel

    chemin = []
    actuel = arrivee

    while actuel != depart:
        ancien = precedents[actuel]
        chemin.insert(0, (ancien, actuel))
        actuel = ancien

    return chemin, distances[arrivee]


class FenetrePrincipale(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Team System - Carrefour connecté")
        self.resize(1000, 700)

        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 900, 550)
        self.scene.setBackgroundBrush(QColor("#eaf0f2"))

        self.vue = QGraphicsView(self.scene)
        self.setCentralWidget(self.vue)

        self.chemin, self.temps_total = calculer_chemin("A", "B")

        self.dessiner_routes()
        self.dessiner_passages_pietons()
        self.dessiner_feux()
        self.dessiner_carrefours()
        self.dessiner_ambulance()
        self.dessiner_informations()

    def route_dans_chemin(self, depart, arrivee):
        return (
            (depart, arrivee) in self.chemin
            or (arrivee, depart) in self.chemin
        )

    def dessiner_routes(self):
        for depart, arrivee, temps in ROUTES:
            x1, y1 = POINTS[depart]
            x2, y2 = POINTS[arrivee]

            dans_chemin = self.route_dans_chemin(depart, arrivee)

            # Corps de la route
            couleur = QColor("#168bd1") if dans_chemin else QColor("#4f5d68")
            largeur = 32

            stylo_route = QPen(couleur, largeur)
            stylo_route.setCapStyle(Qt.PenCapStyle.RoundCap)

            self.scene.addLine(x1, y1, x2, y2, stylo_route)

            # Ligne centrale de la route
            stylo_centre = QPen(QColor("#e4edf2"), 2)
            stylo_centre.setStyle(Qt.PenStyle.DashLine)

            self.scene.addLine(x1, y1, x2, y2, stylo_centre)

            # Temps affiché sur la route
            milieu_x = (x1 + x2) / 2
            milieu_y = (y1 + y2) / 2

            texte = QGraphicsTextItem(f"{temps} s")
            texte.setDefaultTextColor(couleur)
            texte.setPos(milieu_x - 15, milieu_y - 28)
            self.scene.addItem(texte)

    def dessiner_passages_pietons(self):
        for depart, arrivee, temps in ROUTES:
            x1, y1 = POINTS[depart]
            x2, y2 = POINTS[arrivee]

            longueur = math.hypot(x2 - x1, y2 - y1)

            direction_x = (x2 - x1) / longueur
            direction_y = (y2 - y1) / longueur

            # Direction perpendiculaire à la route
            perpendiculaire_x = -direction_y
            perpendiculaire_y = direction_x

            extremites = [
                (depart, x1, y1, 1),
                (arrivee, x2, y2, -1),
            ]

            for nom, x, y, sens in extremites:
                # On place un passage seulement aux carrefours
                if not nom.startswith("C"):
                    continue

                # On s'éloigne légèrement du centre du carrefour
                centre_x = x + sens * direction_x * 42
                centre_y = y + sens * direction_y * 42

                # Cinq bandes perpendiculaires à la route
                for decalage in [-16, -8, 0, 8, 16]:
                    position_x = centre_x + direction_x * decalage
                    position_y = centre_y + direction_y * decalage

                    debut_x = position_x - perpendiculaire_x * 14
                    debut_y = position_y - perpendiculaire_y * 14
                    fin_x = position_x + perpendiculaire_x * 14
                    fin_y = position_y + perpendiculaire_y * 14

                    stylo = QPen(QColor("#ffffff"), 3)

                    self.scene.addLine(
                        debut_x,
                        debut_y,
                        fin_x,
                        fin_y,
                        stylo,
                    )
    def dessiner_feux(self):
        for depart, arrivee, temps in ROUTES:
            # Examiner les deux extrémités de chaque route
            for nom, voisin in [(depart, arrivee), (arrivee, depart)]:
                if not nom.startswith("C"):
                    continue

                x, y = POINTS[nom]
                autre_x, autre_y = POINTS[voisin]

                longueur = math.hypot(autre_x - x, autre_y - y)
                direction_x = (autre_x - x) / longueur
                direction_y = (autre_y - y) / longueur

                # Avant le passage piéton, à droite des véhicules entrants
                feu_x = x + direction_x * 60 + direction_y * 23
                feu_y = y + direction_y * 60 - direction_x * 23

                feu = QGraphicsEllipseItem(
                    feu_x - 5, feu_y - 5, 10, 10
                )
                feu.setBrush(QBrush(QColor("#e53935")))
                feu.setPen(QPen(QColor("#7f1d1d"), 1))
                self.scene.addItem(feu)
    def dessiner_ambulance(self):
        if not self.chemin:
            return

        # Première route du trajet calculé
        depart, arrivee = self.chemin[0]
        x1, y1 = POINTS[depart]
        x2, y2 = POINTS[arrivee]

        longueur = math.hypot(x2 - x1, y2 - y1)
        direction_x = (x2 - x1) / longueur
        direction_y = (y2 - y1) / longueur

        # Position sur le côté droit de la route
        x = x1 + direction_x * 70 - direction_y * 8
        y = y1 + direction_y * 70 + direction_x * 8

        # Carrosserie : l'avant du véhicule est à droite
        self.ambulance = QGraphicsRectItem(0, 0, 24, 10)
        self.ambulance.setBrush(QBrush(QColor("white")))
        self.ambulance.setPen(QPen(QColor("#243746"), 1))

        # Petits rectangles attachés à la carrosserie
        details = [
            (18, 1, 4, 8, "#a8d8ef"),  # Pare-brise
            (13, 1, 3, 8, "#168bd1"),  # Gyrophare
            (5, 2, 2, 6, "#e53935"),   # Croix rouge
            (3, 4, 6, 2, "#e53935"),
        ]

        for dx, dy, largeur, hauteur, couleur in details:
            element = QGraphicsRectItem(
                dx, dy, largeur, hauteur, self.ambulance
            )
            element.setBrush(QBrush(QColor(couleur)))
            element.setPen(QPen(Qt.PenStyle.NoPen))

        # Tourner tout le véhicule dans le sens de la route
        angle = math.degrees(math.atan2(direction_y, direction_x))
        self.ambulance.setTransformOriginPoint(12, 5)
        self.ambulance.setRotation(angle)
        self.ambulance.setPos(x - 12, y - 5)
        self.ambulance.setZValue(10)

        self.scene.addItem(self.ambulance)
    def dessiner_carrefours(self):
        for nom, (x, y) in POINTS.items():
            taille = 42

            if nom in ["A", "B"]:
                couleur = QColor("#168bd1")
            elif nom in ["C1", "C3"]:
                couleur = QColor("#34495e")
            else:
                couleur = QColor("#536675")

            cercle = QGraphicsEllipseItem(
                x - taille / 2,
                y - taille / 2,
                taille,
                taille,
            )
            cercle.setBrush(QBrush(couleur))
            cercle.setPen(QPen(Qt.GlobalColor.white, 2))
            self.scene.addItem(cercle)

            texte = QGraphicsTextItem(nom)
            texte.setDefaultTextColor(Qt.GlobalColor.white)
            texte.setPos(x - 10, y - 14)
            self.scene.addItem(texte)

    def dessiner_informations(self):
        texte_titre = QGraphicsTextItem(
            "Trajet le plus rapide calculé par Dijkstra"
        )
        texte_titre.setDefaultTextColor(QColor("#193047"))
        texte_titre.setPos(30, 500)
        self.scene.addItem(texte_titre)

        chemin_texte = " → ".join(
            [self.chemin[0][0]]
            + [arrivee for _, arrivee in self.chemin]
        )

        texte_chemin = QGraphicsTextItem(
            f"Chemin : {chemin_texte} | Temps total : {self.temps_total} secondes"
        )
        texte_chemin.setDefaultTextColor(QColor("#168bd1"))
        texte_chemin.setPos(30, 530)
        self.scene.addItem(texte_chemin)


def main():
    application = QApplication(sys.argv)

    fenetre = FenetrePrincipale()
    fenetre.show()

    sys.exit(application.exec())


if __name__ == "__main__":
    main()