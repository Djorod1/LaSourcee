"""Recherche globale : mentors + questions + secteurs."""

from flask import Blueprint, jsonify, request

from models.db import recuperer_tous
from utils.auth_helpers import connexion_requise

bp_recherche = Blueprint("recherche", __name__, url_prefix="/api/recherche")


@bp_recherche.get("")
@connexion_requise
def globale():
    terme = (request.args.get("q") or "").strip()
    if len(terme) < 2:
        return jsonify({"mentors": [], "questions": [], "secteurs": []})

    motif = f"%{terme}%"

    mentors = recuperer_tous(
        """SELECT u.id_utilisateur, u.prenom, u.nom, u.photo_url
             FROM utilisateur u
             JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
            WHERE u.role = 'mentor' AND u.est_actif = 1
              AND (u.prenom LIKE %s OR u.nom LIKE %s OR u.bio LIKE %s)
         ORDER BY md.est_verifie DESC, md.note_moyenne DESC
            LIMIT 8""",
        (motif, motif, motif),
    )

    questions = recuperer_tous(
        """SELECT id_question, titre
             FROM question
            WHERE titre LIKE %s OR corps LIKE %s
         ORDER BY publiee_le DESC
            LIMIT 8""",
        (motif, motif),
    )

    secteurs = recuperer_tous(
        """SELECT id_secteur, libelle, couleur FROM secteur
            WHERE libelle LIKE %s ORDER BY libelle LIMIT 8""",
        (motif,),
    )

    return jsonify({
        "mentors": mentors,
        "questions": questions,
        "secteurs": secteurs,
    })
