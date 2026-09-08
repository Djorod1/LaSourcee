#!/usr/bin/env python3
"""Gestion des comptes administrateurs de LaSourcee.

Crée les comptes administrateurs officiels, génère un mot de passe
temporaire fort pour chacun et leur envoie l'e-mail d'invitation.

Utilisation (depuis le dossier backend/) :

    python gerer_admins.py creer          Crée les admins officiels et
                                          envoie les invitations
    python gerer_admins.py lister         Affiche les administrateurs
    python gerer_admins.py ajouter <email> "<Prénom>" "<Nom>"
                                          Ajoute un administrateur
    python gerer_admins.py reinitialiser <email>
                                          Régénère le mot de passe et
                                          renvoie l'e-mail
    python gerer_admins.py tester-email <email>
                                          Envoie un e-mail de test

Le mot de passe n'est jamais stocké en clair : il est haché avec bcrypt
et affiché une seule fois dans la console, en plus d'être envoyé par
e-mail à la personne concernée.
"""

import os
import secrets
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import creer_application                       # noqa: E402
from models.db import recuperer_un, recuperer_tous, executer, curseur  # noqa: E402
from utils.auth_helpers import hacher_mot_de_passe      # noqa: E402
from utils.urls import url_publique                     # noqa: E402
from utils import email as mod_email                    # noqa: E402


# ---------------------------------------------------------------------------
# Administrateurs officiels de la plateforme
# ---------------------------------------------------------------------------

ADMINS_OFFICIELS = [
    {"email": "toyohounsogbe1@gmail.com",    "prenom": "Kouessi",  "nom": "TOYOHOUNSOGBE"},
    {"email": "theophiledounon@gmail.com",   "prenom": "Théophile", "nom": "DOUNON"},
    {"email": "espoirmariano@gmail.com",     "prenom": "Mariano",  "nom": "DOSSOUGAN"},
    {"email": "rodriguedjossou93@gmail.com", "prenom": "Rodrigue", "nom": "DJOSSOU"},
]

# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def generer_mot_de_passe(longueur=14):
    """Mot de passe temporaire fort, sans caractères ambigus (O/0, l/1)."""
    minuscules = "abcdefghijkmnopqrstuvwxyz"
    majuscules = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    chiffres = "23456789"
    symboles = "!@#$%&*?"
    alphabet = minuscules + majuscules + chiffres + symboles

    # Garantit au moins un caractère de chaque catégorie
    mdp = [
        secrets.choice(minuscules), secrets.choice(majuscules),
        secrets.choice(chiffres), secrets.choice(symboles),
    ]
    mdp += [secrets.choice(alphabet) for _ in range(longueur - 4)]
    secrets.SystemRandom().shuffle(mdp)
    return "".join(mdp)


def _assurer_colonne_changement_mdp():
    """Ajoute la colonne doit_changer_mdp si elle n'existe pas encore.

    Permet d'imposer le changement du mot de passe temporaire à la
    première connexion. Silencieux si la colonne est déjà présente.
    """
    try:
        executer(
            "ALTER TABLE utilisateur ADD COLUMN doit_changer_mdp INTEGER "
            "NOT NULL DEFAULT 0",
            commit=True,
        )
        print("  Colonne doit_changer_mdp ajoutée à la table utilisateur.")
    except Exception:
        pass  # la colonne existe déjà


def _envoyer_invitation(prenom, nom, email, mot_de_passe, nouveau=True):
    """Envoie l'e-mail d'invitation ou de réinitialisation."""
    lien = url_publique("/index.html")

    if nouveau:
        titre = "Votre compte administrateur LaSourcee"
        intro = (f"Bonjour {prenom},<br><br>"
                 f"Un compte <b>administrateur</b> vient d'être créé pour vous "
                 f"sur la plateforme LaSourcee.")
    else:
        titre = "Nouveau mot de passe administrateur LaSourcee"
        intro = (f"Bonjour {prenom},<br><br>"
                 f"Le mot de passe de votre compte administrateur LaSourcee "
                 f"vient d'être réinitialisé.")

    identifiants = (
        f'<b>Adresse e-mail :</b> {email}<br>'
        f'<b>Mot de passe temporaire :</b> '
        f'<code style="background:#f0f0f0;padding:3px 8px;border-radius:4px;'
        f'font-size:15px;letter-spacing:0.5px;">{mot_de_passe}</code>'
    )

    droits = (
        "En tant qu'administrateur, vous pouvez : valider les mentors, "
        "modérer les contenus signalés, gérer les comptes utilisateurs, "
        "administrer les catégories et consulter le journal d'activité."
    )

    html = mod_email.gabarit_html(
        titre,
        [intro, identifiants, droits],
        bouton_texte="Me connecter à LaSourcee",
        bouton_lien=lien,
        note_bas=("Pour votre sécurité, changez ce mot de passe dès votre "
                  "première connexion (menu profil → Paramètres → Sécurité). "
                  "Ne transmettez ces identifiants à personne."),
    )

    texte = (
        f"Bonjour {prenom},\n\n"
        f"{'Un compte administrateur vient d’être créé pour vous' if nouveau else 'Votre mot de passe a été réinitialisé'} "
        f"sur la plateforme LaSourcee.\n\n"
        f"Adresse e-mail      : {email}\n"
        f"Mot de passe        : {mot_de_passe}\n"
        f"Adresse du site     : {lien}\n\n"
        f"{droits}\n\n"
        f"Pour votre sécurité, changez ce mot de passe dès votre première\n"
        f"connexion (menu profil → Paramètres → Sécurité).\n"
        f"Ne transmettez ces identifiants à personne.\n\n"
        f"L'équipe LaSourcee"
    )

    return mod_email.envoyer(email, titre, texte, corps_html=html)


def _creer_ou_mettre_a_jour(prenom, nom, email, role="super_admin"):
    """Crée le compte s'il n'existe pas, sinon le promeut administrateur.

    Retourne (mot_de_passe, est_nouveau).
    """
    email = email.strip().lower()
    mdp = generer_mot_de_passe()
    hache = hacher_mot_de_passe(mdp)

    existant = recuperer_un(
        "SELECT id_utilisateur, role FROM utilisateur WHERE email = %s",
        (email,),
    )

    if existant:
        executer(
            "UPDATE utilisateur SET role = %s, est_admin = 1, est_actif = 1, "
            "email_verifie = 1, mot_de_passe = %s, doit_changer_mdp = 1 "
            "WHERE id_utilisateur = %s",
            (role, hache, existant["id_utilisateur"]),
            commit=True,
        )
        return mdp, False

    with curseur(commit=True) as cur:
        cur.execute(
            "INSERT INTO utilisateur "
            "(prenom, nom, email, mot_de_passe, role, est_admin, est_actif, "
            " email_verifie, doit_changer_mdp) "
            "VALUES (%s, %s, %s, %s, %s, 1, 1, 1, 1)",
            (prenom, nom, email, hache, role),
        )
    return mdp, True


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

def commande_creer():
    print("\n" + "=" * 66)
    print("  CRÉATION DES COMPTES ADMINISTRATEURS LASOURCEE")
    print("=" * 66)

    ok_smtp, raison = mod_email.configuration_valide()
    if ok_smtp:
        print("  Envoi des e-mails : SMTP configuré, les invitations partiront.")
    else:
        print(f"  Envoi des e-mails : MODE CONSOLE — {raison}")
        print("  Les mots de passe s'afficheront ci-dessous, à transmettre")
        print("  manuellement. Configurez SMTP dans backend/.env pour un envoi réel.")
    print("=" * 66 + "\n")

    _assurer_colonne_changement_mdp()
    resultats = []

    for admin in ADMINS_OFFICIELS:
        mdp, nouveau = _creer_ou_mettre_a_jour(
            admin["prenom"], admin["nom"], admin["email"],
        )
        envoye = _envoyer_invitation(
            admin["prenom"], admin["nom"], admin["email"], mdp, nouveau,
        )
        resultats.append({
            "email": admin["email"], "nom": f"{admin['prenom']} {admin['nom']}",
            "mdp": mdp, "nouveau": nouveau, "envoye": envoye,
        })
        etat = "créé" if nouveau else "mis à jour"
        courriel = "e-mail envoyé" if envoye else "e-mail NON envoyé"
        print(f"  [{etat:^12}] {admin['email']:<34} {courriel}")

    print("\n" + "=" * 66)
    print("  IDENTIFIANTS (à conserver en lieu sûr, affichés une seule fois)")
    print("=" * 66)
    for r in resultats:
        print(f"\n  {r['nom']}")
        print(f"    Adresse      : {r['email']}")
        print(f"    Mot de passe : {r['mdp']}")
    print("\n" + "=" * 66)
    print("  Chaque administrateur devra changer son mot de passe à la")
    print("  première connexion (Paramètres → Sécurité).")
    print("=" * 66 + "\n")


def commande_lister():
    lignes = recuperer_tous(
        "SELECT id_utilisateur, prenom, nom, email, role, est_actif, "
        "derniere_co FROM utilisateur "
        "WHERE role IN ('admin','super_admin') OR est_admin = 1 "
        "ORDER BY role DESC, nom"
    )
    print("\n" + "=" * 78)
    print("  ADMINISTRATEURS DE LA PLATEFORME")
    print("=" * 78)
    if not lignes:
        print("  Aucun administrateur. Lancez : python gerer_admins.py creer")
    else:
        print(f"  {'Nom':<26} {'Adresse e-mail':<32} {'Rôle':<12} {'Actif'}")
        print("  " + "-" * 74)
        for l in lignes:
            nom = f"{l['prenom']} {l['nom']}"[:25]
            actif = "oui" if l["est_actif"] else "non"
            print(f"  {nom:<26} {l['email']:<32} {l['role']:<12} {actif}")
    print("=" * 78 + "\n")


def commande_ajouter(email, prenom, nom):
    _assurer_colonne_changement_mdp()
    mdp, nouveau = _creer_ou_mettre_a_jour(prenom, nom, email)
    envoye = _envoyer_invitation(prenom, nom, email, mdp, nouveau)
    print(f"\n  Compte {'créé' if nouveau else 'mis à jour'} : {email}")
    print(f"  Mot de passe temporaire : {mdp}")
    print(f"  E-mail : {'envoyé' if envoye else 'NON envoyé (voir la configuration SMTP)'}\n")


def commande_reinitialiser(email):
    email = email.strip().lower()
    u = recuperer_un(
        "SELECT prenom, nom FROM utilisateur WHERE email = %s", (email,),
    )
    if not u:
        print(f"\n  Aucun compte avec l'adresse {email}\n")
        return
    _assurer_colonne_changement_mdp()
    mdp, _ = _creer_ou_mettre_a_jour(u["prenom"], u["nom"], email)
    envoye = _envoyer_invitation(u["prenom"], u["nom"], email, mdp, nouveau=False)
    print(f"\n  Mot de passe réinitialisé pour {email}")
    print(f"  Nouveau mot de passe : {mdp}")
    print(f"  E-mail : {'envoyé' if envoye else 'NON envoyé'}\n")


def commande_tester_email(destinataire):
    ok_cfg, raison = mod_email.configuration_valide()
    print(f"\n  Configuration : {raison}")
    html = mod_email.gabarit_html(
        "Test de configuration",
        ["Si vous lisez ce message, l'envoi d'e-mails de LaSourcee "
         "fonctionne correctement.",
         "Vous pouvez maintenant créer les comptes administrateurs et "
         "activer la vérification d'adresse à l'inscription."],
        note_bas="Message de test envoyé depuis gerer_admins.py",
    )
    ok = mod_email.envoyer(
        destinataire, "LaSourcee, test d'envoi",
        "Si vous lisez ce message, l'envoi d'e-mails fonctionne.",
        corps_html=html,
    )
    print(f"  Envoi à {destinataire} : {'réussi' if ok else 'ÉCHEC'}")
    if not ok:
        print("  Vérifiez EMAIL_MODE, SMTP_HOTE, SMTP_UTILISATEUR et "
              "SMTP_MOTDEPASSE dans backend/.env")
    print()


def main():
    args = sys.argv[1:]
    commande = args[0] if args else "aide"

    app = creer_application()
    with app.app_context():
        if commande == "creer":
            commande_creer()
        elif commande == "lister":
            commande_lister()
        elif commande == "ajouter" and len(args) >= 4:
            commande_ajouter(args[1], args[2], args[3])
        elif commande == "reinitialiser" and len(args) >= 2:
            commande_reinitialiser(args[1])
        elif commande == "tester-email" and len(args) >= 2:
            commande_tester_email(args[1])
        else:
            print(__doc__)


if __name__ == "__main__":
    main()
