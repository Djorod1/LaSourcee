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
    -- Code court saisi à la main. Un lien peut échouer, être coupé par
    -- la messagerie ou pointer vers une adresse de déploiement
    -- inaccessible ; six chiffres se recopient depuis n'importe quel
    -- écran.
    code            VARCHAR(10)  NULL,
    tentatives      TINYINT UNSIGNED NOT NULL DEFAULT 0,
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

-- ----- 5. Préférences de notification -----
--
-- Le panneau de notifications affichait huit interrupteurs codés en
-- dur : chacun confirmait l'enregistrement sans rien conserver, et tout
-- revenait à l'état initial au rechargement.
--
-- Les préférences sont toujours lues et écrites d'un bloc, jamais
-- interrogées une par une : une colonne JSON suffit, une table dédiée
-- imposerait une jointure sans rien résoudre.

ALTER TABLE utilisateur ADD COLUMN preferences_notif TEXT NULL;

-- ----- 6. Informations de profil complémentaires -----
--
-- Quatre champs, choisis pour ce qu'ils changent à la qualité d'une
-- mise en relation, et non pour remplir un formulaire :
--
--   situation   : « en licence 3 » situe une question bien mieux que
--                 l'intitulé d'un diplôme.
--   objectif    : ce que la personne cherche, ou ce qu'un référent
--                 propose. C'est ce qui permet d'apparier les deux.
--   langues     : une plateforme ouverte au-delà d'un pays ne peut pas
--                 supposer que tout le monde échange en français.
--   profil_pro  : une adresse professionnelle publique appuie la
--                 crédibilité d'un référent sans rien exiger de secret.

ALTER TABLE utilisateur ADD COLUMN situation  VARCHAR(40)  NULL;
ALTER TABLE utilisateur ADD COLUMN objectif   VARCHAR(60)  NULL;
ALTER TABLE utilisateur ADD COLUMN langues    VARCHAR(120) NULL;
ALTER TABLE utilisateur ADD COLUMN profil_pro VARCHAR(255) NULL;


-- ----- 7. Le parcours, en trois champs plutôt qu'un -----
--
-- « Niveau d'études / Profession » était un seul champ libre. On y
-- lisait aussi bien « Master 2 » que « mécanicien depuis 8 ans » ou
-- « bac G2 Cotonou » : trois informations différentes mêlées dans une
-- phrase, impossibles à filtrer et impossibles à comparer.
--
--   niveau_etudes : le diplôme le plus élevé obtenu. La liste va de
--                   « sans diplôme » au doctorat et place le CAP, le
--                   CQP et le CQM au milieu du parcours, là où ils
--                   sont. Un soudeur n'a pas à se ranger dans « autre ».
--   domaine       : la filière ou le métier. Les filières universitaires
--                   et les métiers manuels figurent dans la même liste,
--                   sans hiérarchie.
--   etablissement : université, école, centre de formation ou atelier.
--                   Reste un champ libre, avec des suggestions : aucune
--                   liste fermée ne contiendrait l'atelier où quelqu'un
--                   apprend son métier auprès d'un maître artisan.

ALTER TABLE utilisateur ADD COLUMN niveau_etudes VARCHAR(60)  NULL;
ALTER TABLE utilisateur ADD COLUMN domaine       VARCHAR(60)  NULL;
ALTER TABLE utilisateur ADD COLUMN etablissement VARCHAR(120) NULL;
