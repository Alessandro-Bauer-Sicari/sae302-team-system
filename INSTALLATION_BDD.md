# Team System — Installer MariaDB

Cette archive contient le projet complet mis à jour. Utiliser cette version sur
le PC graphique ET sur la VM serveur : ne pas garder un ancien serveur en marche.
La base conserve les comparaisons terminées (avec et sans priorité), pas chaque
événement de la simulation libre. Aucun serveur MariaDB à installer sur Windows.

## 1. Sur la VM Debian 13

Télécharger et extraire cette archive sur la VM. Ouvrir le dossier `carrefour-bdd`
qui contient `lancer.py`, `src` et `bdd`, puis ouvrir un terminal dans ce dossier
(clic droit dans un espace vide du dossier, « Ouvrir dans un terminal »).
Arrêter l'ancien serveur avec Ctrl+C dans son terminal.

Depuis le compte normal `vboxuser`, lancer :

```bash
bash bdd/installer.sh
```

Saisir le mot de passe de vboxuser si sudo le demande. Le script installe MariaDB
et son connecteur Python Debian, démarre le service, crée la base `team_system`
et les tables sans supprimer les données existantes. Le message attendu est :
`MariaDB prête pour Team System`.

Puis, dans le même dossier et avec le même compte :

```bash
python3 -m src.serveur.serveur --hote 0.0.0.0 --port 5000 --bdd
```

Garder ce terminal ouvert. Utiliser le Python système `python3` pour le serveur,
car le connecteur est installé par apt, pas dans un environnement virtuel.
Ne pas lancer le serveur avec sudo. MariaDB se relance au démarrage de la VM ;
le serveur Python doit être relancé avec la commande ci-dessus.

## 2. Sur Windows

Fermer l'ancienne fenêtre du carrefour. Extraire aussi la nouvelle archive sur
Windows. Exemple : placer le dossier `carrefour-bdd` dans `C:\Temp`.
Dans PowerShell :

```powershell
cd C:\Temp\carrefour-bdd
& "C:\Python315\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe lancer.py
```

Le chemin Python correspond à celui montré sur ton PC ; l'adapter si tu changes
de machine. Python et PyQt6 doivent déjà être disponibles ou installables sur le
poste graphique. Sur un PC IUT sans ces logiciels, utiliser une VM graphique
préparée à l'avance. MariaDB n'ajoute aucune dépendance au client Windows.

Dans l'interface, saisir `192.168.56.103`, port `5000`, puis **Connecter**.
Cette adresse correspond à la dernière capture de ta VM ; vérifier `ip -br a`
si elle change.

## 3. Vérifier l'enregistrement

1. Cliquer sur **Comparer avec / sans priorité** pendant la connexion au serveur.
2. Attendre la fin du calcul : la sauvegarde est automatique.
3. Vérifier le message **Comparaison n°… enregistrée dans MariaDB**.
4. Fermer la comparaison, puis cliquer sur **Historique MariaDB**.
5. Les deux lignes représentent les résultats sans et avec priorité. Fermer puis
   rouvrir l'application permet de vérifier que l'historique est conservé.

Si la BDD est indisponible, l'interface affiche l'erreur et permet de réessayer.
Le CSV reste disponible. Une nouvelle tentative du même bilan ne crée pas de
copie supplémentaire. Une comparaison faite sans connexion n'est pas sauvegardée
automatiquement plus tard : se connecter puis relancer une comparaison.

Pour voir directement les tables, depuis le dossier du projet sur Debian :

```bash
mariadb team_system < bdd/verifier.sql
```

## Ce que contiennent les tables

| Table | Contenu |
| --- | --- |
| comparaison | Identifiant, date UTC, densité, direction, graine, durée et version du modèle |
| resultat | Deux lignes par comparaison : priorité, temps de mission, attente des voitures et piétons, demandes, entrées, sorties et refus |

`resultat.comparaison_id` référence `comparaison.id`. Les deux résultats sont
insérés dans une même transaction : si une insertion échoue, tout est annulé.
Les valeurs sont vérifiées côté serveur et les requêtes SQL sont paramétrées.
Les résultats sont calculés par le client ; le serveur contrôle leur format et
leur cohérence, sans recalculer les deux simulations.

L'utilisateur SQL local porte le nom du compte Linux et s'authentifie par socket
Unix. Il ne reçoit que SELECT et INSERT. Aucun mot de passe SQL dans GitHub.
Le client communique uniquement avec le serveur Python sur TCP 5000 ; aucun
accès distant à MariaDB n'est nécessaire. Les rôles TCP ne constituent pas une
authentification des clients : cette fonctionnalité reste distincte.

## GitHub

Copier le contenu de `carrefour-bdd` à la **racine du dépôt**, là où se trouve
le README principal : `lancer.py`, `src/`, `bdd/`, etc. Ne pas déposer le dossier
complet dans `src/` : cela produirait `src/src/` et garderait l'ancien code actif.
Conserver vos documents scolaires existants. Ne pas publier le ZIP ni `.venv`.

Nom du commit : `Ajouter MariaDB et l historique des comparaisons`.

## Vérification effectuée

19 tests réussis avec une vraie instance MariaDB 11.8.6, Python 3.12 et PyQt6 6.12.
Ils couvrent le contrôleur, le réseau, la comparaison, la sauvegarde, la relecture,
les doublons, l'annulation de transaction, une panne de BDD et l'interface Qt.
L'installation par sudo/apt et l'authentification Unix doivent encore être
vérifiées sur ta VM ; le test MariaDB ici utilisait une connexion TCP locale.

Sans configuration de base de test, `python -m unittest discover -s tests -v`
exécute 14 tests et ignore les 5 tests MariaDB. Pour ces derniers, voir
`docs/TESTS_BDD.md`. Ne jamais utiliser la base contenant vos vrais résultats
pour les tests : ils effacent les tables de la base dédiée.
