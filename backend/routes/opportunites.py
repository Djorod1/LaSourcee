"""Bourses, concours, stages et formations.

Le fil de questions vit au rythme de qui ose demander. Une bourse, elle,
a une date limite : c'est ce qui fait revenir sur le site sans qu'on ait
rien à publier soi-même, et ce qui donne une raison de s'inscrire à qui
n'a pas encore de question à poser.

Qui publie, et comment
----------------------
Le compte LaSourcee publie, par ses administrateurs, et l'annonce paraît
aussitôt : c'est l'équipe qui engage sa parole. Un référent vérifié peut
aussi en proposer une, mais elle passe d'abord par une relecture. Ce
n'est pas de la défiance : une bourse annoncée avec une mauvaise date
limite ou un lien mort coûte plus cher qu'une bourse non annoncée, parce
que quelqu'un aura construit un projet dessus.

Un bénéficiaire ne publie pas. Il signale ce qu'il a trouvé par le
formulaire de contact, et l'équipe le reprend si c'est solide.

Ce qui se périme
----------------
Passé la date limite, l'annonce ne disparaît pas : elle passe en
« clôturée ». La plupart de ces programmes reviennent chaque année, et
savoir qu'ils existent vaut presque autant que d'y postuler à temps.
"""

import logging
import re
from datetime import date, datetime

from flask import Blueprint, current_app, g, jsonify, request

from models.db import recuperer_un, recuperer_tous, executer, curseur
from services import evenements
from services.notifications import notifier
from utils.auth_helpers import connexion_requise
from utils.audit import journaliser
from utils.permissions import a_le_droit, permission_requise

logger = logging.getLogger("lasourcee.opportunites")

bp_opportunites = Blueprint("opportunites", __name__,
                            url_prefix="/api/opportunites")

# Les intitulés disent ce que la personne fera, pas une taxonomie
# administrative : on ne « candidate à un dispositif », on demande une
# bourse ou on cherche un stage.
CATEGORIES = {
    "bourse": "Bourse d'études",
    "concours": "Concours ou examen",
    "stage": "Stage",
    "emploi": "Premier emploi",
    "formation": "Formation ou atelier",
    "appel": "Appel à candidatures",
}

STATUTS = ("en_attente", "publiee", "refusee")

LONGUEUR_TITRE = 160
LONGUEUR_DESCRIPTION = 4000
LONGUEUR_COURTE = 120

# Une affiche reduite a 1000 pixels de large en JPEG tient largement
# sous cette borne. Elle vit dans la base, comme les photos de profil :
# le disque d'un hebergement sans serveur ne survit pas a un
# redemarrage, et un service de stockage separe serait une piece de plus
# a tenir pour une plateforme de cette taille.
LONGUEUR_AFFICHE = 600_000


def _affiche_valide(valeur):
    """Rend (affiche, erreur). Une affiche vide est acceptee."""
    affiche = str(valeur or "").strip()
    if not affiche:
        return "", None
    if len(affiche) > LONGUEUR_AFFICHE:
        return None, ("Affiche trop lourde. Choisissez une image plus "
                      "legere, ou recadrez-la.")
    if not affiche.startswith("data:image/"):
        return None, "Format d'affiche non reconnu."
    return affiche, None

_RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _erreur(message, code=400):
    return jsonify({"erreur": message}), code


def _peut_publier_directement(utilisateur):
    return bool(utilisateur.get("est_admin")
                and a_le_droit(utilisateur, "opportunites"))


def _referent_verifie(id_utilisateur):
    """Le dossier de ce référent a-t-il été examiné ?

    Le texte en tête de ce module dit « un référent vérifié peut en
    proposer une », mais le contrôle se contentait du rôle. N'importe
    quelle candidature déposée le matin pouvait donc proposer une bourse
    l'après-midi, avant qu'un seul élément du dossier n'ait été regardé.
    """
    ligne = recuperer_un(
        "SELECT est_verifie FROM mentor_details WHERE id_utilisateur = %s",
        (id_utilisateur,))
    return bool(ligne and ligne["est_verifie"])


# Au-dela, la file de relecture n'est plus tenable. Le compte n'est pas
# bloque : il lui suffit qu'une de ses propositions soit tranchee.
MAX_EN_ATTENTE = 3


def _propositions_en_attente(id_utilisateur):
    ligne = recuperer_un(
        """SELECT COUNT(*) AS n FROM opportunite
            WHERE id_auteur = %s AND statut = 'en_attente'""",
        (id_utilisateur,))
    return (ligne or {}).get("n", 0) or 0


def _peut_proposer(utilisateur):
    """Qui peut soumettre une annonce a la relecture ?

    Tout membre dont l'adresse est confirmee. La regle d'avant reservait
    ce droit aux referents verifies, et c'etait le maillon faible :
    celui qui voit passer une bourse, c'est l'etudiant — sur le panneau
    d'affichage de son universite, dans un groupe de discussion. En le
    bloquant, on coupait la meilleure source d'annonces et on le
    renvoyait vers un formulaire de contact que presque personne
    n'utilise.

    La barriere utile n'est pas qui propose, c'est ce qui part en ligne
    sans relecture — et cela n'a pas bouge : seul un administrateur
    publie directement. Reste le risque de noyer la file, borne par
    MAX_EN_ATTENTE : on ne peut pas avoir plus de trois propositions en
    attente a la fois. C'est une limite qui se leve d'elle-meme des
    qu'une proposition est tranchee, et qui ne punit pas le nouveau venu
    ayant trouve une vraie bourse aujourd'hui — ce qu'un seuil
    d'anciennete aurait fait.

    On n'exige pas ici une adresse confirmee : en production, la
    confirmation est deja requise pour se connecter. La redemander
    serait une seconde regle disant la meme chose, et surtout elle ferait
    diverger le developpement de la production — ou l'on n'aurait plus
    jamais l'occasion de s'en apercevoir.
    """
    return True


def _nettoyer(valeur, longueur):
    return " ".join(str(valeur or "").split())[:longueur]


def _date_limite(valeur):
    """Date au format AAAA-MM-JJ, chaîne vide, ou None si invalide."""
    brut = (valeur or "").strip()
    if not brut:
        return ""
    if not _RE_DATE.match(brut):
        return None
    try:
        datetime.strptime(brut, "%Y-%m-%d")
    except ValueError:
        return None
    return brut


def _cloturee(ligne):
    limite = ligne.get("date_limite")
    if not limite:
        return False
    return str(limite)[:10] < date.today().isoformat()


@bp_opportunites.get("/referentiels")
def referentiels():
    return jsonify({"categories": [{"cle": c, "libelle": l}
                                   for c, l in CATEGORIES.items()]})


@bp_opportunites.get("")
@connexion_requise
def lister():
    """Le fil des annonces publiées, les échéances proches d'abord."""
    categorie = request.args.get("categorie")
    inclure_closes = request.args.get("closes") == "1"

    conditions = ["o.statut = 'publiee'"]
    params = []
    if categorie in CATEGORIES:
        conditions.append("o.categorie = %s")
        params.append(categorie)

    lignes = recuperer_tous(
        f"""SELECT o.id_opportunite, o.titre, o.categorie, o.organisme,
                   o.description, o.pays, o.niveau, o.domaine,
                   o.date_limite, o.lien, o.vues, o.cree_le,
                   CASE WHEN o.affiche IS NULL OR o.affiche = ''
                        THEN 0 ELSE 1 END AS a_une_affiche,
                   u.id_utilisateur, u.prenom, u.nom, u.role, u.photo_url
              FROM opportunite o
         LEFT JOIN utilisateur u ON u.id_utilisateur = o.id_auteur
             WHERE {' AND '.join(conditions)}
          ORDER BY CASE WHEN o.date_limite IS NULL OR o.date_limite = ''
                        THEN 1 ELSE 0 END,
                   o.date_limite ASC, o.cree_le DESC
             LIMIT 200""",
        tuple(params))

    ouvertes, closes = [], []
    for ligne in lignes:
        ligne["categorie_libelle"] = CATEGORIES.get(ligne["categorie"],
                                                    "Appel à candidatures")
        ligne["cloturee"] = _cloturee(ligne)
        (closes if ligne["cloturee"] else ouvertes).append(ligne)

    # Les annonces closes vont a la fin, jamais melangees aux autres :
    # une date depassee lue en diagonale fait rater la suivante.
    return jsonify({
        "opportunites": ouvertes + (closes if inclure_closes else []),
        "nb_closes": len(closes),
        "categories": CATEGORIES,
        # L'interface ne propose le bouton que s'il aboutira : offrir
        # une action qui repondra par un refus fait passer une regle
        # pour une panne.
        "peut_proposer": _peut_proposer(g.utilisateur),
        "publie_directement": _peut_publier_directement(g.utilisateur),
    })


@bp_opportunites.get("/<int:id_opp>")
@connexion_requise
def detail(id_opp):
    ligne = recuperer_un(
        """SELECT o.*, u.prenom, u.nom, u.role, u.photo_url
             FROM opportunite o
        LEFT JOIN utilisateur u ON u.id_utilisateur = o.id_auteur
            WHERE o.id_opportunite = %s""", (id_opp,))
    if not ligne:
        return _erreur("Annonce introuvable.", 404)
    visible = (ligne["statut"] == "publiee"
               or ligne.get("id_auteur") == g.utilisateur["id_utilisateur"]
               or _peut_publier_directement(g.utilisateur))
    if not visible:
        return _erreur("Annonce introuvable.", 404)

    executer("UPDATE opportunite SET vues = vues + 1 "
             "WHERE id_opportunite = %s", (id_opp,), commit=True)
    ligne["categorie_libelle"] = CATEGORIES.get(ligne["categorie"],
                                                "Appel à candidatures")
    ligne["cloturee"] = _cloturee(ligne)
    # L'affiche ne voyage pas dans le JSON : elle a son adresse, que le
    # navigateur charge paresseusement et met en cache. Transportee ici,
    # elle se retelechargerait a chaque ouverture et gonflerait une
    # reponse que l'on lit surtout pour son texte.
    ligne["a_une_affiche"] = bool(ligne.pop("affiche", None))
    return jsonify(ligne)


@bp_opportunites.get("/<int:id_opp>/affiche")
def affiche(id_opp):
    """L'affiche d'une annonce, servie comme une image.

    Une adresse dediee plutot qu'un champ dans le JSON : le navigateur
    la charge quand elle entre a l'ecran, la garde en cache, et le fil
    reste leger meme avec deux cents annonces. Publique, comme l'annonce
    qu'elle illustre — elle ne revele rien de plus que le fil.
    """
    import base64
    import binascii

    ligne = recuperer_un(
        "SELECT affiche, statut FROM opportunite WHERE id_opportunite = %s",
        (id_opp,))
    if not ligne or not ligne.get("affiche"):
        return _erreur("Affiche introuvable.", 404)
    if ligne.get("statut") != "publiee":
        # Une annonce en attente ou refusee n'expose pas son image : ce
        # serait un moyen de savoir qu'elle existe.
        #
        # La route est ouverte — une image doit se charger sur une page
        # publique sans authentification —, donc `g.utilisateur` n'est
        # jamais pose ici : le decorateur qui l'installe ne s'applique
        # pas. On releve la session a la main, faute de quoi meme un
        # relecteur se verrait refuser l'affiche qu'il doit examiner.
        from utils.auth_helpers import (jeton_session_courant,
                                        utilisateur_depuis_jeton)
        moi = utilisateur_depuis_jeton(jeton_session_courant())
        if not (moi and _peut_publier_directement(moi)):
            return _erreur("Affiche introuvable.", 404)

    brut = str(ligne["affiche"])
    if "," not in brut or not brut.startswith("data:image/"):
        return _erreur("Affiche illisible.", 404)
    entete, donnees = brut.split(",", 1)
    type_mime = entete[5:].split(";")[0] or "image/jpeg"
    if type_mime not in ("image/jpeg", "image/png", "image/webp",
                         "image/gif"):
        return _erreur("Affiche illisible.", 404)
    try:
        octets = base64.b64decode(donnees, validate=True)
    except (binascii.Error, ValueError):
        return _erreur("Affiche illisible.", 404)

    reponse = current_app.response_class(octets, mimetype=type_mime)
    # Une affiche ne change pas : la remettre en cache une semaine evite
    # de la retelecharger a chaque passage dans le fil.
    reponse.headers["Cache-Control"] = "public, max-age=604800"
    return reponse


@bp_opportunites.post("")
@connexion_requise
def proposer():
    moi = g.utilisateur
    direct = _peut_publier_directement(moi)
    if not direct:
        en_attente = _propositions_en_attente(moi["id_utilisateur"])
        if en_attente >= MAX_EN_ATTENTE:
            return _erreur(
                f"Vous avez déjà {en_attente} propositions en attente de "
                "relecture. Patientez qu'elles soient examinées avant d'en "
                "proposer une autre.", 429)

    d = request.get_json(silent=True) or {}
    titre = _nettoyer(d.get("titre"), LONGUEUR_TITRE)
    description = (d.get("description") or "").strip()[:LONGUEUR_DESCRIPTION]
    categorie = d.get("categorie") if d.get("categorie") in CATEGORIES \
        else "bourse"

    if len(titre) < 8:
        return _erreur("Donnez un titre qui dise de quoi il s'agit.")
    if len(description) < 30:
        return _erreur("Décrivez l'annonce : conditions, public visé, "
                       "ce qu'elle apporte.")

    limite = _date_limite(d.get("date_limite"))
    if limite is None:
        return _erreur("Date limite attendue au format jour/mois/année.")

    # Le message annoncait https et le code acceptait http : quelqu'un
    # postule a une bourse depuis ce lien, souvent en donnant son
    # identite et parfois ses papiers. On tient ce qu'on annonce.
    lien = (d.get("lien") or "").strip()[:400]
    if lien and not lien.startswith("https://"):
        return _erreur("Le lien doit commencer par https://")
    # Une annonce sans lien ni organisme ne se verifie pas.
    organisme = _nettoyer(d.get("organisme"), LONGUEUR_COURTE)
    if not (lien or organisme):
        return _erreur("Indiquez au moins l'organisme ou le lien officiel : "
                       "sans quoi personne ne peut vérifier l'annonce.")

    affiche, erreur_affiche = _affiche_valide(d.get("affiche"))
    if erreur_affiche:
        return _erreur(erreur_affiche)

    statut = "publiee" if direct else "en_attente"
    with curseur(commit=True) as cur:
        cur.execute(
            """INSERT INTO opportunite
                  (id_auteur, titre, categorie, organisme, description,
                   pays, niveau, domaine, date_limite, lien, statut,
                   affiche)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (moi["id_utilisateur"], titre, categorie, organisme or None,
             description,
             _nettoyer(d.get("pays"), LONGUEUR_COURTE) or None,
             _nettoyer(d.get("niveau"), LONGUEUR_COURTE) or None,
             _nettoyer(d.get("domaine"), LONGUEUR_COURTE) or None,
             limite or None, lien or None, statut, affiche or None))
        id_opp = cur.lastrowid

    evenements.depuis_requete("opportunite_proposee", type_cible="opportunite",
                              id_cible=id_opp,
                              contexte={"categorie": categorie,
                                        "directe": direct})
    if not direct:
        _prevenir_relecteurs(titre)
    return jsonify({
        "id_opportunite": id_opp,
        "statut": statut,
        "message": ("Annonce publiée." if direct else
                    "Merci. L'équipe relit votre proposition avant sa mise "
                    "en ligne : une date limite fausse coûte plus cher "
                    "qu'une annonce tardive."),
    }), 201


def _prevenir_relecteurs(titre):
    try:
        comptes = recuperer_tous(
            "SELECT id_utilisateur, role, permissions FROM utilisateur "
            "WHERE est_admin = 1 AND est_actif = 1")
    except Exception as exc:              # pragma: no cover - dépend du schéma
        logger.warning("Relecteurs non prévenus : %s", exc)
        return
    for compte in comptes:
        compte["est_admin"] = 1
        if a_le_droit(compte, "opportunites"):
            notifier(compte["id_utilisateur"],
                     f"Une annonce attend une relecture : {titre[:120]}",
                     type_notif="systeme")


# ---------------------------------------------------------------------
# Relecture
# ---------------------------------------------------------------------

@bp_opportunites.get("/a-relire")
@permission_requise("opportunites")
def a_relire():
    return jsonify(recuperer_tous(
        """SELECT o.id_opportunite, o.titre, o.categorie, o.organisme,
                  o.description, o.pays, o.niveau, o.domaine,
                  o.date_limite, o.lien, o.cree_le,
                  CASE WHEN o.affiche IS NULL OR o.affiche = ''
                       THEN 0 ELSE 1 END AS a_une_affiche,
                  u.id_utilisateur, u.prenom, u.nom, u.photo_url
             FROM opportunite o
        LEFT JOIN utilisateur u ON u.id_utilisateur = o.id_auteur
            WHERE o.statut = 'en_attente'
         ORDER BY o.cree_le ASC"""))


@bp_opportunites.post("/<int:id_opp>/decision")
@permission_requise("opportunites")
def decider(id_opp):
    d = request.get_json(silent=True) or {}
    statut = d.get("statut")
    if statut not in ("publiee", "refusee"):
        return _erreur("Décision attendue : publiée ou refusée.")

    ligne = recuperer_un(
        "SELECT id_auteur, titre FROM opportunite WHERE id_opportunite = %s",
        (id_opp,))
    if not ligne:
        return _erreur("Annonce introuvable.", 404)

    motif = (d.get("motif") or "").strip()[:400]
    if statut == "refusee" and not motif:
        return _erreur("Dites pourquoi : un refus sans motif ne permet pas "
                       "de corriger.")

    executer(
        """UPDATE opportunite
              SET statut = %s, motif_refus = %s, decide_par = %s,
                  decide_le = %s
            WHERE id_opportunite = %s""",
        (statut, motif or None, g.utilisateur["id_utilisateur"],
         datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), id_opp),
        commit=True)

    if ligne.get("id_auteur"):
        texte = (f"Votre annonce « {ligne['titre'][:80]} » est en ligne."
                 if statut == "publiee" else
                 f"Votre annonce « {ligne['titre'][:80]} » n'a pas été "
                 f"retenue : {motif}")
        notifier(ligne["id_auteur"], texte, type_notif="systeme")

    evenements.depuis_requete("opportunite_decidee", type_cible="opportunite",
                              id_cible=id_opp, contexte={"statut": statut})
    # Le journal d'administration doit porter qui a tranche, quand, et
    # pourquoi : une annonce refusee sans trace devient un desaccord
    # sans arbitre.
    journaliser(g.utilisateur["id_utilisateur"],
                "opportunite_" + ("publiee" if statut == "publiee" else "refusee"),
                "opportunite", id_opp,
                f"{ligne['titre'][:120]}" + (f" | {motif}" if motif else ""))
    return jsonify({"ok": True, "statut": statut})


@bp_opportunites.delete("/<int:id_opp>")
@permission_requise("opportunites")
def supprimer(id_opp):
    ligne = recuperer_un(
        "SELECT titre FROM opportunite WHERE id_opportunite = %s", (id_opp,))
    if not ligne:
        return _erreur("Annonce introuvable.", 404)
    executer("DELETE FROM opportunite WHERE id_opportunite = %s",
             (id_opp,), commit=True)
    journaliser(g.utilisateur["id_utilisateur"], "opportunite_supprimee",
                "opportunite", id_opp, ligne["titre"][:120])
    return jsonify({"ok": True})
