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


def executer_tests():
    app = creer_application()

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
        "mot_de_passe": "Aminata2026!", "role": "etudiant"})
    verifier("Inscription d'un étudiant", r.status_code == 201,
             f"reçu {r.status_code} : {r.get_data(as_text=True)[:90]}")

    r = etu.post("/api/auth/inscription", json={
        "prenom": "Autre", "nom": "Personne", "email": "aminata@test.io",
        "mot_de_passe": "Autre2026!", "role": "etudiant"})
    verifier("E-mail en double refusé (409)", r.status_code == 409)

    r = etu.post("/api/auth/inscription", json={
        "prenom": "Faible", "nom": "Mdp", "email": "faible@test.io",
        "mot_de_passe": "123", "role": "etudiant"})
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
        "mot_de_passe": "BrefTest2026!", "role": "etudiant"})
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
             and any(m.get("nom") == "TRAORE" for m in annuaire),
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
        "mot_de_passe": "MotDePasse2026!", "role": "etudiant"})

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
        "mot_de_passe": "SansDroits2026!", "role": "etudiant"})
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
        "mot_de_passe": "Compteur2026!", "role": "etudiant"})
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
        "mot_de_passe": "YaoPartant2026!", "role": "etudiant"})

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
        "mot_de_passe": "LienPerdu2026!", "role": "etudiant"})

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
    verifier("Isolation des fenêtres",
             r.headers.get("Cross-Origin-Opener-Policy") == "same-origin")
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
    print("  18. AUTHENTIFICATION EXTERNE (OAuth)")
    print("═" * 70)
    cfg = anon.get("/api/auth/config")
    verifier("Configuration OAuth exposée", cfg.status_code == 200)
    verifier("Google signalé non configuré (503) au lieu d'une erreur 500",
             anon.post("/api/auth/google",
                       json={"credential": "faux"}).status_code == 503)
    verifier("LinkedIn signalé non configuré (503)",
             anon.get("/api/auth/linkedin").status_code == 503)

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
