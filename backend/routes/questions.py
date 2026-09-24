"""Publication, lecture et tri des questions du fil."""

from flask import Blueprint, g, jsonify, request

from models.db import recuperer_un, recuperer_tous, executer, curseur
from services import evenements
from utils.auth_helpers import connexion_requise
from services.notifications import notifier_reaction, notifier

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

    evenements.depuis_requete("question_publiee", type_cible="question",
                              id_cible=id_q,
                              contexte={"secteur": int(id_sec)})
    return jsonify({"id_question": id_q}), 201


@bp_questions.get("/<int:id_q>")
@connexion_requise
def detail(id_q):
    q = recuperer_un(
        """SELECT q.id_question, q.titre, q.corps, q.publiee_le, q.statut,
                  q.id_auteur, q.id_reponse_retenue, q.resolue_le,
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

    # Une vue par consultation, y compris repetee : distinguer les
    # visiteurs uniques demanderait de garder qui a vu quoi, donc un
    # suivi nominatif de lecture. Le compteur brut suffit a classer les
    # questions par interet, sans cela.
    executer("UPDATE question SET vues = vues + 1 WHERE id_question = %s",
             (id_q,), commit=True)
    evenements.depuis_requete("question_vue", type_cible="question",
                              id_cible=id_q)

    # Les marquages et les notes de la personne connectee voyagent avec
    # la reponse : sans eux l'interface reaffiche un pouce vide et des
    # etoiles vides a chaque rechargement, comme si rien n'avait ete
    # enregistre.
    id_moi = g.utilisateur["id_utilisateur"]
    q["reponses"] = recuperer_tous(
        """SELECT r.id_reponse, r.id_parent_reponse, r.contenu, r.cree_le,
                  u.id_utilisateur, u.prenom, u.nom, u.photo_url, u.role,
                  -- 0 et non FALSE : la colonne est un entier sur les
                  -- trois moteurs, et PostgreSQL refuse de mélanger un
                  -- entier et un booléen dans un COALESCE. Cette route
                  -- répondait donc par une erreur serveur en
                  -- production, ce qui rendait toutes les réponses
                  -- invisibles.
                  COALESCE(md.est_verifie, 0) AS verifie,
                  (SELECT COUNT(*) FROM marquage_reponse m
                     WHERE m.id_reponse = r.id_reponse
                       AND m.type_marquage = 'utile') AS nb_utiles,
                  (SELECT COUNT(*) FROM marquage_reponse m
                     WHERE m.id_reponse = r.id_reponse
                       AND m.type_marquage = 'utile'
                       AND m.id_utilisateur = %s) AS mon_utile,
                  (SELECT COUNT(*) FROM note_reponse n
                     WHERE n.id_reponse = r.id_reponse) AS nb_notes,
                  (SELECT AVG(n.valeur) FROM note_reponse n
                     WHERE n.id_reponse = r.id_reponse) AS note_moyenne,
                  (SELECT n.valeur FROM note_reponse n
                     WHERE n.id_reponse = r.id_reponse
                       AND n.id_utilisateur = %s) AS ma_note
             FROM reponse r
             JOIN utilisateur u ON u.id_utilisateur = r.id_auteur
        LEFT JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
            WHERE r.id_question = %s
         ORDER BY r.cree_le ASC""",
        (id_moi, id_moi, id_q),
    )
    for r in q["reponses"]:
        r["mon_utile"] = bool(r.get("mon_utile"))
        r["note_moyenne"] = round(float(r["note_moyenne"] or 0), 1)
        r["retenue"] = (q.get("id_reponse_retenue") == r["id_reponse"])
        r["sous_reponses"] = []

    # Les reponses a une reponse vivent sous elle plutot qu'en vrac dans
    # la liste : la colonne existait depuis l'origine, mais rien ne
    # l'exploitait, et un echange en trois temps se lisait comme trois
    # reponses independantes a la question de depart.
    racines = [r for r in q["reponses"] if not r.get("id_parent_reponse")]
    par_id = {r["id_reponse"]: r for r in racines}
    for r in q["reponses"]:
        parent = par_id.get(r.get("id_parent_reponse"))
        if parent is not None:
            parent["sous_reponses"].append(r)

    # L'ordre dit ce qui merite d'etre lu en premier : la reponse que
    # l'auteur a retenue, puis celles des referents verifies, puis les
    # plus jugees utiles. Le pur ordre chronologique enterrait la
    # meilleure reponse sous cinq autres des qu'un fil s'animait.
    def _rang(r):
        return (0 if r.get("retenue") else 1,
                0 if r.get("verifie") else 1,
                -(r.get("nb_utiles") or 0),
                -(r.get("note_moyenne") or 0),
                str(r.get("cree_le") or ""))

    q["reponses"] = sorted(racines, key=_rang)

    q["mon_utile"] = bool(recuperer_un(
        """SELECT 1 FROM marquage_question
            WHERE id_question = %s AND id_utilisateur = %s
              AND type_marquage = 'utile'""", (id_q, id_moi)))
    q["sauvegardee"] = bool(recuperer_un(
        "SELECT 1 FROM sauvegarde WHERE id_question = %s AND id_utilisateur = %s",
        (id_q, id_moi)))
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


@bp_questions.post("/<int:id_q>/retenir")
@connexion_requise
def retenir(id_q):
    """L'auteur d'une question désigne la réponse qui l'a aidé.

    Sans cela, dix réponses se valent à l'écran, et celui qui arrive
    plus tard avec la même question doit toutes les lire pour deviner
    laquelle a servi. C'est aussi ce qui permet de dire qu'une question
    est résolue sans demander à personne de le déclarer.

    Le choix appartient à l'auteur, et à lui seul : un administrateur
    qui trancherait à sa place déciderait de ce qui l'a aidé.
    """
    q = recuperer_un(
        "SELECT id_auteur, id_reponse_retenue FROM question "
        "WHERE id_question = %s", (id_q,))
    if not q:
        return jsonify({"erreur": "Question introuvable."}), 404
    if q["id_auteur"] != g.utilisateur["id_utilisateur"]:
        return jsonify({"erreur": "Seul l'auteur de la question choisit la "
                                  "réponse qui l'a aidé."}), 403

    d = request.get_json(silent=True) or {}
    id_r = d.get("id_reponse")
    if id_r is None:
        return jsonify({"erreur": "id_reponse requis."}), 400
    try:
        id_r = int(id_r)
    except (TypeError, ValueError):
        return jsonify({"erreur": "id_reponse invalide."}), 400

    reponse = recuperer_un(
        "SELECT id_question, id_auteur FROM reponse WHERE id_reponse = %s",
        (id_r,))
    if not reponse or reponse["id_question"] != id_q:
        return jsonify({"erreur": "Cette réponse n'est pas sur cette "
                                  "question."}), 400

    # Un second appel sur la meme reponse annule le choix : se tromper
    # doit se corriger sans passer par l'administration.
    if q.get("id_reponse_retenue") == id_r:
        executer("UPDATE question SET id_reponse_retenue = NULL, "
                 "statut = 'ouverte', resolue_le = NULL "
                 "WHERE id_question = %s", (id_q,), commit=True)
        return jsonify({"retenue": None, "statut": "ouverte"})

    executer(
        """UPDATE question
              SET id_reponse_retenue = %s, statut = 'resolue',
                  resolue_le = CURRENT_TIMESTAMP
            WHERE id_question = %s""",
        (id_r, id_q), commit=True)

    if reponse["id_auteur"] != g.utilisateur["id_utilisateur"]:
        notifier(reponse["id_auteur"],
                 "Votre réponse a été retenue comme celle qui a aidé.",
                 type_notif="reaction", id_question=id_q)
    evenements.depuis_requete("reponse_retenue", type_cible="question",
                              id_cible=id_q, contexte={"reponse": id_r})
    return jsonify({"retenue": id_r, "statut": "resolue"})


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
        notifier_reaction(
            id_q, id_user,
            f"{g.utilisateur.get('prenom', '')} "
            f"{(g.utilisateur.get('nom') or '')[:1]}.".strip())
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
    if marque:
        evenements.depuis_requete("question_utile", type_cible="question",
                                  id_cible=id_q)
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
    """Signale une question à la modération, une fois par personne.

    Rien n'empêchait de signaler douze fois la même question : l'écran
    de modération montrait alors douze signalements et concluait à un
    problème collectif, alors qu'une seule personne était en cause.
    C'est exactement ce qui transforme un outil de modération en arme.
    """
    if not recuperer_un("SELECT 1 FROM question WHERE id_question = %s",
                        (id_q,)):
        return jsonify({"erreur": "Question introuvable."}), 404

    d = request.get_json(silent=True) or {}
    motif = (d.get("motif") or "Signalé sans motif précisé").strip()[:300]
    id_user = g.utilisateur["id_utilisateur"]

    deja = recuperer_un(
        """SELECT id_signalement FROM signalement
            WHERE id_signaleur = %s AND type_contenu = 'question'
              AND id_contenu = %s""",
        (id_user, id_q))
    if deja:
        # Le motif est mis a jour : quelqu'un qui precise sa pensee ne
        # doit pas avoir a creer un second signalement pour le faire.
        executer("UPDATE signalement SET motif = %s WHERE id_signalement = %s",
                 (motif, deja["id_signalement"]), commit=True)
        return jsonify({"ok": True, "deja_signale": True,
                        "message": "Vous aviez déjà signalé cette question. "
                                   "Votre motif a été mis à jour."})

    executer(
        """INSERT INTO signalement
              (id_signaleur, type_contenu, id_contenu, motif)
           VALUES (%s, 'question', %s, %s)""",
        (id_user, id_q, motif),
        commit=True,
    )
    # Le motif n'est pas recopie ici : il est ecrit par un membre, et le
    # journal d'activite ne garde aucun texte. Seul compte le fait qu'un
    # signalement a eu lieu, et sur quoi.
    evenements.depuis_requete("signalement", type_cible="question",
                              id_cible=id_q)
    return jsonify({"ok": True})


@bp_questions.get("/vedette")
def vedette():
    """Quelques questions pour la page d'accueil, sans authentification.

    Le fil complet reste réservé aux membres ; cette route n'expose que
    ce que la page d'accueil affiche déjà : un titre, l'auteur et le
    nombre de réponses. Le nom de famille est réduit à son initiale —
    montrer une identité complète à un visiteur anonyme n'apporterait
    rien et exposerait les membres.

    Les questions les plus commentées d'abord : ce sont celles qui
    montrent le mieux ce que la plateforme apporte.
    """
    lignes = recuperer_tous(
        """SELECT q.id_question, q.titre, u.prenom, u.nom,
                  (SELECT COUNT(*) FROM reponse r
                    WHERE r.id_question = q.id_question) AS nb_reponses
             FROM question q
             JOIN utilisateur u ON u.id_utilisateur = q.id_auteur
            WHERE u.est_actif = 1
         ORDER BY nb_reponses DESC, q.publiee_le DESC
            LIMIT 3"""
    )
    return jsonify([{
        "id_question": l["id_question"],
        "titre": l["titre"],
        "auteur": (l["prenom"] or "").strip()
                  + ((" " + l["nom"].strip()[0] + ".") if l.get("nom") else ""),
        "nb_reponses": l["nb_reponses"] or 0,
    } for l in lignes])
