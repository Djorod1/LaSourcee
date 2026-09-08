# Logo LaSourcee — déposer ici vos fichiers officiels

La plateforme **réserve la place** du logo sans chercher à le
reproduire : une recréation automatique s'était affichée déformée, et
c'est votre fichier qui doit faire foi.

## Les trois fichiers attendus

Remplacez ces fichiers par vos versions, en conservant **exactement**
ces noms. Aucune autre modification n'est nécessaire : le code les
charge déjà aux bons endroits.

| Fichier | Contenu | Où il apparaît |
|---|---|---|
| `lasource-logo.png` | logo complet : symbole **et** le mot « LaSourcee » | pages de connexion, d'inscription et de mot de passe oublié |
| `lasource-symbole.png` | symbole seul : soleil et silhouettes, **sans texte** | barre de navigation, en-tête de l'accueil |
| `favicon.png` | le symbole, carré | onglet du navigateur, écran d'accueil mobile |

Un quatrième fichier, `lasource-partage.png`, est l'aperçu affiché quand
le lien du site est partagé sur WhatsApp ou LinkedIn. Il est généré à
partir du symbole ; regénérez-le si vous changez l'identité visuelle.

## Formats

| Fichier | Dimensions conseillées | Remarques |
|---|---|---|
| `lasource-logo.png` | 736 × 608 px ou plus | fond **transparent**, ratio proche de 1,21:1 |
| `lasource-symbole.png` | 512 × 512 px, carré | fond **transparent** |
| `favicon.png` | 180 × 180 px, carré | fond transparent ou uni |
| `lasource-partage.png` | 1200 × 630 px exactement | imposé par les réseaux sociaux |

Le fond transparent est important : le logo est posé sur du blanc comme
sur du bleu selon les écrans. Un fond blanc opaque laisserait un
rectangle visible.

## Pourquoi le logo ne sera pas déformé

Chaque emplacement est un conteneur aux proportions fixes :

- **46 × 46 px** dans la barre de navigation (`.logo-zone-navbar`) ;
- **168 × 139 px** sur les pages d'authentification (`.logo-zone-auth`).

L'image y est insérée avec `object-fit: contain` : elle est mise à
l'échelle proportionnellement, jamais étirée. Si un fichier est absent,
un cadre neutre prend sa place et la page reste lisible — le site ne
casse pas.

## Couleurs de la charte

Reprises de `styles.css`, où elles sont définies une seule fois.

| Rôle | Code | Variable CSS |
|---|---|---|
| Bleu royal (principal) | `#1E3A8A` | `--bleu` |
| Bleu foncé | `#14275C` | `--bleu-fonce` |
| Bleu vif | `#2563EB` | `--bleu-vif` |
| Orange (soleil du logo) | `#F97316` | `--orange-vif` |
| Noir des textes | `#0F172A` | `--noir` |
| Fond de page | `#F6F9FF` | `--fond` |

## Après le remplacement

Rechargez la page en vidant le cache (Ctrl+Maj+R, ou Cmd+Maj+R sur Mac) :
les navigateurs gardent longtemps les images en mémoire.
