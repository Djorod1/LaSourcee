#!/usr/bin/env python3
"""Controle du contraste des couleurs en mode sombre.

Le mode sombre a d'abord ete livre avec un menu d'administration
invisible : son fond empruntait un jeton que j'avais eclairci, alors que
son texte restait blanc. Blanc sur blanc, rien ne s'affichait, et rien
dans les tests ne pouvait le signaler.

Ce controle calcule le rapport de contraste des couples fond/texte
declares, selon la formule des recommandations d'accessibilite. Le seuil
de 4,5 correspond au niveau AA pour du texte courant.

    cd backend && python tests_contraste.py
"""

import pathlib
import re
import sys

RACINE = pathlib.Path(__file__).resolve().parent.parent
SEUIL_AA = 4.5

_echecs = []
_reussites = 0


def _canal(v):
    v = v / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(hexa):
    hexa = hexa.lstrip("#")
    if len(hexa) == 3:
        hexa = "".join(c * 2 for c in hexa)
    r, v, b = (int(hexa[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _canal(r) + 0.7152 * _canal(v) + 0.0722 * _canal(b)


def contraste(avant, arriere):
    a, b = luminance(avant), luminance(arriere)
    clair, sombre = max(a, b), min(a, b)
    return (clair + 0.05) / (sombre + 0.05)


def verifier(libelle, texte, fond):
    global _reussites
    rapport = contraste(texte, fond)
    if rapport >= SEUIL_AA:
        _reussites += 1
        print("  [OK  ] %-46s %.1f:1" % (libelle, rapport))
    else:
        _echecs.append((libelle, texte, fond, rapport))
        print("  [ECHEC] %-45s %.1f:1  (%s sur %s)"
              % (libelle, rapport, texte, fond))


def jetons_du_theme(bloc):
    """Extrait les jetons de couleur d'un bloc de declarations CSS."""
    return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", bloc))


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  LaSourcee, controle de contraste du mode sombre")
    print("=" * 70)

    css = (RACINE / "styles.css").read_text(encoding="utf-8")
    bloc = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\}', css, re.S)
    if not bloc:
        print("\n  Bloc de thème sombre introuvable.")
        sys.exit(1)
    j = jetons_du_theme(bloc.group(1))

    # Couples reellement utilises par la feuille de style.
    verifier("Texte courant sur le fond", j["--texte"], j["--fond"])
    verifier("Texte courant sur une carte", j["--texte"], j["--surface"])
    verifier("Texte attenue sur le fond", j["--texte-doux"], j["--fond"])
    verifier("Texte attenue sur une carte", j["--texte-doux"], j["--surface"])
    verifier("Lien et bouton sur le fond", j["--primaire"], j["--fond"])
    verifier("Lien et bouton sur une carte", j["--primaire"], j["--surface"])
    verifier("Chiffre mis en avant sur sa pastille",
             j["--primaire"], j["--bleu-clair"])

    # Le menu d'administration : fond sombre, texte blanc en dur. C'est
    # precisement le couple qui avait disparu.
    verifier("Menu d'administration", "#FFFFFF", j["--gris-sombre"])

    # Le titre emprunte --noir, qui doit s'eclaircir.
    verifier("Titre sur une carte", j["--noir"], j["--surface"])

    # Le bleu principal sert AUSSI de fond aux boutons. Aucune teinte
    # unique ne peut a la fois se lire comme texte sur fond sombre et
    # porter du blanc : d'ou le jeton --sur-primaire.
    verifier("Texte sur un bouton principal",
             j["--sur-primaire"], j["--primaire"])
    verifier("Texte attenue sur une pastille bleue",
             j["--texte"], j["--primaire-clair"])

    # Etiquettes en couleur, ecrites en dur dans la feuille : elles ne
    # passent par aucun jeton et echapperaient donc au reste du
    # controle. Le violet et le rose qu'elles remplacent ont ete retires
    # parce qu'ils n'appartenaient pas a la marque ; leurs remplacants
    # doivent au moins se lire.
    for nom, regle in (
            ("Etiquette ardoise, theme clair", r"\.tag-ardoise\s*\{([^}]*)\}"),
            ("Etiquette terre cuite, theme clair", r"\.tag-terre\s*\{([^}]*)\}"),
            ("Etiquette ardoise, theme sombre",
             r'data-theme="dark"\]\s*\.tag-ardoise[^{]*\{([^}]*)\}'),
            ("Etiquette terre cuite, theme sombre",
             r'data-theme="dark"\]\s*\.tag-terre[^{]*\{([^}]*)\}'),
    ):
        bloc_tag = re.search(regle, css)
        if not bloc_tag:
            _echecs.append((nom, "?", "?", 0.0))
            print("  [ECHEC] %-45s regle introuvable" % nom)
            continue
        corps = bloc_tag.group(1)
        fond = re.search(r"background:\s*(#[0-9a-fA-F]{3,8})", corps)
        texte = re.search(r"color:\s*(#[0-9a-fA-F]{3,8})", corps)
        if fond and texte:
            verifier(nom, texte.group(1), fond.group(1))

    print("\n" + "=" * 70)
    total = _reussites + len(_echecs)
    print("  BILAN : %d/%d couples au niveau AA (seuil %.1f:1)"
          % (_reussites, total, SEUIL_AA))
    print("=" * 70)
    sys.exit(1 if _echecs else 0)
