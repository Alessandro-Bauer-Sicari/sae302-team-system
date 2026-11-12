# Recette MariaDB — 12 novembre 2026

Résultat : 19 tests exécutés, tous réussis (6,896 secondes).
Environnement : MariaDB 11.8.6, connecteur Python mariadb 1.1.14,
Python 3.12, PyQt6 6.12, Qt offscreen.

Les cinq tests avec MariaDB vérifient :
- sauvegarde, relecture, réessai sans doublon et rejet d'un identifiant réutilisé ;
- annulation de toute la transaction si la deuxième insertion échoue ;
- limitation de l'historique aux 50 dernières comparaisons ;
- protocole TCP et maintien du serveur après une erreur de BDD ;
- sauvegarde automatique depuis la vraie fenêtre de comparaison, affichage de
  l'historique et reprise de la simulation après fermeture des fenêtres.

Deux tests supplémentaires valident les données et les rôles sans base.
Les douze tests précédents de simulation et de réseau passent également.

Pour reproduire les tests MariaDB, créer une base dédiée dont le nom finit par
`_test`, y appliquer `bdd/schema.sql` après remplacement de `team_system` par
le nom de test. Fournir un compte de test autorisé à SELECT, INSERT, DELETE et
TRIGGER sur cette base. Installer le connecteur MariaDB et PyQt6 dans le Python
qui exécute les tests.

Créer un JSON local, par exemple `/tmp/team-system-test.json` :

```json
{"database": "team_system_test", "user": "vboxuser", "unix_socket": "/run/mysqld/mysqld.sock"}
```

Puis, sous Linux, depuis la racine du projet :

```bash
TEAM_SYSTEM_TEST_CONFIG=/tmp/team-system-test.json python3 -m unittest discover -s tests -v
```

Les tests vident les deux tables de la base dédiée ; ils refusent un nom ne
finissant pas par `_test`. Le compte de production créé par installer.sh n'a
volontairement pas les droits DELETE et TRIGGER nécessaires aux tests.

Limites : pas de test sur votre Windows ni votre VM Debian ; le test réel de
MariaDB utilise TCP local. Les captures de comparaison et d'historique ont été
contrôlées. La recette du déploiement final reste à faire avec INSTALLATION_BDD.md.
