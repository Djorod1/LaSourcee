"""Normalisation des dates entre SQLite et MySQL.

SQLite stocke les dates sous forme de texte (« 2026-08-26 13:00:43 »),
alors que MySQL renvoie de vrais objets ``datetime``. Comparer
directement la valeur lue en base avec ``datetime.utcnow()`` provoque
donc une ``TypeError`` en SQLite.

Toute comparaison de date issue de la base doit passer par
``vers_datetime()``.
"""

from datetime import datetime

# Formats rencontrés selon le moteur et la version
FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


def vers_datetime(valeur):
    """Convertit une date lue en base en objet ``datetime``.

    Accepte un ``datetime`` (MySQL) ou une chaîne (SQLite).
    Retourne ``None`` si la valeur est vide ou illisible.
    """
    if valeur is None:
        return None
    if isinstance(valeur, datetime):
        return valeur
    texte = str(valeur).strip()
    if not texte:
        return None
    try:
        return datetime.fromisoformat(texte)
    except ValueError:
        pass
    for fmt in FORMATS:
        try:
            return datetime.strptime(texte, fmt)
        except ValueError:
            continue
    return None


def est_expire(valeur, maintenant=None):
    """Indique si une échéance lue en base est dépassée.

    Une date illisible est considérée comme expirée : en cas de doute
    sur un jeton de sécurité, on refuse plutôt que d'accepter.
    """
    echeance = vers_datetime(valeur)
    if echeance is None:
        return True
    return echeance < (maintenant or datetime.utcnow())
