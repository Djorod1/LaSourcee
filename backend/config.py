"""Paramètres de configuration du backend LaSourcee.

Toute la configuration passe par des variables d'environnement, lues
dans ``backend/.env`` en développement et injectées par l'hébergeur en
production (Vercel, Render, Railway, VPS...).

DB_TYPE choisit le moteur de base de données :
  - ``sqlite``   (défaut) : fichier local, zéro installation ;
  - ``postgres``          : serveur PostgreSQL, **obligatoire sur un
    hébergement sans disque persistant** comme Vercel ;
  - ``mysql``             : serveur MySQL classique.
"""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

DOSSIER_BACKEND = Path(__file__).resolve().parent
load_dotenv(DOSSIER_BACKEND / ".env")


def _booleen(nom, defaut=False):
    """Lit une variable d'environnement booléenne (1/true/oui/yes)."""
    brut = os.getenv(nom)
    if brut is None or brut == "":
        return defaut
    return brut.strip().lower() in ("1", "true", "vrai", "oui", "yes", "on")


def _booleen_ou_auto(nom):
    """Comme ``_booleen`` mais renvoie ``None`` si la variable est absente.

    ``None`` signifie « décide automatiquement à l'exécution ».
    """
    brut = os.getenv(nom)
    if brut is None or brut.strip() == "" or brut.strip().lower() == "auto":
        return None
    return brut.strip().lower() in ("1", "true", "vrai", "oui", "yes", "on")


def _moteur():
    """Moteur de base à utiliser.

    Quand ``DB_TYPE`` n'est pas renseigné mais qu'une URL PostgreSQL est
    présente, c'est elle qui fait foi. Les intégrations d'hébergeurs
    (Vercel Postgres, Neon, Supabase) injectent l'URL automatiquement
    mais pas ``DB_TYPE`` : sans cette déduction, l'application
    retomberait sur SQLite, tenterait d'écrire dans un système de
    fichiers en lecture seule, et le site afficherait « serveur
    indisponible » alors que la base est pourtant là.
    """
    valeur = (os.getenv("DB_TYPE") or "").strip().lower()
    if not valeur:
        if os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL"):
            return "postgres"
        return "sqlite"
    if valeur in ("postgresql", "pg"):
        return "postgres"
    return valeur


def _port_par_defaut(moteur):
    return {"postgres": 5432, "mysql": 3306}.get(moteur, 0)


# Détection de l'environnement d'exécution.
#   VERCEL             -> posée automatiquement par Vercel
#   ENVIRONNEMENT      -> « production » ou « developpement » (au choix)
_SUR_VERCEL = bool(os.getenv("VERCEL"))
_ENVIRONNEMENT = (os.getenv("ENVIRONNEMENT")
                  or os.getenv("VERCEL_ENV")
                  or ("production" if _SUR_VERCEL else "developpement"))


class Config:
    # ---- Environnement ---------------------------------------------------
    ENVIRONNEMENT = _ENVIRONNEMENT.strip().lower()
    EST_PRODUCTION = ENVIRONNEMENT in ("production", "prod")
    SUR_VERCEL = _SUR_VERCEL

    # ---- Clé de signature ------------------------------------------------
    # Utilisée par Flask pour le cookie d'état OAuth LinkedIn. En
    # production elle DOIT être fournie et rester stable : sur un
    # hébergement serverless, chaque instance repartirait sinon avec une
    # clé différente et la connexion LinkedIn échouerait au retour.
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    SECRET_KEY_FOURNIE = bool(os.getenv("SECRET_KEY"))

    # ---- Base de données -------------------------------------------------
    DB_TYPE = _moteur()

    # SQLite — chemin du fichier (relatif au dépôt par défaut)
    DB_PATH = os.getenv(
        "DB_PATH",
        str((DOSSIER_BACKEND.parent / "lasource.db").resolve()),
    )

    # PostgreSQL — une seule variable suffit chez Neon, Supabase, Vercel
    # Postgres, Render et Railway : ils fournissent tous DATABASE_URL.
    DATABASE_URL = (os.getenv("DATABASE_URL")
                    or os.getenv("POSTGRES_URL")
                    or "")

    # Connexion détaillée (PostgreSQL sans DATABASE_URL, ou MySQL)
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT") or _port_par_defaut(DB_TYPE) or 3306)
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "lasource")

    # Création automatique du schéma au premier démarrage.
    INIT_DB_AUTO = _booleen("INIT_DB_AUTO", True)

    # ---- Sessions et cookies --------------------------------------------
    DUREE_SESSION_JOURS = int(os.getenv("DUREE_SESSION_JOURS", "14"))

    # None = détection automatique via X-Forwarded-Proto (recommandé).
    COOKIE_SECURE = _booleen_ou_auto("COOKIE_SECURE")

    # Cookie de session Flask (état OAuth uniquement)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (COOKIE_SECURE if COOKIE_SECURE is not None
                             else EST_PRODUCTION)

    # ---- Adresse publique ------------------------------------------------
    # Utilisée dans les liens des e-mails (vérification d'adresse,
    # réinitialisation de mot de passe, notifications).
    URL_PLATEFORME = (os.getenv("URL_PLATEFORME")
                      or (f"https://{os.getenv('VERCEL_URL')}"
                          if os.getenv("VERCEL_URL") else "")
                      or "http://localhost:5000").rstrip("/")

    # ---- Confirmation d'adresse e-mail -----------------------------------
    # Exiger la confirmation avant la première connexion empêche de créer
    # un compte avec l'adresse de quelqu'un d'autre. Ce n'est activé par
    # défaut que là où le message peut réellement partir : en production
    # ET avec un envoi SMTP configuré. L'imposer sans SMTP rendrait
    # l'inscription impossible, personne ne recevant jamais le lien.
    # VERIFICATION_EMAIL_OBLIGATOIRE tranche explicitement si elle est
    # renseignée.
    VERIFICATION_EMAIL_OBLIGATOIRE = _booleen(
        "VERIFICATION_EMAIL_OBLIGATOIRE",
        EST_PRODUCTION
        and (os.getenv("EMAIL_MODE", "console") or "console").lower() == "smtp",
    )

    # ---- Frontend --------------------------------------------------------
    # Racine du dépôt : index.html, script.js, styles.css, assets/...
    DOSSIER_FRONTEND = DOSSIER_BACKEND.parent.resolve()


def anomalies_configuration():
    """Liste les problèmes de configuration détectés au démarrage.

    Renvoie une liste de couples ``(gravite, message)`` où ``gravite``
    vaut ``"bloquant"`` ou ``"avertissement"``. Rien n'est levé : c'est
    l'appelant qui décide quoi en faire (log au démarrage, page de
    diagnostic pour l'administrateur...).
    """
    problemes = []

    if Config.EST_PRODUCTION and not Config.SECRET_KEY_FOURNIE:
        problemes.append((
            "bloquant",
            "SECRET_KEY n'est pas définie. Une clé aléatoire a été générée "
            "pour cette instance : la connexion LinkedIn échouera de façon "
            "intermittente. Définissez SECRET_KEY dans les variables "
            "d'environnement.",
        ))

    if Config.DB_TYPE == "sqlite" and Config.SUR_VERCEL:
        problemes.append((
            "bloquant",
            "Aucune base PostgreSQL configurée sur Vercel : ni DATABASE_URL "
            "ni POSTGRES_URL n'est présente, et le système de fichiers y est "
            "éphémère et en lecture seule. L'application ne pourra ni lire "
            "ni écrire. Ajoutez DATABASE_URL dans les variables "
            "d'environnement, puis redéployez — les variables ne sont lues "
            "qu'au déploiement.",
        ))

    if Config.DB_TYPE == "postgres" and not (
            Config.DATABASE_URL or os.getenv("DB_HOST")):
        problemes.append((
            "bloquant",
            "DB_TYPE=postgres sans DATABASE_URL ni DB_HOST : aucune base "
            "à contacter.",
        ))

    if Config.EST_PRODUCTION and (
            os.getenv("EMAIL_MODE", "console").lower() != "smtp"):
        problemes.append((
            "avertissement",
            "EMAIL_MODE n'est pas « smtp » : les messages de vérification "
            "d'adresse et de réinitialisation ne partiront pas réellement. "
            "La confirmation d'adresse reste donc facultative, faute de "
            "pouvoir envoyer le lien — n'importe qui peut s'inscrire avec "
            "l'adresse d'un tiers.",
        ))

    # Un identifiant client Google se termine toujours par
    # « .apps.googleusercontent.com ». Une valeur d'une autre forme —
    # le secret client collé par erreur, une valeur tronquée, des
    # guillemets ou une espace résiduelle — produit chez Google une
    # erreur 401 « invalid_client : The OAuth client was not found »,
    # dont rien dans l'application ne laisse deviner l'origine.
    client_google = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    if client_google and not client_google.endswith(
            ".apps.googleusercontent.com"):
        problemes.append((
            "bloquant",
            "GOOGLE_CLIENT_ID ne ressemble pas à un identifiant client "
            "Google : il devrait se terminer par "
            "« .apps.googleusercontent.com ». Google refusera la connexion "
            "avec « invalid_client ». Vérifiez que vous avez copié "
            "l'identifiant client, et non le secret client.",
        ))

    if Config.EST_PRODUCTION and Config.URL_PLATEFORME.startswith("http://"):
        problemes.append((
            "avertissement",
            f"URL_PLATEFORME vaut {Config.URL_PLATEFORME} : les liens "
            "envoyés par e-mail ne seront pas en HTTPS.",
        ))

    return problemes
