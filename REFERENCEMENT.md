# Référencement de LaSourcee

Ce document décrit ce qui est en place, ce qui reste à faire de votre
côté, et pourquoi chaque choix a été fait. Le référencement se joue sur
des mois : l'essentiel est de partir juste, puis de publier.

---

## Ce qui est en place

### Identité de la page

| Élément | Valeur |
|---|---|
| Titre | LaSourcee, plateforme de mentorat et d'orientation |
| Description | met en relation bénéficiaires et référents expérimentés |
| URL canonique | `https://lasourcee.org/` |
| Langue déclarée | `fr` |

L'URL canonique désigne l'apex, sans `www`. C'est elle qui doit être
principale dans Vercel, avec `www` en redirection : deux adresses qui
répondent au même contenu diluent le référencement, les moteurs ne
sachant pas laquelle citer.

### Mots-clés déclarés

Google ignore la balise `keywords` depuis 2009. **Bing s'en sert
encore** comme signal secondaire, et l'exercice a une vertu propre : il
oblige à nommer précisément ce que le site propose.

Les termes retenus reprennent ce que le public tape réellement, pas des
mots génériques :

```
mentorat étudiant, orientation scolaire, conseil de carrière,
éducation financière, choisir sa filière,
poser une question à un professionnel, mentor étudiant Afrique,
orientation universitaire Bénin, reconversion professionnelle,
premier emploi, stage étudiant, référent professionnel
```

Deux d'entre eux sont géographiques. Sur une requête générale comme
« orientation scolaire », un site qui démarre n'a aucune chance face aux
portails installés. Sur « orientation universitaire Bénin », la
concurrence est mince et le visiteur bien plus qualifié. C'est là qu'un
site jeune se classe.

### Données structurées

Trois blocs JSON-LD, que les moteurs lisent directement :

- **WebSite et Organization** : nom, description, logo. Ils permettent
  d'afficher le nom du site plutôt que l'URL brute dans les résultats.
- **SearchAction** : Google peut afficher un champ de recherche interne
  sous le nom du site.
- **FAQPage** : quatre questions fréquentes, susceptibles d'apparaître
  dépliées dans les résultats. Elles occupent plus de place et
  répondent avant même le clic.

Les réponses décrivent le fonctionnement réel du site. Un contenu
structuré qui ne correspond pas à la page est sanctionné.

### Partage sur les réseaux

Balises Open Graph et Twitter Card, avec une image de 1200 × 630 pixels.
Sans elles, un lien partagé sur WhatsApp ou LinkedIn n'affiche qu'une
adresse nue, et le taux de clic s'effondre.

### Exploration

- `robots.txt` autorise l'indexation et déclare le plan du site.
- `sitemap.xml` liste les pages publiques.
- L'API et les pages de jeton (confirmation d'adresse, réinitialisation)
  sont exclues : elles n'ont rien à faire dans un index, et leurs URL
  contiennent des jetons à usage unique.

---

## À faire de votre côté

### 1. Google Search Console

[search.google.com/search-console](https://search.google.com/search-console)

1. Ajoutez la propriété `lasourcee.org` (type « Domaine »).
2. Validez par un enregistrement DNS `TXT` chez Hostinger.
3. Soumettez `https://lasourcee.org/sitemap.xml`.
4. Demandez l'indexation de la page d'accueil.

### 2. Bing Webmaster Tools

[bing.com/webmasters](https://www.bing.com/webmasters)

Bing représente une part non négligeable des recherches, et il indexe
les sites jeunes plus vite que Google. Il permet d'importer directement
la propriété depuis Search Console, ce qui évite de tout refaire.

Bing alimente aussi ChatGPT et Copilot : y être référencé compte
désormais autant qu'être dans Google.

### 3. Choisir le domaine principal

Dans **Vercel → Settings → Domains** : `lasourcee.org` en principal,
`www.lasourcee.org` en redirection. Sans cela, les moteurs voient deux
sites au contenu identique.

---

## Ce qui fera vraiment la différence

Les balises ne créent pas de trafic. Elles permettent seulement d'être
correctement compris quand il y a quelque chose à comprendre.

**Le contenu décide.** Chaque question posée et chaque réponse publiée
créent une page susceptible d'être trouvée. Quelqu'un qui cherche
« faut-il un master pour travailler dans la data » tombera sur cette
question précise, si elle existe et si elle a une vraie réponse.

Trois choses comptent, dans cet ordre :

1. **Des questions réelles, formulées comme on parle.** « Comment
   décrocher un stage en finance quand on étudie au Bénin » vaut mieux
   que « Stages finance ».
2. **Des réponses substantielles.** Trois lignes ne se référencent pas.
   Une réponse détaillée par un référent vérifié, oui.
3. **De la régularité.** Vingt questions en un mois valent mieux que
   deux cents d'un coup puis plus rien.

**Comptez trois à six mois** avant de voir un trafic de recherche
significatif. C'est le délai normal pour un domaine neuf, quoi qu'en
disent les promesses de référencement rapide.

---

## Étape suivante, quand le contenu existera

Aujourd'hui le site est une application d'une seule page : une seule URL
à indexer. Quand vous aurez plusieurs dizaines de questions, il faudra
donner à chacune sa propre adresse, du type
`lasourcee.org/question/comment-choisir-sa-filiere-en-informatique`.

C'est ce qui multiplierait les portes d'entrée : chaque question
deviendrait une page susceptible de ressortir sur sa propre requête.
Cela demande un rendu côté serveur pour ces pages, et un ajout
automatique au plan du site.

Ce chantier n'a de sens qu'une fois le contenu présent. L'engager
maintenant reviendrait à construire des rayonnages avant d'avoir des
livres.
