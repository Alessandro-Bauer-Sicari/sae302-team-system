"""Décision des feux, indépendante de Qt et du réseau.

Une étape correspond à 40 ms de simulation, pas au temps passé sur le réseau.
La même classe sert au serveur, au mode local et à la comparaison.
"""

PHASES = [("vert", "rouge", 10), ("orange", "rouge", 2),
          ("rouge", "rouge", 1), ("rouge", "vert", 10),
          ("rouge", "orange", 2), ("rouge", "rouge", 1)]
PAS = 0.04


def verifier_mesure(mesure):
    """Refuse les données incomplètes et les booléens déguisés en nombres."""
    if not isinstance(mesure, dict):
        raise ValueError("Mesure attendue")
    for cle in ("occupe", "pietons", "demande_pietons", "priorite"):
        if type(mesure.get(cle)) is not bool:
            raise ValueError(f"Booléen attendu : {cle}")
    if mesure.get("ambulance") not in (None, "N", "S", "E", "O"):
        raise ValueError("Direction ambulance invalide")
    if "ambulance" not in mesure:
        raise ValueError("Détection ambulance manquante")


class Controleur:
    """Six phases ; aucune ouverture d'axe tant que le centre est occupé."""

    def __init__(self):
        self.phase = 5
        self.restant = 1.0
        self.ancienne_cible = None

    def avancer(self, mesure):
        verifier_mesure(mesure)
        direction = mesure["ambulance"] if mesure["priorite"] else None
        cible = None if direction is None else (0 if direction in "NS" else 3)
        if self.ancienne_cible is not None and cible is None and self.phase in (0, 3):
            self.restant = min(self.restant, 3.0)
        self.ancienne_cible = cible
        traverser = False
        raison = "Cycle normal"
        if mesure["pietons"]:
            self.phase = 5
            self.restant = 1.0
            raison = "Fin de traversée des piétons"
        elif cible is not None and self.phase == cible:
            self.restant = 3.0
            raison = "Vert maintenu jusqu'à la sortie de l'ambulance"
        else:
            if cible is not None and self.phase in (0, 3):
                self.restant = min(self.restant, 3.0)
            self.restant = max(0.0, self.restant - PAS)
            if self.restant < 1e-8:
                if self.phase in (2, 5) and mesure["occupe"]:
                    raison = "Tout rouge : fin des traversées automobiles"
                elif self.phase in (2, 5) and mesure["demande_pietons"] and cible is None:
                    traverser = True
                    raison = "Piétons autorisés"
                else:
                    self.phase = cible if self.phase in (2, 5) and cible is not None else (self.phase + 1) % 6
                    self.restant = float(PHASES[self.phase][2])
        ns, eo, _ = PHASES[self.phase]
        return {"phase": self.phase, "restant": round(self.restant, 4),
                "feux": {"N": ns, "S": ns, "E": eo, "O": eo},
                "traverser": traverser, "raison": raison}


def verifier_commande(commande):
    """Vérifie une réponse avant de l'appliquer à la maquette."""
    import math
    phase = commande.get("phase")
    if type(phase) is not int or not 0 <= phase < 6:
        raise ValueError("Phase invalide")
    ns, eo, _ = PHASES[phase]
    if commande.get("feux") != {"N": ns, "S": ns, "E": eo, "O": eo}:
        raise ValueError("Couleurs incompatibles avec la phase")
    restant = commande.get("restant")
    if type(restant) not in (int, float) or not math.isfinite(restant) or not 0 <= restant <= 10:
        raise ValueError("Durée invalide")
    if type(commande.get("traverser")) is not bool:
        raise ValueError("Autorisation piétonne invalide")
    if commande["traverser"] and phase not in (2, 5):
        raise ValueError("Piétons autorisés avec un feu automobile ouvert")
