"""Mise en forme des noms de personnes.

Les noms arrivaient en base tels qu'ils avaient été tapés ou tels que
Google les avait transmis. On y trouvait « rodrigue », « DJOSSOU »,
« Rodrigue  Marc » avec deux espaces, des espaces insécables collés par
un copier-coller, et surtout des accents décomposés : « é » écrit comme
un « e » suivi d'un accent séparé. Ces deux formes s'affichent presque
pareil, mais elles ne se comparent pas, ne se trient pas, ne se
cherchent pas de la même façon, et se cassent différemment selon la
police. C'est de là que viennent les noms « bizarres ».

Tout passe donc par une seule porte, ici, avant d'être écrit.
"""

import unicodedata

LONGUEUR_MAX = 60

# Particules qui restent en minuscules quand elles ne commencent pas le
# nom : « Jean de La Fontaine », pas « Jean De La Fontaine ». La liste
# reste courte et couvre le français, le portugais et le néerlandais,
# les trois qu'on rencontre au Bénin et dans sa diaspora.
PARTICULES = {
    "de", "du", "des", "d", "da", "das", "do", "dos",
    "le", "la", "les", "van", "von", "der", "den", "el", "al", "bin",
}

# Séparateurs internes d'un nom composé. Chaque partie reprend une
# majuscule : « Kossi-Marie », « N'Diaye », « Da Silva ».
SEPARATEURS = (" ", "-", "'", "’")

# Caractères invisibles que les copier-coller traînent derrière eux.
# Ils ne se voient pas mais comptent dans la longueur, cassent les
# comparaisons et apparaissent comme des carrés dans certaines polices.
_INVISIBLES = {
    "­",  # trait d'union conditionnel
    "​", "‌", "‍",  # espaces et liants de largeur nulle
    "⁠", "﻿",            # liant sans chasse, marque d'ordre
}


def _nettoyer(brut):
    """Chaîne débarrassée de ce qui ne se voit pas, espaces normalisés."""
    # NFC recompose « e + accent » en « é ». C'est la forme que les
    # bases, les polices et les recherches attendent.
    texte = unicodedata.normalize("NFC", str(brut))
    sortie = []
    for c in texte:
        if c in _INVISIBLES:
            continue
        categorie = unicodedata.category(c)
        # Cc : caractères de contrôle. Cf : marques de formatage.
        # Zs : espaces typographiques, ramenés à l'espace ordinaire.
        if categorie in ("Cc", "Cf"):
            continue
        sortie.append(" " if categorie == "Zs" else c)
    return " ".join("".join(sortie).split())


def _capitaliser_partie(partie, en_tete):
    """Une portion de nom, avec sa majuscule et le reste en minuscules."""
    if not partie:
        return partie
    if not en_tete and partie.lower() in PARTICULES:
        return partie.lower()
    return partie[0].upper() + partie[1:].lower()


def _casse(texte):
    """Rend la casse d'un nom entièrement majuscule ou minuscule.

    Une saisie mélangée est laissée telle quelle : « McDonald »,
    « d'Almeida » ou « van der Berg » sont écrits ainsi volontairement,
    et aucune règle automatique ne les retrouverait. On ne corrige que
    ce qu'on est sûr de ne pas abîmer.
    """
    lettres = [c for c in texte if c.isalpha()]
    if not lettres:
        return texte
    if not (texte == texte.upper() or texte == texte.lower()):
        return texte

    resultat = []
    debut_partie = True
    debut_nom = True
    tampon = []
    for c in texte:
        if c in SEPARATEURS:
            resultat.append(_capitaliser_partie("".join(tampon), debut_nom))
            resultat.append(c)
            tampon = []
            debut_nom = False
            debut_partie = True
        else:
            tampon.append(c)
            debut_partie = False
    resultat.append(_capitaliser_partie("".join(tampon), debut_nom))
    return "".join(resultat)


def normaliser_nom(valeur):
    """Nom propre à écrire en base, ou None si la valeur n'en est pas un.

    Renvoie une chaîne vide pour une valeur vide : à l'appelant de
    décider si le champ est obligatoire.
    """
    texte = _nettoyer(valeur or "")
    if not texte:
        return ""
    if len(texte) > LONGUEUR_MAX:
        texte = texte[:LONGUEUR_MAX].rstrip()
    # Un nom contient des lettres. Une suite de chiffres ou de symboles
    # vient d'un formulaire rempli au hasard ou d'un robot.
    if not any(c.isalpha() for c in texte):
        return None
    return _casse(texte)


def initiales(prenom, nom=""):
    """Une ou deux lettres pour l'avatar.

    Prend la première lettre de chaque nom, pas les deux premiers
    caractères : un prénom commençant par une apostrophe ou un tiret
    donnait des initiales illisibles.
    """
    lettres = []
    for partie in (prenom or "", nom or ""):
        for c in _nettoyer(partie):
            if c.isalpha():
                lettres.append(c.upper())
                break
    return "".join(lettres[:2])


def depuis_adresse(email):
    """Prénom de secours tiré d'une adresse e-mail.

    Quand un fournisseur externe ne transmet pas le prénom, on se
    rabattait sur la partie gauche de l'adresse telle quelle :
    « rodriguedjossou93 » devenait un prénom. On en retire au moins les
    chiffres et les séparateurs, ce qui donne quelque chose de lisible
    en attendant que la personne corrige son profil.
    """
    local = (email or "").split("@")[0]
    for separateur in (".", "_", "-", "+"):
        local = local.replace(separateur, " ")
    local = "".join(c for c in local if not c.isdigit())
    propre = normaliser_nom(local.split(" ")[0] if " " in local else local)
    return propre or "Membre"


def nom_affiche(prenom, nom=""):
    """« Prénom Nom », sans espace en trop si l'un des deux manque."""
    return " ".join(p for p in ((prenom or "").strip(),
                                (nom or "").strip()) if p)
