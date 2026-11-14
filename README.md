# Team System - Carrefour connecté

**SAÉ 3.02 - Alessandro BAUER-SICARI et Yacine BENNOUNE**

Notre projet est une simulation de carrefour en Python. On peut régler le trafic, envoyer une ambulance, demander une traversée piétonne et provoquer un accident. On peut aussi comparer le temps de passage avec et sans priorité, puis garder les résultats dans MariaDB.

L’interface graphique a été réalisée avec l’aide de l’IA. L’IA nous a aussi aidés pour le code, les tests et les erreurs d’installation. Les détails sont dans [IAGraphie.pdf](IAGraphie.pdf).

## Installation complète, dans l’ordre

Les commandes ci-dessous correspondent à nos deux VM Debian 13 avec un bureau graphique. Notre compte Linux s’appelle `vboxuser`. Remplacer ce nom si votre compte est différent. Les réglages réseau se font dans le terminal de VirtualBox, car ils peuvent couper une connexion distante.

### 1. Préparer les cartes dans VirtualBox

Éteindre les deux VM. Dans **Configuration > Réseau**, faire les réglages suivants sur chacune :

- **Carte 1 : NAT**, avec « Câble branché » coché, pour Internet.
- **Carte 2 : Réseau privé hôte (Host-only)**, avec « Câble branché » coché.
- Choisir le **même réseau privé hôte** pour les deux VM. Dans nos essais, c’est le réseau `192.168.56.0/24`, avec le serveur DHCP VirtualBox activé.

Si aucun réseau privé hôte n’existe, le créer dans le gestionnaire réseau de VirtualBox et activer son DHCP. Démarrer ensuite les VM. Les commandes Linux ne remplacent pas ces réglages VirtualBox.

### 2. Donner les droits sudo au compte — sur chaque VM

Si le message `vboxuser is not in the sudoers file` apparaît, ouvrir une session root :

```bash
su -
```

Saisir le **mot de passe root**, puis exécuter :

```bash
usermod -aG sudo vboxuser
reboot
```

Après le redémarrage, se reconnecter avec `vboxuser`, puis vérifier :

```bash
id
sudo -v
```

Cette fois, sudo demande le **mot de passe de vboxuser**. Les mots de passe ne s’affichent pas pendant la saisie. Si le compte a déjà les droits sudo, passer directement à l’étape suivante. Si le mot de passe root n’est pas disponible sur une machine de l’IUT, demander à l’enseignant d’accorder les droits nécessaires.

### 3. Nommer les VM

Sur la VM serveur uniquement :

```bash
sudo hostnamectl set-hostname TEAM-SYSTEM-SERVEUR
```

Sur la VM cliente uniquement :

```bash
sudo hostnamectl set-hostname TEAM-SYSTEM-CLIENT
```

Sur chaque VM, vérifier :

```bash
hostname
```

Le nom dans un terminal déjà ouvert peut rester ancien : fermer puis rouvrir ce terminal.

### 4. Repérer les cartes et les profils — sur chaque VM

```bash
ip -br a
nmcli device status
nmcli -f NAME,UUID,TYPE,DEVICE connection show
```

Dans notre installation :

| Élément | Nom utilisé |
| --- | --- |
| Carte NAT, Internet | `enp0s3` |
| Carte du réseau privé entre les VM | `enp0s8` |
| Profil initial partagé entre les cartes | `Wired connection 1` |

**Adapter les noms dans les commandes suivantes si les résultats sont différents.** Ces commandes supposent NetworkManager, comme dans nos VM Debian graphiques. Notre problème venait d’un seul profil utilisé alternativement par les deux cartes.

### 5. Fixer le profil privé sur la deuxième carte — sur chaque VM

```bash
sudo nmcli connection modify "Wired connection 1" connection.interface-name enp0s8 connection.autoconnect yes ipv4.never-default yes ipv6.never-default yes
```

Cette commande réserve le profil à `enp0s8`. Elle empêche aussi cette carte de remplacer la route Internet. Le profil de nos VM utilise déjà DHCP ; les adresses privées sont attribuées par VirtualBox.

### 6. Créer le profil Internet — sur chaque VM

Si aucun profil `INTERNET` n’existe dans la liste de l’étape 4, le créer une seule fois :

```bash
sudo nmcli connection add type ethernet ifname enp0s3 con-name INTERNET ipv4.method auto connection.autoconnect yes
```

S’il existe déjà, ne pas le recréer. Pour vérifier et remettre ses paramètres :

```bash
sudo nmcli connection modify INTERNET connection.interface-name enp0s3 connection.autoconnect yes ipv4.method auto ipv4.never-default no
```

Activer les deux profils :

```bash
sudo nmcli connection up "Wired connection 1"
sudo nmcli connection up INTERNET
```

### 7. Vérifier le réseau — sur chaque VM

```bash
ip -br a
ip route
getent hosts github.com
```

Résultat attendu dans notre configuration :

- `enp0s3` possède une adresse NAT, généralement `10.0.2.15`.
- `enp0s8` possède une adresse privée en `192.168.56.x`.
- La route `default` passe par `10.0.2.2` sur `enp0s3`.
- `getent hosts github.com` affiche une adresse IP.

Les deux VM peuvent avoir la même adresse NAT `10.0.2.15` : c’est normal avec leurs réseaux NAT séparés. Pour les relier, utiliser les adresses **privées** d’`enp0s8`, qui doivent être différentes.

Nos adresses lors des essais : serveur **192.168.56.103**, client **192.168.56.104**. Elles peuvent changer après importation des VM : relever les adresses actuelles.

Depuis la VM cliente, tester le serveur (adapter l’adresse si elle a changé) :

```bash
ping -c 4 192.168.56.103
```

Si le ping ne répond pas, vérifier que le serveur est allumé et que les deux cartes privées utilisent le même réseau VirtualBox.

### 8. Installer les outils et récupérer le projet — sur chaque VM

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
python3 --version
cd ~
git clone https://github.com/Alessandro-Bauer-Sicari/sae302-team-system.git
cd ~/sae302-team-system
ls
```

On doit voir notamment `lancer.py`, `requirements.txt`, `src` et `bdd`.

**Si le dossier existe déjà**, ne pas refaire `git clone`. Utiliser à la place :

```bash
cd ~/sae302-team-system
git status
git pull --ff-only
ls
```

Conserver les modifications locales avant de mettre le dépôt à jour. Si Git bloque la mise à jour, ne pas supprimer les fichiers pour forcer le passage.

### 9. Installer MariaDB — uniquement sur la VM serveur

Depuis le compte normal `vboxuser` :

```bash
cd ~/sae302-team-system
bash bdd/installer.sh
systemctl is-active mariadb
mariadb team_system < bdd/verifier.sql
```

Le script installe MariaDB et `python3-mariadb-connector`, démarre le service et crée les tables. Le message attendu est `MariaDB prête pour Team System`. La vérification du service doit afficher `active`. Une base neuve ne contient pas encore de comparaisons.

Ne pas ajouter sudo devant `bash bdd/installer.sh` : le script utilise sudo seulement pour les opérations qui en ont besoin. Le compte SQL est lié au compte Linux ; aucun mot de passe SQL n’est à mettre dans le code.

### 10. Lancer le serveur Python

```bash
cd ~/sae302-team-system
python3 -m venv --system-site-packages .venv-serveur
.venv-serveur/bin/python -c "import mariadb; print('Connecteur MariaDB disponible')"
.venv-serveur/bin/python -m src.serveur.serveur --hote 0.0.0.0 --port 5000 --bdd
```

`--system-site-packages` permet au venv de voir le connecteur installé par Debian. Le serveur seul n’a pas besoin de PyQt6. Les messages attendus sont `MariaDB activée` puis `Serveur prêt sur 0.0.0.0:5000`. Garder ce terminal ouvert.

Dans nos essais, nous avons aussi utilisé directement le Python système, **à la place** du lancement précédent :

```bash
python3 -m src.serveur.serveur --hote 0.0.0.0 --port 5000 --bdd
```

Choisir un seul lancement : ne pas démarrer deux serveurs sur le même port.

### 11. Installer et lancer l’interface — uniquement sur la VM cliente

```bash
cd ~/sae302-team-system
sudo apt install -y libegl1 libxcb-cursor0
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python lancer.py
```

`requirements.txt` contient PyQt6 6.12.0. Les dépendances MariaDB du serveur sont installées séparément par le script. Les autres modules Python utilisés font partie de la bibliothèque standard.

Lors de nos essais sur Debian, nous avons utilisé cette autre méthode avec les paquets système :

```bash
sudo apt install -y python3-pyqt6
python3 lancer.py
```

Les deux méthodes sont des alternatives. Le Python utilisé pour lancer l’application doit pouvoir accéder à PyQt6. La méthode venv utilise la version fixée dans `requirements.txt` ; la méthode apt utilise celle fournie par Debian.

### 12. Connecter l’interface et vérifier la sauvegarde

Dans la fenêtre du client, saisir l’adresse privée actuelle du serveur, par exemple `192.168.56.103`, et le port `5000`, puis cliquer sur **Connecter**. Le texte **Serveur actif** doit apparaître et le numéro d’étape doit avancer.

Cliquer sur **Comparer avec / sans priorité**, attendre la confirmation d’enregistrement, puis ouvrir **Historique MariaDB**. Chaque comparaison a deux lignes. Fermer et rouvrir l’application permet de vérifier que les résultats sont conservés.

Ne pas lancer les anciens clients de diagnostic en même temps : l’interface ouvre déjà les trois connexions nécessaires.

### 13. Relancer le projet les jours suivants

Il n’est pas nécessaire de refaire les installations ou la configuration réseau.

Sur le serveur, avec le venv :

```bash
cd ~/sae302-team-system
.venv-serveur/bin/python -m src.serveur.serveur --hote 0.0.0.0 --port 5000 --bdd
```

Sur le client, avec le venv :

```bash
cd ~/sae302-team-system
.venv/bin/python lancer.py
```

Si l’installation a été faite avec les paquets système, utiliser les commandes `python3` indiquées aux étapes 10 et 11. MariaDB démarre normalement avec la VM. Si nécessaire, sur le serveur :

```bash
sudo systemctl start mariadb
```

Pour arrêter : fermer l’interface, puis faire **Ctrl+C** dans le terminal du serveur. Éteindre les VM normalement avant de les exporter.

## Utilisation

1. Démarrer le serveur, puis l’interface sur la VM cliente.
2. Saisir l’adresse du serveur (dans nos essais : `192.168.56.103`) et le port `5000`, puis cliquer sur **Connecter**. Vérifier l’adresse avec `ip -br a` sur le serveur si nécessaire.
3. Régler la densité, choisir une direction et envoyer une ambulance.
4. Cliquer sur **Comparer avec / sans priorité**, attendre la fin puis vérifier le message de sauvegarde.
5. Ouvrir **Historique MariaDB** pour retrouver les deux résultats de chaque comparaison. L’export CSV est aussi disponible.

Sans connexion au serveur, l’application fonctionne en local mais ne sauvegarde pas dans MariaDB. Fermer la fenêtre pour quitter ; Ctrl+C arrête le serveur.

## Tests et limites

Les connexions depuis Windows et entre les deux VM Debian ont été essayées. La sauvegarde et la relecture de l’historique fonctionnent. Le lancement sur les VM a été vérifié avec les paquets Python système ; le parcours venv ci-dessus reste à rejouer lors de la recette d’installation.

Pour lancer les tests depuis le dossier du projet sur le client :

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Sans base de test configurée, 14 tests s’exécutent et 5 tests MariaDB sont ignorés. Voir `docs/TESTS_BDD.md` pour les tests avec une base séparée. Ne pas utiliser la base de démonstration pour ces tests.

Le serveur reçoit trois connexions logiques regroupées dans la même interface. Les échanges TCP ne sont ni authentifiés ni chiffrés : utiliser le réseau privé de démonstration. L’ambulance ne dépasse pas les voitures accidentées. Une traversée piétonne commencée se termine avant son passage. La base garde les comparaisons, pas tous les événements.
