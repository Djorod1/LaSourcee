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

# Un droit par ecran d'administration, plus l'export, qui merite le sien :
# telecharger la base entiere n'est pas la meme chose que la consulter.
PERMISSIONS = {
    "utilisateurs": "Consulter et gerer les comptes",
    "referents": "Examiner les candidatures de referent",
    "signalements": "Moderer les contenus signales",
    "categories": "Gerer les secteurs d'activite",
    "audit": "Consulter le journal des actions d'administration",
    "diagnostic": "Voir la configuration du serveur",
    "export": "Telecharger les donnees de la plateforme",
    "administrateurs": "Creer des administrateurs et fixer leurs droits",
}

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
