"""Publication, lecture et tri des questions du fil."""

from flask import Blueprint, g, jsonify, request

from models.db import recuperer_un, recuperer_tous, executer, curseur
from utils.auth_helpers import connexion_requise

bp_questions = Blueprint("questions", __name__, url_prefix="/api/questions")

TRIS_AUTORISES = {"recent", "populaire", "sansrep"}


@bp_questions.get("")
@connexion_requise
def lister():
    tri        = request.args.get("tri", "recent")
    id_secteur = request.args.get("id_secteur", type=int)
    id_pays    = request.args.get("id_pays", type=int)
    terme      = (request.args.get("q") or "").strip()
    limite     = min(request.args.get("limite", default=30, type=int), 100)

    if tri not in TRIS_AUTORISES:
        tri = "recent"

    conditions = []
    params = []
    if id_secteur:
        conditions.append("q.id_secteur = %s")
        params.append(id_secteur)
    if id_pays:
        conditions.append("u.id_pays = %s")
        params.append(id_pays)
    if terme:
        conditions.append("(q.titre LIKE %s OR q.corps LIKE %s)")
        params.extend([f"%{terme}%", f"%{terme}%"])
    if tri == "sansrep":
        conditions.append(
            "NOT EXISTS (SELECT 1 FROM reponse r WHERE r.id_question = q.id_question)"
        )

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    if tri == "populaire":
        ordre = """ORDER BY (SELECT COUNT(*) FROM marquage_question m
                              WHERE m.id_question = q.id_question
                                AND m.type_marquage = 'utile') DESC,
                            q.publiee_le DESC"""
    else:
        ordre = "ORDER BY q.publiee_le DESC"

    sql = f"""
        SELECT q.id_question, q.titre, q.corps, q.publiee_le,
               s.id_secteur, s.libelle  AS secteur, s.couleur,
               u.id_utilisateur, u.prenom, u.nom, u.photo_url,
               p.libelle AS pays,
               (SELECT COUNT(*) FROM reponse r
                  WHERE r.id_question = q.id_question)        AS nb_reponses,
               (SELECT COUNT(*) FROM marquage_question m
                  WHERE m.id_question = q.id_question
                    AND m.type_marquage = 'utile')            AS nb_utiles
          FROM question q
          JOIN utilisateur u ON u.id_utilisateur = q.id_auteur
     LEFT JOIN secteur s     ON s.id_secteur = q.id_secteur
     LEFT JOIN pays p        ON p.id_pays = u.id_pays
        {where}
        {ordre}
        LIMIT %s
    """
    params.append(limite)
    return jsonify(recuperer_tous(sql, params))


@bp_questions.post("")
@connexion_requise
def publier():
    d = request.get_json(silent=True) or {}
    titre  = (d.get("titre") or "").strip()
    corps  = (d.get("corps") or "").strip()
    id_sec = d.get("id_secteur")

    if not titre:
        return jsonify({"erreur": "Titre requis."}), 400
    if len(titre) > 200:
        return jsonify({"erreur": "Titre trop long (max 200)."}), 400
    if not corps:
        return jsonify({"erreur": "Corps de question requis."}), 400
    if not id_sec:
        return jsonify({"erreur": "Catégorie obligatoire."}), 400

    with curseur(commit=True) as cur:
        cur.execute(
            """INSERT INTO question (id_auteur, titre, corps, id_secteur)
               VALUES (%s, %s, %s, %s)""",
            (g.utilisateur["id_utilisateur"], titre, corps, int(id_sec)),
        )
        id_q = cur.lastrowid

    return jsonify({"id_question": id_q}), 201


@bp_questions.get("/<int:id_q>")
@connexion_requise
def detail(id_q):
    q = recuperer_un(
        """SELECT q.id_question, q.titre, q.corps, q.publiee_le, q.statut,
                  s.id_secteur, s.libelle AS secteur, s.couleur,
                  u.id_utilisateur, u.prenom, u.nom, u.photo_url,
                  p.libelle AS pays,
                  (SELECT COUNT(*) FROM marquage_question m
                     WHERE m.id_question = q.id_question
                       AND m.type_marquage = 'utile') AS nb_utiles
             FROM question q
             JOIN utilisateur u ON u.id_utilisateur = q.id_auteur
        LEFT JOIN secteur s     ON s.id_secteur = q.id_secteur
        LEFT JOIN pays p        ON p.id_pays = u.id_pays
            WHERE q.id_question = %s""",
        (id_q,),
    )
    if not q:
        return jsonify({"erreur": "Question introuvable."}), 404

    q["reponses"] = recuperer_tous(
        """SELECT r.id_reponse, r.id_parent_reponse, r.contenu,
                  r.note_etoiles, r.cree_le,
                  u.id_utilisateur, u.prenom, u.nom, u.photo_url, u.role,
                  COALESCE(md.est_verifie, FALSE) AS verifie,
                  (SELECT COUNT(*) FROM marquage_reponse m
                     WHERE m.id_reponse = r.id_reponse
                       AND m.type_marquage = 'utile') AS nb_utiles
             FROM reponse r
             JOIN utilisateur u ON u.id_utilisateur = r.id_auteur
        LEFT JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
            WHERE r.id_question = %s
         ORDER BY r.cree_le ASC""",
        (id_q,),
    )
    return jsonify(q)


@bp_questions.delete("/<int:id_q>")
@connexion_requise
def supprimer(id_q):
    q = recuperer_un("SELECT id_auteur FROM question WHERE id_question = %s",
                     (id_q,))
    if not q:
        return jsonify({"erreur": "Question introuvable."}), 404
    if q["id_auteur"] != g.utilisateur["id_utilisateur"] \
            and not g.utilisateur.get("est_admin"):
        return jsonify({"erreur": "Action non autorisée."}), 403
    executer("DELETE FROM question WHERE id_question = %s",
             (id_q,), commit=True)
    return jsonify({"ok": True})


# ---------- Marquages : utile / aimé ----------

@bp_questions.post("/<int:id_q>/utile")
@connexion_requise
def basculer_utile(id_q):
    id_user = g.utilisateur["id_utilisateur"]
    deja = recuperer_un(
        """SELECT 1 FROM marquage_question
            WHERE id_question = %s AND id_utilisateur = %s
              AND type_marquage = 'utile'""",
        (id_q, id_user),
    )
    if deja:
        executer(
            """DELETE FROM marquage_question
                WHERE id_question = %s AND id_utilisateur = %s
                  AND type_marquage = 'utile'""",
            (id_q, id_user), commit=True,
        )
        marque = False
    else:
        executer(
            """INSERT INTO marquage_question
                  (id_question, id_utilisateur, type_marquage)
               VALUES (%s, %s, 'utile')""",
            (id_q, id_user), commit=True,
        )
        marque = True

    total = recuperer_un(
        """SELECT COUNT(*) AS n FROM marquage_question
            WHERE id_question = %s AND type_marquage = 'utile'""",
        (id_q,),
    )
    return jsonify({"marque": marque, "nb_utiles": total["n"]})


# ---------- Sauvegardes ----------

@bp_questions.post("/<int:id_q>/sauvegarder")
@connexion_requise
def basculer_sauver(id_q):
    id_user = g.utilisateur["id_utilisateur"]
    deja = recuperer_un(
        """SELECT 1 FROM sauvegarde
            WHERE id_question = %s AND id_utilisateur = %s""",
        (id_q, id_user),
    )
    if deja:
        executer(
            """DELETE FROM sauvegarde
                WHERE id_question = %s AND id_utilisateur = %s""",
            (id_q, id_user), commit=True,
        )
        return jsonify({"sauvegardee": False})
    executer(
        "INSERT INTO sauvegarde (id_utilisateur, id_question) VALUES (%s, %s)",
        (id_user, id_q), commit=True,
    )
    return jsonify({"sauvegardee": True})


# ---------- Signalement ----------

@bp_questions.post("/<int:id_q>/signaler")
@connexion_requise
def signaler(id_q):
    d = request.get_json(silent=True) or {}
    motif = (d.get("motif") or "Signalé sans motif précisé").strip()[:300]
    executer(
        """INSERT INTO signalement
              (id_signaleur, type_contenu, id_contenu, motif)
           VALUES (%s, 'question', %s, %s)""",
        (g.utilisateur["id_utilisateur"], id_q, motif),
        commit=True,
    )
    return jsonify({"ok": True})
