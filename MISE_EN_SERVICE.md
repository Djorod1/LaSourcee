# LaSourcee — Guide de mise en service

Ce document explique comment rendre la plateforme pleinement
opérationnelle : envoi réel des e-mails, comptes administrateurs,
validation des mentors, connexion Google.

---

## 1. Ce qui fonctionne désormais

| Fonctionnalité | État | Vérifié par |
|---|---|---|
| Absence de tout compte de démonstration | Garantie | Section 2 |
| Inscription par e-mail | Opérationnelle | Section 3 |
| Connexion / déconnexion | Opérationnelle | Section 3 |
| Vérification d'adresse e-mail | Opérationnelle | Section 4 |
| Mot de passe oublié | Opérationnelle | Section 5 |
| Comptes administrateurs | Opérationnels | Section 6 |
| Candidature et validation de mentor | Opérationnelle | Section 7 |
| Publication, favoris, réponses, recherche | Opérationnelles | Section 8 |
| Envoi réel d'e-mails (SMTP) | Opérationnel après configuration | § 2 |
| Connexion Google et LinkedIn | Opérationnelle après configuration | § 5 |

Lancer la vérification complète à tout moment :

```bash
cd backend
python tests_integration.py       # doit afficher 325/363 tests réussis
```

La même suite tourne à l'identique sur les trois moteurs. Pour la
vérifier sur PostgreSQL :

```bash
DB_TYPE=postgres DATABASE_URL="postgresql://..." python tests_integration.py
```

---

## 2. Activer l'envoi réel des e-mails

Sans cette étape, les messages sont seulement écrits dans les logs du
serveur : personne ne les reçoit.

### Avec une adresse Gmail

1. Activez la **validation en 2 étapes** sur le compte Google.
2. Allez dans **Compte Google → Sécurité → Mots de passe d'application**.
3. Créez un mot de passe pour « Autre (LaSourcee) » et copiez les
   16 caractères obtenus.
4. Dans `backend/.env` :

```env
EMAIL_MODE=smtp
URL_PLATEFORME=https://lasourcee.org
SMTP_HOTE=smtp.gmail.com
SMTP_PORT=587
SMTP_UTILISATEUR=votre.adresse@gmail.com
SMTP_MOTDEPASSE=les16caracteres
SMTP_EXPEDITEUR=LaSourcee <votre.adresse@gmail.com>
SMTP_SECURITE=starttls
```

> Le mot de passe habituel du compte Google est **refusé** : seul un
> mot de passe d'application fonctionne.

### Autres fournisseurs

| Fournisseur | Hôte | Port | Sécurité |
|---|---|---|---|
| Outlook / Microsoft 365 | `smtp.office365.com` | 587 | starttls |
| OVH | `ssl0.ovh.net` | 587 | starttls |
| SendGrid | `smtp.sendgrid.net` | 587 | starttls (utilisateur : `apikey`) |

### Vérifier que l'envoi marche

```bash
cd backend
python gerer_admins.py tester-email votre.adresse@gmail.com
```

Un message doit arriver dans la boîte de réception. En cas d'échec, la
console indique précisément la cause (authentification, hôte injoignable…).

---

## 3. Créer les comptes administrateurs

Une fois l'envoi d'e-mails configuré :

```bash
cd backend
python gerer_admins.py creer
```

Cette commande :

- crée les quatre comptes administrateurs officiels ;
- génère pour chacun un mot de passe temporaire fort et unique ;
- envoie à chacun un e-mail contenant ses identifiants ;
- affiche les mots de passe dans la console (à conserver si l'envoi
  d'e-mails n'est pas encore actif).

Comptes créés, tous avec le rôle **super administrateur** :

| Nom | Adresse |
|---|---|
| Kouessi TOYOHOUNSOGBE | `toyohounsogbe1@gmail.com` |
| Théophile DOUNON | `theophiledounon@gmail.com` |
| Mariano DOSSOUGAN | `espoirmariano@gmail.com` |
| Rodrigue DJOSSOU | `rodriguedjossou93@gmail.com` |

### Autres commandes utiles

```bash
python gerer_admins.py lister                       # liste les administrateurs
python gerer_admins.py ajouter <email> "Prénom" "Nom"  # ajoute un administrateur
python gerer_admins.py reinitialiser <email>        # régénère un mot de passe
```

Chaque administrateur doit changer son mot de passe temporaire à la
première connexion : **menu profil → Paramètres → Sécurité**.

---

## 4. Le parcours mentor

### Côté candidat

1. L'utilisateur se connecte, puis ouvre **Espace mentor**.
2. Il clique sur **Déposer ma candidature** et renseigne :
   profession, employeur, années d'expérience, présentation publique,
   motivation, domaines d'expertise, profil professionnel (facultatif).
3. Sa candidature est transmise ; il reçoit un accusé de réception.

Contrôles appliqués : profession obligatoire, au moins un an
d'expérience, présentation d'au moins 40 caractères, motivation d'au
moins 80 caractères, au moins un domaine d'expertise.

### Côté administrateur

1. Tous les administrateurs reçoivent un e-mail signalant la candidature.
2. Dans **Administration → Validation mentors**, ils voient le dossier.
3. Ils valident ou refusent (un motif peut être joint au refus).

### Résultat

- **Validation** : le compte passe au rôle mentor, obtient le badge
  « Mentor vérifié », apparaît dans l'annuaire public. Le candidat est
  prévenu par e-mail.
- **Refus** : le compte revient au rôle étudiant. Le candidat est
  prévenu par e-mail, avec le motif s'il a été renseigné.

---

## 5. Activer la connexion Google

1. Rendez-vous sur [console.cloud.google.com](https://console.cloud.google.com/).
2. Créez un projet, puis **API et services → Identifiants →
   Créer des identifiants → ID client OAuth 2.0**.
3. Type d'application : **Application Web**.
4. Dans **Origines JavaScript autorisées**, ajoutez :
   - `http://localhost:5000` (développement)
   - `https://lasourcee.org` (production)
5. Copiez l'identifiant client dans `backend/.env` :

```env
GOOGLE_CLIENT_ID=xxxxxxxxxxxx.apps.googleusercontent.com
```

Tant que cette variable est vide, le bouton « Continuer avec Google »
est **automatiquement masqué** : aucun bouton mort n'est affiché.

La connexion Google crée le compte s'il n'existe pas, ou le rattache au
compte existant si l'adresse correspond — sans jamais créer de doublon.

---

## 6. Rendre la vérification d'adresse obligatoire

Recommandé en production pour éviter les inscriptions avec de fausses
adresses :

```env
VERIFICATION_EMAIL_OBLIGATOIRE=1
```

L'utilisateur doit alors cliquer le lien reçu par e-mail avant de
pouvoir se connecter.

---

## 7. Mise en ligne sur un domaine

Le frontend seul (fichiers HTML, CSS, JS) peut être hébergé n'importe
où. **Mais l'inscription, les e-mails et l'administration exigent que le
backend Python tourne.** Un hébergement purement statique comme GitHub
Pages ne suffit donc pas : toute tentative de création de compte y
renvoie l'erreur `405 Method Not Allowed`.

La procédure complète pour **Vercel**, l'hébergement retenu, est décrite
dans **[`DEPLOIEMENT.md`](DEPLOIEMENT.md)** : création de la base
PostgreSQL, variables d'environnement, déploiement, création des
administrateurs, domaine personnalisé.

| Solution | Coût indicatif | Base de données | Remarque |
|---|---|---|---|
| **Vercel** | gratuit | PostgreSQL externe **obligatoire** | retenu pour le projet |
| Render, Railway | gratuit à 7 € / mois | PostgreSQL fourni | déploiement depuis Git |
| Serveur virtuel (Hetzner, DigitalOcean) | 4 à 6 € / mois | SQLite suffit | contrôle complet |
| PythonAnywhere | gratuit à 5 € / mois | SQLite suffit | démarrage rapide |

> Sur Vercel, Render et Railway, le disque est éphémère : un fichier
> SQLite serait effacé à chaque redémarrage, avec tous les comptes.
> `DB_TYPE=postgres` et `DATABASE_URL` sont indispensables. L'application
> détecte cette situation et l'inscrit dans ses logs au démarrage.

### Sur un serveur classique

```bash
git clone <votre-depot> lasource && cd lasource
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install gunicorn

cp backend/.env.example backend/.env
# Renseignez SECRET_KEY, les paramètres SMTP et GOOGLE_CLIENT_ID
# et ajoutez : ENVIRONNEMENT=production

cd backend
../.venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 'app:creer_application()'
```

Reverse proxy nginx :

```nginx
server {
    server_name lasourcee.org www.lasourcee.org;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Les en-têtes `X-Forwarded-*` ne sont pas décoratifs : sans eux,
l'application ne verrait que l'adresse du proxy. Tous les visiteurs
partageraient alors le même compteur anti-force-brute, et le cookie de
session ne porterait pas le drapeau `Secure`. Ajoutez `NB_PROXYS=1` dans
`backend/.env` pour que ces en-têtes soient pris en compte.

Puis le certificat HTTPS, gratuit :

```bash
sudo certbot --nginx -d lasourcee.org -d www.lasourcee.org
```

Enfin, les comptes administrateurs :

```bash
cd backend && ../.venv/bin/python gerer_admins.py creer
```

### À vérifier avant l'ouverture au public

- [ ] `SECRET_KEY` remplacée par une chaîne aléatoire longue et **stable**
- [ ] `ENVIRONNEMENT=production`
- [ ] `EMAIL_MODE=smtp` et envoi de test réussi
      (`python gerer_admins.py tester-email votre@adresse`)
- [ ] `URL_PLATEFORME=https://lasourcee.org`
- [ ] `VERIFICATION_EMAIL_OBLIGATOIRE=1`
- [ ] HTTPS actif
- [ ] Comptes administrateurs créés et mots de passe temporaires changés
- [ ] `python tests_integration.py` affiche 363/363
- [ ] `python tests_deploiement.py` affiche 80/80 (déploiement serverless)

---

## 8. Base de données : SQLite, PostgreSQL ou MySQL

Le code applicatif est identique dans les trois cas. Toutes les requêtes
s'écrivent avec le paramètre `%s` ; la couche d'accès
(`backend/models/db.py`) traduit le dialecte selon le moteur, de sorte
qu'aucune route n'a à savoir sur quelle base elle tourne.

**SQLite** (par défaut) convient jusqu'à plusieurs milliers
d'utilisateurs. Aucun serveur à installer : la base est un simple fichier
`lasource.db` — pensez à le sauvegarder. À réserver aux hébergements
disposant d'un disque persistant.

**PostgreSQL** est obligatoire sur Vercel, Render et Railway, et
recommandé dès que plusieurs processus écrivent en parallèle. Une seule
variable suffit :

```env
DB_TYPE=postgres
DATABASE_URL=postgresql://utilisateur:motdepasse@hote:5432/lasource
```

Le schéma se crée automatiquement au premier démarrage. Pour le faire à
la main, exécutez `database/schema_postgres.sql` et mettez
`INIT_DB_AUTO=0`.

**MySQL** reste disponible si le cahier des charges l'impose. Les trois
fichiers sont à appliquer dans l'ordre :

```bash
mysql -u root -p < database/schema.sql
mysql -u root -p < database/migration_v2.sql
mysql -u root -p < database/migration_v3.sql
```

puis dans `backend/.env` : `DB_TYPE=mysql` et les paramètres `DB_*`.

> La suite de tests automatisés couvre SQLite et PostgreSQL, pas MySQL —
> aucun serveur MySQL n'est mobilisé pendant les tests. Le schéma est
> tenu aligné sur les deux autres, mais si vous choisissez MySQL,
> déroulez une fois le parcours complet (inscription, confirmation par
> e-mail, connexion Google) avant l'ouverture au public.
