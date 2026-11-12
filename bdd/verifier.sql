USE team_system;
SHOW TABLES;
SELECT c.id,c.cree_le,c.densite,c.direction,r.priorite,r.mission_s,r.attente_s,r.pietons_s
FROM comparaison c JOIN resultat r ON r.comparaison_id=c.id
ORDER BY c.id DESC,r.priorite LIMIT 20;
