"""Fermeture d'un compte qui porte des décisions d'administration.

Le journal d'administration référence son auteur par une clé déclarée
en cascade : effacer un compte d'administrateur effaçait donc toutes ses
décisions, au moment précis où l'on aurait besoin de les relire. Une
cascade ne se modifie pas sans reconstruire la table ; la parade est
donc ici, dans le code : un compte qui a décidé n'est pas effacé, il
est vidé de ce qui identifie la personne et fermé.

Deux chemins y mènent : la suppression par l'administration, et la
suppression par le titulaire lui-même. Le second effaçait le journal
d'un administrateur qui fermait son propre compte.
"""

import secrets

from models.db import executer, recuperer_un

# Adresse de remplacement : le domaine « .invalid » est réservé et ne
# recevra jamais de courrier. Elle sert aussi à reconnaître un compte
# vidé, que rien ne doit rouvrir.
DOMAINE_VIDE = "lasourcee.invalid"


def a_des_decisions(id_user):
    """Nombre de lignes du journal d'administration dont il est l'auteur."""
    return (recuperer_un(
        "SELECT COUNT(*) AS n FROM audit_admin WHERE id_acteur = %s",
        (id_user,)) or {}).get("n", 0) or 0


def est_vide(email):
    """Vrai pour l'adresse de remplacement d'un compte anonymisé."""
    return (email or "").endswith("@" + DOMAINE_VIDE)


def anonymiser(id_user):
    """Vide le compte de ses données personnelles et le ferme pour de bon.

    Le mot de passe est remplacé par un hachage aléatoire que personne ne
    connaît, et les accès annexes (lien Google, sessions, liens de
    réinitialisation ou de confirmation) sont détruits : le compte vidé
    gardait sinon son ancien mot de passe, c'est-à-dire une porte ouverte
    vers un compte sans titulaire.
    """
    from utils.auth_helpers import hacher_mot_de_passe
    executer(
        """UPDATE utilisateur
              SET prenom = 'Compte', nom = 'supprimé',
                  email = %s, bio = NULL, photo_url = NULL,
                  telephone = NULL, etablissement = NULL,
                  filiere = NULL, profil_pro = NULL,
                  est_actif = 0, est_admin = 0, role = 'visiteur',
                  permissions = '[]', mot_de_passe = %s
            WHERE id_utilisateur = %s""",
        (f"supprime-{id_user}@{DOMAINE_VIDE}",
         hacher_mot_de_passe(secrets.token_urlsafe(32)), id_user),
        commit=True)
    for table in ("session_web", "identite_externe",
                  "reinitialisation_mdp", "verification_email"):
        executer(f"DELETE FROM {table} WHERE id_utilisateur = %s",
                 (id_user,), commit=True)
