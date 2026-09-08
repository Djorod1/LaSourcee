"""Création du premier compte administrateur au démarrage.

Sur un hébergement serverless, il n'y a pas de console où lancer
``gerer_admins.py`` : le seul canal de configuration est la variable
d'environnement. Ce module crée donc le compte d'administration à partir
de deux variables, une seule fois.

    ADMIN_EMAIL        adresse du compte
    ADMIN_MOTDEPASSE   mot de passe initial

L'opération est idempotente : si le compte existe déjà, rien n'est
touché — ni son mot de passe, ni son rôle. Redémarrer l'application ne
peut donc pas réinitialiser un mot de passe qui aurait été changé
depuis, et retirer les variables après coup ne supprime pas le compte.

Le compte est créé avec ``doit_changer_mdp`` : le mot de passe passé par
variable d'environnement n'est qu'un sésame d'ouverture, l'interface
impose d'en choisir un autre à la première connexion.
"""

import logging
import os

from models.db import recuperer_un, executer, curseur
from utils.auth_helpers import hacher_mot_de_passe
from utils.securite import mot_de_passe_valide

logger = logging.getLogger("lasourcee.amorcage")


def creer_admin_initial(app):
    """Crée le compte d'administration si les variables sont fournies.

    Ne lève jamais : un échec ici ne doit pas empêcher le site de
    répondre. Il est journalisé, et le compte pourra être créé
    autrement.
    """
    email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    motdepasse = os.getenv("ADMIN_MOTDEPASSE") or ""
    if not email or not motdepasse:
        return

    ok, motif = mot_de_passe_valide(motdepasse)
    if not ok:
        logger.error("ADMIN_MOTDEPASSE refusé : %s", motif)
        return

    prenom = (os.getenv("ADMIN_PRENOM") or "Administrateur").strip()
    nom = (os.getenv("ADMIN_NOM") or "").strip()

    try:
        with app.app_context():
            existant = recuperer_un(
                "SELECT id_utilisateur, est_admin FROM utilisateur "
                "WHERE email = %s", (email,))

            if existant and existant.get("est_admin"):
                return                      # déjà en place, on ne touche à rien

            if existant:
                # Le compte existe sans les droits : on les accorde, sans
                # toucher au mot de passe que la personne utilise déjà.
                executer(
                    "UPDATE utilisateur SET role = 'super_admin', "
                    "est_admin = 1, est_actif = 1 WHERE id_utilisateur = %s",
                    (existant["id_utilisateur"],), commit=True)
                logger.info("Droits d'administration accordés à %s", email)
                return

            with curseur(commit=True) as cur:
                cur.execute(
                    """INSERT INTO utilisateur
                          (prenom, nom, email, mot_de_passe, role,
                           est_admin, est_actif, email_verifie,
                           doit_changer_mdp)
                       VALUES (%s, %s, %s, %s, 'super_admin', 1, 1, 1, 1)""",
                    (prenom, nom, email, hacher_mot_de_passe(motdepasse)),
                )
            logger.info(
                "Compte d'administration créé pour %s. Le mot de passe "
                "devra être changé à la première connexion.", email)

    except Exception as exc:
        logger.error("Création du compte d'administration impossible : %s", exc)
