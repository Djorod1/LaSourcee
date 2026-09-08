#!/usr/bin/env python3
"""Controle de la redaction des textes vus par les utilisateurs.

Le tiret cadratin a ete retire de tout ce qui s'affiche : titres
d'onglet, libelles de l'interface, objets et corps des e-mails, messages
d'erreur. Sans ce controle, il reviendrait a la premiere modification,
et personne ne s'en apercevrait avant qu'un utilisateur ne le voie.

Les commentaires de code et les messages de journal ne sont pas
concernes : ils ne sortent jamais de la machine.

    cd backend && python tests_redaction.py
"""

import pathlib
import sys

RACINE = pathlib.Path(__file__).resolve().parent.parent

# Fichiers dont le contenu peut atteindre un utilisateur.
FICHIERS = [
    "index.html", "verifier-email.html", "reinitialiser.html",
    "script.js", "api.js",
    "backend/routes/auth.py", "backend/routes/oauth.py",
    "backend/routes/admin.py", "backend/routes/profil.py",
    "backend/routes/questions.py", "backend/routes/reponses.py",
    "backend/routes/candidature_mentor.py", "backend/routes/mentors.py",
    "backend/routes/notifications.py", "backend/routes/messagerie.py",
    "backend/utils/email.py", "backend/gerer_admins.py",
    "backend/config.py",
]

# Lignes exemptees : journaux serveur, jamais affiches a un visiteur.
EXEMPTIONS = {
    ("backend/utils/email.py", "logger.error"),
    ("backend/utils/email.py", "logger.info"),
}

TIRETS = ("—", "–")      # cadratin, demi-cadratin

GUILLEMETS_TRIPLES = ('"' * 3, "'" * 3)

_echecs = []


class Lecteur:
    """Suit l'etat des commentaires en parcourant un fichier.

    Un simple test sur le debut de ligne ne suffit pas : les blocs
    /* ... */ et les chaines de documentation Python s'etendent sur
    plusieurs lignes, et leurs lignes de continuation ne portent aucune
    marque. Sans cet etat, tout le contenu d'un commentaire serait
    signale comme visible.
    """

    def __init__(self):
        self.bloc_html = False
        self.bloc_c = False          # /* ... */
        self.bloc_python = False     # chaine de documentation
        self.delimiteur = None

    def est_commentaire(self, ligne):
        nu = ligne.strip()

        # --- commentaire HTML ---------------------------------------
        if self.bloc_html:
            self.bloc_html = "-->" not in nu
            return True
        if "<!--" in nu:
            self.bloc_html = "-->" not in nu
            return True

        # --- bloc /* ... */ (JavaScript, CSS) -----------------------
        if self.bloc_c:
            self.bloc_c = "*/" not in nu
            return True
        if nu.startswith("/*"):
            self.bloc_c = "*/" not in nu
            return True
        if nu.startswith("//"):
            return True

        # --- chaine de documentation Python -------------------------
        if self.bloc_python:
            if self.delimiteur in nu:
                self.bloc_python = False
                self.delimiteur = None
            return True
        for marque in GUILLEMETS_TRIPLES:
            if marque in nu:
                # Ouverte et refermee sur la meme ligne : pas de bloc.
                if nu.count(marque) == 1:
                    self.bloc_python = True
                    self.delimiteur = marque
                return True

        return nu.startswith(("#", "-- "))


def controler(chemin):
    fichier = RACINE / chemin
    if not fichier.exists():
        return
    lecteur = Lecteur()
    for numero, ligne in enumerate(
            fichier.read_text(encoding="utf-8").split("\n"), 1):
        if lecteur.est_commentaire(ligne):
            continue
        if not any(t in ligne for t in TIRETS):
            continue
        if any(chemin == f and marque in ligne for f, marque in EXEMPTIONS):
            continue
        _echecs.append((chemin, numero, ligne.strip()[:88]))


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  LaSourcee, controle de redaction des textes visibles")
    print("=" * 70)

    for chemin in FICHIERS:
        controler(chemin)

    if _echecs:
        print("\n  %d tiret(s) dans un texte visible :\n" % len(_echecs))
        for chemin, numero, extrait in _echecs:
            print("  %s:%d" % (chemin, numero))
            print("      %s" % extrait)
        print("\n  Remplacez-les par une virgule, un deux-points ou un point.")
    else:
        print("\n  Aucun tiret dans les %d fichiers controles."
              % len(FICHIERS))

    print("=" * 70)
    sys.exit(1 if _echecs else 0)
