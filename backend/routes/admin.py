"""Routes d'administration : tableau de bord, utilisateurs, secteurs,
mentors, signalements, audit."""

from flask import Blueprint, jsonify, request, g

from models.db import recuperer_un, recuperer_tous, executer, curseur
from utils.auth_helpers import admin_requis
from utils.audit import journaliser

bp_admin = Blueprint("admin", __name__, url_prefix="/api/admin")

ROLES_AUTORISES = {"visiteur", "etudiant", "mentor", "admin", "super_admin"}


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
@admin_requis
def lister_utilisateurs():
    """Annuaire administratif avec filtres optionnels."""
    role = request.args.get("role")
    actif = request.args.get("actif")
    recherche = (request.args.get("q") or "").strip()
    limite = min(request.args.get("limite", default=100, type=int), 500)

    conditions, params = [], []
    if role in ROLES_AUTORISES:
        conditions.append("u.role = %s"); params.append(role)
    if actif in ("0", "1"):
        conditions.append("u.est_actif = %s"); params.append(int(actif))
    if recherche:
        conditions.append("(u.prenom LIKE %s OR u.nom LIKE %s OR u.email LIKE %s)")
        m = f"%{recherche}%"; params.extend([m, m, m])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limite)

    return jsonify(recuperer_tous(
        f"""SELECT u.id_utilisateur, u.prenom, u.nom, u.email, u.role,
                   u.est_actif, u.cree_le, u.derniere_co,
                   p.libelle AS pays
              FROM utilisateur u
         LEFT JOIN pays p ON p.id_pays = u.id_pays
            {where}
         ORDER BY u.cree_le DESC
            LIMIT %s""",
        params,
    ))


@bp_admin.get("/utilisateurs/<int:id_user>")
@admin_requis
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
@admin_requis
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

    fragments = ", ".join(f"{k} = %s" for k in champs)
    try:
        executer(
            f"UPDATE utilisateur SET {fragments} WHERE id_utilisateur = %s",
            list(champs.values()) + [id_user], commit=True,
        )
    except Exception:
        return jsonify({"erreur": "Conflit (e-mail déjà utilisé ?)."}), 409
    journaliser(g.utilisateur["id_utilisateur"], "modifier_utilisateur",
                "utilisateur", id_user, ",".join(champs.keys()))
    return jsonify({"ok": True})


@bp_admin.post("/utilisateurs/<int:id_user>/suspendre")
@admin_requis
def suspendre(id_user):
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
@admin_requis
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
@admin_requis
def supprimer_utilisateur(id_user):
    if id_user == g.utilisateur["id_utilisateur"]:
        return jsonify({"erreur": "Auto-suppression interdite."}), 400
    n = executer("DELETE FROM utilisateur WHERE id_utilisateur = %s",
                 (id_user,), commit=True)
    if not n:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404
    journaliser(g.utilisateur["id_utilisateur"], "supprimer_utilisateur",
                "utilisateur", id_user)
    return jsonify({"ok": True})


@bp_admin.post("/utilisateurs/<int:id_user>/role")
@admin_requis
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

    # Si on passe de mentor à autre chose, conserver mentor_details mais ce sera ignoré
    n = executer(
        "UPDATE utilisateur SET role = %s WHERE id_utilisateur = %s",
        (nouveau, id_user), commit=True,
    )
    if not n:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404

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
                "utilisateur", id_user, f"-> {nouveau}")
    return jsonify({"ok": True})


# ============================================================
# SECTEURS (CRUD complet)
# ============================================================

@bp_admin.get("/secteurs")
@admin_requis
def lister_secteurs():
    return jsonify(recuperer_tous(
        "SELECT id_secteur, libelle, couleur FROM secteur ORDER BY libelle"
    ))


@bp_admin.post("/secteurs")
@admin_requis
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
@admin_requis
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
@admin_requis
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
@admin_requis
def mentors_a_verifier():
    return jsonify(recuperer_tous(
        """SELECT u.id_utilisateur, u.prenom, u.nom, u.email, u.bio,
                  u.ville, p.libelle AS pays,
                  md.est_verifie, md.dispo, md.anciennete
             FROM utilisateur u
             JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
        LEFT JOIN pays p ON p.id_pays = u.id_pays
            WHERE md.est_verifie = 0 AND u.est_actif = 1
         ORDER BY u.cree_le DESC
            LIMIT 100"""
    ))


@bp_admin.post("/mentors/<int:id_mentor>/verifier")
@admin_requis
def verifier_mentor(id_mentor):
    """Valide un mentor : badge vérifié + e-mail de confirmation."""
    n = executer(
        "UPDATE mentor_details SET est_verifie = 1 WHERE id_utilisateur = %s",
        (id_mentor,), commit=True,
    )
    if not n:
        return jsonify({"erreur": "Mentor introuvable."}), 404

    # S'assure que le rôle suit la validation
    executer("UPDATE utilisateur SET role = 'mentor' WHERE id_utilisateur = %s",
             (id_mentor,), commit=True)

    journaliser(g.utilisateur["id_utilisateur"], "verifier_mentor",
                "utilisateur", id_mentor)

    from routes.candidature_mentor import notifier_decision
    prevenu = notifier_decision(id_mentor, acceptee=True)
    return jsonify({"ok": True, "email_envoye": prevenu})


@bp_admin.post("/mentors/<int:id_mentor>/refuser")
@admin_requis
def refuser_mentor(id_mentor):
    """Refuse la candidature : retour au rôle étudiant + e-mail motivé."""
    motif = (request.get_json(silent=True) or {}).get("motif", "")

    n = executer(
        "UPDATE utilisateur SET role = 'etudiant' WHERE id_utilisateur = %s",
        (id_mentor,), commit=True,
    )
    if not n:
        return jsonify({"erreur": "Mentor introuvable."}), 404

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

@bp_admin.get("/signalements")
@admin_requis
def signalements():
    statut = request.args.get("statut", "ouvert")
    if statut not in ("ouvert", "traite", "rejete"):
        statut = "ouvert"
    return jsonify(recuperer_tous(
        """SELECT s.id_signalement, s.type_contenu, s.id_contenu,
                  s.motif, s.statut, s.cree_le,
                  u.id_utilisateur AS id_signaleur,
                  u.prenom, u.nom
             FROM signalement s
             JOIN utilisateur u ON u.id_utilisateur = s.id_signaleur
            WHERE s.statut = %s
         ORDER BY s.cree_le DESC
            LIMIT 100""",
        (statut,),
    ))


@bp_admin.post("/signalements/<int:id_sig>")
@admin_requis
def traiter_signalement(id_sig):
    d = request.get_json(silent=True) or {}
    decision = d.get("statut")
    if decision not in ("traite", "rejete"):
        return jsonify({"erreur": "Décision invalide."}), 400
    n = executer(
        "UPDATE signalement SET statut = %s WHERE id_signalement = %s",
        (decision, id_sig), commit=True,
    )
    if not n:
        return jsonify({"erreur": "Signalement introuvable."}), 404
    journaliser(g.utilisateur["id_utilisateur"], "traiter_signalement",
                "signalement", id_sig, decision)
    return jsonify({"ok": True})


# ============================================================
# JOURNAL D'AUDIT
# ============================================================

@bp_admin.get("/audit")
@admin_requis
def consulter_audit():
    limite = min(request.args.get("limite", default=50, type=int), 200)
    return jsonify(recuperer_tous(
        """SELECT a.id_audit, a.action, a.type_cible, a.id_cible,
                  a.details, a.cree_le, a.ip,
                  u.prenom, u.nom, u.email
             FROM audit_admin a
             JOIN utilisateur u ON u.id_utilisateur = a.id_acteur
         ORDER BY a.cree_le DESC
            LIMIT %s""",
        (limite,),
    ))


# ============================================================
# DIAGNOSTIC DE CONFIGURATION
# ============================================================

@bp_admin.get("/diagnostic")
@admin_requis
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
        "email": {
            "mode": (os.getenv("EMAIL_MODE", "console") or "console").lower(),
            "operationnel": smtp_ok,
            "motif": smtp_motif,
            "expediteur": os.getenv("SMTP_EXPEDITEUR", ""),
            "hote": os.getenv("SMTP_HOTE", ""),
            "confirmation_obligatoire": bool(
                current_app.config.get("VERIFICATION_EMAIL_OBLIGATOIRE")),
        },
        "google": google,
        "linkedin": linkedin,
        "cle_signature_fournie": bool(
            current_app.config.get("SECRET_KEY_FOURNIE")),
        "anomalies": [{"gravite": g, "message": m}
                      for g, m in anomalies_configuration()],
    })


@bp_admin.post("/diagnostic/test-email")
@admin_requis
def tester_envoi_email():
    """Envoie un message d'essai pour valider la configuration SMTP.

    Vérifier l'envoi en créant de vrais comptes laisserait des traces en
    base et n'indiquerait pas la cause d'un échec. Ici, le motif exact
    remonte : authentification refusée, hôte injoignable, port bloqué.
    """
    from utils.email import envoyer, configuration_valide

    destinataire = (g.utilisateur.get("email") or "").strip()
    if not destinataire:
        return jsonify({"erreur": "Votre compte n'a pas d'adresse."}), 400

    ok, motif = configuration_valide()
    if not ok:
        return jsonify({"envoye": False, "motif": motif}), 200

    try:
        envoye = envoyer(
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

    journaliser(g.utilisateur["id_utilisateur"], "test_email",
                details=destinataire)
    return jsonify({
        "envoye": bool(envoye),
        "destinataire": destinataire,
        "motif": "" if envoye else
                 "L'envoi a échoué. Consultez les journaux du serveur.",
    })
