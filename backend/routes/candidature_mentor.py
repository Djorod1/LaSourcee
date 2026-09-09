"""Candidature au statut de mentor officiel.

Parcours complet :

  1. Un utilisateur connecté (étudiant ou mentor non vérifié) dépose sa
     candidature avec sa présentation, ses domaines d'expertise et son
     parcours professionnel.
  2. Les administrateurs sont prévenus par e-mail qu'une candidature
     attend leur validation.
  3. L'administrateur valide ou refuse depuis son espace.
  4. Le candidat est prévenu par e-mail de la décision. S'il est validé,
     son compte passe au rôle « mentor » avec le badge vérifié.
"""

import os

from flask import Blueprint, g, jsonify, request

from models.db import recuperer_un, recuperer_tous, executer, curseur
from utils.auth_helpers import connexion_requise
from utils.urls import url_publique
from utils import email as mod_email

bp_candidature = Blueprint("candidature", __name__, url_prefix="/api/mentors")


LONGUEUR_MIN_MOTIVATION = 80
LONGUEUR_MIN_BIO = 40


# ---------------------------------------------------------------------------
# Dépôt de candidature
# ---------------------------------------------------------------------------

@bp_candidature.post("/candidature")
@connexion_requise
def deposer_candidature():
    """Dépose ou met à jour une candidature au statut de mentor."""
    d = request.get_json(silent=True) or {}
    id_user = g.utilisateur["id_utilisateur"]

    bio          = (d.get("bio") or "").strip()
    motivation   = (d.get("motivation") or "").strip()
    profession   = (d.get("profession") or "").strip()
    organisation = (d.get("organisation") or "").strip()
    annees       = d.get("annees_experience")
    lien_pro     = (d.get("lien_professionnel") or "").strip()
    secteurs     = d.get("secteurs") or []
    experiences  = d.get("experiences") or []

    # ---- Contrôles de recevabilité --------------------------------------
    if len(bio) < LONGUEUR_MIN_BIO:
        return jsonify({"erreur":
            f"Votre présentation doit faire au moins {LONGUEUR_MIN_BIO} "
            f"caractères."}), 400
    if len(motivation) < LONGUEUR_MIN_MOTIVATION:
        return jsonify({"erreur":
            f"Expliquez votre motivation en au moins "
            f"{LONGUEUR_MIN_MOTIVATION} caractères."}), 400
    if not profession:
        return jsonify({"erreur": "Indiquez votre profession actuelle."}), 400
    if not secteurs:
        return jsonify({"erreur":
            "Choisissez au moins un domaine d'expertise."}), 400
    try:
        annees = int(annees or 0)
    except (TypeError, ValueError):
        annees = 0
    if annees < 1:
        return jsonify({"erreur":
            "Indiquez au moins une année d'expérience."}), 400

    profil = recuperer_un(
        "SELECT prenom, nom, email, role FROM utilisateur "
        "WHERE id_utilisateur = %s", (id_user,),
    )
    if not profil:
        return jsonify({"erreur": "Compte introuvable."}), 404

    # Déjà mentor vérifié : rien à faire
    details = recuperer_un(
        "SELECT est_verifie FROM mentor_details WHERE id_utilisateur = %s",
        (id_user,),
    )
    if details and details["est_verifie"]:
        return jsonify({"erreur":
            "Votre compte référent est déjà vérifié."}), 409

    # ---- Enregistrement --------------------------------------------------
    with curseur(commit=True) as cur:
        cur.execute(
            "UPDATE utilisateur SET bio = %s, role = 'mentor' "
            "WHERE id_utilisateur = %s",
            (bio, id_user),
        )

        if details:
            cur.execute(
                "UPDATE mentor_details SET anciennete = %s, dispo = 'disponible' "
                "WHERE id_utilisateur = %s",
                (f"{annees} an{'s' if annees > 1 else ''}", id_user),
            )
        else:
            cur.execute(
                "INSERT INTO mentor_details "
                "(id_utilisateur, est_verifie, dispo, anciennete) "
                "VALUES (%s, 0, 'disponible', %s)",
                (id_user, f"{annees} an{'s' if annees > 1 else ''}"),
            )

        # Domaines d'expertise : remplacement complet
        cur.execute(
            "DELETE FROM utilisateur_secteur WHERE id_utilisateur = %s",
            (id_user,),
        )
        for id_secteur in secteurs:
            try:
                cur.execute(
                    "INSERT INTO utilisateur_secteur "
                    "(id_utilisateur, id_secteur) VALUES (%s, %s)",
                    (id_user, int(id_secteur)),
                )
            except (TypeError, ValueError):
                continue

        # Parcours : poste actuel puis expériences complémentaires
        cur.execute("DELETE FROM experience WHERE id_utilisateur = %s",
                    (id_user,))
        intitule = profession + (f", {organisation}" if organisation else "")
        cur.execute(
            "INSERT INTO experience "
            "(id_utilisateur, type_experience, intitule, periode, ordre) "
            "VALUES (%s, 'poste', %s, %s, 0)",
            (id_user, intitule[:150], f"{annees} an{'s' if annees > 1 else ''}"),
        )
        for i, exp in enumerate(experiences[:5], start=1):
            titre = (exp.get("intitule") or "").strip()
            if not titre:
                continue
            cur.execute(
                "INSERT INTO experience "
                "(id_utilisateur, type_experience, intitule, periode, ordre) "
                "VALUES (%s, %s, %s, %s, %s)",
                (id_user,
                 exp.get("type") if exp.get("type") in ("poste", "diplome")
                 else "autre",
                 titre[:150], (exp.get("periode") or "")[:60], i),
            )

    _prevenir_administrateurs(profil, profession, organisation, annees,
                              motivation, lien_pro)
    _accuser_reception(profil)

    return jsonify({
        "ok": True,
        "statut": "en_attente",
        "message": "Votre candidature a bien été transmise. "
                   "Un administrateur l'examinera sous peu.",
    }), 201


@bp_candidature.get("/ma-candidature")
@connexion_requise
def etat_candidature():
    """Renvoie l'état de la candidature de l'utilisateur connecté."""
    id_user = g.utilisateur["id_utilisateur"]
    u = recuperer_un(
        "SELECT role FROM utilisateur WHERE id_utilisateur = %s", (id_user,),
    )
    details = recuperer_un(
        "SELECT est_verifie, dispo, anciennete, note_moyenne, nb_reponses "
        "FROM mentor_details WHERE id_utilisateur = %s", (id_user,),
    )

    if not details:
        return jsonify({"statut": "aucune",
                        "message": "Vous n'avez pas encore déposé de candidature."})
    if details["est_verifie"]:
        return jsonify({
            "statut": "validee",
            "message": "Votre compte référent est vérifié.",
            "details": details,
        })
    return jsonify({
        "statut": "en_attente",
        "message": "Votre candidature est en cours d'examen par un administrateur.",
        "details": details,
    })


# ---------------------------------------------------------------------------
# Notifications par e-mail
# ---------------------------------------------------------------------------

def _prevenir_administrateurs(profil, profession, organisation, annees,
                              motivation, lien_pro):
    """Alerte tous les administrateurs qu'une candidature attend."""
    admins = recuperer_tous(
        "SELECT prenom, email FROM utilisateur "
        "WHERE (role IN ('admin','super_admin') OR est_admin = 1) "
        "AND est_actif = 1"
    )
    if not admins:
        return

    candidat = f"{profil['prenom']} {profil['nom']}"
    poste = profession + (f" chez {organisation}" if organisation else "")
    lien_admin = url_publique("/index.html")

    for admin in admins:
        html = mod_email.gabarit_html(
            "Nouvelle candidature de référent",
            [f"Bonjour {admin['prenom']},",
             f"<b>{candidat}</b> souhaite devenir référent sur LaSourcee.",
             f"<b>Poste :</b> {poste}<br>"
             f"<b>Expérience :</b> {annees} an{'s' if annees > 1 else ''}<br>"
             f"<b>Contact :</b> {profil['email']}"
             + (f"<br><b>Profil professionnel :</b> {lien_pro}" if lien_pro else ""),
             f"<b>Motivation :</b><br><i>{motivation[:600]}</i>"],
            bouton_texte="Examiner la candidature",
            bouton_lien=lien_admin,
            note_bas="Espace d'administration → Validation référents.",
        )
        texte = (
            f"Bonjour {admin['prenom']},\n\n"
            f"{candidat} souhaite devenir référent sur LaSourcee.\n\n"
            f"Poste       : {poste}\n"
            f"Experience  : {annees} an(s)\n"
            f"Contact     : {profil['email']}\n\n"
            f"Motivation :\n{motivation[:600]}\n\n"
            f"Validez ou refusez depuis l'espace d'administration :\n{lien_admin}\n"
        )
        mod_email.envoyer(admin["email"],
                          f"Candidature référent : {candidat}", texte,
                          corps_html=html)


def _accuser_reception(profil):
    """Confirme au candidat que sa demande est bien partie."""
    html = mod_email.gabarit_html(
        "Votre candidature a bien été reçue",
        [f"Bonjour {profil['prenom']},",
         "Nous avons bien reçu votre candidature au statut de "
         "<b>référent vérifié</b> sur LaSourcee.",
         "Un administrateur va l'examiner. Vous recevrez un e-mail dès "
         "qu'une décision sera prise, généralement sous quelques jours.",
         "En attendant, vous pouvez déjà répondre aux questions de la "
         "communauté : votre badge « vérifié » apparaîtra une fois la "
         "validation effectuée."],
        note_bas="Merci de contribuer à l'entraide entre les membres.",
    )
    texte = (
        f"Bonjour {profil['prenom']},\n\n"
        f"Nous avons bien recu votre candidature au statut de referent verifie "
        f"sur LaSourcee.\n\n"
        f"Un administrateur va l'examiner. Vous recevrez un e-mail des qu'une "
        f"decision sera prise.\n\n"
        f"L'equipe LaSourcee"
    )
    mod_email.envoyer(profil["email"],
                      "Votre candidature de référent sur LaSourcee", texte,
                      corps_html=html)


def notifier_decision(id_mentor, acceptee, motif=""):
    """Prévient le candidat de la décision de l'administrateur.

    Appelée depuis routes/admin.py après validation ou refus.
    """
    u = recuperer_un(
        "SELECT prenom, nom, email FROM utilisateur WHERE id_utilisateur = %s",
        (id_mentor,),
    )
    if not u:
        return False

    lien = url_publique("/index.html")

    if acceptee:
        html = mod_email.gabarit_html(
            "Vous êtes désormais référent vérifié",
            [f"Félicitations {u['prenom']},",
             "Votre candidature a été <b>acceptée</b>. Votre compte porte "
             "maintenant le badge <b>Référent vérifié</b>, visible par tous "
             "les membres de la plateforme.",
             "Vous pouvez répondre aux questions, être suivi par les "
             "bénéficiaires et apparaître dans l'annuaire des référents."],
            bouton_texte="Accéder à mon espace référent",
            bouton_lien=lien,
            note_bas="Merci de faire vivre l'entraide sur LaSourcee.",
        )
        texte = (
            f"Felicitations {u['prenom']},\n\n"
            f"Votre candidature de referent a ete acceptee. Votre compte porte "
            f"desormais le badge Referent verifie.\n\n"
            f"Connectez-vous : {lien}\n\nL'equipe LaSourcee"
        )
        sujet = "Votre candidature de référent est acceptée"
    else:
        raison = (f"<br><br><b>Motif :</b> {motif}" if motif else "")
        html = mod_email.gabarit_html(
            "Suite à votre candidature de référent",
            [f"Bonjour {u['prenom']},",
             "Après examen, votre candidature au statut de référent vérifié "
             "n'a pas été retenue pour le moment." + raison,
             "Votre compte reste actif : vous pouvez continuer à poser des "
             "questions et à participer à la communauté. Vous pourrez "
             "déposer une nouvelle candidature plus tard, en détaillant "
             "davantage votre parcours professionnel."],
            bouton_texte="Retourner sur LaSourcee",
            bouton_lien=lien,
        )
        texte = (
            f"Bonjour {u['prenom']},\n\n"
            f"Apres examen, votre candidature au statut de referent verifie n'a "
            f"pas ete retenue pour le moment."
            + (f"\n\nMotif : {motif}" if motif else "")
            + f"\n\nVotre compte reste actif.\n\nL'equipe LaSourcee"
        )
        sujet = "Suite à votre candidature de référent"

    return mod_email.envoyer(u["email"], sujet, texte, corps_html=html)
