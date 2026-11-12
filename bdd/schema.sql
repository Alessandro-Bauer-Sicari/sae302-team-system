-- MariaDB : deux résultats (sans/avec priorité) par comparaison.
-- Réexécutable : aucune table existante n'est effacée.
CREATE DATABASE IF NOT EXISTS team_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE team_system;

CREATE TABLE IF NOT EXISTS comparaison (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    identifiant CHAR(36) NOT NULL UNIQUE,
    empreinte CHAR(64) NOT NULL,
    cree_le DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    densite TINYINT UNSIGNED NOT NULL CHECK (densite <= 100),
    direction ENUM('N','S','E','O') NOT NULL,
    graine BIGINT UNSIGNED NOT NULL,
    duree_s SMALLINT UNSIGNED NOT NULL,
    version_modele VARCHAR(40) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS resultat (
    comparaison_id BIGINT UNSIGNED NOT NULL,
    priorite BOOLEAN NOT NULL CHECK (priorite IN (0,1)),
    mission_s DOUBLE NULL CHECK (mission_s IS NULL OR mission_s >= 0),
    attente_s DOUBLE NOT NULL CHECK (attente_s >= 0),
    moyenne_s DOUBLE NOT NULL CHECK (moyenne_s >= 0),
    pietons_s DOUBLE NULL CHECK (pietons_s IS NULL OR pietons_s >= 0),
    demandes INT UNSIGNED NOT NULL,
    entrees INT UNSIGNED NOT NULL,
    sorties INT UNSIGNED NOT NULL,
    refusees INT UNSIGNED NOT NULL,
    PRIMARY KEY (comparaison_id, priorite),
    FOREIGN KEY (comparaison_id) REFERENCES comparaison(id),
    CHECK (demandes = entrees + refusees),
    CHECK (sorties <= entrees)
) ENGINE=InnoDB;
