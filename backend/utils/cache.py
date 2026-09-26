"""Mise en cache des réponses publiques, identiques pour tout le monde.

Toute réponse de l'API part en « no-store » (utils/securite.py) : elle
porte en général des données propres à une session. Quelques-unes n'en
portent aucune — la liste des pays, des secteurs, les chiffres de la
page d'accueil, les pages publiques des questions — et elles étaient
relues à chaque ouverture de page, sur des connexions où chaque
aller-retour coûte près d'une demi-seconde.

``s-maxage`` est ce qui permet au réseau de diffusion de Vercel de
répondre sans réveiller la fonction ni la base ; ``max-age`` vaut pour
le navigateur. Les durées restent courtes pour ce qui peut être retiré
par la modération : un contenu retiré ne doit pas rester servi.
"""

from functools import wraps

from flask import make_response


def cache_public(navigateur, reseau=None):
    """Décorateur : cache public sur les réponses 200 de la route.

    Une erreur n'est jamais mise en cache : une panne passagère de la
    base resterait sinon servie à tout le monde pendant la durée prévue.
    """
    reseau = navigateur if reseau is None else reseau

    def decorateur(fonction):
        @wraps(fonction)
        def emballe(*args, **kwargs):
            reponse = make_response(fonction(*args, **kwargs))
            if reponse.status_code == 200:
                reponse.headers["Cache-Control"] = (
                    f"public, max-age={navigateur}, s-maxage={reseau}")
            return reponse
        return emballe
    return decorateur
