# Domaine chez Hostinger — où héberger LaSourcee

Le domaine `lasourcee.org` est pris chez Hostinger. Reste à décider **où
tourne l'application**, et c'est une décision qui doit être prise avant
d'importer le moindre fichier.

---

## Le point à connaître avant tout

**L'hébergement web mutualisé de Hostinger — les formules Premium et
Business — n'exécute pas Python.** Il fait tourner PHP et MySQL.
Installer Python demande un accès root, pour poser l'interpréteur, gérer
les paquets avec pip et créer un environnement virtuel : les formules
mutualisées et cloud n'y donnent pas accès. Seul le VPS le permet.

Or le backend de LaSourcee est écrit en Python, avec Flask.

Conséquence concrète si les fichiers sont importés sur un hébergement
mutualisé : **la page d'accueil s'affichera normalement, avec sa mise en
page et son logo, mais rien ne fonctionnera.** Ni inscription, ni
connexion, ni administration. Chaque formulaire renverra une erreur —
exactement le `405 Method Not Allowed` rencontré sur GitHub Pages, pour
la même raison : personne n'exécute le code serveur.

C'est le pire scénario pour une démonstration : un site qui a l'air
correct et s'effondre au premier clic.

---

## Deux chemins possibles

### A. Hostinger pour le domaine, Vercel pour l'application

**Recommandé.** Le domaine acheté reste utilisé, l'application tourne là
où elle fonctionne, et cela ne coûte rien de plus : l'offre gratuite de
Vercel suffit largement pour ce projet.

Hostinger sert alors de bureau d'enregistrement — son rôle principal —
et Vercel sert le site. Les visiteurs ne voient que `lasourcee.org`.

**Ce qu'il faut faire :**

1. Dans l'assistant Hostinger, **passer l'étape d'import de fichiers**.
   Il n'y a rien à importer.
2. Déployer sur Vercel en suivant [`DEPLOIEMENT.md`](DEPLOIEMENT.md)
   (base PostgreSQL, variables d'environnement, déploiement).
3. Dans Vercel : **Settings → Domains → Add**, saisir `lasourcee.org`.
   Vercel affiche alors les enregistrements DNS à créer.
4. Dans Hostinger : **Domaines → lasourcee.org → DNS / Serveurs de noms
   → Gérer les enregistrements DNS**, et créer :

   | Type | Nom | Valeur |
   |---|---|---|
   | `A` | `@` | `76.76.21.21` |
   | `CNAME` | `www` | `cname.vercel-dns.com` |

   **Prendre les valeurs affichées par Vercel plutôt que celles de ce
   tableau** : elles peuvent changer, et l'écran de Vercel fait foi.

5. Attendre la propagation DNS — de quelques minutes à quelques heures.
   Vercel émet le certificat HTTPS automatiquement.

> Si Hostinger a déjà pointé le domaine vers son propre hébergement,
> supprimez d'abord l'enregistrement `A` existant sur `@`. Deux
> enregistrements `A` contradictoires enverraient les visiteurs
> alternativement sur les deux hébergements.

### B. Tout chez Hostinger, sur un VPS

Possible, mais c'est un autre métier : il faut administrer un serveur.
Le VPS donne un accès root complet et fait tourner Python sans
difficulté. Comptez environ 6,50 $ par mois pour la formule d'entrée
(KVM 1 : 1 vCPU, 4 Go de RAM), en plus du domaine.

Il faut alors installer soi-même : Python 3 et pip, un environnement
virtuel, PostgreSQL ou rester sur SQLite, Gunicorn comme serveur WSGI,
Nginx en frontal, et Certbot pour le certificat HTTPS. La marche à
suivre figure dans [`MISE_EN_SERVICE.md`](MISE_EN_SERVICE.md), section
« Sur un serveur classique ».

Ce chemin a un avantage : sur un VPS le disque est persistant, donc
SQLite suffit et il n'y a pas de base externe à provisionner. Il a un
coût : les mises à jour de sécurité du serveur, les sauvegardes et la
surveillance sont à votre charge.

---

## Comparaison

| | A — Vercel | B — VPS Hostinger |
|---|---|---|
| Coût mensuel | 0 € | environ 6,50 $ |
| Mise en place | 30 minutes | une demi-journée |
| Base de données | PostgreSQL externe, gratuit | SQLite sur disque local |
| Certificat HTTPS | automatique | Certbot, à renouveler |
| Mises à jour serveur | aucune | à votre charge |
| Sauvegardes | gérées par l'hébergeur de base | à mettre en place |
| Déploiement | `git push` | manuel, ou à scripter |

---

## Ce qu'il ne faut pas faire

**Importer le projet sur l'hébergement mutualisé.** Le site s'affichera,
et c'est précisément le piège : l'apparence sera correcte, mais aucun
compte ne pourra être créé. Si la formule Business a déjà été payée,
elle reste utile pour le domaine et l'adresse e-mail professionnelle —
mais pas pour faire tourner l'application.

---

## Une adresse e-mail au bon domaine

Quelle que soit l'option retenue, l'offre Hostinger inclut généralement
des boîtes aux lettres sur le domaine. Une adresse comme
`contact@lasourcee.org` comme expéditeur des e-mails de la plateforme
vaut mieux qu'une adresse Gmail : les messages de confirmation
d'inscription arrivent moins souvent en indésirable, et la plateforme
paraît plus sérieuse.

Une fois la boîte créée, relevez ses paramètres SMTP dans hPanel et
renseignez dans la configuration de l'application :

```env
EMAIL_MODE=smtp
SMTP_HOTE=smtp.hostinger.com
SMTP_PORT=587
SMTP_UTILISATEUR=contact@lasourcee.org
SMTP_MOTDEPASSE=le-mot-de-passe-de-la-boite
SMTP_EXPEDITEUR=LaSourcee <contact@lasourcee.org>
SMTP_SECURITE=starttls
```

Vérifiez l'envoi avant d'ouvrir au public :

```bash
cd backend && python gerer_admins.py tester-email votre.adresse@gmail.com
```

---

## Sources

- [Hostinger Python Hosting Review](https://hostadvice.com/hosting-company/hostinger-reviews/hostinger-python-hosting-review/)
- [Can Hostinger Run Python Scripts?](https://ratingeer.com/blog/can-hostinger-run-python-scripts)
