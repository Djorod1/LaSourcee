"""Outils d'authentification et de protection des routes."""

import secrets
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
from flask import g, jsonify, request, current_app

from models.db import recuperer_un, executer

NOM_COOKIE_SESSION = "ls_session"


def hacher_mot_de_passe(mdp_clair: str) -> str:
    """Hash bcrypt (12 tours, salt aléatoire)."""
    if not mdp_clair or len(mdp_clair) < 8:
        raise ValueError("Le mot de passe doit comporter au moins 8 caractères.")
    sel = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(mdp_clair.encode("utf-8"), sel).decode("utf-8")


def verifier_mot_de_passe(mdp_clair: str, hache: str) -> bool:
    try:
        return bcrypt.checkpw(mdp_clair.encode("utf-8"), hache.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def creer_session(id_utilisateur: int, user_agent: str = None) -> str:
    """Crée un jeton de session opaque persisté en base."""
    purger_sessions_expirees()
    token = secrets.token_hex(32)
    duree = current_app.config["DUREE_SESSION_JOURS"]
    expire_le = datetime.utcnow() + timedelta(days=duree)
    executer(
        """INSERT INTO session_web (id_token, id_utilisateur,
                                    expire_le, user_agent)
           VALUES (%s, %s, %s, %s)""",
        (token, id_utilisateur, expire_le, (user_agent or "")[:255]),
        commit=True,
    )
    return token


def detruire_session(token: str) -> None:
    if token:
        executer("DELETE FROM session_web WHERE id_token = %s",
                 (token,), commit=True)


def utilisateur_depuis_jeton(token):
    if not token:
        return None
    return recuperer_un(
        """SELECT u.id_utilisateur, u.prenom, u.nom, u.email,
                  u.role, u.est_admin, u.permissions
             FROM session_web s
             JOIN utilisateur u ON u.id_utilisateur = s.id_utilisateur
            WHERE s.id_token = %s
              AND s.expire_le > CURRENT_TIMESTAMP
              AND u.est_actif = 1""",
        (token,),
    )


def jeton_session_courant():
    """Jeton de la requête en cours : cookie, ou en-tête pour les clients
    qui ne gèrent pas les cookies (tests, application mobile future)."""
    return (request.cookies.get(NOM_COOKIE_SESSION)
            or request.headers.get("X-Auth-Token"))


def _cookie_securise() -> bool:
    """Faut-il poser le drapeau ``Secure`` sur le cookie de session ?

    Derrière un reverse proxy ou sur une plateforme serverless (Vercel,
    Render), Flask ne voit qu'une connexion HTTP interne : c'est
    l'en-tête ``X-Forwarded-Proto`` qui indique le protocole réellement
    utilisé par le navigateur. ``COOKIE_SECURE`` permet de forcer la
    valeur si l'infrastructure est atypique.
    """
    force = current_app.config.get("COOKIE_SECURE")
    if force is not None:
        return bool(force)
    protocole = request.headers.get("X-Forwarded-Proto", "")
    if protocole:
        return protocole.split(",")[0].strip().lower() == "https"
    return bool(request.is_secure)


def poser_cookie_session(reponse, token):
    """Pose le cookie de session (HttpOnly, SameSite=Lax, Secure si HTTPS)."""
    jours = current_app.config.get("DUREE_SESSION_JOURS", 14)
    reponse.set_cookie(
        NOM_COOKIE_SESSION, token,
        httponly=True,
        secure=_cookie_securise(),
        samesite="Lax",
        path="/",
        max_age=60 * 60 * 24 * jours,
    )
    return reponse


def supprimer_cookie_session(reponse):
    """Efface le cookie de session avec exactement les mêmes attributs.

    Un navigateur n'efface un cookie que si le domaine, le chemin et les
    attributs de sécurité correspondent à ceux posés à la création.
    """
    reponse.delete_cookie(
        NOM_COOKIE_SESSION,
        path="/",
        httponly=True,
        secure=_cookie_securise(),
        samesite="Lax",
    )
    return reponse


def connexion_requise(fonction):
    """Refuse l'accès si aucun jeton de session valide n'est fourni."""

    @wraps(fonction)
    def emballe(*args, **kwargs):
        token = jeton_session_courant()
        utilisateur = utilisateur_depuis_jeton(token)
        if utilisateur is None:
            # Un jeton present mais refuse signifie une session expiree
            # ou revoquee ; son absence, une simple visite. Les deux cas
            # appellent la meme action mais pas la meme explication.
            if token:
                message = ("Votre session a expiré. Reconnectez-vous pour "
                           "continuer.")
            else:
                message = ("Connectez-vous pour accéder à cette partie du "
                           "site.")
            return jsonify({"erreur": message, "session_expiree": bool(token)}), 401
        g.utilisateur = utilisateur
        return fonction(*args, **kwargs)

    return emballe


def admin_requis(fonction):
    """Réservé aux comptes ``est_admin`` actif."""

    @wraps(fonction)
    @connexion_requise
    def emballe(*args, **kwargs):
        if not g.utilisateur.get("est_admin"):
            return jsonify({"erreur": "Accès réservé aux administrateurs."}), 403
        return fonction(*args, **kwargs)

    return emballe


def purger_sessions_expirees():
    """Supprime les sessions arrivees a echeance.

    Une session expiree ne donne plus acces a rien, mais sa ligne
    subsiste : le jeton reste en base indefiniment, et la table grossit
    sans fin. Declenchee une fois sur cinquante pour ne pas balayer la
    table a chaque connexion, et sans dependre d'une tache planifiee que
    l'hebergement serverless ne saurait pas executer.
    """
    import random
    if random.randint(1, 50) != 1:
        return
    try:
        executer("DELETE FROM session_web WHERE expire_le < CURRENT_TIMESTAMP",
                 commit=True)
    except Exception:
        pass
