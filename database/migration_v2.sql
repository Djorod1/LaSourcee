-- =====================================================================
-- LaSourcee — Migration v2
-- À exécuter UNE FOIS après schema.sql, AVANT seed.sql.
-- Ajoute : rôle super_admin, réinitialisation de mot de passe,
--          journal d'audit admin.
-- =====================================================================

USE lasource;

-- ----- 1. Élargir l'ENUM `role` -----

ALTER TABLE utilisateur
  MODIFY COLUMN role ENUM('visiteur','etudiant','mentor','admin','super_admin')
                NOT NULL DEFAULT 'etudiant';

-- ----- 2. Jetons de réinitialisation de mot de passe -----

CREATE TABLE IF NOT EXISTS reinitialisation_mdp (
    id_jeton        CHAR(64) NOT NULL,
    id_utilisateur  INT UNSIGNED NOT NULL,
    cree_le         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expire_le       DATETIME NOT NULL,
    utilise_le      DATETIME NULL,
    ip_demande      VARCHAR(45) NULL,
    PRIMARY KEY (id_jeton),
    KEY idx_reinit_user (id_utilisateur),
    KEY idx_reinit_expire (expire_le),
    CONSTRAINT fk_reinit_user FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----- 3. Journal d'audit des actions administrateur -----

CREATE TABLE IF NOT EXISTS audit_admin (
    id_audit        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_acteur       INT UNSIGNED NOT NULL,
    action          VARCHAR(80)  NOT NULL,
    type_cible      VARCHAR(40)  NULL,
    id_cible        INT UNSIGNED NULL,
    details         VARCHAR(500) NULL,
    cree_le         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip              VARCHAR(45)  NULL,
    PRIMARY KEY (id_audit),
    KEY idx_audit_acteur (id_acteur, cree_le),
    KEY idx_audit_action (action),
    CONSTRAINT fk_audit_acteur FOREIGN KEY (id_acteur)
        REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
