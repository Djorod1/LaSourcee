"""Point d'entrée du backend LaSourcee.

L'application Flask sert :

  - l'API JSON sous le préfixe ``/api`` ;
  - le frontend statique (index.html, script.js, styles.css) lorsqu'elle
    tourne seule, en développement ou sur un serveur classique.

Sur Vercel, les fichiers statiques sont distribués par le CDN et seules
les routes ``/api/*`` atteignent cette application : voir ``api/index.py``
et ``vercel.json`` à la racine du dépôt.
"""

import logging
import os
import traceback

from flask import Flask, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config, anomalies_configuration
from models.db import fermer_connexion, initialiser_si_necessaire
from utils.securite import appliquer_entetes_securite

from routes.auth          import bp_auth
from routes.oauth         import bp_oauth
from routes.profil        import bp_profil
from routes.questions     import bp_questions
from routes.reponses      import bp_reponses
from routes.mentors       import bp_mentors
from routes.candidature_mentor import bp_candidature
from routes.messagerie    import bp_messagerie
from routes.notifications import bp_notifications
from routes.recherche     import bp_recherche
from routes.admin         import bp_admin

logger = logging.getLogger("lasource")


# Fichiers du dépôt réellement destinés au navigateur. Tout le reste —
# code du backend, schémas SQL, scripts d'administration, fichier .env —
# doit rester inaccessible : servir la racine du dépôt telle quelle
# publierait le code source de l'application.
FICHIERS_PUBLICS = {
    "index.html",
    "verifier-email.html",
    "reinitialiser.html",
    "api.js",
    "script.js",
    "styles.css",
    "favicon.ico",
    "robots.txt",
    "sitemap.xml",
}

DOSSIERS_PUBLICS = {"assets"}


def _configurer_logs():
    """Logs structurés : un seul flux, format compact, pas de doublon."""
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        "%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _nombre_de_proxys():
    """Combien de reverse proxys de confiance devant l'application ?

    Sans cette information, ``request.remote_addr`` renverrait l'adresse
    du proxy : tous les visiteurs partageraient alors le même compteur
    anti-force-brute, et les liens d'e-mail seraient en ``http://``.

    À l'inverse, faire confiance aux en-têtes ``X-Forwarded-*`` sans
    proxy devant permettrait à n'importe quel client de se forger une
    fausse adresse IP. La valeur par défaut est donc 0 en local et 1 sur
    une plateforme managée.
    """
    brut = os.getenv("NB_PROXYS")
    if brut is not None and brut.strip() != "":
        try:
            return max(0, int(brut))
        except ValueError:
            pass
    return 1 if (Config.SUR_VERCEL or Config.EST_PRODUCTION) else 0


def _signaler_configuration():
    """Écrit dans les logs ce qui est mal configuré, sans jamais planter."""
    for gravite, message in anomalies_configuration():
        if gravite == "bloquant":
            logger.error("Configuration : %s", message)
        else:
            logger.warning("Configuration : %s", message)


def _ressource_publique(dossier_front, ressource):
    """Le chemin demandé désigne-t-il un fichier destiné au public ?

    Refuse aussi bien les fichiers du dépôt qui ne sont pas du frontend
    que les tentatives de remontée d'arborescence (``../``).
    """
    try:
        cible = (dossier_front / ressource).resolve()
        relatif = cible.relative_to(dossier_front)
    except (ValueError, OSError):
        return False

    parties = relatif.parts
    if not parties:
        return False
    if len(parties) == 1:
        return parties[0] in FICHIERS_PUBLICS
    return parties[0] in DOSSIERS_PUBLICS


def creer_application():
    _configurer_logs()
    dossier_front = Config.DOSSIER_FRONTEND
    # static_folder=None : le service des fichiers est assuré plus bas par
    # une route explicite, restreinte aux ressources du frontend.
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    nb_proxys = _nombre_de_proxys()
    if nb_proxys:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=nb_proxys, x_proto=nb_proxys,
            x_host=nb_proxys, x_port=nb_proxys,
        )

    for bp in (bp_auth, bp_oauth, bp_profil, bp_questions, bp_reponses,
               bp_mentors, bp_candidature, bp_messagerie, bp_notifications,
               bp_recherche, bp_admin):
        app.register_blueprint(bp)

    app.teardown_appcontext(fermer_connexion)
    app.after_request(appliquer_entetes_securite)

    _signaler_configuration()

    # Création automatique du schéma au premier démarrage. Ne doit jamais
    # empêcher l'application de répondre : sur un système de fichiers en
    # lecture seule, l'échec est journalisé puis ignoré.
    if app.config.get("INIT_DB_AUTO", True):
        try:
            initialiser_si_necessaire(app)
        except Exception as exc:
            logger.error("Initialisation de la base impossible : %s", exc)

    logger.info("Base de données : %s | environnement : %s",
                app.config.get("DB_TYPE"), app.config.get("ENVIRONNEMENT"))

    # ---- Gestion globale des erreurs : jamais de pile en réponse client ----

    @app.errorhandler(HTTPException)
    def _erreur_http(exc):
        # 404, 405, 413... renvoyés en JSON propre
        return jsonify({"erreur": exc.description}), exc.code

    @app.errorhandler(Exception)
    def _erreur_inattendue(exc):
        # Log côté serveur (avec pile) mais réponse anonyme côté client
        logger.error("Exception non gérée : %s\n%s",
                     exc, traceback.format_exc())
        return jsonify({
            "erreur": "Une erreur interne est survenue. "
                      "Si le problème persiste, contactez l'administrateur."
        }), 500

    @app.errorhandler(404)
    def _non_trouve(_):
        return jsonify({"erreur": "Ressource introuvable."}), 404

    # ---- Service du frontend statique ----
    #
    # Utile en développement et sur un serveur classique. Sur Vercel ces
    # fichiers sont distribués par le CDN et cette route n'est jamais
    # atteinte.

    @app.get("/")
    def racine():
        return send_from_directory(dossier_front, "index.html")

    @app.get("/<path:ressource>")
    def fichier_frontend(ressource):
        if not _ressource_publique(dossier_front, ressource):
            return jsonify({"erreur": "Ressource introuvable."}), 404
        try:
            return send_from_directory(dossier_front, ressource)
        except NotFound:
            return jsonify({"erreur": "Ressource introuvable."}), 404

    # ---- Supervision ----

    @app.get("/api/sante")
    def sante():
        """Sonde utilisée par le frontend au chargement et par l'hébergeur.

        Elle vérifie que la base répond réellement : un serveur qui
        démarre mais dont la base est injoignable doit être signalé comme
        dégradé, pas comme sain.
        """
        from models.db import recuperer_un

        details = {
            "statut": "ok",
            "base": app.config.get("DB_TYPE"),
            "environnement": app.config.get("ENVIRONNEMENT"),
        }
        try:
            recuperer_un("SELECT 1 AS ok")
        except Exception as exc:
            logger.error("Sonde de santé : base injoignable (%s)", exc)
            details["statut"] = "degrade"
            details["erreur"] = "Base de données injoignable."
            return jsonify(details), 503
        return jsonify(details), 200

    return app


if __name__ == "__main__":
    # DEBUG dépend d'une variable d'env, jamais activé par défaut en prod
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    port = int(os.getenv("PORT", "5000"))
    creer_application().run(host="0.0.0.0", port=port, debug=debug)
