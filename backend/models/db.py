"""Accès à la base de données : SQLite, PostgreSQL ou MySQL.

La variable d'environnement ``DB_TYPE`` choisit le moteur :

  - ``sqlite`` (défaut) : fichier local ``lasource.db``. Aucune
    installation, idéal en développement et pour un hébergement
    disposant d'un disque persistant.
  - ``postgres`` : serveur PostgreSQL. **Indispensable sur les
    hébergements sans disque persistant (Vercel, Render, Railway)**,
    où un fichier SQLite serait effacé à chaque redémarrage.
  - ``mysql`` : serveur MySQL, si le cahier des charges l'impose.

Toutes les requêtes du code métier s'écrivent avec le paramètre ``%s``.
Pour SQLite il est traduit en ``?`` à la volée. Aucune route n'a donc à
connaître le moteur utilisé.

Sur PostgreSQL, la variable ``DATABASE_URL`` (fournie telle quelle par
Vercel, Neon, Supabase et Render) suffit : elle contient l'hôte, le
port, l'utilisateur, le mot de passe et la base.
"""

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import g, current_app


# ----- Détection du moteur ------------------------------------------------

def _type_db():
    valeur = (os.getenv("DB_TYPE", "sqlite") or "sqlite").lower()
    # « postgresql » et « pg » sont acceptés comme synonymes
    if valeur in ("postgresql", "pg"):
        return "postgres"
    return valeur


# ----- Imports conditionnels (aucune dépendance inutile) ------------------

def _import_pymysql():
    import pymysql
    import pymysql.cursors
    return pymysql, pymysql.cursors


def _import_psycopg():
    """Accepte psycopg2 (classique) ou psycopg 3."""
    try:
        import psycopg2
        import psycopg2.extras
        return psycopg2, psycopg2.extras, 2
    except ImportError:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg, dict_row, 3


# ----- Traduction du dialecte pour SQLite --------------------------------

_RE_PARAM = re.compile(r"%s")


def _convertir_pour_sqlite(sql):
    """Remplace les paramètres %s par ? (dialecte SQLite)."""
    return _RE_PARAM.sub("?", sql)


# ----- Curseur uniforme ---------------------------------------------------

class CurseurAdapte:
    """Expose la même interface quel que soit le moteur :

    - ``execute(sql, params)`` accepte du SQL écrit avec ``%s`` ;
    - ``fetchone`` / ``fetchall`` renvoient des dictionnaires ;
    - ``lastrowid`` fonctionne aussi sur PostgreSQL.
    """

    def __init__(self, curseur_natif, moteur):
        self._cur = curseur_natif
        self._moteur = moteur          # 'sqlite' | 'postgres' | 'mysql'
        self._derniere_requete = ""

    # -- exécution --------------------------------------------------------

    def _adapter(self, sql):
        if self._moteur == "sqlite":
            return _convertir_pour_sqlite(sql)
        if self._moteur == "mysql":
            # MySQL n'accepte pas « INSERT ... DEFAULT VALUES »
            return sql.replace("DEFAULT VALUES", "() VALUES ()")
        return sql

    def execute(self, sql, params=()):
        self._derniere_requete = sql
        return self._cur.execute(self._adapter(sql), params or ())

    def executemany(self, sql, seq_params):
        self._derniere_requete = sql
        return self._cur.executemany(self._adapter(sql), seq_params)

    # -- lecture ----------------------------------------------------------

    def fetchone(self):
        ligne = self._cur.fetchone()
        if ligne is None:
            return None
        if self._moteur == "sqlite":
            return {k: ligne[k] for k in ligne.keys()}
        return dict(ligne)

    def fetchall(self):
        lignes = self._cur.fetchall()
        if self._moteur == "sqlite":
            return [{k: l[k] for k in l.keys()} for l in lignes]
        return [dict(l) for l in lignes]

    # -- métadonnées ------------------------------------------------------

    @property
    def lastrowid(self):
        """Identifiant de la dernière ligne insérée.

        PostgreSQL n'expose pas ``lastrowid`` : on interroge la dernière
        valeur de séquence produite dans la session courante.
        """
        if self._moteur == "postgres":
            try:
                self._cur.execute("SELECT lastval()")
                ligne = self._cur.fetchone()
                if ligne is None:
                    return None
                return ligne["lastval"] if isinstance(ligne, dict) else ligne[0]
            except Exception:
                return None
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        return self._cur.close()


# ----- Ouverture de connexion --------------------------------------------

def _ouvrir_connexion():
    cfg = current_app.config
    moteur = cfg.get("DB_TYPE", _type_db())

    # ---- SQLite ---------------------------------------------------------
    if moteur == "sqlite":
        chemin = Path(cfg.get("DB_PATH", "lasource.db")).resolve()
        chemin.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(chemin), isolation_level="DEFERRED")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn, "sqlite"

    # ---- PostgreSQL -----------------------------------------------------
    if moteur == "postgres":
        module, extras, version = _import_psycopg()
        url = cfg.get("DATABASE_URL") or os.getenv("DATABASE_URL", "")
        if version == 2:
            if url:
                conn = module.connect(url, cursor_factory=extras.RealDictCursor)
            else:
                conn = module.connect(
                    host=cfg["DB_HOST"], port=cfg.get("DB_PORT", 5432),
                    user=cfg["DB_USER"], password=cfg["DB_PASSWORD"],
                    dbname=cfg["DB_NAME"],
                    sslmode=os.getenv("DB_SSLMODE", "prefer"),
                    cursor_factory=extras.RealDictCursor,
                )
        else:  # psycopg 3
            if url:
                conn = module.connect(url, row_factory=extras)
            else:
                conn = module.connect(
                    host=cfg["DB_HOST"], port=cfg.get("DB_PORT", 5432),
                    user=cfg["DB_USER"], password=cfg["DB_PASSWORD"],
                    dbname=cfg["DB_NAME"], row_factory=extras,
                )
        conn.autocommit = False
        return conn, "postgres"

    # ---- MySQL ----------------------------------------------------------
    pymysql, curseurs = _import_pymysql()
    conn = pymysql.connect(
        host=cfg["DB_HOST"], port=cfg.get("DB_PORT", 3306),
        user=cfg["DB_USER"], password=cfg["DB_PASSWORD"],
        database=cfg["DB_NAME"], charset="utf8mb4",
        cursorclass=curseurs.DictCursor, autocommit=False,
    )
    return conn, "mysql"


# ----- API publique -------------------------------------------------------

def obtenir_connexion():
    if "db_conn" not in g:
        g.db_conn, g.db_moteur = _ouvrir_connexion()
    return g.db_conn


def fermer_connexion(_=None):
    conn = g.pop("db_conn", None)
    g.pop("db_moteur", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


@contextmanager
def curseur(commit=False):
    conn = obtenir_connexion()
    moteur = g.get("db_moteur", "sqlite")
    cur = CurseurAdapte(conn.cursor(), moteur)
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        cur.close()


def executer(sql, params=None, commit=False):
    with curseur(commit=commit) as cur:
        cur.execute(sql, params or ())
        return cur.rowcount


def recuperer_un(sql, params=None):
    with curseur() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def recuperer_tous(sql, params=None):
    with curseur() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


# ----- Initialisation automatique du schéma -------------------------------

def _fichier_schema(moteur, racine):
    noms = {
        "sqlite": "schema_sqlite.sql",
        "postgres": "schema_postgres.sql",
        "mysql": "schema.sql",
    }
    return racine / "database" / noms.get(moteur, "schema_sqlite.sql")


def initialiser_si_necessaire(app):
    """Crée le schéma au premier démarrage.

    - SQLite : crée le fichier s'il n'existe pas.
    - PostgreSQL : crée les tables si elles sont absentes (utile pour un
      déploiement automatique où l'on n'a pas de console SQL).
    - MySQL : ne fait rien, le schéma se charge manuellement.
    """
    moteur = app.config.get("DB_TYPE", _type_db())
    racine = Path(__file__).resolve().parent.parent.parent
    schema = _fichier_schema(moteur, racine)

    if moteur == "sqlite":
        chemin = Path(app.config.get("DB_PATH", "lasource.db")).resolve()
        if chemin.exists() and chemin.stat().st_size > 0:
            return
        if not schema.exists():
            return
        chemin.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(chemin))
        try:
            conn.executescript(schema.read_text(encoding="utf-8"))
            conn.commit()
        finally:
            conn.close()
        return

    if moteur == "postgres":
        if not schema.exists():
            return
        with app.app_context():
            try:
                deja = recuperer_un(
                    "SELECT 1 AS present FROM information_schema.tables "
                    "WHERE table_name = 'utilisateur' LIMIT 1"
                )
                if deja:
                    return
                with curseur(commit=True) as cur:
                    cur.execute(schema.read_text(encoding="utf-8"))
            except Exception as exc:
                app.logger.warning(
                    "Initialisation PostgreSQL ignorée : %s", exc)
