"""Réponses et sous-réponses aux questions."""

from flask import Blueprint, g, jsonify, request

from models.db import recuperer_un, executer, curseur
from services import evenements
from utils.auth_helpers import connexion_requise
from services.notifications import notifier_reponse

bp_reponses = Blueprint("reponses", __name__, url_prefix="/api/reponses")


@bp_reponses.post("")
@connexion_requise
def publier():
    d = request.get_json(silent=True) or {}
    id_q       = d.get("id_question")
    id_parent  = d.get("id_parent_reponse")
    contenu    = (d.get("contenu") or "").strip()
    etoiles    = d.get("note_etoiles")

    if not id_q:
        return jsonify({"erreur": "id_question requis."}), 400
    if not contenu:
        return jsonify({"erreur": "Contenu requis."}), 400
    if len(contenu) > 4000:
        return jsonify({"erreur": "Réponse trop longue (max 4000)."}), 400
    if etoiles is not None:
        try:
            etoiles = int(etoiles)
            if etoiles < 1 or etoiles > 5:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"erreur": "Étoiles : entier de 1 à 5."}), 400

    question = recuperer_un(
        "SELECT 1 FROM question WHERE id_question = %s",
        (id_q,),
    )
    if not question:
        return jsonify({"erreur": "Question introuvable."}), 404

    if id_parent is not None:
        parent = recuperer_un(
            "SELECT id_question FROM reponse WHERE id_reponse = %s",
            (id_parent,),
        )
        if not parent or parent["id_question"] != int(id_q):
            return jsonify({"erreur": "Réponse parent invalide."}), 400

    with curseur(commit=True) as cur:
        cur.execute(
            """INSERT INTO reponse
                  (id_question, id_auteur, id_parent_reponse,
                   contenu, note_etoiles)
               VALUES (%s, %s, %s, %s, %s)""",
            (int(id_q), g.utilisateur["id_utilisateur"],
             int(id_parent) if id_parent else None,
             contenu, etoiles),
        )
        id_r = cur.lastrowid

        # Recalcul léger : si l'auteur est mentor, incrémenter son compteur.
        if g.utilisateur["role"] == "mentor":
            cur.execute(
                """UPDATE mentor_details
                      SET nb_reponses = nb_reponses + 1
                    WHERE id_utilisateur = %s""",
                (g.utilisateur["id_utilisateur"],),
            )

    # Date de la premiere reponse, posee une seule fois. Le delai entre
    # une question et sa premiere reponse est la mesure la plus parlante
    # de la vitalite de la plateforme, et elle ne se reconstitue pas
    # apres coup si on ne l'inscrit pas.
    executer(
        """UPDATE question SET premiere_reponse_le = CURRENT_TIMESTAMP
            WHERE id_question = %s AND premiere_reponse_le IS NULL""",
        (int(id_q),), commit=True)
    evenements.depuis_requete("reponse_publiee", type_cible="question",
                              id_cible=int(id_q),
                              contexte={"reponse": id_r,
                                        "est_reponse_a_reponse": bool(id_parent)})

    # La notification vient apres l'enregistrement : elle ne doit ni le
    # retarder ni le compromettre si elle echoue.
    notifier_reponse(
        int(id_q), g.utilisateur["id_utilisateur"],
        f"{g.utilisateur.get('prenom', '')} "
        f"{(g.utilisateur.get('nom') or '')[:1]}.".strip())

    return jsonify({"id_reponse": id_r}), 201


@bp_reponses.delete("/<int:id_r>")
@connexion_requise
def supprimer(id_r):
    r = recuperer_un("SELECT id_auteur FROM reponse WHERE id_reponse = %s",
                     (id_r,))
    if not r:
        return jsonify({"erreur": "Réponse introuvable."}), 404
    if r["id_auteur"] != g.utilisateur["id_utilisateur"] \
            and not g.utilisateur.get("est_admin"):
        return jsonify({"erreur": "Action non autorisée."}), 403
    executer("DELETE FROM reponse WHERE id_reponse = %s",
             (id_r,), commit=True)
    # Le compteur du referent n'etait jamais corrige : il montait a la
    # publication et ne redescendait pas. L'annuaire affichait « 10
    # reponses » sous quelqu'un qui en avait deux, et le classait devant
    # des referents plus actifs, puisque c'est sur ce compteur qu'il
    # trie. On le recale sur ce que la base contient reellement.
    _recaler_compteur(r["id_auteur"])
    return jsonify({"ok": True})


def _recaler_compteur(id_auteur):
    """Remet nb_reponses en accord avec les reponses existantes."""
    reel = (recuperer_un(
        "SELECT COUNT(*) AS n FROM reponse WHERE id_auteur = %s",
        (id_auteur,)) or {}).get("n", 0)
    executer(
        "UPDATE mentor_details SET nb_reponses = %s WHERE id_utilisateur = %s",
        (reel, id_auteur), commit=True)
    return reel


@bp_reponses.post("/<int:id_r>/note")
@connexion_requise
def noter(id_r):
    """Note une réponse de un à cinq, et met à jour la moyenne du référent.

    Les étoiles existaient à l'écran depuis l'origine : on cliquait, un
    message confirmait « Note attribuée », et rien ne partait nulle
    part. La moyenne affichée sur les profils de référents valait donc
    zéro pour tout le monde, faute d'avoir jamais été calculée.
    """
    d = request.get_json(silent=True) or {}
    try:
        valeur = int(d.get("valeur"))
    except (TypeError, ValueError):
        return jsonify({"erreur": "Note attendue entre 1 et 5."}), 400
    if not 1 <= valeur <= 5:
        return jsonify({"erreur": "Note attendue entre 1 et 5."}), 400

    reponse = recuperer_un(
        "SELECT id_auteur FROM reponse WHERE id_reponse = %s", (id_r,))
    if not reponse:
        return jsonify({"erreur": "Réponse introuvable."}), 404
    id_user = g.utilisateur["id_utilisateur"]
    if reponse["id_auteur"] == id_user:
        return jsonify({"erreur": "On ne note pas sa propre réponse."}), 400

    deja = recuperer_un(
        """SELECT valeur FROM note_reponse
            WHERE id_reponse = %s AND id_utilisateur = %s""",
        (id_r, id_user))
    if deja:
        executer(
            """UPDATE note_reponse SET valeur = %s
                WHERE id_reponse = %s AND id_utilisateur = %s""",
            (valeur, id_r, id_user), commit=True)
    else:
        executer(
            """INSERT INTO note_reponse (id_reponse, id_utilisateur, valeur)
               VALUES (%s, %s, %s)""",
            (id_r, id_user, valeur), commit=True)

    note_auteur = _recalculer_note(reponse["id_auteur"])
    resume = recuperer_un(
        """SELECT COUNT(*) AS n, AVG(valeur) AS moyenne
             FROM note_reponse WHERE id_reponse = %s""", (id_r,)) or {}
    evenements.depuis_requete("reponse_notee", type_cible="reponse",
                              id_cible=id_r, contexte={"valeur": valeur})
    return jsonify({
        "ma_note": valeur,
        "nb_notes": resume.get("n") or 0,
        "note_moyenne": round(float(resume.get("moyenne") or 0), 1),
        "note_auteur": note_auteur,
    })


def _recalculer_note(id_auteur):
    """Moyenne des notes reçues par un référent, sur toutes ses réponses."""
    ligne = recuperer_un(
        """SELECT AVG(n.valeur) AS moyenne
             FROM note_reponse n
             JOIN reponse r ON r.id_reponse = n.id_reponse
            WHERE r.id_auteur = %s""", (id_auteur,)) or {}
    moyenne = round(float(ligne.get("moyenne") or 0), 2)
    executer(
        "UPDATE mentor_details SET note_moyenne = %s WHERE id_utilisateur = %s",
        (moyenne, id_auteur), commit=True)
    return moyenne


@bp_reponses.post("/<int:id_r>/utile")
@connexion_requise
def basculer_utile(id_r):
    id_user = g.utilisateur["id_utilisateur"]
    deja = recuperer_un(
        """SELECT 1 FROM marquage_reponse
            WHERE id_reponse = %s AND id_utilisateur = %s
              AND type_marquage = 'utile'""",
        (id_r, id_user),
    )
    if deja:
        executer(
            """DELETE FROM marquage_reponse
                WHERE id_reponse = %s AND id_utilisateur = %s
                  AND type_marquage = 'utile'""",
            (id_r, id_user), commit=True,
        )
        return jsonify({"marque": False})
    executer(
        """INSERT INTO marquage_reponse
              (id_reponse, id_utilisateur, type_marquage)
           VALUES (%s, %s, 'utile')""",
        (id_r, id_user), commit=True,
    )
    # « Cette réponse m'a servi » est le seul signal de qualité que
    # laisse un bénéficiaire. Il figurait au vocabulaire du journal sans
    # y être jamais inscrit.
    evenements.depuis_requete("reponse_utile", type_cible="reponse",
                              id_cible=id_r)
    return jsonify({"marque": True})
