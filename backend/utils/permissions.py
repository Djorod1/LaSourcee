"""Droits d'administration, par domaine plutot qu'en bloc.

Jusqu'ici un seul drapeau, ``est_admin``, ouvrait tout : la moderation,
le journal d'audit, la configuration du serveur, la liste complete des
comptes. Confier la moderation a quelqu'un revenait donc a lui confier
aussi les adresses de tous les membres et les reglages de la plateforme.

Chaque ecran demande desormais son propre droit. Un compte peut moderer
sans lire le journal, ou valider des referents sans toucher aux comptes.

Deux regles gouvernent le reste :

  - **Le super administrateur a tout**, sans qu'on ait a l'ecrire. Lui
    retirer un droit par megarde fermerait la porte a la seule personne
    capable de la rouvrir.
  - **Un droit absent est refuse.** Une liste vide ne veut pas dire
    « tout », elle veut dire « rien » : l'inverse laisserait un compte
    mal configure avec les pleins pouvoirs.

Les comptes crees avant l'existence de ces droits font exception : leur
colonne est vide alors qu'ils administraient tout. Ils gardent
l'ensemble des droits, faute de quoi une mise a jour verrouillerait
l'equipe hors de son propre site. Ils sont reconnaissables a ce que la
colonne vaut NULL, et non a une liste vide, qui est un choix explicite.
"""

import json
from functools import wraps

from flask import g, jsonify

from utils.auth_helpers import connexion_requise

# Un droit par ecran d'administration, plus l'export, qui merite le
# sien : telecharger la base entiere n'est pas la meme chose que la
# consulter a l'ecran.
#
# Chaque droit porte un nom lisible et une phrase qui dit ce qu'il
# ouvre, et surtout ce qu'il donne a voir. Une liste de mots-cles nus se
# coche au hasard : personne ne sait ce que « audit » recouvre avant de
# l'avoir accorde, et l'on decouvre trop tard qu'il donnait acces aux
# adresses de tous les membres.
#
# « portee » classe le droit par ce qu'il engage, pour que l'ecran les
# presente dans cet ordre plutot qu'en vrac.
PERMISSIONS_DETAIL = {
    "signalements": {
        "nom": "Modération",
        "description": "Examiner les contenus signalés, les retirer, "
                       "avertir ou suspendre leur auteur.",
        "portee": "animation",
    },
    "referents": {
        "nom": "Validation des référents",
        "description": "Lire les dossiers de candidature et accorder le "
                       "badge de référent vérifié.",
        "portee": "animation",
    },
    "categories": {
        "nom": "Secteurs d'activité",
        "description": "Ajouter, renommer ou retirer les secteurs "
                       "proposés aux membres.",
        "portee": "animation",
    },
    "utilisateurs": {
        "nom": "Comptes des membres",
        "description": "Consulter l'annuaire complet, les adresses "
                       "e-mail, suspendre ou supprimer un compte.",
        "portee": "sensible",
    },
    "audit": {
        "nom": "Journal d'administration",
        "description": "Lire qui a fait quoi, quand, et depuis quelle "
                       "adresse IP.",
        "portee": "sensible",
    },
    "export": {
        "nom": "Export des données",
        "description": "Télécharger la base : comptes, contenus, "
                       "signalements, journal. Les fichiers sortent de "
                       "la plateforme.",
        "portee": "sensible",
    },
    "diagnostic": {
        "nom": "Configuration du serveur",
        "description": "Voir l'état du serveur, l'hébergement, l'envoi "
                       "d'e-mails et les identifiants de connexion "
                       "externes.",
        "portee": "sensible",
    },
    "administrateurs": {
        "nom": "Gestion des administrateurs",
        "description": "Nommer d'autres administrateurs et fixer leurs "
                       "droits. Ce droit permet de s'en donner d'autres.",
        "portee": "critique",
    },
}

# Ordre d'affichage : du plus courant au plus lourd de consequences.
ORDRE_PORTEE = {"animation": 0, "sensible": 1, "critique": 2}

# Compatibilite : la forme simple {cle: description} reste servie.
PERMISSIONS = {cle: d["description"]
               for cle, d in PERMISSIONS_DETAIL.items()}

# Ce qu'on accorde par defaut a un nouvel administrateur : de quoi
# animer la plateforme, sans le journal, la configuration ni l'export,
# qui touchent a la vie privee des membres ou aux secrets du serveur.
PERMISSIONS_PAR_DEFAUT = ["utilisateurs", "referents", "signalements",
                          "categories"]


def permissions_de(utilisateur):
    """Liste effective des droits d'un compte."""
    if not utilisateur or not utilisateur.get("est_admin"):
        return []
    if utilisateur.get("role") == "super_admin":
        return list(PERMISSIONS)

    brut = utilisateur.get("permissions")
    if brut is None:
        # Compte anterieur aux droits par domaine : il administrait tout.
        return list(PERMISSIONS)
    try:
        liste = json.loads(brut) if isinstance(brut, str) else brut
    except (ValueError, TypeError):
        return []
    if not isinstance(liste, list):
        return []
    return [p for p in liste if p in PERMISSIONS]


def a_le_droit(utilisateur, cle):
    return cle in permissions_de(utilisateur)


def permission_requise(cle):
    """Reserve une route a un droit precis.

    Remplace ``admin_requis`` la ou un domaine est en jeu. Le message
    d'erreur nomme le droit manquant : « acces refuse » sans autre
    precision laisse chercher, et fait souvent conclure a une panne.
    """
    if cle not in PERMISSIONS:
        raise ValueError(f"Droit inconnu : {cle}")

    def decorateur(fonction):
        @wraps(fonction)
        @connexion_requise
        def emballe(*args, **kwargs):
            if not g.utilisateur.get("est_admin"):
                return jsonify({
                    "erreur": "Acces reserve aux administrateurs."
                }), 403
            if not a_le_droit(g.utilisateur, cle):
                return jsonify({
                    "erreur": f"Votre compte n'a pas le droit « {cle} ». "
                              f"Demandez-le a un super administrateur."
                }), 403
            return fonction(*args, **kwargs)
        return emballe
    return decorateur


def normaliser(liste):
    """Nettoie une liste de droits recue d'un client."""
    if not isinstance(liste, list):
        return []
    return sorted({p for p in liste if p in PERMISSIONS})
