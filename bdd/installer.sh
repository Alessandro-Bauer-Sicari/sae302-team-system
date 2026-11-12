#!/bin/bash
# Lancer avec : bash bdd/installer.sh (depuis le compte normal, sans sudo devant).
set -euo pipefail
cd "$(dirname "$0")/.."
utilisateur_bdd="$(id -un)"
if [[ "$utilisateur_bdd" == root || ! "$utilisateur_bdd" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
    echo "Lancer ce script depuis le compte Linux normal (par exemple vboxuser)."
    exit 1
fi
sudo apt update
sudo apt install -y mariadb-server python3-mariadb-connector
sudo systemctl enable --now mariadb
sudo mariadb < bdd/schema.sql
# Compte SQL local lié au compte Linux : aucun mot de passe à publier sur GitHub.
sudo mariadb <<SQL
CREATE USER IF NOT EXISTS '$utilisateur_bdd'@'localhost' IDENTIFIED VIA unix_socket;
GRANT SELECT, INSERT ON team_system.* TO '$utilisateur_bdd'@'localhost';
SQL
python3 -c 'from src.serveur.stockage import StockageMariaDB; StockageMariaDB().verifier(); print("MariaDB prête pour Team System")'
