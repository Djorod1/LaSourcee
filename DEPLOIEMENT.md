# Mettre LaSourcee en ligne

Ce guide décrit la mise en production sur **Vercel**, l'hébergeur retenu
pour le projet. Le déploiement sur un serveur classique reste possible et
est décrit à la fin.

Comptez une trentaine de minutes la première fois.

---

## Ce qu'il faut savoir avant de commencer

LaSourcee n'est pas un site statique : c'est une application avec des
comptes, des sessions et une base de données. Deux conséquences directes :

**GitHub Pages ne peut pas héberger ce projet.** GitHub Pages ne sert que
des fichiers ; il n'exécute aucun code serveur. Toute tentative de
création de compte y renvoie l'erreur `405 Method Not Allowed`, car il n'y
a personne pour traiter la requête. C'est précisément l'erreur rencontrée
lors des premiers essais.

**Le stockage de Vercel est éphémère.** Chaque requête peut être traitée
par une nouvelle instance, dont le disque est en lecture seule et remis à
zéro. Un fichier SQLite y serait perdu — avec tous les comptes créés. La
base doit donc être un **PostgreSQL** hébergé séparément.

L'application détecte cette configuration : déployée sur Vercel avec
`DB_TYPE=sqlite`, elle inscrit une erreur explicite dans les logs au lieu
de perdre silencieusement les données.

---

## Étape 1 — Créer la base PostgreSQL

N'importe quel PostgreSQL accessible depuis Internet convient. Trois
options gratuites, par ordre de simplicité :

| Fournisseur | Offre gratuite | Adresse |
|---|---|---|
| **Neon** | 0,5 Go, sans carte bancaire | https://neon.tech |
| **Supabase** | 500 Mo | https://supabase.com |
| **Vercel Postgres** | intégré au tableau de bord Vercel | via l'onglet Storage |

Quel que soit le choix, récupérez la **chaîne de connexion**. Elle
ressemble à :

```
postgresql://utilisateur:motdepasse@ep-xxxx.eu-central-1.aws.neon.tech/lasource?sslmode=require
```

Conservez-la : c'est la valeur de `DATABASE_URL` à l'étape 3.

> Avec Neon, la chaîne se trouve sur le tableau de bord du projet,
> rubrique « Connection string ». Choisissez le format « psql » et
> gardez le paramètre `?sslmode=require`.

Le schéma des 24 tables se crée **tout seul au premier démarrage**. Si
vous préférez le faire à la main, exécutez `database/schema_postgres.sql`
dans la console SQL du fournisseur et mettez `INIT_DB_AUTO=0`.

---

## Étape 2 — Importer le projet dans Vercel

1. Poussez le dépôt sur GitHub s'il ne l'est pas déjà.
2. Sur https://vercel.com, cliquez sur **Add New → Project**.
3. Sélectionnez le dépôt `projet_orienty`.
4. **Framework Preset : `Other`.** Laissez les commandes de build vides —
   `vercel.json` décrit déjà tout ce qu'il faut.
5. Ne cliquez pas encore sur **Deploy** : renseignez d'abord les
   variables d'environnement (étape suivante).

---

## Étape 3 — Déclarer les variables d'environnement

Dans **Settings → Environment Variables**, ajoutez au minimum :

| Variable | Valeur | Pourquoi |
|---|---|---|
| `DB_TYPE` | `postgres` | sans quoi l'application chercherait un fichier SQLite |
| `DATABASE_URL` | la chaîne de l'étape 1 | connexion à la base |
| `SECRET_KEY` | 64 caractères aléatoires | signe l'état OAuth LinkedIn |
| `ENVIRONNEMENT` | `production` | active les contrôles de production |

Pour générer la clé :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> `SECRET_KEY` doit rester **identique** entre les déploiements. Si elle
> change, les connexions LinkedIn en cours échouent au retour.

### Pour que les e-mails partent réellement

Sans ces variables, les messages sont seulement écrits dans les logs :
la confirmation d'adresse et la réinitialisation de mot de passe ne
fonctionneront pas pour les utilisateurs.

| Variable | Exemple |
|---|---|
| `EMAIL_MODE` | `smtp` |
| `SMTP_HOTE` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_UTILISATEUR` | `contact.lasource@gmail.com` |
| `SMTP_MOTDEPASSE` | le mot de passe d'application (16 caractères) |
| `SMTP_EXPEDITEUR` | `LaSourcee <contact.lasource@gmail.com>` |
| `SMTP_SECURITE` | `starttls` |

Avec Gmail, le mot de passe habituel du compte est refusé. Il faut :
activer la validation en 2 étapes, puis **Compte Google → Sécurité →
Mots de passe d'application**, et créer un mot de passe dédié.

### Pour activer les connexions Google et LinkedIn

| Variable | Où l'obtenir |
|---|---|
| `GOOGLE_CLIENT_ID` | https://console.cloud.google.com → Identifiants → ID client OAuth 2.0 |
| `LINKEDIN_CLIENT_ID` | https://www.linkedin.com/developers/apps |
| `LINKEDIN_CLIENT_SECRET` | idem |
| `LINKEDIN_REDIRECT_URI` | `https://lasourcee.org/api/auth/linkedin/callback` |

Côté Google, ajoutez `https://lasourcee.org` aux **origines JavaScript
autorisées**. Côté LinkedIn, ajoutez l'URI de redirection ci-dessus aux
**URLs de redirection autorisées**. Ces adresses doivent correspondre au
caractère près, sinon le fournisseur refuse la connexion.

Tant que le domaine n'est pas encore branché (étape 6), déclarez aussi
l'adresse temporaire en `.vercel.app` que Vercel vous attribue, pour
pouvoir tester ; vous la retirerez ensuite.

Ces variables sont facultatives : sans elles, les boutons correspondants
répondent « service non configuré » (erreur 503 explicite) au lieu de
provoquer une erreur serveur.

---

## Étape 4 — Déployer

Cliquez sur **Deploy**. Le premier déploiement prend deux à trois
minutes : Vercel installe les dépendances de `requirements.txt` et
construit la fonction `api/index.py`.

Vérifiez ensuite, dans cet ordre :

1. **`/api/sante`** sur l'adresse `.vercel.app` fournie doit renvoyer
   `{"statut":"ok","base":"postgres","environnement":"production"}`.
   Un `statut: "degrade"` signifie que la base n'est pas joignable :
   vérifiez `DATABASE_URL`.
2. **La page d'accueil** s'affiche avec sa mise en page et son logo.
3. **Créez un compte de test** : si l'inscription aboutit, la chaîne
   complète (frontend → fonction → PostgreSQL) fonctionne.

En cas d'échec, l'onglet **Logs** du tableau de bord Vercel affiche le
détail. L'application journalise au démarrage tout ce qui est mal
configuré, avec la marche à suivre.

---

## Étape 5 — Créer les comptes administrateurs

Les comptes ne sont pas créés automatiquement : il n'existe **aucun
compte de démonstration** sur la plateforme.

Depuis votre machine, en pointant sur la base de production :

```bash
cd backend
export DB_TYPE=postgres
export DATABASE_URL="postgresql://..."     # la même qu'à l'étape 1
export EMAIL_MODE=smtp                     # + les variables SMTP
export URL_PLATEFORME="https://lasourcee.org"

python gerer_admins.py creer
```

La commande crée les quatre comptes administrateurs, génère pour chacun
un mot de passe temporaire différent et **envoie l'invitation par
e-mail** :

- Kouessi TOYOHOUNSOGBE — `toyohounsogbe1@gmail.com`
- Théophile DOUNON — `theophiledounon@gmail.com`
- Mariano DOSSOUGAN — `espoirmariano@gmail.com`
- Rodrigue DJOSSOU — `rodriguedjossou93@gmail.com`

Le mot de passe temporaire doit être changé à la première connexion.

Autres commandes disponibles :

```bash
python gerer_admins.py lister                      # état des comptes
python gerer_admins.py ajouter prenom nom email    # nouvel administrateur
python gerer_admins.py reinitialiser email         # nouveau mot de passe
python gerer_admins.py tester-email adresse        # vérifier le SMTP
```

> Vérifiez la configuration SMTP avec `tester-email` **avant** de lancer
> `creer` : si l'envoi échoue, les mots de passe temporaires ne sont
> affichés qu'une seule fois, dans la console.

---

## Étape 6 — Brancher le domaine lasourcee.org

Le domaine retenu pour le projet est **lasourcee.org**. Réservez-le chez
un bureau d'enregistrement (Namecheap, Gandi, OVH, Porkbun...) puis
reliez-le à Vercel.

### 1. Ajouter le domaine dans Vercel

**Settings → Domains → Add**, saisissez `lasourcee.org`. Ajoutez ensuite
`www.lasourcee.org` et choisissez **Redirect to lasourcee.org** : les
deux adresses mènent au même site, sans contenu dupliqué.

Vercel affiche alors les enregistrements DNS à créer.

### 2. Créer les enregistrements DNS

Chez votre bureau d'enregistrement, dans la zone DNS de `lasourcee.org` :

| Type | Nom | Valeur |
|---|---|---|
| `A` | `@` | `76.76.21.21` |
| `CNAME` | `www` | `cname.vercel-dns.com` |

**Prenez les valeurs affichées par Vercel plutôt que celles de ce
tableau** : elles peuvent changer, et l'écran de Vercel fait foi.

La propagation DNS prend de quelques minutes à quelques heures. Vercel
émet le certificat HTTPS automatiquement dès qu'il voit les
enregistrements ; aucune manipulation de certificat n'est nécessaire.

### 3. Mettre à jour les variables d'environnement

Une fois le domaine actif, dans **Settings → Environment Variables** :

```
URL_PLATEFORME = https://lasourcee.org
```

Sans cette variable, les liens des e-mails suivent le domaine par lequel
le visiteur est arrivé. Avec elle, ils pointent toujours vers le domaine
définitif — y compris ceux envoyés par les scripts d'administration, qui
tournent hors requête HTTP.

**Redéployez** après avoir ajouté la variable : sur Vercel, les
variables d'environnement ne sont lues qu'au déploiement.

### 4. Déclarer le domaine chez Google et LinkedIn

Les deux fournisseurs refusent toute adresse non déclarée, au caractère
près.

**Google Cloud Console** → Identifiants → votre ID client OAuth 2.0 →
*Origines JavaScript autorisées* :

```
https://lasourcee.org
```

**LinkedIn Developers** → votre app → onglet *Auth* → *URLs de
redirection autorisées* :

```
https://lasourcee.org/api/auth/linkedin/callback
```

Puis, dans Vercel :

```
LINKEDIN_REDIRECT_URI = https://lasourcee.org/api/auth/linkedin/callback
```

### 5. Vérifier

```bash
curl -I https://lasourcee.org                 # 200, et HTTPS valide
curl -I https://www.lasourcee.org             # 308 vers lasourcee.org
curl    https://lasourcee.org/api/sante       # {"statut":"ok",...}
curl    https://lasourcee.org/robots.txt      # doit répondre
```

Vérifiez enfin l'aperçu de partage en collant `https://lasourcee.org`
dans une conversation WhatsApp ou un message LinkedIn : le titre, la
description et l'image `assets/lasource-partage.png` doivent s'afficher.

> Les réseaux sociaux gardent ces aperçus en cache. Si vous modifiez
> l'image ou le texte plus tard, utilisez le *Post Inspector* de LinkedIn
> ou le *Sharing Debugger* de Facebook pour forcer l'actualisation.

### Référencement

`robots.txt` et `sitemap.xml` sont servis à la racine et déclarent
`https://lasourcee.org`. L'API et les pages de jeton (confirmation
d'adresse, réinitialisation) en sont exclues : elles n'ont rien à faire
dans un index de moteur de recherche.

Pour accélérer l'indexation, déclarez le site sur
[Google Search Console](https://search.google.com/search-console) et
soumettez `https://lasourcee.org/sitemap.xml`.

---

## Vérifier avant de déployer

Un script contrôle l'application dans les conditions exactes de Vercel :
importation du point d'entrée serverless, connexion PostgreSQL, drapeaux
du cookie de session derrière un proxy HTTPS, restitution de l'adresse IP
réelle du visiteur, liens d'e-mail en HTTPS, politique de sécurité du
contenu, et non-exposition du code source.

```bash
cd backend
DATABASE_URL="postgresql://..." python tests_deploiement.py
```

Il doit afficher `85/85 vérifications réussies`.

Et la suite fonctionnelle complète, sur les deux moteurs :

```bash
python tests_integration.py                                    # SQLite
DB_TYPE=postgres DATABASE_URL="postgresql://..." python tests_integration.py
```

Elle doit afficher `383/383 tests réussis` dans les deux cas.

---

## Comment le déploiement est configuré

**`vercel.json`** décrit deux choses :

- `api/index.py` est construit comme fonction Python ; toutes les
  requêtes `/api/*` y sont dirigées, en conservant l'URL d'origine ;
- seuls les fichiers du frontend (`index.html`, `script.js`,
  `styles.css`, `assets/`...) sont publiés en statique. Le dossier
  `backend/` n'est **jamais** exposé : il n'existe que dans le paquet de
  la fonction.

**`api/index.py`** ajoute `backend/` au chemin Python et expose
l'application Flask sous le nom `app`, que Vercel reconnaît comme une
application WSGI.

**`requirements.txt`** est à la racine parce que c'est là que Vercel le
cherche. `backend/requirements.txt` y renvoie : il n'y a qu'une liste à
maintenir.

Deux points d'attention traités dans le code, propres à ce type
d'hébergement :

- **l'adresse IP du visiteur.** Derrière le proxy de Vercel, l'application
  ne verrait que l'adresse du proxy : tous les visiteurs partageraient le
  même compteur anti-force-brute, et bloquer un attaquant bloquerait tout
  le monde. Les en-têtes `X-Forwarded-*` sont donc pris en compte — mais
  uniquement en production, où un proxy est réellement présent. En local,
  s'y fier permettrait à n'importe qui de se forger une fausse adresse.
- **le drapeau `Secure` du cookie de session.** L'application ne reçoit
  qu'une connexion HTTP interne ; c'est l'en-tête `X-Forwarded-Proto` qui
  indique que le visiteur est bien en HTTPS.

---

## Déploiement sur un serveur classique

Sur un VPS ou un hébergement avec disque persistant, SQLite suffit et il
n'y a pas de base externe à provisionner.

```bash
git clone <dépôt> && cd projet_orienty
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp backend/.env.example backend/.env
# renseignez SECRET_KEY, EMAIL_MODE, SMTP_*, URL_PLATEFORME

pip install gunicorn
cd backend
gunicorn --bind 127.0.0.1:5000 --workers 3 "app:creer_application()"
```

Placez Nginx devant, avec un certificat Let's Encrypt, et transmettez les
en-têtes de proxy :

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Puis, dans `backend/.env` : `ENVIRONNEMENT=production` et `NB_PROXYS=1`.

---

## Problèmes courants

| Symptôme | Cause | Solution |
|---|---|---|
| `405 Method Not Allowed` à l'inscription | site déployé sur un hébergeur statique | déployer sur Vercel |
| `/api/sante` renvoie `degrade` | base injoignable | vérifier `DATABASE_URL`, garder `?sslmode=require` |
| Les comptes disparaissent | `DB_TYPE=sqlite` sur Vercel | passer à `postgres` |
| Aucun e-mail reçu | `EMAIL_MODE` ≠ `smtp` | renseigner les variables SMTP, tester avec `gerer_admins.py tester-email` |
| Bouton Google absent | `GOOGLE_CLIENT_ID` non défini, ou domaine absent des origines autorisées | compléter la console Google Cloud |
| LinkedIn : « État OAuth invalide » | `SECRET_KEY` absente ou changeante | définir une `SECRET_KEY` fixe |
| Déconnexions aléatoires | `SECRET_KEY` régénérée à chaque déploiement | définir une `SECRET_KEY` fixe |
