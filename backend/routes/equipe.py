"""Messages adressés à l'équipe de LaSourcee.

Les membres n'avaient aucun endroit où dire qu'une page ne marchait
pas, qu'un libellé prêtait à confusion, ou simplement qu'ils auraient
aimé autre chose. Un problème qu'on ne peut pas signaler ne disparaît
pas : il fait partir la personne, et l'équipe ne sait jamais pourquoi.

Trois choix guident ce module :

  - **on n'exige pas de compte.** Quelqu'un qui n'arrive pas à se
    connecter est précisément celui qui a le plus besoin d'écrire ;
  - **le contexte technique part avec le message.** La page d'où l'on
    écrit et le navigateur utilisé évitent l'aller-retour « sur quelle
    page ? », qui décourage la moitié des signalements ;
  - **on répond.** Un message sans accusé de réception ne se renvoie
    pas, il s'oublie, et la personne conclut que personne ne lit.
"""

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from models.db import recuperer_un, recuperer_tous, executer, curseur
from services import evenements
from services.notifications import notifier
from utils.auth_helpers import jeton_session_courant, utilisateur_depuis_jeton
from utils.audit import journaliser
from utils.noms import normaliser_nom
from utils.permissions import permission_requise
from utils.securite import est_bloque, enregistrer_echec

logger = logging.getLogger("lasourcee.equipe")

bp_equipe = Blueprint("equipe", __name__, url_prefix="/api/equipe")

# Ce qu'on peut signaler. La liste est courte exprès : un menu de
# quinze rubriques fait choisir « autre » à tout le monde.
CATEGORIES = {
    "panne": "Quelque chose ne marche pas",
    "erreur": "Une information est fausse ou mal écrite",
    "suggestion": "Une idée pour améliorer LaSourcee",
    "compte": "Un problème avec mon compte",
    "signalement": "Un comportement ou un contenu déplacé",
    "autre": "Autre chose",
}

STATUTS = ("nouveau", "en_cours", "traite")

LONGUEUR_MESSAGE_MIN = 10
LONGUEUR_MESSAGE_MAX = 4000
MAX_MESSAGES = 5          # par fenêtre de limitation, et par adresse IP


@bp_equipe.get("/categories")
def categories():
    """Rubriques proposées, servies par le serveur.

    La liste affichée et la liste acceptée ne peuvent ainsi pas
    diverger, ce qui arrivait chaque fois qu'on en ajoutait une.
    """
    return jsonify({"categories": [{"cle": c, "libelle": l}
                                   for c, l in CATEGORIES.items()]})


@bp_equipe.post("/message")
def ecrire():
    # Un formulaire ouvert sans compte est un formulaire ouvert aux
    # robots. La limitation vaut par adresse, pas par personne.
    cle = f"equipe|{request.remote_addr}"
    reste = est_bloque(cle, MAX_MESSAGES)
    if reste:
        return jsonify({"erreur":
            "Vous avez déjà envoyé plusieurs messages. Laissez-nous le "
            f"temps de les lire : réessayez dans {max(1, reste // 60)} "
            "minute(s)."}), 429

    d = request.get_json(silent=True) or {}
    message = (d.get("message") or "").strip()
    categorie = d.get("categorie") if d.get("categorie") in CATEGORIES \
        else "autre"

    if len(message) < LONGUEUR_MESSAGE_MIN:
        return jsonify({"erreur":
            "Décrivez ce que vous avez constaté en quelques mots."}), 400
    if len(message) > LONGUEUR_MESSAGE_MAX:
        return jsonify({"erreur":
            f"Message trop long (maximum {LONGUEUR_MESSAGE_MAX} "
            "caractères)."}), 400

    # Une session peut exister ou non : c'est une route ouverte.
    jeton = jeton_session_courant()
    moi = utilisateur_depuis_jeton(jeton) if jeton else None
    if moi:
        id_user = moi["id_utilisateur"]
        nom = f"{moi.get('prenom') or ''} {moi.get('nom') or ''}".strip()
        email = moi.get("email")
    else:
        id_user = None
        nom = normaliser_nom(d.get("nom")) or ""
        email = (d.get("email") or "").strip().lower()[:160]
        if not email:
            return jsonify({"erreur":
                "Laissez une adresse e-mail pour qu'on puisse vous "
                "répondre, ou connectez-vous."}), 400

    with curseur(commit=True) as cur:
        cur.execute(
            """INSERT INTO message_equipe
                  (id_utilisateur, nom, email, categorie, message,
                   page, navigateur)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (id_user, nom[:120] or None, email or None, categorie, message,
             (d.get("page") or "")[:200] or None,
             (request.headers.get("User-Agent") or "")[:200] or None),
        )
        id_message = cur.lastrowid

    enregistrer_echec(cle)   # ici : compte l'envoi, pas un échec
    evenements.depuis_requete("message_equipe", type_cible="message",
                              id_cible=id_message,
                              contexte={"categorie": categorie})
    _prevenir_equipe(categorie, nom)

    return jsonify({
        "id_message": id_message,
        "message": "Votre message est arrivé. L'équipe le lit et vous "
                   "répond à l'adresse indiquée.",
    }), 201


def _prevenir_equipe(categorie, nom):
    """Notifie dans l'application les comptes qui suivent l'assistance.

    L'e-mail peut être hors service sans que personne s'en aperçoive :
    c'est exactement la panne qu'un membre viendrait signaler ici.
    """
    try:
        destinataires = recuperer_tous(
            "SELECT id_utilisateur, role, permissions FROM utilisateur "
            "WHERE est_admin = 1 AND est_actif = 1")
    except Exception as exc:              # pragma: no cover - dépend du schéma
        logger.warning("Notification d'assistance impossible : %s", exc)
        return
    from utils.permissions import a_le_droit
    libelle = CATEGORIES.get(categorie, "Autre chose")
    qui = nom or "Quelqu'un"
    for compte in destinataires:
        compte["est_admin"] = 1
        if not a_le_droit(compte, "assistance"):
            continue
        notifier(compte["id_utilisateur"],
                 f"{qui} a écrit à l'équipe : {libelle.lower()}.",
                 type_notif="systeme")


# ---------------------------------------------------------------------
# Côté administration
# ---------------------------------------------------------------------

@bp_equipe.get("/messages")
@permission_requise("assistance")
def lister():
    statut = request.args.get("statut")
    conditions, params = [], []
    if statut in STATUTS:
        conditions.append("m.statut = %s")
        params.append(statut)
    filtre = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    lignes = recuperer_tous(
        f"""SELECT m.id_message, m.categorie, m.message, m.page,
                   m.navigateur, m.statut, m.reponse, m.traite_le,
                   m.cree_le, m.nom, m.email, m.id_utilisateur,
                   u.prenom, u.nom AS nom_compte, u.role, u.photo_url,
                   t.prenom AS traite_prenom, t.nom AS traite_nom
              FROM message_equipe m
         LEFT JOIN utilisateur u ON u.id_utilisateur = m.id_utilisateur
         LEFT JOIN utilisateur t ON t.id_utilisateur = m.traite_par
            {filtre}
          ORDER BY CASE m.statut WHEN 'nouveau' THEN 0
                                 WHEN 'en_cours' THEN 1 ELSE 2 END,
                   m.cree_le DESC
             LIMIT 200""",
        tuple(params))
    for ligne in lignes:
        ligne["categorie_libelle"] = CATEGORIES.get(ligne["categorie"],
                                                    "Autre chose")
    compte = recuperer_un(
        "SELECT COUNT(*) AS n FROM message_equipe WHERE statut = 'nouveau'")
    return jsonify({"messages": lignes,
                    "nouveaux": (compte or {}).get("n", 0),
                    "categories": CATEGORIES})


@bp_equipe.post("/messages/<int:id_message>/traiter")
@permission_requise("assistance")
def traiter(id_message):
    d = request.get_json(silent=True) or {}
    statut = d.get("statut")
    if statut not in STATUTS:
        return jsonify({"erreur": "Statut inconnu."}), 400

    ligne = recuperer_un(
        "SELECT id_utilisateur FROM message_equipe WHERE id_message = %s",
        (id_message,))
    if not ligne:
        return jsonify({"erreur": "Message introuvable."}), 404

    reponse = (d.get("reponse") or "").strip()[:LONGUEUR_MESSAGE_MAX]
    executer(
        """UPDATE message_equipe
              SET statut = %s, reponse = %s, traite_par = %s, traite_le = %s
            WHERE id_message = %s""",
        (statut, reponse or None, g.utilisateur["id_utilisateur"],
         datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), id_message),
        commit=True)

    journaliser(g.utilisateur["id_utilisateur"], "message_equipe_" + statut,
                "message", id_message, (reponse or "")[:200] or None)

    # La personne qui a écrit doit savoir que quelqu'un a lu. Sans
    # cela, on écrit une fois et on n'écrit plus jamais.
    if reponse and ligne.get("id_utilisateur"):
        notifier(ligne["id_utilisateur"],
                 "L'équipe de LaSourcee a répondu à votre message : "
                 + reponse[:180],
                 type_notif="systeme")
    return jsonify({"ok": True, "statut": statut})
