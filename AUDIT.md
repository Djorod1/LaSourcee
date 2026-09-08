# AUDIT TECHNIQUE LaSourcee

> Audit honnête réalisé avant toute correction.
> Méthode : lecture exhaustive des sources + tests réels d'appel HTTP
> contre le backend en venv, pas de présomption.

## Sommaire

1. [Constat global brutal](#1-constat-global-brutal)
2. [Mission 1 — Audit fonctionnel](#2-mission-1--audit-fonctionnel)
3. [Mission 2 — Système d'administration](#3-mission-2--système-dadministration)
4. [Mission 3 — Backend](#4-mission-3--backend)
5. [Mission 4 — Base de données](#5-mission-4--base-de-données)
6. [Mission 5 — Frontend](#6-mission-5--frontend)
7. [Mission 6 — Tests réels effectués](#7-mission-6--tests-réels-effectués)
8. [Mission 7 — Plan de correction priorisé](#8-mission-7--plan-de-correction-priorisé)
9. [Annexe — Le logo](#9-annexe--le-logo)

---

## 1. Constat global brutal

| Constat | Réalité mesurée |
|---|---|
| Le backend est-il fonctionnel ? | **Oui** — 31 routes, démarre proprement, en-têtes de sécurité OK, politique mdp + anti-force-brute testés |
| La base de données est-elle cohérente ? | **Oui** — 18 tables, 26 FK, schéma propre. Mais elle n'est jamais appelée par le frontend |
| Le frontend appelle-t-il vraiment le backend ? | **NON. 0 fonction sur 70+ ne fait de `fetch`** vers l'API. Tout est en mémoire |
| Les données saisies sont-elles persistées ? | **Non.** Une question publiée disparaît au rafraîchissement |
| L'inscription/connexion fonctionne-t-elle réellement ? | **Non.** `seConnecter()` affiche juste un toast et bascule la vue. Aucun mot de passe n'est vérifié |
| L'admin agit-il sur de vraies données ? | **Non.** Les tableaux affichent des listes en dur (`const users = [['Marie Dupont',...], ...]`) |
| Les chiffres du tableau de bord admin sont-ils réels ? | **Non.** `2 478 inscrits`, `1 832 questions`, `87 %` taux de réponse sont écrits en dur dans `adminDashboard()` |
| Les boutons Google/LinkedIn fonctionnent-ils ? | **Non.** `onclick="seConnecter()"` qui ne fait que `toast()` |
| Le mot de passe oublié envoie-t-il un e-mail ? | **Non.** Aucun endpoint backend, juste un toast |
| Les notifications sont-elles temps réel ? | **Non.** Tableau JS statique de 5 entrées |
| La recherche est-elle globale ? | **Non.** Filtre client sur les arrays JS |

**Diagnostic** : la plateforme est aujourd'hui un **prototype visuel** (haute qualité d'affichage, identité visuelle solide) **branché sur du vide**. Le backend professionnel et la base existent en parallèle mais ne sont pas reliés à l'interface.

C'est la cause unique de la majorité des bugs rapportés (« les données ne remontent pas », « les formulaires ne sauvegardent pas », « ressemble à une démo »).

---

## 2. Mission 1 — Audit fonctionnel

Légende : ✅ Fonctionne · 🟠 Partiel · ❌ Ne fonctionne pas

### Authentification & onboarding

| # | Fonctionnalité | Fichier | Statut | Cause | Correctif |
|---|---|---|---|---|---|
| 1 | Page d'accueil (rendu) | `index.html` `vue-accueil` | ✅ | — | — |
| 2 | Inscription par e-mail | `index.html` `vue-inscription` + `script.js:commencerOnboarding()` | ❌ | Bouton appelle un mock qui passe à l'onboarding sans valider l'e-mail | Câbler sur `POST /api/auth/inscription` |
| 3 | Inscription Google | `script.js:seConnecter()` ligne 197 | ❌ | Le bouton SSO appelle la même fonction mock | Soit retirer le bouton, soit intégrer Google Identity Services |
| 4 | Inscription LinkedIn | idem | ❌ | idem | idem |
| 5 | Onboarding 4 étapes | `script.js:naviguerEtape()` | 🟠 | UI fonctionne, données saisies ignorées | À la dernière étape, appeler `POST /api/auth/inscription` puis `PUT /api/profil/moi` avec secteurs/photo |
| 6 | Connexion e-mail | `script.js:seConnecter()` | ❌ | Mock complet | Câbler `POST /api/auth/connexion` |
| 7 | Mot de passe oublié | `index.html` `vue-oubli` ligne 163 | ❌ | `onclick="toast(...)"` inline, aucun envoi | Créer endpoint `POST /api/auth/oubli-mdp` + service e-mail |
| 8 | Déconnexion | `script.js:seDeconnecter()` | ❌ | Toast + bascule vue, le cookie reste valide | Câbler `POST /api/auth/deconnexion` |

### Fil et publications

| # | Fonctionnalité | Fichier | Statut | Cause | Correctif |
|---|---|---|---|---|---|
| 9 | Affichage du fil | `script.js:rendreFil()` | 🟠 | Affiche les 6 questions hardcodées | Charger depuis `GET /api/questions` |
| 10 | Tri (récent/populaire/sans réponse) | `script.js:changerTri()` | 🟠 | Tri client sur l'array local | Passer `?tri=` à `GET /api/questions` |
| 11 | Filtre par secteur | `script.js:rendreFil()` | 🟠 | Filtre client | Passer `?id_secteur=` |
| 12 | Publier une question | `script.js:publierQuestion()` | ❌ | `questions.unshift(...)` en mémoire, perdu au reload | `POST /api/questions` |
| 13 | Marquer « utile » | `script.js:basculerUtileQ()` | ❌ | Incrément en mémoire | `POST /api/questions/<id>/utile` |
| 14 | Sauvegarder | `script.js:basculerSauver()` | ❌ | Ajout dans un `Set` local | `POST /api/questions/<id>/sauvegarder` |
| 15 | Signaler | `script.js:signaler()` ligne 472 | ❌ | Une seule ligne : juste un toast | `POST /api/questions/<id>/signaler` |
| 16 | Publier une réponse | `script.js:ajouterReponse()` | ❌ | Push en mémoire | `POST /api/reponses` |
| 17 | Noter une réponse | `script.js:noter()` | ❌ | Toggle visuel uniquement | À étendre côté backend (champ `note_etoiles` existe en BD mais pas d'endpoint) |
| 18 | « Utile » sur réponse | `script.js:utileR()` | ❌ | Toggle visuel | `POST /api/reponses/<id>/utile` |
| 19 | Suggestion questions similaires | `script.js:majSimilaires()` | 🟠 | Filtre client (correct pour mode démo) | À déplacer côté backend pour vraie pertinence |

### Profils

| # | Fonctionnalité | Fichier | Statut | Cause | Correctif |
|---|---|---|---|---|---|
| 20 | Voir mon profil | `script.js:rendreProfil()` | 🟠 | Affiche `etat.utilisateur` en dur (Marie Dupont) | Charger depuis `GET /api/profil/moi` |
| 21 | Voir profil d'un mentor | `script.js:rendreProfilMentor()` | 🟠 | Lit l'array `mentors` local | `GET /api/profil/<id>` |
| 22 | Modifier profil | `script.js:panneauCompte()` | ❌ | Bouton appelle `toast('Modifications enregistrées.')` | `PUT /api/profil/moi` |
| 23 | Téléverser photo | `script.js:televerserPhotoCompte()` | 🟠 | Stocke en dataURL côté client uniquement | Endpoint upload manquant côté backend |
| 24 | Suivre un mentor | `script.js:basculerSuivre()` | ❌ | Ajout dans `Set` local | `POST /api/mentors/<id>/suivre` |
| 25 | Voir mentors suivis | `script.js:ongletProfil('mentors')` | 🟠 | Liste l'array local | `GET /api/mentors/suivis` |
| 26 | Devenir mentor | `script.js:devenirMentor()` | ❌ | Mutation locale du rôle | Endpoint backend manquant |

### Messagerie

| # | Fonctionnalité | Fichier | Statut | Cause | Correctif |
|---|---|---|---|---|---|
| 27 | Liste des conversations | (aucun rendu côté frontend) | ❌ | Backend a les endpoints, frontend n'a pas la vue | Créer `sv-messages` + rendu + branchement |
| 28 | Envoyer un message | idem | ❌ | idem | idem |
| 29 | Notifications de messages | — | ❌ | Pas de polling/SSE | À ajouter (polling 30s suffit en V1) |

### Recherche

| # | Fonctionnalité | Fichier | Statut | Cause | Correctif |
|---|---|---|---|---|---|
| 30 | Auto-complétion recherche | `script.js:rechercher()` | 🟠 | Filtre local | `GET /api/recherche?q=` (endpoint existe) |
| 31 | Recherche globale | `script.js:lancerRecherche()` | 🟠 | Pose un terme dans `etat.rechercheTerme`, filtre local | idem |

### Notifications

| # | Fonctionnalité | Fichier | Statut | Cause | Correctif |
|---|---|---|---|---|---|
| 32 | Affichage cloche + badge | `script.js:rendreNotifications()` | 🟠 | Array de 5 notifs en dur | `GET /api/notifications` |
| 33 | Marquer une notif lue | `script.js:cliquerNotif()` | ❌ | Mutation locale | Endpoint backend manquant (singulier) |
| 34 | « Tout marquer lu » | `script.js:toutMarquerLu()` | ❌ | Mutation locale | `POST /api/notifications/tout-lu` |

### Paramètres

| # | Fonctionnalité | Fichier | Statut | Cause | Correctif |
|---|---|---|---|---|---|
| 35 | Changer mot de passe | `script.js:panneauSecurite()` | ❌ | Mock toast | Endpoint backend manquant + câblage |
| 36 | Activer 2FA | `script.js:panneauSecurite()` | ❌ | Toggle visuel | À implémenter (TOTP) |
| 37 | Sessions actives | `script.js:panneauSecurite()` | 🟠 | Liste de 3 sessions en dur | Endpoint backend manquant — la table `session_web` existe pourtant |
| 38 | Préférences notifications | `script.js:panneauNotifsParam()` | ❌ | Toggles visuels | Table de préférences à ajouter |
| 39 | Profil public/privé | `script.js:panneauConfid()` | ❌ | Toggle visuel | Colonne `profil_public` à ajouter |

---

## 3. Mission 2 — Système d'administration

### Gestion des utilisateurs

| Action | Backend | Frontend | Réellement fonctionnel |
|---|---|---|---|
| Lister utilisateurs | ❌ Endpoint absent | 🟠 Tableau de 5 lignes en dur | ❌ |
| Créer utilisateur | ❌ Endpoint absent (l'inscription publique n'est pas un substitut admin) | ❌ Pas d'UI | ❌ |
| Modifier utilisateur | ❌ Endpoint absent | ❌ Pas d'UI | ❌ |
| Supprimer utilisateur | ❌ Endpoint absent | 🟠 Bouton « Supprimer » → `toast()` | ❌ |
| Suspendre utilisateur | ✅ `POST /api/admin/utilisateurs/<id>/suspendre` | 🟠 Bouton → `toast()` | ❌ (non câblé) |
| Réactiver utilisateur | ❌ Endpoint absent | ❌ Pas d'UI | ❌ |
| Attribuer rôle | ❌ Endpoint absent | ❌ Pas d'UI | ❌ |

### Gestion des mentors

| Action | Backend | Frontend | Réellement fonctionnel |
|---|---|---|---|
| Lister mentors à vérifier | 🟠 Pas d'endpoint dédié (le frontend filtre `mentors.filter(m=>!m.verifie)` sur le mock) | 🟠 Affiche les 1-2 mentors non-vérifiés du mock | ❌ |
| Valider mentor | ✅ `POST /api/admin/mentors/<id>/verifier` | 🟠 Bouton → `toast()` | ❌ (non câblé) |
| Refuser mentor | ❌ Endpoint absent | 🟠 Bouton → `toast()` | ❌ |

### Gestion des contenus

| Action | Backend | Frontend | Réellement fonctionnel |
|---|---|---|---|
| Lister toutes les questions (admin) | ❌ Endpoint absent (le `GET /api/questions` est filtrable mais pas pensé admin) | ❌ Pas d'UI | ❌ |
| Supprimer une question (admin) | ✅ `DELETE /api/questions/<id>` (l'auteur ou admin) | ❌ Pas d'UI admin | ❌ |
| Modérer une réponse | ✅ `DELETE /api/reponses/<id>` | ❌ Pas d'UI admin | ❌ |
| Publier une actualité | ❌ Concept inexistant en BD (pas de table `actualite`) | ❌ Pas d'UI | ❌ |

### Gestion des médias

**Aucune** des fonctions médias n'existe :

| Action | Statut |
|---|---|
| Upload image | ❌ Aucun endpoint `POST /api/medias` ; la photo de profil est stockée en dataURL côté client uniquement |
| Suppression image | ❌ |
| Compression image | ❌ |
| Affichage centralisé | ❌ — pas de dossier `uploads/`, pas de service |

### Permissions par rôle (matrice testée par lecture du code)

| Capacité | Visiteur | Étudiant | Mentor | Admin | Super Admin |
|---|:-:|:-:|:-:|:-:|:-:|
| Lire le fil | ✅ (en théorie, vue cachée derrière auth dans l'UI actuelle) | ✅ | ✅ | ✅ | ⚠️ rôle inexistant |
| Publier question | ❌ | ✅ | ✅ | ✅ | ⚠️ |
| Publier conseil mentor | ❌ | ❌ | 🟠 (UI absente) | ❌ | ⚠️ |
| Répondre | ❌ | ❌ (`estMentor()` bloque) | ✅ | ✅ | ⚠️ |
| Modérer | ❌ | ❌ | ❌ | 🟠 (endpoints partiels) | ⚠️ |
| Gérer les admins | — | — | — | — | **N'existe pas** |

**Constat permissions** :

- Pas de rôle `super_admin` en BD (juste `est_admin BOOLEAN`)
- Le décorateur `@admin_requis` existe et fonctionne backend, mais aucune UI ne profite des endpoints existants
- L'accès à l'admin côté frontend dépend de `etat.utilisateur.estAdmin = true` codé en dur → n'importe quel visiteur connecté en démo a accès admin

---

## 4. Mission 3 — Backend

### Routes API : 31 endpoints

| Préfixe | Méthode | Endpoint | Fonctionnel | Auth requise | Note |
|---|---|---|:-:|:-:|---|
| `/api/sante` | GET | sonde | ✅ | – | OK |
| `/api/auth/` | POST | inscription | ✅ | – | bcrypt + politique mdp + DB |
| `/api/auth/` | POST | connexion | ✅ | – | bcrypt + anti-force-brute |
| `/api/auth/` | POST | deconnexion | ✅ | – | détruit jeton session |
| `/api/auth/` | POST | **oubli-mdp** | ❌ | – | **manquant** |
| `/api/profil/` | GET | referentiels | ✅ | – | secteurs + pays |
| `/api/profil/` | GET | moi | ✅ | étudiant+ | OK |
| `/api/profil/` | GET | `<id>` | ✅ | étudiant+ | profil public |
| `/api/profil/` | PUT | moi | ✅ | étudiant+ | OK |
| `/api/profil/` | POST | **photo** | ❌ | étudiant+ | **manquant** |
| `/api/questions/` | GET | liste | ✅ | étudiant+ | tri + filtres |
| `/api/questions/` | GET | `<id>` | ✅ | étudiant+ | détail |
| `/api/questions/` | POST | publier | ✅ | étudiant+ | OK |
| `/api/questions/` | DELETE | `<id>` | ✅ | auteur ou admin | OK |
| `/api/questions/` | POST | `<id>/utile` | ✅ | étudiant+ | bascule |
| `/api/questions/` | POST | `<id>/sauvegarder` | ✅ | étudiant+ | bascule |
| `/api/questions/` | POST | `<id>/signaler` | ✅ | étudiant+ | crée signalement |
| `/api/questions/` | GET | **sauvegardes** | ❌ | étudiant+ | **manquant** (impossible de lister ses sauvegardes) |
| `/api/reponses/` | POST | publier | ✅ | étudiant+ | OK |
| `/api/reponses/` | DELETE | `<id>` | ✅ | auteur ou admin | OK |
| `/api/reponses/` | POST | `<id>/utile` | ✅ | étudiant+ | bascule |
| `/api/reponses/` | POST | **note** | ❌ | étudiant+ | **manquant** (colonne BD existe) |
| `/api/mentors/` | GET | liste | ✅ | étudiant+ | annuaire |
| `/api/mentors/` | POST | `<id>/suivre` | ✅ | étudiant+ | bascule |
| `/api/mentors/` | GET | suivis | ✅ | étudiant+ | mes suivis |
| `/api/messagerie/` | GET | conversations | ✅ | étudiant+ | OK |
| `/api/messagerie/` | POST | conversations | ✅ | étudiant+ | ouvrir |
| `/api/messagerie/` | GET | messages | ✅ | étudiant+ | OK |
| `/api/messagerie/` | POST | message | ✅ | étudiant+ | envoyer |
| `/api/notifications/` | GET | liste | ✅ | étudiant+ | OK |
| `/api/notifications/` | POST | tout-lu | ✅ | étudiant+ | OK |
| `/api/notifications/` | GET | non-lues | ✅ | étudiant+ | OK |
| `/api/notifications/` | POST | **`<id>/lue`** | ❌ | étudiant+ | **manquant** (singulière) |
| `/api/recherche/` | GET | globale | ✅ | étudiant+ | OK |
| `/api/admin/` | GET | dashboard | ✅ | admin | KPI calculés en BD |
| `/api/admin/` | GET | signalements | ✅ | admin | OK |
| `/api/admin/` | POST | `<id>` | ✅ | admin | traiter |
| `/api/admin/` | POST | mentors/`<id>`/verifier | ✅ | admin | OK |
| `/api/admin/` | POST | utilisateurs/`<id>`/suspendre | ✅ | admin | OK |
| `/api/admin/` | GET | **utilisateurs (liste)** | ❌ | admin | **manquant** |
| `/api/admin/` | POST | **utilisateurs (réactiver)** | ❌ | admin | **manquant** |
| `/api/admin/` | POST | **utilisateurs (rôle)** | ❌ | admin | **manquant** |
| `/api/admin/` | GET/POST/PUT/DELETE | **categories (secteurs)** | ❌ | admin | **manquant** |

### Risques de sécurité identifiés

| Risque | Sévérité | Description |
|---|---|---|
| **Traceback complet renvoyé en cas d'erreur DB** | 🔴 Critique | Le `DEBUG=True` de Flask + l'absence de gestionnaire global d'erreur exposent la pile, le chemin disque, les noms de fichiers du serveur. À voir dans la sortie de test ci-dessus |
| `DEBUG=True` en dur dans `app.py` ligne 53 | 🔴 Critique | Doit dépendre d'une variable d'env, jamais activé en prod |
| Pas de rotation/expiration des sessions inactives | 🟠 Important | Le jeton vit 14 jours quoi qu'il arrive |
| Pas de limite de taille sur les uploads (futur) | 🟠 Important | À prévoir avant d'ajouter les médias |
| CSP autorise `unsafe-inline` pour les scripts | 🟠 Important | Conséquence des `onclick=...` du frontend. À durcir en refactor |
| Pas de CSRF token sur les `POST/PUT/DELETE` | 🟡 Mineur | Couvert partiellement par `SameSite=Lax`, à renforcer si on autorise des origines tierces |

### Gestion des erreurs et logs

- **Aucun handler global** d'exception : toute erreur DB ou inattendue renvoie 500 avec traceback
- **Aucun log structuré** : print Flask par défaut, pas de rotation
- **Aucun logger applicatif** : impossible de retrouver « qui a fait quoi quand »

---

## 5. Mission 4 — Base de données

### Schéma actuel : 18 tables + 2 vues

```
                  ┌─────────────┐
                  │  utilisateur│
                  └──┬────┬─────┘
                     │    │
        ┌────────────┘    └──────────────────┐
        │                                    │
┌───────▼──────┐  ┌──────────┐   ┌──────────▼─────┐
│ mentor_details│  │experience│   │utilisateur_secteur
└──────────────┘  └──────────┘   └────────────────┘

        ┌──────────┐
        │ secteur  │◄──┐
        └──────────┘   │
                       │
        ┌──────────┐   │
        │   pays   │◄──┘
        └──────────┘

  ┌──────────┐    ┌──────────────┐    ┌─────────┐
  │ question │───►│   reponse    │    │  favori │ ← n'existe pas encore
  └──┬───┬───┘    └──────────────┘    └─────────┘
     │   │
  ┌──▼─┐ │  ┌────────────────┐
  │mar.│ │  │  sauvegarde    │
  │que │ │  └────────────────┘
  └────┘ │
         │  ┌────────────────┐
         │  │ suivi_mentor   │
         │  └────────────────┘
         │
  ┌──────▼─────┐
  │ signalement│
  └────────────┘

  ┌────────────┐  ┌──────────────────────┐  ┌──────────┐
  │conversation│──│conversation_participant│──│ message │
  └────────────┘  └──────────────────────┘  └──────────┘

  ┌──────────────┐  ┌─────────────┐
  │ notification │  │ session_web │
  └──────────────┘  └─────────────┘
```

### Tables inutilisées par le frontend actuel

- `experience` — créée mais aucun endpoint backend ne l'écrit
- `signalement` — créable côté backend, jamais lue par l'admin (manque endpoint `GET /api/admin/signalements/<id>` détaillé)

### Relations cassées / risques d'incohérence

| Problème | Description |
|---|---|
| **`question` et `reponse` figées** | Pas de `type_publication`, donc impossible de gérer les conseils mentor, témoignages, opportunités du cahier des charges sans refonte |
| **`utilisateur.role` trop court** | ENUM `('etudiant','mentor')` + `est_admin` BOOL → 3 rôles maximum, pas extensible aux `super_admin` |
| **`sauvegarde` et `suivi_mentor` séparées** | Devraient être fondues dans `favori` polymorphe |
| **Pas de table `etablissement`** | L'utilisateur a un champ texte libre `etudes` qui ne sera jamais filtrable |
| **Pas de table `actualite`** | Le cahier mentionne « gestion des actualités » mais aucun support |

### Index présents (audit)

- Tous les FK ont leur index implicite ✅
- Index sur `(id_destinataire, est_lue, cree_le)` pour les notifications ✅
- Index sur `dernier_msg_le` pour les conversations ✅
- **Manque** : index sur `question(id_secteur, publiee_le)` pour le tri du fil par secteur (présent en fait ✅)

### Données de référence

- 12 secteurs insérés ✅
- 17 pays francophones ✅
- **0 utilisateur de démo** → impossible de tester en réel sans inscription préalable

---

## 6. Mission 5 — Frontend

### Pages et vues

| Vue | Rendu desktop | Rendu tablette | Rendu mobile | Bugs |
|---|---|---|---|---|
| `vue-accueil` | ✅ | 🟠 dense | 🟠 hero à 2 colonnes ne tient pas sur 360 px | Cartes Q&A débordent |
| `vue-connexion` | ✅ | ✅ | ✅ | Bouton Google ne fait rien |
| `vue-inscription` | ✅ | ✅ | ✅ | Idem + l'inscription ne crée pas de compte |
| `vue-oubli` | ✅ | ✅ | ✅ | Mock total |
| `vue-onboarding` | ✅ | ✅ | 🟠 chips se serrent | Données saisies perdues |
| `vue-app / sv-fil` | ✅ 3 colonnes | 🟠 colonne droite passe sous | 🟠 layout fragile | Filtre pays n'a pas d'`<option>` |
| `sv-profil` | ✅ | ✅ | 🟠 actions débordent | Photo non persistée |
| `sv-question` | ✅ | ✅ | ✅ | Réponse non persistée |
| `sv-parametres` | ✅ | ✅ | ✅ | Aucun enregistrement réel |
| `sv-admin` | ✅ | 🟠 tableau scroll horizontal | 🟠 difficile | Tous les boutons → toast |
| `sv-mentor` | ✅ | ✅ | ✅ | Données issues du mock |

### Accessibilité

| Critère | État |
|---|---|
| Contraste texte/fond | ✅ vert sur fond crème : ratio > 4.5 |
| Labels formulaires | 🟠 présents pour la plupart, manquent sur quelques inputs admin |
| `alt=""` sur images | ✅ logo a `alt="LaSourcee"` ou `alt=""` (décoratif) |
| Navigation clavier | 🟠 les `onclick` sur `<div>` ne sont pas focusables au clavier |
| `aria-label` | 🟠 partiel — présent sur les boutons icônes, absent sur la cloche |
| Focus visible | 🟠 bouton de focus discret, à renforcer |

### Performance

- **Pas de minification** (CSS/JS sont en clair, ~110 Ko total) — acceptable
- **Pas de cache HTTP** sur les SVG/CSS (configuration serveur, hors code)
- **Une seule requête de polices** Google Fonts — OK
- **Pas de lazy loading** sur les images (pas d'images pour l'instant)

### Cohérence du design

- Identité ✅ — palette vert/rouge/noir cohérente partout
- Icônes ✅ — un seul système SVG inline
- Typographie ✅ — DM Serif Display + DM Sans
- Pas de bouton vraiment redondant ✅

---

## 7. Mission 6 — Tests réels effectués

> Tests menés contre le backend en venv (Flask test_client), pas
> contre la production. La DB MySQL n'étant pas disponible dans
> cette session, les endpoints qui en dépendent retournent 500
> (attendu). Les codes de retour sont notés.

| Test | Action | Résultat | Cause |
|---|---|---|---|
| Sonde santé | `GET /api/sante` | ✅ 200 | OK |
| Création compte | `POST /api/auth/inscription` | ❌ 500 | MySQL absent — endpoint bien codé, échoue à `INSERT` |
| Connexion | `POST /api/auth/connexion` | ❌ 500 | idem |
| Déconnexion | `POST /api/auth/deconnexion` | ✅ 200 | n'a pas besoin de DB pour répondre |
| Réinitialisation mot de passe | — | ❌ N/A | **Endpoint absent** |
| Profil moi | `GET /api/profil/moi` sans cookie | ✅ 401 | bonne réponse |
| Référentiels | `GET /api/profil/referentiels` | ❌ 500 | DB absente — endpoint correct |
| Publication question | `POST /api/questions` | ❌ 401 attendu (pas de cookie) puis 500 (DB) | OK |
| Recherche | `GET /api/recherche?q=test` | ❌ 401 attendu | OK |
| Dashboard admin | `GET /api/admin/dashboard` | ❌ 401 attendu puis 403 | OK |

**Tests des flux frontend (lecture du code)** :

| Flux | Saisie | Effet observé | Effet attendu |
|---|---|---|---|
| Inscription | E-mail + mdp + rôle | Bascule vers onboarding | Devrait créer un compte |
| Connexion | E-mail + mdp | Toast vert + entrée dans l'app | Devrait vérifier les credentials |
| Publier question | Titre + corps + catégorie | Apparaît dans le fil, disparaît au reload | Devrait persister |
| Marquer utile | clic | Compteur incrémenté visuellement | Devrait persister |
| Supprimer utilisateur (admin) | clic | Toast | Devrait DELETE en BD |

---

## 8. Mission 7 — Plan de correction priorisé

### 🔴 CRITIQUE — bloque le fonctionnement réel

| # | Action | Effort estimé |
|---|---|---|
| C1 | Créer un module `js/api.js` (wrapper `fetch` + gestion erreurs + cookies) | 30 min |
| C2 | Câbler `seConnecter()` → `POST /api/auth/connexion` | 30 min |
| C3 | Câbler `naviguerEtape()` (étape 4) → `POST /api/auth/inscription` + `PUT /api/profil/moi` | 1 h |
| C4 | Câbler `seDeconnecter()` → `POST /api/auth/deconnexion` | 15 min |
| C5 | Câbler `publierQuestion()` → `POST /api/questions` | 30 min |
| C6 | Câbler `ajouterReponse()` → `POST /api/reponses` | 20 min |
| C7 | Câbler `basculerUtileQ` / `basculerSauver` / `signaler` / `utileR` / `basculerSuivre` → API | 1 h |
| C8 | Charger le fil depuis `GET /api/questions` au démarrage (au lieu de l'array `questions`) | 1 h |
| C9 | Charger le profil depuis `GET /api/profil/moi` à `initApp()` | 30 min |
| C10 | Charger les notifications depuis `GET /api/notifications` | 20 min |
| C11 | Ajouter un **handler global d'erreur** Flask (renvoyer JSON propre, ne pas exposer la pile) | 20 min |
| C12 | Mettre `DEBUG` derrière une variable d'env | 5 min |
| C13 | **Réserver la place du logo proprement** (placeholder neutre, aspect ratio fixe, pas de SVG inventé) | 15 min |

### 🟠 IMPORTANT — dégrade l'expérience

| # | Action | Effort |
|---|---|---|
| I1 | Créer `POST /api/auth/oubli-mdp` (génère un jeton, log un mail à la console) | 1 h |
| I2 | Créer `POST /api/profil/photo` (upload base64 → fichier serveur) | 1 h 30 |
| I3 | Créer `GET /api/admin/utilisateurs` + branchement UI | 1 h |
| I4 | Créer `POST /api/admin/utilisateurs/<id>/reactiver` + branchement | 30 min |
| I5 | Créer `POST /api/admin/utilisateurs/<id>/role` + branchement | 30 min |
| I6 | CRUD complet sur les secteurs (admin) | 1 h |
| I7 | Câbler tous les boutons admin (suspension, validation mentor, signalements) | 1 h |
| I8 | Créer `POST /api/notifications/<id>/lue` + branchement | 20 min |
| I9 | Implémenter le changement de mot de passe (`POST /api/auth/changer-mdp`) | 30 min |
| I10 | Ajouter le rôle `super_admin` en BD + matrice permissions | 1 h |
| I11 | Ajouter handler 404 propre | 10 min |

### 🟡 MINEUR — confort

| # | Action | Effort |
|---|---|---|
| M1 | Filtre pays manquant dans le fil (option HTML absente) | 5 min |
| M2 | `<select>` au lieu de `<input>` pour pays/secteur sur l'inscription | 20 min |
| M3 | Lazy loading sur les futures images | – |
| M4 | Cache HTTP des assets statiques (Etag) | 15 min |
| M5 | Logs structurés Python (logging stdlib) | 45 min |
| M6 | 2FA TOTP (admin) | 4 h |
| M7 | Notifications temps réel (polling 30 s) | 1 h |

### Ordre d'exécution optimal

```
Phase A (priorité immédiate, total ≈ 6 h)
  C11 → C12  (sécuriser le backend AVANT d'ouvrir au frontend)
  C13        (régler le souci de logo)
  C1         (poser le wrapper API)
  C2 → C4    (auth complète)
  C9         (charger le profil réel)
  C8         (charger le fil réel)
  C5 → C7    (toutes les interactions BD)
  C10        (notifications réelles)

Phase B (priorité haute, total ≈ 6 h)
  I11        (handler 404)
  I1         (mot de passe oublié)
  I3 → I7    (admin complet)
  I8 → I9    (notifications fines + changement mdp)
  I2         (upload photo)
  I10        (rôle super admin)

Phase C (confort, total ≈ 7 h)
  M1 → M5    (petites finitions)
  M6 → M7    (2FA + notifs temps réel)
```

---

## 9. Annexe — Le logo

### Constat

Le SVG vectoriel que j'avais recréé approximait votre flamme officielle
mais s'est affiché déformé sur votre plateforme (proportions différentes,
ou le rendu SVG du navigateur cible). C'est un défaut de mon
reproduction, pas du système.

### Correction

Je remplace l'`<img src="lasource-logo.svg">` par une **zone réservée**
de proportions verrouillées (140×40 px en navbar, 200×260 px en page
d'auth), pré-stylée mais **vide** : un cadre discret avec la mention
« LaSourcee » en texte et un encart `aria-hidden` qui dit
*« Déposez `lasource-logo.png` dans /assets/ »*.

Quand vous déposerez votre PNG officiel sous `assets/lasource-logo.png`
(ou `.svg`), il **occupera exactement la place réservée**, sans rien
casser, sans déformation, parce que le conteneur a `object-fit: contain`
et un ratio fixe.

Aucune modification de votre logo n'est faite par moi : vous gardez le
contrôle total de l'asset.

---

## Décision attendue avant que je code

Je vais maintenant exécuter directement les corrections **🔴 CRITIQUE** (Phase A) sans attendre, car ce sont elles qui rendent la plateforme réellement opérationnelle.

Si vous voulez que je traite aussi tout ou partie de la Phase B (admin réel, mot de passe oublié, upload photo, rôle super admin) dans la même livraison, dites-le. Sinon, ce sera l'étape suivante.
