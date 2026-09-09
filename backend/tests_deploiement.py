"""Vérification de l'application telle que Vercel l'exécutera.

Ce script ne teste pas les fonctionnalités (c'est le rôle de
``tests_integration.py``) : il vérifie que l'application se comporte
correctement dans les conditions particulières d'un hébergement
serverless derrière un reverse proxy HTTPS.

Points contrôlés :
  1. le point d'entrée ``api/index.py`` s'importe et expose bien ``app`` ;
  2. la base PostgreSQL est jointe et le schéma créé automatiquement ;
  3. le cookie de session porte les drapeaux HttpOnly, Secure, SameSite ;
  4. l'adresse IP réelle du visiteur est restituée malgré le proxy
     (sans quoi tous les visiteurs partageraient le compteur
     anti-force-brute) ;
  5. les liens envoyés par e-mail sont en HTTPS et sur le bon domaine ;
  6. la politique de sécurité du contenu autorise Google Identity
     Services, faute de quoi le bouton « Continuer avec Google »
     n'apparaîtrait pas ;
  7. le code source du backend n'est pas servi par l'application.

Utilisation :

    DATABASE_URL=postgresql://... python tests_deploiement.py
"""

import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# L'environnement doit être posé AVANT tout import : config.py lit les
# variables au moment où le module est chargé, exactement comme sur la
# plateforme.
# ---------------------------------------------------------------------

DOMAINE = "lasource-test.vercel.app"

os.environ.setdefault("DATABASE_URL",
                      "postgresql://postgres@127.0.0.1:5433/lasource_deploi")
os.environ.update({
    "VERCEL": "1",
    "VERCEL_ENV": "production",
    "VERCEL_URL": DOMAINE,
    "DB_TYPE": "postgres",
    "SECRET_KEY": "cle-de-test-stable-pour-la-verification-de-deploiement",
    "EMAIL_MODE": "console",
    "VERIFICATION_EMAIL_OBLIGATOIRE": "0",
})
os.environ.pop("URL_PLATEFORME", None)   # doit être déduite de VERCEL_URL

sys.path.insert(0, str(RACINE / "backend"))


def _vider_base():
    """Repart d'une base vierge avant de contrôler.

    Plusieurs vérifications supposent une base neuve : l'absence de
    compte après création du schéma, et une inscription qui aboutit. Un
    second passage sur la même base les faisait échouer, non parce que
    l'application était en cause, mais parce que la trace du passage
    précédent subsistait. Un test qui n'aboutit que sur une base
    préparée à la main finit par être cru sur parole.
    """
    try:
        import psycopg2
    except ImportError:
        return
    try:
        cx = psycopg2.connect(os.environ["DATABASE_URL"])
    except Exception:
        return          # base injoignable : la sonde le signalera
    try:
        cx.autocommit = True
        cur = cx.cursor()
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        tables = [r[0] for r in cur.fetchall()]
        if tables:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        cx.close()


_vider_base()

# En-têtes que Vercel ajoute systématiquement devant la fonction.
ENTETES_PROXY = {
    "X-Forwarded-Proto": "https",
    "X-Forwarded-Host": DOMAINE,
    "X-Forwarded-For": "41.85.160.7",
    "Host": DOMAINE,
}

_total = 0
_reussis = 0


def titre(texte):
    print("\n" + "═" * 70)
    print("  " + texte)
    print("═" * 70)


def verifier(libelle, condition, detail=""):
    global _total, _reussis
    _total += 1
    if condition:
        _reussis += 1
        print(f"  [OK  ] {libelle}")
    else:
        print(f"  [ÉCHEC] {libelle}" + (f"  -> {detail}" if detail else ""))


def cookie_session(reponse):
    """Renvoie l'en-tête Set-Cookie du cookie de session, ou ''."""
    for entete in reponse.headers.getlist("Set-Cookie"):
        if entete.startswith("ls_session="):
            return entete
    return ""


def executer():
    # -----------------------------------------------------------------
    titre("1. POINT D'ENTRÉE SERVERLESS")
    # -----------------------------------------------------------------
    import importlib.util

    chemin = RACINE / "api" / "index.py"
    verifier("Le fichier api/index.py existe", chemin.exists())

    spec = importlib.util.spec_from_file_location("vercel_index", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    application = getattr(module, "app", None)
    verifier("api/index.py expose une variable « app »", application is not None)
    verifier("« app » est une application WSGI appelable",
             callable(application))

    from config import Config, anomalies_configuration

    verifier("Environnement détecté comme production", Config.EST_PRODUCTION)
    verifier("Moteur PostgreSQL sélectionné", Config.DB_TYPE == "postgres")
    verifier("Adresse publique déduite de VERCEL_URL",
             Config.URL_PLATEFORME == f"https://{DOMAINE}",
             Config.URL_PLATEFORME)

    bloquants = [m for g, m in anomalies_configuration() if g == "bloquant"]
    verifier("Aucune anomalie bloquante de configuration",
             not bloquants, " | ".join(bloquants))

    # Route de diagnostic : elle doit être déclarée avant la première
    # requête, et permet de constater ce que l'application perçoit
    # réellement une fois la requête passée par la couche proxy.
    from flask import jsonify, request as requete_flask

    @application.get("/__diagnostic_proxy")
    def _diagnostic_proxy():
        return jsonify({
            "ip": requete_flask.remote_addr,
            "https": requete_flask.is_secure,
            "hote": requete_flask.host,
        })

    client = application.test_client()

    # -----------------------------------------------------------------
    titre("2. BASE DE DONNÉES POSTGRESQL")
    # -----------------------------------------------------------------
    r = client.get("/api/sante", headers=ENTETES_PROXY)
    verifier("La sonde /api/sante répond 200", r.status_code == 200,
             r.get_data(as_text=True)[:200])
    corps = r.get_json() or {}
    verifier("La sonde confirme que la base répond",
             corps.get("statut") == "ok", str(corps))
    verifier("La sonde indique le moteur utilisé",
             corps.get("base") == "postgres", str(corps))

    from models.db import recuperer_un
    with application.app_context():
        tables = recuperer_un(
            "SELECT COUNT(*) AS n FROM information_schema.tables "
            "WHERE table_schema = 'public'")
        verifier("Le schéma a été créé automatiquement",
                 (tables or {}).get("n", 0) >= 20, str(tables))
        secteurs = recuperer_un("SELECT COUNT(*) AS n FROM secteur")
        verifier("Les référentiels sont chargés",
                 (secteurs or {}).get("n", 0) > 0, str(secteurs))
        comptes = recuperer_un("SELECT COUNT(*) AS n FROM utilisateur")
        verifier("Aucun compte de démonstration créé au déploiement",
                 (comptes or {}).get("n", 0) == 0, str(comptes))

    # -----------------------------------------------------------------
    titre("3. COOKIE DE SESSION DERRIÈRE LE PROXY HTTPS")
    # -----------------------------------------------------------------
    r = client.post("/api/auth/inscription", headers=ENTETES_PROXY, json={
        "prenom": "Fatou", "nom": "SANOGO",
        "email": "fatou.deploiement@exemple.org",
        "mot_de_passe": "Deploiement2026!",
        "role": "etudiant",
    })
    verifier("Inscription acceptée (201)", r.status_code == 201,
             r.get_data(as_text=True)[:200])

    entete = cookie_session(r)
    verifier("Un cookie de session est posé", bool(entete))
    verifier("Cookie HttpOnly (inaccessible au JavaScript)",
             "HttpOnly" in entete, entete)
    verifier("Cookie Secure (jamais transmis en clair)",
             "Secure" in entete, entete)
    verifier("Cookie SameSite=Lax (protection CSRF)",
             "SameSite=Lax" in entete, entete)
    verifier("Cookie limité à la racine du site",
             "Path=/" in entete, entete)

    r = client.get("/api/profil/moi", headers=ENTETES_PROXY)
    verifier("La session est utilisable sur la requête suivante",
             r.status_code == 200, r.get_data(as_text=True)[:200])

    r = client.post("/api/auth/deconnexion", headers=ENTETES_PROXY)
    entete = cookie_session(r)
    verifier("La déconnexion efface le cookie avec les mêmes attributs",
             "Secure" in entete and "HttpOnly" in entete, entete)
    r = client.get("/api/profil/moi", headers=ENTETES_PROXY)
    verifier("La session n'est plus valide après déconnexion",
             r.status_code == 401)

    # -----------------------------------------------------------------
    titre("4. ADRESSE IP RÉELLE DU VISITEUR")
    # -----------------------------------------------------------------
    vu = client.get("/__diagnostic_proxy", headers=ENTETES_PROXY).get_json() or {}
    verifier("remote_addr correspond au visiteur, pas au proxy",
             vu.get("ip") == "41.85.160.7", str(vu))
    verifier("La requête est vue comme sécurisée (HTTPS)",
             vu.get("https") is True, str(vu))
    verifier("Le nom d'hôte public est restitué",
             vu.get("hote") == DOMAINE, str(vu))

    # Sans en-tête de proxy, aucune confiance accordée : une IP forgée
    # par un client direct ne doit pas être reprise.
    vu = client.get("/__diagnostic_proxy").get_json() or {}
    verifier("Adresse par défaut conservée hors proxy",
             vu.get("ip") != "41.85.160.7", str(vu))

    # -----------------------------------------------------------------
    titre("5. LIENS ENVOYÉS PAR E-MAIL")
    # -----------------------------------------------------------------
    from utils.urls import url_publique
    with application.test_request_context("/api/auth/inscription",
                                          headers=ENTETES_PROXY):
        lien = url_publique("/verifier-email.html?jeton=abc")
    verifier("Lien de vérification en HTTPS", lien.startswith("https://"), lien)
    verifier("Lien de vérification sur le bon domaine",
             lien == f"https://{DOMAINE}/verifier-email.html?jeton=abc", lien)

    # Hors contexte de requête (script en ligne de commande)
    with application.app_context():
        lien_cli = url_publique("/index.html")
    verifier("Les scripts d'administration produisent aussi une URL publique",
             lien_cli == f"https://{DOMAINE}/index.html", lien_cli)

    # -----------------------------------------------------------------
    titre("6. EN-TÊTES DE SÉCURITÉ")
    # -----------------------------------------------------------------
    r = client.get("/api/sante", headers=ENTETES_PROXY)
    csp = r.headers.get("Content-Security-Policy", "")
    verifier("Politique de sécurité du contenu présente", bool(csp))
    verifier("Google Identity Services autorisé (script)",
             "script-src" in csp and "https://accounts.google.com" in csp, csp)
    verifier("Iframe Google autorisée (frame-src)",
             "frame-src https://accounts.google.com" in csp, csp)
    verifier("Police DM Sans autorisée",
             "https://fonts.gstatic.com" in csp
             and "https://fonts.googleapis.com" in csp, csp)
    verifier("Photos de profil Google et LinkedIn autorisées",
             "lh3.googleusercontent.com" in csp
             and "media.licdn.com" in csp, csp)
    verifier("Inclusion dans une iframe interdite",
             "frame-ancestors 'none'" in csp, csp)
    verifier("En-tête X-Content-Type-Options",
             r.headers.get("X-Content-Type-Options") == "nosniff")
    verifier("En-tête X-Frame-Options",
             r.headers.get("X-Frame-Options") == "DENY")

    # -----------------------------------------------------------------
    titre("7. CODE SOURCE NON EXPOSÉ")
    # -----------------------------------------------------------------
    for chemin_interdit in ("/backend/config.py", "/backend/app.py",
                            "/database/schema_postgres.sql",
                            "/backend/.env", "/api/index.py"):
        r = client.get(chemin_interdit, headers=ENTETES_PROXY)
        verifier(f"{chemin_interdit} inaccessible", r.status_code == 404,
                 str(r.status_code))

    # -----------------------------------------------------------------
    titre("8. RÉFÉRENCEMENT ET MÉTADONNÉES DE LA PAGE")
    # -----------------------------------------------------------------
    # Ces balises se perdent facilement : elles ne cassent rien en
    # disparaissant, aucun test fonctionnel ne les touche, et personne ne
    # s'en aperçoit avant de constater des mois plus tard que le site ne
    # ressort nulle part.
    import json as _json
    import re as _re

    page = (RACINE / "index.html").read_text(encoding="utf-8")

    for libelle, marque in [
        ("Titre de page", "<title>"),
        ("Description", 'name="description"'),
        ("URL canonique", 'rel="canonical"'),
        ("Mots-clés", 'name="keywords"'),
        ("Directive robots", 'name="robots"'),
        ("Auteur", 'name="author"'),
        ("Aperçu de partage (Open Graph)", 'property="og:image"'),
        ("Aperçu Twitter", 'name="twitter:card"'),
        ("Couleur de thème", 'name="theme-color"'),
        ("Langue déclarée", 'lang="fr"'),
    ]:
        verifier(libelle, marque in page)

    blocs = _re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', page, _re.S)
    verifier("Trois blocs de données structurées", len(blocs) == 3,
             str(len(blocs)))
    types = []
    for bloc in blocs:
        try:
            types.append(_json.loads(bloc).get("@type"))
        except ValueError as exc:
            verifier("Données structurées valides", False, str(exc))
    verifier("Données structurées valides", len(types) == len(blocs))
    verifier("Fiche du site déclarée", "WebSite" in types, str(types))
    verifier("Questions fréquentes déclarées", "FAQPage" in types, str(types))

    verifier("L'adresse canonique désigne le domaine définitif",
             'href="https://lasourcee.org/"' in page)
    verifier("Aucun chiffre inventé sur la page",
             "+12 000" not in page and "+24 000" not in page)
    verifier("Aucune question inventée sur la page",
             "Sophie M." not in page and "Karim B." not in page)

    for libelle, marque in [
        ("Bouton de thème présent", 'class="bouton-theme"'),
        ("Thème appliqué avant le rendu", "lasourcee-theme"),
        ("Pied de page présent", 'class="pied-page"'),
        ("Signature du développeur", "Coding_DJOROD"),
    ]:
        verifier(libelle, marque in page)

    # -----------------------------------------------------------------
    titre("9. CONFIGURATION DE DÉPLOIEMENT")
    # -----------------------------------------------------------------
    import json
    fichier = RACINE / "vercel.json"
    verifier("vercel.json présent", fichier.exists())
    conf = json.loads(fichier.read_text(encoding="utf-8"))
    sources = [b.get("src") for b in conf.get("builds", [])]
    verifier("api/index.py déclaré comme fonction",
             "api/index.py" in sources, str(sources))
    verifier("Aucun fichier du backend publié en statique",
             not any((s or "").startswith(("backend/", "database/"))
                     for s in sources), str(sources))
    routes = conf.get("routes", [])
    verifier("Les requêtes /api/* sont routées vers la fonction",
             any(r.get("src") == "/(.*)" or r.get("src") == "/api/(.*)"
                 for r in routes)
             and any(r.get("dest") == "/api/index.py" for r in routes))

    requis = RACINE / "requirements.txt"
    verifier("requirements.txt présent à la racine (attendu par Vercel)",
             requis.exists())
    contenu = requis.read_text(encoding="utf-8") if requis.exists() else ""
    verifier("Pilote PostgreSQL déclaré", "psycopg2" in contenu)
    verifier("Flask déclaré", "Flask" in contenu)


if __name__ == "__main__":
    print("\n" + "═" * 70)
    print("  LaSourcee — vérification de déploiement (conditions Vercel)")
    print("═" * 70)
    try:
        executer()
    except Exception as exc:                      # pragma: no cover
        import traceback
        print("\n[INTERROMPU] " + str(exc))
        traceback.print_exc()
        _total += 1

    print("\n" + "═" * 70)
    print(f"  BILAN : {_reussis}/{_total} vérifications réussies")
    print("═" * 70)
    sys.exit(0 if _reussis == _total else 1)
