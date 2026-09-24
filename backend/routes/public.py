"""Pages lisibles sans compte, et sans JavaScript.

Le site entier vivait derrière une connexion : un moteur de recherche
n'en voyait qu'une page, l'accueil. Aucune quantité de balises ne
compense cela. Ce qui rend un site trouvable, ce sont des pages qui
répondent à une question que quelqu'un a réellement tapée, et ces
pages-là existent déjà sur la plateforme : ce sont les questions des
membres, et les réponses des référents.

Elles sont donc servies ici en HTML complet, rendu par le serveur.
Aucun JavaScript n'est nécessaire pour les lire, ce qui compte autant
pour un robot d'indexation que pour quelqu'un qui ouvre le lien sur une
connexion lente.

Ce que ces pages ne montrent pas
--------------------------------
Le nom complet de l'auteur : prénom et initiale, comme dans les
notifications. Ni adresse, ni téléphone, ni établissement. Une question
publique ne doit pas rendre publique la personne qui l'a posée.

Ce réglage se coupe
-------------------
``QUESTIONS_PUBLIQUES=0`` referme tout : les pages répondent alors 404 et
le plan du site se réduit à l'accueil. Rendre publiques les questions
des membres est une décision qui appartient à la plateforme, pas au
code, et elle doit figurer dans la politique de confidentialité.
"""

import html
import logging
import re
import unicodedata
from datetime import datetime

from flask import Blueprint, Response, abort, current_app, request

from models.db import recuperer_un, recuperer_tous
from utils.urls import url_publique

logger = logging.getLogger("lasourcee.public")

bp_public = Blueprint("public", __name__)

PAR_PAGE = 50
MAX_SITEMAP = 5000

AUCUNE_REPONSE = "<p>Personne n'a encore répondu à cette question.</p>"


def _actif():
    return bool(current_app.config.get("QUESTIONS_PUBLIQUES", True))


def _slug(texte):
    """Titre réduit à ce qui tient dans une adresse."""
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", str(texte or ""))
        if unicodedata.category(c) != "Mn")
    propre = re.sub(r"[^a-zA-Z0-9]+", "-", sans_accent).strip("-").lower()
    return propre[:70] or "question"


def _e(valeur):
    return html.escape(str(valeur or ""), quote=True)


def _auteur(ligne):
    """Prénom et initiale du nom, jamais le nom complet."""
    prenom = (ligne.get("prenom") or "").strip()
    initiale = (ligne.get("nom") or "").strip()[:1]
    return f"{prenom} {initiale}.".strip() if initiale else (prenom or "Membre")


def _date_iso(valeur):
    if not valeur:
        return ""
    texte = str(valeur).replace(" ", "T")
    return texte if texte.endswith("Z") else texte + "Z"


def _date_lisible(valeur):
    try:
        d = datetime.strptime(str(valeur)[:19], "%Y-%m-%dT%H:%M:%S"
                              if "T" in str(valeur) else "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return ""
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{d.day} {mois[d.month - 1]} {d.year}"


def _adresse():
    return url_publique("").rstrip("/")


def _page(titre, description, corps, chemin, extra_tete=""):
    """Squelette commun : mêmes balises que l'application, sans son poids."""
    base = _adresse()
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_e(titre)}</title>
<meta name="description" content="{_e(description)}" />
<link rel="canonical" href="{_e(base + chemin)}" />
<meta name="robots" content="index, follow, max-snippet:-1" />
<meta property="og:type" content="article" />
<meta property="og:site_name" content="LaSourcee" />
<meta property="og:locale" content="fr_FR" />
<meta property="og:title" content="{_e(titre)}" />
<meta property="og:description" content="{_e(description)}" />
<meta property="og:url" content="{_e(base + chemin)}" />
<meta property="og:image" content="{_e(base)}/assets/lasource-partage.png" />
<link rel="icon" type="image/png" href="{_e(base)}/assets/favicon.png" />
<link rel="stylesheet" href="{_e(base)}/styles.css" />
{extra_tete}
</head>
<body class="page-publique">
<header class="bandeau-public">
  <a href="{_e(base)}/" class="marque-public">LaSourcee</a>
  <nav>
    <a href="{_e(base)}/questions">Questions</a>
    <a href="{_e(base)}/" class="btn btn-primaire btn-petit">Créer un compte</a>
  </nav>
</header>
<main class="contenu-public">
{corps}
</main>
<footer class="pied-public">
  <p>LaSourcee met en relation des personnes en demande d'orientation et
     des référents expérimentés. Poser une question est gratuit.</p>
  <p><a href="{_e(base)}/">Accéder à la plateforme</a></p>
</footer>
</body>
</html>"""


def _questions_publiques(limite=PAR_PAGE, decalage=0):
    return recuperer_tous(
        """SELECT q.id_question, q.titre, q.corps, q.publiee_le, q.maj_le,
                  s.libelle AS secteur,
                  u.prenom, u.nom,
                  (SELECT COUNT(*) FROM reponse r
                    WHERE r.id_question = q.id_question) AS nb_reponses
             FROM question q
             JOIN utilisateur u ON u.id_utilisateur = q.id_auteur
        LEFT JOIN secteur s     ON s.id_secteur = q.id_secteur
            WHERE q.statut <> 'fermee'
         ORDER BY q.publiee_le DESC
            LIMIT %s OFFSET %s""",
        (limite, decalage))


@bp_public.get("/questions")
def liste_questions():
    """Toutes les questions, en une page qu'un robot sait lire."""
    if not _actif():
        abort(404)
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    lignes = _questions_publiques(PAR_PAGE, (page - 1) * PAR_PAGE)
    base = _adresse()

    if not lignes and page > 1:
        abort(404)

    articles = "\n".join(
        f"""<article class="carte carte-publique">
  <h2><a href="{_e(base)}/question/{l['id_question']}-{_slug(l['titre'])}">{
            _e(l['titre'])}</a></h2>
  <p class="meta-publique">{_e(l.get('secteur') or 'Toutes filières')} ·
     {_e(_date_lisible(l['publiee_le']))} ·
     {l['nb_reponses']} réponse{'s' if (l['nb_reponses'] or 0) > 1 else ''}</p>
  <p>{_e((l['corps'] or '')[:220])}{'…' if len(l['corps'] or '') > 220 else ''}</p>
</article>""" for l in lignes)

    suivante = (f'<a class="btn btn-secondaire" href="{_e(base)}/questions'
                f'?page={page + 1}">Page suivante</a>'
                if len(lignes) == PAR_PAGE else "")
    precedente = (f'<a class="btn btn-secondaire" href="{_e(base)}/questions'
                  f'?page={page - 1}">Page précédente</a>' if page > 1 else "")

    corps = f"""
<h1>Questions d'orientation, de carrière et d'argent</h1>
<p class="intro-publique">Des questions posées par des étudiants, des
   apprentis et des personnes en reconversion, et les réponses de
   référents qui exercent le métier. La lecture est libre ; répondre
   demande un compte.</p>
{articles or '<p>Aucune question publiée pour le moment.</p>'}
<nav class="pagination-publique">{precedente}{suivante}</nav>
"""
    return Response(
        _page("Questions d'orientation et de carrière, LaSourcee",
              "Questions d'orientation scolaire, de choix de filière, de "
              "premier emploi et d'éducation financière, avec les réponses "
              "de référents expérimentés.",
              corps, "/questions"),
        mimetype="text/html")


@bp_public.get("/question/<int:id_q>")
@bp_public.get("/question/<int:id_q>-<path:slug>")
def page_question(id_q, slug=None):
    """Une question et ses réponses, lisibles sans compte."""
    if not _actif():
        abort(404)
    q = recuperer_un(
        """SELECT q.id_question, q.titre, q.corps, q.publiee_le, q.maj_le,
                  q.statut, q.vues,
                  s.libelle AS secteur, u.prenom, u.nom, p.libelle AS pays
             FROM question q
             JOIN utilisateur u ON u.id_utilisateur = q.id_auteur
        LEFT JOIN secteur s     ON s.id_secteur = q.id_secteur
        LEFT JOIN pays p        ON p.id_pays = u.id_pays
            WHERE q.id_question = %s AND q.statut <> 'fermee'""",
        (id_q,))
    if not q:
        abort(404)

    reponses = recuperer_tous(
        """SELECT r.contenu, r.cree_le, u.prenom, u.nom, u.role,
                  COALESCE(md.est_verifie, 0) AS verifie,
                  (SELECT COUNT(*) FROM marquage_reponse m
                    WHERE m.id_reponse = r.id_reponse
                      AND m.type_marquage = 'utile') AS nb_utiles
             FROM reponse r
             JOIN utilisateur u ON u.id_utilisateur = r.id_auteur
        LEFT JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
            WHERE r.id_question = %s AND r.id_parent_reponse IS NULL
         ORDER BY r.cree_le ASC""",
        (id_q,))

    base = _adresse()
    chemin = f"/question/{id_q}-{_slug(q['titre'])}"

    bloc_reponses = "\n".join(
        f"""<article class="reponse-publique">
  <p class="meta-publique"><strong>{_e(_auteur(r))}</strong>{
            ' · Référent vérifié' if r.get('verifie') else ''} ·
     <time datetime="{_e(_date_iso(r['cree_le']))}">{
            _e(_date_lisible(r['cree_le']))}</time></p>
  <p class="texte-libre">{_e(r['contenu'])}</p>
</article>""" for r in reponses)

    # Donnees structurees QAPage : c'est ce format que les moteurs
    # exploitent pour afficher une question et sa meilleure reponse
    # directement dans leurs resultats.
    import json as _json
    structure = {
        "@context": "https://schema.org",
        "@type": "QAPage",
        "mainEntity": {
            "@type": "Question",
            "name": q["titre"],
            "text": q["corps"],
            "answerCount": len(reponses),
            "datePublished": _date_iso(q["publiee_le"]),
            "author": {"@type": "Person", "name": _auteur(q)},
        },
    }
    if reponses:
        structure["mainEntity"]["acceptedAnswer"] = {
            "@type": "Answer",
            "text": reponses[0]["contenu"],
            "datePublished": _date_iso(reponses[0]["cree_le"]),
            "author": {"@type": "Person", "name": _auteur(reponses[0])},
            "upvoteCount": reponses[0].get("nb_utiles") or 0,
        }
    tete = ('<script type="application/ld+json">'
            + _json.dumps(structure, ensure_ascii=False) + "</script>")

    corps = f"""
<article class="carte carte-publique">
  <p class="fil-ariane"><a href="{_e(base)}/questions">Questions</a> ·
     {_e(q.get('secteur') or 'Toutes filières')}</p>
  <h1>{_e(q['titre'])}</h1>
  <p class="meta-publique">Posée par {_e(_auteur(q))}{
        ' · ' + _e(q['pays']) if q.get('pays') else ''} ·
     <time datetime="{_e(_date_iso(q['publiee_le']))}">{
        _e(_date_lisible(q['publiee_le']))}</time></p>
  <p class="texte-libre">{_e(q['corps'])}</p>
</article>

<h2>{len(reponses)} réponse{'s' if len(reponses) > 1 else ''}</h2>
{bloc_reponses or AUCUNE_REPONSE}

<aside class="carte appel-public">
  <h2>Vous pouvez répondre</h2>
  <p>Si vous exercez ce métier ou avez suivi ce parcours, votre réponse
     vaut plus qu'une recherche. Créer un compte prend une minute.</p>
  <p><a class="btn btn-primaire" href="{_e(base)}/">Rejoindre LaSourcee</a></p>
</aside>
"""
    description = (q["corps"] or "")[:155].replace("\n", " ")
    return Response(
        _page(q["titre"] + ", LaSourcee", description, corps, chemin, tete),
        mimetype="text/html")


@bp_public.get("/sitemap.xml")
def sitemap():
    """Plan du site, construit à partir de ce qui existe réellement.

    Le fichier statique ne listait que l'accueil. Un plan qui ne change
    jamais n'apprend rien à un moteur de recherche, et les pages qu'il
    ignore n'existent pas pour lui.
    """
    base = _adresse()
    urls = [(base + "/", None, "daily", "1.0"),
            (base + "/questions", None, "daily", "0.9")]

    if _actif():
        for l in _questions_publiques(MAX_SITEMAP, 0):
            urls.append((
                f"{base}/question/{l['id_question']}-{_slug(l['titre'])}",
                str(l.get("maj_le") or l.get("publiee_le") or "")[:10],
                "weekly", "0.7"))

    corps = "\n".join(
        "  <url>\n"
        f"    <loc>{_e(adresse)}</loc>\n"
        + (f"    <lastmod>{_e(maj)}</lastmod>\n" if maj else "")
        + f"    <changefreq>{freq}</changefreq>\n"
        f"    <priority>{prio}</priority>\n"
        "  </url>"
        for adresse, maj, freq, prio in urls)

    return Response(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + corps + "\n</urlset>\n",
        mimetype="application/xml")
