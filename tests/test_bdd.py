"""Tests MariaDB réels, activés avec TEAM_SYSTEM_TEST_CONFIG (JSON local).

Utiliser une base dédiée dont le nom se termine par _test : ces tests vident
ses deux tables. Les tests de validation seuls ne nécessitent pas MariaDB.
"""
import copy
import json
import os
from pathlib import Path
import threading
import unittest
from uuid import uuid4

from src.serveur.stockage import StockageMariaDB, ErreurStockage, verifier_bilan
from src.serveur.serveur import Serveur
from src.clients.client import Client


def bilan():
    """Renvoie un bilan valide avec un identifiant unique pour les tests."""
    r = dict(mission=12.0, attente=20.0, moyenne=2.0, pietons=None,
             demandes=12, entrees=10, sorties=8, refusees=2)
    return dict(identifiant=str(uuid4()), densite=45, direction='N', graine=2026,
                duree_s=120, version_modele='carrefour-40ms-v1', resultats=[r.copy(), r.copy()])


class ValidationTests(unittest.TestCase):
    """Teste les données et les droits de rôle sans connexion à MariaDB."""
    def test_valeurs_invalides_refusees(self):
        """Vérifie le rejet des valeurs invalides et accepte une mission non terminée."""
        for cle, valeur in [('densite', True), ('densite', 101), ('direction', "N';DROP TABLE resultat;--"),
                            ('graine', -1), ('duree_s', 119), ('identifiant', 'invalide')]:
            b=bilan();b[cle]=valeur
            with self.assertRaises(ValueError):verifier_bilan(b)
        for cle, valeur in [('mission', float('nan')), ('attente', -1), ('entrees', True), ('moyenne', 8)]:
            b=bilan();b['resultats'][0][cle]=valeur
            with self.assertRaises(ValueError):verifier_bilan(b)
        b=bilan();b['resultats'][0]['mission']=None
        self.assertIsNone(verifier_bilan(b)['resultats'][0]['mission'])

    def test_bdd_desactivee_et_role(self):
        """Vérifie les erreurs si le rôle est incorrect ou si MariaDB est désactivée."""
        s=Serveur()
        self.assertEqual(s.traiter_bdd('capteur',{'type':'historique'})['type'],'erreur_bdd')
        self.assertIn('désactivée',s.traiter_bdd('regulateur',{'type':'historique'})['message'])


@unittest.skipUnless(os.environ.get('TEAM_SYSTEM_TEST_CONFIG'), 'Configurer une base MariaDB dédiée aux tests')
class MariaDBTests(unittest.TestCase):
    """Teste le stockage réel dans une base dédiée dont les tables sont vidées."""
    def setUp(self):
        """Charge la configuration et vide les deux tables de la base de test.

        Raises:
            RuntimeError: Si le nom de la base ne se termine pas par _test.
            ErreurStockage: Si la base ou son schéma est inaccessible.
        """
        self.options=json.loads(Path(os.environ['TEAM_SYSTEM_TEST_CONFIG']).read_text())
        if not self.options.get('database','').endswith('_test'):
            raise RuntimeError('Les tests nécessitent une base dédiée terminant par _test')
        self.stockage=StockageMariaDB(**self.options)
        self.stockage.verifier()
        c=self.stockage.connecter()
        try:
            cur=c.cursor();cur.execute('DELETE FROM resultat');cur.execute('DELETE FROM comparaison');c.commit()
        finally:c.close()

    def test_sauvegarde_relecture_doublon_et_conflit(self):
        """Vérifie la persistance, le réessai sans doublon et le rejet d'un conflit."""
        b=bilan();numero=self.stockage.enregistrer(b)
        self.assertEqual(numero,self.stockage.enregistrer(b))
        nouveau=StockageMariaDB(**self.options)
        lignes=nouveau.historique()
        self.assertEqual(len(lignes),2)
        self.assertEqual([r['priorite'] for r in lignes],[0,1])
        self.assertTrue(all(r['pietons_s'] is None for r in lignes))
        self.assertEqual(lignes[0]['mission_s'],12)
        b['densite']=46
        with self.assertRaises(ValueError):self.stockage.enregistrer(b)
        self.assertEqual(len(nouveau.historique()),2)

    def test_transaction_annulee_si_second_resultat_echoue(self):
        """Force une erreur SQL pour vérifier que toute la comparaison est annulée."""
        c=self.stockage.connecter();cur=c.cursor()
        cur.execute("CREATE TRIGGER echec_test BEFORE INSERT ON resultat FOR EACH ROW BEGIN IF NEW.priorite=1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test rollback'; END IF; END")
        c.close()
        try:
            with self.assertRaises(ErreurStockage):self.stockage.enregistrer(bilan())
            c=self.stockage.connecter();cur=c.cursor();cur.execute('SELECT COUNT(*) FROM comparaison')
            self.assertEqual(cur.fetchone()[0],0);c.close()
            self.assertEqual(self.stockage.historique(),[])
        finally:
            c=self.stockage.connecter();c.cursor().execute('DROP TRIGGER echec_test');c.close()

    def test_50_derniers_bilans_et_taille_message(self):
        """Vérifie la limite de 50 comparaisons et la taille de la réponse JSON."""
        from src.reseau import ConnexionJSON
        for _ in range(52):self.stockage.enregistrer(bilan())
        lignes=self.stockage.historique()
        self.assertEqual(len(lignes),100)
        self.assertLess(len(json.dumps({'type':'historique','lignes':lignes}).encode()),65536)
        self.assertGreater(lignes[0]['id'],lignes[-1]['id'])

    def test_tcp_sauvegarde_et_panne_bdd(self):
        """Vérifie les opérations MariaDB par TCP et la survie du serveur après une panne."""
        serveur=Serveur(port=0,stockage=self.stockage)
        t=threading.Thread(target=serveur.demarrer);t.start();serveur.pret.wait(2)
        client=Client('regulateur',port=serveur.port);client.connecter()
        try:
            b=bilan()
            self.assertEqual(client.echanger({'type':'sauver_comparaison','bilan':b})['type'],'comparaison_sauvee')
            self.assertEqual(len(client.echanger({'type':'historique'})['lignes']),2)
            ancien=self.stockage.options.copy()
            self.stockage.options.update(unix_socket=None,host='127.0.0.1',port=1)
            self.assertEqual(client.echanger({'type':'historique'})['type'],'erreur_bdd')
            self.assertEqual(client.ping()['type'],'pong')
            self.stockage.options=ancien
            self.assertEqual(len(client.echanger({'type':'historique'})['lignes']),2)
        finally:
            client.fermer();serveur.arreter();t.join(3)

    def test_interface_comparaison_historique_et_reprise(self):
        """Vérifie la sauvegarde Qt, l'affichage de l'historique et la reprise de simulation."""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
        from src.interface.main import FenetrePrincipale
        from src.interface.comparaison import Comparaison
        from src.interface.historique import Historique
        from tests.test_integration import attendre
        app=QApplication.instance() or QApplication([])
        serveur=Serveur(port=0,stockage=self.stockage)
        t=threading.Thread(target=serveur.demarrer);t.start();serveur.pret.wait(2)
        f=FenetrePrincipale(45,2026);f.accidents_aleatoires.setChecked(False)
        f.port_serveur.setValue(serveur.port)
        observations=[]
        timer=QTimer()
        def fermer_dialogue():
            """Observe le dialogue terminé, capture son affichage et le ferme."""
            d=app.activeModalWidget()
            if isinstance(d,Comparaison) and d.bilan_sauve:
                observations.append(d.etat_bdd.text())
                d.grab().save('/tmp/comparaison-bdd.png')
                d.reject()
            elif isinstance(d,Historique) and not d.en_cours:
                observations.append(d.tableau.rowCount())
                d.grab().save('/tmp/historique-bdd.png')
                d.reject()
        timer.timeout.connect(fermer_dialogue);timer.start(30)
        # Évite un blocage de la recette si une réponse ne vient pas.
        secours=QTimer();secours.setSingleShot(True)
        secours.timeout.connect(lambda: app.activeModalWidget().reject() if app.activeModalWidget() else None)
        try:
            f.basculer_connexion();attendre(lambda:f.reseau_pret and f.temps_simule>.08)
            secours.start(15000);f.ouvrir_comparaison();secours.stop()
            self.assertEqual(len(observations),1)
            self.assertIn('enregistrée',observations[0])
            temps=f.temps_simule;attendre(lambda:f.temps_simule>temps+.08)
            secours.start(5000);f.ouvrir_historique();secours.stop()
            self.assertEqual(observations[1],2)
            self.assertEqual(len(self.stockage.historique()),2)
            temps=f.temps_simule;attendre(lambda:f.temps_simule>temps+.08)
        finally:
            timer.stop();secours.stop()
            if f.client_reseau:
                f.client_reseau.arreter();attendre(lambda:f.client_reseau is None)
            f.close();serveur.arreter();t.join(3)
