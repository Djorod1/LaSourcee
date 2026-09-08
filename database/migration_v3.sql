-- =====================================================================
-- LaSourcee — Migration v3 (MySQL)
--
-- À exécuter UNE FOIS après schema.sql et migration_v2.sql.
-- Aligne le schéma MySQL sur ceux de SQLite et PostgreSQL :
--   - vérification d'adresse e-mail à l'inscription ;
--   - connexion Google et LinkedIn ;
--   - mot de passe temporaire des comptes administrateurs.
--
-- Sans cette migration, les requêtes de routes/auth.py et routes/oauth.py
-- échouent sur MySQL : les colonnes et tables n'existent pas.
--
-- Les installations neuves n'ont rien à faire : schema.sql contient déjà
-- les deux colonnes ajoutées ci-dessous.
-- =====================================================================

USE lasource;

-- ----- 1. Colonnes ajoutées à la table utilisateur -----
--
-- MySQL 8.0 ne connaît pas « ADD COLUMN IF NOT EXISTS » : sur une base
-- créée avec le schema.sql à jour, ces deux instructions signalent une
-- colonne déjà présente. L'erreur est sans conséquence, passez à la
-- suite.

ALTER TABLE utilisateur
  ADD COLUMN email_verifie BOOLEAN NOT NULL DEFAULT FALSE AFTER est_actif;

ALTER TABLE utilisateur
  ADD COLUMN doit_changer_mdp BOOLEAN NOT NULL DEFAULT FALSE AFTER email_verifie;

-- ----- 2. Jetons de vérification d'adresse e-mail -----

CREATE TABLE IF NOT EXISTS verification_email (
    id_jeton        CHAR(64)     NOT NULL,
    id_utilisateur  INT UNSIGNED NOT NULL,
    cree_le         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expire_le       DATETIME     NOT NULL,
    verifie_le      DATETIME     NULL,
    PRIMARY KEY (id_jeton),
    KEY idx_verif_user (id_utilisateur),
    CONSTRAINT fk_verif_user FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----- 3. Identités externes (OAuth Google / LinkedIn) -----
--
-- La contrainte d'unicité sur (fournisseur, identifiant) est ce qui
-- empêche deux comptes de revendiquer la même identité Google.

CREATE TABLE IF NOT EXISTS identite_externe (
    id_externe      INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_utilisateur  INT UNSIGNED NOT NULL,
    fournisseur     ENUM('google','linkedin') NOT NULL,
    identifiant     VARCHAR(255) NOT NULL,   -- « sub » Google ou id LinkedIn
    email_verifie   BOOLEAN      NOT NULL DEFAULT FALSE,
    cree_le         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_externe),
    UNIQUE KEY uq_externe (fournisseur, identifiant),
    KEY idx_externe_user (id_utilisateur),
    CONSTRAINT fk_externe_user FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----- 4. Tentatives d'authentification (anti-force-brute) -----
--
-- Le compteur de tentatives vivait en mémoire vive. Sur un hébergement
-- sans état, chaque requête peut être traitée par une instance
-- différente : le compteur ne s'incrémentait jamais et la protection
-- était purement décorative. Il est désormais persisté.
--
-- L'horodatage est un entier epoch : la comparaison de fenêtre devient
-- identique sur les trois moteurs, sans arithmétique de dates.

CREATE TABLE IF NOT EXISTS tentative_auth (
    id_tentative INT UNSIGNED NOT NULL AUTO_INCREMENT,
    cle          VARCHAR(255) NOT NULL,   -- « action|identifiant|adresse IP »
    horodatage   BIGINT       NOT NULL,
    PRIMARY KEY (id_tentative),
    KEY idx_tentative_cle (cle, horodatage)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
