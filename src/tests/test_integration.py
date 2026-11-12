"""Recette exécutable : contrôleur, vraie liaison TCP et fenêtre Qt."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import csv
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from src.controleur import Controleur, verifier_commande
from src.clients.client import Client
from src.serveur.serveur import Serveur
from src.interface.main import FenetrePrincipale
from src.interface.comparaison import Comparaison

APP = QApplication.instance() or QApplication([])


def mesure(**modifications):
    valeur = dict(occupe=False, ambulance=None, priorite=True,
                  pietons=False, demande_pietons=False)
    valeur.update(modifications)
    return valeur


def attendre(condition, secondes=5):
    limite = time.monotonic() + secondes
    while not condition() and time.monotonic() < limite:
        APP.processEvents()
        time.sleep(.002)
    if not condition():
        raise AssertionError('Condition non obtenue dans le délai')


class ControleurTests(unittest.TestCase):
    def test_durees_et_cycle(self):
        c = Controleur()
        for phase, tours in ((5,25),(0,250),(1,50),(2,25),(3,250),(4,50)):
            self.assertEqual(c.phase, phase)
            for _ in range(tours-1):
                c.avancer(mesure())
                self.assertEqual(c.phase,phase)
            c.avancer(mesure())
        self.assertEqual(c.phase,5)

    def test_priorite_quatre_directions_et_sortie(self):
        for direction in 'NSEO':
            c = Controleur()
            cible = 0 if direction in 'NS' else 3
            c.phase = 3 if cible == 0 else 0
            c.restant = 10
            for _ in range(75): c.avancer(mesure(ambulance=direction))
            self.assertIn(c.phase,(1,4))
            for _ in range(50): c.avancer(mesure(ambulance=direction))
            self.assertIn(c.phase,(2,5))
            for _ in range(100): c.avancer(mesure(ambulance=direction,occupe=True))
            self.assertIn(c.phase,(2,5))
            c.avancer(mesure(ambulance=direction))
            self.assertEqual(c.phase,cible)
            for _ in range(1000): c.avancer(mesure(ambulance=direction))
            self.assertEqual(c.phase,cible)
            for _ in range(75): c.avancer(mesure())
            self.assertIn(c.phase,(1,4))

    def test_pietons_avant_ambulance_deja_engages(self):
        c=Controleur()
        for _ in range(25): r=c.avancer(mesure(demande_pietons=True))
        self.assertTrue(r['traverser'])
        for _ in range(170):
            r=c.avancer(mesure(pietons=True,ambulance='E'))
            self.assertTrue(all(v=='rouge' for v in r['feux'].values()))
        for _ in range(25): c.avancer(mesure(ambulance='E'))
        self.assertEqual(c.phase,3)

    def test_sans_priorite_et_donnees_invalides(self):
        a,b=Controleur(),Controleur()
        for _ in range(800):
            self.assertEqual(a.avancer(mesure()),b.avancer(mesure(ambulance='E',priorite=False)))
        for cle in ('occupe','pietons','priorite','demande_pietons'):
            with self.assertRaises(ValueError): a.avancer(mesure(**{cle:1}))
        r=a.avancer(mesure()); r['feux']['E']='vert';r['feux']['N']='vert'
        with self.assertRaises(ValueError): verifier_commande(r)


class ReseauTests(unittest.TestCase):
    def setUp(self):
        self.serveur=Serveur(port=0)
        self.thread=threading.Thread(target=self.serveur.demarrer)
        self.thread.start()
        self.assertTrue(self.serveur.pret.wait(2))
        self.clients=[]

    def tearDown(self):
        for c in self.clients: c.fermer()
        self.serveur.arreter(); self.thread.join(3)
        self.assertFalse(self.thread.is_alive())

    def connecter(self,role):
        c=Client(role,port=self.serveur.port);c.connecter();self.clients.append(c);return c

    def session(self):
        r,c,f=[self.connecter(role) for role in ('regulateur','capteur','feux')]
        self.assertEqual(r.echanger({'type':'initialiser'})['type'],'initialise')
        return r,c,f

    def test_tcp_identique_controleur_local(self):
        r,c,f=self.session(); local=Controleur()
        for i in range(1,901):
            m=mesure(ambulance='E' if 100<i<550 else None,
                     occupe=200<i<280, pietons=650<i<800)
            self.assertEqual(c.echanger({'type':'mesure','revision':i,'mesure':m})['type'],'mesure_recue')
            self.assertEqual(r.echanger({'type':'calculer','revision':i})['type'],'calcul_termine')
            commande=f.echanger({'type':'commande','revision':i})
            attendu=local.avancer(m)
            self.assertEqual({k:commande[k] for k in attendu},attendu)
        self.assertTrue(r.obtenir_etat()['simulation_connectee'])

    def test_maquette_complete_sur_tcp(self):
        r,c,feux=self.session()
        fenetre=FenetrePrincipale(45,2026,True)
        fenetre.accidents_aleatoires.setChecked(False)
        fenetre.choix_direction.setCurrentIndex(fenetre.choix_direction.findData('E'))
        try:
            for revision in range(1,3001):
                if revision==301: fenetre.demander_ambulance()
                if revision==601: fenetre.demander_pietons()
                m=fenetre.relever_capteurs()
                self.assertEqual(c.echanger({'type':'mesure','revision':revision,'mesure':m})['type'],'mesure_recue')
                self.assertEqual(r.echanger({'type':'calculer','revision':revision})['type'],'calcul_termine')
                commande=feux.echanger({'type':'commande','revision':revision})
                fenetre.appliquer_commande(commande)
                if fenetre.pietons: self.assertIn(fenetre.phase,(2,5))
                axes={v['direction'] in 'NS' for v in fenetre.voitures if 310<v['distance']<490}
                self.assertLessEqual(len(axes),1)
            self.assertIsNotNone(fenetre.duree_mission)
            self.assertIsNotNone(fenetre.attente_pietons)
            self.assertIsNone(self.serveur.maquette.mesure['ambulance'])
        finally: fenetre.close()

    def test_revision_roles_doublons_et_capteur_perdu(self):
        r,c,f=self.session()
        self.assertEqual(r.echanger({'type':'mesure','revision':1,'mesure':mesure()})['type'],'erreur')
        self.assertEqual(c.echanger({'type':'mesure','revision':2,'mesure':mesure()})['type'],'erreur')
        self.assertEqual(c.echanger({'type':'mesure','revision':1,'mesure':mesure()})['type'],'mesure_recue')
        self.assertEqual(c.echanger({'type':'mesure','revision':1,'mesure':mesure()})['type'],'erreur')
        with self.assertRaises(ConnectionError): self.connecter('capteur')
        c.fermer()
        attendre(lambda: self.serveur.maquette is None)
        self.assertFalse(r.obtenir_etat()['simulation_connectee'])
        self.assertEqual(f.echanger({'type':'commande','revision':1})['type'],'erreur')

    def test_fenetre_connexion_panne_reconnexion_et_fermeture(self):
        f=FenetrePrincipale(densite=0)
        f.accidents_aleatoires.setChecked(False)
        f.port_serveur.setValue(self.serveur.port)
        try:
            f.basculer_connexion()
            attendre(lambda:f.temps_simule>.2 and f.reseau_pret)
            self.assertTrue(self.serveur.maquette is not None)
            f.demander_ambulance()
            attendre(lambda:self.serveur.maquette.mesure['ambulance']=='N')
            self.serveur.arreter()
            attendre(lambda:f.client_reseau is None)
            temps=f.temps_simule
            for _ in range(100): f.pas_animation()
            self.assertEqual(temps,f.temps_simule)
            self.assertEqual(f.phase,5)
            self.assertTrue(f.mode_reseau)
            f.reprendre_local();f.pas_animation()
            self.assertGreater(f.temps_simule,temps)
            # Nouvelle instance du serveur : même maquette, reprise sûre au rouge.
            self.thread.join(3)
            self.serveur=Serveur(port=0)
            self.thread=threading.Thread(target=self.serveur.demarrer)
            self.thread.start();self.serveur.pret.wait(2)
            f.port_serveur.setValue(self.serveur.port);f.basculer_connexion()
            attendre(lambda:f.reseau_pret and f.temps_simule>temps+.08)
            f.close()
            attendre(lambda:f.client_reseau is None)
        finally:
            if f.client_reseau:
                f.client_reseau.arreter();attendre(lambda:f.client_reseau is None)
            f.close()

    def test_serveur_mu_et_garde_fou_interface(self):
        f=FenetrePrincipale(densite=0)
        f.port_serveur.setValue(self.serveur.port)
        original=self.serveur.traiter_maquette
        bloquer=threading.Event(); liberer=threading.Event()
        def retard(role,message):
            if message['type']=='mesure' and bloquer.is_set(): liberer.wait(3)
            return original(role,message)
        self.serveur.traiter_maquette=retard
        try:
            f.basculer_connexion();attendre(lambda:f.reseau_pret and f.temps_simule>.08)
            bloquer.set()
            attendre(lambda:f.derniere_erreur_reseau is not None,3)
            self.assertEqual(f.phase,5)
            temps=f.temps_simule
            liberer.set();attendre(lambda:f.client_reseau is None)
            self.assertEqual(f.temps_simule,temps)
        finally:
            liberer.set()
            if f.client_reseau:
                f.client_reseau.arreter();attendre(lambda:f.client_reseau is None)
            f.close()


class SimulationTests(unittest.TestCase):
    def test_scenarios_densites_directions_et_securite(self):
        for densite in (0,45,100):
            for direction in 'NSEO':
                f=FenetrePrincipale(densite,2026,True)
                f.accidents_aleatoires.setChecked(False)
                f.choix_direction.setCurrentIndex(f.choix_direction.findData(direction))
                try:
                    for i in range(3000):
                        if i==300:f.demander_ambulance()
                        if i==600:f.demander_pietons()
                        f.pas_local()
                        if f.pietons:self.assertIn(f.phase,(2,5))
                        axes={v['direction'] in 'NS' for v in f.voitures if 310<v['distance']<490}
                        self.assertLessEqual(len(axes),1,'Axes opposés dans le centre')
                        for d in 'NSEO':
                            positions=sorted(v['distance'] for v in f.voitures if v['direction']==d)
                            self.assertTrue(all(b-a>=48-1e-7 for a,b in zip(positions,positions[1:])))
                    self.assertIsNotNone(f.duree_mission)
                    self.assertIsNotNone(f.attente_pietons)
                finally:f.close()

    def test_accident_ambulance_derriere_et_degagement(self):
        f=FenetrePrincipale(0,2026,True);f.accidents_aleatoires.setChecked(False)
        try:
            v=f.creer_voiture('N','#63b3ed');v['distance']=180
            f.provoquer_accident();f.demander_ambulance()
            for _ in range(100):f.pas_local()
            self.assertEqual(v['distance'],180)
            self.assertLessEqual(f.ambulance['distance'],132)
            for _ in range(1200):f.pas_local()
            self.assertIsNone(f.accident)
            self.assertIsNotNone(f.duree_mission)
        finally:f.close()

    def test_comparaison_reproductible_et_csv(self):
        resultats=[]
        for _ in range(2):
            d=Comparaison(None,45,'N',FenetrePrincipale);d.calcul.stop()
            while d.tour<d.nombre_tours:d.calculer_lot()
            d.calculer_lot()
            resultats.append(d.resultats)
            self.assertEqual(d.resultats[0]['demandes'],d.resultats[1]['demandes'])
            self.assertLess(d.resultats[1]['mission'],d.resultats[0]['mission'])
            with tempfile.TemporaryDirectory() as dossier:
                p=Path(dossier)/'bilan.csv';d.enregistrer_csv(p)
                with p.open(encoding='utf-8-sig',newline='') as fichier:
                    lignes=list(csv.reader(fichier,delimiter=';'))
                self.assertTrue(any('Ambulance' in ligne[0] for ligne in lignes if ligne))
            d.close()
        self.assertEqual(resultats[0],resultats[1])
        print('Comparaison vérifiée :',resultats[0])


if __name__=='__main__':unittest.main()
