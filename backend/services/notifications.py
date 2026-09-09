"""Creation des notifications adressees aux membres.

La table existait et la route de lecture aussi, mais rien n'y inserait
jamais : la cloche restait desesperement vide, quoi qu'il arrive sur la
plateforme. Ce module comble ce manque.

Deux principes tiennent tout le reste :

  - **On ne se notifie pas soi-meme.** Repondre a sa propre question ou
    aimer sa propre reponse ne doit rien declencher.
  - **Les preferences font foi.** Quelqu'un qui a decoche « Reactions
    sur mes publications » ne doit plus en recevoir, sinon le reglage
    ne sert a rien.

Aucune fonction ne leve : une notification perdue est regrettable, une
reponse perdue parce que sa notification a echoue ne l'est pas.
"""

import json
import logging

from models.db import recuperer_un, executer

logger = logging.getLogger("lasourcee.notifications")

# Correspondance entre le type de notification et la preference qui la
# gouverne. Un type absent de cette table est toujours envoye : c'est le
# cas des messages du systeme, qu'on ne peut pas refuser.
PREFERENCE_PAR_TYPE = {
    "reponse": "reponse_question",
    "reaction": "reactions",
    "nouvelle_question": "questions_secteur",
    "suivi": None,
    "message": None,
    "systeme": None,
}

LONGUEUR_MAX = 300


def _accepte(id_destinataire, type_notif):
    """La personne a-t-elle accepte ce genre de notification ?"""
    cle = PREFERENCE_PAR_TYPE.get(type_notif)
    if cle is None:
        return True
    ligne = recuperer_un(
        "SELECT preferences_notif FROM utilisateur WHERE id_utilisateur = %s",
        (id_destinataire,),
    )
    brut = (ligne or {}).get("preferences_notif")
    if not brut:
        return True             # jamais regle : valeurs par defaut
    try:
        return bool(json.loads(brut).get("app", {}).get(cle, True))
    except (ValueError, TypeError):
        return True


def notifier(id_destinataire, texte, type_notif="systeme", id_question=None,
             id_acteur=None):
    """Depose une notification, si elle a lieu d'etre.

    ``id_acteur`` est l'auteur de l'action : le passer evite de notifier
    quelqu'un de sa propre activite, ce qui est la source d'agacement la
    plus courante sur ce genre de plateforme.
    """
    try:
        if not id_destinataire:
            return False
        if id_acteur is not None and int(id_acteur) == int(id_destinataire):
            return False
        if not _accepte(id_destinataire, type_notif):
            return False

        executer(
            """INSERT INTO notification
                  (id_destinataire, texte, lien_question, type_notif)
               VALUES (%s, %s, %s, %s)""",
            (id_destinataire, (texte or "")[:LONGUEUR_MAX],
             id_question, type_notif),
            commit=True,
        )
        return True
    except Exception as exc:
        # Une notification perdue est regrettable ; une reponse perdue
        # parce que sa notification a echoue ne l'est pas.
        logger.warning("Notification non deposee pour %s : %s",
                       id_destinataire, exc)
        return False


def notifier_reponse(id_question, id_auteur_reponse, nom_repondant):
    """Previent l'auteur d'une question qu'on lui a repondu."""
    question = recuperer_un(
        "SELECT id_auteur, titre FROM question WHERE id_question = %s",
        (id_question,),
    )
    if not question:
        return False
    titre = (question.get("titre") or "").strip()
    extrait = titre if len(titre) <= 60 else titre[:57] + "..."
    return notifier(
        question["id_auteur"],
        f"{nom_repondant} a repondu a votre question : « {extrait} »",
        type_notif="reponse",
        id_question=id_question,
        id_acteur=id_auteur_reponse,
    )


def notifier_reaction(id_question, id_acteur, nom_acteur):
    """Previent l'auteur d'une question qu'elle a ete jugee utile."""
    question = recuperer_un(
        "SELECT id_auteur, titre FROM question WHERE id_question = %s",
        (id_question,),
    )
    if not question:
        return False
    titre = (question.get("titre") or "").strip()
    extrait = titre if len(titre) <= 60 else titre[:57] + "..."
    return notifier(
        question["id_auteur"],
        f"{nom_acteur} a trouve votre question utile : « {extrait} »",
        type_notif="reaction",
        id_question=id_question,
        id_acteur=id_acteur,
    )


def notifier_suivi(id_referent, id_suiveur, nom_suiveur):
    """Previent un referent qu'on s'est abonne a ses reponses."""
    return notifier(
        id_referent,
        f"{nom_suiveur} suit desormais vos reponses.",
        type_notif="suivi",
        id_acteur=id_suiveur,
    )


def notifier_decision_candidature(id_candidat, acceptee):
    """Previent un candidat de la decision prise sur son dossier."""
    if acceptee:
        texte = ("Votre candidature de referent est acceptee. Le badge "
                 "Referent verifie apparait desormais sur vos reponses.")
    else:
        texte = ("Votre candidature de referent n'a pas ete retenue cette "
                 "fois. Vous pouvez la deposer a nouveau.")
    return notifier(id_candidat, texte, type_notif="systeme")
