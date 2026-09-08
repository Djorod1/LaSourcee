# LaSourcee

> Plateforme de mentorat pour la jeunesse.
> Une question, une réponse, un acte de mentorat.

LaSourcee met en relation des étudiants en demande d'orientation avec des
mentors expérimentés, autour de trois axes : **mentorat académique**,
**orientation de carrière** et **éducation financière**.

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
./demarrer.sh tests      # suite de tests d'intégration (98 tests)
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

Deux scripts vérifient l'application avant mise en ligne :

```bash
cd backend
python tests_integration.py     # 98 tests fonctionnels
DATABASE_URL="postgresql://..." python tests_deploiement.py   # 49 vérifications
```

`tests_deploiement.py` reproduit les conditions de Vercel : point d'entrée
serverless, PostgreSQL, proxy HTTPS, cookies, adresse IP réelle du
visiteur, en-têtes de sécurité, non-exposition du code source.

Les deux suites tournent automatiquement sur chaque pull request et sur
chaque poussée vers `main` (`.github/workflows/tests.yml`), sur SQLite
puis sur PostgreSQL 16.

---

## Stack technique

| Couche | Choix |
|---|---|
| Frontend | HTML / CSS / JavaScript, sans framework |
| Backend | Python 3.10+ — Flask 3, 60 routes HTTP |
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
│   ├── tests_integration.py  98 tests fonctionnels
│   ├── tests_deploiement.py  49 vérifications de mise en ligne
│   ├── models/db.py          Accès uniforme SQLite / PostgreSQL / MySQL
│   ├── utils/
│   │   ├── auth_helpers.py     bcrypt, sessions, cookies, décorateurs
│   │   ├── securite.py         politique mdp, anti-force-brute, en-têtes
│   │   ├── email.py            envoi SMTP réel (ou console en dev)
│   │   ├── urls.py             URL publiques des liens d'e-mail
│   │   ├── dates.py            comparaison de dates multi-moteurs
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
│   └── services/suggestions.py  suggestion de mentors
│
└── database/
    ├── schema_sqlite.sql      22 tables — développement
    ├── schema_postgres.sql    22 tables — production
    ├── schema.sql             22 tables — MySQL
    └── migration_v2.sql
```

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
- `DEBUG` derrière une variable d'environnement, jamais actif par défaut.

---

## Rôles

| Rôle | Capacités |
|---|---|
| `visiteur` | consulter le fil public |
| `etudiant` | publier des questions, commenter, mettre en favori, suivre des mentors |
| `mentor` | répondre aux questions, statut de vérification, profil public enrichi |
| `admin` | modération, suspension, validation des candidatures de mentor |
| `super_admin` | création d'autres administrateurs, journal d'audit complet |

Un mentor n'est pas un administrateur : il ne dispose d'aucun droit sur
les comptes ni sur les contenus des autres. Le passage au rôle mentor
suppose une candidature validée par un administrateur.

---

## Documentation

| Fichier | Contenu |
|---|---|
| [`DEPLOIEMENT.md`](DEPLOIEMENT.md) | mise en ligne sur Vercel, pas à pas |
| [`HOSTINGER.md`](HOSTINGER.md) | domaine acheté chez Hostinger : où héberger l'application |
| [`MISE_EN_SERVICE.md`](MISE_EN_SERVICE.md) | configuration SMTP, OAuth, administration |
| [`AUDIT.md`](AUDIT.md) | audit technique complet |
| [`STRATEGIE.md`](STRATEGIE.md) | vision produit et analyse comparative |
| [`PLAN_PRODUIT.md`](PLAN_PRODUIT.md) | feuille de route |
