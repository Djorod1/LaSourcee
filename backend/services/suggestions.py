"""Suggestions de mentors pour un étudiant.

Heuristique simple combinant :
    1. Recouvrement entre les secteurs d'intérêt de l'étudiant et les
       secteurs d'expertise déclarés par le mentor ;
    2. Proximité géographique (même pays) ;
    3. Qualité du mentor (note moyenne, statut vérifié).

Le score final est normalisé sur 100 pour l'affichage.
"""

from models.db import recuperer_un, recuperer_tous

POIDS_SECTEURS = 0.55
POIDS_PAYS     = 0.20
POIDS_QUALITE  = 0.25


def suggerer_mentors_pour(id_utilisateur, limite=10):
    base = recuperer_un(
        """SELECT id_utilisateur, id_pays
             FROM utilisateur WHERE id_utilisateur = %s""",
        (id_utilisateur,),
    )
    if not base:
        return []

    secteurs_etudiant = {
        s["id_secteur"] for s in recuperer_tous(
            """SELECT id_secteur FROM utilisateur_secteur
                WHERE id_utilisateur = %s""",
            (id_utilisateur,),
        )
    }

    mentors = recuperer_tous(
        """SELECT u.id_utilisateur, u.prenom, u.nom, u.photo_url, u.bio,
                  u.id_pays, p.libelle AS pays,
                  md.est_verifie, md.note_moyenne, md.nb_reponses
             FROM utilisateur u
             JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
        LEFT JOIN pays p ON p.id_pays = u.id_pays
            WHERE u.role = 'mentor' AND u.est_actif = TRUE
              AND u.id_utilisateur <> %s""",
        (id_utilisateur,),
    )

    resultats = []
    for m in mentors:
        secteurs_mentor = {
            s["id_secteur"] for s in recuperer_tous(
                """SELECT id_secteur FROM utilisateur_secteur
                    WHERE id_utilisateur = %s""",
                (m["id_utilisateur"],),
            )
        }
        communs = secteurs_etudiant & secteurs_mentor

        s_sect = (len(communs) / len(secteurs_etudiant)) if secteurs_etudiant else 0.0
        s_pays = 1.0 if (base["id_pays"] and base["id_pays"] == m["id_pays"]) else 0.3
        s_qual = float(m["note_moyenne"]) / 5.0
        if m["est_verifie"]:
            s_qual = min(1.0, s_qual + 0.15)

        score = (POIDS_SECTEURS * s_sect
                 + POIDS_PAYS * s_pays
                 + POIDS_QUALITE * s_qual)

        resultats.append({
            "mentor": m,
            "score": round(score * 100),
            "secteurs_communs": list(communs),
        })

    resultats.sort(key=lambda r: r["score"], reverse=True)
    return resultats[:limite]
