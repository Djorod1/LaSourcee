"""Annuaire des référents et dépôt de candidature."""

from flask import Blueprint, g, jsonify, request

from models.db import recuperer_un, recuperer_tous, executer
from utils.auth_helpers import connexion_requise

bp_mentors = Blueprint("mentors", __name__, url_prefix="/api/mentors")


@bp_mentors.get("")
@connexion_requise
def lister():
    """Annuaire des mentors avec filtres par secteur, pays, disponibilité."""
    id_sec = request.args.get("id_secteur", type=int)
    id_pays = request.args.get("id_pays", type=int)
    dispo = request.args.get("dispo")
    terme = (request.args.get("q") or "").strip()
    limite = min(request.args.get("limite", default=30, type=int), 100)

    # md.est_verifie s'ajoute au rôle plutôt que de s'y substituer.
    # L'annuaire est ce qu'un bénéficiaire consulte pour choisir à qui
    # confier une question : n'y faire figurer que des dossiers examinés
    # est le minimum. La condition tient même si un rôle était accordé
    # par erreur ailleurs dans le code.
    conditions = ["u.role = 'mentor'", "u.est_actif = 1", "md.est_verifie = 1"]
    params = []
    if id_pays:
        conditions.append("u.id_pays = %s")
        params.append(id_pays)
    if dispo in ("disponible", "occupe", "absent"):
        conditions.append("md.dispo = %s")
        params.append(dispo)
    if terme:
        conditions.append("(u.prenom LIKE %s OR u.nom LIKE %s OR u.bio LIKE %s)")
        params.extend([f"%{terme}%", f"%{terme}%", f"%{terme}%"])
    if id_sec:
        conditions.append(
            """EXISTS (SELECT 1 FROM utilisateur_secteur us
                        WHERE us.id_utilisateur = u.id_utilisateur
                          AND us.id_secteur = %s)"""
        )
        params.append(id_sec)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT u.id_utilisateur, u.prenom, u.nom, u.photo_url, u.bio,
               u.ville, p.libelle AS pays,
               md.est_verifie, md.dispo, md.anciennete,
               md.note_moyenne, md.nb_reponses
          FROM utilisateur u
          JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
     LEFT JOIN pays p ON p.id_pays = u.id_pays
         WHERE {where}
      ORDER BY md.est_verifie DESC, md.note_moyenne DESC, md.nb_reponses DESC
         LIMIT %s
    """
    params.append(limite)
    mentors = recuperer_tous(sql, params)

    if mentors:
        ids = [m["id_utilisateur"] for m in mentors]
        placeholders = ", ".join(["%s"] * len(ids))
        liens = recuperer_tous(
            f"""SELECT us.id_utilisateur, s.id_secteur, s.libelle, s.couleur
                  FROM utilisateur_secteur us
                  JOIN secteur s ON s.id_secteur = us.id_secteur
                 WHERE us.id_utilisateur IN ({placeholders})""",
            ids,
        )
        groupes = {}
        for l in liens:
            groupes.setdefault(l["id_utilisateur"], []).append({
                "id_secteur": l["id_secteur"],
                "libelle": l["libelle"],
                "couleur": l["couleur"],
            })
        for m in mentors:
            m["secteurs"] = groupes.get(m["id_utilisateur"], [])
    return jsonify(mentors)
