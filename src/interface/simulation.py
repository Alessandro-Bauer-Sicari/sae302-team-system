"""Mouvements, priorités et événements de la simulation.

Ces méthodes partagent encore les objets graphiques de la fenêtre.
Cette séparation organise le code ; le moteur n’est pas encore autonome.
"""

import random
from PyQt6.QtGui import (
    QBrush, QColor, QPen,
)
if __package__:
    from .parametres import (DISTANCE_ARRET, DISTANCE_SORTIE, ESPACEMENT, LARGEUR_VOITURE, LONGUEUR_VOITURE, PAS_TEMPS, PHASES, TAILLE, VITESSE)
else:
    from parametres import (DISTANCE_ARRET, DISTANCE_SORTIE, ESPACEMENT, LARGEUR_VOITURE, LONGUEUR_VOITURE, PAS_TEMPS, PHASES, TAILLE, VITESSE)


class SimulationCarrefour:
    """Règles de circulation utilisées par la fenêtre principale."""

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
