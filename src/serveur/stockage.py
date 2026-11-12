"""Sauvegarde MariaDB : validation, requêtes paramétrées et transaction.

Une nouvelle connexion SQL par opération : pas de connexion partagée entre threads.
L'accès local utilise le compte Linux (unix_socket), sans mot de passe dans le code.
"""
import getpass
import hashlib
import json
import math
import os
from uuid import UUID

VERSION_MODELE = "carrefour-40ms-v1"


class ErreurStockage(Exception):
    """Erreur lisible pour le client, sans paramètres de connexion SQL."""


def verifier_bilan(bilan):
    """Renvoie une copie normalisée, ou refuse avant toute écriture."""
    if not isinstance(bilan, dict):
        raise ValueError("Bilan manquant")
    try:
        identifiant = str(UUID(bilan.get("identifiant", "")))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Identifiant de comparaison invalide") from None
    if type(bilan.get("densite")) is not int or not 0 <= bilan["densite"] <= 100:
        raise ValueError("Densité invalide")
    if bilan.get("direction") not in ("N", "S", "E", "O"):
        raise ValueError("Direction invalide")
    if type(bilan.get("graine")) is not int or not 0 <= bilan["graine"] <= 2**32-1:
        raise ValueError("Graine invalide")
    if bilan.get("version_modele") != VERSION_MODELE or type(bilan.get("duree_s")) is not int or bilan["duree_s"] != 120:
        raise ValueError("Version ou durée de comparaison incompatible")
    resultats = bilan.get("resultats")
    if not isinstance(resultats, list) or len(resultats) != 2:
        raise ValueError("Deux résultats attendus : sans puis avec priorité")
    valides = []
    for r in resultats:
        if not isinstance(r, dict):
            raise ValueError("Résultat invalide")
        valeurs = {}
        for cle in ("mission", "attente", "moyenne", "pietons"):
            valeur = r.get(cle)
            if cle in ("mission", "pietons") and cle in r and valeur is None:
                valeurs[cle] = None  # Mission/traversée non terminée.
                continue
            limite = 1000000 if cle == "attente" else 120
            if type(valeur) not in (int, float) or not math.isfinite(valeur) or not 0 <= valeur <= limite:
                raise ValueError(f"Durée invalide : {cle}")
            valeurs[cle] = float(valeur)
        for cle in ("demandes", "entrees", "sorties", "refusees"):
            valeur = r.get(cle)
            if type(valeur) is not int or not 0 <= valeur <= 604:
                raise ValueError(f"Compteur invalide : {cle}")
            valeurs[cle] = valeur
        if valeurs["demandes"] != valeurs["entrees"] + valeurs["refusees"] or valeurs["sorties"] > valeurs["entrees"]:
            raise ValueError("Compteurs incohérents")
        if not math.isclose(valeurs["moyenne"], valeurs["attente"] / max(1, valeurs["entrees"]), abs_tol=1e-6):
            raise ValueError("Attente moyenne incohérente")
        valides.append(valeurs)
    if valides[0]["demandes"] != valides[1]["demandes"]:
        raise ValueError("Les deux scénarios doivent avoir la même demande")
    return {"identifiant": identifiant, "densite": bilan["densite"],
            "direction": bilan["direction"], "graine": bilan["graine"],
            "duree_s": 120, "version_modele": VERSION_MODELE, "resultats": valides}


class StockageMariaDB:
    def __init__(self, **options):
        try:
            import mariadb
        except ImportError:
            raise ErreurStockage("Installer python3-mariadb-connector dans la VM serveur") from None
        self.pilote = mariadb
        self.options = dict(
            unix_socket=os.environ.get("TEAM_SYSTEM_DB_SOCKET", "/run/mysqld/mysqld.sock"),
            user=os.environ.get("TEAM_SYSTEM_DB_USER", getpass.getuser()),
            database=os.environ.get("TEAM_SYSTEM_DB_NAME", "team_system"),
            connect_timeout=2, read_timeout=2, write_timeout=2,
        )
        self.options.update(options)

    def connecter(self):
        try:
            return self.pilote.connect(**self.options)
        except self.pilote.Error:
            raise ErreurStockage("MariaDB inaccessible : vérifier le service et lancer bdd/installer.sh") from None

    def verifier(self):
        connexion = self.connecter()
        try:
            curseur = connexion.cursor()
            curseur.execute("SELECT id FROM comparaison LIMIT 0")
            curseur.execute("SELECT comparaison_id FROM resultat LIMIT 0")
        except self.pilote.Error:
            raise ErreurStockage("Schéma absent ou accès refusé : lancer bdd/installer.sh") from None
        finally:
            connexion.close()

    def enregistrer(self, bilan):
        bilan = verifier_bilan(bilan)
        empreinte = hashlib.sha256(json.dumps(bilan, sort_keys=True, allow_nan=False).encode()).hexdigest()
        connexion = self.connecter()
        try:
            curseur = connexion.cursor()
            curseur.execute("SELECT id, empreinte FROM comparaison WHERE identifiant=?", (bilan["identifiant"],))
            existant = curseur.fetchone()
            if existant:
                if existant[1] != empreinte:
                    raise ValueError("Cet identifiant correspond déjà à un autre bilan")
                return existant[0]  # Nouvelle tentative après réponse réseau perdue.
            curseur.execute(
                "INSERT INTO comparaison (identifiant,empreinte,cree_le,densite,direction,graine,duree_s,version_modele) "
                "VALUES (?,?,UTC_TIMESTAMP(),?,?,?,?,?)",
                (bilan["identifiant"], empreinte, bilan["densite"], bilan["direction"],
                 bilan["graine"], bilan["duree_s"], bilan["version_modele"]))
            identifiant = curseur.lastrowid
            for priorite, r in enumerate(bilan["resultats"]):
                curseur.execute(
                    "INSERT INTO resultat (comparaison_id,priorite,mission_s,attente_s,moyenne_s,pietons_s,demandes,entrees,sorties,refusees) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (identifiant, priorite, r["mission"], r["attente"], r["moyenne"], r["pietons"],
                     r["demandes"], r["entrees"], r["sorties"], r["refusees"]))
            connexion.commit()  # Les deux résultats sont sauvegardés ensemble.
            return identifiant
        except self.pilote.Error:
            connexion.rollback()
            raise ErreurStockage("Échec de sauvegarde MariaDB : réessayer ; aucun succès confirmé") from None
        finally:
            connexion.close()

    def historique(self):
        """Les 50 dernières comparaisons, deux lignes par comparaison."""
        connexion = self.connecter()
        try:
            curseur = connexion.cursor(dictionary=True)
            curseur.execute(
                "SELECT c.id, DATE_FORMAT(c.cree_le, '%Y-%m-%d %H:%i:%s') AS date_utc, "
                "c.densite,c.direction,c.graine,c.duree_s,c.version_modele, "
                "r.priorite,r.mission_s,r.attente_s,r.moyenne_s,r.pietons_s, "
                "r.demandes,r.entrees,r.sorties,r.refusees "
                "FROM (SELECT * FROM comparaison ORDER BY id DESC LIMIT 50) c "
                "JOIN resultat r ON r.comparaison_id=c.id ORDER BY c.id DESC,r.priorite")
            return curseur.fetchall()
        except self.pilote.Error:
            raise ErreurStockage("Lecture de l'historique MariaDB impossible") from None
        finally:
            connexion.close()
