"""Lecture et mise à jour du profil utilisateur."""

from flask import Blueprint, g, jsonify, request

from models.db import recuperer_un, recuperer_tous, executer, curseur
from utils.auth_helpers import connexion_requise

bp_profil = Blueprint("profil", __name__, url_prefix="/api/profil")


@bp_profil.get("/referentiels")
def referentiels():
    """Endpoint public : secteurs et pays disponibles."""
    return jsonify({
        "secteurs": recuperer_tous(
            "SELECT id_secteur, libelle, couleur FROM secteur ORDER BY libelle"
        ),
        "pays": recuperer_tous(
            "SELECT id_pays, libelle, code_iso FROM pays ORDER BY libelle"
        ),
    })


@bp_profil.get("/moi")
@connexion_requise
def mon_profil():
    return jsonify(_charger_profil(g.utilisateur["id_utilisateur"]))


@bp_profil.get("/<int:id_user>")
@connexion_requise
def voir_profil(id_user):
    profil = _charger_profil(id_user, public=True)
    if profil is None:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404
    return jsonify(profil)


@bp_profil.put("/moi")
@connexion_requise
def modifier_profil():
    d = request.get_json(silent=True) or {}
    id_user = g.utilisateur["id_utilisateur"]

    champs = {
        "prenom": d.get("prenom"),
        "nom": d.get("nom"),
        "bio": d.get("bio"),
        "photo_url": d.get("photo_url"),
        "etudes": d.get("etudes"),
        "ville": d.get("ville"),
        "id_pays": d.get("id_pays"),
    }
    champs = {k: v for k, v in champs.items() if v is not None}
    if champs:
        fragments = ", ".join(f"{k} = %s" for k in champs)
        executer(
            f"UPDATE utilisateur SET {fragments} WHERE id_utilisateur = %s",
            list(champs.values()) + [id_user],
            commit=True,
        )

    # Secteurs d'intérêt : remplacement atomique
    if "secteurs" in d:
        with curseur(commit=True) as cur:
            cur.execute(
                "DELETE FROM utilisateur_secteur WHERE id_utilisateur = %s",
                (id_user,),
            )
            for id_sect in d["secteurs"] or []:
                cur.execute(
                    """INSERT INTO utilisateur_secteur
                          (id_utilisateur, id_secteur) VALUES (%s, %s)""",
                    (id_user, int(id_sect)),
                )

    # Détails mentor (si applicable)
    if g.utilisateur["role"] == "mentor":
        dispo = d.get("dispo")
        anciennete = d.get("anciennete")
        if dispo in ("disponible", "occupe", "absent"):
            executer(
                "UPDATE mentor_details SET dispo = %s WHERE id_utilisateur = %s",
                (dispo, id_user), commit=True,
            )
        if anciennete is not None:
            executer(
                """UPDATE mentor_details SET anciennete = %s
                    WHERE id_utilisateur = %s""",
                (anciennete[:40], id_user), commit=True,
            )

    return jsonify(_charger_profil(id_user))


def _charger_profil(id_user, public=False):
    base = recuperer_un(
        """SELECT u.id_utilisateur, u.prenom, u.nom, u.email,
                  u.role, u.photo_url, u.bio, u.etudes, u.ville,
                  u.id_pays, p.libelle AS pays,
                  u.est_admin, u.doit_changer_mdp, u.cree_le,
                  md.est_verifie, md.dispo, md.anciennete,
                  md.delai_reponse, md.note_moyenne, md.nb_reponses
             FROM utilisateur u
        LEFT JOIN pays p           ON p.id_pays = u.id_pays
        LEFT JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
            WHERE u.id_utilisateur = %s""",
        (id_user,),
    )
    if not base:
        return None
    if public:
        base.pop("email", None)
        base.pop("est_admin", None)
        # Ne jamais révéler qu'un compte tourne encore avec un mot de
        # passe temporaire : ce serait désigner une cible.
        base.pop("doit_changer_mdp", None)

    base["secteurs"] = recuperer_tous(
        """SELECT s.id_secteur, s.libelle, s.couleur
             FROM utilisateur_secteur us
             JOIN secteur s ON s.id_secteur = us.id_secteur
            WHERE us.id_utilisateur = %s
         ORDER BY s.libelle""",
        (id_user,),
    )
    base["experiences"] = recuperer_tous(
        """SELECT id_experience, type_experience, intitule, periode, ordre
             FROM experience
            WHERE id_utilisateur = %s
         ORDER BY ordre, id_experience""",
        (id_user,),
    )
    return base


@bp_profil.get("/statistiques")
def statistiques_publiques():
    """Chiffres réels de la plateforme, pour la page d'accueil.

    La page annonçait des nombres écrits en dur, sans rapport avec la
    base. Afficher des chiffres inventés sur un site public engage la
    crédibilité du projet, et un visiteur qui s'inscrit après avoir lu
    « 12 000 membres » découvre autre chose.

    Seuls des agrégats sont exposés : aucun nom, aucune adresse. Les
    comptes désactivés sont exclus, sans quoi une suspension gonflerait
    encore le total.
    """
    def compter(requete):
        return (recuperer_un(requete) or {}).get("n", 0) or 0

    return jsonify({
        "membres": compter(
            "SELECT COUNT(*) AS n FROM utilisateur WHERE est_actif = 1"),
        "mentors": compter(
            "SELECT COUNT(*) AS n FROM utilisateur "
            "WHERE role = 'mentor' AND est_actif = 1"),
        "questions": compter("SELECT COUNT(*) AS n FROM question"),
        "reponses": compter("SELECT COUNT(*) AS n FROM reponse"),
    })
