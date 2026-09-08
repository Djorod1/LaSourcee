"""Messagerie privée entre utilisateurs."""

from datetime import datetime

from flask import Blueprint, g, jsonify, request

from models.db import recuperer_un, recuperer_tous, executer, curseur
from utils.auth_helpers import connexion_requise

bp_messagerie = Blueprint("messagerie", __name__, url_prefix="/api/messagerie")


@bp_messagerie.get("/conversations")
@connexion_requise
def lister_conversations():
    id_user = g.utilisateur["id_utilisateur"]
    return jsonify(recuperer_tous(
        """SELECT c.id_conversation, c.dernier_msg_le,
                  autre.id_utilisateur AS id_autre,
                  autre.prenom, autre.nom, autre.photo_url, autre.role,
                  (SELECT contenu FROM message
                     WHERE id_conversation = c.id_conversation
                     ORDER BY envoye_le DESC LIMIT 1) AS dernier_contenu,
                  (SELECT COUNT(*) FROM message m
                     WHERE m.id_conversation = c.id_conversation
                       AND m.id_expediteur <> %s
                       AND (cp_moi.lu_jusqua IS NULL
                            OR m.envoye_le > cp_moi.lu_jusqua)) AS non_lus
             FROM conversation c
             JOIN conversation_participant cp_moi
               ON cp_moi.id_conversation = c.id_conversation
              AND cp_moi.id_utilisateur = %s
             JOIN conversation_participant cp_autre
               ON cp_autre.id_conversation = c.id_conversation
              AND cp_autre.id_utilisateur <> %s
             JOIN utilisateur autre
               ON autre.id_utilisateur = cp_autre.id_utilisateur
         ORDER BY COALESCE(c.dernier_msg_le, c.cree_le) DESC""",
        (id_user, id_user, id_user),
    ))


@bp_messagerie.post("/conversations")
@connexion_requise
def ouvrir():
    d = request.get_json(silent=True) or {}
    id_autre = d.get("id_utilisateur")
    if not id_autre:
        return jsonify({"erreur": "Destinataire requis."}), 400

    id_moi = g.utilisateur["id_utilisateur"]
    if id_autre == id_moi:
        return jsonify({"erreur": "Conversation avec soi-même impossible."}), 400

    autre = recuperer_un(
        "SELECT id_utilisateur FROM utilisateur "
        "WHERE id_utilisateur = %s AND est_actif = 1",
        (id_autre,),
    )
    if not autre:
        return jsonify({"erreur": "Destinataire introuvable."}), 404

    existante = recuperer_un(
        """SELECT cp1.id_conversation
             FROM conversation_participant cp1
             JOIN conversation_participant cp2
               ON cp1.id_conversation = cp2.id_conversation
            WHERE cp1.id_utilisateur = %s AND cp2.id_utilisateur = %s
            LIMIT 1""",
        (id_moi, id_autre),
    )
    if existante:
        return jsonify({"id_conversation": existante["id_conversation"]})

    with curseur(commit=True) as cur:
        cur.execute("INSERT INTO conversation DEFAULT VALUES")
        id_conv = cur.lastrowid
        cur.executemany(
            """INSERT INTO conversation_participant
                  (id_conversation, id_utilisateur) VALUES (%s, %s)""",
            [(id_conv, id_moi), (id_conv, id_autre)],
        )
    return jsonify({"id_conversation": id_conv}), 201


@bp_messagerie.get("/conversations/<int:id_conv>/messages")
@connexion_requise
def lire(id_conv):
    id_user = g.utilisateur["id_utilisateur"]
    if not _participe(id_user, id_conv):
        return jsonify({"erreur": "Accès refusé."}), 403

    messages = recuperer_tous(
        """SELECT id_message, id_expediteur, contenu, envoye_le
             FROM message
            WHERE id_conversation = %s
         ORDER BY envoye_le ASC""",
        (id_conv,),
    )
    executer(
        """UPDATE conversation_participant
              SET lu_jusqua = %s
            WHERE id_conversation = %s AND id_utilisateur = %s""",
        (datetime.utcnow(), id_conv, id_user), commit=True,
    )
    return jsonify(messages)


@bp_messagerie.post("/conversations/<int:id_conv>/messages")
@connexion_requise
def envoyer(id_conv):
    d = request.get_json(silent=True) or {}
    contenu = (d.get("contenu") or "").strip()
    if not contenu:
        return jsonify({"erreur": "Message vide."}), 400
    if len(contenu) > 4000:
        return jsonify({"erreur": "Message trop long (max 4000)."}), 400

    id_user = g.utilisateur["id_utilisateur"]
    if not _participe(id_user, id_conv):
        return jsonify({"erreur": "Accès refusé."}), 403

    with curseur(commit=True) as cur:
        cur.execute(
            """INSERT INTO message (id_conversation, id_expediteur, contenu)
               VALUES (%s, %s, %s)""",
            (id_conv, id_user, contenu),
        )
        id_msg = cur.lastrowid
        cur.execute(
            """UPDATE conversation SET dernier_msg_le = CURRENT_TIMESTAMP
                WHERE id_conversation = %s""",
            (id_conv,),
        )

    return jsonify(recuperer_un(
        "SELECT id_message, id_expediteur, contenu, envoye_le "
        "FROM message WHERE id_message = %s",
        (id_msg,),
    )), 201


def _participe(id_user, id_conv):
    return recuperer_un(
        """SELECT 1 FROM conversation_participant
            WHERE id_conversation = %s AND id_utilisateur = %s""",
        (id_conv, id_user),
    ) is not None
