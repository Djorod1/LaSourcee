"""Journal d'activite de la plateforme.

Les tables metier disent l'etat present : qui est inscrit, quelles
questions existent, lesquelles ont une reponse. Elles ne disent pas ce
qui s'est passe. Combien de temps entre une question et sa premiere
reponse, quels secteurs attirent, a quel moment quelqu'un cesse de
revenir : rien de tout cela ne se lit dans un etat, seulement dans une
suite d'evenements.

C'est aussi ce qu'il faut pour entrainer quoi que ce soit. Un modele
n'apprend pas d'une photographie, il apprend d'une serie.

Trois limites sont posees ici, et elles sont volontaires :

  - **Aucun contenu ecrit par un membre.** On note qu'une question a ete
    publiee, pas ce qu'elle disait. Le texte vit dans sa table ; le
    recopier ici le rendrait ineffacable, et un export d'evenements
    deviendrait un export de contenus.
  - **L'identifiant, jamais l'adresse ni le nom.** Un fichier
    d'evenements ne doit pas suffire a reconnaitre quelqu'un.
  - **Aucune levee d'exception.** Une mesure perdue est sans gravite ;
    une question perdue parce que sa mesure a echoue ne l'est pas.

Le champ ``contexte`` accueille en JSON ce qui varie d'un type a
l'autre. Il ne se lit qu'en connaissant le type de l'evenement.
"""

import json
import logging

from models.db import executer

logger = logging.getLogger("lasourcee.evenements")

# Types connus. La liste n'est pas une contrainte technique, elle sert a
# ce que l'analyse porte sur un vocabulaire stable : un type invente au
# fil de l'eau produit des series impossibles a comparer.
TYPES = {
    "inscription": "Creation d'un compte",
    "connexion": "Ouverture de session",
    "question_publiee": "Publication d'une question",
    "reponse_publiee": "Publication d'une reponse",
    "question_vue": "Consultation d'une question",
    "reponse_utile": "Reponse marquee utile",
    "question_utile": "Question marquee utile",
    "suivi": "Abonnement a un referent",
    "recherche": "Recherche effectuee",
    "candidature": "Depot d'une candidature de referent",
    "candidature_tranchee": "Decision sur une candidature",
    "profil_complete": "Mise a jour du profil",
    "signalement": "Signalement d'un contenu",
    "moderation": "Decision de moderation",
    "compte_supprime": "Suppression d'un compte",
}

LONGUEUR_MAX_CONTEXTE = 2000


def enregistrer(type_evenement, id_utilisateur=None, type_cible=None,
                id_cible=None, contexte=None, role=None):
    """Depose un evenement. Ne leve jamais."""
    try:
        charge = None
        if contexte:
            charge = json.dumps(contexte, ensure_ascii=False,
                                default=str)[:LONGUEUR_MAX_CONTEXTE]
        executer(
            """INSERT INTO evenement
                  (id_utilisateur, type_evenement, type_cible, id_cible,
                   contexte, role_acteur)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (id_utilisateur, str(type_evenement)[:40],
             type_cible, id_cible, charge, role),
            commit=True,
        )
        return True
    except Exception as exc:
        logger.debug("Evenement %s non enregistre : %s", type_evenement, exc)
        return False


def depuis_requete(type_evenement, **kwargs):
    """Enregistre en reprenant l'acteur de la requete en cours.

    Le role est fige au moment de l'action : il change avec le temps, et
    une analyse posterieure attribuerait sinon toute l'activite passee
    d'un referent au role qu'il porte aujourd'hui.
    """
    try:
        from flask import g
        utilisateur = getattr(g, "utilisateur", None) or {}
        kwargs.setdefault("id_utilisateur", utilisateur.get("id_utilisateur"))
        kwargs.setdefault("role", utilisateur.get("role"))
    except Exception:
        pass
    return enregistrer(type_evenement, **kwargs)
