# LaSourcee — Stratégie d'évolution v2

> Document de cadrage produit avant toute implémentation.
> Aucune ligne de code n'a été modifiée à ce stade.

## Sommaire

1. [Audit de l'existant](#1-audit-de-lexistant)
2. [Vision cible](#2-vision-cible)
3. [Décisions d'architecture clés](#3-décisions-darchitecture-clés)
4. [Rôles et permissions](#4-rôles-et-permissions)
5. [Évolutions de la base de données](#5-évolutions-de-la-base-de-données)
6. [Évolutions du backend](#6-évolutions-du-backend)
7. [Évolutions du frontend](#7-évolutions-du-frontend)
8. [Texte d'introduction — 3 propositions](#8-texte-dintroduction--3-propositions)
9. [Roadmap par phases](#9-roadmap-par-phases)
10. [Recommandations stratégiques](#10-recommandations-stratégiques)
11. [Benchmark international](#11-benchmark-international) *(en cours de rédaction)*

---

## 1. Audit de l'existant

### 1.1 Inventaire technique

| Couche | État | Volumétrie |
|---|---|---|
| Frontend SPA | `index.html` + `script.js` + `styles.css` à la racine | 52 / 176 / 94 Ko |
| Backend Flask | 11 blueprints, 78 routes HTTP | 29 modules Python |
| Base de données | 24 tables + 2 vues + données de référence | 3 schémas (SQLite, PostgreSQL, MySQL) |
| Identité | Palette bleu royal + orange du logo, icônes SVG, aucun emoji | OK |
| Sécurité | bcrypt 12, anti-force-brute, CSP, échappement anti-XSS | OK |

### 1.2 Vues actuelles du SPA

| ID HTML | Rôle | Statut |
|---|---|---|
| `vue-accueil` | Page d'accueil publique | Trop dense, à refondre |
| `vue-connexion` | Connexion (e-mail + boutons sociaux mockés) | À brancher sur l'API |
| `vue-inscription` | Inscription (choix de rôle) | À brancher sur l'API |
| `vue-oubli` | Mot de passe oublié | Mocké |
| `vue-onboarding` | 4 étapes | OK |
| `vue-app` (avec 6 sous-vues : fil, profil, question, paramètres, admin, mentor) | Application connectée | Mélange admin et public ; à séparer |

### 1.3 Tables existantes

`secteur`, `pays`, `utilisateur`, `utilisateur_secteur`, `mentor_details`,
`experience`, `question`, `reponse`, `marquage_question`, `marquage_reponse`,
`sauvegarde`, `suivi_mentor`, `signalement`, `conversation`,
`conversation_participant`, `message`, `notification`, `session_web`.

### 1.4 Forces

- **Frontend autonome** déployable sur GitHub Pages sans backend
- **Backend rigoureux** (SQL paramétré, en-têtes de sécurité, anti-force-brute, sessions opaques)
- **Modèle de données propre** pour les questions/réponses arborescentes
- **Identité visuelle distinctive** (teal + terre cuite, icônes SVG, zéro emoji)
- **Documentation** complète dans le README

### 1.5 Limites identifiées

| Limite | Impact | Origine |
|---|---|---|
| **Boutons Google/LinkedIn factices** | Le visiteur clique, rien ne se passe vraiment (`seConnecter()` ne fait que `toast()`) | Frontend mocké |
| **Frontend non branché sur l'API** | Les questions/mentors restent des tableaux JS en dur | Pas d'intégration |
| **Admin dans la même SPA** | Visible dans le menu profil de tout utilisateur ; surface d'attaque accrue | Conception initiale |
| **Un seul type de publication** (`question`) | Impossible pour un mentor de publier un conseil, un témoignage, une opportunité | Modèle figé |
| **Suivi mentors ≠ Sauvegardes questions** (deux mécaniques séparées) | Pas d'espace unifié « Mes favoris » | Modèle dispersé |
| **Landing dense** (hero + 3 cartes Q&A + stats) | Surcharge cognitive immédiate | Choix de design |
| **Pas de thème transversal** | Tout est mélangé dans un seul fil | Modèle plat |
| **Rôle binaire** (étudiant/mentor + bool admin) | Pas de Super Admin ni de Visiteur | ENUM trop court |
| **Pas de système de commentaires** sur autre chose que les questions | Bloque les publications mentor commentables | Pas de table générique |

---

## 2. Vision cible

LaSourcee cesse d'être un **système de Q&A** pour devenir un **écosystème d'accompagnement étudiant** structuré autour de **trois piliers** et **deux moments-clés**.

### 2.1 Trois piliers

| Pilier | Question type | Acteurs principaux |
|---|---|---|
| **Académique** | « Comment réussir ma L1 d'informatique ? » | Étudiants avancés, anciens diplômés |
| **Professionnel** | « Comment décrocher un premier stage en finance ? » | Professionnels, alumni, mentors |
| **Financier** | « Comment monter un revenu freelance étudiant ? » | Entrepreneurs, jeunes pros |

### 2.2 Deux moments-clés (le « pourquoi je viens »)

| Moment | Profil utilisateur | Besoin |
|---|---|---|
| **Intégration universitaire** | Lycéen admis, primo-étudiant | Comprendre la vie u, éviter les erreurs, trouver des repères |
| **Orientation académique et pro** | Étudiant L3/M1/M2 | Choisir un master, comprendre les débouchés, valider un projet |

Ces deux moments structurent l'**onboarding** : la première question posée au visiteur est « *qu'est-ce qui vous amène ?* », pas « *quel est votre rôle ?* ».

### 2.3 Cinq rôles utilisateurs

| Rôle | Capacités principales |
|---|---|
| **Visiteur** | Consulter le fil public (limité aux X premières publications), s'inscrire |
| **Étudiant** | Tout du Visiteur + publier des questions/témoignages, commenter, mettre en favoris, suivre des mentors |
| **Mentor** | Tout de l'Étudiant + publier des conseils/opportunités/ressources, répondre, statut vérifié |
| **Administrateur** | Tableau de bord, modération signalements, validation mentors, gestion catégories |
| **Super Admin** | Tout de l'Administrateur + gestion des admins, paramètres globaux |

---

## 3. Décisions d'architecture clés

### 3.1 Garder la SPA publique, créer un portail admin séparé

**Décision :** L'application publique reste l'unique SPA à la racine (`index.html`).
L'administration est extraite dans un dossier `/admin/` avec sa propre page HTML, ses propres styles et son propre script.

```
/
├── index.html              ← grand public + mentors + étudiants
├── script.js
├── styles.css
├── admin/
│   ├── index.html          ← portail admin (sobre, table-driven)
│   ├── admin.js
│   └── admin.css
├── backend/
└── database/
```

**Bénéfices :**
- Le lien « Administration » disparaît du menu profil grand public
- Surface d'attaque réduite (URL admin masquée, pas exposée dans le markup grand public)
- Possibilité de durcir la CSP du portail admin (pas de `unsafe-inline` par exemple)
- Permet une identité visuelle plus dépouillée pour l'admin (lecture rapide de tableaux)

### 3.2 Modèle de publication unifié

**Décision :** remplacer la table `question` par une table `publication` polymorphe avec une colonne `type_publication`.

```sql
CREATE TABLE publication (
  id_publication  INT UNSIGNED PRIMARY KEY,
  id_auteur       INT UNSIGNED,
  type_publication ENUM('question','conseil','temoignage','opportunite','ressource'),
  id_pilier       TINYINT,                  -- académique / pro / financier
  id_secteur      SMALLINT,                 -- Tech, Finance, etc.
  titre           VARCHAR(200),
  corps           TEXT,
  url_externe     VARCHAR(500) NULL,        -- pour les ressources
  statut          ENUM('brouillon','publie','archive','supprime'),
  publiee_le      DATETIME,
  ...
);
```

Les **réponses** (table `reponse`) deviennent des **commentaires** (table `commentaire`) génériques sur n'importe quelle publication, conservant la mécanique arborescente déjà en place.

**Bénéfices :**
- Un seul moteur de fil/tri/filtres pour tous les types de contenu
- Les mentors publient sans avoir à « poser de fausse question »
- Les admis/anciens publient des témoignages
- Future addition d'un type (« offre de stage » par exemple) = une ligne de plus dans l'ENUM

### 3.3 Modèle de favori unifié

**Décision :** fusionner `sauvegarde` (questions) + `suivi_mentor` (mentors) en une seule table `favori` polymorphe.

```sql
CREATE TABLE favori (
  id_utilisateur INT UNSIGNED,
  type_cible     ENUM('publication','commentaire','utilisateur'),
  id_cible       INT UNSIGNED,
  cree_le        DATETIME,
  PRIMARY KEY (id_utilisateur, type_cible, id_cible)
);
```

UI : un seul onglet « Mes favoris » avec 4 filtres internes (Publications · Commentaires · Mentors · Étudiants).

### 3.4 Thématisation transversale

**Décision :** introduire deux référentiels nouveaux qui s'ajoutent au `secteur` existant :

- **`pilier`** (3 entrées) : académique, professionnel, financier
- **`theme`** (10-15 entrées) : intégration, orientation, stage, emploi, carrière, budget, freelance, entrepreneuriat, soft skills, vie étudiante, etc.

Une publication a **un pilier**, **un thème** (optionnel), et **0..n secteurs**.

---

## 4. Rôles et permissions

### 4.1 Matrice d'accès

| Capacité | Visiteur | Étudiant | Mentor | Admin | Super Admin |
|---|:-:|:-:|:-:|:-:|:-:|
| Lire le fil public | ✓ (limité) | ✓ | ✓ | ✓ | ✓ |
| Publier une question | – | ✓ | ✓ | ✓ | ✓ |
| Publier un témoignage | – | ✓ | ✓ | ✓ | ✓ |
| Publier un conseil mentor | – | – | ✓ (vérifié) | – | – |
| Publier une opportunité | – | – | ✓ (vérifié) | ✓ | ✓ |
| Commenter | – | ✓ | ✓ | ✓ | ✓ |
| Mettre en favori | – | ✓ | ✓ | ✓ | ✓ |
| Messagerie privée | – | ✓ | ✓ | – | – |
| Modérer un signalement | – | – | – | ✓ | ✓ |
| Valider un mentor | – | – | – | ✓ | ✓ |
| Gérer les admins | – | – | – | – | ✓ |

### 4.2 Évolution SQL

```sql
ALTER TABLE utilisateur
  MODIFY COLUMN role ENUM('visiteur','etudiant','mentor','admin','super_admin')
                NOT NULL DEFAULT 'etudiant';
-- est_admin devient redondant ; à retirer lors de la migration.
```

---

## 5. Évolutions de la base de données

### 5.1 Tables à ajouter

| Table | Rôle |
|---|---|
| `pilier` | Référentiel : académique, professionnel, financier |
| `theme` | Référentiel : intégration, orientation, stage, emploi, budget, freelance… |
| `publication` | Remplace `question` (polymorphe) |
| `publication_secteur` | M-N publication ↔ secteur |
| `commentaire` | Remplace `reponse` (générique, arborescent) |
| `favori` | Fusionne `sauvegarde` + `suivi_mentor` |
| `etablissement` | Université / école (facultatif, pour le profil étudiant) |

### 5.2 Tables à modifier

| Table | Modification |
|---|---|
| `utilisateur` | ENUM `role` enrichi + champ `id_etablissement` + retirer `est_admin` |
| `notification` | Lien `lien_publication` au lieu de `lien_question` |

### 5.3 Tables à supprimer (après migration des données)

`question`, `reponse`, `marquage_question`, `marquage_reponse`, `sauvegarde`, `suivi_mentor` → fondues dans le nouveau modèle.

### 5.4 Vues à mettre à jour

`v_question_stats` → `v_publication_stats`
`v_mentor_carte` → inchangée

---

## 6. Évolutions du backend

### 6.1 Routes à modifier

| Préfixe actuel | Évolution |
|---|---|
| `/api/questions/*` | Renommer `/api/publications/*`, prendre le `type` en paramètre |
| `/api/reponses/*` | Renommer `/api/commentaires/*` |
| `/api/profil/referentiels` | Ajouter `piliers`, `themes`, `etablissements` |

### 6.2 Routes à ajouter

| Route | Rôle |
|---|---|
| `POST /api/auth/google` | OAuth Google réel (Google Identity Services) |
| `POST /api/auth/admin/connexion` | Connexion admin séparée (rate-limit plus strict) |
| `GET /api/favoris?type=publication\|utilisateur\|...` | Mes favoris unifiés |
| `POST /api/favoris` | Ajouter |
| `DELETE /api/favoris/<type>/<id>` | Retirer |
| `GET /api/fil?pilier=...&theme=...` | Fil thématique |
| `POST /api/admin/admins` | Création d'admin (Super Admin uniquement) |

### 6.3 Décorateurs à enrichir

```python
@role_requis('mentor', 'admin', 'super_admin')   # liste blanche par rôle
@mentor_verifie_requis                            # mentor vérifié uniquement
@super_admin_requis                               # gestion des admins
```

### 6.4 Sécurité supplémentaire pour l'admin

- Rate-limit `/api/auth/admin/connexion` : 3 tentatives / 30 min au lieu de 5 / 15 min
- 2FA obligatoire (TOTP) pour `admin` et `super_admin` (champ `mfa_secret` sur `utilisateur`)
- Journal d'audit : table `audit_admin` (qui a fait quoi, quand)

---

## 7. Évolutions du frontend

### 7.1 Page d'accueil refondue

**Structure proposée** (par ordre vertical) :

1. **Bandeau navigation** (logo + 2 CTA : « Se connecter » / « Créer un compte »)
2. **Hero épuré** : titre + introduction (texte long, voir section 8) + CTA principal unique
3. **Sélecteur « Qu'est-ce qui vous amène ? »** (3 cartes cliquables → onboarding adapté)
    - Je m'intègre à l'université
    - Je prépare mon orientation
    - Je veux mentorer
4. **Bandeau social proof** (chiffres-clés, sobre, sans surcharge)
5. **Section « Comment ça fonctionne »** en 3 étapes
6. **Section « Trois piliers »** (académique, pro, financier) avec icônes SVG
7. **Pied de page**

→ **Supprimer** les 3 cartes Q&A illustratives du hero (overload visuel).

### 7.2 Vues à ajouter

| Vue | Rôle |
|---|---|
| `vue-pilier` | Page d'un pilier (académique/pro/financier) avec son propre fil filtré |
| `vue-publication` | Lecture d'une publication (ex `vue-question`, adaptée au type) |
| `vue-favoris` | Mes favoris (4 onglets) |
| `vue-publier` | Modal/page de publication adaptative selon le rôle et le type choisi |

### 7.3 Vues à retirer du SPA grand public

- `sv-admin` → migré dans `/admin/index.html`
- Lien « Administration » du menu profil → retiré

### 7.4 Connexion réelle au backend

Aujourd'hui `seConnecter()` ne fait que `toast('Connexion réussie. Bienvenue !')`. Cible : remplacer par un véritable `fetch('/api/auth/connexion')` avec gestion des erreurs et stockage du jeton.

---

## 8. Texte d'introduction — 3 propositions

### Version A — Sobre et factuelle

> LaSourcee met en relation les étudiants avec des professionnels, des
> diplômés et des personnes ayant déjà parcouru le chemin qui les
> intéresse. Posez vos questions, lisez les retours d'expérience,
> avancez avec des conseils concrets — académiques, professionnels ou
> financiers.

### Version B — Orientée parcours utilisateur

> Vous entrez à l'université, vous préparez une orientation, vous
> cherchez votre premier stage ou vous voulez monter un revenu en
> parallèle de vos études ? **LaSourcee** vous met directement en
> contact avec celles et ceux qui sont déjà passés par là.
>
> Demandez, écoutez, choisissez en connaissance de cause.

### Version C — Plus narrative *(recommandée pour le hero)*

> Trop d'étudiants choisissent à l'aveugle.
>
> **LaSourcee** rassemble des mentors, des diplômés et des
> professionnels qui acceptent de répondre publiquement aux questions
> que vous vous posez : sur les études, le métier, l'argent, la vie
> universitaire. Les réponses sont gratuites, écrites par des humains
> qui ont déjà fait le chemin, et accessibles à toute la communauté.

**Recommandation :** la version C en hero, la version A reprise dans la section « Comment ça fonctionne ».

---

## 9. Roadmap par phases

Ordre conçu pour maximiser la valeur ajoutée à chaque incrément, sans jamais casser ce qui marche.

### Phase 1 — Fondations (3 à 5 jours) — *priorité haute*

**But :** rendre la plateforme réellement utilisable de bout en bout, séparer l'admin, refondre la landing.

| Action | Fichiers |
|---|---|
| Brancher inscription/connexion sur l'API existante | `script.js` (fonctions `seConnecter`, `commencerOnboarding`) |
| Migrer le rôle vers ENUM enrichi | `database/schema.sql`, `backend/routes/auth.py`, `backend/utils/auth_helpers.py` |
| Créer le portail admin séparé | `admin/index.html` (nouveau), `admin/admin.js`, `admin/admin.css` |
| Retirer `sv-admin` du SPA | `index.html`, `script.js` |
| Refondre la landing (suppression cartes Q&A, ajout sélecteur « qu'est-ce qui vous amène ? ») | `index.html` (section `vue-accueil`), `styles.css` |
| Mettre à jour le texte d'introduction | `index.html` (hero) |
| Ajouter le rate-limit renforcé pour l'admin | `backend/utils/securite.py`, `backend/routes/auth.py` |

### Phase 2 — Modèle de publication unifié (4 à 6 jours)

**But :** permettre aux mentors et aux anciens étudiants de publier librement.

| Action | Fichiers |
|---|---|
| Schéma : tables `publication`, `commentaire`, migration des données | `database/schema.sql`, script de migration `database/migration_v2.sql` |
| Routes API `/api/publications/*` et `/api/commentaires/*` | `backend/routes/publications.py` (nouveau), `backend/routes/commentaires.py` (nouveau) |
| Suppression des anciennes routes `/api/questions`, `/api/reponses` (ou wrappers de compatibilité) | `backend/routes/questions.py`, `backend/routes/reponses.py` |
| UI : carte de publication adaptative (badge type, code couleur) | `script.js` (fonction `cartePublicationHTML`), `styles.css` |
| Modal de publication adaptative selon rôle | `index.html` (modale), `script.js` (`publierContenu()`) |

### Phase 3 — Trois piliers thématiques (3 à 4 jours)

**But :** matérialiser les piliers académique / professionnel / financier dans l'UX.

| Action | Fichiers |
|---|---|
| Tables `pilier` + `theme` + données de référence | `database/schema.sql` |
| Filtres par pilier et thème dans le fil | `backend/routes/publications.py`, `script.js` (`rendreFil`) |
| Sous-vues dédiées par pilier (URL `#pilier/academique`) | `index.html`, `script.js` (`naviguerPilier`) |
| Icônes SVG des 3 piliers | `script.js` (objet `ICONES`) |

### Phase 4 — Favoris unifiés et profil étendu (3 à 4 jours)

**But :** unifier les sauvegardes et enrichir le profil étudiant.

| Action | Fichiers |
|---|---|
| Table `favori` polymorphe + migration `sauvegarde`/`suivi_mentor` | `database/schema.sql`, `database/migration_v2.sql` |
| Routes `/api/favoris/*` | `backend/routes/favoris.py` (nouveau) |
| Onglet « Mes favoris » à 4 filtres dans le profil | `index.html` (sv-profil), `script.js` (`ongletProfil`) |
| Table `etablissement` + champ profil | `database/schema.sql`, `backend/routes/profil.py` |

### Phase 5 — Engagement et viralité (5 à 7 jours) — *priorité basse*

| Action | Fichiers |
|---|---|
| Notifications navigateur (Push API) | nouveau `backend/services/push.py`, `script.js` |
| Système de réputation mentor (badges automatiques) | `backend/services/reputation.py` |
| Partage public d'une publication (lien direct, métadonnées Open Graph) | `index.html`, `backend/routes/publications.py` |
| Espace « Témoignages d'admis » filtrable par établissement | `script.js`, `backend/routes/publications.py` |

### Phase 6 — OAuth réel et 2FA (3 à 4 jours)

| Action | Fichiers |
|---|---|
| Google Sign-In (Google Identity Services côté front + vérification ID token côté back) | `index.html`, `script.js`, `backend/routes/auth.py` |
| LinkedIn OAuth 2.0 (idem) | idem |
| 2FA TOTP pour les comptes admin | `backend/utils/securite.py`, `backend/routes/auth.py`, `admin/admin.js` |

---

## 10. Recommandations stratégiques

### 10.1 Tenir la promesse « réponse humaine, gratuite, publique »

C'est le différenciateur principal vs LinkedIn, Discord et les groupes WhatsApp d'orientation. Toute fonctionnalité qui dilue ce principe (chatbot, contenu auto-généré, paywall) doit être refusée.

### 10.2 Mobile-first dès la phase 2

En Afrique francophone, l'usage est massivement mobile. La SPA actuelle a un media-query mobile mais la landing est pensée desktop. La refonte de phase 1 doit être conçue en partant du mobile, le desktop n'étant qu'une élévation.

### 10.3 Viralité par le contenu, pas par les notifications

Plutôt que des notifications push agressives, miser sur la **citabilité** :
- Chaque publication a un permalien partageable (ex : `lasource.io/p/abc123`)
- Une carte Open Graph soignée pour le partage WhatsApp / Telegram / Twitter
- Possibilité d'« épingler » une réponse remarquable sur le profil mentor

### 10.4 Modération transparente

Afficher publiquement les règles, justifier les suspensions visibles (sans dévoiler les motifs de signalement). Un signalement = une notification à l'auteur après traitement.

### 10.5 Garder le frontend déployable seul

Conserver la possibilité d'ouvrir `index.html` localement sans backend (mode démo avec données factices). Pour la démonstration au jury, c'est précieux : pas besoin d'avoir MySQL qui tourne.

### 10.6 Documenter dans le code, pas dans des outils tiers

Maintenir le `README.md` comme source unique. Préférer les commentaires français concis dans les fonctions plutôt qu'un wiki séparé qui se désynchronise.

### 10.7 Mesurer pour itérer

Dès la mise en ligne réelle, ajouter trois compteurs en base (sans outil tiers) :
- Nombre de visiteurs uniques par jour
- Taux d'inscription après visite
- Taux de réponse d'une question dans les 48 h

Sans ces trois nombres, impossible de savoir si la plateforme fonctionne.

---

## 11. Benchmark international

> Méthode : les descriptions ci-dessous reposent sur ce qui est
> publiquement connu de ces plateformes. Quand l'information n'est pas
> fiable, c'est indiqué explicitement plutôt que d'extrapoler.

### 11.1 Mentorat étudiant et alumni

**ADPList** — marketplace gratuite où les mentors (designers, PM, devs)
ouvrent des créneaux de 15 à 45 minutes que les mentees réservent via un
calendrier intégré. Friction minimale.
- À reprendre : badges et classements publics qui valorisent les mentors actifs (boucle de réputation visible).
- À éviter : la gratuité totale rend la qualité hétérogène et l'engagement mentor fragile.

**MentorCruise** — abonnement mensuel payant (200 à 400 USD) entre un
mentee et un mentor unique, messagerie continue et appels hebdomadaires.
- À reprendre : matching guidé par formulaire structuré puis essai gratuit de 7 jours.
- À éviter : modèle économique inadapté au pouvoir d'achat étudiant africain.

### 11.2 Réseaux alumni

**Hivebrite** — SaaS en marque blanche pour réseaux alumni
institutionnels (annuaire, événements, groupes, job board).
- À reprendre : segmentation fine de l'annuaire (promo, géo, secteur, compétence) + emailing ciblé pour réactiver les profils dormants.
- À éviter : outil descendant, peu d'incitation native à l'entraide pair-à-pair.

**Ten Thousand Coffees** — algorithme qui propose chaque mois un binôme
« café virtuel » à des membres d'une même communauté.
- À reprendre : la cadence imposée (un match par mois) qui transforme l'intention en habitude sans effort actif.
- À éviter : si la base d'utilisateurs est trop petite, les matchs deviennent redondants.

### 11.3 Orientation académique

**JobTeaser** — plateforme déployée dans les services carrière des
universités européennes (stages, contenus d'orientation, événements).
- À reprendre : intégration directe avec les bureaux d'aide à l'insertion (adoption institutionnelle plutôt qu'organique).
- À éviter : très orienté recrutement employeur, le conseil entre pairs reste secondaire.

**MyMajors** — questionnaire d'auto-évaluation qui recommande des
filières universitaires avec score de correspondance.
- À reprendre : restitution visuelle simple (top filières + pourquoi), compréhensible par un lycéen.
- À éviter : tout repose sur un test unique, sans suivi ni dialogue humain.

### 11.4 Communautés Q&A

**Reddit (subreddits universitaires)** — forums modérés avec tri par votes,
capital de savoir consultable sans inscription.
- À reprendre : archivage searchable des questions résolues, base de connaissances vivante.
- À éviter : anonymat total + toxicité possible ; modèle très anglo-saxon, peu transposable sur un public africain francophone qui privilégie la relation interpersonnelle identifiée.

**Discord (serveurs étudiants)** — salons texte/voix permanents avec
entraide en temps réel.
- À reprendre : rôles configurables (année, filière, mentor) qui structurent la communauté.
- À éviter : lourd en data mobile, exige une connexion stable — problème pour le public africain hors wifi.

### 11.5 Éducation financière jeune public

**Khan Academy (parcours Personal Finance)** — cours vidéo gratuits
structurés en modules courts avec quiz.
- À reprendre : granularité des modules (5 à 10 min) pour consommation mobile par micro-sessions.
- À éviter : contenu américain (crédit étudiant, 401k, FICO) — peu pertinent pour la réalité bancaire africaine.

**Pixpay** (néobanque ado française) — carte + appli avec contrôle
parental et missions de gamification autour de l'épargne.
- À reprendre : gamification des objectifs d'épargne.
- À éviter : modèle B2C payant, dépendant d'un système bancaire mature.

> L'agent n'a pas trouvé d'information fiable sur « Yomoni Future »
> spécifiquement dédié au jeune public et a refusé d'inventer.

### 11.6 Plateformes africaines pertinentes

**Andela** — sélection ultra-sélective de développeurs africains, puis
placement chez des clients internationaux en remote.
- À reprendre : parcours de progression structuré (assessment, formation, placement) — trajectoire claire et lisible.
- À éviter : modèle top-down et élitiste, qui n'aide pas la masse des étudiants en orientation.

**Ingressive for Good (I4G)** — association panafricaine (bourses,
formations tech gratuites, opportunités) animée via Discord/WhatsApp.
- À reprendre : usage massif de WhatsApp et Telegram comme canaux principaux d'animation, alignés avec les usages réels du public jeune africain.
- À éviter : très dépendant de financements externes et d'un noyau bénévole — modèle économique pérenne flou.

**ALU (African Leadership University) — réseau alumni** — accompagnement
entrepreneurial avec mentors industrie identifiés par secteur.
- À reprendre : ancrage du mentorat dans une mission de carrière concrète plutôt que dans une discussion ouverte (échanges plus actionnables).
- À éviter : niche élitiste, non directement transposable hors d'un écosystème privé.

> L'agent a explicitement refusé de noter une vingtaine d'autres
> plateformes (Sayna, Wits-CMU, Mentor & Reverse, Pathstream, AlumNet,
> AlumniFire, Graduway, Wizbii, Career Karma, Roadtrip Nation, Polywork,
> Studocu, Yubo, Quora, Cashlib, Tomorrow Money, etc.) faute
> d'information fiable suffisante. Une recherche terrain ciblée
> (entretiens locaux, captures d'app) serait nécessaire avant inclusion.

### 11.7 Bonnes pratiques retenues pour LaSourcee

1. **Cadencer la rencontre plutôt que la rendre élective** — s'inspirer
   de Ten Thousand Coffees en proposant un match mensuel automatique
   mentor-mentee pour transformer l'intention vague en habitude.
2. **Hybrider gratuité et engagement vérifié** — éviter le piège ADPList
   en introduisant un mécanisme de réputation visible (badges, statut
   « mentor actif du mois », validations par les pairs) pour soutenir la
   qualité sans frais d'entrée.
3. **Mobile-first et data-light** — modules courts façon Khan Academy
   (5-10 min), pas de visio lourde par défaut, fallback texte/audio sur
   WhatsApp ou Telegram (méthode Ingressive for Good).
4. **Ancrer les contenus financiers dans la réalité locale** — remplacer
   les exemples FICO / 401k par mobile money, tontines, freelance en
   ligne, micro-entrepreneuriat ; produire avec des mentors africains
   identifiés pour leur légitimité.
5. **Rendre la confiance lisible** — profils mentors complets et
   vérifiés (parcours, école, employeur, témoignages), à l'opposé de
   l'anonymat Reddit ; afficher le modèle économique pour lever la
   défiance vis-à-vis des plateformes opaques.
6. **S'appuyer sur des relais institutionnels** — le succès de JobTeaser
   tient à son intégration dans les bureaux carrière ; nouer des
   partenariats avec services d'orientation, amicales et associations
   étudiantes pour amorcer l'adoption par bouche-à-oreille structuré.
7. **Trois parcours distincts mais connectés** — académique /
   professionnel / financier doivent avoir leurs entrées propres dans le
   produit ; un onboarding aiguille dès la première session vers le bon
   parcours et le bon mentor (un nouvel étudiant ne cherche pas la même
   chose qu'un L3 en quête de master).

---

## Validation attendue

Merci de valider ou amender :

1. **L'architecture de séparation admin** (portail dédié sous `/admin/`)
2. **Le modèle de publication polymorphe** (remplace `question`)
3. **La structure en 3 piliers + thèmes**
4. **Les 5 rôles et leur matrice de permissions**
5. **L'ordre des 6 phases** de la roadmap
6. **Le choix de texte d'introduction** (A, B ou C)

Une fois ces six points validés, la phase 1 peut démarrer.
