"""Lecture et marquage comme lu des notifications."""

from flask import Blueprint, g, jsonify

from models.db import recuperer_tous, executer
from utils.auth_helpers import connexion_requise

bp_notifications = Blueprint("notifications", __name__,
                             url_prefix="/api/notifications")


@bp_notifications.get("")
@connexion_requise
def lister():
    return jsonify(recuperer_tous(
        """SELECT id_notification, texte, lien_question, type_notif,
                  est_lue, cree_le
             FROM notification
            WHERE id_destinataire = %s
         ORDER BY cree_le DESC
            LIMIT 50""",
        (g.utilisateur["id_utilisateur"],),
    ))


@bp_notifications.post("/tout-lu")
@connexion_requise
def tout_marquer_lu():
    executer(
        """UPDATE notification SET est_lue = 1
            WHERE id_destinataire = %s AND est_lue = 0""",
        (g.utilisateur["id_utilisateur"],),
        commit=True,
    )
    return jsonify({"ok": True})


@bp_notifications.get("/non-lues")
@connexion_requise
def compter_non_lues():
    lignes = recuperer_tous(
        """SELECT COUNT(*) AS n FROM notification
            WHERE id_destinataire = %s AND est_lue = 0""",
        (g.utilisateur["id_utilisateur"],),
    )
    return jsonify({"non_lues": lignes[0]["n"] if lignes else 0})
