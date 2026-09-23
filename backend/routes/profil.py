"""Lecture et mise à jour du profil utilisateur."""

import json
import unicodedata

from flask import Blueprint, g, jsonify, request

from models.db import recuperer_un, recuperer_tous, executer, curseur
from utils.auth_helpers import connexion_requise
from utils.noms import normaliser_nom

bp_profil = Blueprint("profil", __name__, url_prefix="/api/profil")

# Valeurs a choix ferme. Une liste courte se remplit ; une liste longue
# se survole et personne ne la renseigne. Ces intitules disent une
# situation reelle, pas un niveau administratif : « en reconversion »
# eclaire une question mieux que « bac+3 ».
SITUATIONS = [
    "Au lycée",
    "En licence",
    "En master",
    "En doctorat",
    "En apprentissage",
    "Jeune diplômé",
    "En activité",
    "En reconversion",
    "En recherche d'emploi",
]

# Ce que la personne cherche, ou ce qu'un referent propose. C'est ce
# champ qui permet d'apparier les deux cotes de la plateforme.
OBJECTIFS = [
    "Choisir ma filière",
    "Préparer mes études à l'étranger",
    "Apprendre un métier",
    "Trouver un stage",
    "Décrocher mon premier emploi",
    "Changer de voie",
    "Gérer mon argent",
    "Accompagner d'autres membres",
]

# Les objectifs se cumulent, dans une seule colonne, separes par une
# virgule. Aucun intitule n'en contient : un test le verifie, et le
# jour ou l'on en ajouterait un, il faudrait changer de separateur
# plutot que decouper aux mauvais endroits sans s'en apercevoir.
SEPARATEUR_OBJECTIFS = ", "
LIMITE_OBJECTIFS = 4          # au-dela, le profil ne dit plus rien
LONGUEUR_OBJECTIFS = 255


def normaliser_telephone(valeur):
    """Numéro nettoyé, ou None si la valeur ne peut pas en être un.

    Le champ existait en base depuis l'origine sans jamais être rempli.
    Il compte : au Bénin comme ailleurs, on se joint par téléphone bien
    plus souvent que par e-mail, et un référent injoignable autrement
    que par la plateforme l'est à peu près complètement.

    On ne valide pas le pays, seulement la forme : espaces, points et
    tirets sont retirés, le « + » initial conservé. Imposer un indicatif
    exclurait des numéros parfaitement valides ailleurs, pour une
    rigueur que personne n'a demandée.
    """
    brut = (valeur or "").strip()
    if not brut:
        return ""
    plus = brut.startswith("+")
    chiffres = "".join(c for c in brut if c.isdigit())
    if not (LONGUEUR_TEL_MIN <= len(chiffres) <= LONGUEUR_TEL_MAX):
        return None
    return ("+" if plus else "") + chiffres


LONGUEUR_TEL_MIN = 8      # un numero beninois local en compte huit
LONGUEUR_TEL_MAX = 15     # maximum prevu par la norme internationale


def _eclater_objectifs(valeur):
    """Liste des objectifs a partir de la colonne stockee."""
    if not valeur:
        return []
    if isinstance(valeur, (list, tuple)):
        return [str(v).strip() for v in valeur if str(v).strip()]
    return [m.strip() for m in str(valeur).split(",") if m.strip()]

# Diplome le plus eleve obtenu.
#
# La liste nommait les diplomes beninois : CEP, BEPC, CQM. Quelqu'un au
# Cameroun, au Canada ou en France ne s'y reconnaissait pas, et cochait
# au hasard le libelle qui ressemblait le plus. Elle nomme desormais le
# NIVEAU atteint, qui se compare d'un pays a l'autre, et cite les
# diplomes locaux en exemple pour que chacun se retrouve.
#
# Les titres professionnels restent au milieu du parcours, la ou ils
# sont reellement : un CAP n'est pas une case « autre » en bas de liste.
NIVEAUX_ETUDES = [
    "Sans diplôme",
    "Fin de primaire (CEP, CEPE…)",
    "Fin de collège (BEPC, brevet…)",
    "Diplôme professionnel (CAP, CQP, CQM, BEP…)",
    "Baccalauréat ou équivalent",
    "Bac+2 (BTS, DUT, DEC, DT…)",
    "Licence (bac+3)",
    "Master (bac+5)",
    "Doctorat",
]

# Ce que les comptes crees avant cette liste portent en base. Les
# refuser empecherait ces personnes d'enregistrer leur profil, pour un
# changement dont elles ne sont pas responsables.
ANCIENS_NIVEAUX = {
    "cep (primaire)": "Fin de primaire (CEP, CEPE…)",
    "bepc (college)": "Fin de collège (BEPC, brevet…)",
    "cap, cqp ou cqm (metier)": "Diplôme professionnel (CAP, CQP, CQM, BEP…)",
    "baccalaureat": "Baccalauréat ou équivalent",
    "bts, dut ou dt (bac+2)": "Bac+2 (BTS, DUT, DEC, DT…)",
}

# Domaine d'etudes ou de metier. Les filieres universitaires et les
# metiers manuels figurent dans la meme liste, sans hierarchie : la
# soudure et le droit s'y choisissent de la meme facon.
DOMAINES = [
    "Informatique et numérique",
    "Ingénierie et industrie",
    "Bâtiment et travaux publics",
    "Mécanique et automobile",
    "Soudure et métallerie",
    "Électricité et électronique",
    "Froid et climatisation",
    "Agriculture et agroalimentaire",
    "Santé et soins",
    "Commerce et vente",
    "Gestion, comptabilité et finance",
    "Droit et administration",
    "Enseignement et éducation",
    "Communication, arts et culture",
    "Couture, mode et esthétique",
    "Hôtellerie et restauration",
    "Transport et logistique",
    "Sciences humaines et sociales",
    "Autre domaine",
]

# Suggestions, et non liste fermee : aucune liste ne contiendra jamais
# tous les etablissements d'un pays, encore moins les ateliers ou se
# fait l'apprentissage. Le champ reste libre ; ces valeurs ne font que
# rendre la saisie plus rapide pour les cas frequents.
#
# Elles sont classees par pays : proposer dix universites beninoises a
# quelqu'un qui etudie a Dakar ou a Montreal ne l'aide pas, et laisse
# croire que la plateforme n'est pas pour lui.
ETABLISSEMENTS_PAR_PAYS = {
    "Bénin": [
        "Université d'Abomey-Calavi (UAC)",
        "Université de Parakou (UP)",
        "UNSTIM (Abomey)",
        "Université Nationale d'Agriculture (UNA)",
        "IFRI (Informatique, UAC)",
        "EPAC (École Polytechnique d'Abomey-Calavi)",
        "ENEAM (Économie Appliquée et Management)",
        "ENSET (Lokossa)",
        "INSTI (Lokossa)",
        "ESGIS Bénin",
        "Institut CERCO",
        "HECM (Commerce et Management)",
        "IRGIB Africa",
        "Lycée technique Coulibaly (Cotonou)",
    ],
    "Togo": [
        "Université de Lomé",
        "Université de Kara",
        "École Polytechnique de Lomé (EPL)",
        "ESGIS Togo",
    ],
    "Côte d'Ivoire": [
        "Université Félix Houphouët-Boigny",
        "Institut National Polytechnique Houphouët-Boigny (INP-HB)",
        "Université Nangui Abrogoua",
        "ESATIC",
    ],
    "Sénégal": [
        "Université Cheikh Anta Diop (UCAD)",
        "Université Gaston Berger (UGB)",
        "École Supérieure Polytechnique (ESP)",
        "Université Amadou Mahtar Mbow",
    ],
    "Cameroun": [
        "Université de Yaoundé I",
        "Université de Douala",
        "Université de Buea",
        "École Nationale Supérieure Polytechnique (ENSP)",
    ],
    "Burkina Faso": [
        "Université Joseph Ki-Zerbo",
        "Université Nazi Boni",
        "Institut 2iE",
    ],
    "Mali": ["Université des Sciences Sociales et de Gestion de Bamako",
             "Université des Sciences, Techniques et Technologies de Bamako"],
    "Niger": ["Université Abdou Moumouni", "Université de Zinder"],
    "Maroc": ["Université Mohammed V de Rabat",
              "Université Hassan II de Casablanca",
              "Université Cadi Ayyad", "ENSA", "ENCG"],
    "Tunisie": ["Université de Tunis El Manar", "Université de Carthage",
                "INSAT"],
    "Algérie": ["Université d'Alger", "USTHB", "Université de Constantine"],
    "France": ["Sorbonne Université", "Université Paris-Saclay",
               "Université de Lille", "Université de Bordeaux",
               "INSA", "IUT", "BTS en lycée"],
    "Canada": ["Université de Montréal", "Université Laval",
               "Université du Québec (UQAM)", "Cégep", "McGill University"],
    "Belgique": ["Université libre de Bruxelles (ULB)", "UCLouvain",
                 "Université de Liège", "Haute École"],
    "Suisse": ["Université de Genève", "Université de Lausanne", "EPFL"],
}

# Propositions valables partout, ajoutees a celles du pays : elles
# decrivent un lieu de formation plutot qu'un etablissement precis, et
# couvrent l'apprentissage, qui n'a d'annuaire nulle part.
ETABLISSEMENTS_UNIVERSELS = [
    "Lycée ou collège",
    "Centre de formation professionnelle",
    "Atelier ou maître artisan",
    "Formation en ligne",
    "En autodidacte",
]

# Conserve pour les appels qui ne precisent aucun pays.
ETABLISSEMENTS_SUGGERES = (ETABLISSEMENTS_PAR_PAYS["Bénin"]
                           + ETABLISSEMENTS_UNIVERSELS)


def etablissements_pour(pays):
    """Suggestions adaptées au pays, puis celles valables partout."""
    if not pays:
        return ETABLISSEMENTS_UNIVERSELS
    cible = _sans_accent(pays)
    for nom, liste in ETABLISSEMENTS_PAR_PAYS.items():
        if _sans_accent(nom) == cible:
            return liste + ETABLISSEMENTS_UNIVERSELS
    return ETABLISSEMENTS_UNIVERSELS


LONGUEUR_ETABLISSEMENT = 120

# La filiere precise ce que le domaine laisse large : « Informatique et
# numerique » ne dit pas si l'on fait du reseau ou du developpement, et
# c'est justement ce qui permet d'orienter quelqu'un. Champ libre :
# aucune liste ne contiendra les filieres de cent dix-sept pays.
LONGUEUR_FILIERE = 120

# Une image de 320 pixels de côté encodée en JPEG tient largement
# dessous ; au-delà, c'est qu'elle n'a pas été réduite.
LONGUEUR_PHOTO = 400_000


def _sans_accent(texte):
    """Version comparable d'un libelle : sans accent, en minuscules."""
    decompose = unicodedata.normalize("NFD", str(texte))
    return "".join(c for c in decompose
                   if unicodedata.category(c) != "Mn").strip().lower()


def niveau_retenu(valeur):
    """Niveau d'études officiel, ou None.

    Accepte les libellés d'avant l'ouverture internationale : quelqu'un
    dont le profil porte « BEPC (collège) » doit pouvoir l'enregistrer
    à nouveau sans que ce changement, dont il n'est pas responsable, lui
    ferme la porte.
    """
    if valeur is None:
        return None
    officiel = _canoniser(valeur, NIVEAUX_ETUDES)
    if officiel is not None:
        return officiel
    return ANCIENS_NIVEAUX.get(_sans_accent(valeur))


def _canoniser(valeur, liste):
    """Ramene une valeur a l'intitule exact de la liste, ou None.

    La comparaison ignore les accents. Les premieres versions de ces
    listes s'ecrivaient sans accent, et « Jeune diplome » est encore
    stocke dans les comptes crees a ce moment la : le refuser
    empecherait ces personnes d'enregistrer leur profil, pour un
    changement dont elles ne sont pas responsables.
    """
    if valeur is None:
        return None
    brut = str(valeur).strip()
    if not brut:
        return ""
    cible = _sans_accent(brut)
    for officiel in liste:
        if _sans_accent(officiel) == cible:
            return officiel
    return None


LONGUEUR_DOMAINE = 80


def domaine_retenu(valeur):
    """Domaine a enregistrer, ou None si la valeur ne convient pas.

    La liste ne contiendra jamais tous les metiers. « Autre domaine »
    existait donc en dernier choix, mais sans nulle part ou dire
    lequel : la personne cochait la case et son metier disparaissait.
    Une valeur absente de la liste est desormais acceptee telle quelle,
    apres nettoyage. C'est aussi ce qui permet aux comptes deja crees
    avec un domaine libre de continuer a enregistrer leur profil.
    """
    if valeur is None:
        return None
    brut = " ".join(str(valeur).split())
    if not brut:
        return ""
    officiel = _canoniser(brut, DOMAINES)
    if officiel:
        return officiel
    if len(brut) < 2 or not any(c.isalpha() for c in brut):
        return None
    return brut[:LONGUEUR_DOMAINE]


def id_pays_depuis(valeur):
    """Identifiant du pays a partir d'un identifiant ou d'un libelle.

    Le client envoyait un identifiant qu'il devait retrouver lui-meme
    dans un referentiel charge a part. Quand ce chargement echouait, le
    pays partait vide sans que rien ne le signale.
    """
    if valeur in (None, ""):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        pass
    cible = _sans_accent(valeur)
    for ligne in recuperer_tous("SELECT id_pays, libelle FROM pays"):
        if _sans_accent(ligne["libelle"]) == cible:
            return ligne["id_pays"]
    return None


def ids_secteurs_depuis(valeurs):
    """Identifiants de secteurs a partir d'identifiants ou de libelles."""
    if not valeurs:
        return []
    connus = recuperer_tous("SELECT id_secteur, libelle FROM secteur")
    par_libelle = {_sans_accent(s["libelle"]): s["id_secteur"] for s in connus}
    existants = {s["id_secteur"] for s in connus}
    retenus = []
    for brut in valeurs:
        trouve = None
        try:
            entier = int(brut)
            trouve = entier if entier in existants else None
        except (TypeError, ValueError):
            trouve = par_libelle.get(_sans_accent(brut))
        if trouve is not None and trouve not in retenus:
            retenus.append(trouve)
    return retenus


# Champs du profil que l'inscription peut deja renseigner. Ils etaient
# recueillis pendant l'accueil guide, gardes dans une variable de la
# page, puis envoyes seulement apres la saisie du code de confirmation.
# Toute personne qui fermait l'onglet pour aller lire son e-mail
# perdait la totalite de sa saisie et trouvait un profil vide.
CHAMPS_INSCRIPTION = ("bio", "niveau_etudes", "domaine", "filiere",
                      "etablissement", "situation", "telephone", "ville")


def profil_initial(bloc):
    """Colonnes a ecrire a la creation du compte, depuis le bloc recu.

    Renvoie ``(colonnes, secteurs, erreur)``. Une valeur refusee ne fait
    pas echouer l'inscription : le compte se crée, le champ reste vide,
    et la personne le corrigera depuis ses parametres. Perdre un compte
    pour un etablissement trop long serait hors de proportion.
    """
    if not isinstance(bloc, dict):
        return {}, [], None

    colonnes = {}
    for cle in CHAMPS_INSCRIPTION:
        valeur = bloc.get(cle)
        if valeur in (None, ""):
            continue
        colonnes[cle] = valeur

    if "niveau_etudes" in colonnes:
        retenu = niveau_retenu(colonnes["niveau_etudes"])
        if retenu:
            colonnes["niveau_etudes"] = retenu
        else:
            colonnes.pop("niveau_etudes")

    if "situation" in colonnes:
        retenu = _canoniser(colonnes["situation"], SITUATIONS)
        if retenu:
            colonnes["situation"] = retenu
        else:
            colonnes.pop("situation")

    if "domaine" in colonnes:
        retenu = domaine_retenu(colonnes["domaine"])
        if retenu:
            colonnes["domaine"] = retenu
        else:
            colonnes.pop("domaine")

    if "telephone" in colonnes:
        numero = normaliser_telephone(colonnes["telephone"])
        if numero:
            colonnes["telephone"] = numero
        else:
            colonnes.pop("telephone")

    if "etablissement" in colonnes:
        colonnes["etablissement"] = \
            str(colonnes["etablissement"]).strip()[:LONGUEUR_ETABLISSEMENT]
    if "filiere" in colonnes:
        colonnes["filiere"] = \
            " ".join(str(colonnes["filiere"]).split())[:LONGUEUR_FILIERE]
    if "bio" in colonnes:
        colonnes["bio"] = str(colonnes["bio"]).strip()[:2000]
    if "ville" in colonnes:
        colonnes["ville"] = str(colonnes["ville"]).strip()[:120]

    objectifs = bloc.get("objectifs")
    if isinstance(objectifs, (list, tuple)):
        retenus = []
        for brut in list(objectifs)[:LIMITE_OBJECTIFS]:
            officiel = _canoniser(brut, OBJECTIFS)
            if officiel and officiel not in retenus:
                retenus.append(officiel)
        if retenus:
            colonnes["objectif"] = \
                SEPARATEUR_OBJECTIFS.join(retenus)[:LONGUEUR_OBJECTIFS]

    id_pays = id_pays_depuis(bloc.get("id_pays") or bloc.get("pays"))
    if id_pays:
        colonnes["id_pays"] = id_pays

    return colonnes, ids_secteurs_depuis(bloc.get("secteurs")), None


@bp_profil.get("/referentiels-profil")
def referentiels_profil():
    """Valeurs proposees pour les champs a choix ferme.

    Servies par le serveur plutot qu'ecrites dans la page : la liste
    validee et la liste affichee ne peuvent alors pas diverger.
    """
    # Les suggestions d'établissement suivent le pays : proposer dix
    # universités béninoises à quelqu'un qui étudie à Dakar ou à
    # Montréal ne l'aide pas, et laisse croire que la plateforme n'est
    # pas pour lui.
    pays = request.args.get("pays")
    return jsonify({
        "situations": SITUATIONS,
        "objectifs": OBJECTIFS,
        "niveaux_etudes": NIVEAUX_ETUDES,
        "domaines": DOMAINES,
        "etablissements": etablissements_pour(pays),
        "pays_avec_suggestions": sorted(ETABLISSEMENTS_PAR_PAYS),
    })


@bp_profil.get("/referentiels")
def referentiels():
    """Endpoint public : secteurs et pays disponibles."""
    return jsonify({
        "secteurs": recuperer_tous(
            "SELECT id_secteur, libelle, couleur FROM secteur ORDER BY libelle"
        ),
        "pays": recuperer_tous(
            "SELECT id_pays, libelle, code_iso FROM pays ORDER BY libelle"
        ),
    })


@bp_profil.get("/moi")
@connexion_requise
def mon_profil():
    return jsonify(_charger_profil(g.utilisateur["id_utilisateur"]))


@bp_profil.get("/<int:id_user>")
@connexion_requise
def voir_profil(id_user):
    profil = _charger_profil(id_user, public=True)
    if profil is None:
        return jsonify({"erreur": "Utilisateur introuvable."}), 404
    return jsonify(profil)


@bp_profil.put("/moi")
@connexion_requise
def modifier_profil():
    d = request.get_json(silent=True) or {}
    id_user = g.utilisateur["id_utilisateur"]

    champs = {
        "prenom": d.get("prenom"),
        "nom": d.get("nom"),
        "bio": d.get("bio"),
        "photo_url": d.get("photo_url"),
        "etudes": d.get("etudes"),
        "ville": d.get("ville"),
        "id_pays": d.get("id_pays"),
        "situation": d.get("situation"),
        "objectif": d.get("objectif"),
        "langues": d.get("langues"),
        "profil_pro": d.get("profil_pro"),
        "niveau_etudes": d.get("niveau_etudes"),
        "filiere": d.get("filiere"),
        "domaine": d.get("domaine"),
        "etablissement": d.get("etablissement"),
        "telephone": d.get("telephone"),
    }
    champs = {k: v for k, v in champs.items() if v is not None}

    # Les valeurs a choix ferme sont verifiees cote serveur : un client
    # peut envoyer ce qu'il veut, et une valeur inventee remonterait
    # telle quelle sur les profils publics. La valeur retenue est celle
    # de la liste, pas celle recue : la base ne garde ainsi qu'une seule
    # orthographe par intitule.
    if "situation" in champs:
        retenu = _canoniser(champs["situation"], SITUATIONS)
        if retenu is None:
            return jsonify({"erreur": "Situation inconnue."}), 400
        champs["situation"] = retenu

    if "niveau_etudes" in champs:
        retenu = niveau_retenu(champs["niveau_etudes"])
        if retenu is None:
            return jsonify({"erreur": "Niveau d'études inconnu."}), 400
        champs["niveau_etudes"] = retenu

    # Le domaine, lui, reste ouvert : voir domaine_retenu.
    if "domaine" in champs:
        retenu = domaine_retenu(champs["domaine"])
        if retenu is None:
            return jsonify({"erreur": "Précisez votre domaine ou métier "
                                      "en toutes lettres."}), 400
        champs["domaine"] = retenu

    # Les noms passent par la même mise en forme qu'à l'inscription :
    # une modification de profil ne doit pas rouvrir la porte que
    # l'inscription vient de fermer.
    for cle in ("prenom", "nom"):
        if cle not in champs:
            continue
        propre = normaliser_nom(champs[cle])
        if not propre:
            return jsonify({"erreur":
                "Le prénom et le nom doivent contenir des lettres."}), 400
        champs[cle] = propre

    # Plusieurs objectifs a la fois. Personne ne cherche une seule chose
    # : on prepare un depart a l'etranger tout en cherchant un stage, on
    # apprend un metier tout en voulant gerer son argent. Le choix
    # unique obligeait a trancher entre des besoins qui coexistent, et
    # la moitie de l'information se perdait.
    if "objectifs" in d or "objectif" in champs:
        recus = d.get("objectifs")
        if recus is None:
            recus = _eclater_objectifs(champs.get("objectif"))
        elif not isinstance(recus, list):
            return jsonify({"erreur": "Les objectifs doivent être une "
                                      "liste."}), 400
        retenus = []
        for brut in recus[:LIMITE_OBJECTIFS]:
            officiel = _canoniser(brut, OBJECTIFS)
            if officiel is None:
                return jsonify({"erreur": "Objectif inconnu."}), 400
            if officiel and officiel not in retenus:
                retenus.append(officiel)
        champs["objectif"] = SEPARATEUR_OBJECTIFS.join(retenus)

    # L'etablissement reste libre : aucune liste ne contiendra l'atelier
    # ou quelqu'un apprend son metier.
    if "telephone" in champs:
        numero = normaliser_telephone(champs["telephone"])
        if numero is None:
            return jsonify({"erreur":
                "Numéro de téléphone invalide : entre "
                f"{LONGUEUR_TEL_MIN} et {LONGUEUR_TEL_MAX} chiffres, "
                "avec ou sans indicatif."}), 400
        champs["telephone"] = numero

    # La photo est stockée dans la base, faute de disque persistant sur
    # l'hébergement. La page la réduit avant de l'envoyer ; cette borne
    # est le garde-fou, pour qu'un client modifié ne puisse pas y loger
    # une image entière.
    if "photo_url" in champs:
        photo = str(champs["photo_url"]).strip()
        if len(photo) > LONGUEUR_PHOTO:
            return jsonify({"erreur":
                "Image trop lourde. Choisissez une photo plus légère."}), 400
        if photo and not photo.startswith(("data:image/", "http://",
                                           "https://")):
            return jsonify({"erreur": "Format d'image non reconnu."}), 400
        champs["photo_url"] = photo

    if "etablissement" in champs:
        champs["etablissement"] = \
            str(champs["etablissement"]).strip()[:LONGUEUR_ETABLISSEMENT]
    if "filiere" in champs:
        champs["filiere"] = \
            " ".join(str(champs["filiere"]).split())[:LONGUEUR_FILIERE]
    if champs.get("profil_pro"):
        lien = champs["profil_pro"].strip()
        if lien and not lien.startswith(("https://", "http://")):
            return jsonify({
                "erreur": "Le lien professionnel doit commencer par https://"
            }), 400
        champs["profil_pro"] = lien[:255]
    for cle in ("situation", "langues"):
        if cle in champs and champs[cle] is not None:
            champs[cle] = str(champs[cle])[:120]
    if "objectif" in champs and champs["objectif"] is not None:
        # Plus long que les autres : il porte jusqu'a quatre intitules.
        champs["objectif"] = str(champs["objectif"])[:LONGUEUR_OBJECTIFS]
    if champs:
        fragments = ", ".join(f"{k} = %s" for k in champs)
        executer(
            f"UPDATE utilisateur SET {fragments} WHERE id_utilisateur = %s",
            list(champs.values()) + [id_user],
            commit=True,
        )

    # Secteurs d'intérêt : remplacement atomique
    if "secteurs" in d:
        with curseur(commit=True) as cur:
            cur.execute(
                "DELETE FROM utilisateur_secteur WHERE id_utilisateur = %s",
                (id_user,),
            )
            for id_sect in d["secteurs"] or []:
                cur.execute(
                    """INSERT INTO utilisateur_secteur
                          (id_utilisateur, id_secteur) VALUES (%s, %s)""",
                    (id_user, int(id_sect)),
                )

    # Détails mentor (si applicable)
    if g.utilisateur["role"] == "mentor":
        dispo = d.get("dispo")
        anciennete = d.get("anciennete")
        if dispo in ("disponible", "occupe", "absent"):
            executer(
                "UPDATE mentor_details SET dispo = %s WHERE id_utilisateur = %s",
                (dispo, id_user), commit=True,
            )
        if anciennete is not None:
            executer(
                """UPDATE mentor_details SET anciennete = %s
                    WHERE id_utilisateur = %s""",
                (anciennete[:40], id_user), commit=True,
            )

    return jsonify(_charger_profil(id_user))


def _est_en_ligne(derniere_activite):
    """Vrai si ce compte a agi dans les dernieres minutes."""
    if not derniere_activite:
        return False
    from datetime import datetime, timedelta
    from utils.auth_helpers import DELAI_EN_LIGNE
    texte = str(derniere_activite).replace("T", " ")[:19]
    try:
        vue = datetime.strptime(texte, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return datetime.utcnow() - vue < timedelta(seconds=DELAI_EN_LIGNE)


def _charger_profil(id_user, public=False):
    base = recuperer_un(
        """SELECT u.id_utilisateur, u.prenom, u.nom, u.email,
                  u.role, u.photo_url, u.bio, u.etudes, u.ville,
                  u.id_pays, p.libelle AS pays,
                  u.est_admin, u.doit_changer_mdp, u.cree_le,
                  u.derniere_activite,
                  u.situation, u.objectif, u.langues, u.profil_pro,
                  u.niveau_etudes, u.domaine, u.filiere, u.etablissement,
                  u.telephone,
                  u.email_verifie,
                  md.est_verifie, md.dispo, md.anciennete,
                  md.delai_reponse, md.note_moyenne, md.nb_reponses
             FROM utilisateur u
        LEFT JOIN pays p           ON p.id_pays = u.id_pays
        LEFT JOIN mentor_details md ON md.id_utilisateur = u.id_utilisateur
            WHERE u.id_utilisateur = %s""",
        (id_user,),
    )
    if not base:
        return None
    if public:
        base.pop("email", None)
        # Le numéro ne se montre pas au tout-venant : il sert à joindre
        # quelqu'un, pas à être collecté. Seule la personne le voit sur
        # son propre profil.
        base.pop("telephone", None)
        base.pop("est_admin", None)
        # Ne jamais révéler qu'un compte tourne encore avec un mot de
        # passe temporaire : ce serait désigner une cible.
        base.pop("doit_changer_mdp", None)

    # La colonne reste une chaine, pour rester lisible dans un export et
    # cherchable avec un simple LIKE. L'interface recoit en plus la
    # liste deja decoupee : lui faire refaire ce decoupage exposerait a
    # ce que les deux cotes s'accordent mal sur le separateur.
    base["objectifs"] = _eclater_objectifs(base.get("objectif"))

    # Statistiques reelles, comptees plutot que denormalisees. Le
    # compteur de mentor_details n'existe que pour les referents : le
    # servir a tout le monde affichait « 0 Reponses » sur le profil d'un
    # administrateur, ce qui donne l'impression d'un compte vide ou
    # casse. Chaque role a ses chiffres, et l'interface choisit ceux qui
    # ont un sens pour lui.
    def _compter(requete):
        return (recuperer_un(requete, (id_user,)) or {}).get("n", 0)

    base["nb_questions"] = _compter(
        "SELECT COUNT(*) AS n FROM question WHERE id_auteur = %s")
    base["nb_reponses_publiees"] = _compter(
        "SELECT COUNT(*) AS n FROM reponse WHERE id_auteur = %s")
    base["nb_utiles_recus"] = _compter(
        """SELECT COUNT(*) AS n FROM marquage_reponse m
             JOIN reponse r ON r.id_reponse = m.id_reponse
            WHERE r.id_auteur = %s AND m.type_marquage = 'utile'""")

    # Presence. Calculee ici plutot que dans le navigateur : celui-ci ne
    # connait ni l'heure du serveur ni le seuil retenu, et deux
    # navigateurs mal regles afficheraient deux etats differents pour la
    # meme personne.
    base["en_ligne"] = _est_en_ligne(base.get("derniere_activite"))
    # L'heure exacte de la derniere venue ne regarde que la personne
    # elle-meme : suivre les allees et venues de quelqu'un a la minute
    # pres n'a pas a etre offert a tous.
    if public:
        base.pop("derniere_activite", None)

    base["secteurs"] = recuperer_tous(
        """SELECT s.id_secteur, s.libelle, s.couleur
             FROM utilisateur_secteur us
             JOIN secteur s ON s.id_secteur = us.id_secteur
            WHERE us.id_utilisateur = %s
         ORDER BY s.libelle""",
        (id_user,),
    )
    base["experiences"] = recuperer_tous(
        """SELECT id_experience, type_experience, intitule, periode, ordre
             FROM experience
            WHERE id_utilisateur = %s
         ORDER BY ordre, id_experience""",
        (id_user,),
    )
    return base


@bp_profil.get("/statistiques")
def statistiques_publiques():
    """Chiffres réels de la plateforme, pour la page d'accueil.

    La page annonçait des nombres écrits en dur, sans rapport avec la
    base. Afficher des chiffres inventés sur un site public engage la
    crédibilité du projet, et un visiteur qui s'inscrit après avoir lu
    « 12 000 membres » découvre autre chose.

    Seuls des agrégats sont exposés : aucun nom, aucune adresse. Les
    comptes désactivés sont exclus, sans quoi une suspension gonflerait
    encore le total.
    """
    def compter(requete):
        return (recuperer_un(requete) or {}).get("n", 0) or 0

    return jsonify({
        "membres": compter(
            "SELECT COUNT(*) AS n FROM utilisateur WHERE est_actif = 1"),
        "mentors": compter(
            "SELECT COUNT(*) AS n FROM utilisateur "
            "WHERE role = 'mentor' AND est_actif = 1"),
        "questions": compter("SELECT COUNT(*) AS n FROM question"),
        "reponses": compter("SELECT COUNT(*) AS n FROM reponse"),
    })


# ============================================================
# PRÉFÉRENCES DE NOTIFICATION
# ============================================================

# Clés reconnues et valeur par défaut de chacune. Une liste fermée est
# indispensable : sans elle, n'importe quel client pourrait faire
# grossir indéfiniment la colonne en y écrivant des clés arbitraires.
PREFERENCES_CONNUES = {
    "reponse_question": True,
    "reactions": True,
    "questions_secteur": False,
    "infolettre": False,
    # Le résumé de ce qui bouge, au plus une fois tous les deux jours.
    # Activé par défaut : c'est ce qui ramène des gens qui n'ont aucune
    # raison de revenir d'eux-mêmes, et chaque message porte son lien de
    # désinscription.
    "resume_activite": True,
}
CANAUX = ("app", "email")


def _preferences_par_defaut():
    return {canal: dict(PREFERENCES_CONNUES) for canal in CANAUX}


def _lire_preferences(id_user):
    """Préférences enregistrées, complétées par les valeurs par défaut.

    Un compte créé avant l'ajout de la colonne, ou dont le contenu
    serait illisible, retombe sur les valeurs par défaut plutôt que de
    faire échouer l'affichage.
    """

    prefs = _preferences_par_defaut()
    ligne = recuperer_un(
        "SELECT preferences_notif FROM utilisateur WHERE id_utilisateur = %s",
        (id_user,),
    )
    brut = (ligne or {}).get("preferences_notif")
    if not brut:
        return prefs
    try:
        enregistre = json.loads(brut)
    except (ValueError, TypeError):
        return prefs

    for canal in CANAUX:
        valeurs = enregistre.get(canal) or {}
        for cle in PREFERENCES_CONNUES:
            if cle in valeurs:
                prefs[canal][cle] = bool(valeurs[cle])
    return prefs


@bp_profil.get("/preferences")
@connexion_requise
def lire_preferences():
    return jsonify(_lire_preferences(g.utilisateur["id_utilisateur"]))


@bp_profil.put("/preferences")
@connexion_requise
def enregistrer_preferences():
    """Enregistre les préférences de notification.

    Seules les clés connues sont retenues : le contenu écrit en base est
    donc borné, quoi qu'envoie le client.
    """

    recu = request.get_json(silent=True) or {}
    prefs = _preferences_par_defaut()
    for canal in CANAUX:
        valeurs = recu.get(canal) or {}
        for cle in PREFERENCES_CONNUES:
            if cle in valeurs:
                prefs[canal][cle] = bool(valeurs[cle])

    executer(
        "UPDATE utilisateur SET preferences_notif = %s WHERE id_utilisateur = %s",
        (json.dumps(prefs), g.utilisateur["id_utilisateur"]),
        commit=True,
    )
    return jsonify(prefs)


# ============================================================
# SUPPRESSION DU COMPTE
# ============================================================

@bp_profil.delete("/moi")
@connexion_requise
def supprimer_mon_compte():
    """Supprime définitivement le compte de la personne connectée.

    Trois garde-fous, parce que l'opération est irréversible :

    1. le mot de passe est redemandé, ce qui empêche un tiers d'effacer
       un compte depuis une session laissée ouverte ;
    2. la personne recopie un mot exact, ce qui écarte le clic
       accidentel sur un bouton rouge ;
    3. le dernier administrateur ne peut pas se supprimer, sans quoi la
       plateforme deviendrait ingérable sans intervention en base.

    Les questions et réponses partent avec le compte, par cascade
    déclarée dans le schéma. C'est ce que dit la page de
    confidentialité, et c'est ce qui se passe.
    """
    from utils.auth_helpers import verifier_mot_de_passe, supprimer_cookie_session

    d = request.get_json(silent=True) or {}
    motdepasse = d.get("mot_de_passe") or ""
    confirmation = (d.get("confirmation") or "").strip().upper()

    if confirmation != "SUPPRIMER":
        return jsonify({
            "erreur": "Recopiez le mot SUPPRIMER pour confirmer."}), 400

    id_user = g.utilisateur["id_utilisateur"]
    ligne = recuperer_un(
        "SELECT mot_de_passe, est_admin FROM utilisateur "
        "WHERE id_utilisateur = %s", (id_user,))
    if not ligne:
        return jsonify({"erreur": "Compte introuvable."}), 404

    if not verifier_mot_de_passe(motdepasse, ligne["mot_de_passe"]):
        return jsonify({"erreur": "Mot de passe incorrect."}), 401

    if ligne.get("est_admin"):
        restants = (recuperer_un(
            "SELECT COUNT(*) AS n FROM utilisateur "
            "WHERE est_admin = 1 AND est_actif = 1 "
            "AND id_utilisateur <> %s", (id_user,)) or {}).get("n", 0)
        if not restants:
            return jsonify({
                "erreur": "Vous êtes le dernier administrateur. Nommez "
                          "quelqu'un d'autre avant de supprimer ce compte."
            }), 409

    executer("DELETE FROM utilisateur WHERE id_utilisateur = %s",
             (id_user,), commit=True)

    reponse = jsonify({"ok": True})
    return supprimer_cookie_session(reponse)


@bp_profil.get("/moi/donnees")
@connexion_requise
def exporter_mes_donnees():
    """Renvoie tout ce que la plateforme conserve sur cette personne.

    Pouvoir emporter ses données est le pendant du droit de les faire
    effacer : sans cela, supprimer son compte revient à tout perdre sans
    savoir ce qu'on perd.
    """
    id_user = g.utilisateur["id_utilisateur"]

    # Toutes les colonnes du profil, sans exception : un export qui
    # annonce « tout ce que la plateforme conserve » et en omet une
    # partie vaut moins que pas d'export du tout.
    profil = recuperer_un(
        """SELECT prenom, nom, email, role, bio, etudes, ville,
                  photo_url, cree_le, derniere_co, email_verifie,
                  situation, objectif, langues, profil_pro,
                  niveau_etudes, domaine, filiere, etablissement, telephone
             FROM utilisateur WHERE id_utilisateur = %s""", (id_user,))

    return jsonify({
        "profil": profil or {},
        "preferences": _lire_preferences(id_user),
        "questions": recuperer_tous(
            "SELECT titre, corps, publiee_le FROM question "
            "WHERE id_auteur = %s ORDER BY publiee_le", (id_user,)),
        "reponses": recuperer_tous(
            "SELECT contenu, cree_le FROM reponse "
            "WHERE id_auteur = %s ORDER BY cree_le", (id_user,)),
        "secteurs": recuperer_tous(
            "SELECT s.libelle FROM secteur s "
            "JOIN utilisateur_secteur us ON us.id_secteur = s.id_secteur "
            "WHERE us.id_utilisateur = %s", (id_user,)),
    })


# ============================================================
# RÉSUMÉ PÉRIODIQUE
# ============================================================

@bp_profil.get("/resume/stop")
def desinscrire_resume():
    """Désinscription du résumé, sans avoir à se connecter.

    Un désabonnement difficile ne se fait pas : il se règle en marquant
    l'expéditeur comme indésirable, ce qui coûte au domaine entier. Le
    lien porte donc une signature dérivée de la clé du serveur, valable
    sans session et inutilisable pour désinscrire quelqu'un d'autre.
    """
    from services.resume import jeton_valide

    try:
        id_user = int(request.args.get("u") or 0)
    except (TypeError, ValueError):
        id_user = 0
    if not id_user or not jeton_valide(id_user, request.args.get("j")):
        return jsonify({"erreur": "Lien de désinscription invalide."}), 400

    prefs = _lire_preferences(id_user)
    prefs.setdefault("email", {})["resume_activite"] = False
    executer(
        "UPDATE utilisateur SET preferences_notif = %s WHERE id_utilisateur = %s",
        (json.dumps(prefs), id_user), commit=True)
    return jsonify({
        "ok": True,
        "message": "C'est fait : vous ne recevrez plus le résumé de "
                   "l'activité. Les réponses à vos propres questions "
                   "continuent de vous parvenir.",
    })
