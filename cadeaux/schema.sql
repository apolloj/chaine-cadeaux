-- Schéma de la base de la chaîne de cadeaux (MySQL 8).
-- Chargé par « python -m cadeaux init » ; peut être rejoué sans risque.

CREATE TABLE IF NOT EXISTS personnes (
    id       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nom      VARCHAR(100) NOT NULL,
    -- Année à partir de laquelle la personne ne participe plus aux tirages (NULL = active).
    archive_depuis  SMALLINT UNSIGNED NULL,
    cree_le  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- La collation ignore accents et majuscules : « Elise » et « élise » sont la même personne.
    UNIQUE KEY uq_personnes_nom (nom)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

-- Paires qui ne se tirent jamais (couples, foyers), stockées une fois avec personne_a < personne_b.
CREATE TABLE IF NOT EXISTS exclusions (
    personne_a  INT UNSIGNED NOT NULL,
    personne_b  INT UNSIGNED NOT NULL,
    motif       VARCHAR(255) NULL,
    PRIMARY KEY (personne_a, personne_b),
    CONSTRAINT fk_exclusions_a FOREIGN KEY (personne_a) REFERENCES personnes (id) ON DELETE CASCADE,
    CONSTRAINT fk_exclusions_b FOREIGN KEY (personne_b) REFERENCES personnes (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

-- Un tirage par année.
CREATE TABLE IF NOT EXISTS tirages (
    annee       SMALLINT UNSIGNED PRIMARY KEY,
    note        VARCHAR(255) NULL,
    cree_le     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modifie_le  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

-- Qui offre à qui : chacun donne un seul cadeau et en reçoit un seul par année.
CREATE TABLE IF NOT EXISTS attributions (
    annee        SMALLINT UNSIGNED NOT NULL,
    donneur_id   INT UNSIGNED NOT NULL,
    receveur_id  INT UNSIGNED NOT NULL,
    PRIMARY KEY (annee, donneur_id),
    UNIQUE KEY uq_attributions_receveur (annee, receveur_id),
    CONSTRAINT ck_attributions_pas_soi_meme CHECK (donneur_id <> receveur_id),
    CONSTRAINT fk_attributions_tirage FOREIGN KEY (annee) REFERENCES tirages (annee) ON DELETE CASCADE,
    CONSTRAINT fk_attributions_donneur FOREIGN KEY (donneur_id) REFERENCES personnes (id),
    CONSTRAINT fk_attributions_receveur FOREIGN KEY (receveur_id) REFERENCES personnes (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

-- Vue lisible des tirages, pratique aussi dans MySQL Workbench.
CREATE OR REPLACE VIEW vue_attributions AS
SELECT a.annee, d.nom AS donneur, r.nom AS receveur
FROM attributions a
JOIN personnes d ON d.id = a.donneur_id
JOIN personnes r ON r.id = a.receveur_id;
