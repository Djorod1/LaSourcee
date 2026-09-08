"""OAuth Google et LinkedIn — authentification fédérée réelle.

Configuration requise (backend/.env) :
  GOOGLE_CLIENT_ID         (créé sur Google Cloud Console)
  LINKEDIN_CLIENT_ID
  LINKEDIN_CLIENT_SECRET
  LINKEDIN_REDIRECT_URI    (par exemple http://localhost:5000/api/auth/linkedin/callback)

Si une de ces variables est absente, l'endpoint correspondant retourne
une erreur 503 explicite au lieu d'une 500 cryptique.
"""

import logging
import os
import secrets
from urllib.parse import urlencode

from flask import Blueprint, current_app, jsonify, redirect, request, session

from models.db import recuperer_un, executer, curseur
from utils.auth_helpers import creer_session, poser_cookie_session

bp_oauth = Blueprint("oauth", __name__, url_prefix="/api/auth")
logger = logging.getLogger("lasource.oauth")


# ============================================================
# CONFIG — exposée au frontend via /api/config
# ============================================================

@bp_oauth.get("/config")
def config_publique():
    """Expose aux frontend les clés publiques nécessaires (Client ID Google,
    flag LinkedIn). Pas de secret."""
    return jsonify({
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "linkedin_configure": bool(
            os.getenv("LINKEDIN_CLIENT_ID") and os.getenv("LINKEDIN_CLIENT_SECRET")
        ),
    })


# ============================================================
# GOOGLE — vérification de l'ID token via google-auth
# ============================================================

@bp_oauth.post("/google")
def connexion_google():
    """Reçoit un ID token Google, le vérifie, crée/connecte le compte."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        return jsonify({
            "erreur": "Connexion Google non configurée sur ce serveur. "
                      "Voir README pour la procédure de configuration."
        }), 503

    d = request.get_json(silent=True) or {}
    jeton_id = d.get("credential")
    if not jeton_id:
        return jsonify({"erreur": "Jeton Google manquant."}), 400

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as gr
        info = id_token.verify_oauth2_token(jeton_id, gr.Request(), client_id)
    except ImportError:
        return jsonify({"erreur": "google-auth non installé sur le serveur."}), 500
    except ValueError as exc:
        logger.warning("ID token Google invalide : %s", exc)
        return jsonify({"erreur": "Jeton Google invalide."}), 401

    sub = info.get("sub")
    email = (info.get("email") or "").lower()
    email_verifie = bool(info.get("email_verified"))
    prenom = info.get("given_name") or email.split("@")[0]
    nom = info.get("family_name") or ""
    photo = info.get("picture")

    if not sub or not email:
        return jsonify({"erreur": "Profil Google incomplet."}), 400

    id_user = _trouver_ou_creer_compte_externe(
        "google", sub, email, email_verifie, prenom, nom, photo
    )
    return _terminer_connexion(id_user)


# ============================================================
# LINKEDIN — flow Authorization Code OAuth 2.0
# ============================================================

@bp_oauth.get("/linkedin")
def lancer_linkedin():
    client_id = os.getenv("LINKEDIN_CLIENT_ID")
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI")
    if not (client_id and redirect_uri):
        return jsonify({
            "erreur": "Connexion LinkedIn non configurée sur ce serveur."
        }), 503

    # Stocker un état anti-CSRF dans la session Flask serveur
    etat = secrets.token_urlsafe(24)
    session["linkedin_state"] = etat

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": etat,
        "scope": "openid profile email",
    }
    return redirect("https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params))


@bp_oauth.get("/linkedin/callback")
def retour_linkedin():
    client_id = os.getenv("LINKEDIN_CLIENT_ID")
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI")
    if not (client_id and client_secret and redirect_uri):
        return jsonify({"erreur": "LinkedIn non configuré."}), 503

    code = request.args.get("code")
    etat = request.args.get("state")
    erreur = request.args.get("error")
    if erreur:
        return redirect("/?erreur=" + erreur)
    if not code:
        return jsonify({"erreur": "Code OAuth manquant."}), 400
    if etat != session.pop("linkedin_state", None):
        return jsonify({"erreur": "État OAuth invalide (CSRF)."}), 400

    # Échanger le code contre un access token
    try:
        import requests as req
    except ImportError:
        return jsonify({"erreur": "Bibliothèque requests non installée."}), 500

    try:
        r = req.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        r.raise_for_status()
        jeton = r.json().get("access_token")
        if not jeton:
            raise ValueError("Pas d'access_token dans la réponse LinkedIn.")

        # OpenID Connect endpoint LinkedIn /v2/userinfo
        ru = req.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {jeton}"},
            timeout=10,
        )
        ru.raise_for_status()
        info = ru.json()
    except Exception as exc:
        logger.warning("Échec OAuth LinkedIn : %s", exc)
        return redirect("/?erreur=linkedin")

    sub = info.get("sub")
    email = (info.get("email") or "").lower()
    email_verifie = bool(info.get("email_verified"))
    prenom = info.get("given_name") or email.split("@")[0]
    nom = info.get("family_name") or ""
    photo = info.get("picture")

    if not sub or not email:
        return redirect("/?erreur=linkedin_profil_incomplet")

    id_user = _trouver_ou_creer_compte_externe(
        "linkedin", sub, email, email_verifie, prenom, nom, photo
    )
    # La réponse DOIT être celle qui porte le cookie : renvoyer une
    # redirection construite à part perdrait la session.
    return _terminer_connexion(id_user, redirection="/?connexion=linkedin")


# ============================================================
# Helpers internes
# ============================================================

def _trouver_ou_creer_compte_externe(fournisseur, sub_externe,
                                     email, email_verifie,
                                     prenom, nom, photo_url):
    """Politique :
      1. Si identité externe (fournisseur, sub) existe → connecter ce compte.
      2. Sinon si un compte existe avec cet e-mail → lier l'identité externe.
      3. Sinon créer un nouveau compte (mdp aléatoire long).
    """
    existe = recuperer_un(
        "SELECT id_utilisateur FROM identite_externe "
        "WHERE fournisseur = %s AND identifiant = %s",
        (fournisseur, sub_externe),
    )
    if existe:
        return existe["id_utilisateur"]

    compte = recuperer_un(
        "SELECT id_utilisateur FROM utilisateur WHERE email = %s",
        (email,),
    )

    with curseur(commit=True) as cur:
        if compte:
            id_user = compte["id_utilisateur"]
        else:
            # Création : mdp aléatoire (l'utilisateur ne s'en sert pas, OAuth seul)
            import bcrypt as _b
            hache = _b.hashpw(secrets.token_urlsafe(32).encode(),
                              _b.gensalt(rounds=12)).decode()
            cur.execute(
                """INSERT INTO utilisateur
                      (prenom, nom, email, mot_de_passe, role,
                       photo_url, email_verifie, est_actif)
                   VALUES (%s, %s, %s, %s, 'etudiant', %s, %s, 1)""",
                (prenom, nom, email, hache, photo_url,
                 1 if email_verifie else 0),
            )
            id_user = cur.lastrowid

        cur.execute(
            """INSERT INTO identite_externe
                  (id_utilisateur, fournisseur, identifiant, email_verifie)
               VALUES (%s, %s, %s, %s)""",
            (id_user, fournisseur, sub_externe, 1 if email_verifie else 0),
        )
    return id_user


def _terminer_connexion(id_user, redirection=None):
    """Crée la session, pose le cookie et renvoie la réponse.

    - ``redirection`` renseignée : le navigateur revient d'un fournisseur
      externe (LinkedIn), on le renvoie sur la page demandée ;
    - sinon : réponse JSON, attendue par l'appel ``fetch`` (Google).
    """
    user_agent = request.headers.get("User-Agent", "")[:255]
    token = creer_session(id_user, user_agent)
    rep = (redirect(redirection) if redirection
           else jsonify({"ok": True, "id_utilisateur": id_user}))
    return poser_cookie_session(rep, token)
