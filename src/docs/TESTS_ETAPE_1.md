# Recette de l’étape 1 — 12 novembre 2026

Base récupérée sur GitHub : `c67113d58554c5340d1b22431eef1239e9081d13`.

Environnement vérifié : Linux, Python 3.12.14, PyQt6 6.12.0, Qt offscreen.
Commande : `python -m unittest discover -s tests -v`.

Résultat : **12 tests réussis**. Les échanges réseau utilisent de vraies sockets
TCP sur 127.0.0.1, avec ports libres attribués par le système.

## Couverture

- Durées exactes du cycle : 10 s vert, 2 s orange, 1 s tout rouge.
- Priorité dans les quatre directions, occupation bloquant l’autre axe,
  vert maintenu jusqu’à sortie, retour au cycle normal.
- Piétons déjà engagés avant une ambulance ; données invalides refusées.
- Sans priorité : cycle identique au fonctionnement ordinaire.
- 900 étapes TCP identiques aux décisions du contrôleur local.
- 3 000 étapes de maquette sur TCP (120 s simulées) : véhicules, ambulance,
  piétons, commande appliquée au dessin et détection automatique de sortie.
- Mauvais rôle, révision périmée, duplication de rôle, perte du capteur.
- Fenêtre réelle Qt connectée au serveur, coupure, pause sans mouvement,
  reprise locale explicite, reconnexion et fermeture du thread.
- Serveur volontairement retardé : rouge et suspension après une seconde,
  réponse tardive ignorée.
- 12 scénarios (densités 0/45/100 %, quatre directions), 120 s chacun :
  espacement des véhicules, absence d’axes opposés simultanément dans le centre,
  traversées piétonnes au rouge et missions terminées.
- Accident devant l’ambulance, attente en file puis dégagement automatique.
- Comparaison rejouée deux fois à l’identique et export CSV relu.
- Capture de la fenêtre examinée : commandes, carrefour et journal visibles.

## Exemple reproductible

Densité 45 %, ambulance nord, graine 2026, 120 s simulées :

| Mesure | Sans priorité | Avec priorité |
| --- | ---: | ---: |
| Mission ambulance | 31,56 s | 10,16 s |
| Attente avant traversée piétonne | 4,64 s | 5,44 s |
| Attente cumulée automobile | 1 092,12 s | 1 141,52 s |
| Demandes d’arrivée | 252 | 252 |
| Véhicules admis | 115 | 118 |
| Arrivées refusées | 137 | 134 |

Dans ce scénario, l’ambulance gagne 21,40 s, avec davantage d’attente cumulée pour
les autres véhicules. Le résultat dépend du scénario ; il ne représente pas une
mesure sur route réelle.

## Ce qui reste à vérifier sur place

Les VM ne sont pas créées. Windows, le réseau de l’IUT, le pare-feu, l’adressage et
le redéploiement sur les machines finales n’ont pas été testés ici.
La fenêtre héberge trois clients TCP logiques ; cette livraison ne répartit pas
ces trois rôles dans trois processus indépendants sur trois VM clientes.
Le serveur peut déjà tourner sur une VM distincte de la fenêtre.
