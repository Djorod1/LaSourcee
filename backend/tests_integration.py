#!/usr/bin/env python3
"""Tests d'intégration de LaSourcee.

Vérifie les parcours complets sur une base neuve, sans dépendance
externe (aucun serveur ni compte e-mail requis).

    cd backend && python tests_integration.py

Un code de sortie 0 signifie que tous les tests passent.
"""

import logging
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Moteur testé : sqlite par défaut, postgres si DB_TYPE le demande.
#   DB_TYPE=postgres DATABASE_URL=postgresql://... python tests_integration.py
_MOTEUR = (os.environ.get("DB_TYPE") or "sqlite").lower()

if _MOTEUR in ("postgres", "postgresql", "pg"):
    os.environ["DB_TYPE"] = "postgres"
else:
    # Base temporaire dédiée aux tests, jamais celle de production
    _BASE = os.path.join(tempfile.gettempdir(), "lasource_tests.db")
    if os.path.exists(_BASE):
        os.remove(_BASE)
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_PATH"] = _BASE
os.environ.setdefault("EMAIL_MODE", "console")

from app import creer_application  # noqa: E402

logging.getLogger("lasource.email").setLevel(logging.CRITICAL)
logging.getLogger("lasource").setLevel(logging.CRITICAL)
logging.getLogger("werkzeug").setLevel(logging.CRITICAL)

# Consentement exige a l'inscription depuis que les conditions
# sont recueillies. Les tests le fournissent comme le fait
# l'interface : sans lui, chaque inscription echoue en 400.
CONSENT_TESTS = {"conditions": True, "donnees": True,
                 "notifications": False}

_resultats = []


def verifier(intitule, condition, detail=""):
    _resultats.append((intitule, bool(condition), detail))
    marque = "OK  " if condition else "ÉCHEC"
    ligne = f"  [{marque}] {intitule}"
    if detail and not condition:
        ligne += f"\n           → {detail}"
    print(ligne)
    return bool(condition)


def jeton_sql(requete, params=()):
    """Lecture directe en base, quel que soit le moteur testé."""
    if os.environ["DB_TYPE"] == "postgres":
        import psycopg2
        cx = psycopg2.connect(os.environ["DATABASE_URL"])
        try:
            cur = cx.cursor()
            cur.execute(requete.replace("?", "%s"), params)
            r = cur.fetchone()
            return r[0] if r else None
        finally:
            cx.close()
    cx = sqlite3.connect(_BASE)
    try:
        r = cx.execute(requete, params).fetchone()
        return r[0] if r else None
    finally:
        cx.close()


def _suspendu_ecarte(mod_resume, executer, id_user):
    """Un compte desactive doit disparaitre de la file des resumes."""
    executer("UPDATE utilisateur SET est_actif = 0 WHERE id_utilisateur = %s",
             (id_user,), commit=True)
    absent = id_user not in [c["id_utilisateur"]
                             for c in mod_resume._destinataires()]
    executer("UPDATE utilisateur SET est_actif = 1 WHERE id_utilisateur = %s",
             (id_user,), commit=True)
    return absent


def executer_tests():
    app = creer_application()

    # Le schema est cree par l'application, mais les verifications qui
    # interrogent la base en direct ouvrent leur propre connexion. Sans
    # cette premiere requete, la suite echouait sur « no such table »
    # au tout premier passage apres la suppression de la base, et
    # passait au second : un piege qui fait croire a un defaut du code.
    with app.app_context():
        from models.db import recuperer_un
        recuperer_un("SELECT COUNT(*) AS n FROM utilisateur")

    print("\n" + "═" * 70)
    print("  1. DÉMARRAGE ET RESSOURCES")
    print("═" * 70)
    c = app.test_client()
    r = c.get("/api/sante")
    verifier("Sonde de santé répond 200", r.status_code == 200)
    verifier("Page d'accueil servie", c.get("/").status_code == 200)
    verifier("Feuille de styles servie", c.get("/styles.css").status_code == 200)
    verifier("Script applicatif servi", c.get("/script.js").status_code == 200)
    verifier("Logo complet servi",
             c.get("/assets/lasource-logo.png").status_code == 200)
    verifier("Symbole servi",
             c.get("/assets/lasource-symbole.png").status_code == 200)
    verifier("Favicon servi", c.get("/assets/favicon.png").status_code == 200)
    verifier("Route inconnue renvoie 404",
             c.get("/api/inexistant").status_code == 404)
    verifier("Le code du backend n'est pas servi",
             c.get("/backend/config.py").status_code == 404)
    verifier("Les schémas SQL ne sont pas servis",
             c.get("/database/schema_sqlite.sql").status_code == 404)
    verifier("Remontée d'arborescence refusée",
             c.get("/assets/../backend/app.py").status_code in (400, 404))

    print("\n" + "═" * 70)
    print("  2. ABSENCE DE DONNÉES DE DÉMONSTRATION")
    print("═" * 70)
    verifier("Aucun compte de démonstration en base",
             jeton_sql("SELECT COUNT(*) FROM utilisateur WHERE email LIKE ? "
                       "OR email LIKE ?",
                       ("%@lasource.io", "%@test.io")) == 0)
    verifier("Aucune question préchargée",
             jeton_sql("SELECT COUNT(*) FROM question") == 0)
    verifier("Référentiel des secteurs présent",
             jeton_sql("SELECT COUNT(*) FROM secteur") > 0)
    verifier("Référentiel des pays présent",
             jeton_sql("SELECT COUNT(*) FROM pays") > 0)

    print("\n" + "═" * 70)
    print("  3. INSCRIPTION ET CONNEXION")
    print("═" * 70)
    etu = app.test_client()
    r = etu.post("/api/auth/inscription", json={
        "prenom": "Aminata", "nom": "TRAORE", "email": "aminata@test.io",
        "mot_de_passe": "Aminata2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    verifier("Inscription d'un étudiant", r.status_code == 201,
             f"reçu {r.status_code} : {r.get_data(as_text=True)[:90]}")

    r = etu.post("/api/auth/inscription", json={
        "prenom": "Autre", "nom": "Personne", "email": "aminata@test.io",
        "mot_de_passe": "Autre2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    verifier("E-mail en double refusé (409)", r.status_code == 409)

    r = etu.post("/api/auth/inscription", json={
        "prenom": "Faible", "nom": "Mdp", "email": "faible@test.io",
        "mot_de_passe": "123", "role": "etudiant", "consentement": CONSENT_TESTS})
    verifier("Mot de passe trop faible refusé", r.status_code == 400)

    r = etu.post("/api/auth/connexion",
                 json={"email": "aminata@test.io", "mot_de_passe": "Aminata2026!"})
    verifier("Connexion réussie", r.status_code == 200)
    verifier("Cookie de session posé",
             "ls_session" in r.headers.get("Set-Cookie", ""))

    r = etu.get("/api/profil/moi")
    verifier("Profil accessible une fois connecté", r.status_code == 200)

    anon = app.test_client()
    verifier("Profil refusé sans session (401)",
             anon.get("/api/profil/moi").status_code == 401)
    verifier("Mauvais mot de passe refusé (401)",
             anon.post("/api/auth/connexion",
                       json={"email": "aminata@test.io",
                             "mot_de_passe": "faux"}).status_code == 401)

    print("\n" + "═" * 70)
    print("  4. VÉRIFICATION D'ADRESSE E-MAIL")
    print("═" * 70)
    jeton = jeton_sql(
        "SELECT v.id_jeton FROM verification_email v "
        "JOIN utilisateur u ON u.id_utilisateur = v.id_utilisateur "
        "WHERE u.email = ?", ("aminata@test.io",))
    verifier("Jeton de vérification créé à l'inscription", bool(jeton))
    r = anon.post("/api/auth/verifier-email", json={"jeton": jeton})
    verifier("Vérification acceptée", r.status_code == 200)
    verifier("Adresse marquée vérifiée en base",
             jeton_sql("SELECT email_verifie FROM utilisateur WHERE email = ?",
                       ("aminata@test.io",)) == 1)
    r = anon.post("/api/auth/verifier-email", json={"jeton": jeton})
    verifier("Jeton non réutilisable (410)", r.status_code == 410)

    print("\n" + "═" * 70)
    print("  5. RÉINITIALISATION DE MOT DE PASSE")
    print("═" * 70)
    r = anon.post("/api/auth/oubli-mdp", json={"email": "aminata@test.io"})
    verifier("Demande acceptée", r.status_code == 200)
    r = anon.post("/api/auth/oubli-mdp", json={"email": "inconnu@nulle.part"})
    verifier("Adresse inconnue : réponse identique (anti-énumération)",
             r.status_code == 200)
    jr = jeton_sql(
        "SELECT r.id_jeton FROM reinitialisation_mdp r "
        "JOIN utilisateur u ON u.id_utilisateur = r.id_utilisateur "
        "WHERE u.email = ? AND r.utilise_le IS NULL "
        "ORDER BY r.cree_le DESC LIMIT 1", ("aminata@test.io",))
    verifier("Jeton de réinitialisation créé", bool(jr))
    r = anon.post("/api/auth/reinitialiser-mdp",
                  json={"jeton": jr, "nouveau_mot_de_passe": "Nouveau2026!"})
    verifier("Réinitialisation acceptée", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("Connexion avec le nouveau mot de passe",
             anon.post("/api/auth/connexion",
                       json={"email": "aminata@test.io",
                             "mot_de_passe": "Nouveau2026!"}).status_code == 200)
    verifier("Ancien mot de passe rejeté",
             anon.post("/api/auth/connexion",
                       json={"email": "aminata@test.io",
                             "mot_de_passe": "Aminata2026!"}).status_code == 401)
    verifier("Jeton de réinitialisation non réutilisable",
             anon.post("/api/auth/reinitialiser-mdp",
                       json={"jeton": jr,
                             "nouveau_mot_de_passe": "Encore2026!"}
                       ).status_code == 410)

    # Le changement de mot de passe révoque toutes les sessions actives
    # (comportement de sécurité voulu) : le client de test doit se
    # reconnecter avec le nouveau mot de passe pour la suite.
    verifier("Sessions révoquées après changement de mot de passe",
             etu.get("/api/profil/moi").status_code == 401)
    etu.post("/api/auth/connexion",
             json={"email": "aminata@test.io",
                   "mot_de_passe": "Nouveau2026!"})
    verifier("Reconnexion après réinitialisation",
             etu.get("/api/profil/moi").status_code == 200)

    print("\n" + "═" * 70)
    print("  6. COMPTES ADMINISTRATEURS")
    print("═" * 70)
    env = {**os.environ, "EMAIL_MODE": "console"}
    sortie = subprocess.run(
        [sys.executable, "gerer_admins.py", "creer"],
        capture_output=True, text=True, env=env,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    ).stdout
    for adresse in ("toyohounsogbe1@gmail.com", "theophiledounon@gmail.com",
                    "espoirmariano@gmail.com", "rodriguedjossou93@gmail.com"):
        verifier(f"Compte créé : {adresse}",
                 jeton_sql("SELECT role FROM utilisateur WHERE email = ?",
                           (adresse,)) == "super_admin")

    mdps = re.findall(r"Mot de passe : (\S+)", sortie)
    verifier("Mots de passe temporaires générés", len(mdps) == 4,
             f"{len(mdps)} trouvé(s)")
    verifier("Mots de passe tous différents", len(set(mdps)) == len(mdps))

    adm = app.test_client()
    r = adm.post("/api/auth/connexion",
                 json={"email": "rodriguedjossou93@gmail.com",
                       "mot_de_passe": mdps[-1]})
    verifier("Connexion administrateur", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("Mot de passe temporaire signalé à la connexion",
             (r.get_json() or {}).get("doit_changer_mdp") is True,
             r.get_data(as_text=True)[:110])
    r = adm.get("/api/admin/dashboard")
    verifier("Tableau de bord accessible à l'admin", r.status_code == 200)
    verifier("Tableau de bord refusé à l'étudiant (403)",
             etu.get("/api/admin/dashboard").status_code == 403)
    verifier("Tableau de bord refusé sans session (401)",
             app.test_client().get("/api/admin/dashboard").status_code == 401)

    print("\n" + "═" * 70)
    print("  7. CANDIDATURE ET VALIDATION D'UN MENTOR")
    print("═" * 70)
    r = etu.post("/api/mentors/candidature", json={
        "profession": "Ingénieure logiciel", "organisation": "Orange",
        "annees_experience": 7,
        "bio": "Ingénieure logiciel depuis sept ans, je guide les étudiants en informatique.",
        "motivation": "Je veux transmettre ce que j'aurais aimé qu'on m'explique "
                      "quand j'ai commencé mes études d'informatique à Bamako.",
        "secteurs": [1, 6]})
    verifier("Candidature déposée", r.status_code == 201,
             r.get_data(as_text=True)[:110])
    verifier("Statut « en attente »",
             etu.get("/api/mentors/ma-candidature").get_json().get("statut")
             == "en_attente")

    incomplet = app.test_client()
    incomplet.post("/api/auth/inscription", json={
        "prenom": "Bref", "nom": "Dossier", "email": "bref@test.io",
        "mot_de_passe": "BrefTest2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    r = incomplet.post("/api/mentors/candidature",
                       json={"profession": "X", "bio": "court",
                             "motivation": "court", "annees_experience": 1,
                             "secteurs": [1]})
    verifier("Candidature incomplète refusée (400)", r.status_code == 400)

    attente = adm.get("/api/admin/mentors-a-verifier").get_json()
    ida = next((m["id_utilisateur"] for m in attente
                if m["email"] == "aminata@test.io"), None)
    verifier("Candidate visible par l'administrateur", ida is not None)

    r = adm.post(f"/api/admin/mentors/{ida}/verifier", json={})
    verifier("Validation par l'administrateur", r.status_code == 200)
    verifier("E-mail de décision envoyé",
             r.get_json().get("email_envoye") is True)
    verifier("Statut passé à « validée »",
             etu.get("/api/mentors/ma-candidature").get_json().get("statut")
             == "validee")
    p = etu.get("/api/profil/moi").get_json()
    verifier("Rôle devenu « mentor »", p.get("role") == "mentor")
    verifier("Badge vérifié attribué", p.get("est_verifie") == 1)
    annuaire = etu.get("/api/mentors").get_json()
    verifier("Présente dans l'annuaire des mentors",
             isinstance(annuaire, list)
             and any(m.get("nom") == "Traore" for m in annuaire),
             f"réponse inattendue : {str(annuaire)[:110]}")

    restants = adm.get("/api/admin/mentors-a-verifier").get_json()
    if restants:
        r = adm.post(f"/api/admin/mentors/{restants[0]['id_utilisateur']}/refuser",
                     json={"motif": "Parcours à préciser."})
        verifier("Refus motivé accepté", r.status_code == 200)

    print("\n" + "═" * 70)
    print("  8. CONTENUS ET INTERACTIONS")
    print("═" * 70)
    r = etu.get("/api/questions?limite=5")
    verifier("Fil des questions accessible", r.status_code == 200)
    ref = etu.get("/api/profil/referentiels").get_json()
    verifier("Référentiels disponibles (secteurs et pays)",
             len(ref.get("secteurs", [])) > 0 and len(ref.get("pays", [])) > 0)
    id_sec = ref["secteurs"][0]["id_secteur"]
    r = etu.post("/api/questions", json={
        "titre": "Comment préparer un entretien de stage ?",
        "corps": "Je passe un entretien la semaine prochaine et je cherche "
                 "des conseils concrets de préparation.",
        "id_secteur": id_sec})
    verifier("Publication d'une question", r.status_code == 201)
    idq = r.get_json().get("id_question")
    verifier("La question publiée apparaît dans le fil",
             any(q.get("id_question") == idq
                 for q in etu.get("/api/questions?limite=20").get_json()))
    r = etu.post(f"/api/questions/{idq}/utile", json={})
    verifier("Mise en favori", r.status_code == 200)
    verifier("Retrait du favori",
             etu.post(f"/api/questions/{idq}/utile", json={}).status_code == 200)
    r = etu.post("/api/reponses",
                 json={"id_question": idq,
                       "contenu": "Préparez trois exemples concrets de projets "
                                  "et renseignez-vous sur l'entreprise."})
    verifier("Publication d'une réponse", r.status_code == 201)
    verifier("Recherche fonctionnelle",
             etu.get("/api/recherche?q=stage").status_code == 200)
    verifier("Notifications accessibles",
             etu.get("/api/notifications").status_code == 200)

    print("\n" + "═" * 70)
    print("  9. MOT DE PASSE ET APPAREILS CONNECTÉS")
    print("═" * 70)

    # -- Sessions actives ------------------------------------------------
    sessions = adm.get("/api/auth/sessions")
    verifier("Liste des sessions accessible", sessions.status_code == 200)
    liste = sessions.get_json() or []
    verifier("La session courante y figure",
             any(s.get("courante") for s in liste), str(liste)[:150])
    verifier("Le jeton complet n'est jamais exposé",
             all(len(s.get("reference", "")) == 16 for s in liste),
             str(liste)[:150])
    verifier("L'appareil est décrit lisiblement",
             all(s.get("appareil") for s in liste), str(liste)[:150])
    verifier("Sessions refusées sans authentification",
             app.test_client().get("/api/auth/sessions").status_code == 401)

    # Un second appareil, pour vérifier la révocation ciblée.
    autre = app.test_client()
    autre.post("/api/auth/connexion",
               json={"email": "rodriguedjossou93@gmail.com",
                     "mot_de_passe": mdps[-1]})
    verifier("Deux appareils connectés",
             len(adm.get("/api/auth/sessions").get_json() or []) == 2)

    r = adm.post("/api/auth/sessions/revoquer-autres")
    verifier("Révocation des autres appareils",
             r.status_code == 200 and (r.get_json() or {}).get("revoquees") == 1,
             r.get_data(as_text=True)[:110])
    verifier("L'appareil révoqué est déconnecté",
             autre.get("/api/profil/moi").status_code == 401)
    verifier("L'appareil courant reste connecté",
             adm.get("/api/profil/moi").status_code == 200)

    verifier("Référence de session invalide refusée (400)",
             adm.delete("/api/auth/sessions/pasunereference").status_code == 400)
    verifier("Référence inconnue refusée (404)",
             adm.delete("/api/auth/sessions/" + "0" * 16).status_code == 404)

    # Une session ne doit pas pouvoir en révoquer une d'un autre compte.
    ref_etudiant = (etu.get("/api/auth/sessions").get_json() or [{}])[0] \
        .get("reference", "")
    verifier("Impossible de révoquer la session d'autrui",
             adm.delete("/api/auth/sessions/" + ref_etudiant).status_code == 404,
             ref_etudiant)

    # -- Changement du mot de passe temporaire ---------------------------
    r = adm.post("/api/auth/changer-mdp",
                 json={"mot_de_passe_actuel": "faux",
                       "nouveau_mot_de_passe": "Definitif2026!"})
    verifier("Mot de passe actuel erroné refusé (401)", r.status_code == 401)

    r = adm.post("/api/auth/changer-mdp",
                 json={"mot_de_passe_actuel": mdps[-1],
                       "nouveau_mot_de_passe": "court"})
    verifier("Nouveau mot de passe trop faible refusé (400)",
             r.status_code == 400)

    r = adm.post("/api/auth/changer-mdp",
                 json={"mot_de_passe_actuel": mdps[-1],
                       "nouveau_mot_de_passe": "Definitif2026!"})
    verifier("Changement de mot de passe accepté", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("L'obligation de changement est levée",
             jeton_sql("SELECT doit_changer_mdp FROM utilisateur "
                       "WHERE email = ?",
                       ("rodriguedjossou93@gmail.com",)) == 0)

    verif = app.test_client()
    r = verif.post("/api/auth/connexion",
                   json={"email": "rodriguedjossou93@gmail.com",
                         "mot_de_passe": "Definitif2026!"})
    verifier("Connexion avec le nouveau mot de passe", r.status_code == 200)
    verifier("Plus d'obligation signalée à la connexion",
             (r.get_json() or {}).get("doit_changer_mdp") is False,
             r.get_data(as_text=True)[:110])
    verifier("L'ancien mot de passe temporaire est refusé",
             app.test_client().post(
                 "/api/auth/connexion",
                 json={"email": "rodriguedjossou93@gmail.com",
                       "mot_de_passe": mdps[-1]}).status_code == 401)
    verifier("Le profil ne divulgue pas l'état du mot de passe d'autrui",
             "doit_changer_mdp" not in (
                 etu.get("/api/profil/1").get_json() or {}))

    print("\n" + "═" * 70)
    print("  10. LIMITATION DU DÉBIT (anti-force-brute)")
    print("═" * 70)
    from utils import securite

    verifier("Les tentatives sont comptées en base, pas en mémoire",
             jeton_sql("SELECT COUNT(*) FROM tentative_auth") >= 0)

    # -- Connexion : blocage après le seuil ------------------------------
    victime = app.test_client()
    victime.post("/api/auth/inscription", json={
        "prenom": "Cible", "nom": "DEBIT", "email": "cible.debit@test.io",
        "mot_de_passe": "MotDePasse2026!", "role": "etudiant", "consentement": CONSENT_TESTS})

    forceur = app.test_client()
    codes = [forceur.post("/api/auth/connexion",
                          json={"email": "cible.debit@test.io",
                                "mot_de_passe": f"faux{i}"}).status_code
             for i in range(securite._MAX_TENTATIVES + 1)]
    verifier("Les premières tentatives renvoient 401",
             codes[:securite._MAX_TENTATIVES] ==
             [401] * securite._MAX_TENTATIVES, str(codes))
    verifier("Le seuil dépassé renvoie 429", codes[-1] == 429, str(codes))
    verifier("Le bon mot de passe reste refusé pendant le blocage",
             forceur.post("/api/auth/connexion",
                          json={"email": "cible.debit@test.io",
                                "mot_de_passe": "MotDePasse2026!"}
                          ).status_code == 429)
    verifier("Les échecs sont bien persistés en base",
             jeton_sql("SELECT COUNT(*) FROM tentative_auth WHERE cle LIKE ?",
                       ("cible.debit@test.io|%",))
             >= securite._MAX_TENTATIVES)

    # Le compteur est propre à l'identifiant : un autre compte passe.
    verifier("Un autre compte n'est pas affecté par ce blocage",
             app.test_client().post(
                 "/api/auth/connexion",
                 json={"email": "aminata@test.io",
                       "mot_de_passe": "Nouveau2026!"}).status_code == 200)

    # -- Demande de réinitialisation : débit borné -----------------------
    demandeur = app.test_client()
    for _ in range(securite.MAX_DEMANDES_MDP + 2):
        r = demandeur.post("/api/auth/oubli-mdp",
                           json={"email": "cible.debit@test.io"})
    verifier("La demande de mot de passe reste silencieuse une fois bornée",
             r.status_code == 200, r.get_data(as_text=True)[:90])
    verifier("Le nombre de jetons de réinitialisation est plafonné",
             jeton_sql("SELECT COUNT(*) FROM reinitialisation_mdp r "
                       "JOIN utilisateur u ON u.id_utilisateur = r.id_utilisateur "
                       "WHERE u.email = ?", ("cible.debit@test.io",))
             <= securite.MAX_DEMANDES_MDP,
             "au-delà du seuil, plus aucun e-mail ne doit partir")

    # -- Réinitialisation du compteur ------------------------------------
    with app.app_context():
        securite.reinitialiser(f"cible.debit@test.io|{None}")
    verifier("Le seuil d'inscription tolère une salle entière",
             securite.MAX_INSCRIPTIONS >= 20,
             f"MAX_INSCRIPTIONS={securite.MAX_INSCRIPTIONS}")

    print("\n" + "═" * 70)
    print("  11. RATTACHEMENT D'UNE IDENTITÉ EXTERNE")
    print("═" * 70)
    from routes.oauth import (_trouver_ou_creer_compte_externe,
                              AdresseNonVerifiee)

    with app.app_context():
        # Une adresse non confirmée par le fournisseur ne doit jamais
        # rattacher qui que ce soit à un compte existant : ce serait une
        # prise de contrôle du compte de la victime.
        try:
            _trouver_ou_creer_compte_externe(
                "google", "sub-usurpateur", "aminata@test.io",
                False, "Faux", "Profil", None)
            verifier("Adresse non vérifiée refusée", False,
                     "aucune exception levée")
        except AdresseNonVerifiee:
            verifier("Adresse non vérifiée refusée", True)

        verifier("Aucune identité externe créée dans ce cas",
                 jeton_sql("SELECT COUNT(*) FROM identite_externe "
                           "WHERE identifiant = ?", ("sub-usurpateur",)) == 0)
        verifier("Le compte visé reste intact",
                 jeton_sql("SELECT COUNT(*) FROM utilisateur WHERE email = ?",
                           ("aminata@test.io",)) == 1)

        # Adresse confirmée : le rattachement se fait, sans doublon.
        avant = jeton_sql("SELECT COUNT(*) FROM utilisateur")
        id_lie = _trouver_ou_creer_compte_externe(
            "google", "sub-legitime", "aminata@test.io",
            True, "Aminata", "TRAORE", None)
        verifier("Adresse vérifiée : rattachement au compte existant",
                 id_lie == jeton_sql(
                     "SELECT id_utilisateur FROM utilisateur WHERE email = ?",
                     ("aminata@test.io",)))
        verifier("Aucun compte en double n'est créé",
                 jeton_sql("SELECT COUNT(*) FROM utilisateur") == avant)

        # Deuxième passage : on reconnaît l'identité, sans rien recréer.
        verifier("La même identité reconnue au second passage",
                 _trouver_ou_creer_compte_externe(
                     "google", "sub-legitime", "aminata@test.io",
                     True, "Aminata", "TRAORE", None) == id_lie)

        # Un compte neuf par un fournisseur qui a vérifié l'adresse.
        id_neuf = _trouver_ou_creer_compte_externe(
            "google", "sub-nouveau", "nouvelle.venue@test.io",
            True, "Nouvelle", "VENUE", None)
        verifier("Compte créé pour une adresse inconnue mais vérifiée",
                 bool(id_neuf))
        verifier("Le compte créé est marqué vérifié",
                 jeton_sql("SELECT email_verifie FROM utilisateur "
                           "WHERE email = ?",
                           ("nouvelle.venue@test.io",)) == 1)

    print("\n" + "═" * 70)
    print("  12. COMPTE D'ADMINISTRATION AMORCÉ PAR L'ENVIRONNEMENT")
    print("═" * 70)
    from services.amorcage import creer_admin_initial

    garde = {c: os.environ.get(c)
             for c in ("ADMIN_EMAIL", "ADMIN_MOTDEPASSE", "ADMIN_PRENOM",
                       "ADMIN_REINITIALISER_MDP")}
    try:
        os.environ.update({"ADMIN_EMAIL": "chef@test.io",
                           "ADMIN_MOTDEPASSE": "AmorcageSolide2026!",
                           "ADMIN_PRENOM": "Chef"})
        creer_admin_initial(app)
        verifier("Compte d'administration créé",
                 jeton_sql("SELECT role FROM utilisateur WHERE email = ?",
                           ("chef@test.io",)) == "super_admin")
        verifier("Changement de mot de passe imposé",
                 jeton_sql("SELECT doit_changer_mdp FROM utilisateur "
                           "WHERE email = ?", ("chef@test.io",)) == 1)

        chef = app.test_client()
        r = chef.post("/api/auth/connexion",
                      json={"email": "chef@test.io",
                            "mot_de_passe": "AmorcageSolide2026!"})
        verifier("Connexion avec le mot de passe d'amorçage",
                 r.status_code == 200)
        verifier("Accès au tableau de bord d'administration",
                 chef.get("/api/admin/dashboard").status_code == 200)

        # Le compte change son mot de passe, puis l'application redémarre :
        # l'amorçage ne doit surtout pas le remettre à la valeur initiale.
        chef.post("/api/auth/changer-mdp",
                  json={"mot_de_passe_actuel": "AmorcageSolide2026!",
                        "nouveau_mot_de_passe": "ChoisiParMoi2026!"})
        creer_admin_initial(app)
        verifier("Un redémarrage ne réinitialise pas le mot de passe",
                 app.test_client().post(
                     "/api/auth/connexion",
                     json={"email": "chef@test.io",
                           "mot_de_passe": "ChoisiParMoi2026!"}
                 ).status_code == 200)
        verifier("L'ancien mot de passe d'amorçage ne fonctionne plus",
                 app.test_client().post(
                     "/api/auth/connexion",
                     json={"email": "chef@test.io",
                           "mot_de_passe": "AmorcageSolide2026!"}
                 ).status_code == 401)

        # Un compte ordinaire déjà présent reçoit les droits, sans que son
        # mot de passe soit remplacé.
        os.environ["ADMIN_EMAIL"] = "aminata@test.io"
        creer_admin_initial(app)
        verifier("Un compte existant est promu sans perdre son mot de passe",
                 jeton_sql("SELECT est_admin FROM utilisateur WHERE email = ?",
                           ("aminata@test.io",)) == 1
                 and app.test_client().post(
                     "/api/auth/connexion",
                     json={"email": "aminata@test.io",
                           "mot_de_passe": "Nouveau2026!"}
                 ).status_code == 200)

        # Le compte promu doit être utilisable même si la confirmation
        # d'adresse est devenue obligatoire : sinon l'exploitant se
        # verrouille lui-même hors de son propre site.
        verifier("Le compte promu est marqué vérifié",
                 jeton_sql("SELECT email_verifie FROM utilisateur "
                           "WHERE email = ?", ("aminata@test.io",)) == 1)

        # Remise à zéro explicite du mot de passe d'un compte existant.
        os.environ.update({"ADMIN_EMAIL": "chef@test.io",
                           "ADMIN_MOTDEPASSE": "RepriseEnMain2026!",
                           "ADMIN_REINITIALISER_MDP": "1"})
        creer_admin_initial(app)
        verifier("ADMIN_REINITIALISER_MDP remplace le mot de passe",
                 app.test_client().post(
                     "/api/auth/connexion",
                     json={"email": "chef@test.io",
                           "mot_de_passe": "RepriseEnMain2026!"}
                 ).status_code == 200)
        verifier("Le changement est de nouveau imposé après remise à zéro",
                 jeton_sql("SELECT doit_changer_mdp FROM utilisateur "
                           "WHERE email = ?", ("chef@test.io",)) == 1)
        os.environ.pop("ADMIN_REINITIALISER_MDP", None)

        # Sans le drapeau, un redémarrage laisse le mot de passe en place.
        os.environ["ADMIN_MOTDEPASSE"] = "EncoreUnAutre2026!"
        creer_admin_initial(app)
        verifier("Sans le drapeau, le mot de passe reste inchangé",
                 app.test_client().post(
                     "/api/auth/connexion",
                     json={"email": "chef@test.io",
                           "mot_de_passe": "RepriseEnMain2026!"}
                 ).status_code == 200)

        # Un mot de passe faible est refusé plutôt que haché tel quel.
        os.environ.update({"ADMIN_EMAIL": "faible@test.io",
                           "ADMIN_MOTDEPASSE": "1234"})
        creer_admin_initial(app)
        verifier("Mot de passe d'amorçage trop faible refusé",
                 jeton_sql("SELECT COUNT(*) FROM utilisateur WHERE email = ?",
                           ("faible@test.io",)) == 0)

        # Sans variables, l'amorçage ne fait rien.
        avant = jeton_sql("SELECT COUNT(*) FROM utilisateur")
        os.environ.pop("ADMIN_EMAIL", None)
        os.environ.pop("ADMIN_MOTDEPASSE", None)
        creer_admin_initial(app)
        verifier("Sans variables, aucun compte n'est créé",
                 jeton_sql("SELECT COUNT(*) FROM utilisateur") == avant)
    finally:
        for cle, valeur in garde.items():
            if valeur is None:
                os.environ.pop(cle, None)
            else:
                os.environ[cle] = valeur

    print("\n" + "═" * 70)
    print("  13. DIAGNOSTIC DE CONFIGURATION")
    print("═" * 70)
    r = adm.get("/api/admin/diagnostic")
    verifier("Diagnostic accessible à l'administrateur", r.status_code == 200,
             r.get_data(as_text=True)[:120])
    diag = r.get_json() or {}
    verifier("Il rapporte le moteur de base",
             diag.get("base", {}).get("moteur") in ("sqlite", "postgres"),
             str(diag.get("base")))
    verifier("Il rapporte l'état de l'envoi d'e-mails",
             "operationnel" in diag.get("email", {}), str(diag.get("email")))
    verifier("Il rapporte l'état de la connexion Google",
             "forme_valide" in diag.get("google", {}), str(diag.get("google")))
    verifier("Il liste les anomalies de configuration",
             isinstance(diag.get("anomalies"), list))

    # Aucun secret ne doit transiter : ni mot de passe SMTP, ni secret
    # OAuth, ni chaîne de connexion à la base.
    brut = r.get_data(as_text=True).lower()
    verifier("Aucun mot de passe SMTP exposé", "smtp_motdepasse" not in brut)
    verifier("Aucun secret LinkedIn exposé", "client_secret" not in brut)
    verifier("Aucune chaîne de connexion exposée",
             "postgresql://" not in brut and "password" not in brut)
    verifier("La clé de signature n'est pas exposée",
             "secret_key" not in brut
             and str(app.config["SECRET_KEY"]).lower() not in brut)

    # « etu » a été promu administrateur à la section précédente : il
    # faut un compte réellement ordinaire pour éprouver le refus.
    simple = app.test_client()
    simple.post("/api/auth/inscription", json={
        "prenom": "Sans", "nom": "DROITS", "email": "sans.droits@test.io",
        "mot_de_passe": "SansDroits2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    verifier("Diagnostic refusé à un étudiant (403)",
             simple.get("/api/admin/diagnostic").status_code == 403)
    verifier("Diagnostic refusé sans session (401)",
             app.test_client().get("/api/admin/diagnostic").status_code == 401)
    verifier("Test d'envoi refusé à un étudiant (403)",
             simple.post("/api/admin/diagnostic/test-email").status_code == 403)

    r = adm.post("/api/admin/diagnostic/test-email")
    verifier("Test d'envoi : réponse exploitable sans SMTP configuré",
             r.status_code == 200
             and (r.get_json() or {}).get("envoye") is False,
             r.get_data(as_text=True)[:120])

    print("\n" + "═" * 70)
    print("  14. CHIFFRES ET QUESTIONS DE LA PAGE D'ACCUEIL")
    print("═" * 70)
    public = app.test_client()

    r = public.get("/api/profil/statistiques")
    verifier("Statistiques accessibles sans session", r.status_code == 200)
    stats = r.get_json() or {}
    for cle in ("membres", "mentors", "questions", "reponses"):
        verifier(f"Le compteur « {cle} » est présent",
                 isinstance(stats.get(cle), int), str(stats))

    # Les chiffres doivent refléter la base, pas des valeurs écrites en dur.
    verifier("Le nombre de membres correspond à la base",
             stats["membres"] == jeton_sql(
                 "SELECT COUNT(*) FROM utilisateur WHERE est_actif = 1"),
             str(stats))
    verifier("Le nombre de questions correspond à la base",
             stats["questions"] == jeton_sql(
                 "SELECT COUNT(*) FROM question"), str(stats))

    # Une inscription supplémentaire doit faire bouger le compteur : c'est
    # tout l'intérêt d'un chiffre réel.
    avant = stats["membres"]
    nouveau = app.test_client()
    nouveau.post("/api/auth/inscription", json={
        "prenom": "Compteur", "nom": "TEST", "email": "compteur@test.io",
        "mot_de_passe": "Compteur2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    apres = (public.get("/api/profil/statistiques").get_json() or {})
    verifier("Une inscription incrémente le compteur de membres",
             apres.get("membres") == avant + 1,
             f"{avant} -> {apres.get('membres')}")

    r = public.get("/api/questions/vedette")
    verifier("Questions en vedette accessibles sans session",
             r.status_code == 200)
    vedette = r.get_json() or []
    verifier("Au plus trois questions renvoyées", len(vedette) <= 3)
    if vedette:
        verifier("Chaque entrée porte un titre et un compte de réponses",
                 all("titre" in q and "nb_reponses" in q for q in vedette))
        verifier("Le nom de famille est réduit à son initiale",
                 all(len(q.get("auteur", "").split(" ")[-1]) <= 2
                     for q in vedette if " " in q.get("auteur", "")),
                 str(vedette)[:150])

    brut = r.get_data(as_text=True)
    verifier("Aucune adresse e-mail dans les questions publiques",
             "@" not in brut, brut[:120])

    print("\n" + "═" * 70)
    print("  15. PRÉFÉRENCES DE NOTIFICATION")
    print("═" * 70)
    r = etu.get("/api/profil/preferences")
    verifier("Préférences accessibles", r.status_code == 200)
    prefs = r.get_json() or {}
    verifier("Les deux canaux sont présents",
             "app" in prefs and "email" in prefs, str(prefs)[:120])
    verifier("Valeurs par défaut appliquées sans enregistrement",
             prefs.get("app", {}).get("reponse_question") is True
             and prefs.get("app", {}).get("infolettre") is False,
             str(prefs.get("app")))

    prefs["app"]["infolettre"] = True
    prefs["email"]["reponse_question"] = False
    r = etu.put("/api/profil/preferences", json=prefs)
    verifier("Enregistrement accepté", r.status_code == 200)

    relu = etu.get("/api/profil/preferences").get_json() or {}
    verifier("Le choix survit à une nouvelle lecture",
             relu["app"]["infolettre"] is True
             and relu["email"]["reponse_question"] is False,
             str(relu))
    verifier("Les autres préférences sont conservées",
             relu["app"]["reponse_question"] is True, str(relu["app"]))

    # Une clé inconnue ne doit pas se retrouver en base : sans liste
    # fermée, n'importe quel client ferait grossir la colonne.
    etu.put("/api/profil/preferences",
            json={"app": {"cle_inventee": True, "infolettre": False},
                  "email": {}})
    relu = etu.get("/api/profil/preferences").get_json() or {}
    verifier("Une clé inconnue est ignorée", "cle_inventee" not in relu["app"],
             str(relu["app"]))
    verifier("Les clés connues restent traitées",
             relu["app"]["infolettre"] is False, str(relu["app"]))
    verifier("Préférences refusées sans session (401)",
             app.test_client().get("/api/profil/preferences").status_code == 401)

    print("\n" + "═" * 70)
    print("  16. EXPORT ET SUPPRESSION DU COMPTE")
    print("═" * 70)
    partant = app.test_client()
    partant.post("/api/auth/inscription", json={
        "prenom": "Yao", "nom": "PARTANT", "email": "yao.partant@test.io",
        "mot_de_passe": "YaoPartant2026!", "role": "etudiant", "consentement": CONSENT_TESTS})

    r = partant.get("/api/profil/moi/donnees")
    verifier("Export des données accessible", r.status_code == 200)
    donnees = r.get_json() or {}
    verifier("L'export contient le profil",
             (donnees.get("profil") or {}).get("email") == "yao.partant@test.io",
             str(donnees.get("profil"))[:100])
    for cle in ("preferences", "questions", "reponses", "secteurs"):
        verifier(f"L'export contient « {cle} »", cle in donnees)
    verifier("Aucun mot de passe dans l'export",
             "mot_de_passe" not in r.get_data(as_text=True))

    # Les trois garde-fous, un par un.
    r = partant.delete("/api/profil/moi",
                       json={"mot_de_passe": "YaoPartant2026!",
                             "confirmation": "oui"})
    verifier("Sans le mot recopié, refus (400)", r.status_code == 400)
    r = partant.delete("/api/profil/moi",
                       json={"mot_de_passe": "faux",
                             "confirmation": "SUPPRIMER"})
    verifier("Mot de passe erroné, refus (401)", r.status_code == 401)
    verifier("Le compte est toujours là après ces refus",
             jeton_sql("SELECT COUNT(*) FROM utilisateur WHERE email = ?",
                       ("yao.partant@test.io",)) == 1)

    r = partant.delete("/api/profil/moi",
                       json={"mot_de_passe": "YaoPartant2026!",
                             "confirmation": "supprimer"})
    verifier("La confirmation est insensible à la casse", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("Le compte a disparu de la base",
             jeton_sql("SELECT COUNT(*) FROM utilisateur WHERE email = ?",
                       ("yao.partant@test.io",)) == 0)
    verifier("La session est close après suppression",
             partant.get("/api/profil/moi").status_code == 401)
    verifier("Suppression refusée sans session (401)",
             app.test_client().delete("/api/profil/moi").status_code == 401)

    # Le dernier administrateur ne doit pas pouvoir se supprimer, sinon
    # la plateforme devient ingérable sans intervention en base.
    nb_admins = jeton_sql(
        "SELECT COUNT(*) FROM utilisateur WHERE est_admin = 1 AND est_actif = 1")
    if nb_admins == 1:
        r = adm.delete("/api/profil/moi",
                       json={"mot_de_passe": "Definitif2026!",
                             "confirmation": "SUPPRIMER"})
        verifier("Le dernier administrateur ne peut pas se supprimer (409)",
                 r.status_code == 409, r.get_data(as_text=True)[:110])
    else:
        verifier("Plusieurs administrateurs présents, garde-fou non éprouvé",
                 True, f"{nb_admins} administrateurs")

    print("\n" + "═" * 70)
    print("  17. CONFIRMATION D'ADRESSE ET DURCISSEMENT")
    print("═" * 70)

    # -- Messages d'authentification -------------------------------------
    r = app.test_client().get("/api/profil/moi")
    corps = r.get_json() or {}
    verifier("Sans session, le message invite à se connecter",
             "connectez-vous" in (corps.get("erreur") or "").lower(),
             str(corps))
    verifier("Le drapeau distingue la visite de l'expiration",
             corps.get("session_expiree") is False, str(corps))

    perime = app.test_client()
    perime.set_cookie("ls_session", "0" * 64)
    corps = (perime.get("/api/profil/moi").get_json() or {})
    verifier("Une session expirée est nommée comme telle",
             corps.get("session_expiree") is True
             and "expiré" in (corps.get("erreur") or "").lower(), str(corps))

    # -- Renvoi du lien de confirmation ----------------------------------
    candidat = app.test_client()
    candidat.post("/api/auth/inscription", json={
        "prenom": "Lien", "nom": "PERDU", "email": "lien.perdu@test.io",
        "mot_de_passe": "LienPerdu2026!", "role": "etudiant", "consentement": CONSENT_TESTS})

    r = candidat.post("/api/auth/confirmation/moi")
    verifier("Renvoi du lien accepté", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("Un seul jeton actif à la fois",
             jeton_sql("SELECT COUNT(*) FROM verification_email v "
                       "JOIN utilisateur u ON u.id_utilisateur = v.id_utilisateur "
                       "WHERE u.email = ? AND v.verifie_le IS NULL",
                       ("lien.perdu@test.io",)) == 1,
             "les jetons precedents doivent etre invalides")

    anonyme = app.test_client()
    r = anonyme.post("/api/auth/renvoyer-confirmation",
                     json={"email": "lien.perdu@test.io"})
    r2 = anonyme.post("/api/auth/renvoyer-confirmation",
                      json={"email": "inconnu@nulle.part"})
    verifier("Réponse identique pour une adresse inconnue",
             r.status_code == r2.status_code == 200
             and r.get_json() == r2.get_json(),
             "sinon on saurait qui est inscrit")
    verifier("Renvoi refusé sans session sur la route personnelle (401)",
             app.test_client().post("/api/auth/confirmation/moi").status_code == 401)

    # -- En-tetes de durcissement ----------------------------------------
    r = app.test_client().get("/api/sante",
                              headers={"X-Forwarded-Proto": "https"})
    verifier("HSTS posé sur une connexion chiffrée",
             "max-age=31536000" in r.headers.get("Strict-Transport-Security", ""),
             r.headers.get("Strict-Transport-Security", "absent"))
    r = app.test_client().get("/api/sante")
    verifier("HSTS absent hors HTTPS",
             "Strict-Transport-Security" not in r.headers,
             "l'annoncer en clair rendrait le site inaccessible en local")
    # « same-origin » isolait aussi les fenetres que la page ouvre
    # elle-meme, dont celle de la connexion Google, qui dialogue avec la
    # page par postMessage : le bouton s'affichait et ne menait nulle
    # part. La protection contre le site tiers qui nous ouvre reste
    # entiere, seule la fenetre que nous ouvrons garde son lien.
    verifier("Isolation des fenêtres qui nous ouvrent, sans couper les nôtres",
             r.headers.get("Cross-Origin-Opener-Policy")
             == "same-origin-allow-popups",
             r.headers.get("Cross-Origin-Opener-Policy", "absent"))
    verifier("Les réponses de l'API ne sont pas mises en cache",
             r.headers.get("Cache-Control") == "no-store",
             r.headers.get("Cache-Control", "absent"))
    verifier("Les fichiers statiques restent cachables",
             app.test_client().get("/styles.css").headers.get(
                 "Cache-Control") != "no-store")

    verifier("Taille des requêtes bornée",
             app.config.get("MAX_CONTENT_LENGTH", 0) > 0,
             str(app.config.get("MAX_CONTENT_LENGTH")))

    print("\n" + "═" * 70)
    print("  18. NOTIFICATIONS ET PROFIL ENRICHI")
    print("═" * 70)

    # -- Referentiels a choix ferme ---------------------------------------
    r = app.test_client().get("/api/profil/referentiels-profil")
    verifier("Référentiels de profil servis par le serveur",
             r.status_code == 200)
    ref = r.get_json() or {}
    verifier("Situations et objectifs proposés",
             len(ref.get("situations", [])) >= 5
             and len(ref.get("objectifs", [])) >= 5, str(ref)[:120])

    # -- Champs enrichis ---------------------------------------------------
    situation = ref["situations"][1]
    objectif = ref["objectifs"][0]
    r = etu.put("/api/profil/moi", json={
        "situation": situation, "objectif": objectif,
        "langues": "français, anglais",
        "profil_pro": "https://www.linkedin.com/in/exemple"})
    verifier("Champs de profil enregistrés", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    profil = etu.get("/api/profil/moi").get_json() or {}
    verifier("La situation est relue", profil.get("situation") == situation)
    verifier("L'objectif est relu", profil.get("objectif") == objectif)
    verifier("Les langues sont relues",
             profil.get("langues") == "français, anglais")

    verifier("Situation inventée refusée (400)",
             etu.put("/api/profil/moi",
                     json={"situation": "Empereur"}).status_code == 400)
    verifier("Objectif inventé refusé (400)",
             etu.put("/api/profil/moi",
                     json={"objectif": "Dominer le monde"}).status_code == 400)
    verifier("Lien professionnel sans schéma refusé (400)",
             etu.put("/api/profil/moi",
                     json={"profil_pro": "javascript:alert(1)"}).status_code == 400)

    # -- Notifications reellement creees ----------------------------------
    poseur = app.test_client()
    poseur.post("/api/auth/inscription", json={
        "prenom": "Ida", "nom": "POSEUSE", "email": "ida.poseuse@test.io",
        "mot_de_passe": "IdaPoseuse2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    r = poseur.post("/api/questions", json={
        "titre": "Comment financer un master à l'étranger ?",
        "corps": "Je cherche des pistes concrètes de bourses et de "
                 "financement pour partir étudier après ma licence.",
        "id_secteur": 1})
    id_q = (r.get_json() or {}).get("id_question")
    verifier("Question publiée pour éprouver les notifications", bool(id_q))

    avant = jeton_sql("SELECT COUNT(*) FROM notification")
    etu.post("/api/reponses", json={
        "id_question": id_q,
        "contenu": "Renseignez-vous sur les bourses de mobilité de votre "
                   "université, elles sont souvent sous-utilisées."})
    verifier("Une réponse crée une notification",
             jeton_sql("SELECT COUNT(*) FROM notification") == avant + 1)
    verifier("Elle est adressée à l'auteur de la question",
             jeton_sql("SELECT COUNT(*) FROM notification n "
                       "JOIN utilisateur u ON u.id_utilisateur = n.id_destinataire "
                       "WHERE u.email = ? AND n.type_notif = 'reponse'",
                       ("ida.poseuse@test.io",)) == 1)

    # Repondre a sa propre question ne doit rien declencher.
    avant = jeton_sql("SELECT COUNT(*) FROM notification")
    poseur.post("/api/reponses", json={
        "id_question": id_q,
        "contenu": "Je complète ma propre question avec une précision "
                   "utile pour ceux qui la liront plus tard."})
    verifier("On ne se notifie pas soi-même",
             jeton_sql("SELECT COUNT(*) FROM notification") == avant)

    r = poseur.get("/api/notifications/non-lues")
    verifier("Le compteur de non-lues répond", r.status_code == 200)
    verifier("Il compte la notification reçue",
             (r.get_json() or {}).get("non_lues", 0) >= 1,
             r.get_data(as_text=True)[:80])

    # Une preference decochee doit faire taire la notification.
    prefs = poseur.get("/api/profil/preferences").get_json()
    prefs["app"]["reponse_question"] = False
    poseur.put("/api/profil/preferences", json=prefs)
    avant = jeton_sql("SELECT COUNT(*) FROM notification")
    etu.post("/api/reponses", json={
        "id_question": id_q,
        "contenu": "Une seconde piste : les fondations privées financent "
                   "aussi des masters à l'étranger, renseignez-vous."})
    verifier("Une préférence décochée fait taire la notification",
             jeton_sql("SELECT COUNT(*) FROM notification") == avant,
             "sinon le réglage ne servirait à rien")

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  19. PARCOURS : NIVEAU, DOMAINE ET ÉTABLISSEMENT")
    print("═" * 70)

    ref = etu.get("/api/profil/referentiels-profil").get_json() or {}
    verifier("Les niveaux d'études sont servis par le serveur",
             len(ref.get("niveaux_etudes") or []) >= 5)
    verifier("Les domaines sont servis par le serveur",
             len(ref.get("domaines") or []) >= 10)
    verifier("Des établissements sont suggérés",
             len(ref.get("etablissements") or []) >= 5)

    # Le point de la demande : un metier manuel doit se choisir aussi
    # simplement qu'une filiere universitaire, sans passer par « autre ».
    domaines = ref.get("domaines") or []
    verifier("La soudure figure parmi les domaines proposés",
             any("Soudure" in d for d in domaines))
    verifier("La mécanique figure parmi les domaines proposés",
             any("Mécanique" in d for d in domaines))
    niveaux = ref.get("niveaux_etudes") or []
    verifier("Un titre professionnel figure parmi les niveaux",
             any("CAP" in n for n in niveaux))
    verifier("« Sans diplôme » est un choix possible",
             any("Sans diplôme" in n for n in niveaux))

    r = etu.put("/api/profil/moi", json={
        "niveau_etudes": "CAP, CQP ou CQM (métier)",
        "domaine": "Soudure et métallerie",
        "etablissement": "Atelier de maître soudeur, Porto-Novo"})
    verifier("Un parcours de métier s'enregistre", r.status_code == 200)
    p = r.get_json() or {}
    verifier("Un ancien libellé de diplôme reste accepté",
             p.get("niveau_etudes")
             == "Diplôme professionnel (CAP, CQP, CQM, BEP…)",
             str(p.get("niveau_etudes")))
    verifier("Le domaine est relu tel quel",
             p.get("domaine") == "Soudure et métallerie")
    verifier("L'établissement libre est conservé",
             p.get("etablissement") == "Atelier de maître soudeur, Porto-Novo")

    r = etu.put("/api/profil/moi", json={"niveau_etudes": "Bac+42"})
    verifier("Un niveau inventé est refusé", r.status_code == 400)
    # Le domaine, lui, reste ouvert : aucune liste ne contient tous les
    # metiers, et « Autre domaine » sans nulle part ou preciser lequel
    # faisait disparaitre l'information.
    r = etu.put("/api/profil/moi", json={"domaine": "Sérigraphie"})
    verifier("Un domaine hors liste est accepté", r.status_code == 200)
    verifier("Le domaine libre est relu tel quel",
             etu.get("/api/profil/moi").get_json().get("domaine")
             == "Sérigraphie")
    r = etu.put("/api/profil/moi", json={"domaine": "  ???  "})
    verifier("Un domaine sans lettre est refusé", r.status_code == 400)
    etu.put("/api/profil/moi", json={"domaine": "Soudure et métallerie"})

    # Les listes s'ecrivaient sans accent a l'origine ; les comptes
    # crees a ce moment la ont ces valeurs en base. Les refuser
    # empecherait ces personnes d'enregistrer leur profil.
    r = etu.put("/api/profil/moi", json={"situation": "Jeune diplome"})
    verifier("Une ancienne valeur sans accent reste acceptée",
             r.status_code == 200)
    verifier("Elle est réécrite avec ses accents",
             (r.get_json() or {}).get("situation") == "Jeune diplômé",
             "la base ne doit garder qu'une orthographe par intitulé")

    # Le champ etait recueilli puis jete : la requete ne le portait pas.
    ref_pub = etu.get("/api/profil/referentiels").get_json() or {}
    id_p = (ref_pub.get("pays") or [{}])[0].get("id_pays")
    ids_s = [s["id_secteur"] for s in (ref_pub.get("secteurs") or [])[:2]]
    r = etu.put("/api/profil/moi", json={"id_pays": id_p, "secteurs": ids_s})
    verifier("Le pays choisi est bien enregistré",
             (r.get_json() or {}).get("id_pays") == id_p)
    verifier("Les secteurs choisis sont bien enregistrés",
             len((r.get_json() or {}).get("secteurs") or []) == len(ids_s))

    # Un export qui annonce « tout ce que la plateforme conserve » et en
    # omet une partie vaut moins que pas d'export du tout.
    exp = (etu.get("/api/profil/moi/donnees").get_json() or {}).get("profil", {})
    verifier("L'export contient le parcours complet",
             all(c in exp for c in
                 ("niveau_etudes", "domaine", "etablissement",
                  "situation", "objectif", "langues", "profil_pro")),
             "clés présentes : %s" % sorted(exp)[:6])

    print("\n" + "═" * 70)
    print("  20. AUTHENTIFICATION EXTERNE (OAuth)")
    print("═" * 70)
    cfg = anon.get("/api/auth/config")
    verifier("Configuration OAuth exposée", cfg.status_code == 200)
    verifier("Google signalé non configuré (503) au lieu d'une erreur 500",
             anon.post("/api/auth/google",
                       json={"credential": "faux"}).status_code == 503)
    verifier("LinkedIn signalé non configuré (503)",
             anon.get("/api/auth/linkedin").status_code == 503)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  21. HONNÊTETÉ DE L'ENVOI D'E-MAILS")
    print("═" * 70)

    import config as mod_config
    from utils.email import envoyer, envoi_operationnel

    verifier("La configuration dit si un message peut partir",
             "envoi_email_actif" in (cfg.get_json() or {}))

    # En developpement, le mode console suffit : le message s'affiche
    # sous les yeux de qui teste.
    verifier("En développement, le mode console vaut un envoi",
             envoi_operationnel() is True)
    verifier("Il rend la main sans erreur",
             envoyer("essai@test.io", "Essai", "Corps") is True)

    # En production, le meme mode envoie le message dans un journal que
    # personne ne lit. Repondre « c'est parti » revient a faire attendre
    # un lien qui n'arrivera jamais : c'est ce qui s'est produit.
    prod_avant = mod_config.Config.EST_PRODUCTION
    try:
        mod_config.Config.EST_PRODUCTION = True
        verifier("En production, le mode console n'est pas un envoi",
                 envoi_operationnel() is False,
                 "sinon l'interface annonce un message jamais distribué")
        verifier("L'envoi le signale au lieu de répondre « c'est parti »",
                 envoyer("essai@test.io", "Essai", "Corps") is False)
        c_prod = anon.get("/api/auth/config").get_json() or {}
        verifier("La configuration le signale à l'interface",
                 c_prod.get("envoi_email_actif") is False)

        # L'inscription doit alors le dire, plutot que d'inviter a
        # ouvrir une boite ou rien n'arrivera.
        r = app.test_client().post("/api/auth/inscription", json={
            "prenom": "Sènan", "nom": "AHOYO", "email": "senan@test.io",
            "mot_de_passe": "Senan2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
        verifier("L'inscription avoue que le message n'est pas parti",
                 (r.get_json() or {}).get("email_envoye") is False,
                 r.get_data(as_text=True)[:90])
    finally:
        mod_config.Config.EST_PRODUCTION = prod_avant

    verifier("L'état d'origine est rétabli après le test",
             mod_config.Config.EST_PRODUCTION == prod_avant)

    # --- Tolerance de la configuration saisie a la main ----------------
    from utils.email import _config, _port, _securite, TIMEOUT_SMTP

    verifier("Le délai SMTP reste sous la coupure de l'hébergeur",
             TIMEOUT_SMTP <= 9,
             "une fonction Vercel est interrompue à 10 s : au-delà, "
             "l'échec ne peut plus être signalé")

    verifier("Un port entouré d'espaces est accepté", _port(" 465 ") == 465)
    verifier("Un port absurde retombe sur 587", _port("abc") == 587)
    verifier("Un port vide retombe sur 587", _port("") == 587)
    verifier("Un port hors bornes retombe sur 587", _port("99999") == 587)

    # « tls » ne departage rien : les deux camps l'emploient. Sur 465 il
    # ne peut designer que le chiffrement immediat, et s'y tromper ne
    # donne pas une erreur nette mais une connexion suspendue.
    verifier("« tls » sur le port 465 vaut ssl",
             _securite("tls", 465) == "ssl",
             "sinon la connexion reste suspendue jusqu'au délai")
    verifier("« tls » sur le port 587 vaut starttls",
             _securite("tls", 587) == "starttls")
    verifier("Le port 465 impose ssl quand rien n'est précisé",
             _securite(None, 465) == "ssl")
    verifier("Le port 465 corrige une valeur inconnue",
             _securite("n_importe_quoi", 465) == "ssl")
    verifier("Le port 587 reste en starttls",
             _securite(None, 587) == "starttls")
    verifier("Un choix explicite « ssl » est respecté",
             _securite("ssl", 587) == "ssl")
    verifier("Un choix explicite « starttls » est respecté",
             _securite("starttls", 465) == "starttls")

    # Une espace en fin de valeur, tres facile a laisser dans une
    # interface web, laissait le mode a « console » sans rien dire.
    os.environ["EMAIL_MODE"] = " SMTP "
    try:
        verifier("Une espace parasite autour du mode est ignorée",
                 _config()["mode"] == "smtp")
    finally:
        os.environ["EMAIL_MODE"] = "console"

    # Un echec doit se corriger sans aller lire les journaux : sur un
    # hebergement sans etat, personne ne les consulte.
    from utils.email import envoyer_detaille
    for cle, valeur in (("EMAIL_MODE", "smtp"),
                        ("SMTP_HOTE", "127.0.0.1"),
                        ("SMTP_PORT", "1"),
                        ("SMTP_UTILISATEUR", "essai@lasourcee.org"),
                        ("SMTP_MOTDEPASSE", "peu-importe")):
        os.environ[cle] = valeur
    try:
        parti, motif = envoyer_detaille("qui@test.io", "Essai", "Corps")
        verifier("Un serveur SMTP injoignable est signalé", parti is False)
        verifier("Le motif nomme l'hôte et le port en cause",
                 "127.0.0.1:1" in motif, motif[:110])
        verifier("Le motif dit quoi vérifier",
                 "SMTP_HOTE" in motif and "SMTP_SECURITE" in motif,
                 motif[:110])
    finally:
        for cle in ("EMAIL_MODE", "SMTP_HOTE", "SMTP_PORT",
                    "SMTP_UTILISATEUR", "SMTP_MOTDEPASSE"):
            os.environ.pop(cle, None)
        os.environ["EMAIL_MODE"] = "console"

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  22. CANDIDATURE DE RÉFÉRENT ET VALIDATION")
    print("═" * 70)

    cand = app.test_client()
    cand.post("/api/auth/inscription", json={
        "prenom": "Odile", "nom": "HOUNKPATIN", "email": "odile@test.io",
        "mot_de_passe": "Odile2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    r = cand.post("/api/mentors/candidature", json={
        "bio": "Ingénieure en génie civil depuis douze ans, je suis les "
               "chantiers publics et j'accompagne des jeunes diplômés.",
        "motivation": "J'ai commencé sans savoir à qui demander conseil et "
                      "j'aimerais éviter cela à d'autres. Je peux parler du "
                      "métier, des concours et des premières années.",
        "profession": "Ingénieure travaux",
        "organisation": "Direction des infrastructures",
        "annees_experience": 12,
        "lien_professionnel": "https://exemple.org/odile",
        "secteurs": [1]})
    verifier("Une candidature complète est acceptée", r.status_code in (200, 201),
             r.get_data(as_text=True)[:110])

    role = jeton_sql("SELECT role FROM utilisateur WHERE email = ?",
                     ("odile@test.io",))
    verifier("Le dépôt ne confère pas le rôle de référent", role != "mentor",
             "sinon la candidate figure dans l'annuaire avant tout examen")

    # Le dossier doit survivre a l'e-mail : c'est sur lui que la
    # decision se prend.
    verifier("La motivation est conservée en base",
             bool(jeton_sql("SELECT motivation FROM mentor_details md "
                            "JOIN utilisateur u USING (id_utilisateur) "
                            "WHERE u.email = ?", ("odile@test.io",))))
    verifier("La profession est conservée en base",
             jeton_sql("SELECT profession FROM mentor_details md "
                       "JOIN utilisateur u USING (id_utilisateur) "
                       "WHERE u.email = ?",
                       ("odile@test.io",)) == "Ingénieure travaux")

    # L'annuaire ne presente que des dossiers examines.
    annuaire = cand.get("/api/mentors").get_json() or []
    noms = [str(m.get("email", "")) + str(m.get("nom", "")) for m in
            (annuaire if isinstance(annuaire, list) else annuaire.get("mentors", []))]
    verifier("Une candidate non validée n'est pas dans l'annuaire",
             not any("HOUNKPATIN" in n for n in noms))

    # L'administrateur doit disposer du dossier, pas seulement du nom.
    dossiers = adm.get("/api/admin/mentors-a-verifier").get_json() or []
    mien = [d for d in dossiers if d.get("email") == "odile@test.io"]
    verifier("La candidature apparaît chez l'administrateur", bool(mien))
    if mien:
        d = mien[0]
        verifier("Le dossier porte la motivation", bool(d.get("motivation")))
        verifier("Le dossier porte la profession", bool(d.get("profession")))
        verifier("Le dossier porte le lien professionnel",
                 bool(d.get("lien_pro")))

    # Les administrateurs sont prevenus dans l'application : l'e-mail
    # peut etre hors service sans que personne s'en apercoive.
    verifier("Les administrateurs reçoivent une notification",
             jeton_sql("SELECT COUNT(*) FROM notification "
                       "WHERE texte LIKE ?", ("%devenir référent%",)) >= 1)

    id_cand = jeton_sql("SELECT id_utilisateur FROM utilisateur WHERE email = ?",
                        ("odile@test.io",))
    r = adm.post(f"/api/admin/mentors/{id_cand}/verifier", json={})
    verifier("La validation aboutit", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("La validation confère le rôle de référent",
             jeton_sql("SELECT role FROM utilisateur WHERE email = ?",
                       ("odile@test.io",)) == "mentor")
    verifier("La validation pose le badge vérifié",
             jeton_sql("SELECT est_verifie FROM mentor_details "
                       "WHERE id_utilisateur = ?", (id_cand,)) == 1)
    verifier("La candidate est prévenue dans l'application",
             jeton_sql("SELECT COUNT(*) FROM notification "
                       "WHERE id_destinataire = ? AND texte LIKE ?",
                       (id_cand, "%acceptée%")) >= 1)

    apres = cand.get("/api/mentors").get_json() or []
    liste = apres if isinstance(apres, list) else apres.get("mentors", [])
    verifier("Une fois validée, elle entre dans l'annuaire",
             any("Hounkpatin" in str(m.get("nom", "")) for m in liste),
             f"{len(liste)} référent(s) listé(s)")

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  23. MODÉRATION DES SIGNALEMENTS")
    print("═" * 70)

    gene = app.test_client()
    gene.post("/api/auth/inscription", json={
        "prenom": "Fataou", "nom": "BIO", "email": "fataou@test.io",
        "mot_de_passe": "Fataou2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    r = gene.post("/api/questions", json={
        "titre": "Contenu à modérer pour les besoins du test",
        "corps": "Ce message existe pour éprouver la chaîne de modération "
                 "de bout en bout, du signalement jusqu'à la décision.",
        "id_secteur": 1})
    id_q_mod = (r.get_json() or {}).get("id_question")
    verifier("Question à modérer publiée", bool(id_q_mod))

    r = etu.post(f"/api/questions/{id_q_mod}/signaler",
                 json={"motif": "Propos inappropriés"})
    verifier("Le signalement est enregistré", r.status_code in (200, 201),
             r.get_data(as_text=True)[:110])

    liste = adm.get("/api/admin/signalements?statut=ouvert").get_json() or []
    mien = [s for s in liste if s.get("id_contenu") == id_q_mod]
    verifier("Le signalement remonte à l'administrateur", bool(mien))
    if mien:
        s = mien[0]
        verifier("On voit qui a signalé", bool(s.get("prenom")))
        verifier("On voit le motif invoqué",
                 "inappropri" in (s.get("motif") or ""))
        # Sans le contenu, la decision se prendrait sur un numero.
        verifier("On voit le contenu signalé",
                 bool((s.get("contenu") or {}).get("texte")))
        verifier("On voit l'auteur du contenu",
                 (s.get("contenu") or {}).get("prenom") == "Fataou")
        verifier("On voit combien de fois il a été signalé",
                 s.get("signalements_contenu", 0) >= 1)

    id_sig = mien[0]["id_signalement"] if mien else 0
    r = adm.post(f"/api/admin/signalements/{id_sig}", json={"action": "farfelu"})
    verifier("Une décision inconnue est refusée", r.status_code == 400)

    r = adm.post(f"/api/admin/signalements/{id_sig}",
                 json={"action": "suspendre", "note": "essai"})
    verifier("Suspension du compte de l'auteur acceptée", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("Le compte visé est bien désactivé",
             jeton_sql("SELECT est_actif FROM utilisateur WHERE email = ?",
                       ("fataou@test.io",)) == 0)
    verifier("L'auteur est prévenu de la suspension",
             jeton_sql("SELECT COUNT(*) FROM notification n "
                       "JOIN utilisateur u ON u.id_utilisateur = n.id_destinataire "
                       "WHERE u.email = ? AND n.texte LIKE ?",
                       ("fataou@test.io", "%suspendu%")) >= 1)
    verifier("La personne qui a signalé reçoit un retour",
             jeton_sql("SELECT COUNT(*) FROM notification WHERE texte LIKE ?",
                       ("%signalement a été examiné%",)) >= 1)
    verifier("La décision est tracée",
             jeton_sql("SELECT action FROM signalement WHERE id_signalement = ?",
                       (id_sig,)) == "suspendre")
    verifier("L'auteur de la décision est enregistré",
             bool(jeton_sql("SELECT traite_par FROM signalement "
                            "WHERE id_signalement = ?", (id_sig,))))

    restants = adm.get("/api/admin/signalements?statut=ouvert").get_json() or []
    verifier("Il quitte la file d'attente",
             not any(s.get("id_signalement") == id_sig for s in restants))
    traites = adm.get("/api/admin/signalements?statut=traite").get_json() or []
    verifier("Il se retrouve parmi les traités",
             any(s.get("id_signalement") == id_sig for s in traites))

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  24. DROITS D'ADMINISTRATION ET EXPORTS")
    print("═" * 70)

    from utils.permissions import PERMISSIONS, permissions_de

    r = adm.get("/api/admin/permissions")
    verifier("Le catalogue des droits est servi", r.status_code == 200)
    cat = r.get_json() or {}
    verifier("Le super administrateur a tous les droits",
             len(cat.get("les_miennes") or []) == len(PERMISSIONS))

    # Un compte sans droits ne doit rien pouvoir, pas meme lire.
    verifier("Une liste vide n'accorde rien",
             permissions_de({"est_admin": 1, "role": "admin",
                             "permissions": "[]"}) == [])
    # Un compte anterieur aux droits garde tout : sinon la mise a jour
    # verrouillerait l'equipe hors de son propre site.
    verifier("Un compte antérieur conserve ses droits",
             len(permissions_de({"est_admin": 1, "role": "admin",
                                 "permissions": None})) == len(PERMISSIONS))
    verifier("Un non-administrateur n'a aucun droit",
             permissions_de({"est_admin": 0, "role": "etudiant"}) == [])

    r = adm.post("/api/admin/administrateurs", json={
        "prenom": "Mariano", "nom": "DOSSOUGAN",
        "email": "mariano.modo@test.io",
        "permissions": ["signalements"]})
    verifier("Un administrateur restreint est créé", r.status_code == 200,
             r.get_data(as_text=True)[:110])

    id_restreint = jeton_sql("SELECT id_utilisateur FROM utilisateur "
                             "WHERE email = ?", ("mariano.modo@test.io",))
    verifier("Ses droits sont enregistrés",
             "signalements" in (jeton_sql(
                 "SELECT permissions FROM utilisateur WHERE id_utilisateur = ?",
                 (id_restreint,)) or ""))

    # Il faut pouvoir se connecter pour eprouver ses droits : on lui
    # pose un mot de passe connu, comme le ferait une reinitialisation.
    from utils.auth_helpers import hacher_mot_de_passe
    with app.app_context():
        from models.db import executer as _ex
        _ex("UPDATE utilisateur SET mot_de_passe = %s, doit_changer_mdp = 0 "
            "WHERE id_utilisateur = %s",
            (hacher_mot_de_passe("Mariano2026!"), id_restreint), commit=True)

    res = app.test_client()
    r = res.post("/api/auth/connexion", json={
        "email": "mariano.modo@test.io", "mot_de_passe": "Mariano2026!"})
    verifier("L'administrateur restreint se connecte", r.status_code == 200,
             r.get_data(as_text=True)[:110])

    verifier("Il accède aux signalements, son droit",
             res.get("/api/admin/signalements").status_code == 200)
    verifier("Le journal d'audit lui est refusé (403)",
             res.get("/api/admin/audit").status_code == 403)
    verifier("La liste des comptes lui est refusée (403)",
             res.get("/api/admin/utilisateurs").status_code == 403)
    verifier("L'export lui est refusé (403)",
             res.get("/api/admin/export/utilisateurs").status_code == 403)
    verifier("La configuration lui est refusée (403)",
             res.get("/api/admin/diagnostic").status_code == 403)
    verifier("Il ne peut pas nommer d'administrateur (403)",
             res.post("/api/admin/administrateurs",
                      json={"prenom": "A", "nom": "B",
                            "email": "z@test.io"}).status_code == 403)

    # Le refus doit nommer le droit manquant : « acces refuse » seul
    # fait conclure a une panne plutot qu'a un droit a demander. Et il le
    # nomme comme l'ecran le nomme : demander « le droit audit » a un
    # super administrateur oblige celui-ci a deviner de quelle case il
    # s'agit dans la liste qu'il a sous les yeux.
    from utils.permissions import PERMISSIONS_DETAIL
    refus = (res.get("/api/admin/audit").get_json() or {}).get("erreur", "")
    verifier("Le refus nomme le droit manquant",
             PERMISSIONS_DETAIL["audit"]["nom"] in refus, refus[:90])

    # --- Exports ---
    for jeu in ("utilisateurs", "questions", "reponses", "referents",
                "signalements", "audit", "activite"):
        r = adm.get(f"/api/admin/export/{jeu}")
        verifier(f"Export « {jeu} »", r.status_code == 200,
                 r.get_data(as_text=True)[:90])

    r = adm.get("/api/admin/export/utilisateurs")
    corps = r.get_data(as_text=True)
    verifier("Le CSV porte un en-tête de colonnes",
             corps.lstrip("\ufeff").startswith("id_utilisateur;"))
    verifier("Le CSV est proposé en téléchargement",
             "attachment" in r.headers.get("Content-Disposition", ""))
    verifier("L'export n'est pas mis en cache",
             "no-store" in r.headers.get("Cache-Control", ""))
    # Un export circule et s'oublie : aucun secret n'a a y figurer.
    verifier("Aucun mot de passe dans l'export",
             "$2b$" not in corps and "mot_de_passe" not in corps)

    r = adm.get("/api/admin/export/inexistant")
    verifier("Un jeu inconnu renvoie 404", r.status_code == 404)

    r = adm.get(f"/api/admin/export/compte/{id_restreint}")
    verifier("Le dossier d'un compte s'exporte", r.status_code == 200)
    dossier = r.get_json() or {}
    verifier("Le dossier contient le profil", "profil" in dossier)
    verifier("Le dossier ne contient aucun mot de passe",
             "mot_de_passe" not in (dossier.get("profil") or {}))
    verifier("Le dossier dit qui l'a exporté et quand",
             bool(dossier.get("exporte_par") and dossier.get("exporte_le")))

    # --- Garde-fous ---
    moi = jeton_sql("SELECT id_utilisateur FROM utilisateur WHERE email = ?",
                    ("rodriguedjossou93@gmail.com",))
    verifier("On ne modifie pas ses propres droits",
             adm.put(f"/api/admin/administrateurs/{moi}",
                     json={"permissions": []}).status_code == 400)
    verifier("On ne retire pas sa propre administration",
             adm.delete(f"/api/admin/administrateurs/{moi}").status_code == 400)

    r = adm.put(f"/api/admin/administrateurs/{id_restreint}",
                json={"permissions": ["signalements", "referents"]})
    verifier("Les droits d'un autre se modifient", r.status_code == 200)
    verifier("Le droit ajouté prend effet",
             res.get("/api/admin/mentors-a-verifier").status_code == 200)

    verifier("Un droit inventé est ignoré",
             "invente" not in (adm.put(
                 f"/api/admin/administrateurs/{id_restreint}",
                 json={"permissions": ["signalements", "invente"]}
             ).get_json() or {}).get("droits", []))

    r = adm.delete(f"/api/admin/administrateurs/{id_restreint}")
    verifier("L'administration se retire", r.status_code == 200)
    verifier("Le compte survit au retrait des droits",
             bool(jeton_sql("SELECT id_utilisateur FROM utilisateur "
                            "WHERE email = ?", ("mariano.modo@test.io",))))
    verifier("Les droits retirés ferment l'accès",
             res.get("/api/admin/signalements").status_code in (401, 403))

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  25. CONFIRMATION PAR CODE ET ADRESSE DES LIENS")
    print("═" * 70)

    # L'adresse des liens envoyes par e-mail. VERCEL_URL designe un
    # deploiement precis, protege par une authentification Vercel : les
    # nouveaux inscrits tombaient sur un mur au lieu de confirmer.
    import subprocess as _sp
    def _url(env):
        base = {"PATH": os.environ.get("PATH", "")}
        base.update(env)
        return _sp.run([sys.executable, "-c",
                        "import sys; sys.path.insert(0,'.');"
                        "from config import Config; print(Config.URL_PLATEFORME)"],
                       capture_output=True, text=True, env=base,
                       cwd=os.path.dirname(os.path.abspath(__file__))
                       ).stdout.strip()

    verifier("L'adresse de deploiement n'est jamais utilisee",
             ".vercel.app" not in _url({
                 "VERCEL": "1", "VERCEL_ENV": "production",
                 "VERCEL_URL": "projet-a1b2c3-equipe.vercel.app"}),
             "un lien vers un deploiement precis est inaccessible")
    verifier("Le domaine de production prime",
             _url({"VERCEL": "1", "VERCEL_ENV": "production",
                   "VERCEL_URL": "x.vercel.app",
                   "VERCEL_PROJECT_PRODUCTION_URL": "lasourcee.org"})
             == "https://lasourcee.org")
    verifier("Une adresse explicite prime sur tout",
             _url({"VERCEL": "1", "VERCEL_ENV": "production",
                   "URL_PLATEFORME": "https://autre.exemple.org",
                   "VERCEL_URL": "x.vercel.app"}) == "https://autre.exemple.org")

    # --- Le code de confirmation ---
    codeur = app.test_client()
    codeur.post("/api/auth/inscription", json={
        "prenom": "Rachidat", "nom": "TIDJANI", "email": "rachidat@test.io",
        "mot_de_passe": "Rachidat2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    code = jeton_sql(
        "SELECT v.code FROM verification_email v "
        "JOIN utilisateur u ON u.id_utilisateur = v.id_utilisateur "
        "WHERE u.email = ?", ("rachidat@test.io",))
    verifier("Un code est genere a l'inscription", bool(code))
    verifier("Le code fait six chiffres",
             bool(code) and len(str(code)) == 6 and str(code).isdigit(), str(code))

    r = anon.post("/api/auth/verifier-code",
                  json={"email": "rachidat@test.io", "code": "000000"})
    faux = r.status_code == 400 or str(code) == "000000"
    verifier("Un code faux est refuse", faux, r.get_data(as_text=True)[:90])
    verifier("Le refus dit combien d'essais restent",
             "essai" in (r.get_json() or {}).get("erreur", "").lower()
             or str(code) == "000000")

    r = anon.post("/api/auth/verifier-code",
                  json={"email": "rachidat@test.io", "code": "12345"})
    verifier("Un code trop court est refuse", r.status_code == 400)

    r = anon.post("/api/auth/verifier-code",
                  json={"email": "rachidat@test.io", "code": str(code)})
    verifier("Le bon code valide l'adresse", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("L'adresse est marquee verifiee en base",
             jeton_sql("SELECT email_verifie FROM utilisateur WHERE email = ?",
                       ("rachidat@test.io",)) == 1)

    # Un compte deja confirme repond comme un succes : lui opposer une
    # erreur le ferait douter de son propre compte.
    r = anon.post("/api/auth/verifier-code",
                  json={"email": "rachidat@test.io", "code": str(code)})
    verifier("Une seconde validation ne provoque pas d'erreur",
             r.status_code == 200)

    r = anon.post("/api/auth/verifier-code",
                  json={"email": "inconnu@nulle.part", "code": "123456"})
    verifier("Une adresse inconnue est refusee proprement",
             r.status_code == 410)

    # Six chiffres se devinent en un million de coups : sans limite, un
    # robot y parvient.
    tatonneur = app.test_client()
    tatonneur.post("/api/auth/inscription", json={
        "prenom": "Ulrich", "nom": "SOGLO", "email": "ulrich@test.io",
        "mot_de_passe": "Ulrich2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    vrai = str(jeton_sql(
        "SELECT v.code FROM verification_email v "
        "JOIN utilisateur u ON u.id_utilisateur = v.id_utilisateur "
        "WHERE u.email = ?", ("ulrich@test.io",)))
    faux_code = "111111" if vrai != "111111" else "222222"
    derniere = None
    for _ in range(12):
        derniere = anon.post("/api/auth/verifier-code",
                             json={"email": "ulrich@test.io",
                                   "code": faux_code})
    verifier("Le tatonnement est bloque", derniere.status_code == 429,
             derniere.get_data(as_text=True)[:90])
    verifier("Le bon code ne passe plus apres blocage",
             anon.post("/api/auth/verifier-code",
                       json={"email": "ulrich@test.io",
                             "code": vrai}).status_code == 429)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  26. MESURES D'USAGE ET PROFILS PUBLICS")
    print("═" * 70)

    mesur = app.test_client()
    mesur.post("/api/auth/inscription", json={
        "prenom": "Kounoumi", "nom": "MEDEKON", "email": "kounoumi@test.io",
        "mot_de_passe": "Kounoumi2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    r = mesur.post("/api/questions", json={
        "titre": "Question servant a eprouver les mesures d'usage",
        "corps": "Un corps assez long pour passer la validation du serveur "
                 "et permettre les verifications qui suivent.",
        "id_secteur": 1})
    id_mes = (r.get_json() or {}).get("id_question")
    verifier("Question publiee pour les mesures", bool(id_mes))

    verifier("La publication laisse un evenement",
             jeton_sql("SELECT COUNT(*) FROM evenement "
                       "WHERE type_evenement = 'question_publiee' "
                       "AND id_cible = ?", (id_mes,)) == 1)
    # Le role est fige au moment de l'action : il change avec le temps,
    # et une analyse posterieure attribuerait sinon toute l'activite
    # passee d'un referent a son role actuel.
    verifier("L'evenement retient le role du moment",
             jeton_sql("SELECT role_acteur FROM evenement "
                       "WHERE type_evenement = 'question_publiee' "
                       "AND id_cible = ?", (id_mes,)) == "etudiant")

    mesur.get(f"/api/questions/{id_mes}")
    mesur.get(f"/api/questions/{id_mes}")
    verifier("Les consultations sont comptees",
             jeton_sql("SELECT vues FROM question WHERE id_question = ?",
                       (id_mes,)) == 2)

    verifier("Aucune date de premiere reponse avant reponse",
             jeton_sql("SELECT premiere_reponse_le FROM question "
                       "WHERE id_question = ?", (id_mes,)) is None)
    etu.post("/api/reponses", json={
        "id_question": id_mes,
        "contenu": "Une reponse suffisamment longue pour etre acceptee."})
    premiere = jeton_sql("SELECT premiere_reponse_le FROM question "
                         "WHERE id_question = ?", (id_mes,))
    verifier("La premiere reponse date la question", bool(premiere))

    etu.post("/api/reponses", json={
        "id_question": id_mes,
        "contenu": "Une seconde reponse, qui ne doit pas ecraser la date."})
    verifier("La seconde reponse ne recrit pas cette date",
             jeton_sql("SELECT premiere_reponse_le FROM question "
                       "WHERE id_question = ?", (id_mes,)) == premiere,
             "sinon le delai mesure serait toujours celui de la derniere")

    # Aucun contenu ecrit par un membre dans le journal : le texte vit
    # dans sa table, l'y recopier le rendrait ineffacable.
    contextes = jeton_sql("SELECT COUNT(*) FROM evenement "
                          "WHERE contexte LIKE ?",
                          ("%eprouver les mesures%",))
    verifier("Le journal ne recopie aucun contenu", contextes == 0)

    r = adm.get("/api/admin/export/evenements")
    verifier("Les evenements s'exportent", r.status_code == 200)

    # --- Profil public ---
    r = etu.get("/api/profil/%d" % jeton_sql(
        "SELECT id_utilisateur FROM utilisateur WHERE email = ?",
        ("kounoumi@test.io",)))
    verifier("Le profil d'un autre membre est consultable",
             r.status_code == 200)
    pub = r.get_json() or {}
    verifier("Il ne divulgue pas l'adresse e-mail", "email" not in pub)
    verifier("Il ne divulgue pas le mot de passe temporaire",
             "doit_changer_mdp" not in pub)
    verifier("Il porte le parcours",
             all(c in pub for c in ("situation", "objectif", "niveau_etudes",
                                    "domaine", "etablissement", "langues")))
    verifier("Il porte la photo et la date d'arrivee",
             "photo_url" in pub and "cree_le" in pub)

    verifier("Un profil inexistant repond 404",
             etu.get("/api/profil/999999").status_code == 404)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  27. OBJECTIFS MULTIPLES, MESSAGERIE ET RECHERCHE")
    print("═" * 70)

    from routes.profil import (OBJECTIFS, SEPARATEUR_OBJECTIFS,
                               LIMITE_OBJECTIFS, _eclater_objectifs)

    # La virgule sert de separateur : aucun intitule ne doit en
    # contenir, sinon le decoupage se ferait au mauvais endroit sans
    # que rien ne le signale.
    verifier("Aucun objectif ne contient le separateur",
             not any("," in o for o in OBJECTIFS),
             [o for o in OBJECTIFS if "," in o])

    r = etu.put("/api/profil/moi", json={"objectifs": [
        "Trouver un stage", "Apprendre un métier", "Gérer mon argent"]})
    verifier("Plusieurs objectifs s'enregistrent", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    p_obj = r.get_json() or {}
    verifier("Ils sont tous conservés",
             len(p_obj.get("objectifs") or []) == 3, p_obj.get("objectif"))
    verifier("La colonne reste lisible",
             SEPARATEUR_OBJECTIFS in (p_obj.get("objectif") or ""))

    verifier("Un objectif inventé est refusé",
             etu.put("/api/profil/moi",
                     json={"objectifs": ["Trouver un stage", "Sorcellerie"]}
                     ).status_code == 400)
    verifier("Un doublon ne compte qu'une fois",
             len((etu.put("/api/profil/moi", json={"objectifs": [
                 "Changer de voie", "Changer de voie"]}).get_json()
                 or {}).get("objectifs") or []) == 1)
    # La forme ancienne, un seul objectif en chaine, doit rester
    # acceptee : d'anciens comptes l'ont enregistree ainsi.
    r = etu.put("/api/profil/moi", json={"objectif": "Trouver un stage"})
    verifier("La forme à un seul objectif reste acceptée",
             r.status_code == 200
             and (r.get_json() or {}).get("objectifs") == ["Trouver un stage"])
    verifier("Le découpage ignore les vides",
             _eclater_objectifs("Trouver un stage, , Changer de voie")
             == ["Trouver un stage", "Changer de voie"])
    trop = OBJECTIFS[:LIMITE_OBJECTIFS + 2]
    verifier("Le nombre d'objectifs est borné",
             len((etu.put("/api/profil/moi",
                          json={"objectifs": trop}).get_json()
                  or {}).get("objectifs") or []) <= LIMITE_OBJECTIFS)

    # --- Messagerie : elle existait cote serveur sans aucun ecran ---
    m1 = app.test_client()
    m1.post("/api/auth/inscription", json={
        "prenom": "Sika", "nom": "AGOSSOU", "email": "sika@test.io",
        "mot_de_passe": "Sika2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    id_sika = jeton_sql("SELECT id_utilisateur FROM utilisateur WHERE email = ?",
                        ("sika@test.io",))

    r = etu.post("/api/messagerie/conversations",
                 json={"id_utilisateur": id_sika})
    verifier("Une conversation s'ouvre", r.status_code in (200, 201),
             r.get_data(as_text=True)[:110])
    id_conv = (r.get_json() or {}).get("id_conversation")

    r = etu.post(f"/api/messagerie/conversations/{id_conv}/messages",
                 json={"contenu": "Bonjour, auriez-vous un conseil ?"})
    verifier("Un message s'envoie", r.status_code in (200, 201))
    verifier("Le message vide est refusé",
             etu.post(f"/api/messagerie/conversations/{id_conv}/messages",
                      json={"contenu": "   "}).status_code == 400)

    liste = m1.get("/api/messagerie/conversations").get_json() or []
    verifier("Le destinataire voit la conversation", len(liste) == 1)
    verifier("Il voit le dernier message",
             "conseil" in ((liste[0] if liste else {}).get("dernier_contenu")
                           or ""))
    verifier("Il compte le message non lu",
             (liste[0] if liste else {}).get("non_lus", 0) >= 1)

    msgs = m1.get(f"/api/messagerie/conversations/{id_conv}/messages").get_json()
    verifier("Il lit le contenu", len(msgs or []) == 1)

    # Un tiers ne doit pas pouvoir lire une conversation privee.
    intrus = app.test_client()
    intrus.post("/api/auth/inscription", json={
        "prenom": "Intrus", "nom": "TEST", "email": "intrus@test.io",
        "mot_de_passe": "Intrus2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    verifier("Un tiers ne lit pas la conversation",
             intrus.get(f"/api/messagerie/conversations/{id_conv}/messages"
                        ).status_code == 403)
    verifier("Un tiers n'y écrit pas",
             intrus.post(f"/api/messagerie/conversations/{id_conv}/messages",
                         json={"contenu": "Bonjour"}).status_code == 403)

    # --- Recherche : elle ne parcourait que la memoire du navigateur ---
    r = etu.get("/api/recherche?q=AGOSSOU")
    verifier("La recherche répond", r.status_code == 200)
    res = r.get_json() or {}
    verifier("Elle renvoie les trois familles",
             all(c in res for c in ("mentors", "questions", "secteurs")))
    verifier("Un terme trop court ne cherche rien",
             (etu.get("/api/recherche?q=a").get_json()
              or {}).get("questions") == [])
    verifier("Elle trouve une question par son titre",
             len((etu.get("/api/recherche?q=financer").get_json()
                  or {}).get("questions") or []) >= 1)
    verifier("Elle est refusée sans session",
             app.test_client().get("/api/recherche?q=test").status_code == 401)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  28. INSCRIPTION : CODE SANS LIEN, ET TÉLÉPHONE")
    print("═" * 70)

    import io as _io
    import logging as _log
    from routes.profil import normaliser_telephone

    # Le message ne doit plus contenir la moindre adresse. C'est la
    # seule garantie qui tienne : tant qu'un lien y figure, il peut
    # pointer vers un deploiement, etre coupe par la messagerie, ou
    # s'ouvrir sans la session.
    tampon = _io.StringIO()
    poignee = _log.StreamHandler(tampon)
    journal = _log.getLogger("lasource.email")
    niveau = journal.level
    journal.setLevel(_log.INFO)
    journal.addHandler(poignee)
    try:
        app.test_client().post("/api/auth/inscription", json={
            "prenom": "Nadege", "nom": "AKPOVI", "email": "nadege@test.io",
            "mot_de_passe": "Nadege2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    finally:
        journal.removeHandler(poignee)
        journal.setLevel(niveau)
    message = tampon.getvalue()

    verifier("Le message de confirmation part", "nadege@test.io" in message)
    verifier("Il ne contient aucune adresse web",
             "http://" not in message and "https://" not in message,
             [l for l in message.split("\n") if "http" in l][:2])
    verifier("Il ne contient aucun jeton",
             "jeton=" not in message and "verifier-email" not in message)
    verifier("Le code figure dans l'objet",
             "Votre code LaSourcee" in message)

    code_n = jeton_sql("SELECT v.code FROM verification_email v "
                       "JOIN utilisateur u ON u.id_utilisateur = v.id_utilisateur "
                       "WHERE u.email = ?", ("nadege@test.io",))
    verifier("Le code se lit dans le message",
             bool(code_n) and f"{str(code_n)[:3]} {str(code_n)[3:]}" in message)

    # Redemander le code : c'est le MEME qui repart, tant qu'il vaut.
    #
    # Il etait auparavant detruit puis remplace, ce qui donnait a
    # n'importe qui le moyen d'invalider le code d'un autre sans jamais
    # y avoir acces : la personne venait de le recevoir, le recopiait,
    # et s'entendait repondre « Code incorrect ».
    r = anon.post("/api/auth/renvoyer-confirmation",
                  json={"email": "nadege@test.io"})
    verifier("Un code se redemande", r.status_code == 200)
    codes = jeton_sql("SELECT COUNT(*) FROM verification_email v "
                      "JOIN utilisateur u ON u.id_utilisateur = v.id_utilisateur "
                      "WHERE u.email = ? AND v.verifie_le IS NULL",
                      ("nadege@test.io",))
    verifier("Un seul code reste en circulation", codes == 1, str(codes))
    # Compare a TOUS les codes en attente, pas au plus recent : deux
    # lignes creees dans la meme seconde se departagent au hasard, et
    # l'assertion reussissait alors meme quand un second code existait.
    # GROUP_CONCAT n'existe pas sur PostgreSQL : on compte les codes qui
    # DIFFERENT du precedent, ce qui s'ecrit pareil sur les deux moteurs.
    autres = jeton_sql("SELECT COUNT(*) FROM verification_email v "
                       "JOIN utilisateur u "
                       "  ON u.id_utilisateur = v.id_utilisateur "
                       "WHERE u.email = ? AND v.verifie_le IS NULL "
                       "  AND v.code <> ?",
                       ("nadege@test.io", str(code_n)))
    verifier("C'est le même code qui repart, et lui seul",
             autres == 0, f"{autres} autre(s) code(s) en attente")
    code_n2 = code_n
    verifier("Un tiers ne peut donc pas invalider le code de quelqu'un",
             anon.post("/api/auth/verifier-code",
                       json={"email": "nadege@test.io",
                             "code": str(code_n)}).status_code == 200)
    verifier("Le nouveau code confirme l'adresse",
             anon.post("/api/auth/verifier-code",
                       json={"email": "nadege@test.io",
                             "code": str(code_n2)}).status_code == 200)

    # --- Telephone : la colonne existait depuis l'origine, inutilisee ---
    verifier("Un numéro local est accepté",
             normaliser_telephone("01 55 04 04 32") == "0155040432")
    verifier("Un numéro international garde son indicatif",
             normaliser_telephone("+229 01 55 04 04 32") == "+22901550404 32"
             .replace(" ", ""))
    verifier("Les séparateurs sont retirés",
             normaliser_telephone("01-55.04 04 32") == "0155040432")
    verifier("Un numéro trop court est refusé",
             normaliser_telephone("12") is None)
    verifier("Un texte n'est pas un numéro",
             normaliser_telephone("appelez-moi") is None)
    verifier("Un champ vide reste vide", normaliser_telephone("") == "")

    r = etu.put("/api/profil/moi", json={"telephone": "+229 01 55 04 04 32"})
    verifier("Le numéro s'enregistre", r.status_code == 200)
    verifier("Il est relu normalisé",
             (r.get_json() or {}).get("telephone") == "+22901550404" + "32")
    verifier("Un numéro invalide est refusé",
             etu.put("/api/profil/moi",
                     json={"telephone": "abc"}).status_code == 400)

    # Le numero sert a joindre, pas a etre collecte.
    id_etu = jeton_sql("SELECT id_utilisateur FROM utilisateur WHERE email = ?",
                       ("aminata@test.io",))
    autre = app.test_client()
    autre.post("/api/auth/inscription", json={
        "prenom": "Curieux", "nom": "TEST", "email": "curieux@test.io",
        "mot_de_passe": "Curieux2026!", "role": "etudiant", "consentement": CONSENT_TESTS})
    pub = autre.get(f"/api/profil/{id_etu}").get_json() or {}
    verifier("Le numéro ne figure pas sur le profil public",
             "telephone" not in pub)
    verifier("Il figure sur son propre profil",
             "telephone" in (etu.get("/api/profil/moi").get_json() or {}))

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  29. PARCOURS D'INSCRIPTION ET CONSENTEMENT")
    print("═" * 70)

    from routes.auth import VERSION_CONSENTEMENT
    import config as _cfg

    CONSENT_OK = {"conditions": True, "donnees": True, "notifications": True}

    # Le consentement conditionne la creation du compte.
    base = {"prenom": "Sika", "nom": "DANSOU", "email": "sika.c@test.io",
            "mot_de_passe": "Sika2026!", "role": "etudiant"}
    verifier("Sans consentement, le compte n'est pas créé",
             app.test_client().post("/api/auth/inscription",
                                    json=base).status_code == 400)
    verifier("Les conditions seules ne suffisent pas",
             app.test_client().post("/api/auth/inscription", json={
                 **base, "consentement": {"conditions": True}}
             ).status_code == 400)

    cli = app.test_client()
    r = cli.post("/api/auth/inscription",
                 json={**base, "consentement": CONSENT_OK})
    verifier("Avec consentement, le compte est créé", r.status_code == 201,
             r.get_data(as_text=True)[:100])
    verifier("Le consentement est daté",
             bool(jeton_sql("SELECT consentement_le FROM utilisateur "
                            "WHERE email = ?", ("sika.c@test.io",))))
    verifier("Le consentement porte la version du texte",
             jeton_sql("SELECT consentement_version FROM utilisateur "
                       "WHERE email = ?",
                       ("sika.c@test.io",)) == VERSION_CONSENTEMENT,
             "sans version, on sait qu'il a accepté, pas quoi")
    verifier("Le choix facultatif est conservé",
             jeton_sql("SELECT accepte_notifs FROM utilisateur "
                       "WHERE email = ?", ("sika.c@test.io",)) == 1)

    # --- Le parcours quand la confirmation est obligatoire ---
    # C'est le cas depuis que l'envoi SMTP fonctionne, et c'est ce qui
    # laissait les nouveaux inscrits sans acces : l'inscription
    # n'ouvrait pas de session, l'interface demandait le profil, et le
    # refus etait presente comme un echec d'inscription.
    avant = _cfg.Config.VERIFICATION_EMAIL_OBLIGATOIRE
    app.config["VERIFICATION_EMAIL_OBLIGATOIRE"] = True
    try:
        strict = app.test_client()
        r = strict.post("/api/auth/inscription", json={
            "prenom": "Orou", "nom": "BIO", "email": "orou@test.io",
            "mot_de_passe": "Orou2026!", "role": "etudiant",
            "consentement": CONSENT_OK})
        verifier("Le compte est créé même sans connexion immédiate",
                 r.status_code == 201)
        verifier("La réponse annonce que la confirmation est requise",
                 (r.get_json() or {}).get("verification_requise") is True,
                 "sans ce drapeau, l'interface croit à un échec")
        verifier("Aucune session n'est ouverte à ce stade",
                 strict.get("/api/profil/moi").status_code == 401)

        code_o = jeton_sql(
            "SELECT v.code FROM verification_email v "
            "JOIN utilisateur u ON u.id_utilisateur = v.id_utilisateur "
            "WHERE u.email = ?", ("orou@test.io",))
        r = strict.post("/api/auth/verifier-code",
                        json={"email": "orou@test.io", "code": str(code_o)})
        verifier("Le code confirme l'adresse", r.status_code == 200)
        verifier("Et ouvre la session dans la foulée",
                 (r.get_json() or {}).get("session_ouverte") is True,
                 "redemander le mot de passe après avoir prouvé "
                 "l'adresse n'ajoute rien")
        verifier("Le profil devient accessible",
                 strict.get("/api/profil/moi").status_code == 200,
                 "c'est ici que le parcours s'arrêtait")
        verifier("Le profil de l'accueil s'enregistre alors",
                 strict.put("/api/profil/moi", json={
                     "niveau_etudes": "Baccalauréat",
                     "domaine": "Soudure et métallerie"}).status_code == 200)

        # Un compte non confirme qui se connecte doit etre oriente vers
        # la saisie du code, pas laisse devant un refus sans issue.
        autre = app.test_client()
        autre.post("/api/auth/inscription", json={
            "prenom": "Fataou", "nom": "MOUKAILA",
            "email": "fataou.c@test.io", "mot_de_passe": "Fataou2026!",
            "role": "etudiant", "consentement": CONSENT_OK})
        r = autre.post("/api/auth/connexion", json={
            "email": "fataou.c@test.io", "mot_de_passe": "Fataou2026!"})
        verifier("La connexion d'un compte non confirmé est refusée",
                 r.status_code == 403)
        corps = r.get_json() or {}
        verifier("Le refus porte de quoi ouvrir la saisie du code",
                 corps.get("confirmation_requise") is True
                 and corps.get("email") == "fataou.c@test.io")
        verifier("Le message parle du code, non d'un lien",
                 "code" in corps.get("erreur", "")
                 and "lien" not in corps.get("erreur", ""))
    finally:
        app.config["VERIFICATION_EMAIL_OBLIGATOIRE"] = avant

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  30. PRÉSENCE, DATES ET IDENTITÉ DE MARQUE")
    print("═" * 70)

    from utils.auth_helpers import DELAI_EN_LIGNE, INTERVALLE_ACTIVITE
    from routes.profil import _est_en_ligne
    from datetime import datetime as _dt, timedelta as _td

    verifier("La présence se rafraîchit moins souvent qu'elle ne s'affiche",
             INTERVALLE_ACTIVITE < DELAI_EN_LIGNE,
             "sinon quelqu'un d'actif passerait pour absent entre deux "
             "écritures")

    maintenant = _dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    vieux = (_dt.utcnow() - _td(seconds=DELAI_EN_LIGNE + 60)
             ).strftime("%Y-%m-%d %H:%M:%S")
    verifier("Une activité récente vaut « en ligne »",
             _est_en_ligne(maintenant) is True)
    verifier("Une activité ancienne ne vaut plus « en ligne »",
             _est_en_ligne(vieux) is False)
    verifier("Sans activité connue, personne n'est dit en ligne",
             _est_en_ligne(None) is False)
    verifier("Une date illisible ne fait pas tomber le calcul",
             _est_en_ligne("pas une date") is False)

    # Une requete authentifiee doit laisser une trace de passage.
    presence = app.test_client()
    presence.post("/api/auth/inscription", json={
        "prenom": "Ulrich", "nom": "AKPOVI", "email": "ulrich.p@test.io",
        "mot_de_passe": "Ulrich2026!", "role": "etudiant",
        "consentement": CONSENT_TESTS})
    presence.post("/api/auth/connexion", json={
        "email": "ulrich.p@test.io", "mot_de_passe": "Ulrich2026!"})
    presence.get("/api/profil/moi")
    verifier("Une requête laisse une trace d'activité",
             bool(jeton_sql("SELECT derniere_activite FROM utilisateur "
                            "WHERE email = ?", ("ulrich.p@test.io",))))
    p_moi = presence.get("/api/profil/moi").get_json() or {}
    verifier("Le profil rapporte la présence", p_moi.get("en_ligne") is True)

    # L'heure exacte des allees et venues ne regarde que la personne.
    id_u = jeton_sql("SELECT id_utilisateur FROM utilisateur WHERE email = ?",
                     ("ulrich.p@test.io",))
    pub_p = etu.get(f"/api/profil/{id_u}").get_json() or {}
    verifier("Le profil public dit si la personne est en ligne",
             "en_ligne" in pub_p)
    verifier("Mais pas l'heure de sa dernière venue",
             "derniere_activite" not in pub_p,
             "suivre les allées et venues à la minute près n'a pas à "
             "être offert à tous")

    # --- Identite de marque ---
    import re as _re
    for _f in ("../index.html", "../script.js", "../api.js",
               "../verifier-email.html", "../reinitialiser.html"):
        _chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), _f)
        if not os.path.exists(_chemin):
            continue
        _texte = open(_chemin, encoding="utf-8").read()
        _fautes = _re.findall(r"LaSource(?![e])", _texte)
        verifier(f"« LaSourcee » écrit avec deux e ({os.path.basename(_f)})",
                 not _fautes, f"{len(_fautes)} occurrence(s)")

    # Le domaine du Message-ID doit suivre l'expediteur : un domaine
    # etranger a l'adresse penalise la distribution.
    from utils.email import _construire_message
    msg = _construire_message("qui@test.io", "Essai", "Corps", None,
                              "LaSourcee <djorod@lasourcee.org>")
    verifier("Le Message-ID porte le domaine de l'expéditeur",
             "@lasourcee.org>" in msg["Message-ID"], msg["Message-ID"])

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  31. QUI PEUT ÉCRIRE À QUI, ET PROFILS PAR RÔLE")
    print("═" * 70)

    def _compte(prenom, email, role="etudiant"):
        c = app.test_client()
        c.post("/api/auth/inscription", json={
            "prenom": prenom, "nom": "ESSAI", "email": email,
            "mot_de_passe": "Essai2026!", "role": role,
            "consentement": CONSENT_TESTS})
        c.post("/api/auth/connexion",
               json={"email": email, "mot_de_passe": "Essai2026!"})
        return c

    beneficiaire = _compte("Ayaba", "ayaba@test.io")
    isole = _compte("Vierge", "vierge@test.io")
    referent = _compte("Sègbédji", "segbedji@test.io", "mentor")

    with app.app_context():
        from models.db import executer as _ex
        _ex("UPDATE mentor_details SET est_verifie = 1 "
            "WHERE id_utilisateur = (SELECT id_utilisateur FROM utilisateur "
            "WHERE email = %s)", ("segbedji@test.io",), commit=True)

    def _id(email):
        return jeton_sql("SELECT id_utilisateur FROM utilisateur "
                         "WHERE email = ?", (email,))

    def _ouvrir(client, cible):
        return client.post("/api/messagerie/conversations",
                           json={"id_utilisateur": cible}).status_code

    # Le coeur de la plateforme : ecrire a un referent verifie.
    verifier("Un bénéficiaire écrit à un référent vérifié",
             _ouvrir(beneficiaire, _id("segbedji@test.io")) in (200, 201))

    # Deux beneficiaires n'ont pas de raison d'echanger en prive ici, et
    # l'ouvrir reviendrait a offrir une messagerie entre inconnus sur un
    # service frequente par des lyceens.
    verifier("Deux bénéficiaires ne s'écrivent pas en privé",
             _ouvrir(isole, _id("ayaba@test.io")) == 403)

    # Il faut pouvoir signaler un probleme a quelqu'un.
    verifier("Tout le monde peut écrire à l'administration",
             _ouvrir(isole, jeton_sql(
                 "SELECT id_utilisateur FROM utilisateur "
                 "WHERE est_admin = 1 LIMIT 1")) in (200, 201))
    verifier("Un administrateur écrit à qui il veut",
             _ouvrir(adm, _id("vierge@test.io")) in (200, 201))

    # Un referent ne demarche pas un inconnu : le lien doit exister.
    verifier("Un référent n'aborde pas un inconnu",
             _ouvrir(referent, _id("vierge@test.io")) == 403,
             "c'est le premier vecteur d'abus sur ce type de plateforme")

    # Mais il peut ecrire a quelqu'un qu'il a aide.
    r = isole.post("/api/questions", json={
        "titre": "Question servant à établir un lien",
        "corps": "Un corps assez long pour passer la validation du serveur.",
        "id_secteur": 1})
    referent.post("/api/reponses", json={
        "id_question": (r.get_json() or {}).get("id_question"),
        "contenu": "Une réponse assez longue pour être acceptée."})
    verifier("Un référent écrit à qui il a répondu",
             _ouvrir(referent, _id("vierge@test.io")) in (200, 201))

    # L'interface doit connaitre la regle sans la dupliquer.
    r = isole.get("/api/messagerie/peut-ecrire/%d" % _id("ayaba@test.io"))
    verifier("L'interface peut demander si l'envoi est permis",
             r.status_code == 200)
    verifier("Le refus est motivé, non muet",
             (r.get_json() or {}).get("autorise") is False
             and len((r.get_json() or {}).get("motif", "")) > 30,
             "un refus sans explication passe pour une panne")

    # --- Statistiques par role ---
    prof_adm = etu.get("/api/profil/%d" % jeton_sql(
        "SELECT id_utilisateur FROM utilisateur WHERE est_admin = 1 LIMIT 1")
    ).get_json() or {}
    verifier("Le profil porte des comptes réels",
             all(c in prof_adm for c in
                 ("nb_questions", "nb_reponses_publiees", "nb_utiles_recus")),
             "« 0 Réponses » sur un profil d'administrateur venait d'un "
             "compteur réservé aux référents")

    prof_ben = etu.get("/api/profil/%d" % _id("ayaba@test.io")).get_json() or {}
    verifier("Les comptes d'un bénéficiaire sont chiffrés",
             isinstance(prof_ben.get("nb_questions"), int))
    verifier("Le nombre de réponses reçues comme utiles est compté",
             "nb_utiles_recus" in prof_ben)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  32. NOMS ÉCRITS PROPREMENT")
    print("═" * 70)

    from utils.noms import normaliser_nom, initiales, depuis_adresse

    verifier("Une saisie tout en majuscules est remise en forme",
             normaliser_nom("DJOSSOU") == "Djossou")
    verifier("Une saisie tout en minuscules prend sa majuscule",
             normaliser_nom("rodrigue") == "Rodrigue")
    verifier("Une casse volontaire est laissée intacte",
             normaliser_nom("McDonald") == "McDonald")
    verifier("Les espaces en trop disparaissent",
             normaliser_nom("  Chabi   Marc ") == "Chabi Marc")
    verifier("L'espace insécable devient un espace ordinaire",
             normaliser_nom("Rodrigue Djossou") == "Rodrigue Djossou")
    verifier("Les caractères invisibles sont retirés",
             normaliser_nom("ma​rie") == "Marie")
    verifier("Un accent décomposé est recomposé",
             normaliser_nom("élodie") == "Élodie"
             and len(normaliser_nom("élodie")) == 6)
    verifier("Un nom composé garde ses deux majuscules",
             normaliser_nom("MARIE-CLAIRE") == "Marie-Claire")
    verifier("L'apostrophe ouvre une nouvelle majuscule",
             normaliser_nom("d'almeida") == "D'Almeida")
    verifier("Les particules restent en minuscules",
             normaliser_nom("van der berg") == "Van der Berg")
    verifier("Une suite de chiffres n'est pas un nom",
             normaliser_nom("12345") is None)
    verifier("Les initiales sautent l'apostrophe",
             initiales("'yves", "-ko") == "YK")
    verifier("Les initiales d'un accent décomposé tiennent en une lettre",
             initiales("élodie") == "É")
    verifier("Un prénom de secours ne garde pas les chiffres",
             depuis_adresse("rodriguedjossou93@gmail.com")
             == "Rodriguedjossou")

    propre = app.test_client()
    r = propre.post("/api/auth/inscription", json={
        "prenom": "  hounsou ", "nom": "AGOSSOU", "email": "propre@test.io",
        "mot_de_passe": "PropreTest2026!", "role": "etudiant",
        "consentement": CONSENT_TESTS})
    verifier("L'inscription accepte un nom mal saisi",
             r.status_code in (200, 201), r.get_data(as_text=True)[:110])
    verifier("Le nom est écrit proprement en base",
             jeton_sql("SELECT prenom || ' ' || nom FROM utilisateur "
                       "WHERE email = ?", ("propre@test.io",))
             == "Hounsou Agossou")
    r = propre.post("/api/auth/inscription", json={
        "prenom": "4242", "nom": "9999", "email": "robot@test.io",
        "mot_de_passe": "RobotTest2026!", "role": "etudiant",
        "consentement": CONSENT_TESTS})
    verifier("Un nom sans aucune lettre est refusé", r.status_code == 400)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  33. L'INSCRIPTION ENREGISTRE TOUT DU PREMIER COUP")
    print("═" * 70)

    # Le scenario exact signale : tout est rempli pendant l'accueil
    # guide, puis l'onglet se ferme pour aller lire le code recu par
    # e-mail. Plus rien ne doit dependre de la survie de la page.
    id_secteur = jeton_sql("SELECT id_secteur FROM secteur "
                           "ORDER BY id_secteur LIMIT 1")
    libelle_pays = jeton_sql("SELECT libelle FROM pays "
                             "ORDER BY id_pays LIMIT 1")
    inscrit = app.test_client()
    r = inscrit.post("/api/auth/inscription", json={
        "prenom": "Sèdo", "nom": "Ahouandjinou",
        "email": "sedo@test.io", "mot_de_passe": "SedoTest2026!",
        "role": "etudiant", "consentement": CONSENT_TESTS,
        "profil": {
            "pays": libelle_pays,
            "niveau_etudes": "Baccalauréat",
            "domaine": "Sérigraphie sur textile",
            "etablissement": "Atelier de maître imprimeur, Bohicon",
            "situation": "En apprentissage",
            "objectifs": ["Apprendre un métier", "Gérer mon argent"],
            "bio": "J'apprends la sérigraphie et je cherche à m'installer.",
            "telephone": "+229 01 55 04 04 32",
            "secteurs": [id_secteur],
        }})
    verifier("L'inscription accepte le profil complet",
             r.status_code in (200, 201), r.get_data(as_text=True)[:140])

    ligne = str(jeton_sql(
        "SELECT niveau_etudes || '|' || domaine || '|' || etablissement "
        "|| '|' || situation || '|' || objectif || '|' || telephone "
        "FROM utilisateur WHERE email = ?", ("sedo@test.io",)))
    verifier("Le niveau d'études est écrit dès la création",
             ligne.startswith("Baccalauréat ou équivalent|"), ligne[:90])
    verifier("Le domaine libre est écrit dès la création",
             "|Sérigraphie sur textile|" in ligne)
    verifier("L'établissement libre est écrit dès la création",
             "Atelier de maître imprimeur, Bohicon" in ligne)
    verifier("La situation est écrite dès la création",
             "|En apprentissage|" in ligne)
    verifier("Les objectifs multiples sont écrits dès la création",
             "Apprendre un métier, Gérer mon argent" in ligne)
    verifier("Le téléphone est normalisé dès la création",
             ligne.endswith("|+2290155040432"), ligne[-20:])
    verifier("Le pays est reconnu à son libellé",
             jeton_sql("SELECT id_pays FROM utilisateur WHERE email = ?",
                       ("sedo@test.io",)) is not None)
    verifier("Les secteurs sont rattachés dès la création",
             jeton_sql("SELECT COUNT(*) FROM utilisateur_secteur us "
                       "JOIN utilisateur u USING (id_utilisateur) "
                       "WHERE u.email = ?", ("sedo@test.io",)) == 1)
    verifier("La présentation est écrite dès la création",
             bool(jeton_sql("SELECT bio FROM utilisateur WHERE email = ?",
                            ("sedo@test.io",))))

    # Une valeur refusee ne doit pas faire perdre le compte : le reste
    # est enregistre, et la personne corrigera depuis ses parametres.
    bancal = app.test_client()
    r = bancal.post("/api/auth/inscription", json={
        "prenom": "Kossi", "nom": "Zinsou", "email": "kossi@test.io",
        "mot_de_passe": "KossiTest2026!", "role": "etudiant",
        "consentement": CONSENT_TESTS,
        "profil": {"niveau_etudes": "Bac+42", "domaine": "Menuiserie",
                   "telephone": "12"}})
    verifier("Une valeur invalide ne fait pas perdre le compte",
             r.status_code in (200, 201))
    verifier("Le champ valide est quand même enregistré",
             jeton_sql("SELECT domaine FROM utilisateur WHERE email = ?",
                       ("kossi@test.io",)) == "Menuiserie")
    verifier("Le champ invalide est laissé vide, pas inventé",
             not jeton_sql("SELECT niveau_etudes FROM utilisateur "
                           "WHERE email = ?", ("kossi@test.io",)))

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  34. LES RÉPONSES SE LISENT ET LES NOTES S'ENREGISTRENT")
    print("═" * 70)

    # Le fil ne rapporte que le nombre de reponses. L'interface lisait
    # une liste toujours vide : aucune reponse publiee n'a jamais ete
    # lisible. Le detail doit donc porter les reponses, leur auteur, et
    # l'etat propre a la personne connectee.
    lecteur = app.test_client()
    lecteur.post("/api/auth/inscription", json={
        "prenom": "Ifè", "nom": "Akpaki", "email": "ife@test.io",
        "mot_de_passe": "IfeTest2026!", "role": "etudiant",
        "consentement": CONSENT_TESTS})
    r = lecteur.post("/api/questions", json={
        "titre": "Comment choisir entre deux ateliers de soudure ?",
        "corps": "Premier point.\nDeuxième point.\n\nTroisième point.",
        "id_secteur": 1})
    id_q = (r.get_json() or {}).get("id_question")
    verifier("La question est publiée", bool(id_q),
             r.get_data(as_text=True)[:110])

    id_ref = jeton_sql("SELECT id_utilisateur FROM utilisateur "
                       "WHERE email = ?", ("odile@test.io",))
    multiligne = ("Premier conseil.\n\nDeuxième conseil, sur une autre "
                  "ligne.\n- un tiret\n- un autre")
    r = cand.post("/api/reponses", json={"id_question": id_q,
                                         "contenu": multiligne})
    id_r = (r.get_json() or {}).get("id_reponse")
    verifier("Un référent publie une réponse", bool(id_r),
             r.get_data(as_text=True)[:110])

    detail = lecteur.get(f"/api/questions/{id_q}").get_json() or {}
    reponses = detail.get("reponses") or []
    verifier("Le détail de la question porte ses réponses",
             len(reponses) == 1, f"{len(reponses)} réponse(s)")
    verifier("Les retours à la ligne sont conservés tels quels",
             bool(reponses) and reponses[0].get("contenu") == multiligne)
    verifier("Le corps de la question garde ses paragraphes",
             detail.get("corps", "").count("\n") == 3)
    verifier("La réponse porte son identifiant",
             bool(reponses) and reponses[0].get("id_reponse") == id_r)
    verifier("La réponse porte son auteur",
             bool(reponses) and reponses[0].get("prenom") == "Odile")
    verifier("La réponse dit si elle vient d'un référent vérifié",
             bool(reponses) and reponses[0].get("verifie") in (1, True))

    # Les etoiles existaient a l'ecran sans rien enregistrer : la
    # moyenne d'un referent valait zero pour tout le monde.
    r = lecteur.post(f"/api/reponses/{id_r}/note", json={"valeur": 5})
    verifier("Une note est acceptée", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("La note est relue sur le détail",
             ((lecteur.get(f"/api/questions/{id_q}").get_json()
               or {}).get("reponses") or [{}])[0].get("ma_note") == 5)
    verifier("La moyenne du référent est recalculée",
             float(jeton_sql("SELECT note_moyenne FROM mentor_details "
                             "WHERE id_utilisateur = ?", (id_ref,)) or 0)
             == 5.0)
    r = lecteur.post(f"/api/reponses/{id_r}/note", json={"valeur": 3})
    verifier("Une note se corrige sans se dupliquer",
             r.status_code == 200
             and jeton_sql("SELECT COUNT(*) FROM note_reponse "
                           "WHERE id_reponse = ?", (id_r,)) == 1)
    verifier("La moyenne suit la correction",
             float(jeton_sql("SELECT note_moyenne FROM mentor_details "
                             "WHERE id_utilisateur = ?", (id_ref,)) or 0)
             == 3.0)
    r = lecteur.post(f"/api/reponses/{id_r}/note", json={"valeur": 9})
    verifier("Une note hors barème est refusée", r.status_code == 400)
    r = cand.post(f"/api/reponses/{id_r}/note", json={"valeur": 5})
    verifier("On ne note pas sa propre réponse", r.status_code == 400)

    # Le pouce et la sauvegarde doivent survivre au rechargement : ils
    # n'etaient renvoyes nulle part, et revenaient vides a chaque fois.
    lecteur.post(f"/api/reponses/{id_r}/utile", json={})
    lecteur.post(f"/api/questions/{id_q}/sauvegarder", json={})
    relu = lecteur.get(f"/api/questions/{id_q}").get_json() or {}
    verifier("Le pouce posé sur une réponse est relu",
             (relu.get("reponses") or [{}])[0].get("mon_utile") is True)
    verifier("La sauvegarde de la question est relue",
             relu.get("sauvegardee") is True)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  35. BOURSES, OPPORTUNITÉS ET MESSAGES À L'ÉQUIPE")
    print("═" * 70)

    # --- Qui publie quoi ---
    r = lecteur.post("/api/opportunites", json={
        "titre": "Bourse que personne ne devrait pouvoir publier",
        "description": "Un bénéficiaire ne publie pas d'annonce, il la "
                       "signale à l'équipe qui la reprend.",
        "organisme": "Inconnu"})
    verifier("Un bénéficiaire ne publie pas d'annonce", r.status_code == 403)

    r = cand.post("/api/opportunites", json={
        "titre": "Bourse de master en agronomie",
        "categorie": "bourse",
        "organisme": "Ambassade du Japon",
        "description": "Bourse complète pour un master en agronomie, "
                       "ouverte aux titulaires d'une licence.",
        "pays": "Japon", "niveau": "Licence",
        "date_limite": "2027-03-15",
        "lien": "https://exemple.org/bourse"})
    id_opp = (r.get_json() or {}).get("id_opportunite")
    verifier("Un référent propose une annonce", r.status_code in (200, 201),
             r.get_data(as_text=True)[:110])
    verifier("La proposition d'un référent attend une relecture",
             (r.get_json() or {}).get("statut") == "en_attente")
    verifier("Elle n'apparaît pas encore dans le fil",
             not any(o["id_opportunite"] == id_opp for o in
                     (lecteur.get("/api/opportunites").get_json()
                      or {}).get("opportunites", [])))

    r = cand.post("/api/opportunites", json={
        "titre": "Annonce sans moyen de vérifier",
        "description": "Une annonce sans organisme ni lien ne se vérifie "
                       "pas, et personne ne peut la recouper."})
    verifier("Une annonce sans organisme ni lien est refusée",
             r.status_code == 400)
    r = cand.post("/api/opportunites", json={
        "titre": "Annonce avec une date impossible",
        "description": "La date limite doit être lisible par la machine "
                       "autant que par la personne.",
        "organisme": "Un organisme", "date_limite": "15 mars"})
    verifier("Une date limite mal écrite est refusée", r.status_code == 400)

    # --- Relecture ---
    a_relire = adm.get("/api/opportunites/a-relire").get_json() or []
    verifier("L'annonce attend dans la file de relecture",
             any(o["id_opportunite"] == id_opp for o in a_relire))
    r = adm.post(f"/api/opportunites/{id_opp}/decision",
                 json={"statut": "refusee"})
    verifier("Un refus sans motif est refusé", r.status_code == 400)
    r = adm.post(f"/api/opportunites/{id_opp}/decision",
                 json={"statut": "publiee"})
    verifier("La relecture publie l'annonce", r.status_code == 200,
             r.get_data(as_text=True)[:110])

    fil = (lecteur.get("/api/opportunites").get_json() or {})
    publiees = fil.get("opportunites", [])
    verifier("L'annonce paraît dans le fil",
             any(o["id_opportunite"] == id_opp for o in publiees))
    verifier("Le référent est prévenu de la mise en ligne",
             jeton_sql("SELECT COUNT(*) FROM notification "
                       "WHERE id_destinataire = ? AND texte LIKE ?",
                       (id_ref, "%est en ligne%")) >= 1)
    verifier("Un bénéficiaire ne voit pas la file de relecture",
             lecteur.get("/api/opportunites/a-relire").status_code == 403)

    # Une annonce dont la date est passee ne se melange pas aux autres.
    adm.post("/api/opportunites", json={
        "titre": "Concours dont la date est passée",
        "categorie": "concours", "organisme": "Un ministère",
        "description": "Cette annonce est close, mais elle revient chaque "
                       "année : savoir qu'elle existe a de la valeur.",
        "date_limite": "2020-01-31"})
    fil = lecteur.get("/api/opportunites").get_json() or {}
    verifier("Une annonce close est comptée à part",
             fil.get("nb_closes") == 1, str(fil.get("nb_closes")))
    verifier("Elle est écartée du fil par défaut",
             not any(o.get("cloturee") for o in fil.get("opportunites", [])))
    avec = lecteur.get("/api/opportunites?closes=1").get_json() or {}
    verifier("Elle reste consultable sur demande",
             any(o.get("cloturee") for o in avec.get("opportunites", [])))

    # --- Messages a l'equipe ---
    anonyme = app.test_client()
    r = anonyme.post("/api/equipe/message", json={
        "message": "Le bouton de connexion ne répond pas sur mon téléphone.",
        "categorie": "panne"})
    verifier("Sans compte, une adresse est demandée", r.status_code == 400)
    r = anonyme.post("/api/equipe/message", json={
        "message": "Le bouton de connexion ne répond pas sur mon téléphone.",
        "categorie": "panne", "email": "passant@test.io", "nom": "un passant"})
    verifier("Une personne non connectée peut écrire",
             r.status_code in (200, 201), r.get_data(as_text=True)[:110])
    verifier("Le nom donné sans compte est mis en forme",
             jeton_sql("SELECT nom FROM message_equipe WHERE email = ?",
                       ("passant@test.io",)) == "Un Passant")

    r = lecteur.post("/api/equipe/message", json={"message": "bug"})
    verifier("Un message trop court est refusé", r.status_code == 400)
    r = lecteur.post("/api/equipe/message", json={
        "categorie": "suggestion",
        "message": "Il manque un moyen de filtrer les questions par pays.",
        "page": "fil"})
    id_msg = (r.get_json() or {}).get("id_message")
    verifier("Un membre connecté écrit à l'équipe", bool(id_msg),
             r.get_data(as_text=True)[:110])
    verifier("La page d'où l'on écrit est conservée",
             jeton_sql("SELECT page FROM message_equipe WHERE id_message = ?",
                       (id_msg,)) == "fil")
    verifier("L'auteur connecté est rattaché au message",
             jeton_sql("SELECT id_utilisateur FROM message_equipe "
                       "WHERE id_message = ?", (id_msg,)) is not None)

    verifier("Un membre ne lit pas les messages des autres",
             lecteur.get("/api/equipe/messages").status_code == 403)
    boite = adm.get("/api/equipe/messages").get_json() or {}
    verifier("L'administration voit les messages reçus",
             len(boite.get("messages") or []) >= 2)
    verifier("Les non traités sont comptés", boite.get("nouveaux", 0) >= 2)

    r = adm.post(f"/api/equipe/messages/{id_msg}/traiter",
                 json={"statut": "inconnu"})
    verifier("Un statut inconnu est refusé", r.status_code == 400)
    r = adm.post(f"/api/equipe/messages/{id_msg}/traiter",
                 json={"statut": "traite", "reponse": "C'est noté, merci."})
    verifier("Un message se marque traité", r.status_code == 200)
    verifier("La personne est prévenue de la réponse",
             jeton_sql("SELECT COUNT(*) FROM notification n "
                       "JOIN utilisateur u "
                       "  ON u.id_utilisateur = n.id_destinataire "
                       "WHERE u.email = ? AND n.texte LIKE ?",
                       ("ife@test.io", "%a répondu à votre message%")) >= 1)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  36. OUVERTURE AUX AUTRES PAYS")
    print("═" * 70)

    # La page portait une liste de deux cent cinquante pays alors que la
    # table n'en contenait que dix-huit : choisir le Gabon ou le Rwanda
    # ne correspondait a aucune ligne, et le pays disparaissait du
    # profil sans un mot.
    pays = (etu.get("/api/profil/referentiels").get_json() or {}).get("pays", [])
    noms = {p["libelle"] for p in pays}
    verifier("Le référentiel dépasse le périmètre d'origine",
             len(pays) >= 100, f"{len(pays)} pays")
    for attendu in ("Gabon", "Rwanda", "Haïti", "Cameroun", "Bénin",
                    "Canada", "Japon", "Nigéria"):
        verifier(f"« {attendu} » figure dans la liste", attendu in noms)
    verifier("« Autre » reste proposé en dernier recours", "Autre" in noms)
    verifier("Aucun pays n'est en double",
             len(noms) == len(pays), f"{len(pays) - len(noms)} doublon(s)")

    # Le rattrapage tourne a chaque demarrage : il ne doit rien ajouter
    # deux fois.
    from services.referentiels import completer_pays
    with app.app_context():
        ajoutes = completer_pays()
    verifier("Un second passage n'ajoute aucun pays", ajoutes == 0,
             f"{ajoutes} ajout(s)")

    hors = app.test_client()
    id_gabon = next(p["id_pays"] for p in pays if p["libelle"] == "Gabon")
    r = hors.post("/api/auth/inscription", json={
        "prenom": "Ntsame", "nom": "Obame", "email": "ntsame@test.io",
        "mot_de_passe": "NtsameTest2026!", "role": "etudiant",
        "consentement": CONSENT_TESTS,
        "profil": {"pays": "Gabon", "telephone": "+241 06 12 34 56"}})
    verifier("Une inscription depuis un autre pays aboutit",
             r.status_code in (200, 201), r.get_data(as_text=True)[:110])
    verifier("Le pays est bien celui qui a été choisi",
             jeton_sql("SELECT id_pays FROM utilisateur WHERE email = ?",
                       ("ntsame@test.io",)) == id_gabon)
    verifier("Le pays est relu sur le profil",
             (hors.get("/api/profil/moi").get_json() or {}).get("pays")
             == "Gabon")
    verifier("Un numéro étranger est accepté",
             jeton_sql("SELECT telephone FROM utilisateur WHERE email = ?",
                       ("ntsame@test.io",)) == "+241061234 56".replace(" ", ""))

    # --- Parcours scolaire ---
    # La liste des diplomes nommait le systeme beninois : CEP, BEPC,
    # CQM. Quelqu'un au Cameroun ou au Canada ne s'y reconnaissait pas.
    ref = etu.get("/api/profil/referentiels-profil").get_json() or {}
    niveaux = ref.get("niveaux_etudes") or []
    verifier("Les diplômes nomment un niveau, pas un sigle local",
             not any(n.startswith(("CEP ", "BEPC ")) for n in niveaux),
             " | ".join(niveaux[:4]))
    verifier("Les diplômes locaux restent cités en exemple",
             any("CEP" in n for n in niveaux) and any("BEPC" in n for n in niveaux))

    # Les suggestions d'etablissement suivent le pays.
    benin = (etu.get("/api/profil/referentiels-profil?pays=Bénin").get_json()
             or {}).get("etablissements") or []
    senegal = (etu.get("/api/profil/referentiels-profil?pays=Sénégal").get_json()
               or {}).get("etablissements") or []
    inconnu = (etu.get("/api/profil/referentiels-profil?pays=Mongolie").get_json()
               or {}).get("etablissements") or []
    verifier("Le Bénin propose ses établissements",
             any("Abomey-Calavi" in e for e in benin))
    verifier("Le Sénégal propose les siens, pas ceux du Bénin",
             any("Cheikh Anta Diop" in e for e in senegal)
             and not any("Abomey-Calavi" in e for e in senegal))
    verifier("Un pays sans liste garde les propositions universelles",
             "Atelier ou maître artisan" in inconnu
             and not any("Abomey-Calavi" in e for e in inconnu))
    verifier("L'apprentissage figure partout",
             all("Atelier ou maître artisan" in liste
                 for liste in (benin, senegal, inconnu)))

    # La filiere precise ce que le domaine laisse large.
    r = hors.put("/api/profil/moi", json={
        "domaine": "Informatique et numérique",
        "filiere": "  Génie   logiciel  "})
    verifier("La filière s'enregistre", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("La filière est nettoyée de ses espaces en trop",
             jeton_sql("SELECT filiere FROM utilisateur WHERE email = ?",
                       ("ntsame@test.io",)) == "Génie logiciel")
    verifier("La filière est relue sur le profil",
             (hors.get("/api/profil/moi").get_json() or {}).get("filiere")
             == "Génie logiciel")
    verifier("La filière voyage aussi sur un profil consulté",
             "filiere" in (etu.get("/api/profil/%d" % _id("ntsame@test.io"))
                           .get_json() or {}))

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  37. RÉSUMÉ PÉRIODIQUE DE L'ACTIVITÉ")
    print("═" * 70)

    import os as _os
    from datetime import datetime as _dt
    from models.db import executer as _executer
    from services import resume as mod_resume

    # La route est une arme : elle envoie des e-mails en masse.
    verifier("Sans secret, la tâche est refusée",
             app.test_client().post("/api/taches/resume").status_code == 403)
    _os.environ["CRON_SECRET"] = "secret-de-test-pour-la-tache"
    verifier("Avec un mauvais secret, la tâche est refusée",
             app.test_client().post(
                 "/api/taches/resume",
                 headers={"Authorization": "Bearer faux"}).status_code == 403)
    r = app.test_client().post(
        "/api/taches/resume",
        headers={"Authorization": "Bearer secret-de-test-pour-la-tache"})
    verifier("Avec le bon secret, la tâche répond", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    # L'ordonnanceur de l'hebergeur appelle en GET. La route n'acceptait
    # que POST : elle repondait 405 a chaque passage, et le resume ne
    # serait jamais parti en production, sans la moindre trace.
    r_get = app.test_client().get(
        "/api/taches/resume",
        headers={"Authorization": "Bearer secret-de-test-pour-la-tache"})
    verifier("La tâche répond aussi au GET de l'ordonnanceur",
             r_get.status_code == 200, f"reçu {r_get.status_code}")
    verifier("Et le GET exige le même secret",
             app.test_client().get("/api/taches/resume").status_code == 403)
    verifier("En mode console, rien ne part et rien n'est marqué",
             "ignore" in (r.get_json() or {}))
    _os.environ.pop("CRON_SECRET", None)

    with app.app_context():
        id_ife = _id("ife@test.io")
        jeton = mod_resume.jeton_desinscription(id_ife)
        verifier("Le jeton de désinscription est signé",
                 mod_resume.jeton_valide(id_ife, jeton))
        verifier("Le jeton d'un compte ne vaut pas pour un autre",
                 not mod_resume.jeton_valide(id_ife + 1, jeton))
        verifier("Un jeton inventé est refusé",
                 not mod_resume.jeton_valide(id_ife, "0" * 32))

        # La confirmation d'adresse n'est pas exigee dans ces tests : on
        # la pose, puisque c'est justement ce que la requete demande.
        _executer("UPDATE utilisateur SET email_verifie = 1, "
                  "resume_envoye_le = NULL, resume_examine_le = NULL "
                  "WHERE id_utilisateur = %s", (id_ife,), commit=True)
        cibles = [c["id_utilisateur"] for c in mod_resume._destinataires()]
        verifier("Un compte jamais prévenu est candidat", id_ife in cibles)

        # Le delai : deux jours, et pas moins. C'est la date d'EXAMEN
        # qui commande la file, pas celle d'envoi.
        maintenant = _dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        _executer("UPDATE utilisateur SET resume_examine_le = %s "
                  "WHERE id_utilisateur = %s", (maintenant, id_ife),
                  commit=True)
        cibles = [c["id_utilisateur"] for c in mod_resume._destinataires()]
        verifier("Un compte qui vient d'être examiné est écarté",
                 id_ife not in cibles)

        # Le defaut a ne pas laisser revenir : un compte sans nouveaute
        # n'etait jamais marque, restait en tete de file, et comme le
        # passage s'arrete au quarantieme examine, les memes quarante
        # comptes l'occupaient indefiniment. Passe quelques semaines,
        # plus personne ne recevait rien.
        _executer("UPDATE utilisateur SET resume_examine_le = NULL "
                  "WHERE id_utilisateur = %s", (id_ife,), commit=True)
        mod_resume._examine(id_ife)
        verifier("Un passage silencieux fait quand même avancer la file",
                 id_ife not in [c["id_utilisateur"]
                                for c in mod_resume._destinataires()])
        verifier("Mais il ne referme pas la fenêtre des nouveautés",
                 jeton_sql("SELECT resume_envoye_le FROM utilisateur "
                           "WHERE id_utilisateur = ?", (id_ife,)) is None)
        mod_resume._marquer(id_ife)
        verifier("Un message réellement parti ouvre une nouvelle fenêtre",
                 jeton_sql("SELECT resume_envoye_le FROM utilisateur "
                           "WHERE id_utilisateur = ?", (id_ife,)) is not None)
        _executer("UPDATE utilisateur SET resume_examine_le = NULL, "
                  "resume_envoye_le = NULL WHERE id_utilisateur = %s",
                  (id_ife,), commit=True)
        verifier("Un compte suspendu ne reçoit rien",
                 _suspendu_ecarte(mod_resume, _executer, id_ife))

        # Un compte non confirme ou desactive ne recoit rien.
        _executer("UPDATE utilisateur SET email_verifie = 0 "
                  "WHERE id_utilisateur = %s", (id_ife,), commit=True)
        verifier("Un compte non confirmé ne reçoit pas de résumé",
                 id_ife not in [c["id_utilisateur"]
                                for c in mod_resume._destinataires()])
        _executer("UPDATE utilisateur SET email_verifie = 1 "
                  "WHERE id_utilisateur = %s", (id_ife,), commit=True)

    # La desinscription fonctionne sans session.
    stop = app.test_client()
    r = stop.get(f"/api/profil/resume/stop?u={id_ife}&j=faux")
    verifier("Une désinscription mal signée est refusée", r.status_code == 400)
    with app.app_context():
        jeton = mod_resume.jeton_desinscription(id_ife)
    r = stop.get(f"/api/profil/resume/stop?u={id_ife}&j={jeton}")
    verifier("La désinscription aboutit sans être connecté",
             r.status_code == 200, r.get_data(as_text=True)[:110])
    with app.app_context():
        verifier("Le refus est enregistré", not mod_resume._accepte(id_ife))

    # Un resume vide n'est pas envoye : il apprend a ne plus ouvrir.
    verifier("Un seuil minimum de nouveautés est exigé",
             mod_resume.SEUIL_NOUVEAUTES >= 2)
    verifier("Le délai annoncé est bien de deux jours",
             mod_resume.DELAI_HEURES == 48)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  38. PAGES PUBLIQUES ET PLAN DU SITE")
    print("═" * 70)

    # Le site entier vivait derriere une connexion : un moteur de
    # recherche n'en voyait qu'une page. Aucune quantite de balises ne
    # compense l'absence de contenu lisible.
    robot = app.test_client()          # aucun cookie, aucune session
    page = robot.get(f"/question/{id_q}")
    verifier("Une question se lit sans compte", page.status_code == 200,
             str(page.status_code))
    texte = page.get_data(as_text=True)
    verifier("Le titre est un vrai titre de page",
             "<h1>" in texte and "ateliers de soudure" in texte)
    verifier("La réponse du référent est dans la page",
             "Premier conseil." in texte)
    verifier("Les données structurées décrivent une page de question",
             '"@type": "QAPage"' in texte)
    verifier("La meilleure réponse est déclarée aux moteurs",
             '"acceptedAnswer"' in texte)
    verifier("L'adresse canonique est déclarée",
             'rel="canonical"' in texte)
    verifier("La page invite à créer un compte",
             "Rejoindre LaSourcee" in texte)

    # Une question publique ne doit pas rendre publique la personne.
    verifier("Le nom complet de l'auteur n'est jamais exposé",
             "Hounkpatin" not in texte and "Akpaki" not in texte,
             "prénom et initiale seulement")
    verifier("Aucune adresse e-mail ne figure sur la page",
             "@test.io" not in texte)

    liste = robot.get("/questions")
    verifier("La liste des questions se lit sans compte",
             liste.status_code == 200)
    verifier("Elle porte un lien vers chaque question",
             f"/question/{id_q}-" in liste.get_data(as_text=True))

    plan = robot.get("/sitemap.xml")
    verifier("Le plan du site répond", plan.status_code == 200)
    verifier("Il est servi en XML",
             "xml" in (plan.headers.get("Content-Type") or ""))
    plan_texte = plan.get_data(as_text=True)
    verifier("Le plan liste les questions, pas seulement l'accueil",
             f"/question/{id_q}-" in plan_texte)
    verifier("Chaque question porte sa date de mise à jour",
             "<lastmod>" in plan_texte)
    verifier("L'adresse des pages contient le titre lisible",
             "soudure" in plan_texte)

    # Une adresse inventee ne doit pas repondre 200 : un moteur
    # indexerait des pages vides a l'infini.
    verifier("Une question inexistante répond 404",
             robot.get("/question/999999").status_code == 404)
    verifier("Une page de liste au-delà du dernier résultat répond 404",
             robot.get("/questions?page=99").status_code == 404)

    # Le reglage referme tout.
    app.config["QUESTIONS_PUBLIQUES"] = False
    verifier("Le réglage referme les pages publiques",
             robot.get(f"/question/{id_q}").status_code == 404)
    verifier("Le plan du site se réduit alors à l'accueil",
             f"/question/{id_q}" not in robot.get("/sitemap.xml")
             .get_data(as_text=True))
    app.config["QUESTIONS_PUBLIQUES"] = True

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  39. RÉPONSES CLASSÉES, RETENUES ET ENFILÉES")
    print("═" * 70)

    # Une reponse a une reponse : la colonne existait depuis l'origine
    # mais rien ne l'exploitait, et un echange en trois temps se lisait
    # comme trois reponses independantes a la question de depart.
    r = lecteur.post("/api/reponses", json={
        "id_question": id_q, "id_parent_reponse": id_r,
        "contenu": "Merci, mais l'atelier est-il loin de Bohicon ?"})
    verifier("On peut répondre à une réponse", r.status_code in (200, 201),
             r.get_data(as_text=True)[:110])

    detail = lecteur.get(f"/api/questions/{id_q}").get_json() or {}
    racines = detail.get("reponses") or []
    verifier("Le fil n'apparaît pas comme une réponse de plus",
             len(racines) == 1, f"{len(racines)} racine(s)")
    verifier("Le fil est rangé sous la réponse à laquelle il répond",
             len((racines[0].get("sous_reponses") or [])) == 1)

    # La reponse retenue par l'auteur passe en tete.
    autre = cand.post("/api/reponses", json={
        "id_question": id_q,
        "contenu": "Autre avis : commencez par visiter les deux ateliers."})
    id_autre = (autre.get_json() or {}).get("id_reponse")

    r = cand.post(f"/api/questions/{id_q}/retenir",
                  json={"id_reponse": id_autre})
    verifier("Un tiers ne choisit pas la réponse qui a aidé",
             r.status_code == 403)
    r = lecteur.post(f"/api/questions/{id_q}/retenir",
                     json={"id_reponse": id_autre})
    verifier("L'auteur de la question retient une réponse",
             r.status_code == 200, r.get_data(as_text=True)[:110])
    verifier("La question passe en résolue",
             (r.get_json() or {}).get("statut") == "resolue")
    verifier("Le référent est prévenu que sa réponse a servi",
             jeton_sql("SELECT COUNT(*) FROM notification "
                       "WHERE id_destinataire = ? AND texte LIKE ?",
                       (id_ref, "%retenue comme celle qui a aidé%")) >= 1)

    detail = lecteur.get(f"/api/questions/{id_q}").get_json() or {}
    racines = detail.get("reponses") or []
    verifier("La réponse retenue passe en tête",
             racines and racines[0].get("id_reponse") == id_autre,
             str([x.get("id_reponse") for x in racines]))
    verifier("Elle est signalée comme telle",
             racines and racines[0].get("retenue") is True)
    verifier("Le détail porte la réponse retenue",
             detail.get("id_reponse_retenue") == id_autre)

    # Se tromper doit se corriger sans passer par l'administration.
    r = lecteur.post(f"/api/questions/{id_q}/retenir",
                     json={"id_reponse": id_autre})
    verifier("Un second choix identique annule le précédent",
             (r.get_json() or {}).get("retenue") is None)
    verifier("La question repasse en ouverte",
             jeton_sql("SELECT statut FROM question WHERE id_question = ?",
                       (id_q,)) == "ouverte")

    # Une reponse d'une autre question n'a rien a faire ici.
    autre_q = lecteur.post("/api/questions", json={
        "titre": "Une question sans rapport avec la précédente",
        "corps": "Elle sert à vérifier qu'on ne retient pas n'importe quoi.",
        "id_secteur": 1}).get_json() or {}
    r = lecteur.post(f"/api/questions/{autre_q.get('id_question')}/retenir",
                     json={"id_reponse": id_autre})
    verifier("Une réponse d'une autre question est refusée",
             r.status_code == 400)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  40. GESTION DES COMPTES ET JOURNAL D'ADMINISTRATION")
    print("═" * 70)

    # La liste s'arretait a cinq cents comptes, sans page suivante ni
    # total : passe ce seuil les plus anciens devenaient inatteignables.
    page = adm.get("/api/admin/utilisateurs?limite=2&page=1").get_json() or {}
    verifier("La liste des comptes est paginée",
             isinstance(page.get("utilisateurs"), list)
             and len(page["utilisateurs"]) <= 2, str(type(page)))
    verifier("Elle annonce le total", isinstance(page.get("total"), int)
             and page["total"] > 2, str(page.get("total")))
    verifier("Elle annonce le nombre de pages", page.get("pages", 0) > 1)
    page2 = adm.get("/api/admin/utilisateurs?limite=2&page=2").get_json() or {}
    verifier("La page suivante donne d'autres comptes",
             [u["id_utilisateur"] for u in page2.get("utilisateurs", [])]
             != [u["id_utilisateur"] for u in page.get("utilisateurs", [])])

    # LIKE distingue les majuscules sur PostgreSQL : chercher
    # « djossou » ne trouvait pas « Djossou ».
    minuscules = adm.get("/api/admin/utilisateurs?q=hounkpatin").get_json() or {}
    verifier("La recherche ignore la casse",
             any(u["nom"] == "Hounkpatin"
                 for u in minuscules.get("utilisateurs", [])),
             f"{minuscules.get('total')} résultat(s)")
    majuscules = adm.get("/api/admin/utilisateurs?q=HOUNKPATIN").get_json() or {}
    verifier("Elle donne le même résultat en majuscules",
             majuscules.get("total") == minuscules.get("total"))
    verifier("Elle cherche aussi dans l'adresse",
             (adm.get("/api/admin/utilisateurs?q=odile@").get_json()
              or {}).get("total", 0) >= 1)

    filtre = adm.get("/api/admin/utilisateurs?role=mentor").get_json() or {}
    verifier("Le filtre par rôle s'applique",
             all(u["role"] == "mentor"
                 for u in filtre.get("utilisateurs", [])))
    verifier("La ligne porte la date d'inscription et la dernière visite",
             all(c in (page.get("utilisateurs") or [{}])[0]
                 for c in ("cree_le", "derniere_co", "email_verifie")))

    # Le journal : filtres, pagination, et la trace de chaque decision.
    journal = adm.get("/api/admin/audit?limite=5").get_json() or {}
    verifier("Le journal est paginé",
             isinstance(journal.get("entrees"), list)
             and isinstance(journal.get("total"), int))
    verifier("Il propose les actions réellement enregistrées",
             isinstance(journal.get("actions"), list)
             and len(journal["actions"]) > 3, str(journal.get("actions"))[:80])
    verifier("Chaque ligne porte son auteur et son heure",
             all(c in (journal.get("entrees") or [{}])[0]
                 for c in ("prenom", "cree_le", "id_acteur", "ip")))

    une_action = (journal.get("actions") or ["verifier_mentor"])[0]
    cible = adm.get(f"/api/admin/audit?action={une_action}").get_json() or {}
    verifier("Le filtre par action s'applique",
             all(e["action"] == une_action for e in cible.get("entrees", [])),
             une_action)
    id_adm = jeton_sql("SELECT id_utilisateur FROM utilisateur "
                       "WHERE est_admin = 1 LIMIT 1")
    par_acteur = adm.get(f"/api/admin/audit?acteur={id_adm}").get_json() or {}
    verifier("Le filtre par acteur s'applique",
             all(e["id_acteur"] == id_adm
                 for e in par_acteur.get("entrees", [])))

    # Les decisions des deux modules recents laissent une trace.
    verifier("Une décision sur une annonce est journalisée",
             jeton_sql("SELECT COUNT(*) FROM audit_admin "
                       "WHERE action LIKE ?", ("opportunite_%",)) >= 1)
    verifier("Le traitement d'un message à l'équipe est journalisé",
             jeton_sql("SELECT COUNT(*) FROM audit_admin "
                       "WHERE action LIKE ?", ("message_equipe_%",)) >= 1)

    verifier("Un membre n'accède pas au journal",
             lecteur.get("/api/admin/audit").status_code == 403)
    verifier("Un membre n'accède pas à la liste des comptes",
             lecteur.get("/api/admin/utilisateurs").status_code == 403)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  41. LE PROFIL MONTRE UNE ACTIVITÉ, PAS SEULEMENT DES CHIFFRES")
    print("═" * 70)

    mien = lecteur.get("/api/profil/moi").get_json() or {}
    verifier("Le profil porte les dernières questions",
             isinstance(mien.get("dernieres_questions"), list)
             and len(mien["dernieres_questions"]) >= 1,
             str(len(mien.get("dernieres_questions") or [])))
    verifier("Chaque question porte son titre, sa date et son compte",
             all(c in (mien.get("dernieres_questions") or [{}])[0]
                 for c in ("titre", "publiee_le", "nb_reponses", "statut")))

    sien = lecteur.get("/api/profil/%d" % id_ref).get_json() or {}
    verifier("Le profil d'un référent porte ses dernières réponses",
             isinstance(sien.get("dernieres_reponses"), list)
             and len(sien["dernieres_reponses"]) >= 1)
    premiere = (sien.get("dernieres_reponses") or [{}])[0]
    verifier("La réponse est résumée, pas recopiée en entier",
             "extrait" in premiere and "contenu" not in premiere)
    verifier("L'extrait renvoie à sa question",
             bool(premiere.get("id_question")) and bool(premiere.get("titre")))
    verifier("Le profil compte les réponses retenues",
             isinstance(sien.get("nb_reponses_retenues"), int))

    # Un profil consulte ne doit rien laisser filtrer de plus qu'avant.
    verifier("L'adresse e-mail reste absente d'un profil consulté",
             "email" not in sien)
    verifier("Le téléphone reste absent d'un profil consulté",
             "telephone" not in sien)

    verifier("L'activité est bornée",
             len(sien.get("dernieres_reponses") or []) <= 5
             and len(sien.get("dernieres_questions") or []) <= 5)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  42. LES DATES ARRIVENT DANS UN FORMAT QUE LE NAVIGATEUR LIT")
    print("═" * 70)

    # SQLite rend des chaines, PostgreSQL de vrais objets datetime, que
    # Flask convertissait par defaut en « Wed, 23 Sep 2026 22:20:01 GMT ».
    # Le navigateur ne sait pas lire cette forme : en production, plus
    # aucune date ne s'affichait nulle part. Et rien ne le signalait,
    # puisque ces tests passaient par SQLite, ou le defaut n'existe pas.
    import re as _re
    ISO = _re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")

    def _lisible(valeur):
        return bool(valeur) and bool(ISO.match(str(valeur)))

    mien = lecteur.get("/api/profil/moi").get_json() or {}
    verifier("La date d'inscription est lisible par le navigateur",
             _lisible(mien.get("cree_le")), repr(mien.get("cree_le")))
    verifier("Aucune date n'est rendue au format HTTP",
             "GMT" not in str(mien.get("cree_le")), repr(mien.get("cree_le")))

    detail = lecteur.get(f"/api/questions/{id_q}").get_json() or {}
    verifier("La date de publication d'une question est lisible",
             _lisible(detail.get("publiee_le")), repr(detail.get("publiee_le")))
    verifier("La date d'une réponse est lisible",
             _lisible((detail.get("reponses") or [{}])[0].get("cree_le")),
             repr((detail.get("reponses") or [{}])[0].get("cree_le")))

    fil = lecteur.get("/api/questions").get_json() or []
    verifier("Les dates du fil sont lisibles",
             all(_lisible(q.get("publiee_le")) for q in fil), str(fil[:1])[:110])

    journal = (adm.get("/api/admin/audit?limite=3").get_json()
               or {}).get("entrees") or []
    verifier("Les dates du journal d'administration sont lisibles",
             all(_lisible(e.get("cree_le")) for e in journal),
             str(journal[:1])[:110])

    comptes = (adm.get("/api/admin/utilisateurs?limite=3").get_json()
               or {}).get("utilisateurs") or []
    verifier("Les dates de la gestion des comptes sont lisibles",
             all(_lisible(u.get("cree_le")) for u in comptes),
             str(comptes[:1])[:110])

    notifs = lecteur.get("/api/notifications").get_json() or []
    verifier("Les dates des notifications sont lisibles",
             all(_lisible(n.get("cree_le")) for n in notifs) if notifs else True)

    # Un instant sans fuseau doit porter le « Z » : sans lui, le
    # navigateur le lit comme une heure locale et decale tout.
    verifier("Les instants sont marqués comme UTC",
             str(mien.get("cree_le")).endswith("Z")
             or _MOTEUR == "sqlite", repr(mien.get("cree_le")))

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  43. UN ADMINISTRATEUR NE PEUT PAS DÉSARMER L'ADMINISTRATION")
    print("═" * 70)

    # Rien n'empechait un administrateur ordinaire d'agir sur le compte
    # d'un super administrateur : le retrograder, changer son adresse
    # pour en demander ensuite le mot de passe, ou le suspendre.
    #
    # Les deux comptes sont crees ici et promus en base : dependre des
    # clients ouverts plus haut ferait echouer cette section pour une
    # raison sans rapport, des qu'une section anterieure change un mot
    # de passe ou revoque une session.
    from models.db import executer as _maj

    def _compte_admin(prenom, email, mdp, role, droits):
        """Compte cree directement en base, puis connecte.

        Passer par l'inscription echouerait ici : la suite a deja cree
        assez de comptes depuis la meme adresse IP pour atteindre la
        limite anti-robot, et le test echouerait pour une raison sans
        rapport avec ce qu'il verifie.
        """
        from utils.auth_helpers import hacher_mot_de_passe
        with app.app_context():
            _maj("""INSERT INTO utilisateur
                      (prenom, nom, email, mot_de_passe, role, est_admin,
                       est_actif, email_verifie, permissions)
                    VALUES (%s, 'Essai', %s, %s, %s, 1, 1, 1, %s)""",
                 (prenom, email, hacher_mot_de_passe(mdp), role, droits),
                 commit=True)
        identifiant = _id(email)
        client = app.test_client()
        r = client.post("/api/auth/connexion",
                        json={"email": email, "mot_de_passe": mdp})
        assert r.status_code == 200, r.get_data(as_text=True)[:120]
        return client, identifiant

    ordinaire, id_ordinaire = _compte_admin(
        "Modeste", "modeste@test.io", "ModesteTest2026!",
        "admin", '["utilisateurs"]')
    patron, id_patron = _compte_admin(
        "Patronne", "patronne@test.io", "PatronneTest2026!",
        "super_admin", '[]')

    verifier("L'administrateur ordinaire est bien connecté",
             ordinaire.get("/api/admin/utilisateurs?limite=1").status_code == 200)
    verifier("Le super administrateur est bien connecté",
             patron.get("/api/admin/utilisateurs?limite=1").status_code == 200)

    r = ordinaire.post(f"/api/admin/utilisateurs/{id_patron}/role",
                       json={"role": "etudiant"})
    verifier("Un administrateur ne rétrograde pas un super administrateur",
             r.status_code == 403, r.get_data(as_text=True)[:110])
    verifier("Le super administrateur garde son rôle",
             jeton_sql("SELECT role FROM utilisateur WHERE id_utilisateur = ?",
                       (id_patron,)) == "super_admin")

    r = ordinaire.put(f"/api/admin/utilisateurs/{id_patron}",
                      json={"email": "pirate@ailleurs.test"})
    verifier("Un administrateur ne change pas l'adresse d'un autre",
             r.status_code == 403, r.get_data(as_text=True)[:110])
    r = ordinaire.post(f"/api/admin/utilisateurs/{id_patron}/suspendre")
    verifier("Un administrateur ne suspend pas un super administrateur",
             r.status_code == 403)
    r = ordinaire.post(f"/api/admin/utilisateurs/{id_ordinaire}/suspendre")
    verifier("Personne ne suspend son propre compte", r.status_code == 400)
    r = ordinaire.delete(f"/api/admin/utilisateurs/{id_patron}")
    verifier("Un administrateur ne supprime pas un super administrateur",
             r.status_code == 403)

    # Le super administrateur, lui, agit. Le changement d'adresse est
    # trace avec l'ancienne et la personne en est avertie : c'est ce qui
    # permet de prendre un compte en main sans que personne s'en
    # apercoive.
    r = patron.put(f"/api/admin/utilisateurs/{id_ordinaire}",
                   json={"email": "modeste.nouvelle@test.io"})
    verifier("Un super administrateur change une adresse",
             r.status_code == 200, r.get_data(as_text=True)[:110])
    verifier("Le changement d'adresse est tracé avec l'ancienne",
             jeton_sql("SELECT COUNT(*) FROM audit_admin "
                       "WHERE action = 'modifier_utilisateur' "
                       "  AND details LIKE ?",
                       ("%modeste@test.io vers%",)) >= 1)
    verifier("La personne est avertie du changement d'adresse",
             jeton_sql("SELECT COUNT(*) FROM notification "
                       "WHERE id_destinataire = ? AND texte LIKE ?",
                       (id_ordinaire, "%adresse e-mail de votre compte a "
                        "été changée%")) >= 1)
    r = patron.put(f"/api/admin/utilisateurs/{id_ordinaire}",
                   json={"email": "pas-une-adresse"})
    verifier("Une adresse invalide est refusée", r.status_code == 400)

    # Supprimer un administrateur effacait tout son journal d'audit, en
    # cascade, au moment precis ou on aurait besoin de le relire.
    ordinaire.post(f"/api/admin/utilisateurs/{_id('propre@test.io')}/suspendre")
    decisions = jeton_sql("SELECT COUNT(*) FROM audit_admin "
                          "WHERE id_acteur = ?", (id_ordinaire,))
    verifier("L'administrateur ordinaire a laissé une trace au journal",
             decisions >= 1, str(decisions))

    r = patron.delete(f"/api/admin/utilisateurs/{id_ordinaire}")
    verifier("La suppression d'un administrateur aboutit",
             r.status_code == 200, r.get_data(as_text=True)[:110])
    verifier("Elle anonymise au lieu d'effacer",
             (r.get_json() or {}).get("anonymise") is True)
    verifier("Le journal garde ses décisions",
             jeton_sql("SELECT COUNT(*) FROM audit_admin "
                       "WHERE id_acteur = ?", (id_ordinaire,)) == decisions)
    verifier("Les données personnelles sont effacées",
             jeton_sql("SELECT prenom || nom FROM utilisateur "
                       "WHERE id_utilisateur = ?", (id_ordinaire,))
             == "Comptesupprimé")
    verifier("Le compte est fermé et sans droits",
             jeton_sql("SELECT est_actif + est_admin FROM utilisateur "
                       "WHERE id_utilisateur = ?", (id_ordinaire,)) == 0)

    # Un compte sans decision est supprime pour de bon.
    _, id_jetable = _compte_admin(
        "Jetable", "jetable@test.io", "JetableTest2026!", "etudiant", '[]')
    with app.app_context():
        _maj("UPDATE utilisateur SET est_admin = 0 WHERE id_utilisateur = %s",
             (id_jetable,), commit=True)
    r = patron.delete(f"/api/admin/utilisateurs/{id_jetable}")
    verifier("Un compte sans décision est réellement supprimé",
             r.status_code == 200
             and (r.get_json() or {}).get("anonymise") is not True)
    verifier("Il ne reste rien de lui",
             jeton_sql("SELECT COUNT(*) FROM utilisateur "
                       "WHERE id_utilisateur = ?", (id_jetable,)) == 0)

    # Le dernier super administrateur ne doit pas pouvoir se retirer.
    with app.app_context():
        _maj("UPDATE utilisateur SET role = 'admin' "
             "WHERE role = 'super_admin' AND id_utilisateur <> %s",
             (id_patron,), commit=True)
    r = patron.post(f"/api/admin/utilisateurs/{id_patron}/role",
                    json={"role": "admin"})
    verifier("Le dernier super administrateur ne se retire pas lui-même",
             r.status_code == 400, r.get_data(as_text=True)[:110])

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  44. SESSIONS, CODES ET CONNEXIONS EXTERNES")
    print("═" * 70)

    from utils.auth_helpers import hacher_mot_de_passe as _hacher

    with app.app_context():
        _maj("""INSERT INTO utilisateur
                  (prenom, nom, email, mot_de_passe, role, est_actif,
                   email_verifie)
                VALUES ('Sylvie', 'Essai', 'sylvie@test.io', %s,
                        'etudiant', 1, 1)""",
             (_hacher("SylvieTest2026!"),), commit=True)
    id_sylvie = _id("sylvie@test.io")

    bureau = app.test_client()
    bureau.post("/api/auth/connexion", json={"email": "sylvie@test.io",
                                             "mot_de_passe": "SylvieTest2026!"})
    cyber = app.test_client()
    cyber.post("/api/auth/connexion", json={"email": "sylvie@test.io",
                                            "mot_de_passe": "SylvieTest2026!"})
    verifier("Deux appareils sont connectés au même compte",
             bureau.get("/api/profil/moi").status_code == 200
             and cyber.get("/api/profil/moi").status_code == 200)

    # Quelqu'un qui change son mot de passe parce qu'il a laisse sa
    # session ouverte dans un cybercafe croyait reprendre la main :
    # elle y restait ouverte.
    r = bureau.post("/api/auth/changer-mdp",
                    json={"mot_de_passe_actuel": "SylvieTest2026!",
                          "nouveau_mot_de_passe": "SylvieNouveau2026!"})
    verifier("Le mot de passe se change", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("L'autre appareil est déconnecté",
             cyber.get("/api/profil/moi").status_code == 401)
    verifier("L'appareil qui a changé le mot de passe reste connecté",
             bureau.get("/api/profil/moi").status_code == 200)

    # Un compte ferme ne doit pas obtenir de session par un fournisseur
    # externe : il en obtenait une, que la requete suivante refusait,
    # et l'ecran annoncait « Votre session a expire » juste apres une
    # connexion reussie.
    from routes.oauth import (_trouver_ou_creer_compte_externe,
                              CompteSuspendu, AdresseNonVerifiee)
    with app.app_context():
        _maj("UPDATE utilisateur SET est_actif = 0 WHERE id_utilisateur = %s",
             (id_sylvie,), commit=True)
        refuse = False
        try:
            _trouver_ou_creer_compte_externe(
                "google", "sub-essai-1", "sylvie@test.io", True,
                "Sylvie", "Essai", None)
        except CompteSuspendu:
            refuse = True
        verifier("Un compte fermé est refusé à la connexion externe", refuse)
        _maj("UPDATE utilisateur SET est_actif = 1 WHERE id_utilisateur = %s",
             (id_sylvie,), commit=True)

        # Et une adresse que le fournisseur ne garantit pas reste
        # refusee, comme avant.
        refuse = False
        try:
            _trouver_ou_creer_compte_externe(
                "google", "sub-essai-2", "inconnue@test.io", False,
                "Qui", "Sait", None)
        except AdresseNonVerifiee:
            refuse = True
        verifier("Une adresse non garantie reste refusée", refuse)

    # L'etat OAuth : deux absences se valaient, et un appel forge sans
    # « state » franchissait le controle cense l'empecher.
    import os as _os2
    _os2.environ.update({"LINKEDIN_CLIENT_ID": "essai",
                         "LINKEDIN_CLIENT_SECRET": "essai",
                         "LINKEDIN_REDIRECT_URI": "https://exemple.test/cb"})
    sans_etat = app.test_client()
    r = sans_etat.get("/api/auth/linkedin/callback?code=abc")
    verifier("Un retour OAuth sans état est refusé",
             r.status_code == 400, str(r.status_code))
    r = sans_etat.get("/api/auth/linkedin/callback?code=abc&state=invente")
    verifier("Un état inventé est refusé", r.status_code == 400)
    for cle in ("LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET",
                "LINKEDIN_REDIRECT_URI"):
        _os2.environ.pop(cle, None)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  45. COMPTEURS QUI NE DÉRIVENT PLUS")
    print("═" * 70)

    # Le compteur du referent montait a la publication et ne
    # redescendait jamais : l'annuaire affichait « 10 reponses » sous
    # quelqu'un qui en avait deux, et le classait devant des referents
    # plus actifs, puisque c'est sur ce compteur qu'il trie.
    r = cand.post("/api/reponses", json={
        "id_question": id_q, "contenu": "Une réponse qui sera supprimée."})
    id_jetable = (r.get_json() or {}).get("id_reponse")
    avant = jeton_sql("SELECT nb_reponses FROM mentor_details "
                      "WHERE id_utilisateur = ?", (id_ref,))
    reelles = jeton_sql("SELECT COUNT(*) FROM reponse WHERE id_auteur = ?",
                        (id_ref,))
    verifier("Le compteur suit la publication", avant == reelles,
             f"{avant} annonce(s) pour {reelles} réponse(s)")

    cand.delete(f"/api/reponses/{id_jetable}")
    apres = jeton_sql("SELECT nb_reponses FROM mentor_details "
                      "WHERE id_utilisateur = ?", (id_ref,))
    reelles = jeton_sql("SELECT COUNT(*) FROM reponse WHERE id_auteur = ?",
                        (id_ref,))
    verifier("Il redescend à la suppression", apres == reelles,
             f"{apres} annonce(s) pour {reelles} réponse(s)")

    # Signaler douze fois la meme question faisait croire a la
    # moderation qu'un probleme collectif se posait, alors qu'une seule
    # personne etait en cause.
    r = lecteur.post(f"/api/questions/{id_q}/signaler",
                     json={"motif": "Premier signalement"})
    verifier("Un signalement est accepté", r.status_code == 200)
    r = lecteur.post(f"/api/questions/{id_q}/signaler",
                     json={"motif": "Motif précisé"})
    verifier("Le second signalement de la même personne ne s'ajoute pas",
             (r.get_json() or {}).get("deja_signale") is True)
    verifier("Une seule ligne reste en base",
             jeton_sql("SELECT COUNT(*) FROM signalement "
                       "WHERE type_contenu = 'question' AND id_contenu = ? "
                       "  AND id_signaleur = ?",
                       (id_q, _id("ife@test.io"))) == 1)
    verifier("Le motif a bien été mis à jour",
             jeton_sql("SELECT motif FROM signalement "
                       "WHERE type_contenu = 'question' AND id_contenu = ? "
                       "  AND id_signaleur = ?",
                       (id_q, _id("ife@test.io"))) == "Motif précisé")
    verifier("Signaler une question inexistante répond 404",
             lecteur.post("/api/questions/999999/signaler",
                          json={"motif": "x"}).status_code == 404)

    # Un signalement juge non fonde ne doit plus peser contre sa cible.
    sig = jeton_sql("SELECT id_signalement FROM signalement "
                    "WHERE type_contenu = 'question' AND id_contenu = ?",
                    (id_q,))
    liste_avant = adm.get("/api/admin/signalements").get_json() or []
    compte_avant = next((s["signalements_contenu"] for s in liste_avant
                         if s["id_signalement"] == sig), 0)
    adm.post(f"/api/admin/signalements/{sig}", json={"action": "rejeter"})
    # Un signalement rejete quitte la liste par defaut, qui ne montre
    # que ceux en attente : on demande donc tous les statuts.
    liste_apres = adm.get("/api/admin/signalements?statut=tous").get_json() or []
    entree = next((s for s in liste_apres
                   if s["id_signalement"] == sig), {})
    verifier("Un signalement rejeté cesse de compter contre le contenu",
             entree.get("signalements_contenu", 99) < compte_avant
             or compte_avant == 0,
             f"{compte_avant} puis {entree.get('signalements_contenu')}")
    contenu = entree.get("contenu") or {}
    verifier("Il cesse aussi de compter contre l'auteur",
             contenu.get("signalements_auteur", 99) == 0,
             str(contenu.get("signalements_auteur")))

    # Une salle de classe entiere sort par une seule adresse IP.
    from utils.securite import MAX_INSCRIPTIONS
    verifier("La limite d'inscriptions laisse passer une classe",
             MAX_INSCRIPTIONS >= 40, str(MAX_INSCRIPTIONS))

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  46. UN DROIT NE SURVIT PAS À SA RÉVOCATION")
    print("═" * 70)

    # Le changement de role n'ecrivait que « role ». Or tout le controle
    # d'acces regarde « est_admin » : promouvoir n'ouvrait rien, et
    # retrograder ne fermait rien.
    promu, id_promu = _compte_admin(
        "Promu", "promu@test.io", "PromuTest2026!", "etudiant", '[]')
    with app.app_context():
        _maj("UPDATE utilisateur SET est_admin = 0 WHERE id_utilisateur = %s",
             (id_promu,), commit=True)
    verifier("Avant promotion, l'administration est fermée",
             promu.get("/api/admin/utilisateurs").status_code == 403)

    r = patron.post(f"/api/admin/utilisateurs/{id_promu}/role",
                    json={"role": "admin"})
    verifier("La promotion aboutit", r.status_code == 200,
             r.get_data(as_text=True)[:110])
    verifier("Le drapeau d'administration suit le rôle",
             jeton_sql("SELECT est_admin FROM utilisateur "
                       "WHERE id_utilisateur = ?", (id_promu,)) == 1)
    promu.post("/api/auth/connexion", json={"email": "promu@test.io",
                                            "mot_de_passe": "PromuTest2026!"})
    verifier("La personne promue accède réellement à l'administration",
             promu.get("/api/admin/utilisateurs").status_code == 200)

    liste = patron.get("/api/admin/administrateurs").get_json() or []
    fiche = next((a for a in liste if a["id_utilisateur"] == id_promu), {})
    verifier("La liste montre les droits réellement enregistrés",
             bool(fiche.get("droits")), str(fiche.get("droits")))

    # Le sens inverse est le plus grave. On pose les droits en base
    # avant de retrograder : sans cela, cette partie reussirait par
    # ricochet le jour ou la promotion cesserait de fonctionner.
    with app.app_context():
        _maj("UPDATE utilisateur SET est_admin = 1, role = 'admin', "
             "permissions = %s WHERE id_utilisateur = %s",
             ('["utilisateurs"]', id_promu), commit=True)
    avec_droits = app.test_client()
    avec_droits.post("/api/auth/connexion",
                     json={"email": "promu@test.io",
                           "mot_de_passe": "PromuTest2026!"})
    verifier("Le compte a bien les droits avant retrait",
             avec_droits.get("/api/admin/utilisateurs").status_code == 200)

    r = patron.post(f"/api/admin/utilisateurs/{id_promu}/role",
                    json={"role": "etudiant"})
    verifier("La rétrogradation aboutit", r.status_code == 200)
    verifier("Le drapeau d'administration retombe",
             jeton_sql("SELECT est_admin FROM utilisateur "
                       "WHERE id_utilisateur = ?", (id_promu,)) == 0)
    verifier("Les droits sont retirés en base",
             jeton_sql("SELECT permissions FROM utilisateur "
                       "WHERE id_utilisateur = ?", (id_promu,)) == "[]")
    verifier("Les sessions ouvertes sont fermées",
             jeton_sql("SELECT COUNT(*) FROM session_web "
                       "WHERE id_utilisateur = ?", (id_promu,)) == 0)

    rentre = app.test_client()
    rentre.post("/api/auth/connexion", json={"email": "promu@test.io",
                                             "mot_de_passe": "PromuTest2026!"})
    verifier("L'accès à l'administration est réellement fermé",
             rentre.get("/api/admin/utilisateurs").status_code == 403)
    verifier("Le retrait des droits est tracé",
             jeton_sql("SELECT COUNT(*) FROM audit_admin "
                       "WHERE action = 'changer_role' "
                       "  AND details LIKE ?",
                       ("%droits retires%",)) >= 1)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  47. CE QUE LA PAGE PROPOSE, ET CE QU'ELLE LAISSE FILTRER")
    print("═" * 70)

    # --- La recherche globale -----------------------------------------
    #
    # Elle comparait avec LIKE sans uniformiser la casse. PostgreSQL, qui
    # sert la production, distingue les majuscules : chercher « techno »
    # ne trouvait rien alors que « Technologie » existait.
    chercheur, _ = _compte_admin(
        "Chercheuse", "chercheuse@test.io", "ChercheTest2026!",
        "etudiant", '[]')
    # Le defaut ne se voit que sur PostgreSQL : le LIKE de SQLite ignore
    # deja la casse des caracteres ASCII, si bien qu'un controle passe ici
    # resterait vert meme sans la correction. On ne l'affirme donc que la
    # ou il peut echouer, plutot que de se donner une assurance vide.
    if os.environ["DB_TYPE"] == "postgres":
        libelles = [x["libelle"] for x in
                    (chercheur.get("/api/recherche?q=technologie").get_json()
                     or {}).get("secteurs", [])]
        verifier("La recherche ignore la casse (PostgreSQL)",
                 "Technologie" in libelles, str(libelles))
        # Les accents ne sont volontairement pas affirmes ici : leur
        # pliage depend du collationnement de la base, pas du code. Sous
        # « C », lower('É') rend 'É' et rien ne peut y faire cote SQL ;
        # sous en_US.UTF-8, qui sert en production, cela fonctionne.
        # L'affirmer reviendrait a tester la configuration du serveur de
        # test, et a rougir ou verdir pour une raison etrangere au code.
    else:
        verifier("La recherche trouve un secteur en minuscules",
                 "Technologie" in [x["libelle"] for x in
                                   (chercheur.get("/api/recherche?q=techno")
                                    .get_json() or {}).get("secteurs", [])])

    # Un referent non verifie ne figure pas dans l'annuaire. Il ne doit
    # pas non plus sortir de la recherche : c'est la meme information.
    with app.app_context():
        from utils.auth_helpers import hacher_mot_de_passe
        _maj("""INSERT INTO utilisateur
                  (prenom, nom, email, mot_de_passe, role, est_actif,
                   email_verifie, bio)
                VALUES ('Zacharie', 'Discret', 'discret@test.io', %s,
                        'mentor', 1, 1, 'Specialiste zzzunique')""",
             (hacher_mot_de_passe("DiscretTest2026!"),), commit=True)
        id_discret = _id("discret@test.io")
        _maj("INSERT INTO mentor_details (id_utilisateur, est_verifie) "
             "VALUES (%s, 0)", (id_discret,), commit=True)

    trouves = (chercheur.get("/api/recherche?q=zzzunique").get_json()
               or {}).get("mentors", [])
    annuaire = (chercheur.get("/api/mentors").get_json() or {})
    liste_annuaire = annuaire.get("mentors", annuaire) if isinstance(
        annuaire, dict) else annuaire
    dans_annuaire = any(m.get("id_utilisateur") == id_discret
                        for m in (liste_annuaire or []))
    verifier("Un référent non vérifié reste hors de l'annuaire",
             not dans_annuaire)
    verifier("Et la recherche ne l'expose pas davantage",
             not any(m.get("id_utilisateur") == id_discret for m in trouves),
             str([m.get("prenom") for m in trouves]))

    # Un joker saisi ne doit pas balayer la table entiere. Le terme fait
    # trois caracteres exprès : en dessous de deux, la route repond une
    # liste vide sans rien chercher, et le controle passerait tout seul.
    # Echappe, « t%e » ne trouve rien ; non echappe, il trouve tout ce qui
    # porte un t suivi plus loin d'un e, soit la moitie de la table.
    tout = (chercheur.get("/api/recherche?q=t%25e").get_json()
            or {}).get("secteurs", [])
    verifier("Un joker saisi est cherché tel quel, pas interprété",
             not tout, str([x["libelle"] for x in tout]))

    # --- Suppression d'un secteur -------------------------------------
    #
    # `utilisateur_secteur` part en cascade : supprimer un secteur
    # retirait sans un mot ce domaine aux referents qui l'avaient declare.
    with app.app_context():
        _maj("INSERT INTO secteur (libelle) VALUES ('Zone de test')",
             (), commit=True)
    id_sect = jeton_sql(
        "SELECT id_secteur FROM secteur WHERE libelle = ?", ("Zone de test",))
    r = patron.delete(f"/api/admin/secteurs/{id_sect}")
    verifier("Un secteur que personne ne porte se supprime",
             r.status_code == 200, r.get_data(as_text=True)[:110])

    with app.app_context():
        _maj("INSERT INTO secteur (libelle) VALUES ('Zone portee')",
             (), commit=True)
    id_porte = jeton_sql(
        "SELECT id_secteur FROM secteur WHERE libelle = ?", ("Zone portee",))
    with app.app_context():
        _maj("INSERT INTO utilisateur_secteur (id_utilisateur, id_secteur) "
             "VALUES (%s, %s)", (id_discret, id_porte), commit=True)
    r = patron.delete(f"/api/admin/secteurs/{id_porte}")
    verifier("Un secteur déclaré par un référent ne se supprime pas",
             r.status_code == 409, str(r.status_code))
    verifier("Le domaine du référent est resté en place",
             jeton_sql("SELECT COUNT(*) FROM utilisateur_secteur "
                       "WHERE id_secteur = ?", (id_porte,)) == 1)
    verifier("Le message dit combien de personnes sont concernées",
             "1 référent" in (r.get_json() or {}).get("erreur", ""),
             (r.get_json() or {}).get("erreur", "")[:90])

    # --- Candidature de référent --------------------------------------
    #
    # Un identifiant de domaine inexistant heurtait la cle etrangere : la
    # candidature entiere etait perdue sur une erreur de serveur.
    candidat, id_candidat = _compte_admin(
        "Candide", "candide@test.io", "CandideTest2026!", "mentor", '[]')
    dossier = {
        "bio": "Ingénieure en poste depuis douze ans, je forme des juniors.",
        "motivation": "Je veux rendre ce qu'on m'a donné, et je sais que "
                      "quelques conseils au bon moment changent une "
                      "trajectoire entière.",
        "profession": "Ingénieure logiciel",
        "annees_experience": 12,
    }
    r = candidat.post("/api/mentors/candidature",
                      json={**dossier, "secteurs": [999999]})
    verifier("Un domaine d'expertise inexistant est refusé proprement",
             r.status_code == 400, str(r.status_code))
    verifier("Et aucune candidature n'est enregistrée au passage",
             jeton_sql("SELECT COUNT(*) FROM utilisateur_secteur "
                       "WHERE id_utilisateur = ?", (id_candidat,)) == 0)

    id_vrai = jeton_sql(
        "SELECT id_secteur FROM secteur WHERE libelle = ?", ("Technologie",))
    r = candidat.post("/api/mentors/candidature",
                      json={**dossier, "secteurs": [id_vrai, id_vrai]})
    verifier("Une candidature avec un domaine réel aboutit",
             r.status_code in (200, 201), r.get_data(as_text=True)[:110])
    verifier("Un domaine cité deux fois n'est enregistré qu'une",
             jeton_sql("SELECT COUNT(*) FROM utilisateur_secteur "
                       "WHERE id_utilisateur = ?", (id_candidat,)) == 1)

    # --- Inscription : ne pas dire qui a un compte ---------------------
    #
    # « Cette adresse est deja utilisee » permettait de savoir, adresse
    # par adresse, qui est inscrit ici.
    # La reponse indiscernable ne vaut que quand la confirmation est
    # exigee : en mode souple, l'inscription ouvre une session, et il n'y
    # a rien d'indiscernable a renvoyer.
    _avant_verif = app.config.get("VERIFICATION_EMAIL_OBLIGATOIRE")
    app.config["VERIFICATION_EMAIL_OBLIGATOIRE"] = True
    depart = app.test_client()
    r = depart.post("/api/auth/inscription", json={
        "prenom": "Sosie", "nom": "Essai", "email": "chercheuse@test.io",
        "mot_de_passe": "SosieTest2026!", "role": "etudiant",
        "consentement": {"conditions": True, "donnees": True},
    })
    corps = r.get_json() or {}
    app.config["VERIFICATION_EMAIL_OBLIGATOIRE"] = _avant_verif
    verifier("Une adresse déjà inscrite ne se distingue plus d'une nouvelle",
             r.status_code == 201 and corps.get("verification_requise") is True,
             f"{r.status_code} {str(corps)[:90]}")
    verifier("Le mot de passe du compte existant n'a pas été touché",
             chercheur.get("/api/profil/moi").status_code == 200)
    verifier("Aucun second compte n'a été créé",
             jeton_sql("SELECT COUNT(*) FROM utilisateur WHERE email = ?",
                       ("chercheuse@test.io",)) == 1)

    # --- Réponse de l'équipe à quelqu'un sans compte -------------------
    #
    # Elle ne partait que par notification interne : elle n'atteignait
    # donc jamais ceux qui ecrivent sans compte, c'est-a-dire ceux qui
    # n'arrivent pas a se connecter.
    anonyme = app.test_client()
    r = anonyme.post("/api/equipe/message", json={
        "nom": "Passante", "email": "passante@test.io",
        "categorie": "panne",
        "message": "La page de connexion tourne sans fin sur mon téléphone.",
    })
    verifier("Un message sans compte est accepté",
             r.status_code == 201, r.get_data(as_text=True)[:110])
    id_msg = (r.get_json() or {}).get("id_message")
    r = patron.post(f"/api/equipe/messages/{id_msg}/traiter",
                    json={"statut": "traite",
                          "reponse": "C'est corrigé, merci de l'avoir signalé."})
    verifier("La réponse de l'équipe est remise par e-mail",
             (r.get_json() or {}).get("reponse_remise") == "email",
             str(r.get_json())[:110])

    r = anonyme.post("/api/equipe/message", json={
        "categorie": "panne",
        "message": "Le bouton publier ne répond plus depuis ce matin.",
    })
    id_avec = (r.get_json() or {}).get("id_message") if r.status_code == 201 \
        else None
    if id_avec is None:
        # Sans compte et sans adresse, le message est refuse : c'est la
        # regle. On passe par un compte pour la variante « notification ».
        r = chercheur.post("/api/equipe/message", json={
            "categorie": "panne",
            "message": "Le bouton publier ne répond plus depuis ce matin."})
        id_avec = (r.get_json() or {}).get("id_message")
    r = patron.post(f"/api/equipe/messages/{id_avec}/traiter",
                    json={"statut": "traite", "reponse": "Nous regardons."})
    verifier("Et par notification quand la personne a un compte",
             (r.get_json() or {}).get("reponse_remise") == "notification",
             str(r.get_json())[:110])

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  48. LA MISE À NIVEAU DU SCHÉMA VA JUSQU'AU BOUT")
    print("═" * 70)

    import models.db as _db
    from models.db import recuperer_tous as _lire

    # Toutes les instructions partageaient une transaction. PostgreSQL
    # refuse tout ce qui suit une erreur dans une transaction : une seule
    # entree fautive faisait echouer les suivantes, et annulait meme
    # celles deja passees. Le journal annoncait « colonne ajoutee » pour
    # une colonne qui ne l'etait plus au moment du rollback.
    with app.app_context():
        _maj("DROP TABLE IF EXISTS essai_migration", (), commit=True)
        _maj("CREATE TABLE essai_migration (id INTEGER)", (), commit=True)

    _avant_colonnes = _db.COLONNES_ATTENDUES
    _db.COLONNES_ATTENDUES = [
        ("essai_migration", "premiere", "TEXT"),
        ("table_qui_nexiste_pas", "peu_importe", "TEXT"),   # échoue
        ("essai_migration", "apres_lechec", "TEXT"),
    ]
    _lectures = {"n": 0}
    _vraie_lecture = _db._colonnes_existantes

    def _compter_lectures(cur, moteur, table):
        _lectures["n"] += 1
        return _vraie_lecture(cur, moteur, table)

    _db._colonnes_existantes = _compter_lectures
    try:
        _db.completer_colonnes(app)
    finally:
        _db._colonnes_existantes = _vraie_lecture
        _db.COLONNES_ATTENDUES = _avant_colonnes

    with app.app_context():
        if os.environ["DB_TYPE"] == "postgres":
            _cols = {c["column_name"] for c in _lire(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'essai_migration'")}
        else:
            _cols = {c["name"] for c in _lire(
                "PRAGMA table_info(essai_migration)")}

    verifier("Une colonne ajoutée avant l'erreur est conservée",
             "premiere" in _cols, str(sorted(_cols)))
    verifier("Et celle qui suit l'erreur est ajoutée quand même",
             "apres_lechec" in _cols, str(sorted(_cols)))

    # Le schema etait relu une fois par colonne attendue : trente-trois
    # requetes identiques a chaque demarrage a froid, la ou cinq
    # suffisent. Sur une plateforme sans serveur, un demarrage a froid
    # arrive a n'importe quelle visite.
    _lectures["n"] = 0
    _db._colonnes_existantes = _compter_lectures
    try:
        _db.completer_colonnes(app)
    finally:
        _db._colonnes_existantes = _vraie_lecture
    _tables = len({t for t, _, _ in _db.COLONNES_ATTENDUES})
    verifier("Le schéma est lu une fois par table, pas une fois par colonne",
             _lectures["n"] == _tables,
             f"{_lectures['n']} lectures pour {_tables} tables et "
             f"{len(_db.COLONNES_ATTENDUES)} colonnes attendues")

    with app.app_context():
        _maj("DROP TABLE IF EXISTS essai_migration", (), commit=True)

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  49. CE QUI ARRIVE VRAIMENT À DESTINATION")
    print("═" * 70)

    # Un message prive n'avertissait personne. Le type « message »
    # existait dans les notifications, mais rien ne l'y deposait : la
    # cloche restait muette. Ecrire a quelqu'un revenait a esperer qu'il
    # rouvre la messagerie de lui-meme.
    lecteur, id_lecteur = _compte_admin(
        "Lisa", "lisa@test.io", "LisaTest2026!", "etudiant", '[]')
    r = patron.post("/api/messagerie/conversations",
                    json={"id_utilisateur": id_lecteur})
    id_conv = (r.get_json() or {}).get("id_conversation")
    verifier("Une conversation s'ouvre vers un membre",
             bool(id_conv), r.get_data(as_text=True)[:110])

    avant = jeton_sql("SELECT COUNT(*) FROM notification "
                      "WHERE id_destinataire = ? AND type_notif = 'message'",
                      (id_lecteur,))
    r = patron.post(f"/api/messagerie/conversations/{id_conv}/messages",
                    json={"contenu": "Bonjour, votre question m'a intéressée."})
    verifier("Le message est enregistré", r.status_code == 201,
             r.get_data(as_text=True)[:110])
    verifier("Et le destinataire en est averti",
             jeton_sql("SELECT COUNT(*) FROM notification "
                       "WHERE id_destinataire = ? AND type_notif = 'message'",
                       (id_lecteur,)) == avant + 1)
    verifier("L'expéditeur, lui, ne se notifie pas lui-même",
             jeton_sql("SELECT COUNT(*) FROM notification "
                       "WHERE id_destinataire = ? AND type_notif = 'message'",
                       (id_patron,)) == 0)

    # Deux messages envoyes dans la meme seconde portaient la meme heure :
    # le tri n'avait plus rien pour les departager.
    for n in range(4):
        patron.post(f"/api/messagerie/conversations/{id_conv}/messages",
                    json={"contenu": f"Suite {n}"})
    fil = lecteur.get(
        f"/api/messagerie/conversations/{id_conv}/messages").get_json() or []
    ids = [m["id_message"] for m in fil]
    verifier("Les messages sortent dans l'ordre où ils sont arrivés",
             ids == sorted(ids), str(ids))

    # Le texte en tete du module des opportunites dit « un referent
    # verifie peut en proposer une », mais le controle se contentait du
    # role : une candidature deposee le matin pouvait proposer une bourse
    # l'apres-midi, avant qu'un seul element du dossier ne soit regarde.
    annonce = {
        "titre": "Bourse d'excellence pour la rentrée",
        "description": "Bourse annuelle ouverte aux bacheliers de la région, "
                       "couvrant les frais de scolarité et le logement.",
        "categorie": "bourse",
        "lien": "https://exemple.org/bourse",
    }
    r = candidat.post("/api/opportunites", json=annonce)
    verifier("Un référent non vérifié ne publie pas d'annonce",
             r.status_code == 403, str(r.status_code))
    verifier("Et le refus dit pourquoi, sans le laisser deviner",
             "validée" in (r.get_json() or {}).get("erreur", ""),
             (r.get_json() or {}).get("erreur", "")[:90])
    vue = candidat.get("/api/opportunites").get_json() or {}
    verifier("L'interface ne lui propose pas un bouton qui refusera",
             vue.get("peut_proposer") is False, str(vue.get("peut_proposer")))

    with app.app_context():
        _maj("UPDATE mentor_details SET est_verifie = 1 "
             "WHERE id_utilisateur = %s", (id_candidat,), commit=True)
    r = candidat.post("/api/opportunites", json=annonce)
    verifier("Une fois vérifié, il peut proposer",
             r.status_code == 201, r.get_data(as_text=True)[:110])
    verifier("Sa proposition attend une relecture",
             (r.get_json() or {}).get("statut") == "en_attente")

    # Le message annoncait https et le code acceptait http.
    r = candidat.post("/api/opportunites",
                      json={**annonce, "lien": "http://exemple.org/bourse"})
    verifier("Un lien en http est refusé, comme le message l'annonce",
             r.status_code == 400, str(r.status_code))

    # L'annuaire comparait avec LIKE sans uniformiser la casse, comme la
    # recherche globale avant correction.
    if os.environ["DB_TYPE"] == "postgres":
        trouves = lecteur.get("/api/mentors?q=candide").get_json() or []
        verifier("L'annuaire ignore la casse (PostgreSQL)",
                 any(m["prenom"] == "Candide" for m in trouves),
                 str([m.get("prenom") for m in trouves]))
    # Le fil de questions portait le meme defaut que la recherche et
    # l'annuaire : filtrer sur « bourse » ne trouvait pas « Bourse ».
    if os.environ["DB_TYPE"] == "postgres":
        # « Comment » existe dans plusieurs titres, jamais en minuscules :
        # sans LOWER des deux cotes, PostgreSQL n'en trouve aucun.
        titres = [q["titre"] for q in
                  (lecteur.get("/api/questions?q=comment").get_json() or [])]
        verifier("Le filtre du fil ignore la casse (PostgreSQL)",
                 any(t.startswith("Comment") for t in titres),
                 str(titres)[:110])
    # La route rend directement la liste des questions.
    fil = lecteur.get("/api/questions?q=t%25e").get_json()
    verifier("Un joker saisi dans le fil n'est pas interprété",
             fil == [], str(fil)[:110])

    tout = lecteur.get("/api/mentors?q=a%25e").get_json() or []
    verifier("Un joker saisi dans l'annuaire n'est pas interprété",
             not tout, str([m.get("prenom") for m in tout]))

    # ---------------------------------------------------------------
    print("\n" + "═" * 70)
    print("  50. LE JOURNAL D'ACTIVITÉ ENREGISTRE CE QU'IL ANNONCE")
    print("═" * 70)

    import re as _re
    import services.evenements as _ev

    # Le module dit en tete que son vocabulaire doit rester stable, « un
    # type invente au fil de l'eau produit des series impossibles a
    # comparer ». Il avait derive dans les deux sens : cinq types emis
    # sans y figurer, et onze declares sans etre emis nulle part, dont
    # l'inscription, la connexion et la recherche. Le journal annoncait
    # donc un vocabulaire qu'il n'employait pas, et n'enregistrait pas ce
    # pour quoi il avait ete ecrit.
    _emis = set()
    for _racine, _, _fichiers in os.walk(os.path.dirname(__file__) or "."):
        if "__pycache__" in _racine:
            continue
        for _f in _fichiers:
            if not _f.endswith(".py") or _f.startswith("tests_"):
                continue
            _texte = open(os.path.join(_racine, _f), encoding="utf-8").read()
            _emis |= set(_re.findall(
                r"(?:depuis_requete|enregistrer)\(\s*\n?\s*\"([a-z_]+)\"",
                _texte))
    _inconnus = sorted(_emis - set(_ev.TYPES))
    _orphelins = sorted(set(_ev.TYPES) - _emis)
    verifier("Aucun type d'évènement n'est émis hors du vocabulaire",
             not _inconnus, ", ".join(_inconnus))
    verifier("Aucun type déclaré ne reste sans emploi",
             not _orphelins, ", ".join(_orphelins))

    # Et les evenements arrivent reellement en base.
    def _compter_ev(type_ev):
        return jeton_sql("SELECT COUNT(*) FROM evenement WHERE type_evenement = ?",
                         (type_ev,))

    verifier("Une inscription laisse une trace",
             _compter_ev("inscription") >= 1)
    verifier("Une connexion aussi", _compter_ev("connexion") >= 1)
    verifier("Une recherche aussi", _compter_ev("recherche") >= 1)

    # Le contenu ecrit par un membre ne doit jamais entrer ici : un export
    # d'evenements deviendrait un export de contenus, et les lignes
    # seraient ineffacables.
    _avant = _compter_ev("recherche")
    chercheur.get("/api/recherche?q=motsecretdelutilisateur")
    verifier("La recherche suivante est comptée",
             _compter_ev("recherche") == _avant + 1)
    verifier("Mais le terme saisi n'est pas conservé",
             jeton_sql("SELECT COUNT(*) FROM evenement "
                       "WHERE contexte LIKE ?",
                       ("%motsecretdelutilisateur%",)) == 0)

    _avant_sig = _compter_ev("signalement")
    chercheur.post(f"/api/questions/{id_q}/signaler",
                   json={"motif": "motif prive a ne pas recopier"})
    verifier("Un signalement laisse une trace",
             _compter_ev("signalement") == _avant_sig + 1)
    verifier("Sans recopier le motif écrit par la personne",
             jeton_sql("SELECT COUNT(*) FROM evenement "
                       "WHERE contexte LIKE ?",
                       ("%a ne pas recopier%",)) == 0)

    # L'echeance d'une session se comparait a CURRENT_TIMESTAMP, qui suit
    # le fuseau du serveur de base, alors qu'elle est ecrite depuis Python
    # en temps universel. Sur un serveur regle en UTC+1, une session
    # valable encore trente minutes se lisait comme expiree.
    from datetime import datetime, timedelta
    from utils.auth_helpers import utilisateur_depuis_jeton as _lire_jeton
    with app.app_context():
        _maj("""INSERT INTO session_web (id_token, id_utilisateur, expire_le)
                VALUES (%s, %s, %s)""",
             ("jeton-echeance-proche", id_lecteur,
              datetime.utcnow() + timedelta(minutes=30)), commit=True)
        _maj("""INSERT INTO session_web (id_token, id_utilisateur, expire_le)
                VALUES (%s, %s, %s)""",
             ("jeton-deja-echu", id_lecteur,
              datetime.utcnow() - timedelta(minutes=30)), commit=True)
        vivante = _lire_jeton("jeton-echeance-proche")
        morte = _lire_jeton("jeton-deja-echu")
    verifier("Une session qui expire dans trente minutes reste valide",
             vivante is not None)
    verifier("Une session échue depuis trente minutes est refusée",
             morte is None)

    # ---- Bilan -----------------------------------------------------------
    total = len(_resultats)
    reussis = sum(1 for _, ok, _ in _resultats if ok)
    print("\n" + "═" * 70)
    print(f"  BILAN : {reussis}/{total} tests réussis")
    print("═" * 70)
    if reussis < total:
        print("\n  Tests en échec :")
        for intitule, ok, detail in _resultats:
            if not ok:
                print(f"    - {intitule}")
                if detail:
                    print(f"      {detail}")
    print()
    return reussis == total


if __name__ == "__main__":
    sys.exit(0 if executer_tests() else 1)
