"""Inscription, connexion et déconnexion."""

import logging
import re

from flask import Blueprint, current_app, g, request, jsonify, make_response

from models.db import recuperer_un, recuperer_tous, executer, curseur
from utils.auth_helpers import (
    hacher_mot_de_passe,
    verifier_mot_de_passe,
    creer_session,
    detruire_session,
    connexion_requise,
    jeton_session_courant,
    poser_cookie_session,
    supprimer_cookie_session,
)
from utils.urls import url_publique
from utils.securite import (
    mot_de_passe_valide,
    est_bloque,
    enregistrer_echec,
    reinitialiser,
    MAX_INSCRIPTIONS,
    MAX_DEMANDES_MDP,
)

logger = logging.getLogger("lasourcee.auth")

bp_auth = Blueprint("auth", __name__, url_prefix="/api/auth")

REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLES_AUTORISES = {"etudiant", "mentor"}


def _erreur(message, code=400):
    return jsonify({"erreur": message}), code


@bp_auth.post("/inscription")
def inscription():
    # Sans limitation, un robot créerait des comptes en série et
    # déclencherait autant d'envois d'e-mails — au frais du domaine
    # expéditeur, dont la réputation en pâtirait.
    cle_debit = f"inscription|{request.remote_addr}"
    reste = est_bloque(cle_debit, MAX_INSCRIPTIONS)
    if reste:
        return _erreur(
            "Trop de créations de compte depuis cette connexion. "
            f"Réessayez dans environ {max(1, reste // 60)} minute(s).", 429)

    d = request.get_json(silent=True) or {}
    prenom = (d.get("prenom") or "").strip()
    nom    = (d.get("nom") or "").strip()
    email  = (d.get("email") or "").strip().lower()
    mdp    = d.get("mot_de_passe") or ""
    role   = d.get("role") or "etudiant"

    if not (prenom and nom):
        return _erreur("Prénom et nom obligatoires.")
    if not REGEX_EMAIL.match(email):
        return _erreur("Adresse e-mail invalide.")
    if role not in ROLES_AUTORISES:
        return _erreur("Rôle invalide (étudiant ou mentor).")
    ok, message = mot_de_passe_valide(mdp)
    if not ok:
        return _erreur(message)

    if recuperer_un("SELECT 1 FROM utilisateur WHERE email = %s LIMIT 1",
                    (email,)):
        return _erreur("Cette adresse e-mail est déjà utilisée.", 409)

    hache = hacher_mot_de_passe(mdp)
    with curseur(commit=True) as cur:
        cur.execute(
            """INSERT INTO utilisateur
                  (prenom, nom, email, mot_de_passe, role, email_verifie)
               VALUES (%s, %s, %s, %s, %s, 0)""",
            (prenom, nom, email, hache, role),
        )
        id_user = cur.lastrowid
        # Les mentors ont une ligne associée pour leurs détails publics.
        if role == "mentor":
            cur.execute(
                "INSERT INTO mentor_details (id_utilisateur) VALUES (%s)",
                (id_user,),
            )

    enregistrer_echec(cle_debit)   # ici : compte le débit, pas un échec

    # Envoi de l'e-mail de vérification (jeton 24h)
    email_parti = _envoyer_email_verification(id_user, email, prenom)

    # Si vérification obligatoire, on NE connecte PAS automatiquement
    obligatoire = current_app.config["VERIFICATION_EMAIL_OBLIGATOIRE"]
    if obligatoire:
        return jsonify({
            "id_utilisateur": id_user,
            "role": role,
            "verification_requise": True,
            "email_envoye": email_parti,
            "message": (
                "Un e-mail de confirmation vous a été envoyé." if email_parti
                else "Votre compte est créé, mais l'e-mail de confirmation "
                     "n'a pas pu être envoyé. Contactez un administrateur "
                     "pour activer votre accès."),
        }), 201

    # Sinon (mode souple), on connecte immédiatement comme avant
    token = creer_session(id_user, request.headers.get("User-Agent"))
    reponse = jsonify({
        "id_utilisateur": id_user,
        "role": role,
        "email_envoye": email_parti,
    })
    _poser_cookie(reponse, token)
    return reponse, 201


def _envoyer_email_verification(id_user: int, email: str, prenom: str):
    """Génère un jeton de vérification (24h) et envoie le lien par e-mail.

    Renvoie True si le message est réellement parti. L'inscription ne
    doit pas échouer parce que l'envoi a échoué — mais l'échec ne doit
    pas non plus disparaître : sans trace, un serveur SMTP mal configuré
    se traduit par « je ne reçois pas toujours les e-mails », sans
    aucun moyen de savoir pourquoi.
    """
    import secrets
    from datetime import datetime, timedelta
    from utils.email import envoyer

    jeton = secrets.token_hex(32)
    expire = datetime.utcnow() + timedelta(hours=24)
    try:
        executer(
            """INSERT INTO verification_email
                  (id_jeton, id_utilisateur, expire_le)
               VALUES (%s, %s, %s)""",
            (jeton, id_user, expire),
            commit=True,
        )
        lien = url_publique("/verifier-email.html?jeton=" + jeton)
        parti = envoyer(
            email,
            "Bienvenue sur LaSourcee — confirmez votre adresse",
            f"Bonjour {prenom},\n\n"
            f"Bienvenue sur LaSourcee. Pour activer votre compte,\n"
            f"cliquez sur le lien ci-dessous (valable 24 heures) :\n\n"
            f"{lien}\n\n"
            f"Si vous n'avez pas créé ce compte, ignorez ce message.\n\n"
            f"— L'équipe LaSourcee",
        )
        if not parti:
            logger.error(
                "E-mail de confirmation non envoyé à %s : l'envoi a échoué. "
                "Vérifiez EMAIL_MODE et les paramètres SMTP.", email)
        return bool(parti)
    except Exception as exc:
        logger.error("E-mail de confirmation impossible pour %s : %s",
                     email, exc)
        return False


@bp_auth.post("/connexion")
def connexion():
    d = request.get_json(silent=True) or {}
    email = (d.get("email") or "").strip().lower()
    mdp   = d.get("mot_de_passe") or ""

    if not email or not mdp:
        return _erreur("E-mail et mot de passe requis.")

    # Protection contre la force brute : clé = e-mail + adresse IP
    cle_throttle = f"{email}|{request.remote_addr}"
    reste = est_bloque(cle_throttle)
    if reste:
        minutes = max(1, reste // 60)
        return _erreur(
            f"Trop de tentatives. Réessayez dans environ {minutes} minute(s).",
            429,
        )

    user = recuperer_un(
        """SELECT id_utilisateur, mot_de_passe, role, est_actif,
                  email_verifie, doit_changer_mdp
             FROM utilisateur WHERE email = %s""",
        (email,),
    )
    if not user or not verifier_mot_de_passe(mdp, user["mot_de_passe"]):
        enregistrer_echec(cle_throttle)
        return _erreur("Identifiants incorrects.", 401)
    if not user["est_actif"]:
        return _erreur("Compte désactivé.", 403)
    # Bloquer la connexion si l'e-mail n'est pas vérifié et que c'est requis
    obligatoire = current_app.config["VERIFICATION_EMAIL_OBLIGATOIRE"]
    if obligatoire and not user.get("email_verifie"):
        return _erreur(
            "Adresse e-mail non vérifiée. Consultez votre boîte mail "
            "pour confirmer votre inscription.", 403,
        )

    reinitialiser(cle_throttle)   # connexion réussie : on efface le compteur

    executer(
        "UPDATE utilisateur SET derniere_co = CURRENT_TIMESTAMP WHERE id_utilisateur = %s",
        (user["id_utilisateur"],),
        commit=True,
    )

    token = creer_session(user["id_utilisateur"],
                          request.headers.get("User-Agent"))
    reponse = jsonify({
        "id_utilisateur": user["id_utilisateur"],
        "role": user["role"],
        # Vrai pour un compte créé avec un mot de passe temporaire :
        # l'interface impose alors son changement immédiat.
        "doit_changer_mdp": bool(user.get("doit_changer_mdp")),
    })
    _poser_cookie(reponse, token)
    return reponse


@bp_auth.post("/verifier-email")
def verifier_email():
    """Valide un jeton de vérification d'adresse e-mail."""
    from utils.dates import est_expire
    d = request.get_json(silent=True) or {}
    jeton = (d.get("jeton") or "").strip()
    if len(jeton) != 64:
        return _erreur("Jeton invalide.", 400)

    ligne = recuperer_un(
        """SELECT id_utilisateur, expire_le, verifie_le
             FROM verification_email WHERE id_jeton = %s""",
        (jeton,),
    )
    if not ligne or ligne["verifie_le"]:
        return _erreur("Jeton invalide ou déjà utilisé.", 410)
    if est_expire(ligne["expire_le"]):
        return _erreur("Jeton expiré, demandez un nouveau lien.", 410)

    with curseur(commit=True) as cur:
        cur.execute(
            "UPDATE utilisateur SET email_verifie = 1 WHERE id_utilisateur = %s",
            (ligne["id_utilisateur"],),
        )
        cur.execute(
            "UPDATE verification_email SET verifie_le = CURRENT_TIMESTAMP "
            "WHERE id_jeton = %s",
            (jeton,),
        )
    return jsonify({"ok": True, "message": "Adresse e-mail vérifiée."})


@bp_auth.post("/deconnexion")
def deconnexion():
    detruire_session(jeton_session_courant())
    reponse = make_response(jsonify({"ok": True}))
    return supprimer_cookie_session(reponse)


# --- Réinitialisation de mot de passe ----------------------------------------

@bp_auth.post("/oubli-mdp")
def demander_reinitialisation():
    """Demande de réinitialisation par e-mail.

    Renvoie toujours 200 (même si l'e-mail n'existe pas) pour empêcher
    l'énumération de comptes. Un vrai message est envoyé seulement si
    le compte existe et est actif.
    """
    import secrets
    from datetime import datetime, timedelta
    from utils.email import envoyer

    d = request.get_json(silent=True) or {}
    email = (d.get("email") or "").strip().lower()
    if not REGEX_EMAIL.match(email):
        return jsonify({"ok": True})  # 200 silencieux

    # Sans limitation, cette route permettrait d'inonder la boîte d'un
    # tiers de messages de réinitialisation. La réponse reste identique
    # à celle du cas nominal : révéler le blocage renseignerait sur
    # l'existence du compte.
    cle_debit = f"oubli|{email}|{request.remote_addr}"
    if est_bloque(cle_debit, MAX_DEMANDES_MDP):
        return jsonify({"ok": True})
    enregistrer_echec(cle_debit)

    user = recuperer_un(
        "SELECT id_utilisateur, prenom FROM utilisateur "
        "WHERE email = %s AND est_actif = 1",
        (email,),
    )
    if user:
        jeton = secrets.token_hex(32)
        expire_le = datetime.utcnow() + timedelta(hours=1)
        try:
            executer(
                """INSERT INTO reinitialisation_mdp
                      (id_jeton, id_utilisateur, expire_le, ip_demande)
                   VALUES (%s, %s, %s, %s)""",
                (jeton, user["id_utilisateur"], expire_le,
                 request.remote_addr),
                commit=True,
            )
            lien = url_publique("/reinitialiser.html?jeton=" + jeton)
            envoyer(
                email,
                "Réinitialisation de votre mot de passe LaSourcee",
                f"Bonjour {user['prenom']},\n\n"
                f"Voici votre lien de réinitialisation (valable 1 heure) :\n"
                f"{lien}\n\n"
                f"Si vous n'avez pas demandé cette réinitialisation, "
                f"ignorez ce message.\n\n"
                f"— L'équipe LaSourcee",
            )
        except Exception:
            # On reste silencieux côté client (énumération)
            pass

    return jsonify({"ok": True})


@bp_auth.post("/reinitialiser-mdp")
def reinitialiser_mdp():
    """Définit un nouveau mot de passe à partir d'un jeton valide."""
    from datetime import datetime
    from utils.securite import mot_de_passe_valide

    d = request.get_json(silent=True) or {}
    jeton = (d.get("jeton") or "").strip()
    nouveau = d.get("nouveau_mot_de_passe") or ""

    if not jeton or len(jeton) != 64:
        return _erreur("Jeton invalide.", 400)
    ok, msg = mot_de_passe_valide(nouveau)
    if not ok:
        return _erreur(msg, 400)

    ligne = recuperer_un(
        """SELECT id_utilisateur, expire_le, utilise_le
             FROM reinitialisation_mdp WHERE id_jeton = %s""",
        (jeton,),
    )
    if not ligne or ligne["utilise_le"] is not None:
        return _erreur("Jeton invalide ou déjà utilisé.", 410)
    # SQLite renvoie une chaîne, MySQL un datetime : on normalise.
    from utils.dates import est_expire
    if est_expire(ligne["expire_le"]):
        return _erreur("Jeton expiré, demandez un nouveau lien.", 410)

    hache = hacher_mot_de_passe(nouveau)
    with curseur(commit=True) as cur:
        cur.execute(
            "UPDATE utilisateur SET mot_de_passe = %s WHERE id_utilisateur = %s",
            (hache, ligne["id_utilisateur"]),
        )
        cur.execute(
            "UPDATE reinitialisation_mdp SET utilise_le = CURRENT_TIMESTAMP WHERE id_jeton = %s",
            (jeton,),
        )
        # Invalide toutes les autres sessions actives de l'utilisateur
        cur.execute(
            "DELETE FROM session_web WHERE id_utilisateur = %s",
            (ligne["id_utilisateur"],),
        )
    return jsonify({"ok": True})


# --- Changement de mot de passe (utilisateur connecté) -----------------------

@bp_auth.post("/changer-mdp")
def changer_mdp():
    """Permet à un utilisateur connecté de changer son mot de passe.

    Exige le mot de passe actuel pour éviter le piratage par session
    laissée ouverte.
    """
    from utils.auth_helpers import utilisateur_depuis_jeton
    from utils.securite import mot_de_passe_valide

    user = utilisateur_depuis_jeton(jeton_session_courant())
    if not user:
        return _erreur("Authentification requise.", 401)

    d = request.get_json(silent=True) or {}
    actuel = d.get("mot_de_passe_actuel") or ""
    nouveau = d.get("nouveau_mot_de_passe") or ""

    ligne = recuperer_un(
        "SELECT mot_de_passe FROM utilisateur WHERE id_utilisateur = %s",
        (user["id_utilisateur"],),
    )
    if not ligne or not verifier_mot_de_passe(actuel, ligne["mot_de_passe"]):
        return _erreur("Mot de passe actuel incorrect.", 401)
    ok, msg = mot_de_passe_valide(nouveau)
    if not ok:
        return _erreur(msg, 400)

    nouveau_hache = hacher_mot_de_passe(nouveau)
    # Le changement lève l'obligation posée sur les mots de passe
    # temporaires distribués aux administrateurs.
    executer(
        "UPDATE utilisateur SET mot_de_passe = %s, doit_changer_mdp = 0 "
        "WHERE id_utilisateur = %s",
        (nouveau_hache, user["id_utilisateur"]),
        commit=True,
    )
    return jsonify({"ok": True})


# --- Sessions actives --------------------------------------------------------

@bp_auth.get("/sessions")
@connexion_requise
def lister_sessions():
    """Appareils actuellement connectés au compte.

    Le jeton complet n'est jamais renvoyé : il servirait à usurper la
    session. Seul un identifiant court, suffisant pour la révocation,
    est exposé — et toute action est de toute façon restreinte aux
    sessions du compte appelant.
    """
    courant = jeton_session_courant() or ""
    lignes = recuperer_tous(
        """SELECT id_token, cree_le, expire_le, user_agent
             FROM session_web
            WHERE id_utilisateur = %s
              AND expire_le > CURRENT_TIMESTAMP
         ORDER BY cree_le DESC""",
        (g.utilisateur["id_utilisateur"],),
    )
    return jsonify([{
        "reference": l["id_token"][:16],
        "courante": l["id_token"] == courant,
        "cree_le": l["cree_le"],
        "expire_le": l["expire_le"],
        "appareil": _decrire_appareil(l["user_agent"]),
    } for l in lignes])


@bp_auth.delete("/sessions/<reference>")
@connexion_requise
def revoquer_session(reference):
    """Déconnecte un appareil donné.

    La clause sur ``id_utilisateur`` est ce qui empêche de révoquer la
    session de quelqu'un d'autre en devinant une référence.
    """
    if not re.fullmatch(r"[0-9a-f]{16}", reference or ""):
        return _erreur("Référence de session invalide.", 400)

    lignes = recuperer_tous(
        "SELECT id_token FROM session_web WHERE id_utilisateur = %s",
        (g.utilisateur["id_utilisateur"],),
    )
    cible = next((l["id_token"] for l in lignes
                  if l["id_token"].startswith(reference)), None)
    if cible is None:
        return _erreur("Session introuvable.", 404)

    executer("DELETE FROM session_web WHERE id_token = %s "
             "AND id_utilisateur = %s",
             (cible, g.utilisateur["id_utilisateur"]), commit=True)

    reponse = jsonify({"ok": True,
                       "etait_courante": cible == jeton_session_courant()})
    if cible == jeton_session_courant():
        supprimer_cookie_session(reponse)
    return reponse


@bp_auth.post("/sessions/revoquer-autres")
@connexion_requise
def revoquer_autres_sessions():
    """Déconnecte tous les autres appareils, garde celui en cours."""
    courant = jeton_session_courant() or ""
    nb = executer(
        "DELETE FROM session_web WHERE id_utilisateur = %s AND id_token <> %s",
        (g.utilisateur["id_utilisateur"], courant),
        commit=True,
    )
    return jsonify({"ok": True, "revoquees": max(0, nb or 0)})


def _decrire_appareil(user_agent):
    """Description lisible d'un appareil à partir de son User-Agent.

    Volontairement sommaire : il s'agit d'aider quelqu'un à reconnaître
    ses propres appareils, pas de faire de l'empreinte de navigateur.
    """
    ua = user_agent or ""
    if not ua:
        return "Appareil inconnu"

    navigateur = next(
        (n for m, n in (
            ("Edg/", "Edge"), ("OPR/", "Opera"), ("Chrome/", "Chrome"),
            ("Safari/", "Safari"), ("Firefox/", "Firefox"),
        ) if m in ua),
        "Navigateur",
    )
    systeme = next(
        (s for m, s in (
            ("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"),
            ("Windows", "Windows"), ("Mac OS X", "macOS"), ("Linux", "Linux"),
        ) if m in ua),
        None,
    )
    return f"{navigateur} sur {systeme}" if systeme else navigateur


def _poser_cookie(reponse, token):
    """Délègue à l'implémentation unique (utils/auth_helpers.py) pour que
    tous les points d'entrée — mot de passe, Google, LinkedIn — posent
    exactement le même cookie."""
    return poser_cookie_session(reponse, token)
