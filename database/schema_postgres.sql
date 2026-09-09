-- =====================================================================
-- LaSourcee — Schéma PostgreSQL
-- Compatible Vercel Postgres, Neon, Supabase, Render et tout PostgreSQL 12+.
--
-- Chargement :   psql "$DATABASE_URL" -f database/schema_postgres.sql
-- (le serveur le charge aussi automatiquement au premier démarrage
--  si les tables sont absentes)
--
-- Aucun compte de démonstration : seuls les référentiels (secteurs et
-- pays) sont insérés. Les comptes administrateurs se créent ensuite
-- avec :  python backend/gerer_admins.py creer
-- =====================================================================

-- ----- Référentiels -----

CREATE TABLE secteur (
    id_secteur  SERIAL PRIMARY KEY,
    libelle     TEXT    NOT NULL UNIQUE,
    couleur     TEXT
);

CREATE TABLE pays (
    id_pays     SERIAL PRIMARY KEY,
    libelle     TEXT    NOT NULL UNIQUE,
    code_iso    TEXT
);

-- ----- Utilisateurs -----

CREATE TABLE utilisateur (
    id_utilisateur  SERIAL PRIMARY KEY,
    prenom          TEXT    NOT NULL,
    nom             TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    telephone       TEXT,
    mot_de_passe    TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'etudiant'
                    CHECK (role IN ('visiteur','etudiant','mentor','admin','super_admin')),
    photo_url       TEXT,
    bio             TEXT,
    etudes          TEXT,
    id_pays         INTEGER,
    ville           TEXT,
    est_admin       SMALLINT NOT NULL DEFAULT 0,
    est_actif       SMALLINT NOT NULL DEFAULT 1,
    email_verifie   SMALLINT NOT NULL DEFAULT 0,
    -- Mot de passe temporaire : impose le changement à la 1re connexion
    doit_changer_mdp SMALLINT NOT NULL DEFAULT 0,
    -- Préférences de notification, en JSON. NULL = valeurs par défaut.
    preferences_notif TEXT,
    cree_le         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    maj_le          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    derniere_co     TIMESTAMP,
    FOREIGN KEY (id_pays) REFERENCES pays(id_pays) ON DELETE SET NULL
);

CREATE INDEX idx_utilisateur_role ON utilisateur(role);
CREATE INDEX idx_utilisateur_pays ON utilisateur(id_pays);

CREATE TABLE utilisateur_secteur (
    id_utilisateur  INTEGER NOT NULL,
    id_secteur      INTEGER NOT NULL,
    PRIMARY KEY (id_utilisateur, id_secteur),
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    FOREIGN KEY (id_secteur)     REFERENCES secteur(id_secteur)         ON DELETE CASCADE
);

CREATE TABLE mentor_details (
    id_utilisateur  INTEGER PRIMARY KEY,
    est_verifie     SMALLINT NOT NULL DEFAULT 0,
    dispo           TEXT    NOT NULL DEFAULT 'disponible'
                    CHECK (dispo IN ('disponible','occupe','absent')),
    anciennete      TEXT,
    delai_reponse   TEXT,
    note_moyenne    NUMERIC(4,2)    NOT NULL DEFAULT 0.0,
    nb_reponses     SMALLINT NOT NULL DEFAULT 0,
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
);

CREATE TABLE experience (
    id_experience    SERIAL PRIMARY KEY,
    id_utilisateur   INTEGER NOT NULL,
    type_experience  TEXT    NOT NULL DEFAULT 'poste'
                     CHECK (type_experience IN ('poste','diplome','autre')),
    intitule         TEXT    NOT NULL,
    periode          TEXT,
    ordre            SMALLINT NOT NULL DEFAULT 0,
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
);
CREATE INDEX idx_exp_user ON experience(id_utilisateur);

-- ----- Questions et réponses -----

CREATE TABLE question (
    id_question  SERIAL PRIMARY KEY,
    id_auteur    INTEGER NOT NULL,
    titre        TEXT    NOT NULL,
    corps        TEXT    NOT NULL,
    id_secteur   INTEGER,
    statut       TEXT    NOT NULL DEFAULT 'ouverte'
                 CHECK (statut IN ('ouverte','resolue','fermee')),
    publiee_le   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    maj_le       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_auteur)  REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    FOREIGN KEY (id_secteur) REFERENCES secteur(id_secteur)         ON DELETE SET NULL
);
CREATE INDEX idx_question_auteur  ON question(id_auteur);
CREATE INDEX idx_question_secteur ON question(id_secteur, publiee_le);
CREATE INDEX idx_question_recente ON question(publiee_le);

CREATE TABLE reponse (
    id_reponse         SERIAL PRIMARY KEY,
    id_question        INTEGER NOT NULL,
    id_auteur          INTEGER NOT NULL,
    id_parent_reponse  INTEGER,
    contenu            TEXT    NOT NULL,
    note_etoiles       INTEGER CHECK (note_etoiles IS NULL OR (note_etoiles BETWEEN 1 AND 5)),
    cree_le            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_question)       REFERENCES question(id_question)    ON DELETE CASCADE,
    FOREIGN KEY (id_auteur)         REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    FOREIGN KEY (id_parent_reponse) REFERENCES reponse(id_reponse)      ON DELETE CASCADE
);
CREATE INDEX idx_reponse_question ON reponse(id_question, cree_le);
CREATE INDEX idx_reponse_auteur   ON reponse(id_auteur);
CREATE INDEX idx_reponse_parent   ON reponse(id_parent_reponse);

-- ----- Interactions -----

CREATE TABLE marquage_question (
    id_question     INTEGER NOT NULL,
    id_utilisateur  INTEGER NOT NULL,
    type_marquage   TEXT    NOT NULL DEFAULT 'utile'
                    CHECK (type_marquage IN ('utile','aime')),
    cree_le         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_question, id_utilisateur, type_marquage),
    FOREIGN KEY (id_question)    REFERENCES question(id_question)    ON DELETE CASCADE,
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
);

CREATE TABLE marquage_reponse (
    id_reponse      INTEGER NOT NULL,
    id_utilisateur  INTEGER NOT NULL,
    type_marquage   TEXT    NOT NULL DEFAULT 'utile'
                    CHECK (type_marquage IN ('utile','aime')),
    cree_le         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_reponse, id_utilisateur, type_marquage),
    FOREIGN KEY (id_reponse)     REFERENCES reponse(id_reponse)      ON DELETE CASCADE,
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
);

CREATE TABLE sauvegarde (
    id_utilisateur  INTEGER NOT NULL,
    id_question     INTEGER NOT NULL,
    cree_le         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_utilisateur, id_question),
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    FOREIGN KEY (id_question)    REFERENCES question(id_question)       ON DELETE CASCADE
);

CREATE TABLE suivi_mentor (
    id_suiveur  INTEGER NOT NULL,
    id_mentor   INTEGER NOT NULL,
    cree_le     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_suiveur, id_mentor),
    CHECK (id_suiveur <> id_mentor),
    FOREIGN KEY (id_suiveur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    FOREIGN KEY (id_mentor)  REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
);

CREATE TABLE signalement (
    id_signalement  SERIAL PRIMARY KEY,
    id_signaleur    INTEGER NOT NULL,
    type_contenu    TEXT    NOT NULL
                    CHECK (type_contenu IN ('question','reponse','utilisateur')),
    id_contenu      INTEGER NOT NULL,
    motif           TEXT    NOT NULL,
    statut          TEXT    NOT NULL DEFAULT 'ouvert'
                    CHECK (statut IN ('ouvert','traite','rejete')),
    cree_le         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_signaleur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
);
CREATE INDEX idx_signalement_statut ON signalement(statut);

-- ----- Messagerie -----

CREATE TABLE conversation (
    id_conversation SERIAL PRIMARY KEY,
    cree_le         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dernier_msg_le  TIMESTAMP
);
CREATE INDEX idx_conv_dernier ON conversation(dernier_msg_le);

CREATE TABLE conversation_participant (
    id_conversation INTEGER NOT NULL,
    id_utilisateur  INTEGER NOT NULL,
    rejoint_le      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lu_jusqua       TIMESTAMP,
    PRIMARY KEY (id_conversation, id_utilisateur),
    FOREIGN KEY (id_conversation) REFERENCES conversation(id_conversation) ON DELETE CASCADE,
    FOREIGN KEY (id_utilisateur)  REFERENCES utilisateur(id_utilisateur)   ON DELETE CASCADE
);

CREATE TABLE message (
    id_message       SERIAL PRIMARY KEY,
    id_conversation  INTEGER NOT NULL,
    id_expediteur    INTEGER NOT NULL,
    contenu          TEXT    NOT NULL,
    envoye_le        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_conversation) REFERENCES conversation(id_conversation) ON DELETE CASCADE,
    FOREIGN KEY (id_expediteur)   REFERENCES utilisateur(id_utilisateur)   ON DELETE CASCADE
);
CREATE INDEX idx_msg_conv ON message(id_conversation, envoye_le);

-- ----- Notifications -----

CREATE TABLE notification (
    id_notification  SERIAL PRIMARY KEY,
    id_destinataire  INTEGER NOT NULL,
    texte            TEXT    NOT NULL,
    lien_question    INTEGER,
    type_notif       TEXT    NOT NULL DEFAULT 'systeme'
                     CHECK (type_notif IN ('reponse','reaction','suivi','message','nouvelle_question','systeme')),
    est_lue          SMALLINT NOT NULL DEFAULT 0,
    cree_le          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_destinataire) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE,
    FOREIGN KEY (lien_question)   REFERENCES question(id_question)       ON DELETE SET NULL
);
CREATE INDEX idx_notif_destinataire ON notification(id_destinataire, est_lue, cree_le);

-- ----- Sessions web -----

CREATE TABLE session_web (
    id_token        TEXT    PRIMARY KEY,
    id_utilisateur  INTEGER NOT NULL,
    cree_le         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expire_le       TIMESTAMP    NOT NULL,
    user_agent      TEXT,
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
);
CREATE INDEX idx_sw_user ON session_web(id_utilisateur);

-- ----- Réinitialisation mot de passe -----

CREATE TABLE reinitialisation_mdp (
    id_jeton        TEXT    PRIMARY KEY,
    id_utilisateur  INTEGER NOT NULL,
    cree_le         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expire_le       TIMESTAMP    NOT NULL,
    utilise_le      TIMESTAMP,
    ip_demande      TEXT,
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
);
CREATE INDEX idx_reinit_user   ON reinitialisation_mdp(id_utilisateur);
CREATE INDEX idx_reinit_expire ON reinitialisation_mdp(expire_le);

-- ----- Vérification d'adresse e-mail (compte à activer) -----

CREATE TABLE verification_email (
    id_jeton        TEXT    PRIMARY KEY,
    id_utilisateur  INTEGER NOT NULL,
    cree_le         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expire_le       TIMESTAMP    NOT NULL,
    verifie_le      TIMESTAMP,
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
);
CREATE INDEX idx_verif_user ON verification_email(id_utilisateur);

-- ----- Identités externes (OAuth Google / LinkedIn) -----

CREATE TABLE identite_externe (
    id_externe      SERIAL PRIMARY KEY,
    id_utilisateur  INTEGER NOT NULL,
    fournisseur     TEXT    NOT NULL CHECK (fournisseur IN ('google','linkedin')),
    identifiant     TEXT    NOT NULL,   -- sub Google ou id LinkedIn
    email_verifie   SMALLINT NOT NULL DEFAULT 0,
    cree_le         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (fournisseur, identifiant),
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
);
CREATE INDEX idx_externe_user ON identite_externe(id_utilisateur);

-- ----- Journal d'audit admin -----

CREATE TABLE audit_admin (
    id_audit    SERIAL PRIMARY KEY,
    id_acteur   INTEGER NOT NULL,
    action      TEXT    NOT NULL,
    type_cible  TEXT,
    id_cible    INTEGER,
    details     TEXT,
    cree_le     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip          TEXT,
    FOREIGN KEY (id_acteur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
);
CREATE INDEX idx_audit_acteur ON audit_admin(id_acteur, cree_le);
CREATE INDEX idx_audit_action ON audit_admin(action);

-- ----- Vues d'agrégat (SQL identique en MySQL/SQLite) -----

CREATE VIEW v_question_stats AS
SELECT q.id_question, q.id_auteur, q.titre, q.id_secteur, q.publiee_le,
       (SELECT COUNT(*) FROM reponse r WHERE r.id_question = q.id_question) AS nb_reponses,
       (SELECT COUNT(*) FROM marquage_question m
          WHERE m.id_question = q.id_question AND m.type_marquage = 'utile') AS nb_utiles
  FROM question q;

CREATE VIEW v_mentor_carte AS
SELECT u.id_utilisateur, u.prenom, u.nom, u.photo_url, u.bio, u.ville,
       p.libelle AS pays,
       md.est_verifie, md.dispo, md.anciennete,
       COALESCE(md.note_moyenne, 0)            AS note_moyenne,
       (SELECT COUNT(*) FROM reponse r WHERE r.id_auteur = u.id_utilisateur) AS nb_reponses
  FROM utilisateur u
  JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
  LEFT JOIN pays p ON p.id_pays = u.id_pays
 WHERE u.role = 'mentor' AND u.est_actif = 1;

-- ----- Tentatives d'authentification (anti-force-brute) -----
--
-- Persistee en base et non en memoire : sur un hebergement sans etat
-- (Vercel, Render), chaque requete peut etre traitee par une instance
-- differente. Un compteur en memoire vive ne s'incrementerait jamais et
-- la protection serait purement decorative.

CREATE TABLE tentative_auth (
    id_tentative SERIAL PRIMARY KEY,
    cle          TEXT   NOT NULL,
    horodatage   BIGINT NOT NULL
);
CREATE INDEX idx_tentative_cle ON tentative_auth(cle, horodatage);

-- =====================================================================
-- Données de référence
-- =====================================================================

INSERT INTO secteur (libelle, couleur) VALUES
 ('Technologie','#2563EB'),('Médecine','#16A34A'),('Droit','#7C3AED'),
 ('Finance','#F59E0B'),('Arts','#EC4899'),('Éducation','#0EA5E9'),
 ('Ingénierie','#0891B2'),('Entrepreneuriat','#DC2626'),
 ('Sciences','#10B981'),('Communication','#8B5CF6'),
 ('Agriculture','#65A30D'),('Autre','#6B7280');

INSERT INTO pays (libelle, code_iso) VALUES
 ('France','FR'),('Belgique','BE'),('Suisse','CH'),('Canada','CA'),
 ('Sénégal','SN'),('Maroc','MA'),('Côte d''Ivoire','CI'),('Bénin','BJ'),
 ('Cameroun','CM'),('Algérie','DZ'),('Tunisie','TN'),('Mali','ML'),
 ('Burkina Faso','BF'),('Togo','TG'),('Niger','NE'),('Madagascar','MG'),
 ('Guinée','GN'),('Autre',NULL);
