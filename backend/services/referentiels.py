"""Pays proposés à l'inscription, complétés au démarrage.

La liste d'origine tenait en dix-huit pays : la France, la Belgique, le
Canada et quelques pays d'Afrique de l'Ouest. C'était le périmètre
imaginé au départ, pas celui des personnes qui s'inscrivent. Quelqu'un
au Gabon, au Rwanda, en Haïti ou au Québec ne trouvait que « Autre »,
et son pays disparaissait de son profil — donc des réponses qu'on lui
adresse, puisque les conseils dépendent du pays où l'on étudie.

Le fichier de schéma ne sert qu'à la création : une base déjà en service
ne le rejoue jamais. Les pays manquants sont donc ajoutés à chaque
démarrage, par code ISO, sans toucher aux lignes existantes ni aux
profils qui s'y rattachent.
"""

import logging

logger = logging.getLogger("lasourcee.referentiels")

# Codes ISO 3166-1 alpha-2. Le code sert de clé : renommer un libellé
# ne crée pas de doublon, et les profils déjà rattachés suivent.
#
# L'ordre n'a pas d'importance : l'interface trie par libellé.
PAYS = [
    ("Afrique du Sud", "ZA"), ("Algérie", "DZ"), ("Allemagne", "DE"),
    ("Angola", "AO"), ("Arabie saoudite", "SA"), ("Argentine", "AR"),
    ("Australie", "AU"), ("Autriche", "AT"), ("Bangladesh", "BD"),
    ("Belgique", "BE"), ("Bénin", "BJ"), ("Botswana", "BW"),
    ("Brésil", "BR"), ("Bulgarie", "BG"), ("Burkina Faso", "BF"),
    ("Burundi", "BI"), ("Cambodge", "KH"), ("Cameroun", "CM"),
    ("Canada", "CA"), ("Cap-Vert", "CV"), ("Chili", "CL"),
    ("Chine", "CN"), ("Chypre", "CY"), ("Colombie", "CO"),
    ("Comores", "KM"), ("Congo", "CG"),
    ("Congo (République démocratique)", "CD"), ("Corée du Sud", "KR"),
    ("Côte d'Ivoire", "CI"), ("Croatie", "HR"), ("Cuba", "CU"),
    ("Danemark", "DK"), ("Djibouti", "DJ"), ("Égypte", "EG"),
    ("Émirats arabes unis", "AE"), ("Équateur", "EC"), ("Érythrée", "ER"),
    ("Espagne", "ES"), ("Eswatini", "SZ"), ("États-Unis", "US"),
    ("Éthiopie", "ET"), ("Finlande", "FI"), ("France", "FR"),
    ("Gabon", "GA"), ("Gambie", "GM"), ("Ghana", "GH"),
    ("Grèce", "GR"), ("Guinée", "GN"), ("Guinée équatoriale", "GQ"),
    ("Guinée-Bissau", "GW"), ("Haïti", "HT"), ("Hongrie", "HU"),
    ("Inde", "IN"), ("Indonésie", "ID"), ("Irlande", "IE"),
    ("Islande", "IS"), ("Israël", "IL"), ("Italie", "IT"),
    ("Japon", "JP"), ("Jordanie", "JO"), ("Kenya", "KE"),
    ("Liban", "LB"), ("Libéria", "LR"), ("Libye", "LY"),
    ("Luxembourg", "LU"), ("Madagascar", "MG"), ("Malaisie", "MY"),
    ("Malawi", "MW"), ("Mali", "ML"), ("Maroc", "MA"),
    ("Maurice", "MU"), ("Mauritanie", "MR"), ("Mexique", "MX"),
    ("Mozambique", "MZ"), ("Namibie", "NA"), ("Niger", "NE"),
    ("Nigéria", "NG"), ("Norvège", "NO"), ("Nouvelle-Zélande", "NZ"),
    ("Ouganda", "UG"), ("Pakistan", "PK"), ("Pays-Bas", "NL"),
    ("Pérou", "PE"), ("Philippines", "PH"), ("Pologne", "PL"),
    ("Portugal", "PT"), ("Qatar", "QA"), ("République centrafricaine", "CF"),
    ("République tchèque", "CZ"), ("Roumanie", "RO"), ("Royaume-Uni", "GB"),
    ("Russie", "RU"), ("Rwanda", "RW"), ("Sénégal", "SN"),
    ("Serbie", "RS"), ("Seychelles", "SC"), ("Sierra Leone", "SL"),
    ("Singapour", "SG"), ("Somalie", "SO"), ("Soudan", "SD"),
    ("Sri Lanka", "LK"), ("Suède", "SE"), ("Suisse", "CH"),
    ("Tanzanie", "TZ"), ("Tchad", "TD"), ("Thaïlande", "TH"),
    ("Togo", "TG"), ("Tunisie", "TN"), ("Turquie", "TR"),
    ("Ukraine", "UA"), ("Uruguay", "UY"), ("Venezuela", "VE"),
    ("Viêt Nam", "VN"), ("Yémen", "YE"), ("Zambie", "ZM"),
    ("Zimbabwe", "ZW"),
]

# « Autre » reste en dernier recours, sans code : aucune liste ne sera
# jamais complète, et il vaut mieux un profil approximatif qu'un
# formulaire qu'on ne peut pas valider.
AUTRE = ("Autre", None)


def completer_pays():
    """Ajoute les pays absents. Idempotent, sans effet sur l'existant."""
    from models.db import recuperer_tous, curseur

    try:
        existants = recuperer_tous("SELECT libelle, code_iso FROM pays")
    except Exception as exc:                  # pragma: no cover
        logger.warning("Pays non complétés : %s", exc)
        return 0

    codes = {(l.get("code_iso") or "").upper()
             for l in existants if l.get("code_iso")}
    libelles = {(l.get("libelle") or "").strip().lower() for l in existants}

    manquants = [(nom, code) for nom, code in PAYS
                 if code.upper() not in codes
                 and nom.strip().lower() not in libelles]
    if AUTRE[0].lower() not in libelles:
        manquants.append(AUTRE)
    if not manquants:
        return 0

    try:
        with curseur(commit=True) as cur:
            for nom, code in manquants:
                cur.execute(
                    "INSERT INTO pays (libelle, code_iso) VALUES (%s, %s)",
                    (nom, code))
    except Exception as exc:                  # pragma: no cover
        logger.warning("Pays non complétés : %s", exc)
        return 0

    logger.info("%d pays ajoutés au référentiel.", len(manquants))
    return len(manquants)
