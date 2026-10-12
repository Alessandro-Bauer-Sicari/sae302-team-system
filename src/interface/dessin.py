"""Dessin de la maquette et positionnement des objets Qt."""

from PyQt6.QtCore import (
    Qt,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QPen,
)
if __package__:
    from .parametres import (CENTRE, COULEURS_FEUX, DEMI_ROUTE, TAILLE)
else:
    from parametres import (CENTRE, COULEURS_FEUX, DEMI_ROUTE, TAILLE)


class DessinCarrefour:
    """Méthodes de dessin utilisées par la fenêtre principale."""

    def placer_pieton(self, pieton):
        """Place le piéton sur les bandes blanches de son passage."""
        position = 298 + pieton["distance"]
        direction = pieton["direction"]
        if direction in ("N", "S"):
            x, y = position, 286 if direction == "N" else 514
        else:
            x, y = 514 if direction == "E" else 286, position
        pieton["dessin"].setPos(x, y)

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
