"""Construction des URL publiques utilisées dans les e-mails.

Un lien envoyé par e-mail doit pointer vers l'adresse que l'utilisateur
voit dans son navigateur. Or, derrière un reverse proxy ou sur une
plateforme serverless, l'application ne reçoit qu'une requête HTTP
interne : ``request.host_url`` renverrait alors une adresse inutilisable
(``http://`` au lieu de ``https://``, voire un nom d'hôte interne).

Ordre de résolution :
  1. ``URL_PLATEFORME`` si elle a été explicitement configurée ;
  2. les en-têtes ``X-Forwarded-Proto`` / ``X-Forwarded-Host`` posés par
     le proxy ;
  3. ``request.host_url`` en dernier recours (développement local).
"""

import os

from flask import current_app, has_app_context, has_request_context, request

_DEFAUT_LOCAL = "http://localhost:5000"


def _configuree():
    """Adresse publique explicitement configurée, ou chaîne vide."""
    valeur = ""
    if has_app_context():
        valeur = current_app.config.get("URL_PLATEFORME", "") or ""
    if not valeur:
        valeur = os.getenv("URL_PLATEFORME", "") or ""
    valeur = valeur.strip().rstrip("/")
    # La valeur de développement ne doit pas masquer l'hôte réel quand la
    # requête arrive depuis un vrai domaine.
    return "" if valeur == _DEFAUT_LOCAL else valeur


def _depuis_requete():
    if not has_request_context():
        return ""
    protocole = (request.headers.get("X-Forwarded-Proto", "")
                 .split(",")[0].strip().lower())
    hote = (request.headers.get("X-Forwarded-Host", "")
            .split(",")[0].strip())
    if not hote:
        hote = request.host
    if not hote:
        return ""
    if not protocole:
        protocole = "https" if request.is_secure else "http"
    return f"{protocole}://{hote}"


def base_publique():
    """Racine du site, sans barre oblique finale."""
    return (_configuree()
            or _depuis_requete()
            or (os.getenv("URL_PLATEFORME", "") or _DEFAUT_LOCAL).rstrip("/"))


def url_publique(chemin=""):
    """Construit une URL absolue vers ``chemin`` (« /verifier-email.html »)."""
    if not chemin:
        return base_publique()
    if not chemin.startswith("/"):
        chemin = "/" + chemin
    return base_publique() + chemin
