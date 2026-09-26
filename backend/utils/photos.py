"""Photos de profil : hors des listes, servies à part, gardées en cache.

Les photos sont stockées en base sous forme d'image encodée, faute de
disque persistant sur l'hébergement. Elles étaient recopiées telles
quelles dans le JSON de presque toutes les listes : le fil, l'annuaire,
la recherche, la messagerie. Une photo pèse une trentaine de kilo-octets
une fois encodée ; vingt auteurs dans le fil en faisaient 700, que la
compression ne réduit presque pas, et que le navigateur ne pouvait
garder nulle part puisque les réponses de l'API ne se mettent pas en
cache. Mesuré en 3G simulée : les premières questions s'affichaient au
bout de 32 secondes, contre 7 sans les photos.

Une liste ne transporte plus qu'une adresse courte :

    /api/profil/<id>/photo?v=<version>&t=s

servie par une route qui décode l'image une fois et la laisse au
navigateur pour un an. La version change quand la photo change : le
cache ne sert jamais une image périmée, et n'a jamais besoin d'être
revalidé. Une adresse de photo Google, elle, est renvoyée telle quelle.

Deux tailles : la photo de 320 pixels pour un profil, et une vignette
de 96 pixels pour les avatars des listes, qui ne dépassent pas 28 pixels
à l'écran (84 sur un téléphone à haute densité). La vignette est
produite par le navigateur au moment de l'envoi ; une photo plus
ancienne qui n'en a pas est servie en grand, ce qui reste juste.
"""

import base64
import binascii
import hashlib
import re

from flask import Response

# Une vignette de 96 pixels en JPEG tient en quelques kilo-octets ;
# au-delà, elle n'a pas été réduite.
LONGUEUR_VIGNETTE = 60_000

_ENCODEE = re.compile(
    r"data:(image/(?:jpeg|png|webp|gif));base64,([A-Za-z0-9+/]+={0,2})")


def colonnes(alias="u"):
    """Ce qu'une requête de liste lit de la photo, sans lire la photo.

    SUBSTR ne renvoie que les premiers caractères : une photo encodée ne
    quitte pas la base, seule sa nature est connue. Une adresse externe
    (Google) est courte, elle est lue entière.
    """
    return (f"CASE WHEN SUBSTR({alias}.photo_url, 1, 5) = 'data:' "
            f"THEN 1 ELSE 0 END AS photo_interne, "
            f"CASE WHEN SUBSTR({alias}.photo_url, 1, 8) = 'https://' "
            f"THEN {alias}.photo_url END AS photo_externe, "
            f"{alias}.photo_maj_le AS photo_version")


def _version(valeur):
    """Jeton court tiré de la date de mise à jour de la photo.

    Une photo antérieure à cette colonne n'a pas de date : sa version
    vaut « 0 », stable, jusqu'à ce qu'elle change.
    """
    if not valeur:
        return "0"
    return hashlib.sha1(str(valeur).encode()).hexdigest()[:10]


def adresse(id_utilisateur, interne, externe, version, taille="s"):
    """Adresse à mettre dans le JSON, ou None s'il n'y a pas de photo."""
    if externe:
        return externe
    if interne and id_utilisateur:
        suffixe = f"&t={taille}" if taille else ""
        return (f"/api/profil/{int(id_utilisateur)}/photo"
                f"?v={_version(version)}{suffixe}")
    return None


def remplacer(lignes, cle_id="id_utilisateur", cle="photo_url", taille="s"):
    """Pose l'adresse courte sur chaque ligne, retire les colonnes techniques.

    La clé reste « photo_url » : l'interface n'a rien à changer pour
    l'afficher, une adresse se met dans un src comme une image encodée.
    """
    for ligne in lignes:
        ligne[cle] = adresse(ligne.get(cle_id),
                             ligne.pop("photo_interne", 0),
                             ligne.pop("photo_externe", None),
                             ligne.pop("photo_version", None),
                             taille)
    return lignes


def acceptable(valeur, longueur_max):
    """Vrai si la valeur est une image encodée que l'on sait servir."""
    return bool(valeur) and len(valeur) <= longueur_max \
        and bool(_ENCODEE.fullmatch(valeur))


def reponse_image(valeur, version_demandee=None):
    """Réponse HTTP portant l'image encodée, ou None si elle est illisible.

    Le cache est privé : la photo d'un membre, souvent mineur, n'est
    montrée qu'aux personnes connectées, et un cache partagé la servirait
    à n'importe qui. Il dure un an, parce que l'adresse change avec la
    photo ; sans version dans l'adresse, on ne garde qu'une heure.
    """
    trouve = _ENCODEE.fullmatch(valeur or "")
    if not trouve:
        return None
    try:
        octets = base64.b64decode(trouve.group(2), validate=True)
    except (binascii.Error, ValueError):
        return None
    reponse = Response(octets, mimetype=trouve.group(1))
    reponse.headers["Cache-Control"] = (
        "private, max-age=31536000, immutable" if version_demandee
        else "private, max-age=3600")
    # Une image servie par l'API ne doit pas pouvoir être interprétée
    # autrement qu'en image.
    reponse.headers["Content-Disposition"] = "inline"
    return reponse
