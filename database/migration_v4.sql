-- =====================================================================
-- LaSourcee — Migration v4 (MySQL)
--
-- À exécuter UNE FOIS après schema.sql, migration_v2.sql et
-- migration_v3.sql, sur une base MySQL déjà en service.
--
-- SQLite et PostgreSQL n'en ont pas besoin : le démarrage de
-- l'application ajoute lui-même ces colonnes (COLONNES_ATTENDUES dans
-- backend/models/db.py). MySQL, lui, reste aux migrations manuelles.
-- Les installations neuves n'ont rien à faire : schema.sql est à jour.
--
-- MySQL 8.0 ne connaît pas « ADD COLUMN IF NOT EXISTS » : sur une base
-- déjà à jour, une instruction signale une colonne présente. L'erreur
-- est sans conséquence, passez à la suivante.
-- =====================================================================

USE lasource;

-- ----- Photo de profil servie à part (backend/utils/photos.py) -----
--
-- La date de mise à jour fait la version de l'adresse de la photo, donc
-- la durée de son cache ; la vignette sert aux avatars des listes.

ALTER TABLE utilisateur
  ADD COLUMN photo_maj_le VARCHAR(26) NULL AFTER photo_url;

ALTER TABLE utilisateur
  ADD COLUMN photo_vignette TEXT NULL AFTER photo_maj_le;
