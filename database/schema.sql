-- =====================================================================
-- LaSourcee — Schéma de base de données
-- SGBD cible : MySQL 8 (compatible MariaDB 10.5+)
-- Encodage : utf8mb4 / utf8mb4_unicode_ci
-- =====================================================================

DROP DATABASE IF EXISTS lasource;
CREATE DATABASE lasource
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;
USE lasource;

-- ---------------------------------------------------------------------
-- Référentiels : secteurs d'expertise et pays
-- ---------------------------------------------------------------------

CREATE TABLE secteur (
    id_secteur   SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    libelle      VARCHAR(80)  NOT NULL,
    couleur      VARCHAR(20)  NULL,
    PRIMARY KEY (id_secteur),
    UNIQUE KEY uq_secteur_libelle (libelle)
) ENGINE=InnoDB;

CREATE TABLE pays (
    id_pays      SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    libelle      VARCHAR(80)  NOT NULL,
    code_iso     CHAR(2)      NULL,
    PRIMARY KEY (id_pays),
    UNIQUE KEY uq_pays_libelle (libelle)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Utilisateurs (étudiants et mentors partagent la même table)
-- ---------------------------------------------------------------------

CREATE TABLE utilisateur (
    id_utilisateur   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    prenom           VARCHAR(60)  NOT NULL,
    nom              VARCHAR(60)  NOT NULL,
    email            VARCHAR(120) NOT NULL,
    telephone        VARCHAR(20)  NULL,
    mot_de_passe     VARCHAR(255) NOT NULL,           -- hash bcrypt
    role             ENUM('etudiant','mentor') NOT NULL DEFAULT 'etudiant',
    photo_url        TEXT         NULL,               -- chemin ou dataURL
    bio              VARCHAR(500) NULL,
    etudes           VARCHAR(150) NULL,               -- "Master 2 — Sciences Po Paris"
    id_pays          SMALLINT UNSIGNED NULL,
    ville            VARCHAR(80)  NULL,
    est_admin        BOOLEAN      NOT NULL DEFAULT FALSE,
    est_actif        BOOLEAN      NOT NULL DEFAULT TRUE,
    email_verifie    BOOLEAN      NOT NULL DEFAULT FALSE,
    -- Mot de passe temporaire : impose le changement à la 1re connexion
    doit_changer_mdp BOOLEAN      NOT NULL DEFAULT FALSE,
    preferences_notif TEXT        NULL,
    situation        VARCHAR(40)  NULL,
    objectif         VARCHAR(60)  NULL,
    langues          VARCHAR(120) NULL,
    profil_pro       VARCHAR(255) NULL,
    cree_le          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    maj_le           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    derniere_co      DATETIME     NULL,
    PRIMARY KEY (id_utilisateur),
    UNIQUE KEY uq_utilisateur_email (email),
    KEY idx_utilisateur_role (role),
    KEY idx_utilisateur_pays (id_pays),
    CONSTRAINT fk_utilisateur_pays
        FOREIGN KEY (id_pays) REFERENCES pays(id_pays)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- Secteurs d'intérêt (étudiants) ou d'expertise (mentors)
CREATE TABLE utilisateur_secteur (
    id_utilisateur   INT UNSIGNED      NOT NULL,
    id_secteur       SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (id_utilisateur, id_secteur),
    CONSTRAINT fk_us_user FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    CONSTRAINT fk_us_sect FOREIGN KEY (id_secteur)
        REFERENCES secteur(id_secteur) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Détails propres aux mentors (relation 1-à-1 conditionnelle)
CREATE TABLE mentor_details (
    id_utilisateur   INT UNSIGNED NOT NULL,
    est_verifie      BOOLEAN      NOT NULL DEFAULT FALSE,
    dispo            ENUM('disponible','occupe','absent') NOT NULL
                       DEFAULT 'disponible',
    anciennete       VARCHAR(40)  NULL,               -- "3 ans" (libre)
    delai_reponse    VARCHAR(40)  NULL,               -- "sous 24 h"
    note_moyenne     DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    nb_reponses      INT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id_utilisateur),
    CONSTRAINT fk_md_user FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Parcours mentor (diplômes et postes)
CREATE TABLE experience (
    id_experience    INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_utilisateur   INT UNSIGNED NOT NULL,
    type_experience  ENUM('poste','diplome','autre') NOT NULL DEFAULT 'poste',
    intitule         VARCHAR(150) NOT NULL,           -- "Directrice — Goldman Sachs"
    periode          VARCHAR(60)  NULL,               -- "2010-2022"
    ordre            TINYINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id_experience),
    KEY idx_exp_user (id_utilisateur),
    CONSTRAINT fk_exp_user FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Questions (publications) et réponses (commentaires imbriqués)
-- ---------------------------------------------------------------------

CREATE TABLE question (
    id_question      INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_auteur        INT UNSIGNED NOT NULL,
    titre            VARCHAR(200) NOT NULL,
    corps            TEXT         NOT NULL,
    id_secteur       SMALLINT UNSIGNED NULL,
    statut           ENUM('ouverte','resolue','fermee') NOT NULL
                       DEFAULT 'ouverte',
    publiee_le       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    maj_le           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id_question),
    KEY idx_question_auteur  (id_auteur),
    KEY idx_question_secteur (id_secteur, publiee_le),
    KEY idx_question_recente (publiee_le),
    CONSTRAINT fk_question_auteur  FOREIGN KEY (id_auteur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    CONSTRAINT fk_question_secteur FOREIGN KEY (id_secteur)
        REFERENCES secteur(id_secteur) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Réponses arborescentes (sous-réponses via id_parent_reponse)
CREATE TABLE reponse (
    id_reponse        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_question       INT UNSIGNED NOT NULL,
    id_auteur         INT UNSIGNED NOT NULL,
    id_parent_reponse INT UNSIGNED NULL,
    contenu           TEXT         NOT NULL,
    note_etoiles      TINYINT UNSIGNED NULL,           -- 1..5 si notée
    cree_le           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_reponse),
    KEY idx_reponse_question (id_question, cree_le),
    KEY idx_reponse_auteur   (id_auteur),
    KEY idx_reponse_parent   (id_parent_reponse),
    CONSTRAINT fk_reponse_question FOREIGN KEY (id_question)
        REFERENCES question(id_question) ON DELETE CASCADE,
    CONSTRAINT fk_reponse_auteur   FOREIGN KEY (id_auteur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    CONSTRAINT fk_reponse_parent   FOREIGN KEY (id_parent_reponse)
        REFERENCES reponse(id_reponse) ON DELETE CASCADE,
    CONSTRAINT ck_reponse_etoiles  CHECK (note_etoiles IS NULL
                                          OR note_etoiles BETWEEN 1 AND 5)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Interactions : marquages utiles, sauvegardes, suivis, signalements
-- ---------------------------------------------------------------------

CREATE TABLE marquage_question (
    id_question      INT UNSIGNED NOT NULL,
    id_utilisateur   INT UNSIGNED NOT NULL,
    type_marquage    ENUM('utile','aime') NOT NULL DEFAULT 'utile',
    cree_le          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_question, id_utilisateur, type_marquage),
    CONSTRAINT fk_mq_question FOREIGN KEY (id_question)
        REFERENCES question(id_question) ON DELETE CASCADE,
    CONSTRAINT fk_mq_user     FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE marquage_reponse (
    id_reponse       INT UNSIGNED NOT NULL,
    id_utilisateur   INT UNSIGNED NOT NULL,
    type_marquage    ENUM('utile','aime') NOT NULL DEFAULT 'utile',
    cree_le          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_reponse, id_utilisateur, type_marquage),
    CONSTRAINT fk_mr_reponse FOREIGN KEY (id_reponse)
        REFERENCES reponse(id_reponse) ON DELETE CASCADE,
    CONSTRAINT fk_mr_user    FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE sauvegarde (
    id_utilisateur   INT UNSIGNED NOT NULL,
    id_question      INT UNSIGNED NOT NULL,
    cree_le          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_utilisateur, id_question),
    CONSTRAINT fk_sv_user     FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    CONSTRAINT fk_sv_question FOREIGN KEY (id_question)
        REFERENCES question(id_question) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE suivi_mentor (
    id_suiveur       INT UNSIGNED NOT NULL,
    id_mentor        INT UNSIGNED NOT NULL,
    cree_le          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_suiveur, id_mentor),
    CONSTRAINT fk_suivi_suiveur FOREIGN KEY (id_suiveur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    CONSTRAINT fk_suivi_mentor  FOREIGN KEY (id_mentor)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    CONSTRAINT ck_suivi_pair    CHECK (id_suiveur <> id_mentor)
) ENGINE=InnoDB;

CREATE TABLE signalement (
    id_signalement   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_signaleur     INT UNSIGNED NOT NULL,
    type_contenu     ENUM('question','reponse','utilisateur') NOT NULL,
    id_contenu       INT UNSIGNED NOT NULL,
    motif            VARCHAR(300) NOT NULL,
    statut           ENUM('ouvert','traite','rejete') NOT NULL DEFAULT 'ouvert',
    cree_le          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_signalement),
    KEY idx_signalement_statut (statut),
    CONSTRAINT fk_signal_user FOREIGN KEY (id_signaleur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Messagerie privée
-- ---------------------------------------------------------------------

CREATE TABLE conversation (
    id_conversation  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    cree_le          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dernier_msg_le   DATETIME NULL,
    PRIMARY KEY (id_conversation),
    KEY idx_conv_dernier (dernier_msg_le)
) ENGINE=InnoDB;

CREATE TABLE conversation_participant (
    id_conversation  INT UNSIGNED NOT NULL,
    id_utilisateur   INT UNSIGNED NOT NULL,
    rejoint_le       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lu_jusqua        DATETIME NULL,
    PRIMARY KEY (id_conversation, id_utilisateur),
    CONSTRAINT fk_cp_conv FOREIGN KEY (id_conversation)
        REFERENCES conversation(id_conversation) ON DELETE CASCADE,
    CONSTRAINT fk_cp_user FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE message (
    id_message       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_conversation  INT UNSIGNED NOT NULL,
    id_expediteur    INT UNSIGNED NOT NULL,
    contenu          TEXT NOT NULL,
    envoye_le        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_message),
    KEY idx_msg_conv (id_conversation, envoye_le),
    CONSTRAINT fk_msg_conv FOREIGN KEY (id_conversation)
        REFERENCES conversation(id_conversation) ON DELETE CASCADE,
    CONSTRAINT fk_msg_user FOREIGN KEY (id_expediteur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Notifications
-- ---------------------------------------------------------------------

CREATE TABLE notification (
    id_notification  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_destinataire  INT UNSIGNED NOT NULL,
    texte            VARCHAR(300) NOT NULL,
    lien_question    INT UNSIGNED NULL,
    type_notif       ENUM('reponse','reaction','suivi','message',
                          'nouvelle_question','systeme') NOT NULL DEFAULT 'systeme',
    est_lue          BOOLEAN NOT NULL DEFAULT FALSE,
    cree_le          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_notification),
    KEY idx_notif_destinataire (id_destinataire, est_lue, cree_le),
    CONSTRAINT fk_notif_user FOREIGN KEY (id_destinataire)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    CONSTRAINT fk_notif_question FOREIGN KEY (lien_question)
        REFERENCES question(id_question) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Sessions Web (jetons d'authentification persistants côté serveur)
-- ---------------------------------------------------------------------

CREATE TABLE session_web (
    id_token         CHAR(64) NOT NULL,
    id_utilisateur   INT UNSIGNED NOT NULL,
    cree_le          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expire_le        DATETIME NOT NULL,
    user_agent       VARCHAR(255) NULL,
    PRIMARY KEY (id_token),
    KEY idx_sw_user (id_utilisateur),
    CONSTRAINT fk_sw_user FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =====================================================================
-- Données de référence
-- =====================================================================

INSERT INTO secteur (libelle, couleur) VALUES
    ('Technologie',     '#2563EB'),
    ('Médecine',        '#16A34A'),
    ('Droit',           '#7C3AED'),
    ('Finance',         '#F59E0B'),
    ('Arts',            '#EC4899'),
    ('Éducation',       '#0EA5E9'),
    ('Ingénierie',      '#0891B2'),
    ('Entrepreneuriat', '#DC2626'),
    ('Sciences',        '#10B981'),
    ('Communication',   '#8B5CF6'),
    ('Agriculture',     '#65A30D'),
    ('Autre',           '#6B7280');

INSERT INTO pays (libelle, code_iso) VALUES
    ('France',    'FR'),
    ('Belgique',  'BE'),
    ('Suisse',    'CH'),
    ('Canada',    'CA'),
    ('Sénégal',   'SN'),
    ('Maroc',     'MA'),
    ('Côte d''Ivoire', 'CI'),
    ('Bénin',     'BJ'),
    ('Cameroun',  'CM'),
    ('Algérie',   'DZ'),
    ('Tunisie',   'TN'),
    ('Mali',      'ML'),
    ('Burkina Faso', 'BF'),
    ('Togo',      'TG'),
    ('Niger',     'NE'),
    ('Madagascar','MG'),
    ('Autre',     NULL);

-- =====================================================================
-- Vues utiles (SQL côté serveur, montre la maîtrise de l'algèbre rel.)
-- =====================================================================

-- Statistiques de chaque question : nombre de réponses + nombre d'utiles
CREATE OR REPLACE VIEW v_question_stats AS
SELECT q.id_question,
       q.id_auteur,
       q.titre,
       q.id_secteur,
       q.publiee_le,
       (SELECT COUNT(*) FROM reponse r
          WHERE r.id_question = q.id_question)         AS nb_reponses,
       (SELECT COUNT(*) FROM marquage_question m
          WHERE m.id_question = q.id_question
            AND m.type_marquage = 'utile')             AS nb_utiles
  FROM question q;

-- Carte mentor : agrégat note moyenne (à partir des étoiles des réponses)
-- et nombre de réponses publiées.
CREATE OR REPLACE VIEW v_mentor_carte AS
SELECT u.id_utilisateur,
       u.prenom, u.nom, u.photo_url, u.bio, u.ville,
       p.libelle               AS pays,
       md.est_verifie,
       md.dispo,
       md.anciennete,
       COALESCE(md.note_moyenne, 0)          AS note_moyenne,
       (SELECT COUNT(*) FROM reponse r
         WHERE r.id_auteur = u.id_utilisateur) AS nb_reponses
  FROM utilisateur u
  JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
  LEFT JOIN pays p ON p.id_pays = u.id_pays
 WHERE u.role = 'mentor'
   AND u.est_actif = TRUE;

-- ----- Tentatives d'authentification (anti-force-brute) -----

CREATE TABLE IF NOT EXISTS tentative_auth (
    id_tentative INT UNSIGNED NOT NULL AUTO_INCREMENT,
    cle          VARCHAR(255) NOT NULL,
    horodatage   BIGINT       NOT NULL,
    PRIMARY KEY (id_tentative),
    KEY idx_tentative_cle (cle, horodatage)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
