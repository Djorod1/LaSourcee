"""Recherche globale : référents, questions et secteurs.

Deux défauts la rendaient à la fois inutile et indiscrète.

Elle comparait avec ``LIKE`` sans mettre les deux côtés dans la même
casse. Sur PostgreSQL, qui sert la production, ``LIKE`` distingue les
majuscules : chercher « marie » ne trouvait pas Marie, et « TECHNOLOGIE »
ne trouvait pas Technologie. La recherche paraissait ne rien contenir
alors qu'elle contenait tout.

Et elle montrait les référents que l'annuaire écarte. L'annuaire exige
``est_verifie = 1`` ; la recherche se contentait du rôle. On y voyait
donc les candidatures en attente et celles qui avaient été refusées,
c'est-à-dire précisément ce que la vérification sert à ne pas exposer.
Les deux écrans appliquent maintenant la même règle.

Une limite demeure, et elle ne tient pas au code : ``LOWER`` suit le
collationnement de la base. Sous ``en_US.UTF-8``, qui sert en
production, « éducation » trouve « Éducation ». Sous ``C``, non, car
``lower('É')`` y rend ``'É'``. Et dans tous les cas, chercher
« education » sans accent ne trouve rien : il faudrait pour cela
l'extension ``unaccent`` de PostgreSQL, ou une colonne normalisée tenue
à jour. C'est une fonctionnalité à part entière, pas un oubli.
"""

from flask import Blueprint, jsonify, request

from models.db import recuperer_tous
from utils.auth_helpers import connexion_requise

bp_recherche = Blueprint("recherche", __name__, url_prefix="/api/recherche")

LONGUEUR_MIN = 2
MAX_RESULTATS = 8


def motif_like(terme):
    """Prépare un terme pour un LIKE, jokers compris.

    ``%`` et ``_`` sont des jokers : une recherche sur « 100 % » ou sur
    « _ » balayait la table entière et remontait huit lignes au hasard.
    Ils sont échappés, avec la clause ESCAPE qui va avec.
    """
    echappe = (terme.lower()
               .replace("\\", "\\\\")
               .replace("%", "\\%")
               .replace("_", "\\_"))
    return f"%{echappe}%"


@bp_recherche.get("")
@connexion_requise
def globale():
    terme = (request.args.get("q") or "").strip()
    if len(terme) < LONGUEUR_MIN:
        return jsonify({"mentors": [], "questions": [], "secteurs": []})

    motif = motif_like(terme)

    mentors = recuperer_tous(
        """SELECT u.id_utilisateur, u.prenom, u.nom, u.photo_url,
                  md.est_verifie, md.note_moyenne, md.nb_reponses
             FROM utilisateur u
             JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
            WHERE u.role = 'mentor' AND u.est_actif = 1
              AND md.est_verifie = 1
              AND (LOWER(u.prenom) LIKE %s ESCAPE '\\'
                   OR LOWER(u.nom) LIKE %s ESCAPE '\\'
                   OR LOWER(u.bio) LIKE %s ESCAPE '\\')
         ORDER BY md.note_moyenne DESC, md.nb_reponses DESC
            LIMIT %s""",
        (motif, motif, motif, MAX_RESULTATS),
    )

    questions = recuperer_tous(
        """SELECT id_question, titre, publiee_le
             FROM question
            WHERE LOWER(titre) LIKE %s ESCAPE '\\'
               OR LOWER(corps) LIKE %s ESCAPE '\\'
         ORDER BY publiee_le DESC
            LIMIT %s""",
        (motif, motif, MAX_RESULTATS),
    )

    secteurs = recuperer_tous(
        """SELECT id_secteur, libelle, couleur FROM secteur
            WHERE LOWER(libelle) LIKE %s ESCAPE '\\'
         ORDER BY libelle LIMIT %s""",
        (motif, MAX_RESULTATS),
    )

    return jsonify({
        "mentors": mentors,
        "questions": questions,
        "secteurs": secteurs,
    })
