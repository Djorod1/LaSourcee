# LaSourcee

> Plateforme de mentorat pour la jeunesse.
> Une question, une réponse, un acte de mentorat.

LaSourcee met en relation des **bénéficiaires** en demande d'orientation
avec des **référents** expérimentés, autour de trois axes : **mentorat
académique**, **orientation de carrière** et **éducation financière**.

Adresse publique : **[lasourcee.org](https://lasourcee.org)**

**Aucun compte de démonstration.** Tous les comptes sont créés par
inscription réelle, toutes les données sont persistées en base.

---

## Démarrage local en trois commandes

**Prérequis** : Python 3.10 ou plus. Aucun serveur de base de données à
installer.

```bash
./demarrer.sh installer   # une fois : crée le venv et installe les dépendances
./demarrer.sh             # démarre le serveur sur http://localhost:5000
```

Au premier lancement, la base SQLite est créée automatiquement avec le
schéma complet et les référentiels (12 secteurs d'activité, 18 pays).
Elle ne contient **aucun utilisateur** : le premier compte est celui que
vous créerez depuis la page d'accueil.

Autres sous-commandes :

```bash
./demarrer.sh tests      # toutes les vérifications (voir « Vérifications »)
./demarrer.sh reset      # supprime la base locale et la recrée
./demarrer.sh postgres   # démarre sur PostgreSQL (DATABASE_URL requis)
./demarrer.sh aide
```

---

## Comptes administrateurs

Ils se créent avec un script dédié, qui génère un mot de passe temporaire
différent pour chacun et envoie l'invitation par e-mail :

```bash
cd backend
python gerer_admins.py creer
```

| Administrateur | Adresse |
|---|---|
| Kouessi TOYOHOUNSOGBE | `toyohounsogbe1@gmail.com` |
| Théophile DOUNON | `theophiledounon@gmail.com` |
| Mariano DOSSOUGAN | `espoirmariano@gmail.com` |
| Rodrigue DJOSSOU | `rodriguedjossou93@gmail.com` |

Le mot de passe temporaire doit être changé à la première connexion.

```bash
python gerer_admins.py lister                      # état des comptes
python gerer_admins.py ajouter prenom nom email    # nouvel administrateur
python gerer_admins.py reinitialiser email         # nouveau mot de passe
python gerer_admins.py tester-email adresse        # vérifier la config SMTP
```

Sans configuration SMTP, les mots de passe s'affichent dans la console et
sont à transmettre manuellement. Vérifiez toujours l'envoi avec
`tester-email` **avant** de lancer `creer`.

---

## Authentification

Trois moyens de se connecter :

1. **E-mail + mot de passe** — toujours disponible ;
2. **Google** — activé par `GOOGLE_CLIENT_ID` ;
3. **LinkedIn** — activé par `LINKEDIN_CLIENT_ID` et `LINKEDIN_CLIENT_SECRET`.

Si Google ou LinkedIn n'est pas configuré, le bouton correspondant est
masqué côté interface et l'API répond par une erreur explicite (503)
plutôt que par une erreur serveur. La marche à suivre pour obtenir les
identifiants est détaillée dans `backend/.env.example` et dans
`DEPLOIEMENT.md`.

### Vérification d'adresse e-mail

À l'inscription, un message de confirmation part vers l'adresse
renseignée. Par défaut le compte reste utilisable immédiatement ; pour
imposer la confirmation avant toute connexion :

```env
VERIFICATION_EMAIL_OBLIGATOIRE=1
```

### Mot de passe oublié

Un lien valable une heure est envoyé par e-mail. Le changement de mot de
passe **invalide toutes les sessions actives**, y compris celle qui a
demandé la réinitialisation.

---

## Mise en ligne

La procédure complète est dans **[`DEPLOIEMENT.md`](DEPLOIEMENT.md)**.
En résumé :

| Hébergement | Base de données | Remarque |
|---|---|---|
| **Vercel** (retenu) | PostgreSQL externe obligatoire | disque éphémère : un fichier SQLite serait perdu |
| Domaine | `lasourcee.org` | DNS et certificat gérés par Vercel |
| VPS / serveur dédié | SQLite ou PostgreSQL | gunicorn + nginx |
| GitHub Pages | — | **impossible** : aucun code serveur n'y est exécuté |
| Hostinger mutualisé | — | **impossible** : n'exécute que PHP, pas Python (voir [`HOSTINGER.md`](HOSTINGER.md)) |

GitHub Pages ne sert que des fichiers. C'est la cause de l'erreur
`405 Method Not Allowed` obtenue lors des premiers essais d'inscription :
il n'y avait aucun serveur pour traiter la requête.

### Vérifications

Une seule commande les lance toutes :

```bash
./demarrer.sh tests
DATABASE_URL="postgresql://..." ./demarrer.sh tests   # ajoute PostgreSQL
```

| Suite | Portée |
|---|---|
| `tests_redaction.py` | aucun tiret cadratin dans les 18 fichiers dont le texte atteint un utilisateur |
| `tests_contraste.py` | 15 couples de couleurs au niveau WCAG AA, en clair comme en sombre |
| `tests_integration.py` | 383 tests fonctionnels, sur SQLite puis sur PostgreSQL |
| `tests_deploiement.py` | 85 vérifications de mise en ligne |

Sans `DATABASE_URL`, les deux dernières lignes sont annoncées comme non
lancées plutôt que passées sous silence.

`tests_deploiement.py` reproduit les conditions de Vercel : point d'entrée
serverless, PostgreSQL, proxy HTTPS, cookies, adresse IP réelle du
visiteur, en-têtes de sécurité, non-exposition du code source.

Les suites tournent automatiquement sur chaque pull request et sur
chaque poussée vers `main` (`.github/workflows/tests.yml`), sur SQLite
puis sur PostgreSQL 16.

---

## Stack technique

| Couche | Choix |
|---|---|
| Frontend | HTML / CSS / JavaScript, sans framework |
| Backend | Python 3.10+ — Flask 3, 79 routes HTTP |
| Base | SQLite, PostgreSQL ou MySQL selon `DB_TYPE` (tests automatisés sur les deux premiers) |
| Authentification | Sessions serveur, bcrypt 12 tours, OAuth Google et LinkedIn |

Le SQL est écrit à la main, sans ORM. Toutes les requêtes du code métier
utilisent le paramètre `%s` ; la couche d'accès traduit le dialecte selon
le moteur, de sorte qu'aucune route n'a à savoir sur quelle base elle
tourne.

Le choix du JavaScript sans framework est délibéré : l'application tient
dans un seul document, ne nécessite aucune étape de compilation, et se
déploie tel quel sur un CDN. Le backend Flask reste indépendant du
frontend et pourrait servir une autre interface sans modification.

---

## Structure du dépôt

```
.
├── index.html                Application
├── verifier-email.html       Confirmation d'adresse e-mail
├── reinitialiser.html        Réinitialisation de mot de passe
├── script.js                 Logique applicative
├── api.js                    Client HTTP du backend
├── styles.css                Feuille de style
├── robots.txt                Directives d'indexation
├── sitemap.xml               Plan du site
├── assets/                   Logo, symbole, favicon, image de partage
├── demarrer.sh               Script de démarrage local
│
├── vercel.json               Routage et build de la mise en ligne
├── requirements.txt          Dépendances Python (lues par Vercel)
├── api/index.py              Point d'entrée serverless
│
├── backend/
│   ├── app.py                Application Flask, erreurs, fichiers statiques
│   ├── config.py             Configuration et diagnostic de démarrage
│   ├── gerer_admins.py       Gestion des comptes administrateurs
│   ├── tests_integration.py  383 tests fonctionnels
│   ├── tests_deploiement.py  85 vérifications de mise en ligne
│   ├── tests_redaction.py    absence de tiret dans les textes visibles
│   ├── tests_contraste.py    lisibilité des couleurs (WCAG AA)
│   ├── models/db.py          Accès uniforme SQLite / PostgreSQL / MySQL
│   │                         + ajout des colonnes manquantes au démarrage
│   ├── utils/
│   │   ├── auth_helpers.py     bcrypt, sessions, cookies, décorateurs
│   │   ├── securite.py         politique mdp, anti-force-brute, en-têtes
│   │   ├── email.py            envoi SMTP réel (ou console en dev)
│   │   ├── urls.py             URL publiques des liens d'e-mail
│   │   ├── dates.py            comparaison de dates multi-moteurs
│   │   ├── permissions.py      droits d'administration par domaine
│   │   └── audit.py            journal des actions d'administration
│   ├── routes/
│   │   ├── auth.py             inscription, connexion, mot de passe
│   │   ├── oauth.py            Google et LinkedIn
│   │   ├── profil.py           profils et référentiels
│   │   ├── questions.py        publication, fil, favoris, signalements
│   │   ├── reponses.py         réponses
│   │   ├── mentors.py          annuaire et suivi
│   │   ├── candidature_mentor.py  candidature et validation
│   │   ├── messagerie.py       conversations privées
│   │   ├── notifications.py    notifications
│   │   ├── recherche.py        recherche globale
│   │   └── admin.py            tableau de bord et modération
│   └── services/
│       ├── suggestions.py      suggestion de référents
│       ├── notifications.py    dépôt des notifications
│       └── amorcage.py         création du premier admin par variables
│
└── database/
    ├── schema_sqlite.sql      24 tables — développement
    ├── schema_postgres.sql    24 tables — production
    ├── schema.sql             24 tables — MySQL
    ├── migration_v2.sql
    └── migration_v3.sql       profils enrichis, préférences, vérification
```

Les fichiers de schéma ne s'appliquent qu'à la **création** de la base :
une base déjà en service ne les rejoue jamais. C'est pourquoi les
colonnes attendues sont aussi listées dans `models/db.py` et ajoutées au
démarrage si elles manquent. Sans cela, tout déploiement introduisant une
colonne casserait la production, alors que les tests, sur une base neuve,
resteraient verts.

---

## Sécurité

- Mots de passe hachés avec **bcrypt** (12 tours) ;
- politique de robustesse à la création et au changement ;
- **anti-force-brute persisté en base** : 5 échecs de connexion en
  15 minutes → blocage temporaire, la clé combinant l'adresse e-mail et
  l'adresse IP réelle du visiteur. Le compteur vit en base et non en
  mémoire : sur un hébergement sans état comme Vercel, chaque requête
  peut être traitée par une instance différente, et un compteur en
  mémoire ne s'incrémenterait jamais ;
- **débit borné sur l'inscription et le mot de passe oublié** : sans
  cela, un robot créerait des comptes en série — et n'importe qui
  pourrait inonder la boîte d'un tiers de messages de réinitialisation.
  Le seuil d'inscription (30 par adresse IP et par quart d'heure, réglable
  par `MAX_INSCRIPTIONS_PAR_IP`) reste compatible avec une salle de classe
  entière derrière une seule adresse publique ;
- **anti-énumération** : la demande de réinitialisation répond de façon
  identique que l'adresse existe ou non ;
- sessions par **jeton opaque de 64 octets**, cookie `HttpOnly`,
  `SameSite=Lax`, et `Secure` dès que la connexion est en HTTPS ;
- jetons de vérification et de réinitialisation à usage unique, expirant
  respectivement en 24 heures et 1 heure ;
- changement de mot de passe → **révocation de toutes les sessions** ;
- SQL **entièrement paramétré**, aucune concaténation ;
- **journal d'audit** des actions d'administration (qui, quoi, quand, IP) ;
- en-têtes de sécurité sur toutes les réponses, dont une politique de
  sécurité du contenu restreignant les origines externes au strict
  nécessaire ;
- gestionnaire d'erreurs global : aucune trace d'exécution ne remonte au
  client ;
- **le code source n'est jamais servi** : seuls les fichiers du frontend
  sont accessibles, les tentatives de remontée d'arborescence sont
  refusées ;
- **identité externe vérifiée avant rattachement** : une connexion Google
  ou LinkedIn n'est reliée à un compte existant que si le fournisseur
  atteste que l'adresse est vérifiée. Sans ce contrôle, quiconque
  créerait chez un fournisseur une identité portant l'adresse d'un membre
  entrerait dans son compte ;
- `DEBUG` derrière une variable d'environnement, jamais actif par défaut.

### Données personnelles

- **suppression du compte en libre-service**, protégée par la saisie du
  mot de passe et une confirmation explicite ;
- **export de ses propres données** au format JSON, depuis le profil ;
- réglages de notification respectés à l'émission, et non filtrés à
  l'affichage : une case décochée empêche la notification d'exister.

---

## Rôles

L'interface parle de **Référent** et de **Bénéficiaire**. En base, les
valeurs historiques `mentor` et `etudiant` ont été conservées : les
renommer aurait imposé une migration de toutes les lignes existantes pour
un gain nul côté utilisateur, qui ne voit jamais ces chaînes.

| Rôle en base | Nom affiché | Capacités |
|---|---|---|
| `visiteur` | Visiteur | consulter le fil public |
| `etudiant` | Bénéficiaire | publier des questions, commenter, mettre en favori, suivre des référents |
| `mentor` | Référent | répondre aux questions, statut de vérification, profil public enrichi |
| `admin` | Administrateur | modération, suspension, validation des candidatures |
| `super_admin` | Administrateur principal | création d'autres administrateurs, journal d'audit complet |

Un référent n'est pas un administrateur : il ne dispose d'aucun droit sur
les comptes ni sur les contenus des autres. Le passage au rôle référent
suppose une candidature validée par un administrateur : **le dépôt seul
ne l'accorde pas**, et l'annuaire ne présente que des dossiers examinés.

### Droits d'administration

Un seul drapeau ouvrait autrefois tous les écrans. Confier la modération
revenait donc à confier aussi le journal d'audit, les adresses de tous
les membres et la configuration du serveur. Huit droits se donnent
maintenant un par un :

| Droit | Ce qu'il ouvre |
|---|---|
| `utilisateurs` | consulter et gérer les comptes |
| `referents` | examiner les candidatures |
| `signalements` | modérer les contenus signalés |
| `categories` | gérer les secteurs d'activité |
| `audit` | consulter le journal des actions d'administration |
| `diagnostic` | voir la configuration du serveur |
| `export` | télécharger les données de la plateforme |
| `administrateurs` | nommer des administrateurs et fixer leurs droits |

Deux règles gouvernent le reste. Le **super administrateur a tout**, sans
qu'on ait à l'écrire : lui retirer un droit par mégarde fermerait la
porte à la seule personne capable de la rouvrir. Une **liste vide
n'accorde rien** ; un compte antérieur à ces droits, dont la colonne vaut
`NULL`, les conserve tous, faute de quoi une mise à jour verrouillerait
l'équipe hors de son propre site.

Le menu n'affiche que les écrans réellement accessibles : proposer un
onglet qui répondra 403 fait passer un refus de droits pour une panne.

### Export des données

Huit jeux s'exportent en CSV ou en JSON depuis l'administration, plus le
dossier complet d'une personne. Aucun mot de passe ni jeton de session
n'y figure : un export circule et s'oublie. Le CSV porte un BOM et un
point-virgule, pour s'ouvrir directement dans un tableur francophone.

### Données d'analyse

Les tables métier disent l'état présent de la plateforme. Elles ne
disent pas ce qui s'y est passé, et c'est justement ce qu'il faut pour
mesurer, comparer, ou entraîner un modèle : une série, pas une
photographie.

La table `evenement` enregistre une ligne par action notable, avec le
rôle de la personne **au moment de l'action** : il change avec le temps,
et une analyse postérieure attribuerait sinon toute l'activité passée
d'un référent au rôle qu'il porte aujourd'hui. S'y ajoutent, sur chaque
question, le nombre de consultations et la date de la première réponse,
qui ne se reconstitue pas après coup.

Trois limites sont posées, et elles sont volontaires :

- **aucun contenu écrit par un membre.** On note qu'une question a été
  publiée, pas ce qu'elle disait. Le texte vit dans sa table ; l'y
  recopier le rendrait ineffaçable, et un export d'événements
  deviendrait un export de contenus ;
- **l'identifiant, jamais l'adresse ni le nom.** Un fichier d'événements
  ne doit pas suffire à reconnaître quelqu'un ;
- **suppression en cascade.** Effacer son compte efface son activité,
  sans quoi le droit à l'effacement ne serait qu'un mot.

Ce que la plateforme collecte doit rester annoncé aux membres dans la
politique de confidentialité : une collecte silencieuse, même
techniquement irréprochable, ne l'est pas juridiquement.

---

## Documentation

| Fichier | Contenu |
|---|---|
| [`DEPLOIEMENT.md`](DEPLOIEMENT.md) | mise en ligne sur Vercel, pas à pas |
| [`HOSTINGER.md`](HOSTINGER.md) | domaine acheté chez Hostinger : où héberger l'application |
| [`REFERENCEMENT.md`](REFERENCEMENT.md) | référencement : ce qui est en place, ce qui reste à faire |
| [`MISE_EN_SERVICE.md`](MISE_EN_SERVICE.md) | configuration SMTP, OAuth, administration |
| [`AUDIT.md`](AUDIT.md) | audit technique complet |
| [`STRATEGIE.md`](STRATEGIE.md) | vision produit et analyse comparative |
| [`PLAN_PRODUIT.md`](PLAN_PRODUIT.md) | feuille de route |
