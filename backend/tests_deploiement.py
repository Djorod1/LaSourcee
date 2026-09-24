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

import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# L'environnement doit être posé AVANT tout import : config.py lit les
# variables au moment où le module est chargé, exactement comme sur la
# plateforme.
# ---------------------------------------------------------------------

# Adresse du deploiement, telle que Vercel la pose dans VERCEL_URL.
DEPLOIEMENT = "lasource-test-a1b2c3-equipe.vercel.app"
# Domaine du site, celui que les visiteurs connaissent. C'est lui qui
# doit figurer dans les liens envoyes par e-mail : l'adresse d'un
# deploiement est protegee par une authentification Vercel, et les
# nouveaux inscrits y tombaient sur un mur.
DOMAINE = "lasource-test.org"

os.environ.setdefault("DATABASE_URL",
                      "postgresql://postgres@127.0.0.1:5433/lasource_deploi")
os.environ.update({
    "VERCEL": "1",
    "VERCEL_ENV": "production",
    "VERCEL_URL": DEPLOIEMENT,
    "VERCEL_PROJECT_PRODUCTION_URL": DOMAINE,
    "DB_TYPE": "postgres",
    "SECRET_KEY": "cle-de-test-stable-pour-la-verification-de-deploiement",
    "EMAIL_MODE": "console",
    "VERIFICATION_EMAIL_OBLIGATOIRE": "0",
})
os.environ.pop("URL_PLATEFORME", None)   # doit être déduite du domaine de production

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

# Consentement exige a l'inscription. Les tests le fournissent
# comme l'interface, sinon chaque creation de compte echoue.
CONSENT_DEPLOI = {"conditions": True, "donnees": True,
                  "notifications": False}

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
    verifier("Adresse publique prise sur le domaine de production",
             Config.URL_PLATEFORME == f"https://{DOMAINE}",
             Config.URL_PLATEFORME)
    verifier("L'adresse du déploiement n'est jamais utilisée",
             DEPLOIEMENT not in Config.URL_PLATEFORME,
             "un lien vers un déploiement précis demande une "
             "authentification Vercel : personne n'aboutit")

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
        "consentement": CONSENT_DEPLOI})
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

    # La connexion Google passe par One Tap, qui dialogue avec sa propre
    # fenêtre par postMessage. « same-origin » coupe ce lien : le bouton
    # s'affichait et ne menait nulle part, sans le moindre message. Rien
    # ne le signalerait ici, l'échec se produisant dans le navigateur du
    # visiteur. La protection contre le site tiers qui nous ouvre reste
    # entière, seule la fenêtre que nous ouvrons garde son lien.
    coop = r.headers.get("Cross-Origin-Opener-Policy", "")
    verifier("La fenêtre de connexion Google reste jointe à la page",
             coop == "same-origin-allow-popups", f"reçu « {coop} »")

    titre("EN-TÊTES SUR LES PAGES SERVIES PAR LE CDN")

    # Les en-têtes posés par Flask ne touchent que ce que Flask sert. Or
    # index.html, verifier-email.html et les autres fichiers statiques
    # sont distribués par le CDN : la règle `handle: filesystem` de
    # vercel.json les sert sans jamais passer par la fonction Python.
    #
    # La politique de sécurité du contenu n'atteignait donc AUCUNE des
    # pages HTML — c'est-à-dire précisément celles qui exécutent du
    # JavaScript et qui portent le bouton de connexion Google. Elle ne
    # protégeait que les réponses de l'API et les pages publiques.
    # Cross-Origin-Opener-Policy non plus. Les deux sont maintenant
    # déclarés dans vercel.json, qui s'applique à toutes les réponses.
    config = json.loads((RACINE / "vercel.json").read_text(encoding="utf-8"))
    entetes_cdn = {}
    for regle in config.get("routes", []):
        if regle.get("src") == "/(.*)" and regle.get("headers"):
            entetes_cdn = regle["headers"]
            break
    verifier("Une règle pose des en-têtes sur toutes les réponses",
             bool(entetes_cdn))
    for nom in ("Content-Security-Policy", "Cross-Origin-Opener-Policy",
                "X-Content-Type-Options", "X-Frame-Options",
                "Referrer-Policy", "Strict-Transport-Security"):
        verifier(f"{nom} atteint aussi les pages statiques",
                 nom in entetes_cdn, "absent de vercel.json")

    # Deux définitions de la même politique finissent toujours par
    # diverger : celle du CDN et celle de Flask doivent rester identiques,
    # sinon on durcit d'un côté en croyant durcir partout.
    from utils.securite import POLITIQUE_CSP as _csp_flask
    verifier("La politique du CDN est exactement celle de Flask",
             entetes_cdn.get("Content-Security-Policy") == _csp_flask,
             "vercel.json et securite.py ont divergé")
    verifier("La fenêtre de connexion Google reste jointe, côté CDN aussi",
             entetes_cdn.get("Cross-Origin-Opener-Policy")
             == "same-origin-allow-popups",
             str(entetes_cdn.get("Cross-Origin-Opener-Policy")))

    titre("FICHIER D'EXEMPLE DES VARIABLES")

    # .env.example est ce qu'on lit pour savoir quoi configurer avant une
    # mise en ligne. Il avait pris du retard sur le code : CRON_SECRET n'y
    # figurait pas, si bien qu'on pouvait tout renseigner sans jamais
    # apprendre que le résumé ne partirait pas. Une variable lue par le
    # code et absente d'ici est une panne qu'on découvrira en production.
    exemple = (RACINE / "backend" / ".env.example").read_text(encoding="utf-8")
    declarees = set(re.findall(r"^\s*#?\s*([A-Z][A-Z0-9_]+)=", exemple, re.M))

    lues = set()
    for dossier, _, fichiers in os.walk(RACINE / "backend"):
        if "__pycache__" in dossier:
            continue
        for f in fichiers:
            if not f.endswith(".py") or f.startswith("tests_"):
                continue
            texte = Path(dossier, f).read_text(encoding="utf-8")
            lues |= set(re.findall(
                r'(?:getenv|environ\.get|environ\[)\(?\s*"([A-Z][A-Z0-9_]+)"',
                texte))
            lues |= set(re.findall(
                r'_(?:booleen|entier)\(\s*"([A-Z][A-Z0-9_]+)"', texte))

    # Celles-ci sont posées par la plateforme, pas par la personne qui
    # configure : elles n'ont rien à faire dans un fichier d'exemple.
    POSEES_PAR_LA_PLATEFORME = {
        "VERCEL", "VERCEL_ENV", "VERCEL_URL",
        "VERCEL_PROJECT_PRODUCTION_URL", "PORT", "POSTGRES_URL", "FLASK_DEBUG",
    }
    oubliees = sorted(lues - declarees - POSEES_PAR_LA_PLATEFORME)
    verifier("Toute variable lue par le code figure dans .env.example",
             not oubliees, ", ".join(oubliees))

    titre("HEURE DE LA BASE DE DONNÉES")

    # Toutes les dates sont écrites depuis Python en temps universel, et
    # les colonnes dont la valeur par défaut est CURRENT_TIMESTAMP la
    # reçoivent du serveur de base. Si celui-ci n'est pas réglé sur UTC,
    # les deux sources divergent de l'écart du fuseau : un code de
    # confirmation paraît expiré à l'avance, une personne connectée à
    # l'instant semble absente depuis une heure, le résumé périodique
    # part au mauvais moment. Rien ne lève, rien ne se voit dans les
    # traces, et l'écart est constant donc invisible à l'œil.
    #
    # Les échéances de session ne dépendent plus du fuseau, elles se
    # comparent à une heure universelle explicite. Les valeurs par défaut
    # des colonnes, elles, ne peuvent se corriger qu'en migrant le
    # schéma : ce contrôle les rend visibles plutôt que silencieuses.
    with application.app_context():
        from models.db import recuperer_un as _lire_un
        from datetime import datetime as _dt
        ligne = _lire_un("SELECT CURRENT_TIMESTAMP AS base") or {}
        base = ligne.get("base")
        ecart = None
        if base is not None:
            valeur = base.replace(tzinfo=None) if hasattr(base, "replace") \
                else None
            if valeur is not None:
                ecart = abs((valeur - _dt.utcnow()).total_seconds())
    verifier("L'heure de la base est la même que celle du serveur, en UTC",
             ecart is not None and ecart < 120,
             f"écart de {int(ecart)} s" if ecart is not None
             else "heure illisible")

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

    # -----------------------------------------------------------------
    titre("8ter. MISE À NIVEAU D'UNE BASE DÉJÀ EN SERVICE")
    # -----------------------------------------------------------------
    # Un fichier de schéma ne s'applique qu'à la création. Une base déjà
    # en place ne le rejoue jamais : chaque colonne et chaque table
    # ajoutées depuis y manquent définitivement, et le site tombe en
    # erreur serveur sur la première route qui les touche. C'est arrivé.
    #
    # On reproduit donc le cas : une base au schéma complet, dont on
    # retire ce qui a été ajouté après coup, puis un démarrage.
    from models.db import COLONNES_ATTENDUES, TABLES_ATTENDUES

    try:
        import psycopg2 as _pg
        _cx = _pg.connect(os.environ["DATABASE_URL"])
        _cx.autocommit = True
        _c = _cx.cursor()

        # Retirer les tables et colonnes de la liste de mise à niveau.
        for _table, _ in TABLES_ATTENDUES:
            _c.execute(f"DROP TABLE IF EXISTS {_table} CASCADE")
        for _table, _colonne, _ in COLONNES_ATTENDUES:
            try:
                _c.execute(f"ALTER TABLE {_table} "
                           f"DROP COLUMN IF EXISTS {_colonne} CASCADE")
            except Exception:
                pass

        _c.execute("SELECT COUNT(*) FROM information_schema.tables "
                   "WHERE table_name = %s", (TABLES_ATTENDUES[0][0],))
        verifier("La table récente est bien absente au départ",
                 _c.fetchone()[0] == 0)

        # Le démarrage doit tout rétablir, sans intervention.
        from models.db import completer_colonnes
        completer_colonnes(application)

        _c.execute("SELECT COUNT(*) FROM information_schema.tables "
                   "WHERE table_name = %s", (TABLES_ATTENDUES[0][0],))
        verifier("Le démarrage recrée la table manquante",
                 _c.fetchone()[0] == 1,
                 "sans elle, le journal d'activité échoue en silence")

        _absentes = []
        for _table, _colonne, _ in COLONNES_ATTENDUES:
            _c.execute("SELECT COUNT(*) FROM information_schema.columns "
                       "WHERE table_name = %s AND column_name = %s",
                       (_table, _colonne))
            if _c.fetchone()[0] == 0:
                _absentes.append(f"{_table}.{_colonne}")
        verifier("Le démarrage rétablit toutes les colonnes",
                 not _absentes, _absentes[:5])
        _cx.close()

        # Et le site répond ensuite, sur les routes qui touchent
        # justement ces colonnes.
        _r = client.post("/api/auth/inscription", headers=ENTETES_PROXY, json={
            "prenom": "Migration", "nom": "ESSAI",
            "email": "migration.essai@exemple.org",
            "mot_de_passe": "Migration2026!", "role": "etudiant",
        "consentement": CONSENT_DEPLOI})
        verifier("Une inscription aboutit après mise à niveau",
                 _r.status_code == 201, _r.get_data(as_text=True)[:90])
        client.post("/api/auth/connexion", headers=ENTETES_PROXY, json={
            "email": "migration.essai@exemple.org",
            "mot_de_passe": "Migration2026!"})
        _r = client.put("/api/profil/moi", headers=ENTETES_PROXY,
                        json={"telephone": "0155040432"})
        verifier("Le profil s'enregistre après mise à niveau",
                 _r.status_code == 200, _r.get_data(as_text=True)[:90])
    except ImportError:
        verifier("Mise à niveau vérifiable (psycopg2 requis)", False)

    # -----------------------------------------------------------------
    titre("8bis. COHÉRENCE DES TROIS SCHÉMAS")
    # -----------------------------------------------------------------
    # Une colonne ajoutée à un seul schéma ne se voit pas : les tests
    # tournent sur SQLite et PostgreSQL, et MySQL part en silence. La
    # divergence n'apparaît qu'à l'installation, chez quelqu'un d'autre.
    import re as _re

    def _colonnes(fichier, table):
        texte = (RACINE / "database" / fichier).read_text(encoding="utf-8")
        m = _re.search(r"CREATE TABLE " + table + r"\s*\((.*?)\n\)",
                       texte, _re.S)
        if not m:
            return None
        noms = set()
        for ligne in m.group(1).split("\n"):
            ligne = ligne.strip()
            if not ligne or ligne.startswith("--") or ligne.upper().startswith(
                    ("PRIMARY", "FOREIGN", "CONSTRAINT", "UNIQUE", "KEY",
                     "CHECK", "INDEX")):
                continue
            mm = _re.match(r"([a-z_]+)\s", ligne)
            if mm:
                noms.add(mm.group(1))
        return noms

    for _table in ("utilisateur", "mentor_details", "signalement",
                   "question", "reponse"):
        _s = _colonnes("schema_sqlite.sql", _table)
        _p = _colonnes("schema_postgres.sql", _table)
        _m = _colonnes("schema.sql", _table)
        _ecart = ((_s or set()) ^ (_p or set())) | ((_s or set()) ^ (_m or set()))
        verifier(f"Colonnes identiques dans les 3 schémas ({_table})",
                 _s and _s == _p == _m, sorted(_ecart)[:5])

    for libelle, marque in [
        ("Bouton de thème présent", "bouton-theme"),
        ("Thème appliqué avant le rendu", "lasourcee-theme"),
        ("Pied de page présent", 'class="pied-page"'),
        ("Signature du développeur", "Coding_DJOROD"),
    ]:
        verifier(libelle, marque in page)

    # Le reglage du theme existe sous deux formes, une par largeur
    # d'ecran : l'icone dans la barre au-dessus de 720px, la ligne
    # nommee dans le menu en dessous. Il en faut exactement deux de
    # chaque, une pour l'accueil et une pour l'application ; en manquer
    # une rendrait le reglage introuvable sur l'un des deux ecrans.
    verifier("Deux icônes de thème, une par barre",
             page.count("theme-barre") == 2, page.count("theme-barre"))
    verifier("Deux lignes de thème, une par menu",
             page.count('class="ligne-theme"') == 2,
             page.count('class="ligne-theme"'))
    verifier("Chaque ligne affiche l'état du thème",
             page.count("ligne-theme-etat") == 2)
    # Le bouton etait imbrique dans le bloc cliquable du profil :
    # changer de theme ouvrait aussi le menu.
    apres_profil = page.split('class="nav-profil"')
    verifier("Le bouton de thème n'est plus dans le bloc du profil",
             len(apres_profil) < 2
             or "bouton-theme" not in apres_profil[1].split("</div>")[0])

    # -----------------------------------------------------------------
    titre("9. CONFIGURATION DE DÉPLOIEMENT")
    # -----------------------------------------------------------------
    # `json` est importé en tête du module. Le réimporter ici en faisait
    # une variable locale à toute la fonction, si bien que les contrôles
    # placés plus haut échouaient avant même de s'exécuter.
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

    titre("SYNTAXE DES FICHIERS SERVIS AU NAVIGATEUR")

    # Une erreur de syntaxe dans script.js ne casse pas le serveur : la
    # page se charge, et plus aucun bouton ne répond. Rien ne le
    # signale côté serveur, et les tests d'intégration n'y touchent
    # pas. Ce contrôle attrape la faute avant la mise en ligne.
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        verifier("Contrôle de syntaxe JavaScript (node absent, ignoré)", True)
    else:
        for fichier in ("script.js", "api.js"):
            chemin = RACINE / fichier
            if not chemin.exists():
                verifier(f"{fichier} présent", False)
                continue
            sortie = subprocess.run([node, "--check", str(chemin)],
                                    capture_output=True, text=True)
            verifier(f"{fichier} est syntaxiquement valide",
                     sortie.returncode == 0,
                     " ".join((sortie.stderr or "").split())[:120])

    # Un gestionnaire cité dans le HTML mais absent du script laisse un
    # bouton qui ne fait rien, sans le moindre message.
    html = (RACINE / "index.html").read_text(encoding="utf-8")
    script = (RACINE / "script.js").read_text(encoding="utf-8")
    appeles = set(re.findall(r'on\w+="\s*([a-zA-Z_$][\w$]*)\s*\(', html))
    connus = set(re.findall(r'function\s+([a-zA-Z_$][\w$]*)\s*\(', script))
    connus |= set(re.findall(
        r'(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*'
        r'(?:async\s+)?(?:function|\()', script))
    natifs = {"event", "this", "window", "document", "alert", "confirm",
              "if", "return", "for", "while", "switch"}
    manquants = sorted(appeles - connus - natifs)
    verifier("Tous les gestionnaires cités dans la page existent",
             not manquants, ", ".join(manquants[:6]))

    # Un appel vers une route disparue ne casse rien au chargement : il
    # echoue au moment ou quelqu'un clique, et le message d'erreur parle
    # du serveur alors que la faute est dans la page.
    regles = [(sorted(r.methods - {"HEAD", "OPTIONS"}), str(r))
              for r in application.url_map.iter_rules()]

    def _correspond(chemin, regle):
        return re.fullmatch(re.sub(r"<[^>]+>", "SEG", regle), chemin) is not None

    orphelins, examines = [], 0
    for verbe, brut in re.findall(
            r"API\.(get|post|put|delete)\(\s*([`'\"][^)]*?)[,)]", script):
        examines += 1
        chemin = re.sub(r"\$\{[^}]*\}", "SEG", brut)
        chemin = re.sub(r"['\"`]\s*\+[^+]*?\+\s*['\"`]", "SEG", chemin)
        chemin = re.sub(r"['\"`]\s*\+.*$", "/SEG", chemin)
        chemin = "/api" + re.sub(
            r"/+", "/", chemin.strip("`'\"").split("?")[0]).rstrip("/")
        # Un segment variable qui porte un verbe, comme
        # /admin/mentors/<id>/<action> : on essaie les valeurs connues.
        candidats = [chemin] + [chemin[:-3] + mot
                                for mot in ("verifier", "refuser")
                                if chemin.endswith("/SEG")]
        if not any(verbe.upper() in m and _correspond(c, r)
                   for c in candidats for m, r in regles):
            orphelins.append(f"{verbe.upper()} {chemin}")

    verifier(f"Les {examines} appels du navigateur visent une route existante",
             not orphelins, ", ".join(sorted(set(orphelins))[:4]))

    titre("ACCESSIBILITÉ AU CLAVIER DE LA PAGE")

    # Une page dont les balises se croisent s'affiche quand même : le
    # navigateur répare à sa façon, et le résultat diffère d'un moteur à
    # l'autre. Un <button> fermé par </div> passe ainsi inaperçu jusqu'au
    # jour où une moitié de formulaire se retrouve dans le bouton.
    ouvertes, fautes_structure = [], []
    ORPHELINES = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                  "link", "meta", "param", "source", "track", "wbr", "path",
                  "circle", "rect", "line", "polyline", "polygon", "ellipse",
                  "use", "stop"}

    class _Structure(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag not in ORPHELINES:
                ouvertes.append((tag, self.getpos()[0]))

        def handle_endtag(self, tag):
            if tag in ORPHELINES:
                return
            for i in range(len(ouvertes) - 1, -1, -1):
                if ouvertes[i][0] == tag:
                    for t, ligne in ouvertes[i + 1:]:
                        fautes_structure.append(
                            f"<{t}> l.{ligne} fermé par </{tag}> "
                            f"l.{self.getpos()[0]}")
                    del ouvertes[i:]
                    return
            fautes_structure.append(f"</{tag}> l.{self.getpos()[0]} sans ouverture")

    _Structure(convert_charrefs=True).feed(html)
    verifier("Les balises de la page s'ouvrent et se ferment dans l'ordre",
             not fautes_structure and not ouvertes,
             "; ".join(fautes_structure[:3])
             or ", ".join(f"<{t}> l.{n}" for t, n in ouvertes[:3]))

    # Un onclick posé sur un <div> ne se déclenche ni à Entrée ni à la
    # barre d'espace, et le lecteur d'écran n'annonce rien. L'étape 2 de
    # l'inscription exigeant deux secteurs, une pastille non focusable y
    # bloquait purement et simplement qui navigue au clavier. La règle
    # retenue : un élément cliquable est soit focusable lui-même, soit il
    # contient un élément qui l'est et qui fait la même chose.
    FOCUSABLES = {"button", "a", "input", "select", "textarea", "summary"}
    pile, sans_clavier = [], []

    class _Clavier(HTMLParser):
        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            focusable = tag in FOCUSABLES or "tabindex" in d
            if focusable:
                for entree in pile:
                    entree[3] = True
            if tag in ORPHELINES:
                return
            pile.append([tag, self.getpos()[0],
                         "onclick" in d and not focusable, False])

        def handle_endtag(self, tag):
            for i in range(len(pile) - 1, -1, -1):
                if pile[i][0] == tag:
                    for t, ligne, cliquable, atteignable in pile[i:]:
                        if cliquable and not atteignable:
                            sans_clavier.append(f"<{t}> l.{ligne}")
                    del pile[i:]
                    return

    _Clavier(convert_charrefs=True).feed(html)
    verifier("Tout ce qui est cliquable est atteignable au clavier",
             not sans_clavier, ", ".join(sans_clavier[:5]))

    # Même contrôle sur le HTML que le script fabrique : il échappe au
    # parseur ci-dessus puisqu'il n'existe qu'à l'exécution. La balise
    # ouvrante et sa fermeture tiennent rarement sur la même ligne, on
    # cherche donc dans le texte entier et non ligne par ligne.
    mal_fermes = []
    for debut in re.finditer(r"<button\b", script):
        reste = script[debut.end():]
        fin_bouton, fin_div = reste.find("</button>"), reste.find("</div>")
        if fin_div == -1 or (fin_bouton != -1 and fin_bouton < fin_div):
            continue
        if "<div" in reste[:fin_div]:       # le bouton contient une boîte
            continue
        mal_fermes.append(f"l.{script.count(chr(10), 0, debut.start()) + 1}")
    verifier("Les boutons fabriqués par le script se ferment par </button>",
             not mal_fermes, ", ".join(mal_fermes[:5]))

    # Une pastille de secteur est un <button>. Si quelqu'un la remet en
    # <div>, l'inscription redevient infranchissable au clavier sans que
    # rien ne le signale.
    pastilles_div = re.findall(r'<div[^>]*\bclass="[^"]*\bchip-select\b[^"]*"'
                               r'[^>]*\bonclick=', html + script)
    verifier("Les pastilles de secteur restent des boutons",
             not pastilles_div, f"{len(pastilles_div)} pastille(s) en <div>")

    # Le contrôle de la page ne voit pas le HTML que le script fabrique,
    # et c'est là que se cachaient les onglets de profil, les résultats
    # de recherche, les notifications et les lignes d'activité : tous
    # cliquables, aucun atteignable au clavier. On relit donc aussi les
    # balises ouvrantes écrites dans les gabarits du script.
    muets = []
    for ouvrante in re.finditer(r"<(div|span|li|td|tr)\b[^>]*?\bonclick=",
                                script):
        fin = script.find(">", ouvrante.start())
        balise = script[ouvrante.start():fin if fin > 0 else ouvrante.end()]
        if "tabindex" in balise:
            continue
        muets.append(f"l.{script.count(chr(10), 0, ouvrante.start()) + 1}")
    verifier("Le HTML fabriqué par le script est lui aussi utilisable au clavier",
             not muets, ", ".join(muets[:6]))

    # Le bandeau « Serveur indisponible » restait affiché indéfiniment :
    # la sonde repassait au vert, l'application refonctionnait, et le
    # visiteur lisait encore qu'elle ne marchait pas. Et une panne
    # constatée au chargement ne relançait aucune sonde, donc quelqu'un
    # arrivé pendant une coupure restait devant un site mort jusqu'à ce
    # qu'il pense à recharger.
    api_js = (RACINE / "api.js").read_text(encoding="utf-8")
    verifier("Le bandeau de panne se retire quand le serveur revient",
             "function masquerServeurIndisponible" in api_js
             and re.search(r"Backend\.disponible\s*\)\s*\{[^}]*"
                           r"masquerServeurIndisponible\(\)", api_js,
                           re.S) is not None)
    verifier("Une panne constatée au chargement relance une sonde",
             re.search(r"if\s*\(!Backend\.disponible\)\s*_resonder\(\)",
                       api_js) is not None)

    # Un élément qui se dit bouton doit se comporter comme un bouton.
    # Plusieurs portaient role="button" sans que rien n'écoute Entrée :
    # ils prenaient le focus, s'annonçaient comme des boutons, et ne
    # faisaient rien.
    verifier("Un écouteur clavier dessert les éléments role=\"button\"",
             "getAttribute('role') !== 'button'" in script
             and "cible.click()" in script)

    titre("TÂCHES PLANIFIÉES")

    # L'ordonnanceur de la plateforme appelle en GET. La route du résumé
    # n'acceptait que POST : elle aurait répondu 405 à chaque passage, et
    # le résumé ne serait jamais parti, sans la moindre trace. Un
    # silence de ce genre se confond avec une panne d'envoi et se cherche
    # pendant des semaines du mauvais côté.
    config = json.loads((RACINE / "vercel.json").read_text(encoding="utf-8"))
    taches = config.get("crons") or []
    verifier("Au moins une tâche planifiée est déclarée", bool(taches))
    for tache in taches:
        chemin = tache.get("path", "")
        # Un chemin peut porter plusieurs regles, une par verbe : les
        # reunir, sinon on ne lit que la premiere et le controle conclut
        # de travers.
        verbes = sorted({m for r in application.url_map.iter_rules()
                         if str(r) == chemin
                         for m in r.methods - {"HEAD", "OPTIONS"}})
        verifier(f"La tâche {chemin} répond au GET de l'ordonnanceur",
                 "GET" in verbes,
                 f"verbes acceptés : {verbes or 'route absente'}")
        # Et elle reste fermée à qui n'a pas le secret, quel que soit le
        # verbe : une route qui envoie des e-mails en masse est une arme.
        for verbe in ("get", "post"):
            r = client.open(chemin, method=verbe.upper())
            verifier(f"{chemin} en {verbe.upper()} exige le secret partagé",
                     r.status_code == 403, f"reçu {r.status_code}")


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
