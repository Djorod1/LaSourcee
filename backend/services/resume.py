"""Résumé périodique de ce qui bouge sur la plateforme.

Une plateforme de questions et de réponses meurt du même silence des
deux côtés : personne ne publie parce que personne ne répond, et
personne ne répond parce que personne ne publie. Le message périodique
casse cette boucle en disant ce qui s'est passé, à des gens qui n'ont
aucune raison de revenir d'eux-mêmes.

Quatre règles le gouvernent, et chacune existe parce que son contraire
fait désabonner :

  - **Jamais deux fois en deux jours.** Un message quotidien devient du
    bruit, et le bruit se range dans les indésirables avec le reste du
    domaine expéditeur.
  - **Rien à dire, rien à envoyer.** Un résumé vide apprend à ne plus
    ouvrir les suivants. Un seuil minimum est exigé.
  - **Ce qui concerne la personne d'abord.** Les réponses à ses propres
    questions passent avant l'activité générale ; un référent voit
    d'abord les questions de son secteur restées sans réponse.
  - **Un lien de désinscription dans chaque message.** Il ne demande ni
    de se connecter ni de retrouver un réglage : un désabonnement
    difficile se règle en marquant l'expéditeur comme indésirable, ce
    qui coûte bien plus cher.
"""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta

from flask import current_app

from models.db import recuperer_un, recuperer_tous, executer
from utils.urls import url_publique

logger = logging.getLogger("lasourcee.resume")

# Deux jours entre deux messages, comme demandé, et pas moins.
DELAI_HEURES = 48

# En dessous, on se tait. Annoncer « une nouveauté » pour une seule
# question publiée use la patience plus vite qu'elle ne l'entretient.
SEUIL_NOUVEAUTES = 2

# Garde-fou : un envoi en masse sur une fonction serverless limitée à
# dix secondes n'aboutirait pas. Les suivants partent au passage
# suivant, la colonne resume_envoye_le faisant office de curseur.
MAX_PAR_PASSAGE = 40


def _depuis(heures):
    return (datetime.utcnow() - timedelta(hours=heures)
            ).strftime("%Y-%m-%d %H:%M:%S")


def jeton_desinscription(id_utilisateur):
    """Signature courte qui autorise à se désinscrire sans se connecter.

    Dérivée de la clé du serveur : aucune table à tenir, rien à purger,
    et un identifiant seul ne suffit pas à désinscrire quelqu'un d'autre.
    """
    cle = (current_app.config.get("SECRET_KEY") or "").encode("utf-8")
    empreinte = hmac.new(cle, f"resume:{id_utilisateur}".encode("utf-8"),
                         hashlib.sha256)
    return empreinte.hexdigest()[:32]


def jeton_valide(id_utilisateur, jeton):
    return hmac.compare_digest(jeton_desinscription(id_utilisateur),
                               str(jeton or ""))


def _destinataires():
    """Comptes actifs, confirmés, qui n'ont rien reçu depuis deux jours."""
    limite = _depuis(DELAI_HEURES)
    return recuperer_tous(
        """SELECT u.id_utilisateur, u.prenom, u.email, u.role,
                  u.derniere_co, u.resume_envoye_le
             FROM utilisateur u
            WHERE u.est_actif = 1
              AND u.email_verifie = 1
              AND (u.resume_envoye_le IS NULL OR u.resume_envoye_le < %s)
         ORDER BY CASE WHEN u.resume_envoye_le IS NULL THEN 0 ELSE 1 END,
                  u.resume_envoye_le
            LIMIT %s""",
        (limite, MAX_PAR_PASSAGE))


def _accepte(id_utilisateur):
    """Le résumé est-il accepté par cette personne ?"""
    from routes.profil import _lire_preferences
    try:
        prefs = _lire_preferences(id_utilisateur)
    except Exception:                        # pragma: no cover
        return False
    return bool(prefs.get("email", {}).get("resume_activite", True))


def _nouveautes(compte, depuis):
    """Ce qu'il y a à dire à cette personne, et rien d'autre."""
    id_user = compte["id_utilisateur"]
    lignes = []

    reponses = recuperer_un(
        """SELECT COUNT(*) AS n FROM reponse r
             JOIN question q ON q.id_question = r.id_question
            WHERE q.id_auteur = %s AND r.id_auteur <> %s
              AND r.cree_le > %s""",
        (id_user, id_user, depuis)) or {}
    if reponses.get("n"):
        n = reponses["n"]
        lignes.append(("vos questions",
                       f"{n} nouvelle{'s' if n > 1 else ''} réponse"
                       f"{'s' if n > 1 else ''} à vos questions"))

    # Les questions du secteur de la personne : c'est la ou elle peut
    # aider, et ce qui la concerne le plus apres ses propres questions.
    mien = recuperer_un(
        """SELECT COUNT(*) AS n
             FROM question q
             JOIN utilisateur_secteur us ON us.id_secteur = q.id_secteur
            WHERE us.id_utilisateur = %s AND q.id_auteur <> %s
              AND q.publiee_le > %s""",
        (id_user, id_user, depuis)) or {}
    if mien.get("n"):
        n = mien["n"]
        lignes.append(("vos secteurs",
                       f"{n} question{'s' if n > 1 else ''} "
                       f"dans vos secteurs d'intérêt"))

    if compte.get("role") == "mentor":
        sans = recuperer_un(
            """SELECT COUNT(*) AS n FROM question q
                WHERE q.publiee_le > %s
                  AND NOT EXISTS (SELECT 1 FROM reponse r
                                   WHERE r.id_question = q.id_question)""",
            (depuis,)) or {}
        if sans.get("n"):
            n = sans["n"]
            lignes.append(("sans réponse",
                           f"{n} question{'s' if n > 1 else ''} "
                           f"attend{'ent' if n > 1 else ''} encore une réponse"))

    opportunites = recuperer_un(
        """SELECT COUNT(*) AS n FROM opportunite
            WHERE statut = 'publiee' AND cree_le > %s""",
        (depuis,)) or {}
    if opportunites.get("n"):
        n = opportunites["n"]
        lignes.append(("opportunités",
                       f"{n} bourse{'s' if n > 1 else ''} ou "
                       f"opportunité{'s' if n > 1 else ''} publiée"
                       f"{'s' if n > 1 else ''}"))

    return lignes


def _corps(compte, lignes, adresse):
    prenom = compte.get("prenom") or "Bonjour"
    jeton = jeton_desinscription(compte["id_utilisateur"])
    lien_stop = (f"{adresse}/api/profil/resume/stop"
                 f"?u={compte['id_utilisateur']}&j={jeton}")
    corps = [f"Bonjour {prenom},", "",
             "Voici ce qui s'est passé sur LaSourcee depuis votre dernière "
             "visite :", ""]
    corps += [f"  - {texte}." for _, texte in lignes]
    corps += ["",
              f"Tout se retrouve ici : {adresse}", "",
              "Une question posée aujourd'hui trouve souvent sa réponse "
              "dans la journée. Si vous en avez une, c'est le moment.", "",
              "---",
              "Vous recevez ce message parce que vous avez un compte sur "
              "LaSourcee. Pour ne plus le recevoir, ouvrez ce lien :",
              lien_stop]
    return "\n".join(corps)


def envoyer_resumes():
    """Envoie le résumé à qui y a droit. Renvoie un bilan chiffré."""
    from utils.email import envoyer

    depuis = _depuis(DELAI_HEURES)
    adresse = url_publique("").rstrip("/")
    bilan = {"examines": 0, "envoyes": 0, "sans_nouveaute": 0, "refuses": 0,
             "echecs": 0}

    for compte in _destinataires():
        bilan["examines"] += 1
        if not compte.get("email"):
            continue
        if not _accepte(compte["id_utilisateur"]):
            bilan["refuses"] += 1
            # Marque quand meme la date : sans cela, ce compte serait
            # reexamine a chaque passage et occuperait la file.
            _marquer(compte["id_utilisateur"])
            continue

        lignes = _nouveautes(compte, compte.get("resume_envoye_le") or depuis)
        total = len(lignes)
        if total < SEUIL_NOUVEAUTES:
            bilan["sans_nouveaute"] += 1
            continue

        sujet = "LaSourcee : " + lignes[0][1].lower()
        parti = envoyer(compte["email"], sujet,
                        _corps(compte, lignes, adresse))
        if parti:
            bilan["envoyes"] += 1
            _marquer(compte["id_utilisateur"])
        else:
            bilan["echecs"] += 1

    logger.info("Résumés : %s", bilan)
    return bilan


def _marquer(id_utilisateur):
    executer(
        "UPDATE utilisateur SET resume_envoye_le = %s WHERE id_utilisateur = %s",
        (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), id_utilisateur),
        commit=True)
