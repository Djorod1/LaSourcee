"""Renforcement de la sécurité applicative.

Regroupe :
  - une politique de robustesse des mots de passe ;
  - une protection contre les attaques par force brute sur la connexion
    (limitation du nombre de tentatives par identifiant + adresse IP) ;
  - les en-têtes HTTP de sécurité appliqués à chaque réponse.

Les tentatives infructueuses sont comptées en base : c'est la seule
façon que la limitation résiste à un hébergement sans état, où les
instances vont et viennent.
"""

import logging
import os
import re
import time

from flask import request
from threading import Lock

logger = logging.getLogger("lasourcee.securite")

# --- Politique de mot de passe ------------------------------------------

LONGUEUR_MIN = 8


def mot_de_passe_valide(mdp: str):
    """Retourne (True, '') si le mot de passe respecte la politique,
    sinon (False, message d'explication)."""
    if not mdp or len(mdp) < LONGUEUR_MIN:
        return False, f"Le mot de passe doit comporter au moins {LONGUEUR_MIN} caractères."
    if mdp.isdigit() or mdp.isalpha():
        return False, "Le mot de passe doit mélanger lettres, chiffres et symboles."
    if not re.search(r"[A-Za-z]", mdp) or not re.search(r"\d", mdp):
        return False, "Le mot de passe doit contenir au moins une lettre et un chiffre."
    return True, ""


# --- Anti-force-brute ----------------------------------------------------
#
# Les tentatives sont comptées en base, pas en mémoire vive. Sur un
# hébergement sans état — Vercel, Render — chaque requête peut être
# traitée par une instance différente, créée puis détruite en continu :
# un compteur en mémoire ne s'incrémenterait jamais d'une tentative à la
# suivante, et la protection ne serait qu'apparente.
#
# Le magasin en mémoire subsiste uniquement comme filet : si la table est
# absente (installation non migrée) ou la base momentanément injoignable,
# la limitation continue de fonctionner au sein de l'instance plutôt que
# de disparaître ou de faire échouer la requête.

_MAX_TENTATIVES = 5          # échecs tolérés avant blocage (connexion)
_FENETRE = 15 * 60           # fenêtre d'observation (secondes)
_DUREE_BLOCAGE = 15 * 60     # durée du blocage après dépassement (secondes)

# Seuils par action. Ils ne poursuivent pas le même but : sur la
# connexion il s'agit d'arrêter une attaque par force brute, donc le
# seuil est bas ; sur l'inscription il s'agit d'endiguer un robot, et le
# seuil doit rester compatible avec une salle de classe entière derrière
# une seule adresse IP publique — cas courant sur un campus ou un réseau
# mobile. Un robot en fait des milliers : trente ne le gêne pas moins.
MAX_INSCRIPTIONS = int(os.getenv("MAX_INSCRIPTIONS_PAR_IP", "30"))
MAX_DEMANDES_MDP = int(os.getenv("MAX_DEMANDES_MDP", "3"))

_tentatives = {}             # repli : clé -> liste d'horodatages d'échec
_verrou = Lock()


def _nettoyer(maintenant, horodatages):
    return [t for t in horodatages if maintenant - t < _FENETRE]


# -- Repli en mémoire ----------------------------------------------------

def _est_bloque_memoire(cle, maintenant, maximum=_MAX_TENTATIVES):
    with _verrou:
        horodatages = _nettoyer(maintenant, _tentatives.get(cle, []))
        _tentatives[cle] = horodatages
        if len(horodatages) >= maximum:
            return max(0, int(_DUREE_BLOCAGE - (maintenant - horodatages[-1])))
    return 0


def _enregistrer_echec_memoire(cle, maintenant):
    with _verrou:
        horodatages = _nettoyer(maintenant, _tentatives.get(cle, []))
        horodatages.append(maintenant)
        _tentatives[cle] = horodatages


# -- API publique --------------------------------------------------------

def est_bloque(cle: str, maximum: int = None) -> int:
    """Secondes de blocage restantes pour cette clé (0 si non bloquée)."""
    maximum = _MAX_TENTATIVES if maximum is None else maximum
    maintenant = time.time()
    try:
        from models.db import recuperer_un
        ligne = recuperer_un(
            "SELECT COUNT(*) AS nb, MAX(horodatage) AS dernier "
            "FROM tentative_auth WHERE cle = %s AND horodatage > %s",
            (cle, int(maintenant - _FENETRE)),
        ) or {}
        if (ligne.get("nb") or 0) < maximum:
            return 0
        return max(0, int(_DUREE_BLOCAGE - (maintenant - (ligne.get("dernier") or 0))))
    except Exception:
        logger.warning("Compteur anti-force-brute en base indisponible ; "
                       "repli sur la mémoire de l'instance.")
        return _est_bloque_memoire(cle, maintenant, maximum)


def enregistrer_echec(cle: str) -> None:
    """Comptabilise une tentative infructueuse."""
    maintenant = time.time()
    try:
        from models.db import executer
        executer(
            "INSERT INTO tentative_auth (cle, horodatage) VALUES (%s, %s)",
            (cle[:255], int(maintenant)),
            commit=True,
        )
        _purger_anciennes(maintenant)
    except Exception:
        _enregistrer_echec_memoire(cle, maintenant)


def reinitialiser(cle: str) -> None:
    """Efface le compteur — à appeler après une authentification réussie."""
    try:
        from models.db import executer
        executer("DELETE FROM tentative_auth WHERE cle = %s", (cle[:255],),
                 commit=True)
    except Exception:
        pass
    with _verrou:
        _tentatives.pop(cle, None)


def _purger_anciennes(maintenant):
    """Supprime les tentatives sorties de la fenêtre.

    Déclenchée une fois sur vingt : la table reste petite sans imposer un
    balayage à chaque échec, et sans dépendre d'une tâche planifiée que
    l'hébergement serverless ne saurait pas exécuter.
    """
    if int(maintenant) % 20:
        return
    try:
        from models.db import executer
        executer("DELETE FROM tentative_auth WHERE horodatage < %s",
                 (int(maintenant - _FENETRE - _DUREE_BLOCAGE),), commit=True)
    except Exception:
        pass


# --- En-têtes HTTP de sécurité ------------------------------------------

# Politique de sécurité du contenu.
#
# Le frontend s'appuie sur des gestionnaires d'évènements en ligne
# (onclick=...) : 'unsafe-inline' est donc requis pour les scripts.
# Les origines externes sont limitées au strict nécessaire :
#   - fonts.googleapis.com / fonts.gstatic.com : police DM Sans ;
#   - accounts.google.com : bibliothèque Google Identity Services, qui
#     charge un script, une feuille de style et une iframe. Sans ces
#     autorisations, le bouton « Continuer avec Google » ne s'affiche pas ;
#   - lh3.googleusercontent.com / media.licdn.com : photos de profil
#     rapatriées lors d'une connexion Google ou LinkedIn.
# Aucune autre source n'est acceptée, l'inclusion dans une iframe reste
# interdite et base-uri est verrouillée.
#
# Durcissement futur : externaliser les gestionnaires d'évènements pour
# pouvoir retirer 'unsafe-inline' de script-src.
POLITIQUE_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https://lh3.googleusercontent.com "
    "https://media.licdn.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
    "https://accounts.google.com; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "script-src 'self' 'unsafe-inline' https://accounts.google.com; "
    "connect-src 'self' https://accounts.google.com; "
    "frame-src https://accounts.google.com; "
    "form-action 'self' https://www.linkedin.com; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


def appliquer_entetes_securite(reponse):
    """Durcit chaque réponse contre le clickjacking, le sniffing MIME et
    les fuites de référent, et applique la politique de sécurité du
    contenu définie ci-dessus."""
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    reponse.headers["X-Frame-Options"] = "DENY"
    reponse.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    reponse.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    reponse.headers["Content-Security-Policy"] = POLITIQUE_CSP

    # HSTS : le navigateur refuse ensuite toute connexion en clair vers
    # ce domaine, y compris si un lien HTTP lui est presente. Pose
    # uniquement quand la connexion est deja chiffree : l'annoncer sur
    # du HTTP local rendrait le site inaccessible en developpement.
    if request and request.headers.get("X-Forwarded-Proto", "").startswith("https"):
        reponse.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains")

    # Isole la page des fenetres qu'elle ouvre et de celles qui
    # l'ouvrent : sans cela, un site tiers gardant une reference sur
    # notre onglet peut le rediriger.
    reponse.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    reponse.headers["X-Permitted-Cross-Domain-Policies"] = "none"

    # Les reponses de l'API ne doivent jamais etre mises en cache par un
    # intermediaire : elles contiennent des donnees propres a une
    # session.
    if request and request.path.startswith("/api/"):
        reponse.headers["Cache-Control"] = "no-store"
    return reponse
