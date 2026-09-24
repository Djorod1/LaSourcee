"""Routes d'administration : tableau de bord, utilisateurs, secteurs,
référents, signalements, audit, administrateurs et exports."""

import json
from datetime import datetime

from flask import Blueprint, jsonify, request, g

from utils.noms import normaliser_nom
from models.db import recuperer_un, recuperer_tous, executer, curseur
from utils.auth_helpers import admin_requis
from utils.permissions import (PERMISSIONS, PERMISSIONS_PAR_DEFAUT,
                               permission_requise, permissions_de,
                               normaliser)
from utils.audit import journaliser
from services.notifications import notifier

bp_admin = Blueprint("admin", __name__, url_prefix="/api/admin")

ROLES_AUTORISES = {"visiteur", "etudiant", "mentor", "admin", "super_admin"}

# Rien n'empechait un administrateur ordinaire d'agir sur un compte
# d'administration, y compris celui d'un super administrateur : le
# retrograder, changer son adresse e-mail pour ensuite en demander le
# mot de passe, ou le suspendre. Ces trois gardes ferment la porte.


def _compte(id_user):
    return recuperer_un(
        "SELECT id_utilisateur, prenom, nom, email, role, est_admin "
        "FROM utilisateur WHERE id_utilisateur = %s", (id_user,))


def _refus_sur_administrateur(cible, verbe):
    """Refuse d'agir sur un compte d'administration, sauf super admin.

    Renvoie un message, ou None si l'action est permise.
    """
    if not cible:
        return None
    vise_admin = cible.get("role") in ("admin", "super_admin") \
        or cible.get("est_admin")
    if not vise_admin:
        return None
    if g.utilisateur.get("role") == "super_admin":
        return None
    return (f"Seul un super administrateur peut {verbe} le compte d'un "
            "autre administrateur.")


def _dernier_super_admin(id_user):
    """Vrai si retirer ce compte laisserait la plateforme sans pilote."""
    if not (_compte(id_user) or {}).get("role") == "super_admin":
        return False
    restants = (recuperer_un(
        "SELECT COUNT(*) AS n FROM utilisateur "
        "WHERE role = 'super_admin' AND est_actif = 1 "
        "  AND id_utilisateur <> %s", (id_user,)) or {}).get("n", 0)
    return restants == 0


# ============================================================
# TABLEAU DE BORD
# ============================================================

@bp_admin.get("/dashboard")
@admin_requis
def dashboard():
    """Indicateurs principaux calculés en temps réel sur la base."""

    def n(sql, params=()):
        ligne = recuperer_un(sql, params)
        return ligne["n"] if ligne else 0

    return jsonify({
        "utilisateurs":     n("SELECT COUNT(*) AS n FROM utilisateur"),
        "mentors":          n("SELECT COUNT(*) AS n FROM utilisateur WHERE role='mentor'"),
        "etudiants":        n("SELECT COUNT(*) AS n FROM utilisateur WHERE role='etudiant'"),
        "admins":           n("SELECT COUNT(*) AS n FROM utilisateur WHERE role IN ('admin','super_admin')"),
        "questions":        n("SELECT COUNT(*) AS n FROM question"),
        "reponses":         n("SELECT COUNT(*) AS n FROM reponse"),
        "signalements_ouverts": n(
            "SELECT COUNT(*) AS n FROM signalement WHERE statut = 'ouvert'"
        ),
        "mentors_a_verifier": n(
            "SELECT COUNT(*) AS n FROM mentor_details WHERE est_verifie = 0"
        ),
        "comptes_suspendus": n(
            "SELECT COUNT(*) AS n FROM utilisateur WHERE est_actif = 0"
        ),
    })


# ============================================================
# UTILISATEURS — CRUD complet
# ============================================================

@bp_admin.get("/utilisateurs")
@permission_requise("utilisateurs")
def lister_utilisateurs():
    """Annuaire administratif : filtres, recherche et pagination.

    La liste s'arrêtait à cinq cents comptes, sans page suivante ni
    total : passé ce seuil, les plus anciens devenaient inatteignables
    et rien ne le disait. Et la recherche comparait avec LIKE, qui
    distingue les majuscules sur PostgreSQL : chercher « djossou » ne
    trouvait pas « Djossou ».
    """
    role = request.args.get("role")
    actif = request.args.get("actif")
    verifie = request.args.get("verifie")
    recherche = (request.args.get("q") or "").strip()
    limite = min(max(request.args.get("limite", default=50, type=int), 1), 200)
    page = max(request.args.get("page", default=1, type=int), 1)

    conditions, params = [], []
    if role in ROLES_AUTORISES:
        conditions.append("u.role = %s"); params.append(role)
    if actif in ("0", "1"):
        conditions.append("u.est_actif = %s"); params.append(int(actif))
    if verifie in ("0", "1"):
        conditions.append("u.email_verifie = %s"); params.append(int(verifie))
    if recherche:
        conditions.append(
            "(LOWER(u.prenom) LIKE %s OR LOWER(u.nom) LIKE %s "
            " OR LOWER(u.email) LIKE %s)")
        m = f"%{recherche.lower()}%"
        params.extend([m, m, m])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    total = (recuperer_un(
        f"SELECT COUNT(*) AS n FROM utilisateur u {where}",
        tuple(params)) or {}).get("n", 0)

    lignes = recuperer_tous(
        f"""SELECT u.id_utilisateur, u.prenom, u.nom, u.email, u.role,
                   u.est_actif, u.email_verifie, u.cree_le, u.derniere_co,
                   u.derniere_activite, u.photo_url,
                   p.libelle AS pays
              FROM utilisateur u
         LEFT JOIN pays p ON p.id_pays = u.id_pays
            {where}
         ORDER BY u.cree_le DESC
            LIMIT %s OFFSET %s""",
        tuple(params) + (limite, (page - 1) * limite),
    )
    return jsonify({
        "utilisateurs": lignes,
        "total": total,
        "page": page,
        "par_page": limite,
        "pages": max(1, (total + limite - 1) // limite),
    })


@bp_admin.get("/utilisateurs/<int:id_user>")
@permission_requise("utilisateurs")
def detail_utilisateur(id_user):
    u = recuperer_un(
        """SELECT u.*, p.libelle AS pays_nom
             FROM utilisateur u
        LEFT JOIN pays p ON p.id_pays = u.id_pays
            WHERE u.id_utilisateur = %s""",
        (id_user,),
    )
    if not u:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404
    u.pop("mot_de_passe", None)  # jamais en sortie
    return jsonify(u)


@bp_admin.put("/utilisateurs/<int:id_user>")
@permission_requise("utilisateurs")
def modifier_utilisateur(id_user):
    d = request.get_json(silent=True) or {}
    champs = {
        "prenom": d.get("prenom"),
        "nom": d.get("nom"),
        "email": (d.get("email") or "").strip().lower() or None,
        "bio": d.get("bio"),
        "etudes": d.get("etudes"),
        "id_pays": d.get("id_pays"),
    }
    champs = {k: v for k, v in champs.items() if v is not None}
    if not champs:
        return jsonify({"erreur": "Aucun champ à modifier."}), 400

    cible = _compte(id_user)
    if not cible:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404
    refus = _refus_sur_administrateur(cible, "modifier")
    if refus:
        return jsonify({"erreur": refus}), 403

    # Changer l'adresse d'un compte suffit a en prendre le controle :
    # il reste a demander une reinitialisation de mot de passe sur la
    # nouvelle adresse. Elle est donc verifiee, tracee, et la personne
    # en est avertie.
    ancienne = cible.get("email")
    if "email" in champs:
        nouvelle = champs["email"]
        if "@" not in nouvelle or "." not in nouvelle.split("@")[-1]:
            return jsonify({"erreur": "Adresse e-mail invalide."}), 400
        if nouvelle == ancienne:
            champs.pop("email")

    for cle in ("prenom", "nom"):
        if cle in champs:
            propre = normaliser_nom(champs[cle])
            if not propre:
                return jsonify({"erreur": "Le prénom et le nom doivent "
                                          "contenir des lettres."}), 400
            champs[cle] = propre

    fragments = ", ".join(f"{k} = %s" for k in champs)
    try:
        executer(
            f"UPDATE utilisateur SET {fragments} WHERE id_utilisateur = %s",
            list(champs.values()) + [id_user], commit=True,
        )
    except Exception:
        return jsonify({"erreur": "Conflit (e-mail déjà utilisé ?)."}), 409
    detail = ",".join(champs.keys())
    if "email" in champs:
        detail += f" | adresse : {ancienne} vers {champs['email']}"
        notifier(id_user,
                 "L'adresse e-mail de votre compte a été changée par "
                 "l'administration. Si vous n'êtes pas à l'origine de ce "
                 "changement, écrivez immédiatement à l'équipe.",
                 type_notif="systeme")
    journaliser(g.utilisateur["id_utilisateur"], "modifier_utilisateur",
                "utilisateur", id_user, detail)
    return jsonify({"ok": True})


@bp_admin.post("/utilisateurs/<int:id_user>/suspendre")
@permission_requise("utilisateurs")
def suspendre(id_user):
    if id_user == g.utilisateur["id_utilisateur"]:
        return jsonify({"erreur": "Vous ne pouvez pas suspendre votre "
                                  "propre compte : personne ne pourrait "
                                  "vous rouvrir la porte."}), 400
    cible = _compte(id_user)
    if not cible:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404
    refus = _refus_sur_administrateur(cible, "suspendre")
    if refus:
        return jsonify({"erreur": refus}), 403
    if _dernier_super_admin(id_user):
        return jsonify({"erreur": "C'est le dernier super administrateur "
                                  "actif : le suspendre fermerait la "
                                  "plateforme à tout le monde."}), 400
    n = executer(
        "UPDATE utilisateur SET est_actif = 0 WHERE id_utilisateur = %s",
        (id_user,), commit=True,
    )
    if not n:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404
    # Détruire toutes les sessions actives de l'utilisateur suspendu
    executer("DELETE FROM session_web WHERE id_utilisateur = %s",
             (id_user,), commit=True)
    journaliser(g.utilisateur["id_utilisateur"], "suspendre",
                "utilisateur", id_user)
    return jsonify({"ok": True})


@bp_admin.post("/utilisateurs/<int:id_user>/reactiver")
@permission_requise("utilisateurs")
def reactiver(id_user):
    n = executer(
        "UPDATE utilisateur SET est_actif = 1 WHERE id_utilisateur = %s",
        (id_user,), commit=True,
    )
    if not n:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404
    journaliser(g.utilisateur["id_utilisateur"], "reactiver",
                "utilisateur", id_user)
    return jsonify({"ok": True})


@bp_admin.delete("/utilisateurs/<int:id_user>")
@permission_requise("utilisateurs")
def supprimer_utilisateur(id_user):
    """Supprime un compte, ou l'anonymise s'il porte des décisions.

    Le journal d'administration référence son auteur, et cette
    référence est posée en cascade : supprimer un administrateur
    effaçait donc toutes ses décisions du journal, au moment précis où
    l'on aurait besoin de les relire.

    Un compte qui n'a jamais rien décidé est supprimé comme avant. Un
    compte qui a décidé est vidé de ce qui identifie la personne et
    fermé définitivement : les données personnelles disparaissent, la
    trace de ce qui a été fait reste. C'est aussi ce qu'attend un
    droit à l'effacement, qui porte sur la personne et non sur les
    registres.
    """
    if id_user == g.utilisateur["id_utilisateur"]:
        return jsonify({"erreur": "Auto-suppression interdite."}), 400
    cible = _compte(id_user)
    if not cible:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404
    refus = _refus_sur_administrateur(cible, "supprimer")
    if refus:
        return jsonify({"erreur": refus}), 403
    if _dernier_super_admin(id_user):
        return jsonify({"erreur": "C'est le dernier super administrateur "
                                  "actif : le supprimer fermerait "
                                  "l'administration à tout le monde."}), 400

    decisions = (recuperer_un(
        "SELECT COUNT(*) AS n FROM audit_admin WHERE id_acteur = %s",
        (id_user,)) or {}).get("n", 0)

    if decisions:
        executer(
            """UPDATE utilisateur
                  SET prenom = 'Compte', nom = 'supprimé',
                      email = %s, bio = NULL, photo_url = NULL,
                      telephone = NULL, etablissement = NULL,
                      filiere = NULL, profil_pro = NULL,
                      est_actif = 0, est_admin = 0, role = 'visiteur',
                      permissions = '[]'
                WHERE id_utilisateur = %s""",
            (f"supprime-{id_user}@lasourcee.invalid", id_user), commit=True)
        executer("DELETE FROM session_web WHERE id_utilisateur = %s",
                 (id_user,), commit=True)
        journaliser(g.utilisateur["id_utilisateur"], "anonymiser_utilisateur",
                    "utilisateur", id_user,
                    f"{decisions} décision(s) au journal : compte vidé et "
                    "fermé plutôt qu'effacé, pour ne pas perdre la trace")
        return jsonify({"ok": True, "anonymise": True,
                        "message": "Ce compte portait des décisions "
                                   "d'administration. Ses données "
                                   "personnelles sont effacées et le compte "
                                   "fermé ; le journal reste lisible."})

    executer("DELETE FROM utilisateur WHERE id_utilisateur = %s",
             (id_user,), commit=True)
    journaliser(g.utilisateur["id_utilisateur"], "supprimer_utilisateur",
                "utilisateur", id_user,
                f"{cible.get('email')}")
    return jsonify({"ok": True})


@bp_admin.post("/utilisateurs/<int:id_user>/role")
@permission_requise("utilisateurs")
def changer_role(id_user):
    """Réservé aux super_admin pour créer d'autres admins/super_admins.

    Les admins simples peuvent promouvoir/rétrograder entre
    visiteur/etudiant/mentor, mais ne peuvent pas créer d'admin.
    """
    d = request.get_json(silent=True) or {}
    nouveau = d.get("role")
    if nouveau not in ROLES_AUTORISES:
        return jsonify({"erreur": "Rôle invalide."}), 400

    moi = g.utilisateur
    if nouveau in ("admin", "super_admin") and moi.get("role") != "super_admin":
        return jsonify({"erreur": "Seul un super administrateur peut attribuer ce rôle."}), 403

    if id_user == moi["id_utilisateur"] and nouveau != moi.get("role"):
        return jsonify({"erreur": "Vous ne pouvez pas modifier votre propre rôle."}), 400

    # Le controle ci-dessus n'interdisait que d'ACCORDER le role
    # d'administrateur. Rien n'empechait un administrateur ordinaire de
    # le RETIRER : il pouvait retrograder tous les super administrateurs
    # et laisser la plateforme sans personne pour rouvrir la porte.
    cible = _compte(id_user)
    if not cible:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404
    refus = _refus_sur_administrateur(cible, "changer le rôle d")
    if refus:
        return jsonify({"erreur": refus}), 403
    if nouveau != "super_admin" and _dernier_super_admin(id_user):
        return jsonify({"erreur": "C'est le dernier super administrateur "
                                  "actif : le rétrograder fermerait "
                                  "l'administration à tout le monde."}), 400

    # Le role et le drapeau d'administration doivent bouger ensemble.
    #
    # Cette route n'ecrivait que « role ». Or tout le controle d'acces
    # regarde « est_admin » : admin_requis et permission_requise.
    # Promouvoir quelqu'un ne lui ouvrait donc rien — il se faisait
    # refuser partout pendant que la liste des administrateurs
    # l'affichait avec tous les droits.
    #
    # L'autre sens est pire : retrograder un administrateur laissait
    # est_admin a 1 et sa colonne de droits intacte. Le compte
    # apparaissait « Beneficiaire » dans l'ecran des comptes et gardait
    # tous ses acces a l'administration. Un droit qui survit a sa
    # revocation, sans trace ni alerte.
    devient_admin = nouveau in ("admin", "super_admin")
    droits_avant = permissions_de(
        {**(cible or {}), "est_admin": cible.get("est_admin")})

    if devient_admin:
        droits = json.dumps(PERMISSIONS_PAR_DEFAUT)
    else:
        droits = json.dumps([])

    n = executer(
        "UPDATE utilisateur SET role = %s, est_admin = %s, permissions = %s "
        "WHERE id_utilisateur = %s",
        (nouveau, 1 if devient_admin else 0, droits, id_user), commit=True,
    )
    if not n:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404

    # Les sessions ouvertes portent l'ancien role : les fermer evite
    # qu'un acces retire continue de servir jusqu'a expiration.
    if droits_avant and not devient_admin:
        executer("DELETE FROM session_web WHERE id_utilisateur = %s",
                 (id_user,), commit=True)

    # Si on promeut en mentor, créer mentor_details si manquant
    if nouveau == "mentor":
        existe = recuperer_un(
            "SELECT 1 FROM mentor_details WHERE id_utilisateur = %s",
            (id_user,),
        )
        if not existe:
            executer(
                "INSERT INTO mentor_details (id_utilisateur) VALUES (%s)",
                (id_user,), commit=True,
            )

    journaliser(moi["id_utilisateur"], "changer_role",
                "utilisateur", id_user,
                f"{cible.get('role')} vers {nouveau}"
                + (f" | droits retires : {', '.join(droits_avant)}"
                   if droits_avant and not devient_admin else ""))
    return jsonify({"ok": True})


# ============================================================
# SECTEURS (CRUD complet)
# ============================================================

@bp_admin.get("/secteurs")
@permission_requise("categories")
def lister_secteurs():
    return jsonify(recuperer_tous(
        "SELECT id_secteur, libelle, couleur FROM secteur ORDER BY libelle"
    ))


@bp_admin.post("/secteurs")
@permission_requise("categories")
def creer_secteur():
    d = request.get_json(silent=True) or {}
    libelle = (d.get("libelle") or "").strip()
    couleur = (d.get("couleur") or "#16A34A").strip()
    if not libelle:
        return jsonify({"erreur": "Libellé requis."}), 400
    if len(libelle) > 80:
        return jsonify({"erreur": "Libellé trop long (max 80)."}), 400
    try:
        executer(
            "INSERT INTO secteur (libelle, couleur) VALUES (%s, %s)",
            (libelle, couleur[:20]), commit=True,
        )
    except Exception:
        return jsonify({"erreur": "Ce secteur existe déjà."}), 409
    journaliser(g.utilisateur["id_utilisateur"], "creer_secteur",
                "secteur", None, libelle)
    return jsonify({"ok": True}), 201


@bp_admin.put("/secteurs/<int:id_s>")
@permission_requise("categories")
def modifier_secteur(id_s):
    d = request.get_json(silent=True) or {}
    libelle = (d.get("libelle") or "").strip()
    couleur = (d.get("couleur") or "").strip()
    if not libelle:
        return jsonify({"erreur": "Libellé requis."}), 400
    n = executer(
        "UPDATE secteur SET libelle = %s, couleur = %s WHERE id_secteur = %s",
        (libelle, couleur[:20] or "#16A34A", id_s), commit=True,
    )
    if not n:
        return jsonify({"erreur": "Secteur introuvable."}), 404
    journaliser(g.utilisateur["id_utilisateur"], "modifier_secteur",
                "secteur", id_s, libelle)
    return jsonify({"ok": True})


@bp_admin.delete("/secteurs/<int:id_s>")
@permission_requise("categories")
def supprimer_secteur(id_s):
    # Refuse si utilisé par au moins une question
    usage = recuperer_un(
        "SELECT COUNT(*) AS n FROM question WHERE id_secteur = %s",
        (id_s,),
    )
    if usage and usage["n"] > 0:
        return jsonify({
            "erreur": f"Ce secteur est utilisé par {usage['n']} question(s). "
                      "Réassignez-les avant suppression."
        }), 409
    n = executer("DELETE FROM secteur WHERE id_secteur = %s",
                 (id_s,), commit=True)
    if not n:
        return jsonify({"erreur": "Secteur introuvable."}), 404
    journaliser(g.utilisateur["id_utilisateur"], "supprimer_secteur",
                "secteur", id_s)
    return jsonify({"ok": True})


# ============================================================
# MENTORS À VÉRIFIER
# ============================================================

@bp_admin.get("/mentors-a-verifier")
@permission_requise("referents")
def mentors_a_verifier():
    return jsonify(recuperer_tous(
        # Le dossier complet, et non le seul nom : valider quelqu'un sur
        # sa ville et sa biographie n'est pas une vérification. La
        # motivation, la profession et le lien professionnel sont ce qui
        # permet de décider.
        """SELECT u.id_utilisateur, u.prenom, u.nom, u.email, u.bio,
                  u.ville, p.libelle AS pays,
                  u.niveau_etudes, u.domaine, u.etablissement,
                  md.est_verifie, md.dispo, md.anciennete,
                  md.motivation, md.lien_pro, md.profession,
                  md.organisation, md.depose_le
             FROM utilisateur u
             JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
        LEFT JOIN pays p ON p.id_pays = u.id_pays
            WHERE md.est_verifie = 0 AND u.est_actif = 1
         ORDER BY md.depose_le DESC, u.cree_le DESC
            LIMIT 100"""
    ))


@bp_admin.post("/mentors/<int:id_mentor>/verifier")
@permission_requise("referents")
def verifier_mentor(id_mentor):
    """Valide un mentor : badge vérifié + e-mail de confirmation."""
    n = executer(
        "UPDATE mentor_details SET est_verifie = 1 WHERE id_utilisateur = %s",
        (id_mentor,), commit=True,
    )
    if not n:
        return jsonify({"erreur": "Référent introuvable."}), 404

    # S'assure que le rôle suit la validation
    executer("UPDATE utilisateur SET role = 'mentor' WHERE id_utilisateur = %s",
             (id_mentor,), commit=True)

    journaliser(g.utilisateur["id_utilisateur"], "verifier_mentor",
                "utilisateur", id_mentor)

    from routes.candidature_mentor import notifier_decision
    prevenu = notifier_decision(id_mentor, acceptee=True)
    return jsonify({"ok": True, "email_envoye": prevenu})


@bp_admin.post("/mentors/<int:id_mentor>/refuser")
@permission_requise("referents")
def refuser_mentor(id_mentor):
    """Refuse la candidature : retour au rôle étudiant + e-mail motivé."""
    motif = (request.get_json(silent=True) or {}).get("motif", "")

    n = executer(
        "UPDATE utilisateur SET role = 'etudiant' WHERE id_utilisateur = %s",
        (id_mentor,), commit=True,
    )
    if not n:
        return jsonify({"erreur": "Référent introuvable."}), 404

    # Prévient AVANT de supprimer les détails, pour disposer des infos
    from routes.candidature_mentor import notifier_decision
    prevenu = notifier_decision(id_mentor, acceptee=False, motif=motif)

    executer("DELETE FROM mentor_details WHERE id_utilisateur = %s",
             (id_mentor,), commit=True)
    journaliser(g.utilisateur["id_utilisateur"], "refuser_mentor",
                "utilisateur", id_mentor, motif[:200] if motif else None)
    return jsonify({"ok": True, "email_envoye": prevenu})


# ============================================================
# SIGNALEMENTS
# ============================================================

def _contenu_signale(type_contenu, id_contenu):
    """Le contenu visé, son auteur, et de quoi le juger.

    L'écran n'affichait que « question #14 ». Décider sans lire ce qui
    est reproché revient à trancher au hasard : soit on croit le
    signaleur sur parole, soit on rejette tout.
    """
    if type_contenu == "question":
        ligne = recuperer_un(
            """SELECT q.titre, q.corps AS texte, q.publiee_le AS cree_le,
                      u.id_utilisateur AS id_auteur, u.prenom, u.nom,
                      u.est_actif
                 FROM question q
                 JOIN utilisateur u ON u.id_utilisateur = q.id_auteur
                WHERE q.id_question = %s""", (id_contenu,))
    elif type_contenu == "reponse":
        ligne = recuperer_un(
            """SELECT r.contenu AS texte, r.cree_le,
                      u.id_utilisateur AS id_auteur, u.prenom, u.nom,
                      u.est_actif
                 FROM reponse r
                 JOIN utilisateur u ON u.id_utilisateur = r.id_auteur
                WHERE r.id_reponse = %s""", (id_contenu,))
    else:
        ligne = recuperer_un(
            """SELECT bio AS texte, cree_le,
                      id_utilisateur AS id_auteur, prenom, nom, est_actif
                 FROM utilisateur WHERE id_utilisateur = %s""", (id_contenu,))

    if not ligne:
        # Contenu deja supprime : le dire plutot que d'afficher un vide
        # qu'on prendrait pour un defaut d'affichage.
        return {"supprime": True}

    ligne["supprime"] = False
    # Le passe de l'auteur pese dans la decision : un premier
    # signalement n'appelle pas la meme reponse qu'un cinquieme.
    # Les signalements JUGES NON FONDES ne comptent pas. Sans cette
    # exclusion, quelqu'un vise par des signalements abusifs, tous
    # rejetes un par un, portait quand meme l'etiquette rouge « auteur
    # deja signale 4 fois » a cote du bouton de suspension. L'acharnement
    # se retournait ainsi contre sa victime.
    ligne["signalements_auteur"] = (recuperer_un(
        """SELECT COUNT(*) AS n FROM signalement s
            WHERE s.type_contenu = 'question'
              AND s.statut <> 'rejete'
              AND s.id_contenu IN (SELECT id_question FROM question
                                    WHERE id_auteur = %s)""",
        (ligne["id_auteur"],)) or {}).get("n", 0)
    return ligne


@bp_admin.get("/signalements")
@permission_requise("signalements")
def signalements():
    statut = request.args.get("statut", "ouvert")
    if statut not in ("ouvert", "traite", "rejete", "tous"):
        statut = "ouvert"

    condition = "" if statut == "tous" else "WHERE s.statut = %s"
    params = () if statut == "tous" else (statut,)
    lignes = recuperer_tous(
        f"""SELECT s.id_signalement, s.type_contenu, s.id_contenu,
                   s.motif, s.statut, s.cree_le, s.action, s.traite_le,
                   u.id_utilisateur AS id_signaleur,
                   u.prenom, u.nom, u.email,
                   a.prenom AS admin_prenom, a.nom AS admin_nom
              FROM signalement s
              JOIN utilisateur u ON u.id_utilisateur = s.id_signaleur
         LEFT JOIN utilisateur a ON a.id_utilisateur = s.traite_par
              {condition}
          ORDER BY s.cree_le DESC
             LIMIT 100""", params)

    for ligne in lignes:
        ligne["contenu"] = _contenu_signale(ligne["type_contenu"],
                                            ligne["id_contenu"])
        # Plusieurs PERSONNES signalant la meme chose, c'est un signal
        # en soi : le nombre doit sauter aux yeux. Les signalements deja
        # juges non fondes en sont exclus, sinon un contenu blanchi
        # trois fois arrive devant le moderateur avec trois etiquettes
        # rouges.
        ligne["signalements_contenu"] = (recuperer_un(
            "SELECT COUNT(DISTINCT id_signaleur) AS n FROM signalement "
            "WHERE type_contenu = %s AND id_contenu = %s "
            "  AND statut <> 'rejete'",
            (ligne["type_contenu"], ligne["id_contenu"])) or {}).get("n", 1)
    return jsonify(lignes)


# Décisions possibles : chacune dit ce qu'elle fait, et à qui. Un simple
# « traité » laissait ignorer si le contenu avait été retiré ou non.
ACTIONS_SIGNALEMENT = {
    "rejeter":            ("rejete", "Signalement non fondé"),
    "classer":            ("traite", "Examiné, aucune suite"),
    "avertir":            ("traite", "Auteur averti"),
    "supprimer":          ("traite", "Contenu supprimé"),
    "supprimer_avertir":  ("traite", "Contenu supprimé et auteur averti"),
    "suspendre":          ("traite", "Compte de l'auteur suspendu"),
}


@bp_admin.post("/signalements/<int:id_sig>")
@permission_requise("signalements")
def traiter_signalement(id_sig):
    d = request.get_json(silent=True) or {}
    # « statut » reste accepté : d'anciens appels l'utilisent encore.
    action = d.get("action") or {"traite": "classer",
                                 "rejete": "rejeter"}.get(d.get("statut"))
    if action not in ACTIONS_SIGNALEMENT:
        return jsonify({"erreur": "Décision inconnue."}), 400
    statut, libelle = ACTIONS_SIGNALEMENT[action]
    note = (d.get("note") or "").strip()[:500]

    sig = recuperer_un(
        "SELECT type_contenu, id_contenu, id_signaleur, statut "
        "FROM signalement WHERE id_signalement = %s", (id_sig,))
    if not sig:
        return jsonify({"erreur": "Signalement introuvable."}), 404

    cible = _contenu_signale(sig["type_contenu"], sig["id_contenu"])
    id_auteur = cible.get("id_auteur")
    moi = g.utilisateur["id_utilisateur"]

    # Un administrateur ne se suspend pas lui-même, et ne suspend pas un
    # autre administrateur sur un simple signalement.
    if action == "suspendre":
        if id_auteur == moi:
            return jsonify({"erreur":
                "Vous ne pouvez pas suspendre votre propre compte."}), 400
        vise = recuperer_un(
            "SELECT est_admin, role FROM utilisateur WHERE id_utilisateur = %s",
            (id_auteur,)) or {}
        if vise.get("est_admin") or vise.get("role") in ("admin", "super_admin"):
            return jsonify({"erreur":
                "Un administrateur ne se suspend pas depuis un "
                "signalement."}), 400

    if action in ("supprimer", "supprimer_avertir") and not cible.get("supprime"):
        table, cle = {"question": ("question", "id_question"),
                      "reponse": ("reponse", "id_reponse")}.get(
                          sig["type_contenu"], (None, None))
        if table:
            executer(f"DELETE FROM {table} WHERE {cle} = %s",
                     (sig["id_contenu"],), commit=True)

    if action == "suspendre" and id_auteur:
        executer("UPDATE utilisateur SET est_actif = 0 WHERE id_utilisateur = %s",
                 (id_auteur,), commit=True)

    if action in ("avertir", "supprimer_avertir", "suspendre") and id_auteur:
        messages = {
            "avertir": "Un de vos contenus a été signalé et examiné. "
                       "Merci de veiller au respect des règles de la "
                       "plateforme.",
            "supprimer_avertir": "Un de vos contenus a été retiré après "
                                 "signalement, car il ne respectait pas les "
                                 "règles de la plateforme.",
            "suspendre": "Votre compte a été suspendu à la suite d'un "
                         "signalement. Contactez un administrateur pour en "
                         "connaître le motif.",
        }
        notifier(id_auteur, messages[action] + (f" Motif : {note}" if note else ""),
                 type_notif="systeme")

    # Le signaleur est prévenu que son signalement a servi à quelque
    # chose. Sans retour, on cesse de signaler.
    notifier(sig["id_signaleur"],
             f"Votre signalement a été examiné : {libelle.lower()}.",
             type_notif="systeme")

    executer(
        """UPDATE signalement
              SET statut = %s, action = %s, traite_par = %s, traite_le = %s
            WHERE id_signalement = %s""",
        (statut, action, moi,
         datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), id_sig),
        commit=True,
    )
    journaliser(moi, "traiter_signalement", "signalement", id_sig,
                libelle + (f" ({note})" if note else ""))
    return jsonify({"ok": True, "libelle": libelle})


# ============================================================
# JOURNAL D'AUDIT
# ============================================================

@bp_admin.get("/audit")
@permission_requise("audit")
def consulter_audit():
    """Journal d'administration, filtrable et paginé.

    Deux cents lignes sans filtre ni page suivante : dès que le journal
    s'allonge, il ne répond plus à la seule question qu'on lui pose,
    « qui a fait quoi à ce compte, et quand ». Il se filtre donc par
    acteur, par action et par date, et dit combien de lignes existent.
    """
    limite = min(max(request.args.get("limite", default=50, type=int), 1), 200)
    page = max(request.args.get("page", default=1, type=int), 1)
    action = (request.args.get("action") or "").strip()
    acteur = request.args.get("acteur", type=int)
    cible = request.args.get("cible", type=int)
    depuis = (request.args.get("depuis") or "").strip()

    conditions, params = [], []
    if action:
        conditions.append("a.action = %s"); params.append(action[:80])
    if acteur:
        conditions.append("a.id_acteur = %s"); params.append(acteur)
    if cible:
        conditions.append("a.id_cible = %s"); params.append(cible)
    if depuis:
        conditions.append("a.cree_le >= %s"); params.append(depuis[:19])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    total = (recuperer_un(
        f"SELECT COUNT(*) AS n FROM audit_admin a {where}",
        tuple(params)) or {}).get("n", 0)

    lignes = recuperer_tous(
        f"""SELECT a.id_audit, a.action, a.type_cible, a.id_cible,
                   a.details, a.cree_le, a.ip, a.id_acteur,
                   u.prenom, u.nom, u.email
              FROM audit_admin a
              JOIN utilisateur u ON u.id_utilisateur = a.id_acteur
             {where}
          ORDER BY a.cree_le DESC
             LIMIT %s OFFSET %s""",
        tuple(params) + (limite, (page - 1) * limite),
    )
    return jsonify({
        "entrees": lignes,
        "total": total,
        "page": page,
        "par_page": limite,
        "pages": max(1, (total + limite - 1) // limite),
        # Les actions reellement presentes, pour que le filtre propose ce
        # qui existe plutot qu'une liste ecrite en dur qui derive.
        "actions": [l["action"] for l in recuperer_tous(
            "SELECT DISTINCT action FROM audit_admin ORDER BY action")],
    })


# ============================================================
# DIAGNOSTIC DE CONFIGURATION
# ============================================================

def _etat_email(smtp_ok, smtp_motif):
    """Configuration d'envoi telle que le code la lit, sans le secret.

    Rapporter les variables brutes cachait les écarts introduits en
    chemin : « SMTP » avec une espace finale devient « smtp », un port
    465 impose le chiffrement immédiat quelle que soit la valeur saisie.
    Montrer le résultat de cette normalisation évite de chercher une
    faute là où il n'y en a pas, et de la manquer là où elle est.
    """
    from flask import current_app
    from utils.email import _config, envoi_operationnel, TIMEOUT_SMTP

    c = _config()
    return {
        "mode": c["mode"],
        "operationnel": smtp_ok,
        "motif": smtp_motif,
        # Vrai seulement si un message peut réellement atteindre une
        # boîte : en production, le mode console n'y suffit pas.
        "envoi_effectif": envoi_operationnel(),
        "hote": c["hote"],
        "port": c["port"],
        "securite": c["securite"],
        "utilisateur": c["utilisateur"],
        "expediteur": c["expediteur"],
        "delai_secondes": TIMEOUT_SMTP,
        "motdepasse_fourni": bool(c["motdepasse"]),
        "confirmation_obligatoire": bool(
            current_app.config.get("VERIFICATION_EMAIL_OBLIGATOIRE")),
    }


@bp_admin.get("/diagnostic")
@permission_requise("diagnostic")
def diagnostic():
    """État réel de la configuration, vu par le serveur lui-même.

    Sur un hébergement serverless, les variables d'environnement ne sont
    lisibles que dans le tableau de bord — et celles enregistrées comme
    « secret » n'y sont plus consultables du tout après enregistrement.
    Impossible, alors, de vérifier ce que l'application a réellement reçu
    : on ne peut que constater qu'une fonctionnalité ne marche pas, sans
    savoir laquelle des variables est en cause.

    Cette route répond à cette question. Elle est réservée aux
    administrateurs et ne renvoie aucune valeur secrète : les mots de
    passe SMTP et les secrets OAuth ne sont jamais exposés, seulement le
    fait qu'ils soient renseignés ou non.
    """
    import os
    from flask import current_app
    from config import anomalies_configuration
    from utils.email import configuration_valide
    from utils.urls import base_publique

    smtp_ok, smtp_motif = configuration_valide()
    client_google = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()

    # L'identifiant client Google n'est pas un secret : il est deja
    # publie dans la page et par /api/auth/config. Le montrer ici evite
    # d'avoir a le rendre lisible dans le tableau de bord.
    google = {
        "configure": bool(client_google),
        "valeur": client_google,
        "forme_valide": client_google.endswith(".apps.googleusercontent.com"),
    }

    linkedin = {
        "client_renseigne": bool(os.getenv("LINKEDIN_CLIENT_ID")),
        "secret_renseigne": bool(os.getenv("LINKEDIN_CLIENT_SECRET")),
        "uri_retour": os.getenv("LINKEDIN_REDIRECT_URI", ""),
    }

    return jsonify({
        "environnement": current_app.config.get("ENVIRONNEMENT"),
        "adresse_publique": base_publique(),
        "base": {
            "moteur": current_app.config.get("DB_TYPE"),
            "url_fournie": bool(current_app.config.get("DATABASE_URL")),
            "comptes": (recuperer_un(
                "SELECT COUNT(*) AS n FROM utilisateur") or {}).get("n", 0),
            "administrateurs": (recuperer_un(
                "SELECT COUNT(*) AS n FROM utilisateur "
                "WHERE est_admin = 1") or {}).get("n", 0),
        },
        # La configuration telle que le code d'envoi la lit vraiment, et
        # non telle qu'elle a été saisie. Le port et le mode de sécurité
        # sont normalisés en chemin, et c'est précisément là que se
        # cachent les écarts : une espace en fin de valeur, un « tls »
        # ambigu, un port qui ne s'accorde pas avec le chiffrement. Le
        # mot de passe n'y figure pas.
        "email": _etat_email(smtp_ok, smtp_motif),
        "google": google,
        "linkedin": linkedin,
        "cle_signature_fournie": bool(
            current_app.config.get("SECRET_KEY_FOURNIE")),
        "anomalies": [{"gravite": g, "message": m}
                      for g, m in anomalies_configuration()],
    })


@bp_admin.post("/diagnostic/test-email")
@permission_requise("diagnostic")
def tester_envoi_email():
    """Envoie un message d'essai pour valider la configuration SMTP.

    Vérifier l'envoi en créant de vrais comptes laisserait des traces en
    base et n'indiquerait pas la cause d'un échec. Ici, le motif exact
    remonte : authentification refusée, hôte injoignable, port bloqué.
    """
    from utils.email import envoyer_detaille, configuration_valide

    destinataire = (g.utilisateur.get("email") or "").strip()
    if not destinataire:
        return jsonify({"erreur": "Votre compte n'a pas d'adresse."}), 400

    ok, motif = configuration_valide()
    if not ok:
        return jsonify({"envoye": False, "motif": motif}), 200

    try:
        envoye, motif = envoyer_detaille(
            destinataire,
            "LaSourcee, test de configuration",
            "Ce message confirme que l'envoi d'e-mails fonctionne.\n\n"
            "Les confirmations d'inscription et les réinitialisations de "
            "mot de passe partiront donc correctement.\n\n"
            "L'équipe LaSourcee",
        )
    except Exception as exc:
        journaliser(g.utilisateur["id_utilisateur"], "test_email_echec",
                    details=str(exc)[:200])
        return jsonify({"envoye": False, "motif": str(exc)[:200]}), 200

    journaliser(g.utilisateur["id_utilisateur"],
                "test_email" if envoye else "test_email_echec",
                details=destinataire if envoye else motif[:200])
    # Le motif exact plutôt qu'un renvoi aux journaux du serveur : sur un
    # hébergement sans état, personne ne va les consulter, et « mot de
    # passe refusé » ne se corrige pas comme « hôte injoignable ».
    return jsonify({
        "envoye": bool(envoye),
        "destinataire": destinataire,
        "motif": "" if envoye else motif,
    })


# ============================================================
# ADMINISTRATEURS ET DROITS
# ============================================================
#
# Un seul drapeau ouvrait tout : confier la modération à quelqu'un
# revenait à lui confier aussi le journal d'audit, les adresses de tous
# les membres et la configuration du serveur. Les droits se donnent
# désormais un par un, et seul un super administrateur les attribue.

@bp_admin.get("/permissions")
@admin_requis
def catalogue_permissions():
    """Droits existants, et ceux du compte qui interroge.

    L'interface s'en sert pour n'afficher que les écrans réellement
    accessibles : proposer un onglet qui répondra 403 fait passer un
    refus pour une panne.
    """
    from utils.permissions import PERMISSIONS_DETAIL, ORDRE_PORTEE
    catalogue = sorted(
        ({"cle": cle, **detail} for cle, detail in PERMISSIONS_DETAIL.items()),
        key=lambda d: (ORDRE_PORTEE.get(d["portee"], 9), d["nom"]))
    return jsonify({
        "catalogue": catalogue,
        # Forme historique, conservée pour ne pas casser un appel ancien.
        "libelles": PERMISSIONS,
        "par_defaut": PERMISSIONS_PAR_DEFAUT,
        "les_miennes": permissions_de(g.utilisateur),
        "super_admin": g.utilisateur.get("role") == "super_admin",
    })


@bp_admin.get("/administrateurs")
@permission_requise("administrateurs")
def lister_administrateurs():
    lignes = recuperer_tous(
        """SELECT id_utilisateur, prenom, nom, email, role, est_actif,
                  est_admin, permissions, derniere_co, cree_le
             FROM utilisateur
            WHERE est_admin = 1 OR role IN ('admin','super_admin')
         ORDER BY role DESC, cree_le""")
    for l in lignes:
        # Les droits reellement enregistres, et non ceux qu'on aurait si
        # le compte etait administrateur. Forcer est_admin a 1 ici
        # faisait afficher les dix droits a un compte qui n'en avait
        # aucun, et masquait exactement l'incoherence ci-dessus.
        l["droits"] = permissions_de(l)
        l["est_admin"] = bool(l.get("est_admin"))
        l.pop("permissions", None)
    return jsonify(lignes)


@bp_admin.post("/administrateurs")
@permission_requise("administrateurs")
def creer_administrateur():
    """Crée un compte d'administration et lui envoie ses accès.

    Le mot de passe est tiré au hasard et n'est jamais choisi par la
    personne qui crée le compte : sans cela, un mot de passe de
    convenance circule par messagerie et sert souvent tel quel pendant
    des mois. Le changement est imposé à la première connexion.
    """
    from utils.auth_helpers import hacher_mot_de_passe
    from utils.urls import url_publique
    from utils import email as mod_email
    import secrets

    if g.utilisateur.get("role") != "super_admin":
        return jsonify({"erreur":
            "Seul un super administrateur crée des administrateurs."}), 403

    d = request.get_json(silent=True) or {}
    prenom = normaliser_nom(d.get("prenom")) or ""
    nom = normaliser_nom(d.get("nom")) or ""
    email = (d.get("email") or "").strip().lower()
    droits = normaliser(d.get("permissions") or PERMISSIONS_PAR_DEFAUT)
    super_admin = bool(d.get("super_admin"))

    if not (prenom and nom and email):
        return jsonify({"erreur": "Prénom, nom et adresse sont requis."}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"erreur": "Adresse e-mail invalide."}), 400
    if not droits and not super_admin:
        return jsonify({"erreur":
            "Accordez au moins un droit, sinon le compte ne pourra rien "
            "faire."}), 400

    motdepasse = secrets.token_urlsafe(12) + "9a"
    role = "super_admin" if super_admin else "admin"
    existant = recuperer_un(
        "SELECT id_utilisateur FROM utilisateur WHERE email = %s", (email,))

    if existant:
        # Promotion d'un compte existant : son mot de passe reste le
        # sien. Le remplacer déconnecterait quelqu'un sans prévenir.
        id_user = existant["id_utilisateur"]
        executer(
            """UPDATE utilisateur
                  SET role = %s, est_admin = 1, est_actif = 1,
                      email_verifie = 1, permissions = %s
                WHERE id_utilisateur = %s""",
            (role, json.dumps(droits), id_user), commit=True)
        cree = False
    else:
        with curseur(commit=True) as cur:
            cur.execute(
                """INSERT INTO utilisateur
                      (prenom, nom, email, mot_de_passe, role, est_admin,
                       est_actif, email_verifie, doit_changer_mdp, permissions)
                   VALUES (%s, %s, %s, %s, %s, 1, 1, 1, 1, %s)""",
                (prenom, nom, email, hacher_mot_de_passe(motdepasse), role,
                 json.dumps(droits)))
        id_user = (recuperer_un(
            "SELECT id_utilisateur FROM utilisateur WHERE email = %s",
            (email,)) or {}).get("id_utilisateur")
        cree = True

    journaliser(g.utilisateur["id_utilisateur"], "creer_administrateur",
                "utilisateur", id_user,
                f"{role} : {', '.join(droits) if droits else 'tous droits'}")

    parti = False
    if cree:
        lien = url_publique("/index.html")
        html = mod_email.gabarit_html(
            "Votre accès d'administration LaSourcee",
            [f"Bonjour {prenom},",
             "Un compte d'administration vient d'être créé pour vous sur "
             "LaSourcee.",
             f"<b>Adresse :</b> {email}<br>"
             f"<b>Mot de passe provisoire :</b> {motdepasse}",
             "Ce mot de passe est à usage unique : l'interface vous "
             "demandera d'en choisir un autre dès votre première "
             "connexion.",
             "<b>Vos droits :</b> "
             + (", ".join(PERMISSIONS[p] for p in droits) if droits
                else "tous les droits")],
            bouton_texte="Me connecter", bouton_lien=lien,
            note_bas="Ce message contient un accès : ne le transférez pas.")
        texte = (
            f"Bonjour {prenom},\n\n"
            f"Un compte d'administration vient d'être créé pour vous sur "
            f"LaSourcee.\n\n"
            f"Adresse            : {email}\n"
            f"Mot de passe       : {motdepasse}\n\n"
            f"Ce mot de passe est provisoire : l'interface vous demandera "
            f"d'en choisir un autre à la première connexion.\n\n"
            f"Connexion : {lien}\n")
        parti = mod_email.envoyer(
            email, "Votre accès d'administration LaSourcee", texte,
            corps_html=html)

    notifier(id_user,
             "Des droits d'administration vous ont été accordés sur "
             "LaSourcee.", type_notif="systeme")

    return jsonify({
        "ok": True, "id_utilisateur": id_user, "cree": cree,
        "email_envoye": parti,
        # Affiché une fois, et seulement si l'e-mail n'est pas parti :
        # sans cela l'accès serait créé sans que personne puisse s'en
        # servir. Il n'est jamais renvoyé ensuite.
        "mot_de_passe": motdepasse if (cree and not parti) else None,
    })


@bp_admin.put("/administrateurs/<int:id_user>")
@permission_requise("administrateurs")
def modifier_droits(id_user):
    if g.utilisateur.get("role") != "super_admin":
        return jsonify({"erreur":
            "Seul un super administrateur modifie les droits."}), 403
    if id_user == g.utilisateur["id_utilisateur"]:
        # Se retirer un droit fermerait la porte à la seule personne
        # capable de la rouvrir.
        return jsonify({"erreur":
            "Vous ne pouvez pas modifier vos propres droits."}), 400

    d = request.get_json(silent=True) or {}
    droits = normaliser(d.get("permissions") or [])
    cible = recuperer_un(
        "SELECT role FROM utilisateur WHERE id_utilisateur = %s", (id_user,))
    if not cible:
        return jsonify({"erreur": "Compte introuvable."}), 404
    if cible["role"] == "super_admin":
        return jsonify({"erreur":
            "Les droits d'un super administrateur ne se restreignent "
            "pas."}), 400

    executer("UPDATE utilisateur SET permissions = %s WHERE id_utilisateur = %s",
             (json.dumps(droits), id_user), commit=True)
    journaliser(g.utilisateur["id_utilisateur"], "modifier_droits",
                "utilisateur", id_user, ", ".join(droits) or "aucun droit")
    notifier(id_user, "Vos droits d'administration ont été modifiés.",
             type_notif="systeme")
    return jsonify({"ok": True, "droits": droits})


@bp_admin.delete("/administrateurs/<int:id_user>")
@permission_requise("administrateurs")
def retirer_administrateur(id_user):
    """Retire les droits sans supprimer le compte.

    Supprimer le compte effacerait aussi ses questions et ses réponses,
    et le journal d'audit perdrait le nom derrière ses entrées.
    """
    if g.utilisateur.get("role") != "super_admin":
        return jsonify({"erreur":
            "Seul un super administrateur retire ces droits."}), 403
    if id_user == g.utilisateur["id_utilisateur"]:
        return jsonify({"erreur":
            "Vous ne pouvez pas retirer vos propres droits."}), 400

    restants = (recuperer_un(
        "SELECT COUNT(*) AS n FROM utilisateur "
        "WHERE role = 'super_admin' AND est_actif = 1 "
        "AND id_utilisateur <> %s", (id_user,)) or {}).get("n", 0)
    cible = recuperer_un(
        "SELECT role FROM utilisateur WHERE id_utilisateur = %s", (id_user,))
    if not cible:
        return jsonify({"erreur": "Compte introuvable."}), 404
    if cible["role"] == "super_admin" and restants == 0:
        # Retirer le dernier super administrateur laisserait la
        # plateforme sans personne pour en créer un autre.
        return jsonify({"erreur":
            "C'est le dernier super administrateur : nommez-en un autre "
            "avant de retirer celui-ci."}), 400

    executer(
        """UPDATE utilisateur
              SET est_admin = 0, role = 'etudiant', permissions = %s
            WHERE id_utilisateur = %s""",
        (json.dumps([]), id_user), commit=True)
    journaliser(g.utilisateur["id_utilisateur"], "retirer_administrateur",
                "utilisateur", id_user)
    notifier(id_user, "Vos droits d'administration ont été retirés.",
             type_notif="systeme")
    return jsonify({"ok": True})


# ============================================================
# EXPORT DES DONNÉES
# ============================================================
#
# Les données de la plateforme n'étaient consultables qu'à l'écran, page
# par page. Impossible d'en tirer une analyse, de préparer un rapport ou
# de garder une copie hors ligne. Deux formats : CSV pour un tableur,
# JSON pour un traitement.
#
# L'export est un droit distinct de la consultation : parcourir une
# liste à l'écran et emporter la base entière sur une clé n'engagent pas
# la même responsabilité.

def _csv(lignes):
    """Sérialise des dictionnaires en CSV, séparateur point-virgule.

    Le point-virgule plutôt que la virgule : les tableurs configurés en
    français ouvrent le fichier directement, là où la virgule aligne
    tout dans une seule colonne. Le BOM en tête sert le même but, il
    fait reconnaître l'UTF-8 à Excel, qui lirait sinon « Ã© ».
    """
    import csv
    import io
    if not lignes:
        return "﻿"
    tampon = io.StringIO()
    tampon.write("﻿")
    plume = csv.DictWriter(tampon, fieldnames=list(lignes[0].keys()),
                           delimiter=";", extrasaction="ignore")
    plume.writeheader()
    for ligne in lignes:
        plume.writerow({k: ("" if v is None else v) for k, v in ligne.items()})
    return tampon.getvalue()


def _reponse_fichier(lignes, nom, format_demande):
    """Renvoie les lignes en pièce jointe, au format demandé."""
    from flask import Response
    horodatage = datetime.utcnow().strftime("%Y%m%d")
    if format_demande == "csv":
        corps, type_mime, ext = _csv(lignes), "text/csv; charset=utf-8", "csv"
    else:
        corps = json.dumps(lignes, ensure_ascii=False, indent=2, default=str)
        type_mime, ext = "application/json; charset=utf-8", "json"
    return Response(
        corps, mimetype=type_mime,
        headers={
            "Content-Disposition":
                f'attachment; filename="lasourcee-{nom}-{horodatage}.{ext}"',
            # Un export contient des données personnelles : aucun cache,
            # ni navigateur ni intermédiaire.
            "Cache-Control": "no-store, no-cache, must-revalidate",
        })


# Jeux exportables. Les mots de passe, les jetons de session et les
# jetons de réinitialisation ne figurent dans aucun : un export circule,
# s'oublie sur une clé, et rien de tout cela n'a à voyager.
JEUX_EXPORT = {
    "utilisateurs": (
        "Comptes",
        """SELECT u.id_utilisateur, u.prenom, u.nom, u.email, u.role,
                  u.est_actif, u.email_verifie, p.libelle AS pays, u.ville,
                  u.situation, u.objectif, u.niveau_etudes, u.domaine,
                  u.etablissement, u.langues, u.cree_le, u.derniere_co
             FROM utilisateur u
        LEFT JOIN pays p ON p.id_pays = u.id_pays
         ORDER BY u.cree_le"""),
    "questions": (
        "Questions",
        """SELECT q.id_question, q.titre, q.corps, q.statut, q.publiee_le,
                  q.vues, q.premiere_reponse_le, q.resolue_le,
                  s.libelle AS secteur,
                  u.id_utilisateur AS id_auteur, u.prenom, u.nom,
                  (SELECT COUNT(*) FROM reponse r
                    WHERE r.id_question = q.id_question) AS nb_reponses
             FROM question q
             JOIN utilisateur u ON u.id_utilisateur = q.id_auteur
        LEFT JOIN secteur s ON s.id_secteur = q.id_secteur
         ORDER BY q.publiee_le"""),
    "reponses": (
        "Réponses",
        """SELECT r.id_reponse, r.id_question, r.contenu, r.cree_le,
                  u.id_utilisateur AS id_auteur, u.prenom, u.nom, u.role
             FROM reponse r
             JOIN utilisateur u ON u.id_utilisateur = r.id_auteur
         ORDER BY r.cree_le"""),
    "referents": (
        "Référents et candidatures",
        """SELECT u.id_utilisateur, u.prenom, u.nom, u.email,
                  md.est_verifie, md.profession, md.organisation,
                  md.anciennete, md.lien_pro, md.depose_le,
                  md.nb_reponses, md.note_moyenne
             FROM mentor_details md
             JOIN utilisateur u ON u.id_utilisateur = md.id_utilisateur
         ORDER BY md.depose_le"""),
    "signalements": (
        "Signalements",
        """SELECT s.id_signalement, s.type_contenu, s.id_contenu, s.motif,
                  s.statut, s.action, s.cree_le, s.traite_le,
                  u.prenom AS signaleur_prenom, u.nom AS signaleur_nom,
                  a.prenom AS traite_par_prenom, a.nom AS traite_par_nom
             FROM signalement s
             JOIN utilisateur u ON u.id_utilisateur = s.id_signaleur
        LEFT JOIN utilisateur a ON a.id_utilisateur = s.traite_par
         ORDER BY s.cree_le"""),
    "audit": (
        "Journal d'administration",
        """SELECT j.id_audit, j.action, j.type_cible, j.id_cible,
                  j.details, j.ip, j.cree_le,
                  u.prenom, u.nom, u.email
             FROM audit_admin j
        LEFT JOIN utilisateur u ON u.id_utilisateur = j.id_acteur
         ORDER BY j.cree_le"""),
    "evenements": (
        "Journal d'activité",
        """SELECT e.id_evenement, e.type_evenement, e.type_cible, e.id_cible,
                  e.role_acteur, e.contexte, e.cree_le, e.id_utilisateur
             FROM evenement e
         ORDER BY e.cree_le"""),
    "activite": (
        "Activité par jour",
        """SELECT jour, SUM(inscriptions) AS inscriptions,
                  SUM(questions) AS questions, SUM(reponses) AS reponses
             FROM (
               SELECT SUBSTR(CAST(cree_le AS CHAR), 1, 10) AS jour,
                      COUNT(*) AS inscriptions, 0 AS questions, 0 AS reponses
                 FROM utilisateur GROUP BY 1
               UNION ALL
               SELECT SUBSTR(CAST(publiee_le AS CHAR), 1, 10), 0,
                      COUNT(*), 0 FROM question GROUP BY 1
               UNION ALL
               SELECT SUBSTR(CAST(cree_le AS CHAR), 1, 10), 0, 0,
                      COUNT(*) FROM reponse GROUP BY 1
             ) t
         GROUP BY jour ORDER BY jour"""),
}


@bp_admin.get("/export")
@permission_requise("export")
def catalogue_export():
    """Jeux disponibles, avec le nombre de lignes de chacun."""
    tables = {"utilisateurs": "utilisateur", "questions": "question",
              "reponses": "reponse", "referents": "mentor_details",
              "signalements": "signalement", "audit": "audit_admin",
              "evenements": "evenement"}
    jeux = []
    for cle, (libelle, _) in JEUX_EXPORT.items():
        n = None
        if cle in tables:
            n = (recuperer_un(
                f"SELECT COUNT(*) AS n FROM {tables[cle]}") or {}).get("n")
        jeux.append({"cle": cle, "libelle": libelle, "lignes": n})
    return jsonify(jeux)


@bp_admin.get("/export/<jeu>")
@permission_requise("export")
def exporter_jeu(jeu):
    if jeu not in JEUX_EXPORT:
        return jsonify({"erreur": "Jeu de données inconnu."}), 404
    format_demande = "csv" if request.args.get("format") != "json" else "json"
    libelle, requete = JEUX_EXPORT[jeu]

    # SUBSTR sur une date se dit differemment selon le moteur : SQLite
    # accepte CAST(... AS CHAR), PostgreSQL veut du texte explicite.
    from config import Config
    if Config.DB_TYPE == "postgres":
        requete = requete.replace("CAST(cree_le AS CHAR)", "cree_le::text")
        requete = requete.replace("CAST(publiee_le AS CHAR)", "publiee_le::text")

    lignes = recuperer_tous(requete)
    journaliser(g.utilisateur["id_utilisateur"], "export", "jeu", None,
                f"{jeu} ({len(lignes)} lignes, {format_demande})")
    return _reponse_fichier(lignes, jeu, format_demande)


@bp_admin.get("/export/compte/<int:id_user>")
@permission_requise("export")
def exporter_compte(id_user):
    """Tout ce que la plateforme conserve sur une personne.

    Utile pour répondre à une demande d'accès, pour instruire un
    signalement, ou pour comprendre un parcours. Le mot de passe et les
    jetons de session en sont exclus : les inclure ferait de ce fichier
    un moyen d'usurper le compte.
    """
    profil = recuperer_un(
        """SELECT u.*, p.libelle AS pays_nom FROM utilisateur u
      LEFT JOIN pays p ON p.id_pays = u.id_pays
          WHERE u.id_utilisateur = %s""", (id_user,))
    if not profil:
        return jsonify({"erreur": "Compte introuvable."}), 404
    for secret in ("mot_de_passe", "permissions"):
        profil.pop(secret, None)

    dossier = {
        "profil": profil,
        "referent": recuperer_un(
            "SELECT * FROM mentor_details WHERE id_utilisateur = %s",
            (id_user,)),
        "secteurs": recuperer_tous(
            "SELECT s.libelle FROM secteur s "
            "JOIN utilisateur_secteur us ON us.id_secteur = s.id_secteur "
            "WHERE us.id_utilisateur = %s", (id_user,)),
        "questions": recuperer_tous(
            "SELECT id_question, titre, corps, statut, publiee_le "
            "FROM question WHERE id_auteur = %s ORDER BY publiee_le",
            (id_user,)),
        "reponses": recuperer_tous(
            "SELECT id_reponse, id_question, contenu, cree_le "
            "FROM reponse WHERE id_auteur = %s ORDER BY cree_le", (id_user,)),
        "signalements_emis": recuperer_tous(
            "SELECT id_signalement, type_contenu, id_contenu, motif, statut, "
            "cree_le FROM signalement WHERE id_signaleur = %s", (id_user,)),
        "sessions_actives": (recuperer_un(
            "SELECT COUNT(*) AS n FROM session_web WHERE id_utilisateur = %s",
            (id_user,)) or {}).get("n", 0),
        "exporte_le": datetime.utcnow().isoformat(timespec="seconds"),
        "exporte_par": g.utilisateur["email"],
    }
    journaliser(g.utilisateur["id_utilisateur"], "export_compte",
                "utilisateur", id_user)

    from flask import Response
    return Response(
        json.dumps(dossier, ensure_ascii=False, indent=2, default=str),
        mimetype="application/json; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="lasourcee-compte-{id_user}.json"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        })
