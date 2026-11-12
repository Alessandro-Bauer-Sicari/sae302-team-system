# Team System — Carrefour connecté

Maquette pédagogique de la SAÉ 3.02 : un carrefour, quatre entrées, voitures,
ambulance prioritaire, piétons, accidents et comparaison avec/sans priorité.
Interface Python/PyQt6, serveur TCP/JSON avec la bibliothèque standard.

## Nouvelle version avec MariaDB

Pour installer la base sur la VM Debian et connecter Windows, suivre
**[INSTALLATION_BDD.md](INSTALLATION_BDD.md)**. Le serveur doit être lancé avec
`--bdd` pour enregistrer les comparaisons et consulter leur historique.
Les commandes ci-dessous sans cette option restent utilisables sans base.

## Démarrage sous Windows

Extraire ce dossier, par exemple dans `C:\Temp\carrefour-final`.
Ouvrir PowerShell et se placer dans le dossier contenant `lancer.py` :

```powershell
cd C:\Temp\carrefour-final
```

Si l'environnement `C:\.venv` utilisé précédemment existe :

```powershell
C:\.venv\Scripts\python.exe -m pip install -r requirements.txt
C:\.venv\Scripts\python.exe -m src.serveur.serveur
```

Garder ce premier terminal ouvert. Dans un deuxième PowerShell :

```powershell
cd C:\Temp\carrefour-final
C:\.venv\Scripts\python.exe lancer.py
```

Dans la fenêtre, garder `127.0.0.1`, port `5000`, puis cliquer sur **Connecter**.
Le texte « Serveur actif — étape … » doit avancer. Les détections sont automatiques.
Il ne faut pas lancer en plus les anciens clients de terminal : leurs rôles sont
utilisés par la fenêtre.

Si `C:\.venv` n'existe pas, créer un environnement avec le Python complet déjà
repéré sur ton ordinateur (adapter le chemin si nécessaire) :

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Dans les commandes précédentes, remplacer ensuite `C:\.venv\Scripts\python.exe`
par `.\.venv\Scripts\python.exe`. Ne pas utiliser le Python de WAPT.

## Autre système ou VM

Python 3.10 ou supérieur pour l'interface ; version vérifiée : Python 3.12.14,
PyQt6 6.12.0. Depuis la racine du projet :

```bash
python -m venv .venv
# Linux : source .venv/bin/activate
# Windows : utiliser directement .venv\Scripts\python.exe
python -m pip install -r requirements.txt
python -m src.serveur.serveur --hote 0.0.0.0 --port 5000
```

Sur le poste graphique, lancer `python lancer.py`, saisir l'adresse IP de la VM
serveur et cliquer sur **Connecter**. Le serveur seul ne nécessite pas PyQt6.
Autoriser TCP 5000 sur le réseau privé entre ces deux postes si le pare-feu le bloque.

**Les VM ne sont pas créées par ce code.** La recette sur les machines finales reste à effectuer.

## Fonctionnement du réseau

La fenêtre ouvre trois connexions TCP distinctes, dans un thread réseau :

1. **Capteur** : transmet occupation, direction de l'ambulance, option de priorité,
   demande de piétons et traversée en cours.
2. **Régulateur** : demande au serveur de calculer la prochaine étape.
3. **Feux** : reçoit la commande, qui est appliquée aux feux et aux déplacements Qt.

Ces trois clients logiques tournent dans le même programme graphique. Cette version
se déploie donc sur une machine serveur et une machine graphique, physiques ou VM.
Elle ne fournit pas trois applications graphiques réparties sur trois VM clientes.
Vérifier la répartition demandée avec les consignes du cours avant de créer les VM.

Une seule mesure est en attente à la fois. Les messages portent un numéro d'étape.
Le serveur refuse les messages périmés, les étapes désordonnées et les mauvais rôles.
Le temps avance de **40 ms simulées** après chaque réponse appliquée. Le réseau lent
ralentit la simulation ; il ne fait jamais sauter une phase de sécurité.

En l'absence de réponse pendant une seconde : tous les feux affichent rouge et la
simulation reste suspendue. Le thread ferme ses connexions au plus tard après son
délai réseau de cinq secondes par échange en cours. Une reconnexion repart au rouge.
**Reprendre en local** permet de reprendre explicitement sans serveur.

Les rôles sont des identifiants de protocole, pas une authentification.

## Règles de circulation

- Cycle normal : nord/sud vert 10 s, orange 2 s, tout rouge 1 s ; puis est/ouest pareil.
- Un véhicule déjà engagé finit de traverser. L'autre axe attend que la zone soit libre.
- Ambulance : détection dès la demande, même si elle attend pour entrer ; vert opposé
  ramené à 3 s maximum, puis orange et tout rouge. Vert prioritaire maintenu jusqu'au
  franchissement de la sortie à 565 pixels par le centre du véhicule.
- Le choix « Priorité ambulance » s'applique à la prochaine mission.
- Les piétons demandent une traversée : elle commence au tout rouge, carrefour libre,
  sans priorité ambulance active. Une traversée commencée se termine toujours : 6,8 s.
- Densité : probabilité d'une tentative d'arrivée, par entrée, toutes les 800 ms.
  Une entrée encombrée refuse l'arrivée ; aucune file cachée hors écran.
- Accident : une voiture immobilisée 20 s, hors centre et passages piétons ; dégagement
  manuel possible. Les accidents automatiques tentent une création en moyenne toutes
  les 55 s. L'ambulance ne double pas une voiture bloquée.
- Le journal utilise le temps simulé.

## Comparaison et export

Le bouton « Comparer avec / sans priorité » suspend la démonstration, puis simule
120 s deux fois : même densité, direction, graine 2026, ambulance à 12 s et piétons
à 24 s. Accidents désactivés pour rendre l'expérience reproductible.

Le calcul est local et utilise exactement la classe de décision employée par le
serveur. Il mesure la politique de priorité, pas la latence réseau. Le tableau et
l'export CSV comprennent temps de mission, attente des piétons, attente automobile,
arrivées demandées, admises, refusées et sorties. Une mission non terminée est indiquée.
Le gain de l'ambulance peut augmenter l'attente des autres usagers.

## Fichiers à apprendre dans cet ordre

| Fichier | Rôle |
| --- | --- |
| `lancer.py` | Démarrage de la fenêtre |
| `src/interface/parametres.py` | Dimensions et paramètres d'affichage |
| `src/interface/dessin.py` | Dessin du carrefour et des usagers |
| `src/controleur.py` | Décisions et durées des feux, sans Qt |
| `src/interface/simulation.py` | Déplacements, ambulance, piétons et accidents |
| `src/interface/main.py` | Boutons, horloge et application des commandes |
| `src/interface/comparaison.py` | Deux expériences et export CSV |
| `src/reseau.py` | Messages JSON délimités par une fin de ligne |
| `src/clients/client.py` | Connexion TCP et échanges demande/réponse |
| `src/clients/client_qt.py` | Trois connexions dans un thread Qt |
| `src/serveur/maquette.py` | Ordre des étapes et contrôle des révisions |
| `src/serveur/serveur.py` | Serveur multiclient et verrou d'accès |
| `src/serveur/stockage.py` | Validation et requêtes MariaDB |
| `src/interface/historique.py` | Consultation des résultats sauvegardés |
| `bdd/schema.sql` | Création des deux tables |
| `tests/test_integration.py` et `tests/test_bdd.py` | Tests automatiques |

`src/clients/capteur.py` et `feux.py` restent des outils manuels de diagnostic hors
session graphique. Leur cycle historique n'est pas utilisé par la maquette connectée.

## Vérification

```powershell
C:\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les tests fonctionnent sans écran grâce au mode Qt `offscreen`. Voir
`docs/TESTS_ETAPE_1.md` pour le résultat et les limites de la recette.

## Ajouter au dépôt GitHub

Cette archive contient le code complet de cette étape, à copier dans la racine du
dépôt existant. **Conserver les documents déjà présents dans `docs` et `bdd`.**
Ne pas envoyer `.venv`, `__pycache__` ou le ZIP dans le dépôt.

```bash
git add src bdd lancer.py requirements.txt README.md INSTALLATION_BDD.md tests docs
git commit -m "Ajouter MariaDB et l historique des comparaisons"
git push
```

Le code inclut la sauvegarde MariaDB. Les rendus scolaires et les
tests sur les machines finales restent à réaliser.
