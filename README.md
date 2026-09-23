# SAÉ 3.02 — Team System

Maquette Python d’un carrefour connecté pour faciliter le passage des véhicules d’urgence.

## Équipe

- Alessandro BAUER-SICARI
- Yacine BENNOUNE

## État du projet

Projet en phase de démarrage. Le dépôt contient le cahier des charges et la structure de travail. L’application n’est pas encore développée et aucune commande de lancement n’est disponible.

## Objectif

Simuler un seul carrefour et réduire le temps de passage d’un véhicule d’urgence entre une entrée A et une sortie B. La priorité doit respecter les transitions des feux et l’occupation du carrefour. Le régulateur pourra régler la densité du trafic entre 0 et 100 %.

## Choix techniques prévus

- Python 3.12, PyCharm et environnement virtuel `venv`.
- PyQt6, avec `QGraphicsScene` / `QGraphicsView` pour l’affichage 2D.
- Un serveur central et trois clients : véhicule d’urgence, carrefour et régulateur.
- Sockets TCP brutes et messages JSON.
- QThread / signaux Qt et, selon le besoin, `threading`.
- MariaDB sur Linux.

Les versions des dépendances seront ajoutées à `requirements.txt` après installation et vérification. Les messages réseau, les ports et le schéma de la base restent à définir. Les machines visées sont Windows et Linux ; la compatibilité sera vérifiée pendant le développement.

## Organisation des fichiers

| Chemin | Contenu prévu |
| --- | --- |
| `src/serveur/` | Serveur de régulation et décisions de priorité |
| `src/clients/` | Communications des clients avec le serveur |
| `src/interface/` | Interface PyQt6 et affichage du carrefour |
| `src/simulation/` | Véhicules, trafic et états des feux |
| `bdd/` | Création de la base et configuration d’exemple |
| `docs/` | Cahier des charges, suivi et préparation de l’IA-graphie |

Les dossiers sont actuellement des emplacements de travail, sans code applicatif.

## Documentation

- [Cahier des charges](docs/Cahier_des_Charges_Team_System.pdf)
- [Suivi de l’utilisation de l’IA](docs/Suivi_IA.md)
- Les relevés hebdomadaires seront ajoutés dans `docs/comptes_rendus/`.

## Prochaines étapes

1. Cloner le dépôt dans PyCharm sur les deux postes et créer un environnement virtuel.
2. Installer PyQt6, vérifier une première fenêtre et fixer la version testée.
3. Tester un échange TCP simple entre un serveur et un client.
4. Développer progressivement les feux, la circulation et la priorité.
5. Ajouter MariaDB et documenter l’installation complète.

## Installation et recette finale

L’objectif demandé est de déployer et lancer le projet sur des machines vierges en **30 minutes maximum**. Ce délai n’a pas encore été testé. La procédure finale décrira les prérequis, la création du venv, les dépendances, MariaDB, la configuration réseau et l’ordre de lancement. Elle sera testée sur des machines vierges avant le rendu.

## Travail en binôme

Chacun utilisera son compte GitHub et conservera ses propres contributions. Les tâches, décisions et temps seront suivis chaque semaine. Les changements devront être compris et expliqués par les deux membres du binôme.

## Rendus prévus

- Dépôt GitHub public, code documenté, `requirements.txt` et README complet.
- `Bilan_Projet.pdf` à la racine du dépôt.
- `IAGraphie.pdf` ou section dédiée dans le bilan.
- Comptes rendus hebdomadaires et portfolios individuels.

Livraison visée : **15 novembre 2026**. Le portfolio est à rendre avant **23 h 59**.
