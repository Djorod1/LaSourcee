# PLAN PRODUIT — Du prototype à la plateforme professionnelle

> Document de cadrage **avant code**. Aucune modification de fichier
> tant que vous n'avez pas validé la roadmap ci-dessous.
>
> Trois angles d'analyse : **Product Manager Senior**, **Software
> Architect Senior**, **UX Designer Senior**.

---

## Sommaire

1. [Diagnostic honnête : pourquoi rien ne marche vraiment chez vous](#1-diagnostic-honnête)
2. [Audit produit — ce qui sépare le prototype de la plateforme](#2-audit-produit)
3. [Audit UX — ce qui sent le « généré par IA »](#3-audit-ux)
4. [Audit architecture — couplage mort entre démo et réel](#4-audit-architecture)
5. [Vision produit — les trois piliers](#5-vision-produit)
6. [Benchmark — ce qui marche ailleurs et qu'on retient](#6-benchmark)
7. [Roadmap proposée — 4 sprints](#7-roadmap-proposée)
8. [Fichiers à modifier par sprint](#8-fichiers-à-modifier)
9. [Validation attendue](#9-validation-attendue)

---

## 1. Diagnostic honnête

### Pourquoi votre inscription ne marche pas en pratique

Vous avez raison, et je dois être direct sur le **pourquoi exact** :

| Scénario d'utilisation | Ce qui se passe vraiment |
|---|---|
| Vous ouvrez `index.html` en double-cliquant dessus (file://) | Le frontend ping `/api/sante` → échec → `MODE.api = false` → **mode démo activé**. L'inscription affiche un toast vert mais **rien n'est sauvegardé**. Vous croyez que c'est branché, ce n'est pas branché. |
| Vous démarrez Flask **sans MySQL** | L'inscription appelle `POST /api/auth/inscription` → backend essaie d'INSERT → MySQL absent → 500 → toast d'erreur générique chez vous |
| Vous démarrez Flask + MySQL **sans charger `schema.sql`** | Même chose : la table `utilisateur` n'existe pas → 500 → toast d'erreur |
| Vous démarrez Flask + MySQL + schema chargé | **Ça marche**, mais aucun mode d'emploi clair ne vous a guidé jusqu'ici |

**Conclusion brutale** : aujourd'hui votre plateforme exige **3 étapes manuelles préalables** (installer MySQL, charger le schema, lancer Flask) pour qu'un simple bouton fonctionne. Aucun produit professionnel ne demande ça à son utilisateur. Le « mode démo » a été pensé comme un filet de sécurité — il est devenu un piège qui masque l'absence de vraie configuration.

### Pourquoi le bouton « Continuer avec Google » ne fait rien

```html
<button class="btn-social" onclick="commencerOnboarding()">
  <svg>...Google...</svg> Continuer avec Google
</button>
```

C'est un **bouton décoratif**. Il appelle la même fonction que le bouton classique. **Aucune intégration OAuth réelle**, juste l'icône Google. Pareil pour LinkedIn.

### Pourquoi « Mot de passe oublié » envoie un e-mail fantôme

```html
<button onclick="toast('Lien de réinitialisation envoyé par e-mail.'); afficherVue('vue-connexion')">
```

Le toast s'affiche, c'est tout. **Il n'existe pas d'endpoint backend** `POST /api/auth/oubli-mdp`. Vérifié : `grep -r "oubli|reset|forgot" backend/routes/` retourne **zéro résultat**.

### Pourquoi l'admin « ne marche pas »

Les tableaux admin affichent **5 utilisateurs en dur** (`['Marie Dupont','marie@email.com',...]`). Les boutons « Suspendre » et « Supprimer » lancent un toast. Le `GET /api/admin/utilisateurs` qui permettrait de lister les vrais utilisateurs **n'existe pas** dans le backend.

### Verdict général

> La plateforme est aujourd'hui un **prototype de prototype** : la phase A a câblé 15 fonctions au backend, mais l'expérience de premier contact (ouvrir le fichier, créer un compte, se connecter, voir ses données) **ne fonctionne pas sans une installation experte**. C'est la cause unique de votre frustration. Il faut **régler ce problème en premier**, avant toute nouvelle fonctionnalité.

---

## 2. Audit produit

### Critères d'une vraie plateforme professionnelle vs LaSourcee aujourd'hui

| Critère professionnel | LaSourcee actuel | Écart |
|---|---|---|
| **Onboarding < 60 secondes** | Inscription en 4 étapes + saisie répétitive, dépend de 3 outils externes | 🔴 Critique |
| **Persistance immédiate** | Tout disparaît au rafraîchissement en mode démo | 🔴 Critique |
| **Compte vérifié par e-mail** | Pas de vérification | 🟠 Important |
| **Récupération de mot de passe fonctionnelle** | Mock | 🔴 Critique |
| **Authentification OAuth (Google/LinkedIn)** | Boutons décoratifs | 🟠 Important |
| **Page d'admin protégée et fonctionnelle** | Visible par tout utilisateur connecté en démo, données factices | 🔴 Critique |
| **Modération réelle des contenus** | Boutons mock | 🟠 Important |
| **Upload de média (photo de profil)** | Stocké en dataURL côté client uniquement | 🟠 Important |
| **Notifications réelles** | Tableau JS statique de 5 entrées | 🟠 Important |
| **Recherche sur la base** | Filtre client sur 6 questions hardcodées | 🟠 Important |
| **Mobile parfaitement utilisable** | OK mais responsive imparfait sur 360 px | 🟡 Mineur |
| **Documentation déploiement** | README technique, manque un guide pas-à-pas pour démarrer la stack | 🟠 Important |

### Ce qui manque pour être une plateforme

1. **Un parcours de premier lancement** — un installer (ou un Docker Compose) qui démarre tout d'un coup
2. **Un compte de démonstration pré-créé** — pour qu'un visiteur ou un évaluateur puisse tester sans s'inscrire
3. **Des données de seed réalistes** — pas seulement 12 secteurs et 17 pays, mais aussi des utilisateurs, questions, réponses, mentors pour montrer l'app vivante
4. **Une page « À propos » et « Confidentialité »** — obligatoires pour la crédibilité
5. **Un fil d'Ariane (breadcrumb) ou un retour visible** — l'utilisateur se perd entre les vues
6. **Des états vides explicites** — quand il n'y a aucune question dans un secteur, montrer « Soyez le premier à poser une question » avec CTA, pas une zone blanche
7. **Des messages d'erreur humains** — « Erreur 500 » est inacceptable côté utilisateur

---

## 3. Audit UX

### Signaux qui sentent le « généré par IA »

| Signal | Localisation | Pourquoi ça pue l'IA |
|---|---|---|
| Stats parfaitement rondes | Hero `2 400+ étudiants`, `380+ mentors`, `9 secteurs` | Chiffres trop ronds, jamais vérifiés |
| Données de mentors irréalistes | `script.js` `mentors` array | Sophie Lambert ex-Goldman Sachs, Karim Benali ex-Google, tous notés 4.7-4.9 → faux |
| Questions de démo prétentieuses | `Comment décrocher un stage en M&A à Londres` | Personne en L1 ne parle comme ça |
| Bandeau « 5 sessions actives » | `panneauSecurite()` en dur | Trois sessions inventées (« Chrome sur Windows », etc.) |
| Catégories abstraites identiques partout | Tech, Médecine, Finance, Droit | Liste générique copiée-collée |
| Toasts excessifs | Chaque clic produit un toast vert | Aucun produit pro ne fait ça |
| Footer aux liens vides | `<a href="#">` partout | Maquette, pas produit |
| Texte d'intro vague | « Apprenez de ceux qui ont déjà tracé la voie » | Slogan sans engagement précis |
| Trois cartes Q&A dans le hero | Layout symétrique chargé | Personne ne lit ces 3 cartes — bruit visuel |

### Frictions UX critiques observées

| Friction | Description |
|---|---|
| **Bouton « Continuer avec Google » non fonctionnel** | Frustration immédiate du nouvel utilisateur |
| **Inscription en 5 écrans** (rôle, infos, secteurs, photo, bienvenue) avant d'accéder au contenu | Trop long pour un essai |
| **Aucun contenu visible avant inscription** | L'utilisateur ne peut pas évaluer la valeur avant de s'engager |
| **Menu profil mélange `Mon profil`, `Espace mentor`, `Administration`** | Pas de hiérarchie claire entre actions personnelles et privilèges admin |
| **« Espace mentor » et « Administration » dans le même menu** | Risque de confusion sur les rôles |
| **Pas de retour visible** après publication d'une question | L'utilisateur ne sait pas où aller |
| **Réponses des mentors mélangées dans une longue page** | Pas d'épinglage de la « meilleure réponse » |

---

## 4. Audit architecture

### Le couplage mort entre démo et réel

```
[Frontend index.html]
       ↓
   [script.js avec arrays mentors/questions/notifications en dur]
       ↓
   MODE.api ? oui → fetch /api/...     ← câblage Phase A
            ? non → manipule les arrays locaux
                    (le user croit que ça marche, mais c'est en RAM)
```

**Problème** : le mode démo est un parallel universe. Quand `MODE.api = true`, le frontend charge les questions depuis l'API et remplace l'array `questions`. Mais les avatars, les notifications et les mentors restent les démos hardcodés.

**Conséquence** : même en backend connecté, l'application affiche partiellement des données factices (les 5 mentors Sophie/Karim/Amélie/Thomas/Fatou apparaissent toujours dans la sidebar et la colonne droite).

### Modèle de données figé

Le schema actuel n'a qu'**un seul type de publication** (`question`) et un seul type d'interaction (`reponse`). Le cahier des charges parle de :

- Conseils mentors (à publier librement)
- Témoignages d'admis
- Opportunités (stages, emplois)
- Ressources (liens utiles, guides)
- Actualités (admin)

→ Refonte vers un modèle `publication` polymorphe **inévitable** pour aller plus loin.

### Couche admin sous-développée

| Endpoint backend admin | Existe | UI branchée |
|---|---|---|
| `GET /api/admin/dashboard` | ✅ | ✅ (mais frontend affiche données mock) |
| `GET /api/admin/signalements` | ✅ | ❌ |
| `POST /api/admin/signalements/<id>` | ✅ | ❌ |
| `POST /api/admin/mentors/<id>/verifier` | ✅ | ❌ |
| `POST /api/admin/utilisateurs/<id>/suspendre` | ✅ | ❌ |
| `GET /api/admin/utilisateurs` (lister) | ❌ | ❌ |
| `POST /api/admin/utilisateurs` (créer) | ❌ | ❌ |
| `PUT /api/admin/utilisateurs/<id>` (modifier) | ❌ | ❌ |
| `DELETE /api/admin/utilisateurs/<id>` | ❌ | ❌ |
| `POST /api/admin/utilisateurs/<id>/role` | ❌ | ❌ |
| CRUD secteurs/catégories | ❌ | ❌ |

### Sécurité

- ✅ bcrypt, anti-force-brute, en-têtes CSP/Frame, échappement XSS, handler erreur sans fuite (déjà en place)
- ❌ Pas de vérification e-mail à l'inscription
- ❌ Pas de 2FA
- ❌ Pas de log d'audit des actions admin
- ❌ Pas de limite de taille upload (à anticiper)

### Performance et observabilité

- ✅ Connexion DB par requête, suffisante en démo
- ❌ Pas de logs structurés (juste print Flask par défaut)
- ❌ Pas de métriques de santé applicative (`/api/sante` renvoie juste OK, pas l'état DB)
- ❌ Pas de cache HTTP sur les assets statiques

---

## 5. Vision produit

LaSourcee ne devient une **vraie** plateforme étudiante que si elle adresse les **trois piliers** de la vie étudiante.

### Pilier 1 — Mentorat académique

Le pilier historique, à conserver.

| Sous-domaine | Exemple de question | Type de mentor cible |
|---|---|---|
| Réussite universitaire | « Comment réviser efficacement en L1 ? » | Étudiants L3/M1 avancés |
| Méthodologie | « Comment rédiger un mémoire ? » | Doctorants, profs |
| Orientation | « Faut-il faire un master de spé ou généraliste ? » | Anciens diplômés |
| Choix de filière | « Maths appli vs informatique : que choisir ? » | Étudiants ayant fait le choix |

### Pilier 2 — Carrière

Pour les étudiants avancés et jeunes diplômés.

| Sous-domaine | Exemple |
|---|---|
| Insertion pro | « Comment trouver son premier emploi sans expérience ? » |
| Stages | « Comment décrocher un stage en agence à Cotonou ? » |
| Opportunités | Offres d'emploi/stages partagées par les mentors |
| Compétences | « Quelles compétences vaut-il mieux apprendre en 2026 ? » |

### Pilier 3 — Éducation financière

**Le plus gros différenciateur** — quasi absent ailleurs en francophonie africaine.

| Sous-domaine | Exemple |
|---|---|
| Gestion de l'argent | « Comment vivre avec 30 000 FCFA par mois ? » |
| Revenus pendant les études | Freelance, micro-services, tutorat |
| Investissement | Démarrer avec petite somme, comprendre les risques |
| Entrepreneuriat étudiant | Lancer une activité tout en étudiant |
| Indépendance financière | Construire ses premières économies |

**Cadrage explicite** : éducation, **pas conseil financier**. La plateforme partage l'expérience d'autres étudiants/jeunes pros, pas des recommandations d'investissement.

### Conséquence sur le modèle de données

Chaque publication aura :
- un **type** (`question`, `conseil`, `temoignage`, `opportunite`, `ressource`)
- un **pilier** (`academique`, `carriere`, `financier`)
- un **thème** (orientation, stage, freelance, budget, etc.)
- 0..n **secteurs** (Tech, Finance, Médecine…)

L'utilisateur peut filtrer le fil par pilier, ce qui donne **trois fils thématiques** distincts mais sur la même architecture.

---

## 6. Benchmark

> Synthèse de 11 plateformes étudiées dans `STRATEGIE.md` section 11.
> Les détails complets s'y trouvent.

### Ce qui marche ailleurs

1. **ADPList** : badges et classements publics des mentors (boucle de réputation visible)
2. **Ten Thousand Coffees** : match mensuel automatique forcé (transforme l'intention en habitude)
3. **JobTeaser** : intégration dans les services carrière institutionnels (adoption par bouche-à-oreille structuré)
4. **Khan Academy** : modules de 5 à 10 minutes adaptés à la consommation mobile
5. **Reddit/Discord** : archivage searchable des questions résolues (base de connaissances vivante)
6. **Ingressive for Good** : usage massif de WhatsApp/Telegram pour animer la communauté africaine
7. **Hivebrite** : segmentation fine du réseau alumni (par promo, secteur, géographie)

### Pratiques retenues pour LaSourcee

| Pratique | Adaptation LaSourcee |
|---|---|
| **Compte démo immédiat** | Un bouton « Visite guidée » sur la home, qui connecte automatiquement un user de démo en lecture seule |
| **Mentor du mois mis en avant** | Sidebar « Mentor à découvrir » qui change chaque semaine |
| **Réponse épinglée par l'auteur** | L'auteur d'une question peut marquer la réponse qui l'a aidée (« Cela m'a aidé ») |
| **Réponse transformée en article** | Bouton « Publier comme article » sur les réponses de mentor (votre demande explicite) |
| **Recherche de questions similaires AVANT publication** | Déjà esquissé, à finaliser |
| **Vie en mobile-first** | Optimiser les flux les plus fréquents pour le tactile |
| **Contenu africain natif** | Mentors, exemples et études de cas ancrés en Afrique francophone |

---

## 7. Roadmap proposée

Quatre sprints courts, valeur ajoutée à chaque livraison, **rien qui bloque le précédent**.

### 🔴 Sprint 1 — Réparer ce qui ne marche pas (3 à 4 jours)

> Objectif : un évaluateur qui ouvre la plateforme doit voir une
> expérience qui fonctionne en moins de 60 secondes.

| Action | Pourquoi |
|---|---|
| **Compte de démonstration pré-créé** (email/mdp publics affichés sur la home) | Pour tester sans s'inscrire |
| **Seed de données réalistes** (10 mentors africains crédibles, 30 questions ancrées localement, secteurs+publications+commentaires) | Pour que la plateforme n'ait pas l'air vide quand elle est branchée |
| **Endpoint `POST /api/auth/oubli-mdp`** + branchement du bouton | Vrai e-mail (loggé console en dev) |
| **Endpoint `POST /api/auth/changer-mdp`** + branchement | Vraie sécurité dans les paramètres |
| **Retirer les boutons Google/LinkedIn** ou afficher « Bientôt disponible » | Honnêteté UX |
| **Mode démo : message d'avertissement clair** « Données non persistées » | L'utilisateur sait où il est |
| **Script de démarrage one-shot** (`./demarrer.sh` qui lance Docker + Flask + seed) | Démarrer en 1 commande |
| **Validation côté frontend** des champs inscription dès l'étape 1 (e-mail format, mdp robustesse) | Pas attendre l'étape 4 pour valider |
| **Page « Comment ça marche » courte** (3 étapes, sobre) | Réassurance avant inscription |

### 🟠 Sprint 2 — Administration réelle et permissions (3 à 4 jours)

> Objectif : l'admin agit sur de vraies données.

| Action | Endpoint à créer | UI à brancher |
|---|---|---|
| Lister les utilisateurs | `GET /api/admin/utilisateurs` | Tableau triable/filtrable |
| Modifier un utilisateur | `PUT /api/admin/utilisateurs/<id>` | Modal édition |
| Suspendre/réactiver | `POST .../suspendre` (existe) + `.../reactiver` (à créer) | Boutons branchés |
| Changer un rôle | `POST /api/admin/utilisateurs/<id>/role` | Sélecteur de rôle |
| CRUD complet sur secteurs/catégories | `GET/POST/PUT/DELETE /api/admin/secteurs` | Onglet « Catégories » fonctionnel |
| Modération réelle (liste, masquer, supprimer) | Endpoints signalements existent | Branchement UI |
| Validation mentors réelle | Existe | Branchement UI |
| **Rôle `super_admin`** | Migration BD + endpoint `POST /api/admin/admins` | UI réservée au super admin |
| **Journal d'audit** | Table `audit_admin` + endpoint lecture | Onglet « Historique des actions » |
| **Page de connexion admin séparée** (`/admin/connexion.html`) | Routes existantes + URL dédiée | Page sobre avec rate-limit renforcé |

### 🟡 Sprint 3 — Les trois piliers + publications libres (4 à 5 jours)

> Objectif : enrichir le modèle de contenu et matérialiser la vision produit.

| Action | Impact BD | Impact backend | Impact frontend |
|---|---|---|---|
| **Tables `pilier` + `theme`** | Nouveau | Référentiels publics | Filtres dans le fil |
| **Refonte `question` → `publication` polymorphe** | Migration | Renommage routes `/api/publications` | Carte de publication adaptative |
| **Permettre aux mentors de publier conseils/témoignages/opportunités/ressources** | Champ `type_publication` | Validation par rôle | Modal de publication adaptative |
| **Témoignages d'admis** (rôle dédié `etudiant_admis` ou tag) | – | Routes filtrables | Vue « Témoignages » dans le pilier académique |
| **Publier une réponse comme article** (votre demande) | Nouveau champ `publiee_comme_article` | `POST /api/reponses/<id>/promouvoir` | Bouton sur les réponses mentor |
| **Favoris unifiés** (questions + mentors + publications) | Table `favori` polymorphe | Routes `/api/favoris` | Onglet « Mes favoris » à 4 filtres |

### 🟢 Sprint 4 — Polish, viralité, engagement (4 à 6 jours)

> Objectif : qualité finale, premiers leviers d'engagement.

| Action |
|---|
| Refonte page d'accueil épurée (sélecteur « qu'est-ce qui vous amène ? ») |
| 3 propositions de texte d'intro (déjà rédigées dans STRATEGIE.md §8) à choisir |
| Upload réel des photos de profil (endpoint + stockage `uploads/`) |
| Notifications branchées en polling (toutes les 30 s) |
| Permaliens partageables (`/p/<id>` avec balises Open Graph WhatsApp/Telegram) |
| Logs structurés Python (logging stdlib + format) |
| Page « À propos » + « Confidentialité » + « Mentions légales » |
| Tests d'intégration sur les 10 flux critiques (Pytest) |
| Améliorations responsive sur 360-414 px |
| Docker Compose en option pour démarrage one-shot |

### Total estimé

- Sprint 1 : 3-4 jours (urgence absolue)
- Sprint 2 : 3-4 jours
- Sprint 3 : 4-5 jours
- Sprint 4 : 4-6 jours

**Total** : 14 à 19 jours de travail effectif.

---

## 8. Fichiers à modifier

### Sprint 1 — Réparer

| Fichier | Action |
|---|---|
| `database/schema.sql` | Ajouter données de seed (10 mentors, 30 publications, 1 compte démo `demo@lasource.io`) |
| `database/seed.sql` (nouveau) | Séparer les données de démonstration du schéma |
| `backend/routes/auth.py` | Ajouter `POST /api/auth/oubli-mdp`, `POST /api/auth/changer-mdp` |
| `backend/services/email.py` (nouveau) | Service d'envoi e-mail (mode dev = log console, prod = SMTP) |
| `backend/utils/jeton.py` (nouveau) | Génération de jetons de réinitialisation à durée limitée |
| `database/schema.sql` | Table `reinitialisation_mdp` (jeton + expiration + utilisé) |
| `index.html` | Retirer les boutons OAuth ou les marquer « Bientôt disponible » |
| `index.html` `vue-oubli` | Câbler sur l'endpoint réel |
| `script.js` | Validation des champs inscription dès l'étape 1, bandeau démo visible |
| `api.js` | Helper `API.estDemo()` qui retourne true si MODE.api=false |
| `demarrer.sh` (nouveau) | Script bash lançant MySQL Docker + Flask + chargement schema/seed |
| `README.md` | Section « Démarrage rapide en 1 commande » |
| `index.html` page d'accueil | Bouton « Visite guidée (compte démo) » qui auto-connecte |
| `styles.css` | Bandeau démo, états vides explicites |

### Sprint 2 — Admin réel

| Fichier | Action |
|---|---|
| `database/schema.sql` | Ajouter ENUM `role` enrichi (`visiteur`, `etudiant`, `mentor`, `admin`, `super_admin`) + table `audit_admin` |
| `database/migration_v2.sql` (nouveau) | Migration depuis l'ancien schéma |
| `backend/routes/admin.py` | 8 nouveaux endpoints (CRUD utilisateurs + rôles + secteurs + audit + admins) |
| `backend/utils/auth_helpers.py` | Décorateur `@role_requis('admin','super_admin')` |
| `backend/services/audit.py` (nouveau) | Journalisation des actions admin |
| `admin/index.html` (nouveau) | Page admin séparée, palette sobre |
| `admin/admin.js` (nouveau) | Logique propre, indépendante du frontend public |
| `admin/admin.css` (nouveau) | Styles dédiés (tables, filtres, modales) |
| `index.html` | Retirer `sv-admin` du SPA public, retirer lien « Administration » du menu profil |
| `script.js` | Retirer les fonctions `admin*` qui passent en `admin/admin.js` |

### Sprint 3 — Trois piliers + publications

| Fichier | Action |
|---|---|
| `database/schema.sql` + migration | Tables `pilier`, `theme`, `publication`, `commentaire`, `favori` + données de référence |
| `backend/routes/publications.py` (nouveau) | Remplace `questions.py` |
| `backend/routes/commentaires.py` (nouveau) | Remplace `reponses.py` |
| `backend/routes/favoris.py` (nouveau) | CRUD favoris polymorphes |
| `backend/routes/auth.py` | Retirer la promotion automatique mentor à l'inscription, ajouter `POST /api/mentors/devenir` avec validation |
| `script.js` | Carte de publication adaptative au type, modal de publication adaptatif |
| `index.html` | Sous-vues `sv-pilier-academique/carriere/financier`, modal publication |
| `styles.css` | Couleurs par pilier, badges de type de publication |

### Sprint 4 — Polish

| Fichier | Action |
|---|---|
| `index.html` | Refonte page d'accueil épurée |
| `script.js` + `index.html` | Sélecteur « qu'est-ce qui vous amène ? » au boot |
| `backend/routes/profil.py` | `POST /api/profil/photo` (upload base64 → fichier serveur, redimension) |
| `backend/uploads/` (nouveau dossier) | Stockage des photos uploadées |
| `backend/services/notifications_polling.py` | Long-polling 30 s |
| `script.js` | Polling notifications + maj badge |
| `index.html` + `script.js` | Page publique `/p/<id>` (permalien partageable) |
| `backend/routes/publications.py` | Métadonnées Open Graph dans la réponse HTML |
| `backend/app.py` | Logging structuré (`logging.basicConfig`) |
| `apropos.html`, `confidentialite.html`, `mentions-legales.html` (nouveaux) | Pages légales |
| `tests/` (nouveau dossier) | Pytest sur les 10 flux critiques |
| `styles.css` | Améliorations responsive 360-414 px |
| `docker-compose.yml` (nouveau) | Démarrage one-shot |
| `Dockerfile.backend` (nouveau) | Image backend |

### Total fichiers impactés sur les 4 sprints

- **À modifier** : ~10 fichiers existants (`schema.sql`, `script.js`, `styles.css`, `index.html`, `auth.py`, `admin.py`, `profil.py`, `app.py`, `api.js`, `README.md`)
- **À créer** : ~25 nouveaux fichiers
- **À renommer/migrer** : 2 (`questions.py` → `publications.py`, `reponses.py` → `commentaires.py`)

---

## 9. Validation attendue

Avant que je code quoi que ce soit, merci de valider ou amender les points suivants :

### A. Périmètre du Sprint 1 (urgent)

- [ ] Compte démo + seed de données réalistes
- [ ] Mot de passe oublié + changement de mot de passe fonctionnels
- [ ] Boutons OAuth retirés (ou marqués « Bientôt »)
- [ ] Script de démarrage one-shot (`./demarrer.sh`)
- [ ] Bandeau visible quand on est en mode démo

### B. Périmètre du Sprint 2 (admin)

- [ ] Page admin **séparée** (`admin/index.html`, URL dédiée)
- [ ] 5 rôles : Visiteur, Étudiant, Mentor, Admin, Super Admin
- [ ] CRUD complet utilisateurs + secteurs + audit log

### C. Périmètre du Sprint 3 (piliers + publications)

- [ ] Modèle de publication polymorphe (remplace `question`)
- [ ] Trois piliers : Académique / Carrière / **Financier**
- [ ] Publication de réponse comme article (votre demande)
- [ ] Favoris unifiés (questions + mentors + publications)

### D. Périmètre du Sprint 4 (polish)

- [ ] Refonte page d'accueil (texte d'intro inclus — A/B/C dans STRATEGIE.md à choisir)
- [ ] Upload photo réel
- [ ] Permaliens partageables
- [ ] Docker Compose pour démarrage

### E. Ordre d'exécution

Je propose **strictement** dans l'ordre 1 → 2 → 3 → 4. Sprint 1 d'abord parce que tant que le compte démo et le seed ne sont pas là, vous ne pourrez pas vraiment **voir** la valeur des sprints suivants.

### F. Logo

Pendant tout ce temps, le placeholder à ratio verrouillé reste en place. Dès que vous déposez `assets/lasource-logo.png` et `assets/lasource-symbole.png`, le placeholder s'efface et votre image apparaît sans déformation. C'est déjà en place et testé.

---

## Récapitulatif pour décision rapide

> **Le problème** : la plateforme ne marche pas pour vous parce qu'elle exige une stack technique complète (MySQL + Flask + schema initialisé) pour qu'un simple bouton fonctionne, et son mode démo cache cette dépendance.
>
> **La solution proposée** : 4 sprints, ~17 jours de travail, livrant progressivement (1) une expérience qui marche d'emblée, (2) un vrai admin, (3) les 3 piliers du produit, (4) le polish final.
>
> **À valider** : les périmètres A, B, C, D et l'ordre 1→2→3→4.
>
> **Une fois validé** : je démarre par le Sprint 1 immédiatement.
