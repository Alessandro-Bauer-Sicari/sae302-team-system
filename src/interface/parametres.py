"""Dimensions, vitesses, durées et couleurs de la maquette."""

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

