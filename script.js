/* =========================================================
   LaSourcee — Logique applicative (vanilla JS)
   ========================================================= */

/* ---------- État global ---------- */
const etat = {
  // Aucune identite par defaut. Ce bloc decrivait une etudiante fictive,
  // administratrice de surcroit : de quoi faire clignoter le nom de
  // quelqu'un qui n'existe pas, et afficher un instant des commandes
  // d'administration a un visiteur. appliquerUtilisateur() remplace
  // l'objet entier des que le serveur a repondu.
  utilisateur: {
    prenom: '', nom: '', initiales: '',
    role: 'etudiant', pays: '', etudes: '',
    bio: '',
    secteurs: [],
    estAdmin: false,
    questionsPosees: 0, mentorsSuivis: 0,
    photo: null // base64 dataURL
  },
  tri: 'recent',
  categorieChoisie: null,
  roleChoisi: 'etudiant',
  etapeOnboarding: 1,
  ongletProfil: 'questions',
  utilesQ: new Set(),       // ids des questions marquées utiles par moi
  sauvegardees: new Set(),  // ids des questions sauvegardées
  suivis: new Set(),        // ids des mentors suivis
  rechercheTerme: '',
  sectionActive: 'fil'
};

/* ---------- Données de démonstration ---------- */
/* Annuaire des mentors, alimenté par le serveur (voir chargerMentorsDepuisApi). */
const mentors = [];

/* Fil des questions, alimenté par le serveur (voir chargerFilDepuisApi). */
const questions = [];

/* Notifications, alimentées par le serveur (voir chargerNotificationsDepuisApi). */
const notifications = [];

/* ---------- Helpers avatar (photo ou initiales) ---------- */
/* Pastille de presence. « en_ligne » est calcule par le serveur : le
   navigateur ne connait ni l'heure du serveur ni le seuil retenu, et
   deux navigateurs mal regles afficheraient deux etats differents pour
   la meme personne.

   Trois etats et non deux : en ligne, vu recemment, et rien du tout.
   Un point gris permanent pour quelqu'un qui n'est jamais venu ne dit
   rien d'utile et encombre. */
function pastillePresence(enLigne, derniereActivite) {
  if (enLigne) {
    return '<span class="presence en-ligne" title="En ligne"'
      + ' aria-label="En ligne"></span>';
  }
  if (!derniereActivite) return '';
  return `<span class="presence hors-ligne"
    title="Vu ${echapper(_tempsRelatif(derniereActivite))}"
    aria-label="Hors ligne, vu ${echapper(_tempsRelatif(derniereActivite))}"></span>`;
}

/* Phrase de presence, pour les endroits ou une pastille ne suffit pas. */
function textePresence(u) {
  if (!u) return '';
  if (u.en_ligne) return 'En ligne';
  if (u.derniere_activite) return 'Vu ' + _tempsRelatif(u.derniere_activite);
  return '';
}

function avatarHTML(initiales, taille = '', photo = null, mentorVerifie = false) {
  const cls = 'avatar' + (taille ? ' avatar-' + taille : '') + (mentorVerifie ? ' mentor-verifie' : '');
  if (photo) return `<div class="${cls}"><img src="${photo}" class="photo-avatar" alt=""></div>`;
  return `<div class="${cls}">${initiales}</div>`;
}
/* Badge mentor vérifié (innovation : couleur vert du logo, lecture immédiate) */
function badgeMentorVerifie() {
  return `<span class="badge-mentor-verifie">${ic('check','ic ic-s')} Référent vérifié</span>`;
}
function monAvatarHTML(taille = '') { return avatarHTML(etat.utilisateur.initiales, taille, etat.utilisateur.photo); }
function estMentor() { return etat.utilisateur.role === 'mentor'; }

/* ---------- Échappement HTML (protection contre l'injection XSS) ----------
   Tout contenu saisi par un utilisateur (titre, bio, message…) doit passer
   par cette fonction avant d'être inséré via innerHTML.                      */
function echapper(valeur) {
  return String(valeur ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/* ---------- Jeu d'icônes (SVG en ligne, tracé fin, couleur héritée) ----------
   Aucune dépendance externe, aucun emoji : chaque icône est un tracé vectoriel
   qui hérite de la couleur du texte via stroke:currentColor.                   */
const ICONES = {
  accueil:    '<path d="M3 11.4 12 4l9 7.4"/><path d="M5.5 9.8V20h13V9.8"/>',
  cloche:     '<path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6"/><path d="M10 21h4"/>',
  profil:     '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 4-6.5 8-6.5s8 2.1 8 6.5"/>',
  groupe:     '<circle cx="8.5" cy="9" r="3"/><path d="M2.5 19.5c0-3.2 2.7-4.8 6-4.8s6 1.6 6 4.8"/><path d="M16 6.2a3 3 0 0 1 0 5.6"/><path d="M17.6 14.9c1.9.5 3.4 1.8 3.4 4.1"/>',
  reglages:   '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.2 5.2l2.1 2.1M16.7 16.7l2.1 2.1M18.8 5.2l-2.1 2.1M7.3 16.7l-2.1 2.1"/>',
  bouclier:   '<path d="M12 3 5 6v5.2c0 4.4 3 7.8 7 9.8 4-2 7-5.4 7-9.8V6z"/>',
  deconnexion:'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 16.5 20.5 12 16 7.5"/><path d="M20.5 12H9"/>',
  graphique:  '<path d="M4 20V4"/><path d="M4 20h16"/><rect x="7" y="12" width="3" height="5"/><rect x="12" y="8" width="3" height="9"/><rect x="17" y="5" width="3" height="12"/>',
  drapeau:    '<path d="M5.5 21V4"/><path d="M5.5 4.5h11l-2 4 2 4h-11"/>',
  etiquette:  '<path d="M3 12.5V5.5A2 2 0 0 1 5 3.5h7l9 9-8.5 8.5z"/><circle cx="8" cy="8.2" r="1.3"/>',
  position:   '<path d="M12 21.2s6.6-5.9 6.6-10.6a6.6 6.6 0 1 0-13.2 0C5.4 15.3 12 21.2 12 21.2Z"/><circle cx="12" cy="10.4" r="2.5"/>',
  ecole:      '<path d="M3 8.2 12 4.4l9 3.8-9 3.8z"/><path d="M21 8.2v5"/><path d="M7 10.3V15c0 1.4 2.2 2.6 5 2.6s5-1.2 5-2.6v-4.7"/>',
  appareil:   '<rect x="3" y="7" width="18" height="13" rx="2.2"/><path d="M8.5 7 10 4.7h4L15.5 7"/><circle cx="12" cy="13.3" r="3.3"/>',
  crayon:     '<path d="M4 20.2 8 19 19 8l-3-3L5 16z"/><path d="M14.5 6.5 17.5 9.5"/>',
  marque:     '<path d="M7 4h10v16l-5-3.2L7 20z"/>',
  bulle:      '<path d="M4 5h16v10.5H9L4.5 20z"/>',
  livre:      '<path d="M5 4.5h10.5a1.6 1.6 0 0 1 1.6 1.6V20H6.5A1.6 1.6 0 0 1 5 18.4z"/><path d="M8.5 4.5V20"/>',
  mallette:   '<rect x="3" y="7.2" width="18" height="12.5" rx="2"/><path d="M8 7.2V5.4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v1.8"/><path d="M3 12.5h18"/>',
  diplome:    '<path d="M3 8.4 12 4.6l9 3.8-9 3.8z"/><path d="M20.4 8.7v4.6"/><path d="M7 11V15c0 1.4 2.2 2.6 5 2.6s5-1.2 5-2.6v-4"/>',
  trophee:    '<path d="M7 4.5h10V8a5 5 0 0 1-10 0z"/><path d="M7 5.8H4.2v1.6a3 3 0 0 0 3 3"/><path d="M17 5.8h2.8v1.6a3 3 0 0 1-3 3"/><path d="M9.5 14.2h5"/><path d="M10 14.2v3h4v-3"/><path d="M8 20h8"/>',
  etincelle:  '<path d="M12 3.2 13.8 9 19.5 10.8 13.8 12.6 12 18.4 10.2 12.6 4.5 10.8 10.2 9z"/>',
  cadenas:    '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  // Un histogramme plutot qu'une fleche ascendante : la fleche est
  // devenue un marqueur de generation automatique, on la voit
  // partout. Les barres disent la meme chose sans cet air de
  // deja-vu.
  tendance:   '<path d="M4 20V13"/><path d="M9.5 20V8"/><path d="M15 20V15"/><path d="M20.5 20V4"/>',
  check:      '<path d="M4.5 12.5 9.5 17.5 19.5 6.5"/>',
  croix:      '<path d="M6 6 18 18M18 6 6 18"/>',
  loupe:      '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>',
  alerte:     '<path d="M12 4 21 19.5H3z"/><path d="M12 10v4.2M12 17.2v.2"/>',
};
function ic(nom, classe = 'ic') {
  return `<svg class="${classe}" viewBox="0 0 24 24" aria-hidden="true">${ICONES[nom] || ''}</svg>`;
}

/* ============================================================
   NAVIGATION
   ============================================================ */
function afficherVue(id) {
  document.querySelectorAll('.vue').forEach(v => v.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo(0, 0);
}

function naviguerApp(panneau) {
  document.querySelectorAll('.sous-vue').forEach(sv => sv.style.display = 'none');
  const cible = document.getElementById('sv-' + panneau);
  if (cible) cible.style.display = 'block';
  document.getElementById('menuProfil').classList.remove('ouvert');
  etat.sectionActive = panneau;
  majNavActif();

  // La section est inscrite dans l'adresse : un rafraîchissement, un
  // retour arrière ou un lien partagé retrouvent le même écran. Sans
  // cela, toute actualisation ramenait au fil d'accueil.
  const vise = '#' + panneau;
  if (window.location.hash !== vise) {
    window.history.replaceState({}, '', window.location.pathname + vise);
  }
  if (panneau === 'fil') rendreFil();
  if (panneau === 'profil') rendreProfil();
  if (panneau === 'mentor') rendreEspaceMentor();
  if (panneau === 'messages') rendreMessagerie();
  if (panneau === 'parametres') changerPanParam(document.querySelector('#menu-param button.actif'), 'compte');
  if (panneau === 'admin') {
    // Le menu est ajusté avant l'affichage : montrer un onglet puis le
    // faire disparaître serait plus déroutant que de ne jamais le
    // montrer.
    ajusterMenuAdmin();
    changerPanAdmin(document.querySelector('.menu-admin button.actif'), 'dashboard');
  }
}

function majNavActif() {
  document.querySelectorAll('.nav-bouton').forEach(b => {
    b.classList.toggle('actif', b.dataset.section === etat.sectionActive);
  });
}

/* ============================================================
   AUTHENTIFICATION & ONBOARDING
   ============================================================ */
function choisirRole(elem, role) {
  document.querySelectorAll('.carte-role').forEach(c => c.classList.remove('actif'));
  elem.classList.add('actif');
  etat.roleChoisi = role;
}
/* Connexion par e-mail et mot de passe. Le serveur fait foi. */
async function seConnecter() {
  const email = (document.getElementById('email-conn')?.value || '').trim().toLowerCase();
  const mdp = document.getElementById('mdp-conn')?.value || '';
  if (!email || !mdp) {
    return toast('Saisissez votre e-mail et votre mot de passe.', 'erreur');
  }

  try {
    await API.post('/auth/connexion', { email, mot_de_passe: mdp });
    MODE.utilisateur = await API.get('/profil/moi');
    appliquerUtilisateur(MODE.utilisateur);
    toast('Connexion réussie. Bienvenue !');
    afficherVue('vue-app'); initApp();
  } catch (err) {
    // Adresse non confirmée : proposer le renvoi du lien plutôt que de
    // laisser la personne devant un refus sans issue.
    if (err.donnees && err.donnees.confirmation_requise) {
      ouvrirConfirmationAdresse(err.donnees.email || email);
      return;
    }
    toast(err.message || 'Identifiants incorrects.', 'erreur');
  }
}

/* ----- Connexion OAuth Google -----
   Utilise Google Identity Services (chargé dans index.html).
   Demande un ID token, puis l'envoie au backend pour vérification. */
/* Consentement avant Google.

   Le bouton ouvrait directement la fenêtre de Google, et le compte se
   créait avec le nom, l'adresse et la photo sans que personne n'ait rien
   accepté ni même lu. Google demande l'autorisation de partager ces
   informations ; il ne demande pas ce que LaSourcee en fera. C'est à
   nous de le dire, et de le demander, avant d'ouvrir sa fenêtre.

   Le panneau est refusé tant que les deux cases nécessaires ne sont pas
   cochées, et il énumère précisément ce qui sera reçu. */
function connecterGoogle() {
  if (!window.GOOGLE_CLIENT_ID) {
    return toast('Connexion Google non configurée sur ce serveur.', 'erreur');
  }
  ouvrirConsentementGoogle();
}

function ouvrirConsentementGoogle() {
  fermerMentionsLegales();
  const fond = document.createElement('div');
  fond.className = 'modale-fond';
  fond.id = 'modaleLegale';
  fond.setAttribute('role', 'dialog');
  fond.setAttribute('aria-modal', 'true');
  fond.innerHTML = `
    <div class="modale-boite">
      <div class="modale-entete">
        <h2>Continuer avec Google</h2>
        <button class="modale-fermer" onclick="fermerMentionsLegales()" aria-label="Fermer">&times;</button>
      </div>
      <div class="modale-corps">
        <p>Google nous transmettra les informations suivantes, et rien
           d'autre :</p>
        <ul class="liste-donnees">
          <li><strong>Votre nom et prénom</strong>, tels qu'ils figurent
            sur votre compte Google.</li>
          <li><strong>Votre adresse e-mail</strong>, ainsi que
            l'indication qu'elle est vérifiée.</li>
          <li><strong>Votre photo de profil</strong>, si vous en avez une.</li>
        </ul>
        <p class="desc">Nous n'avons accès ni à vos messages, ni à vos
           contacts, ni à vos fichiers. LaSourcee ne peut rien publier en
           votre nom.</p>

        <fieldset class="bloc-consentement">
          <legend>Votre autorisation</legend>
          <label class="case-consentement">
            <input type="checkbox" id="g-donnees" onchange="majBoutonGoogle()" />
            <span>J'autorise LaSourcee à recevoir de Google mon nom, mon
              adresse e-mail et ma photo, et à les conserver pour mon
              compte.</span>
          </label>
          <label class="case-consentement">
            <input type="checkbox" id="g-conditions" onchange="majBoutonGoogle()" />
            <span>J'ai lu et j'accepte les
              <a href="#" onclick="event.preventDefault(); ouvrirMentionsLegales('conditions');">conditions d'utilisation</a>
              et la
              <a href="#" onclick="event.preventDefault(); ouvrirMentionsLegales('confidentialite');">politique de confidentialité</a>.</span>
          </label>
          <label class="case-consentement">
            <input type="checkbox" id="g-notifs" />
            <span>J'accepte de recevoir par e-mail les réponses à mes
              questions. <em>Facultatif.</em></span>
          </label>
        </fieldset>

        <button class="btn btn-primaire" id="btn-google-suite" disabled
                onclick="lancerGoogle(this)">Continuer avec Google</button>
        <p class="aide-champ">Vous pourrez supprimer votre compte et
           toutes ces informations à tout moment, depuis vos paramètres.</p>
      </div>
    </div>`;
  fond.addEventListener('click', (e) => {
    if (e.target === fond) fermerMentionsLegales();
  });
  document.body.appendChild(fond);
  document.body.style.overflow = 'hidden';
}

function majBoutonGoogle() {
  const bouton = document.getElementById('btn-google-suite');
  if (!bouton) return;
  bouton.disabled = !(document.getElementById('g-donnees')?.checked
                      && document.getElementById('g-conditions')?.checked);
}

function majBoutonInscription() {
  // Rien à désactiver ici : le contrôle a lieu au clic, avec un message
  // qui dit ce qui manque. Un bouton grisé sans explication laisse
  // chercher.
}

async function lancerGoogle(bouton) {
  const consentement = {
    donnees: !!document.getElementById('g-donnees')?.checked,
    conditions: !!document.getElementById('g-conditions')?.checked,
    notifications: !!document.getElementById('g-notifs')?.checked,
  };
  if (!(consentement.donnees && consentement.conditions)) return;
  bouton.disabled = true;
  fermerMentionsLegales();
  _lancerGoogleAvecConsentement(consentement);
}

async function _lancerGoogleAvecConsentement(consentement) {
  const clientId = window.GOOGLE_CLIENT_ID;
  if (!window.google || !window.google.accounts) {
    return toast('Bibliothèque Google non chargée. Vérifiez votre connexion.', 'erreur');
  }
  window.google.accounts.id.initialize({
    client_id: clientId,
    callback: async (reponse) => {
      try {
        await API.post('/auth/google',
                       { credential: reponse.credential, consentement });
        SESSION.utilisateur = await API.get('/profil/moi');
        appliquerUtilisateur(SESSION.utilisateur);
        toast('Connexion réussie. Google a confirmé votre adresse, aucun '
              + "e-mail de vérification n'est nécessaire.");
        afficherVue('vue-app'); initApp();
      } catch (err) {
        toast(err.message || 'Connexion Google impossible.', 'erreur');
      }
    },
  });
  window.google.accounts.id.prompt();
}

/* ----- Connexion OAuth LinkedIn -----
   Redirection vers l'endpoint backend qui lance le flow Authorization Code. */
function connecterLinkedIn() {
  if (!window.LINKEDIN_CONFIGURE) {
    return toast(
      'LinkedIn OAuth non configuré. Ajoutez LINKEDIN_CLIENT_ID dans backend/.env '
      + '(voir README).', 'erreur'
    );
  }
  window.location.href = '/api/auth/linkedin';
}

/* Mot de passe oublié — demande réelle d'envoi de mail. */
async function demanderReinitialisation() {
  const email = (document.getElementById('email-oubli')?.value || '').trim().toLowerCase();
  if (!email.includes('@')) {
    return toast('Adresse e-mail invalide.', 'erreur');
  }
  if (!MODE.api) {
    // Mode navigateur : on confirme sans révéler l'existence du compte
    toast('Si cet e-mail correspond à un compte, un lien de réinitialisation a été envoyé.');
    afficherVue('vue-connexion'); return;
  }
  try {
    await API.post('/auth/oubli-mdp', { email });
    toast('Si cet e-mail correspond à un compte, vous recevrez un lien dans quelques minutes.');
    afficherVue('vue-connexion');
  } catch (err) {
    toast(err.message || 'Demande impossible.', 'erreur');
  }
}

/* Synchronise l'état UI avec l'utilisateur retourné par /api/profil/moi. */
function appliquerUtilisateur(u) {
  if (!u) return;
  const initiales = ((u.prenom || '?')[0] + (u.nom || '?')[0]).toUpperCase();
  etat.utilisateur = {
    id: u.id_utilisateur,
    prenom: u.prenom || '',
    nom: u.nom || '',
    initiales,
    role: u.role || 'etudiant',
    pays: u.pays || '',
    etudes: u.etudes || '',
    bio: u.bio || '',
    secteurs: (u.secteurs || []).map(s => s.libelle),
    estAdmin: !!u.est_admin,
    questionsPosees: 0,
    mentorsSuivis: 0,
    photo: u.photo_url || null,
    verifie: !!u.est_verifie,
    doit_changer_mdp: !!u.doit_changer_mdp,
    email_verifie: !!u.email_verifie,
    email: u.email || '',
    situation: u.situation || '',
    objectif: u.objectif || '',
    langues: u.langues || '',
    profil_pro: u.profil_pro || '',
    niveau_etudes: u.niveau_etudes || '',
    domaine: u.domaine || '',
    etablissement: u.etablissement || '',
    telephone: u.telephone || '',
    objectifs: u.objectifs || [],
  };
  majRappelMotDePasse();
  majRappelConfirmation();
  majRappelProfil();
  chargerCompteurCandidatures();
  chargerCompteurMessages();
  demarrerReleveNotifications();
}
/* Validation des champs de l'inscription AVANT de passer à l'onboarding. */
function commencerOnboarding() {
  const prenom = (document.getElementById('prenom-ins')?.value || '').trim();
  const nom = (document.getElementById('nom-ins')?.value || '').trim();
  const email = (document.getElementById('email-ins')?.value || '').trim().toLowerCase();
  const mdp = document.getElementById('mdp-ins')?.value || '';
  const mdp2 = document.getElementById('mdp2-ins')?.value || '';

  if (!prenom || !nom) return toast('Prénom et nom obligatoires.', 'erreur');
  if (!email.includes('@') || email.length < 6) return toast('Adresse e-mail invalide.', 'erreur');
  if (mdp.length < 8) return toast('Mot de passe : 8 caractères minimum.', 'erreur');
  if (!/[a-zA-Z]/.test(mdp) || !/\d/.test(mdp)) {
    return toast('Le mot de passe doit mélanger lettres et chiffres.', 'erreur');
  }
  if (mdp !== mdp2) return toast('Les deux mots de passe ne correspondent pas.', 'erreur');

  // Le consentement est verifie ici aussi, et pas seulement par le
  // serveur : laisser avancer pour refuser trois ecrans plus loin, une
  // fois le formulaire rempli, serait la pire facon de le demander.
  if (!document.getElementById('cons-conditions')?.checked
      || !document.getElementById('cons-donnees')?.checked) {
    return toast('Acceptez les conditions et le traitement de vos données '
                 + 'pour continuer.', 'erreur');
  }

  etat.etapeOnboarding = 1;
  majEtapeOnboarding();
  afficherVue('vue-onboarding');
  remplirSelectPays();
  remplirListesParcours();
}
async function naviguerEtape(delta) {
  // Validation des champs OBLIGATOIRES avant d'avancer
  if (delta > 0 && !validerEtapeOnboarding(etat.etapeOnboarding)) return;

  const nouv = etat.etapeOnboarding + delta;
  if (nouv < 1) return;
  if (nouv > 4) {
    const ok = await finaliserInscription();
    if (!ok) return;   // on reste sur l'étape pour corriger
    // « confirmation » : l'écran de saisie du code est déjà affiché,
    // il ne faut pas passer par-dessus.
    if (ok === 'confirmation') return;
    afficherVue('vue-app'); initApp(); return;
  }
  etat.etapeOnboarding = nouv;
  majEtapeOnboarding();
}

/* Informations saisies a l'etape 1, lues par identifiant.

   Les selecteurs de position (« le premier select de l'etape ») se
   trompaient de champ des qu'on en ajoutait un, sans rien signaler. */
function infosEtape1() {
  const val = id => (document.getElementById(id)?.value || '').trim();
  return {
    pays: val('select-pays'),
    niveau_etudes: val('ob-niveau'),
    domaine: val('ob-domaine'),
    etablissement: val('ob-etablissement'),
    bio: val('ob-bio'),
  };
}

/* Vérifie que les informations obligatoires d'une étape sont remplies. */
function validerEtapeOnboarding(etape) {
  if (etape === 1) {
    const d = infosEtape1();
    if (!d.pays) { toast('Le pays est obligatoire.', 'erreur'); return false; }
    if (!d.niveau_etudes) { toast('Indiquez votre diplôme le plus élevé.', 'erreur'); return false; }
    if (!d.domaine) { toast('Indiquez votre domaine ou votre métier.', 'erreur'); return false; }
  }
  if (etape === 2) {
    const n = document.querySelectorAll('#etape-2 .chip-select.actif').length;
    if (n < 2) { toast('Choisissez au moins 2 secteurs d\'intérêt.', 'erreur'); return false; }
  }
  return true;
}

/* Crée le compte, puis conduit à la confirmation ou à l'application.

   Le parcours dépend d'un réglage du serveur. Quand la confirmation est
   obligatoire, l'inscription n'ouvre pas de session : demander le
   profil dans la foulée recevait un refus, et l'interface renvoyait au
   formulaire en annonçant un échec, alors que le compte était créé et
   le code parti. C'est ce qui empêchait de trouver où saisir le code.

   Les informations recueillies pendant l'accueil guidé sont donc mises
   de côté et envoyées après l'ouverture de session, quel que soit le
   moment où elle survient. */
let _profilEnAttente = null;

async function finaliserInscription() {
  const prenom = (document.getElementById('prenom-ins')?.value || '').trim();
  const nom = (document.getElementById('nom-ins')?.value || '').trim();
  const email = (document.getElementById('email-ins')?.value || '').trim().toLowerCase();
  const mdp = document.getElementById('mdp-ins')?.value || '';

  const secteursChoisis = [...document.querySelectorAll('#etape-2 .chip-select.actif')]
    .map(c => c.textContent.trim().replace(/\s*×$/, '').replace(/^\+\s*Autre$/, '')).filter(Boolean);
  const d = infosEtape1();
  const telephone = (document.getElementById('tel-ins')?.value || '').trim();

  try {
    const photoOnboarding = etat.utilisateur && etat.utilisateur.photo;
    const creation = await API.post('/auth/inscription', {
      prenom, nom, email, mot_de_passe: mdp,
      role: etat.roleChoisi || 'etudiant',
      consentement: {
        conditions: !!document.getElementById('cons-conditions')?.checked,
        donnees: !!document.getElementById('cons-donnees')?.checked,
        notifications: !!document.getElementById('cons-notifs')?.checked,
      },
    });

    // Mis de côté, envoyé dès qu'une session existe. Le pays et les
    // secteurs étaient auparavant recueillis puis perdus.
    _profilEnAttente = {
      bio: d.bio,
      ...(telephone ? { telephone } : {}),
      niveau_etudes: d.niveau_etudes,
      domaine: d.domaine,
      etablissement: d.etablissement,
      _pays: d.pays,
      _secteurs: secteursChoisis,
      _photo: photoOnboarding,
    };

    // Confirmation obligatoire : aucune session n'a été ouverte. On
    // conduit directement à la saisie du code, sans toucher au profil.
    if (creation && creation.verification_requise) {
      if (creation.email_envoye === false) {
        toast("Compte créé, mais le code n'a pas pu être envoyé. "
              + 'Prévenez un administrateur.', 'erreur');
      }
      ouvrirEtapeConfirmation(email);
      return 'confirmation';
    }

    // Mode souple : la session est déjà ouverte.
    MODE.utilisateur = await API.get('/profil/moi');
    await envoyerProfilEnAttente();
    appliquerUtilisateur(MODE.utilisateur);
    if (photoOnboarding) etat.utilisateur.photo = photoOnboarding;

    if (creation && creation.email_envoye === false) {
      toast("Compte créé. Le code de confirmation n'a pas pu partir : "
            + 'votre compte reste utilisable.', 'erreur');
      return true;
    }
    ouvrirEtapeConfirmation(email);
    return 'confirmation';
  } catch (err) {
    toast(err.message || 'Inscription impossible.', 'erreur');
    afficherVue('vue-inscription'); return false;
  }
}

/* Envoie au serveur ce que l'accueil guidé avait recueilli. Appelée dès
   qu'une session existe, c'est-à-dire après la saisie du code quand la
   confirmation est obligatoire. */
async function envoyerProfilEnAttente() {
  if (!_profilEnAttente) return;
  const p = _profilEnAttente;
  _profilEnAttente = null;
  try {
    const corps = { ...p };
    delete corps._pays; delete corps._secteurs; delete corps._photo;
    const id_pays = p._pays ? await _idPaysDepuisLibelle(p._pays) : null;
    const secteurs = await _idsSecteursDepuisLibelles(p._secteurs || []);
    if (id_pays) corps.id_pays = id_pays;
    if (secteurs.length) corps.secteurs = secteurs;
    if (Object.values(corps).some(Boolean)) {
      await API.put('/profil/moi', corps);
      MODE.utilisateur = await API.get('/profil/moi');
      appliquerUtilisateur(MODE.utilisateur);
    }
    if (p._photo) etat.utilisateur.photo = p._photo;
  } catch (_) {
    // Le profil se complète depuis les paramètres : mieux vaut laisser
    // entrer que bloquer sur une information secondaire.
  }
}

function majEtapeOnboarding() {
  const e = etat.etapeOnboarding;
  const labels = ['Informations de base', "Secteurs d'intérêt", 'Photo de profil', 'Découverte de la plateforme'];
  for (let i = 1; i <= 4; i++) {
    document.getElementById('ob-e'+i).classList.toggle('fait', i <= e);
    document.getElementById('etape-'+i).style.display = (i === e) ? 'block' : 'none';
  }
  document.getElementById('ob-num').textContent = e;
  document.getElementById('ob-label').textContent = labels[e-1];
  document.getElementById('ob-prec').disabled = (e === 1);
  document.getElementById('ob-suiv').textContent = (e === 4) ? "Accéder à la plateforme →" : 'Suivant →';
  // L'avatar de l'etape photo portait des initiales ecrites en dur,
  // celles d'une personne fictive. Il montre desormais celles que la
  // personne vient de saisir, tant qu'aucune photo n'est choisie.
  const avOb = document.getElementById('avatar-onboarding');
  if (avOb && !etat.utilisateur.photo) {
    const p = (document.getElementById('prenom-ins')?.value || '').trim();
    const n = (document.getElementById('nom-ins')?.value || '').trim();
    avOb.textContent = ((p[0] || '') + (n[0] || '')).toUpperCase();
  }
  // Brancher le bouton photo de l'étape 3
  const etape3 = document.getElementById('etape-3');
  if (etape3 && !etape3.dataset.cable) {
    etape3.dataset.cable = '1';
    const btn = etape3.querySelector('button');
    if (btn) {
      btn.onclick = () => declencherSelectionPhoto((dataUrl) => {
        etat.utilisateur.photo = dataUrl;
        const av = etape3.querySelector('.avatar');
        av.innerHTML = `<img src="${dataUrl}" class="photo-avatar" alt="">`;
        toast('Photo de profil ajoutée.');
      });
    }
  }
}
function toggleChip(elem) { elem.classList.toggle('actif'); }

/* Chip "Autre" : ouvre le champ d'ajout de secteurs personnalisés. */
function ouvrirAjoutSecteur() {
  const champ = document.getElementById('champ-autre-secteur');
  const input = document.getElementById('input-autre-secteur');
  if (!champ || !input) return;
  champ.style.display = '';
  setTimeout(() => input.focus(), 50);
}
/* Ajoute un secteur personnalisé (peut être appelé plusieurs fois). */
function ajouterSecteurPerso() {
  const input = document.getElementById('input-autre-secteur');
  const conteneur = document.querySelector('#etape-2 .chips-select');
  if (!input || !conteneur) return;
  const v = (input.value || '').trim();
  if (!v) { toast('Saisissez un secteur.', 'erreur'); return; }
  // Anti doublons
  const existe = [...conteneur.querySelectorAll('.chip-select')]
    .some(c => c.textContent.trim().replace(/\s*×$/, '').toLowerCase() === v.toLowerCase());
  if (existe) { toast('Ce secteur est déjà présent.', 'erreur'); input.value = ''; return; }
  const chip = document.createElement('div');
  chip.className = 'chip-select chip-perso actif';
  chip.dataset.perso = '1';
  chip.innerHTML = `<span onclick="toggleChip(this.parentElement)">${v}</span><button type="button" class="chip-sup" onclick="this.parentElement.remove()" aria-label="Supprimer">×</button>`;
  // Insérer avant le chip "+ Autre"
  const chipAutre = conteneur.querySelector('[data-autre="1"]');
  conteneur.insertBefore(chip, chipAutre);
  input.value = '';
  input.focus();
}

/* Liste exhaustive des pays (FR) pour le sélecteur de l'onboarding. */
const LISTE_PAYS = [
  "Afghanistan","Afrique du Sud","Albanie","Algérie","Allemagne","Andorre","Angola","Antigua-et-Barbuda","Arabie saoudite","Argentine","Arménie","Australie","Autriche","Azerbaïdjan",
  "Bahamas","Bahreïn","Bangladesh","Barbade","Belgique","Belize","Bénin","Bhoutan","Biélorussie","Birmanie (Myanmar)","Bolivie","Bosnie-Herzégovine","Botswana","Brésil","Brunei","Bulgarie","Burkina Faso","Burundi",
  "Cambodge","Cameroun","Canada","Cap-Vert","Chili","Chine","Chypre","Colombie","Comores","Corée du Nord","Corée du Sud","Costa Rica","Côte d'Ivoire","Croatie","Cuba",
  "Danemark","Djibouti","Dominique",
  "Égypte","Émirats arabes unis","Équateur","Érythrée","Espagne","Estonie","Eswatini","États-Unis","Éthiopie",
  "Fidji","Finlande","France",
  "Gabon","Gambie","Géorgie","Ghana","Grèce","Grenade","Guatemala","Guinée","Guinée équatoriale","Guinée-Bissau","Guyana",
  "Haïti","Honduras","Hongrie",
  "Îles Marshall","Îles Salomon","Inde","Indonésie","Irak","Iran","Irlande","Islande","Israël","Italie",
  "Jamaïque","Japon","Jordanie",
  "Kazakhstan","Kenya","Kirghizistan","Kiribati","Koweït",
  "Laos","Lesotho","Lettonie","Liban","Libéria","Libye","Liechtenstein","Lituanie","Luxembourg",
  "Macédoine du Nord","Madagascar","Malaisie","Malawi","Maldives","Mali","Malte","Maroc","Maurice","Mauritanie","Mexique","Micronésie","Moldavie","Monaco","Mongolie","Monténégro","Mozambique",
  "Namibie","Nauru","Népal","Nicaragua","Niger","Nigéria","Norvège","Nouvelle-Zélande",
  "Oman","Ouganda","Ouzbékistan",
  "Pakistan","Palaos","Palestine","Panama","Papouasie-Nouvelle-Guinée","Paraguay","Pays-Bas","Pérou","Philippines","Pologne","Portugal",
  "Qatar",
  "République centrafricaine","République démocratique du Congo","République dominicaine","République du Congo","République tchèque","Roumanie","Royaume-Uni","Russie","Rwanda",
  "Saint-Christophe-et-Niévès","Saint-Marin","Saint-Vincent-et-les-Grenadines","Sainte-Lucie","Salvador","Samoa","Sao Tomé-et-Principe","Sénégal","Serbie","Seychelles","Sierra Leone","Singapour","Slovaquie","Slovénie","Somalie","Soudan","Soudan du Sud","Sri Lanka","Suède","Suisse","Suriname","Syrie",
  "Tadjikistan","Tanzanie","Tchad","Thaïlande","Timor oriental","Togo","Tonga","Trinité-et-Tobago","Tunisie","Turkménistan","Turquie","Tuvalu",
  "Ukraine","Uruguay",
  "Vanuatu","Vatican","Venezuela","Viêt Nam",
  "Yémen",
  "Zambie","Zimbabwe"
];
function remplirSelectPays() {
  const sel = document.getElementById('select-pays');
  if (!sel || sel.dataset.remp === '1') return;
  sel.dataset.remp = '1';
  sel.innerHTML = '<option value="">Sélectionnez votre pays</option>' +
    LISTE_PAYS.map(p => `<option value="${p}">${p}</option>`).join('');
}

/* Remplit les listes du parcours avec les valeurs du serveur.

   Elles viennent du serveur et ne sont pas ecrites dans la page : la
   liste proposee et la liste acceptee a l'enregistrement ne peuvent
   alors pas diverger, ce qui donnerait un choix refuse apres coup. */
async function remplirListesParcours() {
  if (!etat.referentielsProfil) {
    try {
      etat.referentielsProfil = await API.get('/profil/referentiels-profil');
    } catch (_) { return; }
  }
  const r = etat.referentielsProfil || {};
  const options = (valeurs, choisi) =>
    '<option value="">Choisissez…</option>' + (valeurs || []).map(v =>
      `<option value="${echapper(v)}"${v === choisi ? ' selected' : ''}>${echapper(v)}</option>`
    ).join('');

  const niveau = document.getElementById('ob-niveau');
  if (niveau) niveau.innerHTML = options(r.niveaux_etudes, niveau.value);
  const domaine = document.getElementById('ob-domaine');
  if (domaine) domaine.innerHTML = options(r.domaines, domaine.value);

  // Suggestions, pas contrainte : le champ reste libre pour qui apprend
  // son metier dans un atelier qu'aucune liste ne contiendra.
  const liste = document.getElementById('liste-etablissements');
  if (liste) {
    liste.innerHTML = (r.etablissements || [])
      .map(e => `<option value="${echapper(e)}"></option>`).join('');
  }
}
async function seDeconnecter() {
  document.getElementById('menuProfil').classList.remove('ouvert');
  // On déconnecte l'interface même si l'appel réseau échoue
  try { await API.post('/auth/deconnexion', {}); } catch (_) {}
  SESSION.utilisateur = null;
  toast('Vous avez été déconnecté(e).');
  afficherVue('vue-accueil');
}

/* ============================================================
   PHOTO DE PROFIL (utilitaire)
   ============================================================ */
function declencherSelectionPhoto(callback) {
  const inp = document.createElement('input');
  inp.type = 'file';
  inp.accept = 'image/*';
  inp.onchange = () => {
    const f = inp.files && inp.files[0];
    if (!f) return;
    if (f.size > 3 * 1024 * 1024) return toast('Image trop volumineuse (max 3 Mo).', 'erreur');
    const r = new FileReader();
    r.onload = () => callback(r.result);
    r.readAsDataURL(f);
  };
  inp.click();
}
function televerserPhotoCompte() {
  declencherSelectionPhoto((dataUrl) => {
    etat.utilisateur.photo = dataUrl;
    toast('Photo mise à jour.');
    const panParam = document.querySelector('#menu-param button.actif');
    if (panParam) changerPanParam(panParam, 'compte');
    const navAv = document.getElementById('avatar-nav');
    const filAv = document.getElementById('avatar-fil');
    if (navAv) navAv.innerHTML = `<img src="${dataUrl}" class="photo-avatar" alt="">`;
    if (filAv) filAv.innerHTML = `<img src="${dataUrl}" class="photo-avatar" alt="">`;
    rendreSidebarProfil();
    // Mettre à jour la page profil (cercle au-dessus du nom) si on y est
    if (etat.sectionActive === 'profil') { profilCible = null; rendreProfil(); }
  });
}

/* Icône "pouce" type Facebook (utilisée pour le bouton Utile / Favoris).
   Affichage en contour par défaut, remplie quand `actif` est vrai. */
function iconePouce(actif = false) {
  const d = "M2 10h3.6c.22 0 .4.18.4.4V21.6c0 .22-.18.4-.4.4H2c-.55 0-1-.45-1-1v-10c0-.55.45-1 1-1zm6 0h1.05L13.2 3.6c.42-.7 1.34-.95 2.05-.55.55.31.83.94.7 1.56L14.9 9h5.6c1.1 0 2 .9 2 2v1.18c0 .26-.05.52-.15.76l-3 7.06c-.32.74-1.05 1.22-1.85 1.22H8c-.55 0-1-.45-1-1V11c0-.55.45-1 1-1z";
  if (actif) {
    return `<svg class="icone-pouce" viewBox="0 0 24 24" aria-hidden="true"><path d="${d}" fill="currentColor"/></svg>`;
  }
  return `<svg class="icone-pouce" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="${d}"/></svg>`;
}

/* ============================================================
   INITIALISATION
   ============================================================ */
async function initApp() {
  // En mode API : recharge l'utilisateur courant
  if (MODE.api) {
    try { MODE.utilisateur = await API.get('/profil/moi'); appliquerUtilisateur(MODE.utilisateur); }
    catch (_) { /* on garde l'état local */ }
  }

  document.getElementById('avatar-nav').innerHTML = etat.utilisateur.photo
    ? `<img src="${etat.utilisateur.photo}" class="photo-avatar" alt="">` : etat.utilisateur.initiales;
  document.getElementById('avatar-fil').innerHTML = document.getElementById('avatar-nav').innerHTML;
  document.getElementById('lien-admin').style.display = etat.utilisateur.estAdmin ? 'flex' : 'none';
  document.getElementById('lien-mentor').style.display = (etat.utilisateur.role === 'mentor') ? 'flex' : 'none';
  rendreSidebarProfil();
  rendreFil();              // affichage immédiat (démo ou cache)
  rendreColonneDroite();
  rendreNotifications();
  majNavActif();

  // Recharge asynchrone depuis l'API si dispo
  if (MODE.api) {
    chargerFilDepuisApi();
    chargerMentorsDepuisApi();
    chargerNotificationsDepuisApi();
  }
}

/* ============================================================
   SIDEBAR PROFIL (col gauche)
   ============================================================ */
function rendreSidebarProfil() {
  const u = etat.utilisateur;
  document.getElementById('sidebar-profil').innerHTML = `
    ${avatarHTML(u.initiales, 'l', u.photo)}
    <div class="nom">${echapper(u.prenom + ' ' + u.nom)}</div>
    <span class="badge-role">${u.role === 'mentor' ? ic('trophee','ic ic-s') + ' Mentor' : ic('diplome','ic ic-s') + ' Étudiant'}</span>
    <div class="meta">${ic('position','ic ic-s')} ${echapper(u.pays)}</div>
    <button class="btn btn-secondaire btn-petit btn-bloc" onclick="naviguerApp('profil')">Voir mon profil</button>
    <div class="profil-stats">
      <div><strong>${u.questionsPosees}</strong><span>Questions posées</span></div>
      <div><strong>${u.mentorsSuivis}</strong><span>Référents suivis</span></div>
    </div>`;
  document.getElementById('mes-secteurs').innerHTML =
    u.secteurs.map((s, i) => `<span class="tag ${['','tag-ambre','tag-vert','tag-violet'][i%4]}">${echapper(s)}</span>`).join('');
  document.getElementById('mentors-suivis').innerHTML =
    mentors.slice(0, 4).map(m => `
      <div class="suivi-item" onclick="ouvrirProfilMentor(${m.id})">
        ${avatarHTML(m.initiales, 's')}
        <div class="info"><strong>${echapper(m.prenom + ' ' + m.nom)}</strong><span>${echapper(m.secteur)}</span></div>
      </div>`).join('');
}

/* ============================================================
   FIL D'ACTUALITÉ
   ============================================================ */
function changerTri(elem, tri) {
  document.querySelectorAll('.onglet').forEach(o => o.classList.remove('actif'));
  elem.classList.add('actif');
  etat.tri = tri;
  rendreFil();
}

/* Recharge la variable `questions` depuis le backend et re-rend le fil.
   Si le backend est inaccessible, conserve les données de démo. */
async function chargerFilDepuisApi() {
  if (!MODE.api) return;
  try {
    const params = new URLSearchParams();
    if (etat.tri) params.set('tri', etat.tri);
    const liste = await API.get('/questions?' + params.toString());
    // Adapter la forme API au format attendu par carteQuestionHTML
    const adaptees = liste.map(q => ({
      id: q.id_question,
      titre: q.titre,
      corps: q.corps,
      secteur: q.secteur || 'Autre',
      auteur: `${q.prenom || ''} ${q.nom || ''}`.trim() || 'Anonyme',
      initiales: ((q.prenom || '?')[0] + (q.nom || '?')[0]).toUpperCase(),
      idAuteur: q.id_utilisateur || q.id_auteur || null,
      photoAuteur: q.photo_url || null,
      pays: q.pays || '',
      temps: _tempsRelatif(q.publiee_le),
      utile: q.nb_utiles || 0,
      repCount: q.nb_reponses || 0,
      reponses: [],
    }));
    // Remplace le contenu de l'array (les références sont conservées)
    questions.length = 0;
    questions.push(...adaptees);
    rendreFil(); rendreColonneDroite();
  } catch (err) {
    console.warn('Fil indisponible :', err.message);
  }
}

/* Charge l'annuaire des mentors depuis le serveur. */
async function chargerMentorsDepuisApi() {
  if (!MODE.api) return;
  try {
    const liste = await API.get('/mentors?limite=40');
    const adaptes = (liste || []).map(m => ({
      id: m.id_utilisateur,
      prenom: m.prenom || '',
      nom: m.nom || '',
      initiales: ((m.prenom || '?')[0] + (m.nom || '?')[0]).toUpperCase(),
      secteur: (m.secteurs && m.secteurs[0] && m.secteurs[0].libelle) || 'Autre',
      secteurs: (m.secteurs || []).map(s => s.libelle),
      pays: m.pays || '',
      ville: m.ville || '',
      bio: m.bio || '',
      note: Number(m.note_moyenne || 0),
      reponses: m.nb_reponses || 0,
      anciennete: m.anciennete || '',
      dispo: m.dispo || 'disponible',
      verifie: !!m.est_verifie,
      photo: m.photo_url || null,
      experiences: [],
    }));
    mentors.length = 0;
    mentors.push(...adaptes);
    rendreColonneDroite();
    if (typeof rendreSidebarProfil === 'function') rendreSidebarProfil();
  } catch (err) {
    console.warn('Annuaire des référents indisponible :', err.message);
  }
}

/* Convertit un horodatage du serveur en objet Date.

   La base stocke des instants UTC sous la forme « 2026-09-09 10:46:35 »,
   sans fuseau ni « T ». Passée telle quelle à Date(), cette chaîne est
   lue comme une heure locale par certains navigateurs et refusée par
   d'autres, qui affichent alors « Invalid Date ». Deux défauts pour le
   prix d'un : une heure fausse là où elle s'affiche, et rien du tout
   ailleurs. Le « T » et le « Z » lèvent les deux. */
function _dateServeur(valeur) {
  if (!valeur) return null;
  if (valeur instanceof Date) return valeur;
  let t = String(valeur).trim().replace(' ', 'T');
  if (!/[Zz]|[+-]\d{2}:?\d{2}$/.test(t)) t += 'Z';
  const d = new Date(t);
  return isNaN(d.getTime()) ? null : d;
}

/* Date et heure, dans le fuseau de la personne qui regarde. Une action
   d'administration sans heure ne se recoupe avec rien. */
function formatHorodatage(valeur, avecSecondes = false) {
  const d = _dateServeur(valeur);
  if (!d) return '';
  return d.toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
    ...(avecSecondes ? { second: '2-digit' } : {}),
  });
}

function formatDate(valeur) {
  const d = _dateServeur(valeur);
  return d ? d.toLocaleDateString('fr-FR') : '';
}

function _tempsRelatif(dateIso) {
  const d = _dateServeur(dateIso);
  if (!d) return '';
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return "à l'instant";
  if (sec < 3600) return `il y a ${Math.floor(sec/60)} min`;
  if (sec < 86400) return `il y a ${Math.floor(sec/3600)} h`;
  if (sec < 86400 * 7) return `il y a ${Math.floor(sec/86400)} j`;
  return formatDate(d);
}

function rendreFil() {
  const pays = document.getElementById('filtre-pays')?.value || '';
  const sect = document.getElementById('filtre-secteur')?.value || '';
  let liste = questions.filter(q => (!pays || q.pays === pays) && (!sect || q.secteur === sect));
  if (etat.rechercheTerme) {
    const t = etat.rechercheTerme.toLowerCase();
    liste = liste.filter(q => q.titre.toLowerCase().includes(t) || q.corps.toLowerCase().includes(t) || q.secteur.toLowerCase().includes(t));
  }
  if (etat.tri === 'populaire') liste.sort((a, b) => b.utile - a.utile);
  if (etat.tri === 'sansrep') liste = liste.filter(q => q.reponses.length === 0);

  const conteneur = document.getElementById('fil-questions');
  const banniere = etat.rechercheTerme
    ? `<div class="carte" style="margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
         <span>Résultats pour <strong>« ${echapper(etat.rechercheTerme)} »</strong> : ${liste.length} question(s)</span>
         <button class="btn btn-fantome btn-petit" onclick="effacerRecherche()">${ic('croix','ic ic-s')} Effacer</button>
       </div>` : '';
  if (!liste.length) {
    conteneur.innerHTML = banniere + `<div class="etat-vide carte"><div class="illu">${ic('loupe','ic ic-l')}</div><h3>Aucune question pour ces critères</h3><p>Essayez d'élargir vos filtres ou soyez le premier à poser une question !</p></div>`;
    return;
  }
  conteneur.innerHTML = banniere + liste.map(q => carteQuestionHTML(q)).join('');
}

function carteQuestionHTML(q) {
  const utileActif = etat.utilesQ.has(q.id) ? ' actif' : '';
  const saveActif = etat.sauvegardees.has(q.id) ? ' actif' : '';
  return `
    <article class="carte-question" data-id="${q.id}">
      <div class="q-entete">
        ${avatarLien(q.idAuteur, q.initiales, 's', q.photoAuteur, false, q.auteur)}
        <div class="info"><strong class="nom-cliquable" ${q.idAuteur
          ? `onclick="ouvrirProfilUtilisateur(${q.idAuteur})"` : ''
          }>${echapper(q.auteur)}</strong> · <span>${echapper(q.pays)}</span><time>${echapper(q.temps)}</time></div>
        <button class="btn-fantome btn-petit" title="Signaler" aria-label="Signaler" onclick="signaler(${q.id})">${ic('drapeau','ic ic-s')}</button>
      </div>
      <h3 class="q-titre" style="cursor:pointer;" onclick="ouvrirQuestion(${q.id})">${echapper(q.titre)}</h3>
      <p class="q-corps">${echapper(q.corps)}</p>
      <div class="q-tags"><span class="tag">${echapper(q.secteur)}</span></div>
      <div class="q-pied">
        <button class="btn-utile${utileActif}" onclick="basculerUtileQ(${q.id})" aria-label="En favoris" title="En favoris">${iconePouce(etat.utilesQ.has(q.id))}<span class="cnt">${q.utile}</span><span class="lbl">En favoris</span></button>
        <button onclick="ouvrirQuestion(${q.id})">${ic('bulle','ic ic-s')} ${q.repCount} réponses</button>
        <button class="bouton-sauver${saveActif}" onclick="basculerSauver(${q.id})" title="Sauvegarder">${ic('marque','ic ic-s')} ${etat.sauvegardees.has(q.id) ? 'Sauvegardée' : 'Sauvegarder'}</button>
        <button class="repondre btn btn-secondaire btn-petit" onclick="ouvrirQuestion(${q.id})">Voir / Répondre</button>
      </div>
    </article>`;
}

/* ----- Bouton "utile" : 1 clic = j'aime, 2e clic = annulé ----- */
async function basculerUtileQ(id) {
  const q = questions.find(x => x.id === id); if (!q) return;
  // Optimistic UI : on bascule immédiatement, puis on confirme côté serveur
  const etaitMarque = etat.utilesQ.has(id);
  if (etaitMarque) { etat.utilesQ.delete(id); q.utile = Math.max(0, q.utile - 1); }
  else             { etat.utilesQ.add(id);    q.utile++; }
  rendreCourant();

  if (MODE.api) {
    try {
      const r = await API.post(`/questions/${id}/utile`, {});
      // Synchronise le compteur avec la valeur officielle du serveur
      if (typeof r?.nb_utiles === 'number') {
        q.utile = r.nb_utiles;
        if (r.marque) etat.utilesQ.add(id); else etat.utilesQ.delete(id);
        rendreCourant();
      }
      toast(r?.marque ? 'En favoris.' : 'Retiré des favoris.');
    } catch (err) {
      // Rollback en cas d'échec serveur
      if (etaitMarque) { etat.utilesQ.add(id); q.utile++; }
      else             { etat.utilesQ.delete(id); q.utile = Math.max(0, q.utile - 1); }
      rendreCourant();
      toast(err.message || 'Action impossible.', 'erreur');
    }
  } else {
    toast(etat.utilesQ.has(id) ? 'En favoris.' : 'Retiré des favoris.');
  }
}

async function basculerSauver(id) {
  const etait = etat.sauvegardees.has(id);
  if (etait) etat.sauvegardees.delete(id); else etat.sauvegardees.add(id);
  rendreCourant();

  if (MODE.api) {
    try {
      const r = await API.post(`/questions/${id}/sauvegarder`, {});
      if (typeof r?.sauvegardee === 'boolean') {
        if (r.sauvegardee) etat.sauvegardees.add(id); else etat.sauvegardees.delete(id);
        rendreCourant();
      }
      toast(r?.sauvegardee ? 'Question sauvegardée.' : 'Retirée de vos sauvegardes.');
    } catch (err) {
      if (etait) etat.sauvegardees.add(id); else etat.sauvegardees.delete(id);
      rendreCourant();
      toast(err.message || 'Action impossible.', 'erreur');
    }
  } else {
    toast(etat.sauvegardees.has(id) ? 'Question sauvegardée.' : 'Retirée de vos sauvegardes.');
  }
}

function rendreCourant() {
  if (etat.sectionActive === 'fil') rendreFil();
  else if (etat.sectionActive === 'profil') rendreProfil();
  else if (etat.sectionActive === 'question') { const id = parseInt(document.getElementById('sv-question').dataset.qid); if (id) ouvrirQuestion(id); }
  rendreColonneDroite();
}

/* ----- Ouvrir une question en pleine vue ----- */
function ouvrirQuestion(id) {
  const q = questions.find(x => x.id === id); if (!q) return;
  document.querySelectorAll('.sous-vue').forEach(sv => sv.style.display = 'none');
  const sv = document.getElementById('sv-question');
  sv.style.display = 'block';
  sv.dataset.qid = id;
  etat.sectionActive = 'question';
  majNavActif();
  const utileActif = etat.utilesQ.has(q.id) ? ' actif' : '';
  const saveActif = etat.sauvegardees.has(q.id) ? ' actif' : '';
  const peutRepondre = estMentor();
  const zoneRep = peutRepondre
    ? `<div style="display:flex; gap:8px; margin-top:12px;">
         <input type="text" placeholder="Écrire une réponse…" id="rep-input-${q.id}" />
         <button class="btn btn-primaire btn-petit" onclick="ajouterReponse(${q.id})">Envoyer</button>
       </div>`
    : `<div class="carte" style="margin-top:12px; background:var(--fond); font-size:13px; color:var(--texte-doux); display:flex; gap:8px; align-items:center;">
         ${ic('marque','ic ic-s')} Seuls les référents peuvent répondre aux questions. Devenez référent pour partager votre expertise.
       </div>`;
  document.getElementById('contenu-question').innerHTML = `
    <article class="carte-question">
      <div class="q-entete">
        ${avatarLien(q.idAuteur, q.initiales, 's', q.photoAuteur, false, q.auteur)}
        <div class="info"><strong class="nom-cliquable" ${q.idAuteur
          ? `onclick="ouvrirProfilUtilisateur(${q.idAuteur})"` : ''
          }>${echapper(q.auteur)}</strong> · <span>${echapper(q.pays)}</span><time>${echapper(q.temps)}</time></div>
      </div>
      <h2 class="q-titre">${echapper(q.titre)}</h2>
      <p class="q-corps">${echapper(q.corps)}</p>
      <div class="q-tags"><span class="tag">${echapper(q.secteur)}</span></div>
      <div class="q-pied">
        <button class="btn-utile${utileActif}" onclick="basculerUtileQ(${q.id})" aria-label="En favoris" title="En favoris">${iconePouce(etat.utilesQ.has(q.id))}<span class="cnt">${q.utile}</span><span class="lbl">En favoris</span></button>
        <button class="bouton-sauver${saveActif}" onclick="basculerSauver(${q.id})">${ic('marque','ic ic-s')} ${etat.sauvegardees.has(q.id) ? 'Sauvegardée' : 'Sauvegarder'}</button>
      </div>
      <div class="reponses" style="display:flex; flex-direction:column;">
        <h4 style="margin:14px 0 8px;">${q.reponses.length} réponse(s)</h4>
        ${q.reponses.map(r => reponseHTML(r)).join('') || '<p style="color:var(--texte-doux); font-size:14px;">Aucune réponse pour le moment.</p>'}
        ${zoneRep}
      </div>
    </article>`;
  window.scrollTo(0, 0);
}

function reponseHTML(r) {
  const cls = r.mentor ? 'reponse mentor' : 'reponse';
  const badge = r.verifie
    ? `<span class="badge-verifie">${ic('check','ic ic-s')} Référent vérifié</span>`
    : (r.mentor ? `<span class="badge-mentor badge-role">${ic('trophee','ic ic-s')} Référent</span>` : '');
  const etoiles = r.mentor ? `<span class="etoiles" title="Notez cette réponse">
    ${[1,2,3,4,5].map(i => `<span class="${i <= (r.etoiles||0) ? '' : 'vide'}" onclick="noter(this, ${i})">★</span>`).join('')}
  </span>` : '';
  const sous = (r.sousReponses||[]).map(sr => `
    <div class="reponse-imbriquee">
      <div class="r-entete">${avatarHTML(sr.init, 's')}<div class="info"><strong>${echapper(sr.auteur)}</strong></div></div>
      <p>${echapper(sr.contenu)}</p>
    </div>`).join('');
  return `
    <div class="${cls}">
      <div class="r-entete">${avatarHTML(r.init, 's')}<div class="info"><strong>${echapper(r.auteur)}</strong> ${badge}</div></div>
      <p>${echapper(r.contenu)}</p>
      <div class="actions">
        <button class="btn-utile" onclick="utileR(this)" aria-label="En favoris" title="En favoris">${iconePouce(false)}<span class="cnt">${r.utile}</span><span class="lbl">En favoris</span></button>
        ${etoiles}
      </div>
      ${sous}
    </div>`;
}

async function utileR(btn, idReponse) {
  const actif = btn.classList.toggle('actif');
  // Bascule le rendu de l'icône (contour ↔ rempli) selon l'état
  const ic = btn.querySelector('.icone-pouce');
  if (ic) {
    const nouv = document.createElement('span');
    nouv.innerHTML = iconePouce(actif);
    btn.replaceChild(nouv.firstChild, ic);
  }
  const cnt = btn.querySelector('.cnt');
  const n = parseInt(cnt.textContent, 10) || 0;
  cnt.textContent = actif ? n + 1 : Math.max(0, n - 1);

  if (MODE.api && idReponse) {
    try {
      await API.post(`/reponses/${idReponse}/utile`, {});
      toast(actif ? 'En favoris.' : 'Retiré des favoris.');
    } catch (err) {
      btn.classList.toggle('actif');
      cnt.textContent = n;
      toast(err.message || 'Action impossible.', 'erreur');
    }
  } else {
    toast(actif ? 'En favoris.' : 'Retiré des favoris.');
  }
}
function noter(elem, n) {
  const conteneur = elem.parentElement;
  [...conteneur.children].forEach((c, i) => c.classList.toggle('vide', i >= n));
  toast(`Note attribuée : ${n}/5.`);
}
async function signaler(id) {
  const motif = window.prompt('Motif du signalement (optionnel) :', '') || '';
  if (motif === null) return;  // annulé
  if (MODE.api) {
    try {
      await API.post(`/questions/${id}/signaler`, { motif });
      toast('Question signalée à la modération.');
    } catch (err) {
      toast(err.message || 'Signalement impossible.', 'erreur');
    }
  } else {
    toast('Serveur indisponible.');
  }
}

async function ajouterReponse(id) {
  if (!estMentor()) return toast('Seuls les référents peuvent répondre.', 'erreur');
  const inp = document.getElementById('rep-input-'+id);
  const contenu = (inp?.value || '').trim();
  if (!contenu) return toast('Écrivez votre réponse.', 'erreur');

  if (MODE.api) {
    try {
      await API.post('/reponses', { id_question: id, contenu });
      toast('Réponse publiée.');
      inp.value = '';
      await chargerFilDepuisApi();
      ouvrirQuestion(id);
      return;
    } catch (err) {
      return toast(err.message || 'Publication impossible.', 'erreur');
    }
  }

  // Serveur injoignable : aucune simulation, la réponse n'est pas perdue
  // dans le champ de saisie pour que l'utilisateur puisse réessayer.
  toast("Serveur indisponible : votre réponse n'a pas pu être publiée. "
        + "Réessayez dans quelques instants.", 'erreur');
}

/* ============================================================
   COLONNE DROITE — TENDANCES & SUGGESTIONS
   ============================================================ */
function rendreColonneDroite() {
  document.getElementById('questions-tendance').innerHTML =
    [...questions].sort((a,b) => b.utile - a.utile).slice(0, 5).map(q => `
      <li><a href="#" onclick="event.preventDefault(); ouvrirQuestion(${q.id})">${echapper(q.titre)}</a>
      <span>${q.utile} en favoris · ${q.repCount} réponses</span></li>`).join('');
  document.getElementById('mentors-suggeres').innerHTML =
    mentors.slice(0, 4).map(m => {
      const suivi = etat.suivis.has(m.id);
      return `<li><div class="mentor-sugg">
        ${avatarHTML(m.initiales)}
        <div class="info"><strong>${echapper(m.prenom + ' ' + m.nom)}</strong><span>${echapper(m.secteur)}</span></div>
        <button class="btn btn-fantome btn-petit" onclick="basculerSuivre(${m.id})">${suivi ? ic('check','ic ic-s') + ' Suivi' : '+ Suivre'}</button>
      </div></li>`;
    }).join('');
}

async function basculerSuivre(mentorId) {
  const m = mentors.find(x => x.id === mentorId); if (!m) return;
  const etait = etat.suivis.has(mentorId);
  if (etait) etat.suivis.delete(mentorId); else etat.suivis.add(mentorId);
  rendreColonneDroite();

  if (MODE.api) {
    try {
      const r = await API.post(`/mentors/${mentorId}/suivre`, {});
      if (typeof r?.suivi === 'boolean') {
        if (r.suivi) etat.suivis.add(mentorId); else etat.suivis.delete(mentorId);
        rendreColonneDroite();
      }
      toast(r?.suivi
        ? `Vous suivez désormais ${m.prenom}. Vous serez notifié(e) de ses réponses.`
        : `Vous ne suivez plus ${m.prenom}.`);
    } catch (err) {
      if (etait) etat.suivis.add(mentorId); else etat.suivis.delete(mentorId);
      rendreColonneDroite();
      toast(err.message || 'Action impossible.', 'erreur');
    }
  } else {
    toast(etat.suivis.has(mentorId)
      ? `Vous suivez désormais ${m.prenom}. Vous serez notifié(e) de ses réponses.`
      : `Vous ne suivez plus ${m.prenom}.`);
  }
}

/* Quand un mentor répond, notifier tous ses abonnés */
function notifierAbonnesMentor(nomMentor, questionId, titreQ) {
  // Si l'utilisateur courant suit un mentor portant ce nom, il reçoit une notif
  mentors.forEach(m => {
    if (`${m.prenom} ${m.nom}` === nomMentor && etat.suivis.has(m.id)) {
      notifications.unshift({
        texte: `${nomMentor} (que vous suivez) a répondu à « ${titreQ} »`,
        temps: "à l'instant", nonLu: true, questionId
      });
    }
  });
  rendreNotifications();
}

/* Hook : quand un mentor de la démo "ajoute" une réponse via l'admin/etc. — exposé pour usage futur */
function mentorRepondAQuestion(mentorId, questionId, contenu) {
  const m = mentors.find(x => x.id === mentorId); const q = questions.find(x => x.id === questionId);
  if (!m || !q) return;
  q.reponses.push({ auteur:`${m.prenom} ${m.nom}`, init:m.initiales, mentorId:m.id, mentor:true, verifie:m.verifie, contenu, utile:0 });
  q.repCount++;
  notifierAbonnesMentor(`${m.prenom} ${m.nom}`, q.id, q.titre);
}

/* ============================================================
   MODAL PUBLIER + SIMILAIRES
   ============================================================ */
function ouvrirModal(id) { document.getElementById(id).classList.add('ouvert'); }
function fermerModal(id) { document.getElementById(id).classList.remove('ouvert'); }
function majCompteur() {
  const v = document.getElementById('q-titre').value;
  document.getElementById('compteur').textContent = v.length;
}
function choisirCat(elem) {
  document.querySelectorAll('#chips-cat .chip-select').forEach(c => c.classList.remove('actif'));
  elem.classList.add('actif');
  etat.categorieChoisie = elem.textContent;
}

/* Évalue le titre saisi et propose des questions similaires existantes */
function majSimilaires() {
  const t = (document.getElementById('q-titre').value || '').trim().toLowerCase();
  const bloc = document.getElementById('bloc-similaires');
  const liste = document.getElementById('liste-similaires');
  if (t.length < 4) { bloc.style.display = 'none'; return; }
  const motsT = new Set(t.split(/\W+/).filter(m => m.length > 3));
  const scored = questions.map(q => {
    const motsQ = new Set(q.titre.toLowerCase().split(/\W+/).filter(m => m.length > 3));
    let inter = 0; motsT.forEach(m => { if (motsQ.has(m)) inter++; });
    const inclus = q.titre.toLowerCase().includes(t) ? 2 : 0;
    return { q, score: inter + inclus };
  }).filter(x => x.score > 0).sort((a,b) => b.score - a.score).slice(0, 4);

  if (!scored.length) { bloc.style.display = 'none'; return; }
  liste.innerHTML = scored.map(({q}) =>
    `<li>• <a href="#" onclick="event.preventDefault(); fermerModal('modalPublier'); ouvrirQuestion(${q.id});">${echapper(q.titre)}</a>
       <span style="color:var(--texte-doux); font-size:12px;"> · ${q.repCount} réponse(s)</span></li>`
  ).join('');
  bloc.style.display = 'block';
}

async function publierQuestion() {
  const t = document.getElementById('q-titre').value.trim();
  const c = document.getElementById('q-corps').value.trim();
  if (!t || !c) return toast('Titre et description sont obligatoires.', 'erreur');
  if (!etat.categorieChoisie) return toast('Choisissez une catégorie.', 'erreur');

  // Si backend dispo : POST réel et rechargement du fil
  if (MODE.api) {
    try {
      // Récupère l'id du secteur correspondant au libellé choisi
      const ref = await API.get('/profil/referentiels').catch(() => null);
      const secteur = ref?.secteurs?.find(s => s.libelle === etat.categorieChoisie);
      if (!secteur) {
        return toast('Catégorie inconnue côté serveur.', 'erreur');
      }
      await API.post('/questions', { titre: t, corps: c, id_secteur: secteur.id_secteur });
      toast('Votre question a été publiée !');
      _resetFormulaireQuestion();
      fermerModal('modalPublier');
      await chargerFilDepuisApi();
      return;
    } catch (err) {
      return toast(err.message || 'Publication impossible.', 'erreur');
    }
  }

  // Serveur injoignable : on ne simule rien, on le dit franchement.
  toast("Serveur indisponible : votre question n'a pas pu être publiée. "
        + "Réessayez dans quelques instants.", 'erreur');
}

function _resetFormulaireQuestion() {
  document.getElementById('q-titre').value = '';
  document.getElementById('q-corps').value = '';
  document.querySelectorAll('#chips-cat .chip-select').forEach(c => c.classList.remove('actif'));
  document.getElementById('compteur').textContent = '0';
  const bs = document.getElementById('bloc-similaires');
  if (bs) bs.style.display = 'none';
  etat.categorieChoisie = null;
}

/* ============================================================
   PROFIL
   ============================================================ */
let profilCible = null;

function ouvrirProfilMentor(id) {
  profilCible = mentors.find(m => m.id === id);
  naviguerApp('profil');
}
function rendreProfil() {
  if (profilPublic) return rendreProfilAutre(profilPublic);
  if (profilCible) return rendreProfilMentor(profilCible);
  const u = etat.utilisateur;
  const estMentorVerifie = estMentor() && u.verifie;
  const entete = document.getElementById('entete-profil');
  entete.innerHTML = `
    <div class="col-avatar">
      <span class="${u.photo ? 'avatar-agrandissable' : ''}"
            ${u.photo ? `onclick="ouvrirPhoto('${echapper(u.photo)}', '${echapper(u.prenom + ' ' + u.nom)}')"
            title="Voir la photo en grand" role="button" tabindex="0"` : ''}>
        ${avatarHTML(u.initiales, 'xl', u.photo, estMentorVerifie)}
      </span>
    </div>
    <div class="col-infos">
      <h2>${echapper(u.prenom + ' ' + u.nom)}
        ${estMentorVerifie ? badgeMentorVerifie() : ''}
      </h2>
      <div class="ligne-meta">
        <span class="badge-role">${iconeRole(u.role)} ${
          echapper(nomRole(u.role, u.verifie))}</span>
        <span class="etat-presence en-ligne">En ligne</span>
        ${u.pays ? `<span>${ic('position','ic ic-s')} ${echapper(u.pays)}</span>` : ''}
        ${u.domaine ? `<span>${ic('ecole','ic ic-s')} ${echapper(u.domaine)}</span>`
          : (u.etudes ? `<span>${ic('ecole','ic ic-s')} ${echapper(u.etudes)}</span>` : '')}
      </div>
      <div class="tags-profil">
        ${u.secteurs.map(s => `<span class="tag">${echapper(s)}</span>`).join('')}
      </div>
      ${u.bio ? `<p class="bio-profil">${echapper(u.bio)}</p>` : ''}
      ${blocParcoursProfil(u)}
    </div>
    <div class="col-actions">
      <button class="btn btn-secondaire" onclick="televerserPhotoCompte()">${ic('appareil')} Photo</button>
      <button class="btn btn-secondaire" onclick="naviguerApp('parametres')">${ic('crayon')} Modifier</button>
    </div>`;
  const stats = document.getElementById('stats-profil');
  stats.style.display = '';
  stats.innerHTML = `
    <div class="stat-item">
      <span class="stat-valeur">${u.questionsPosees}</span>
      <span class="stat-label">Questions</span>
    </div>
    <div class="stat-item">
      <span class="stat-valeur">${u.mentorsSuivis}</span>
      <span class="stat-label">Référents suivis</span>
    </div>
    ${estMentor() ? `<div class="stat-item accent">
      <span class="stat-valeur">12</span>
      <span class="stat-label">Réponses publiées</span>
    </div>` : ''}`;
  document.getElementById('tabs-profil').innerHTML = `
    <div class="tab-profil actif" onclick="ongletProfil(this, 'questions')">Mes questions</div>
    <div class="tab-profil" onclick="ongletProfil(this, 'sauvees')">Questions sauvegardées</div>
    <div class="tab-profil" onclick="ongletProfil(this, 'mentors')">Référents suivis</div>`;
  ongletProfil(document.querySelector('.tab-profil.actif'), 'questions');
}
function ongletProfil(elem, t) {
  document.querySelectorAll('.tab-profil').forEach(o => o.classList.remove('actif'));
  elem.classList.add('actif');
  const c = document.getElementById('contenu-profil');
  if (t === 'questions') {
    // La complétion précède les publications : c'est ce qui manque au
    // profil qui décide de l'accueil réservé à ce qu'on y publie.
    c.innerHTML = carteCompletionProfil()
      + detailsProfil(etat.utilisateur)
      + questions.slice(0,3).map(q => carteQuestionHTML(q)).join('');
  } else if (t === 'sauvees') {
    const liste = questions.filter(q => etat.sauvegardees.has(q.id));
    c.innerHTML = liste.length
      ? liste.map(q => carteQuestionHTML(q)).join('')
      : `<div class="etat-vide carte"><div class="illu">${ic('marque','ic ic-l')}</div><h3>Aucune question sauvegardée</h3><p>Sauvegardez les questions intéressantes pour les retrouver ici.</p></div>`;
  } else {
    const ids = [...etat.suivis];
    const suiv = ids.length ? mentors.filter(m => etat.suivis.has(m.id)) : mentors.slice(0, 4);
    c.innerHTML = `<div class="carte"><div class="carte-titre">Mes référents suivis</div>${suiv.map(m => `
      <div class="suivi-item" onclick="ouvrirProfilMentor(${m.id})">
        ${avatarHTML(m.initiales)}
        <div class="info"><strong>${echapper(m.prenom + ' ' + m.nom)}</strong><span>${echapper(m.secteur + ' · ' + m.pays)}</span></div>
      </div>`).join('')}</div>`;
  }
}

function rendreProfilMentor(m) {
  const dispoLabel = { disponible:'Disponible', occupe:'Occupé', absent:'Absent' }[m.dispo];
  const suivi = etat.suivis.has(m.id);
  document.getElementById('entete-profil').innerHTML = `
    <div class="col-avatar">
      ${avatarHTML(m.initiales, 'xl', null, m.verifie)}
    </div>
    <div class="col-infos">
      <h2>${echapper(m.prenom + ' ' + m.nom)} ${m.verifie ? badgeMentorVerifie() : ''}</h2>
      <div class="ligne-meta">
        <span class="badge-role badge-mentor">${ic('trophee','ic ic-s')} Référent</span>
        <span>${ic('position','ic ic-s')} ${echapper(m.ville + ', ' + m.pays)}</span>
        <span><span class="point-statut ${m.dispo}"></span>${dispoLabel}</span>
      </div>
      <div class="tags-profil"><span class="tag tag-ambre">${echapper(m.secteur)}</span></div>
      ${m.bio ? `<p class="bio-profil">${echapper(m.bio)}</p>` : ''}
    </div>
    <div class="col-actions">
      <button class="btn ${suivi ? 'btn-secondaire' : 'btn-primaire'}" onclick="basculerSuivre(${m.id}); profilCible = mentors.find(x => x.id === ${m.id}); rendreProfilMentor(profilCible);">${suivi ? ic('check','ic ic-s') + ' Suivi' : '+ Suivre'}</button>
    </div>`;
  const stats = document.getElementById('stats-profil');
  stats.style.display = '';
  stats.innerHTML = `
    <div class="stat-item">
      <span class="stat-valeur">${m.reponses}</span>
      <span class="stat-label">Réponses</span>
    </div>
    <div class="stat-item accent">
      <span class="stat-valeur">${m.note} ★</span>
      <span class="stat-label">Note moyenne</span>
    </div>
    <div class="stat-item">
      <span class="stat-valeur">${echapper(m.anciennete)}</span>
      <span class="stat-label">Sur LaSourcee</span>
    </div>`;
  document.getElementById('tabs-profil').innerHTML = `
    <div class="tab-profil actif" onclick="ongletMentor(this, 'apropos')">À propos</div>
    <div class="tab-profil" onclick="ongletMentor(this, 'reponses')">Réponses récentes</div>`;
  ongletMentor(document.querySelector('.tab-profil.actif'), 'apropos');
}
function ongletMentor(elem, t) {
  document.querySelectorAll('.tab-profil').forEach(o => o.classList.remove('actif'));
  elem.classList.add('actif');
  const c = document.getElementById('contenu-profil');
  const m = profilCible;
  if (t === 'apropos') {
    c.innerHTML = `<div class="carte"><div class="carte-titre">Expériences & formations</div>
      ${m.experiences.map(e => `<div class="bloc-exp"><div class="icone">${ic(e.type === 'diplome' ? 'diplome' : 'mallette')}</div><div class="details"><strong>${echapper(e.poste)}</strong><span>${echapper(e.dates)}</span></div></div>`).join('')}</div>
      <div style="margin-top:14px;"><button class="btn btn-fantome btn-petit" onclick="profilCible = null; rendreProfil()">← Retour à mon profil</button></div>`;
  } else {
    const reps = questions.flatMap(q => q.reponses.filter(r => r.auteur.includes(m.prenom)).map(r => ({...r, question: q.titre, qid: q.id})));
    c.innerHTML = reps.length ? reps.map(r => `<div class="carte" style="margin-bottom:12px; cursor:pointer;" onclick="ouvrirQuestion(${r.qid})"><strong>Sur :</strong> ${echapper(r.question)}<p style="margin-top:8px; color:var(--texte-doux);">${echapper(r.contenu)}</p></div>`).join('')
      : `<div class="etat-vide carte"><div class="illu">${ic('bulle','ic ic-l')}</div><h3>Pas de réponse récente</h3></div>`;
  }
}

/* ============================================================
   ESPACE MENTOR (réservé au rôle mentor)
   Tableau de bord personnel : statut de vérification, statistiques,
   et questions sans réponse dans les secteurs d'expertise du référent.
   ============================================================ */
function rendreEspaceMentor() {
  const u = etat.utilisateur;
  const c = document.getElementById('contenu-mentor');

  if (u.role !== 'mentor') {
    c.innerHTML = `
      <div class="etat-vide carte" style="text-align:center;">
        <div class="illu">${ic('trophee','ic ic-l')}</div>
        <h3>Devenez référent vérifié</h3>
        <p>Partagez votre expérience professionnelle avec les bénéficiaires.
           Votre candidature sera examinée par un administrateur, et vous
           recevrez la réponse par e-mail.</p>
        <button class="btn btn-primaire" style="margin-top:14px;"
                onclick="devenirMentor()">Déposer ma candidature</button>
      </div>`;
    return;
  }

  // Mentor dont la candidature attend encore la validation d'un administrateur
  if (!u.verifie) {
    c.innerHTML = `
      <div class="entete-mentor">
        <div>
          <h2>Espace référent</h2>
          <p style="color:var(--texte-doux);">
            Votre candidature suit son cours.
          </p>
        </div>
        <span class="bandeau-verif attente">
          ${ic('cloche','ic ic-s')} Vérification en attente
        </span>
      </div>

      <div class="carte">
        <div class="carte-titre">Candidature en cours d'examen</div>
        <p style="color:var(--texte-doux); font-size:14px; line-height:1.6;">
          Un administrateur examine votre dossier. Vous recevrez un e-mail
          dès qu'une décision sera prise.
        </p>
        <p style="color:var(--texte-doux); font-size:14px; line-height:1.6; margin-top:10px;">
          Vous pouvez déjà répondre aux questions de la communauté&nbsp;: le
          badge <b>Référent vérifié</b> apparaîtra sur vos réponses une fois la
          validation effectuée.
        </p>
        <div style="display:flex; gap:10px; margin-top:16px;">
          <button class="btn btn-primaire btn-petit" onclick="naviguerApp('fil')">
            Voir les questions
          </button>
          <button class="btn btn-secondaire btn-petit" onclick="devenirMentor()">
            Compléter mon dossier
          </button>
        </div>
      </div>`;
    return;
  }

  // Questions ouvertes correspondant aux secteurs du mentor
  const aTraiter = questions
    .filter(q => u.secteurs.includes(q.secteur) && q.reponses.length === 0)
    .slice(0, 5);
  const stats = {
    reponses: questions.reduce((n, q) =>
      n + q.reponses.filter(r => r.auteur.includes(u.prenom)).length, 0),
    secteurs: u.secteurs.length,
    abonnes: u.mentorsSuivis,
  };

  c.innerHTML = `
    <div class="entete-mentor">
      <div>
        <h2>Espace référent</h2>
        <p style="color:var(--texte-doux);">Suivez votre activité et repérez les bénéficiaires à aider.</p>
      </div>
      <span class="bandeau-verif ${u.verifie ? 'ok' : 'attente'}">
        ${ic(u.verifie ? 'check' : 'cloche','ic ic-s')}
        ${u.verifie ? 'Profil vérifié' : 'Vérification en attente'}
      </span>
    </div>

    <div class="kpi-grid" style="margin-bottom:18px;">
      <div class="kpi-carte"><div class="kpi-icone">${ic('bulle')}</div><div class="label">Réponses publiées</div><div class="valeur">${stats.reponses}</div></div>
      <div class="kpi-carte"><div class="kpi-icone">${ic('etiquette')}</div><div class="label">Secteurs couverts</div><div class="valeur">${stats.secteurs}</div></div>
      <div class="kpi-carte"><div class="kpi-icone">${ic('groupe')}</div><div class="label">Abonnés</div><div class="valeur">${stats.abonnes}</div></div>
    </div>

    <div class="carte">
      <div class="carte-titre">Questions à traiter dans vos secteurs</div>
      ${aTraiter.length
        ? aTraiter.map(q => `
          <div class="ligne-a-traiter">
            <div>
              <strong style="cursor:pointer;" onclick="ouvrirQuestion(${q.id})">${echapper(q.titre)}</strong>
              <div class="meta-q"><span class="tag">${echapper(q.secteur)}</span> · ${echapper(q.auteur)}</div>
            </div>
            <button class="btn btn-primaire btn-petit" onclick="ouvrirQuestion(${q.id})">Répondre</button>
          </div>`).join('')
        : `<p style="color:var(--texte-doux); font-size:14px;">Aucune question en attente dans vos secteurs pour le moment.</p>`}
    </div>`;
}

/* ============================================================
   CANDIDATURE AU STATUT DE MENTOR VÉRIFIÉ
   La demande est transmise aux administrateurs, qui valident ou
   refusent. Le candidat est prévenu par e-mail de la décision.
   ============================================================ */

/* Point d'entrée : ouvre le formulaire de candidature. */
async function devenirMentor() {
  const zone = document.getElementById('contenu-mentor');
  if (!zone) return;

  if (!MODE.api) {
    return toast(
      "La candidature nécessite la connexion au serveur LaSourcee.", 'erreur');
  }

  zone.innerHTML = `<div class="carte"><p style="color:var(--texte-doux);">
    Chargement du formulaire…</p></div>`;

  // Domaines d'expertise proposés (référentiel serveur)
  let secteurs = [];
  try {
    const ref = await API.get('/profil/referentiels');
    secteurs = ref.secteurs || [];
  } catch (_) { /* le formulaire reste utilisable sans la liste */ }

  zone.innerHTML = `
    <div class="entete-mentor">
      <div>
        <h2>Devenir référent vérifié</h2>
        <p style="color:var(--texte-doux);">
          Présentez votre parcours. Un administrateur examinera votre
          demande et vous recevrez sa réponse par e-mail.
        </p>
      </div>
    </div>

    <div class="carte">
      <div id="zone-alerte-candidature"></div>

      <div class="champ">
        <label for="cm-profession">Profession actuelle <span class="obligatoire">*</span></label>
        <input type="text" id="cm-profession" maxlength="120"
               placeholder="Ex : Ingénieure logiciel, Médecin généraliste, Juriste">
      </div>

      <div class="champs-cote">
        <div class="champ">
          <label for="cm-organisation">Employeur ou structure</label>
          <input type="text" id="cm-organisation" maxlength="120"
                 placeholder="Ex : Bank of Africa, cabinet indépendant">
        </div>
        <div class="champ">
          <label for="cm-annees">Années d'expérience <span class="obligatoire">*</span></label>
          <input type="number" id="cm-annees" min="1" max="60" value="1">
        </div>
      </div>

      <div class="champ">
        <label for="cm-bio">Présentation publique <span class="obligatoire">*</span></label>
        <textarea id="cm-bio" maxlength="500" rows="3"
          placeholder="Cette présentation apparaîtra sur votre profil public (40 caractères minimum)."></textarea>
        <div class="compteur-car"><span id="cm-bio-cnt">0</span>/500</div>
      </div>

      <div class="champ">
        <label for="cm-motivation">Pourquoi souhaitez-vous accompagner ? <span class="obligatoire">*</span></label>
        <textarea id="cm-motivation" maxlength="900" rows="4"
          placeholder="Expliquez ce que vous voulez transmettre et à qui (80 caractères minimum). Ce texte n'est lu que par les administrateurs."></textarea>
        <div class="compteur-car"><span id="cm-moti-cnt">0</span>/900</div>
      </div>

      <div class="champ">
        <label for="cm-lien">Profil professionnel en ligne</label>
        <input type="url" id="cm-lien" maxlength="255"
               placeholder="https://linkedin.com/in/… (facultatif, accélère la validation)">
      </div>

      <div class="champ">
        <label>Domaines d'expertise <span class="obligatoire">*</span></label>
        <div class="chips-select" id="cm-secteurs">
          ${secteurs.map(s => `
            <div class="chip-select" data-id="${s.id_secteur}"
                 onclick="this.classList.toggle('actif')">${echapper(s.libelle)}</div>
          `).join('') || '<p style="color:var(--texte-doux);font-size:13px;">Liste indisponible.</p>'}
        </div>
      </div>

      <div style="display:flex; gap:10px; margin-top:18px;">
        <button class="btn btn-primaire" id="cm-envoyer"
                onclick="soumettreCandidatureMentor()">Envoyer ma candidature</button>
        <button class="btn btn-secondaire" onclick="rendreEspaceMentor()">Annuler</button>
      </div>
    </div>`;

  // Compteurs de caractères
  const lier = (idChamp, idCompteur) => {
    const ch = document.getElementById(idChamp);
    const cpt = document.getElementById(idCompteur);
    if (ch && cpt) ch.addEventListener('input', () => {
      cpt.textContent = ch.value.length;
    });
  };
  lier('cm-bio', 'cm-bio-cnt');
  lier('cm-motivation', 'cm-moti-cnt');
}

/* Envoie la candidature au serveur. */
async function soumettreCandidatureMentor() {
  const val = id => (document.getElementById(id)?.value || '').trim();
  const secteurs = [...document.querySelectorAll('#cm-secteurs .chip-select.actif')]
    .map(c => parseInt(c.dataset.id)).filter(Boolean);

  const donnees = {
    profession: val('cm-profession'),
    organisation: val('cm-organisation'),
    annees_experience: parseInt(val('cm-annees')) || 0,
    bio: val('cm-bio'),
    motivation: val('cm-motivation'),
    lien_professionnel: val('cm-lien'),
    secteurs,
  };

  // Contrôles côté navigateur (le serveur revalide de toute façon)
  const erreur = _validerCandidature(donnees);
  if (erreur) return _alerteCandidature(erreur);

  const bouton = document.getElementById('cm-envoyer');
  if (bouton) { bouton.disabled = true; bouton.textContent = 'Envoi en cours…'; }

  try {
    await API.post('/mentors/candidature', donnees);
    if (SESSION.utilisateur) {
      SESSION.utilisateur = await API.get('/profil/moi').catch(() => SESSION.utilisateur);
      appliquerUtilisateur(SESSION.utilisateur);
    }
    toast('Votre candidature a été transmise aux administrateurs.');
    initApp();
    rendreEspaceMentor();
  } catch (err) {
    _alerteCandidature(err.message || "Envoi impossible.");
    if (bouton) { bouton.disabled = false; bouton.textContent = 'Envoyer ma candidature'; }
  }
}

function _validerCandidature(d) {
  if (!d.profession) return "Indiquez votre profession actuelle.";
  if (d.annees_experience < 1) return "Indiquez au moins une année d'expérience.";
  if (d.bio.length < 40)
    return `Votre présentation doit faire au moins 40 caractères (actuellement ${d.bio.length}).`;
  if (d.motivation.length < 80)
    return `Votre motivation doit faire au moins 80 caractères (actuellement ${d.motivation.length}).`;
  if (!d.secteurs.length) return "Choisissez au moins un domaine d'expertise.";
  return null;
}

function _alerteCandidature(message) {
  const z = document.getElementById('zone-alerte-candidature');
  if (z) {
    z.innerHTML = `<div class="alerte alerte-erreur">${echapper(message)}</div>`;
    z.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } else {
    toast(message, 'erreur');
  }
}

/* ============================================================
   NOTIFICATIONS
   ============================================================ */
function basculerNotifs() {
  document.getElementById('panneauNotifs').classList.toggle('ouvert');
  document.getElementById('menuProfil').classList.remove('ouvert');
  etat.sectionActive = etat.sectionActive === 'notifs' ? 'fil' : 'notifs';
  majNavActif();
}
function rendreNotifications() {
  document.getElementById('liste-notifs').innerHTML = notifications.map((n, i) => `
    <div class="notif-item ${n.nonLu?'non-lu':''} ${n.questionId ? 'cliquable' : ''}" onclick="cliquerNotif(${i})">
      <div class="notif-icone">${ic('cloche','ic ic-s')}</div>
      <div><p>${echapper(n.texte)}</p><time>${echapper(n.temps)}</time></div>
    </div>`).join('');
  majBadgeNotifs();
}
function cliquerNotif(i) {
  const n = notifications[i]; if (!n) return;
  n.nonLu = false;
  document.getElementById('panneauNotifs').classList.remove('ouvert');
  if (n.questionId) ouvrirQuestion(n.questionId);
  rendreNotifications();
}
function majBadgeNotifs() {
  const n = notifications.filter(x => x.nonLu).length;
  const b = document.getElementById('badge-notif');
  b.style.display = n ? 'flex' : 'none'; b.textContent = n;
}
async function toutMarquerLu() {
  notifications.forEach(n => n.nonLu = false);
  rendreNotifications();
  if (MODE.api) {
    try { await API.post('/notifications/tout-lu', {}); } catch (_) { /* tolère */ }
  }
  toast('Toutes les notifications ont été marquées comme lues.');
}

/* Recharge les notifications depuis le backend (silencieux). */
async function chargerNotificationsDepuisApi() {
  if (!MODE.api) return;
  try {
    const liste = await API.get('/notifications');
    notifications.length = 0;
    liste.forEach(n => notifications.push({
      texte: n.texte,
      temps: _tempsRelatif(n.cree_le),
      nonLu: !n.est_lue,
      questionId: n.lien_question || null,
    }));
    rendreNotifications();
  } catch (_) { /* on garde les démo */ }
}

/* ============================================================
   MENU PROFIL
   ============================================================ */
function basculerMenuProfil() {
  document.getElementById('menuProfil').classList.toggle('ouvert');
  document.getElementById('panneauNotifs').classList.remove('ouvert');
}

/* ============================================================
   RECHERCHE GLOBALE
   ============================================================ */
/* La recherche interrogeait les tableaux deja charges en memoire : elle
   ne trouvait donc que ce qui figurait sur la page en cours, et restait
   muette sur tout le reste de la plateforme. Elle passe par le serveur,
   qui cherche dans les titres, les corps, les biographies et les
   secteurs.

   La frappe est temporisee : une requete par caractere saturerait le
   serveur pour un resultat que personne ne lit, la suivante arrivant
   avant la fin de la precedente. */
let _minuteurRecherche = null;
let _dernierTermeRecherche = '';

function rechercher(terme) {
  const drop = document.getElementById('dropRech');
  if (!drop) return;
  const t = (terme || '').trim();
  clearTimeout(_minuteurRecherche);
  if (t.length < 2) { drop.classList.remove('ouvert'); return; }
  _minuteurRecherche = setTimeout(() => _rechercherVraiment(t), 280);
}

async function _rechercherVraiment(terme) {
  const drop = document.getElementById('dropRech');
  if (!drop) return;
  _dernierTermeRecherche = terme;
  let r;
  try {
    r = await API.get('/recherche?q=' + encodeURIComponent(terme));
  } catch (_) {
    drop.classList.remove('ouvert');
    return;
  }
  // Une reponse plus lente qu'une frappe plus recente ne doit pas
  // remplacer un resultat deja plus juste.
  if (_dernierTermeRecherche !== terme) return;

  let html = '';
  if ((r.mentors || []).length) {
    html += '<h5>Référents</h5>';
    html += r.mentors.map(m => `<div class="res-item"
        onclick="ouvrirProfilUtilisateur(${m.id_utilisateur}); fermerRecherche();">
        ${avatarHTML(((m.prenom||'?')[0] + (m.nom||'?')[0]).toUpperCase(), 's', m.photo_url)}
        <span>${echapper((m.prenom || '') + ' ' + (m.nom || ''))}</span>
      </div>`).join('');
  }
  if ((r.questions || []).length) {
    html += '<h5>Questions</h5>';
    html += r.questions.map(q => `<div class="res-item"
        onclick="ouvrirQuestion(${q.id_question}); fermerRecherche();">
        <span>${echapper(q.titre)}</span>
      </div>`).join('');
  }
  if ((r.secteurs || []).length) {
    html += '<h5>Secteurs</h5>';
    html += r.secteurs.map(s => `<div class="res-item"
        onclick="filtrerParSecteur('${echapper(s.libelle)}'); fermerRecherche();">
        <span class="tag">${echapper(s.libelle)}</span>
      </div>`).join('');
  }
  if (!html) {
    html = `<div class="res-vide">Aucun résultat pour « ${echapper(terme)} ».</div>`;
  }
  drop.innerHTML = html;
  drop.classList.add('ouvert');
}

function fermerRecherche() {
  document.getElementById('dropRech')?.classList.remove('ouvert');
}

function filtrerParSecteur(libelle) {
  const sel = document.getElementById('filtre-secteur');
  if (sel) sel.value = libelle;
  naviguerApp('fil');
  rendreFil();
}

function lancerRecherche() {
  const inp = document.getElementById('recherche-glob');
  const v = (inp.value || '').trim();
  if (!v) return toast('Saisissez un terme à rechercher.', 'erreur');
  etat.rechercheTerme = v;
  document.getElementById('dropRech').classList.remove('ouvert');
  naviguerApp('fil');
}
function effacerRecherche() {
  etat.rechercheTerme = '';
  document.getElementById('recherche-glob').value = '';
  rendreFil();
}

/* ============================================================
   PARAMÈTRES
   ============================================================ */
function changerPanParam(elem, p) {
  if (!elem) return;
  document.querySelectorAll('#menu-param button').forEach(b => b.classList.remove('actif'));
  elem.classList.add('actif');
  const c = document.getElementById('contenu-param');
  if (p === 'compte') {
    chargerReferentielsProfil().then(() => {
      c.innerHTML = panneauCompte();
      // L'état de la limite se calcule au rendu, pas au premier clic :
      // sinon quelqu'un arrivant avec quatre objectifs déjà cochés
      // pourrait en cocher un cinquième.
      limiterObjectifs();
    });
  }
  if (p === 'notifs') { c.innerHTML = panneauNotifsParam(); chargerPreferences(); }
  if (p === 'securite') { c.innerHTML = panneauSecurite(); chargerSessions(); }
  if (p === 'confid') c.innerHTML = panneauConfid();
}

function panneauCompte() {
  const u = etat.utilisateur;
  const secteursDefaut = ['Technologie','Médecine','Droit','Finance','Arts','Éducation','Ingénierie','Entrepreneuriat'];
  const secteursPerso = (u.secteurs || []).filter(s => !secteursDefaut.includes(s));
  const optsPays = LISTE_PAYS.map(p =>
    `<option value="${echapper(p)}"${p === u.pays ? ' selected' : ''}>${echapper(p)}</option>`).join('');
  return `<div class="section-param">
    <h2>Mon compte</h2>
    <div class="champs-cote">
      <div class="champ"><label>Prénom</label><input id="pc-prenom" value="${echapper(u.prenom)}" /></div>
      <div class="champ"><label>Nom</label><input id="pc-nom" value="${echapper(u.nom)}" /></div>
    </div>
    <div class="champ"><label>E-mail</label><input id="pc-email" type="email" value="${echapper(u.email || (u.prenom.toLowerCase() + '.' + u.nom.toLowerCase() + '@email.com'))}" /></div>
    <div class="champs-cote">
      <div class="champ"><label for="pc-pays">Pays</label>
        <select id="pc-pays"><option value="">Sélectionnez votre pays</option>${optsPays}</select>
      </div>
      <div class="champ"><label for="pc-tel">Téléphone <span class="facultatif">visible de vous seul</span></label>
        <input id="pc-tel" type="tel" inputmode="tel" autocomplete="tel"
               value="${echapper(u.telephone || '')}"
               placeholder="+229 01 55 04 04 32" />
      </div>
    </div>
    <div class="champ"><label for="pc-situation">Où en êtes-vous ?</label>
      <select id="pc-situation">
        <option value="">Préférer ne pas dire</option>
        ${(etat.referentielsProfil?.situations || []).map(s =>
          `<option value="${echapper(s)}"${s === u.situation ? ' selected' : ''}>${echapper(s)}</option>`).join('')}
      </select>
    </div>
    <fieldset class="champ groupe-objectifs">
      <legend>Ce que vous cherchez</legend>
      <p class="aide-champ" style="margin:0 0 10px;">Plusieurs réponses
         possibles, jusqu'à ${LIMITE_OBJECTIFS}. Personne ne cherche une
         seule chose : on prépare un départ tout en cherchant un stage.</p>
      <div class="chips-objectifs" id="pc-objectifs">
        ${(etat.referentielsProfil?.objectifs || []).map(o => `
          <label class="chip-choix">
            <input type="checkbox" value="${echapper(o)}"
                   ${(u.objectifs || []).includes(o) ? 'checked' : ''}
                   onchange="limiterObjectifs()" />
            <span>${echapper(o)}</span>
          </label>`).join('')}
      </div>
      <p class="aide-champ" id="compte-objectifs"></p>
    </fieldset>
    <div class="champs-cote">
      <div class="champ"><label for="pc-niveau">Diplôme le plus élevé obtenu</label>
        <select id="pc-niveau">
          <option value="">Préférer ne pas dire</option>
          ${(etat.referentielsProfil?.niveaux_etudes || []).map(n =>
            `<option value="${echapper(n)}"${n === u.niveau_etudes ? ' selected' : ''}>${echapper(n)}</option>`).join('')}
        </select>
      </div>
      <div class="champ"><label for="pc-domaine">Domaine ou métier</label>
        <select id="pc-domaine">
          <option value="">Préférer ne pas dire</option>
          ${(etat.referentielsProfil?.domaines || []).map(o =>
            `<option value="${echapper(o)}"${o === u.domaine ? ' selected' : ''}>${echapper(o)}</option>`).join('')}
        </select>
      </div>
    </div>
    <div class="champ"><label for="pc-etablissement">Établissement ou lieu de formation</label>
      <input id="pc-etablissement" list="liste-etablissements-pc" maxlength="120"
             value="${echapper(u.etablissement || '')}"
             placeholder="Université, école, centre de formation ou atelier" />
      <datalist id="liste-etablissements-pc">
        ${(etat.referentielsProfil?.etablissements || []).map(e =>
          `<option value="${echapper(e)}"></option>`).join('')}
      </datalist>
      <p class="aide-champ">Saisissez librement si votre établissement n'est pas proposé.</p>
    </div>
    <div class="champs-cote">
      <div class="champ"><label for="pc-langues">Langues parlées</label>
        <input id="pc-langues" value="${echapper(u.langues || '')}" placeholder="Ex : français, anglais, fon" />
      </div>
      <div class="champ"><label for="pc-profilpro">Profil professionnel</label>
        <input id="pc-profilpro" type="url" value="${echapper(u.profil_pro || '')}" placeholder="https://www.linkedin.com/in/..." />
      </div>
    </div>
    <div class="champ"><label>Biographie</label>
      <textarea id="pc-bio" maxlength="500" oninput="document.getElementById('bio-cnt').textContent=this.value.length">${echapper(u.bio)}</textarea>
      <div class="compteur-car"><span id="bio-cnt">${u.bio.length}</span>/500</div>
    </div>
    <div class="champ"><label>Photo de profil</label>
      <div style="display:flex; align-items:center; gap:14px;">
        ${avatarHTML(u.initiales, 'l', u.photo)}
        <div>
          <button class="btn btn-secondaire" onclick="televerserPhotoCompte()">${ic('appareil')} Téléverser une photo</button>
          <p style="font-size:12px; color:var(--texte-doux); margin-top:6px;">JPG ou PNG, max 3 Mo. Visible par les autres utilisateurs.</p>
        </div>
      </div>
    </div>
    <div class="champ"><label>Secteurs d'intérêt</label>
      <div class="chips-select" id="pc-chips">
        ${secteursDefaut.map(s =>
          `<div class="chip-select ${u.secteurs.includes(s)?'actif':''}" onclick="toggleChip(this)">${s}</div>`).join('')}
        ${secteursPerso.map(s =>
          `<div class="chip-select chip-perso actif" data-perso="1"><span onclick="toggleChip(this.parentElement)">${echapper(s)}</span><button type="button" class="chip-sup" onclick="this.parentElement.remove()" aria-label="Supprimer">×</button></div>`).join('')}
        <div class="chip-select" data-autre="1" onclick="document.getElementById('pc-autre-wrap').style.display=''; document.getElementById('pc-autre-input').focus();">+ Autre</div>
      </div>
      <div id="pc-autre-wrap" style="display:none; margin-top:10px;">
        <div style="display:flex; gap:8px;">
          <input type="text" id="pc-autre-input" placeholder="Ex : Agriculture durable" style="flex:1;" />
          <button type="button" class="btn btn-secondaire btn-petit" onclick="ajouterSecteurPersoParam()">Ajouter</button>
        </div>
        <p style="font-size:12px; color:var(--texte-doux); margin-top:6px;">Vous pouvez ajouter plusieurs secteurs personnalisés, et supprimer ceux ajoutés en cliquant sur ×.</p>
      </div>
    </div>
    <button class="btn btn-primaire" onclick="sauverCompte()">Enregistrer</button>
  </div>`;
}

function ajouterSecteurPersoParam() {
  const input = document.getElementById('pc-autre-input');
  const conteneur = document.getElementById('pc-chips');
  if (!input || !conteneur) return;
  const v = (input.value || '').trim();
  if (!v) { toast('Saisissez un secteur.', 'erreur'); return; }
  const existe = [...conteneur.querySelectorAll('.chip-select')]
    .some(c => c.textContent.trim().replace(/\s*×$/, '').replace(/^\+\s*Autre$/, '').toLowerCase() === v.toLowerCase());
  if (existe) { toast('Ce secteur est déjà présent.', 'erreur'); input.value = ''; return; }
  const chip = document.createElement('div');
  chip.className = 'chip-select chip-perso actif';
  chip.dataset.perso = '1';
  chip.innerHTML = `<span onclick="toggleChip(this.parentElement)">${echapper(v)}</span><button type="button" class="chip-sup" onclick="this.parentElement.remove()" aria-label="Supprimer">×</button>`;
  const chipAutre = conteneur.querySelector('[data-autre="1"]');
  conteneur.insertBefore(chip, chipAutre);
  input.value = '';
  input.focus();
}

async function sauverCompte() {
  const prenom = (document.getElementById('pc-prenom')?.value || '').trim();
  const nom = (document.getElementById('pc-nom')?.value || '').trim();
  const email = (document.getElementById('pc-email')?.value || '').trim();
  const pays = document.getElementById('pc-pays')?.value || '';
  const bio = document.getElementById('pc-bio')?.value || '';
  const situation = document.getElementById('pc-situation')?.value || '';
  const objectifs = [...document.querySelectorAll('#pc-objectifs input:checked')]
    .map(e => e.value);
  const langues = (document.getElementById('pc-langues')?.value || '').trim();
  const profilPro = (document.getElementById('pc-profilpro')?.value || '').trim();
  const telephone = (document.getElementById('pc-tel')?.value || '').trim();
  const niveauEtudes = document.getElementById('pc-niveau')?.value || '';
  const domaine = document.getElementById('pc-domaine')?.value || '';
  const etablissement = (document.getElementById('pc-etablissement')?.value || '').trim();
  const secteurs = [...document.querySelectorAll('#pc-chips .chip-select.actif')]
    .map(c => c.textContent.trim().replace(/\s*×$/, '').replace(/^\+\s*Autre$/, ''))
    .filter(Boolean);
  if (!prenom || !nom) { toast('Prénom et nom obligatoires.', 'erreur'); return; }
  etat.utilisateur.prenom = prenom;
  etat.utilisateur.nom = nom;
  etat.utilisateur.initiales = (prenom[0] + nom[0]).toUpperCase();
  etat.utilisateur.email = email;
  etat.utilisateur.pays = pays;
  etat.utilisateur.bio = bio;
  etat.utilisateur.secteurs = secteurs;
  etat.utilisateur.situation = situation;
  etat.utilisateur.objectifs = objectifs;
  etat.utilisateur.objectif = objectifs.join(', ');
  etat.utilisateur.langues = langues;
  etat.utilisateur.profil_pro = profilPro;
  etat.utilisateur.telephone = telephone;
  etat.utilisateur.niveau_etudes = niveauEtudes;
  etat.utilisateur.domaine = domaine;
  etat.utilisateur.etablissement = etablissement;
  // Rafraîchir la navigation immédiatement (retour visuel)
  const navAv = document.getElementById('avatar-nav');
  if (navAv && !etat.utilisateur.photo) navAv.textContent = etat.utilisateur.initiales;
  if (typeof rendreSidebarProfil === 'function') rendreSidebarProfil();

  // Enregistrement sur le serveur
  try {
    const id_pays = await _idPaysDepuisLibelle(pays);
    await API.put('/profil/moi', {
      prenom, nom, bio,
      photo_url: etat.utilisateur.photo || undefined,
      id_pays: id_pays || undefined,
      // Une chaîne vide est envoyée telle quelle : c'est ainsi qu'on
      // efface un champ. undefined le laisserait inchangé.
      situation, objectifs, langues,
      profil_pro: profilPro,
      telephone,
      niveau_etudes: niveauEtudes,
      domaine,
      etablissement,
      // Les secteurs étaient relevés puis oubliés : la requête ne les
      // portait pas, et les cases cochées revenaient à leur état
      // précédent au rechargement de la page.
      secteurs: await _idsSecteursDepuisLibelles(secteurs),
    });
    SESSION.utilisateur = await API.get('/profil/moi');
    toast('Modifications enregistrées.');
  } catch (err) {
    toast(err.message || "Enregistrement impossible.", 'erreur');
  }
}

/* Convertit un libellé de pays en identifiant du référentiel. */
async function _idPaysDepuisLibelle(libelle) {
  if (!libelle) return null;
  try {
    if (!_idPaysDepuisLibelle._cache) {
      const ref = await API.get('/profil/referentiels');
      _idPaysDepuisLibelle._cache = ref.pays || [];
    }
    const p = _idPaysDepuisLibelle._cache
      .find(x => x.libelle.toLowerCase() === libelle.toLowerCase());
    return p ? p.id_pays : null;
  } catch (_) { return null; }
}

/* Convertit des libellés de secteurs en identifiants du référentiel.

   Le serveur attend des identifiants ; l'interface manipule des
   libellés. Les secteurs saisis librement n'existent pas au
   référentiel et sont ignorés ici plutôt que de faire échouer tout
   l'enregistrement. */
async function _idsSecteursDepuisLibelles(libelles) {
  if (!libelles || !libelles.length) return [];
  try {
    if (!_idsSecteursDepuisLibelles._cache) {
      const ref = await API.get('/profil/referentiels');
      _idsSecteursDepuisLibelles._cache = ref.secteurs || [];
    }
    const connus = _idsSecteursDepuisLibelles._cache;
    return libelles
      .map(l => connus.find(s => s.libelle.toLowerCase() === l.toLowerCase()))
      .filter(Boolean)
      .map(s => s.id_secteur);
  } catch (_) { return []; }
}

/* Les préférences venaient d'une liste écrite en dur : chaque
   interrupteur confirmait l'enregistrement sans rien conserver, et tout
   revenait à l'état initial au rechargement. Elles sont désormais lues
   et écrites sur le serveur. */
const PREFERENCES_NOTIF = [
  ['reponse_question', 'Nouvelle réponse à mes questions'],
  ['reactions',        'Réactions sur mes publications'],
  ['questions_secteur','Nouvelles questions dans mes secteurs'],
  ['reponses_suivis',  'Réponses des référents que je suis'],
  ['infolettre',       'Infolettre hebdomadaire'],
];

/* Le courriel ne reprend que les trois premières : recevoir un message
   pour chaque réaction saturerait la boîte de n'importe qui. */
const PREFERENCES_EMAIL = PREFERENCES_NOTIF.slice(0, 3);

function panneauNotifsParam() {
  return `<div class="section-param"><h2>Notifications</h2>
    <p class="desc" style="margin-bottom:14px;">
      Choisissez ce dont vous voulez être averti. Les modifications sont
      enregistrées immédiatement.</p>
    <div id="zone-preferences"><p class="desc">Chargement…</p></div>
  </div>`;
}

function _ligneToggle(canal, cle, libelle, actif) {
  return `<div class="ligne-toggle">
    <div><strong>${echapper(libelle)}</strong></div>
    <div class="toggle ${actif ? 'on' : ''}" role="switch"
         tabindex="0" aria-checked="${actif ? 'true' : 'false'}"
         aria-label="${echapper(libelle)}"
         data-canal="${canal}" data-cle="${cle}"
         onclick="basculerPreference(this)"
         onkeydown="if(event.key===' '||event.key==='Enter'){event.preventDefault();basculerPreference(this);}"></div>
  </div>`;
}

async function chargerPreferences() {
  const zone = document.getElementById('zone-preferences');
  if (!zone) return;
  let prefs;
  try {
    prefs = await API.get('/profil/preferences');
  } catch (err) {
    zone.innerHTML = `<p class="desc">Préférences indisponibles : ${echapper(err.message || '')}</p>`;
    return;
  }
  etat.preferences = prefs;

  zone.innerHTML = `
    <h3 class="titre-param">Dans l'application</h3>
    ${PREFERENCES_NOTIF.map(([cle, lib]) =>
        _ligneToggle('app', cle, lib, prefs.app && prefs.app[cle])).join('')}
    <h3 class="titre-param" style="margin-top:22px;">Par e-mail</h3>
    ${PREFERENCES_EMAIL.map(([cle, lib]) =>
        _ligneToggle('email', cle, lib, prefs.email && prefs.email[cle])).join('')}
    <p class="note-param" id="etat-preferences"></p>`;
}

async function basculerPreference(element) {
  const canal = element.dataset.canal;
  const cle = element.dataset.cle;
  if (!etat.preferences) return;

  const nouvelEtat = !element.classList.contains('on');
  element.classList.toggle('on', nouvelEtat);
  element.setAttribute('aria-checked', nouvelEtat ? 'true' : 'false');
  etat.preferences[canal][cle] = nouvelEtat;

  const info = document.getElementById('etat-preferences');
  if (info) info.textContent = 'Enregistrement…';
  try {
    etat.preferences = await API.put('/profil/preferences', etat.preferences);
    if (info) info.textContent = 'Préférences enregistrées.';
  } catch (err) {
    // L'interrupteur revient à sa position : afficher un état qui n'a
    // pas été enregistré tromperait la personne.
    element.classList.toggle('on', !nouvelEtat);
    element.setAttribute('aria-checked', !nouvelEtat ? 'true' : 'false');
    etat.preferences[canal][cle] = !nouvelEtat;
    if (info) info.textContent = '';
    toast(err.message || "Impossible d'enregistrer.", 'erreur');
  }
}

/* Rappel affiché tant qu'un compte tourne avec le mot de passe temporaire
   reçu par e-mail. Les comptes administrateurs sont créés ainsi : sans ce
   rappel, le mot de passe provisoire resterait en place indéfiniment. */
function majRappelMotDePasse() {
  const doitChanger = !!(etat.utilisateur && etat.utilisateur.doit_changer_mdp);
  const existant = document.getElementById('rappel-mdp');
  if (!doitChanger) return existant && existant.remove();
  if (existant) return;

  const bandeau = document.createElement('div');
  bandeau.id = 'rappel-mdp';
  bandeau.className = 'bandeau-alerte bandeau-fixe';
  bandeau.setAttribute('role', 'alert');
  bandeau.innerHTML = `
    <span><strong>Mot de passe temporaire.</strong>
      Choisissez votre propre mot de passe pour sécuriser ce compte.</span>
    <button class="btn btn-petit" onclick="allerChangerMotDePasse()">Le changer</button>`;
  document.body.prepend(bandeau);
}

function masquerRappelMotDePasse() {
  const b = document.getElementById('rappel-mdp');
  if (b) b.remove();
}

function allerChangerMotDePasse() {
  naviguerApp('parametres');
  const onglet = document.querySelector('#menu-param button[data-pan="securite"]');
  if (onglet) changerPanParam(onglet, 'securite');
}

/* Champ mot de passe avec bouton « afficher ». Le balisage de l'icône
   était recopié à l'identique à chaque champ : il est factorisé ici. */
function champMotDePasse(id, libelle, attributs = '') {
  return `<div class="champ"><label for="${id}">${libelle}</label>
    <div class="champ-mdp">
      <input type="password" id="${id}" autocomplete="off" ${attributs} />
      <button type="button" class="btn-oeil" aria-label="Afficher le mot de passe" onclick="basculerOeil(this)">
        <svg class="oeil-ouvert" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>
        <svg class="oeil-ferme" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none;"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-11-7-11-7a19.77 19.77 0 0 1 4.22-5.17"/><path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 7 11 7a19.85 19.85 0 0 1-3.17 4.05"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
      </button>
    </div></div>`;
}

function panneauSecurite() {
  const doitChanger = !!(etat.utilisateur && etat.utilisateur.doit_changer_mdp);
  const alerte = doitChanger ? `
    <div class="bandeau-alerte" role="alert">
      <strong>Mot de passe temporaire.</strong>
      Ce compte utilise encore le mot de passe reçu par e-mail.
      Choisissez-en un nouveau maintenant : c'est la seule façon de le
      rendre personnel.
    </div>` : '';

  return `<div class="section-param"><h2>Sécurité</h2>
    ${alerte}
    <h3 class="titre-param">Changer le mot de passe</h3>
    ${champMotDePasse('mdp-actuel', 'Mot de passe actuel')}
    ${champMotDePasse('mdp-nouveau', 'Nouveau mot de passe',
                      'oninput="majRobustesseMdp(this.value)"')}
    <div class="jauge-mdp"><div class="jauge-remplir" id="jauge-mdp"></div></div>
    <div class="aide-mdp" id="aide-mdp">Au moins 8 caractères, avec majuscule, chiffre et symbole.</div>
    ${champMotDePasse('mdp-confirme', 'Confirmer le nouveau mot de passe')}
    <button class="btn btn-primaire" id="btn-changer-mdp" onclick="changerMotDePasse()">Modifier le mot de passe</button>
    <p class="note-param">Le changement déconnecte tous vos autres appareils.</p>

    <h3 class="titre-param" style="margin-top:26px;">Appareils connectés</h3>
    <div id="liste-sessions"><p class="desc">Chargement…</p></div>
    <button class="btn btn-fantome btn-petit" onclick="revoquerAutresSessions()">Déconnecter les autres appareils</button>
  </div>`;
}

/* Changement de mot de passe : contrôles côté navigateur pour un retour
   immédiat, mais c'est le serveur qui fait foi. */
async function changerMotDePasse() {
  const actuel   = document.getElementById('mdp-actuel')?.value || '';
  const nouveau  = document.getElementById('mdp-nouveau')?.value || '';
  const confirme = document.getElementById('mdp-confirme')?.value || '';

  if (!actuel || !nouveau) {
    return toast('Renseignez le mot de passe actuel et le nouveau.', 'erreur');
  }
  if (nouveau !== confirme) {
    return toast('Les deux nouveaux mots de passe ne correspondent pas.', 'erreur');
  }
  if (nouveau === actuel) {
    return toast('Le nouveau mot de passe doit être différent de l\'ancien.', 'erreur');
  }

  const bouton = document.getElementById('btn-changer-mdp');
  if (bouton) { bouton.disabled = true; bouton.textContent = 'Modification…'; }
  try {
    await API.post('/auth/changer-mdp', {
      mot_de_passe_actuel: actuel,
      nouveau_mot_de_passe: nouveau,
    });
    toast('Mot de passe modifié.');
    if (etat.utilisateur) etat.utilisateur.doit_changer_mdp = 0;
    if (SESSION.utilisateur) SESSION.utilisateur.doit_changer_mdp = 0;
    masquerRappelMotDePasse();
    changerPanParam(document.querySelector('#menu-param button[data-pan="securite"]'), 'securite');
  } catch (err) {
    toast(err.message || 'Modification impossible.', 'erreur');
  } finally {
    if (bouton) { bouton.disabled = false; bouton.textContent = 'Modifier le mot de passe'; }
  }
}

/* Liste réelle des sessions ouvertes, lue depuis le serveur. */
async function chargerSessions() {
  const zone = document.getElementById('liste-sessions');
  if (!zone) return;
  try {
    const sessions = await API.get('/auth/sessions');
    if (!sessions.length) {
      zone.innerHTML = '<p class="desc">Aucune session active.</p>';
      return;
    }
    zone.innerHTML = sessions.map(s => `
      <div class="ligne-session">
        <div>
          <strong>${echapper(s.appareil)}</strong>
          <div class="desc">Ouverte ${_tempsRelatif(s.cree_le)}</div>
        </div>
        ${s.courante
          ? '<span class="tag tag-vert">Session courante</span>'
          : `<button class="btn btn-fantome btn-petit" onclick="revoquerSession('${echapper(s.reference)}')">Déconnecter</button>`}
      </div>`).join('');
  } catch (err) {
    zone.innerHTML = `<p class="desc">Sessions indisponibles : ${echapper(err.message || '')}</p>`;
  }
}

async function revoquerSession(reference) {
  try {
    const r = await API.delete('/auth/sessions/' + encodeURIComponent(reference));
    if (r && r.etait_courante) {
      toast('Vous avez été déconnecté de cet appareil.');
      return setTimeout(() => location.reload(), 800);
    }
    toast('Appareil déconnecté.');
    chargerSessions();
  } catch (err) {
    toast(err.message || 'Révocation impossible.', 'erreur');
  }
}

async function revoquerAutresSessions() {
  try {
    const r = await API.post('/auth/sessions/revoquer-autres');
    const n = (r && r.revoquees) || 0;
    toast(n ? `${n} appareil(s) déconnecté(s).` : 'Aucun autre appareil connecté.');
    chargerSessions();
  } catch (err) {
    toast(err.message || 'Opération impossible.', 'erreur');
  }
}

/* Indicateur visuel de robustesse du mot de passe (0 à 4). */
function evaluerMdp(v) {
  let score = 0;
  if (v.length >= 8) score++;
  if (v.length >= 12) score++;
  if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
  if (/\d/.test(v) && /[^A-Za-z0-9]/.test(v)) score++;
  return Math.min(4, score);
}
function majRobustesseMdp(v) {
  const niveaux = [
    { l: 'Très faible', c: 'var(--rouge)',   w: '15%' },
    { l: 'Faible',      c: 'var(--orange)',  w: '35%' },
    { l: 'Correct',     c: '#caa83a',        w: '60%' },
    { l: 'Bon',         c: '#5a9e57',        w: '80%' },
    { l: 'Excellent',   c: 'var(--vert)',    w: '100%' },
  ];
  const n = v ? niveaux[evaluerMdp(v)] : { l: '', c: 'var(--bordure)', w: '0%' };
  const barre = document.getElementById('jauge-mdp');
  const aide = document.getElementById('aide-mdp');
  if (barre) { barre.style.width = n.w; barre.style.background = n.c; }
  if (aide && v) { aide.textContent = 'Robustesse : ' + n.l; aide.style.color = n.c; }
}

function panneauConfid() {
  return `<div class="section-param"><h2>Confidentialité et données</h2>
    <p class="desc" style="margin-bottom:16px;">
      Ce que LaSourcee conserve, qui le voit, et ce que vous pouvez en
      faire.</p>

    <div class="ligne-session"><div>
      <strong>Votre profil</strong>
      <div class="desc">Prénom, nom, photo, présentation et domaines sont
        visibles par les membres connectés. Votre adresse e-mail ne l'est
        jamais.</div></div></div>

    <div class="ligne-session"><div>
      <strong>Cookies</strong>
      <div class="desc">Un seul est déposé, celui de votre session. Aucun
        traceur publicitaire, aucun partage avec des tiers.</div></div></div>

    <div class="ligne-session"><div>
      <strong>Vos publications</strong>
      <div class="desc">Questions et réponses sont visibles des membres :
        c'est ce qui permet à d'autres d'en profiter. Vous pouvez
        supprimer les vôtres à tout moment.</div></div></div>

    <h3 class="titre-param" style="margin-top:24px;">Emporter vos données</h3>
    <p class="desc">Un fichier contenant tout ce que la plateforme
       conserve sur vous : profil, préférences, questions et réponses.</p>
    <button class="btn btn-secondaire btn-petit" onclick="telechargerMesDonnees(this)">
      Télécharger mes données</button>

    <h3 class="titre-param" style="margin-top:26px;">Supprimer mon compte</h3>
    <div class="zone-danger">
      <p>La suppression est <strong>définitive</strong>. Votre profil, vos
         questions et vos réponses disparaissent, et rien ne permet de les
         rétablir.</p>
      <p class="desc">Téléchargez vos données avant, si vous souhaitez en
         garder une trace.</p>
      <button class="btn btn-danger btn-petit" onclick="ouvrirSuppressionCompte()">
        Supprimer définitivement mon compte</button>
    </div>
  </div>`;
}

async function telechargerMesDonnees(bouton) {
  const libelle = bouton.textContent;
  bouton.disabled = true;
  bouton.textContent = 'Préparation…';
  try {
    const donnees = await API.get('/profil/moi/donnees');
    const contenu = JSON.stringify(donnees, null, 2);
    const lien = document.createElement('a');
    lien.href = URL.createObjectURL(
      new Blob([contenu], { type: 'application/json' }));
    lien.download = 'mes-donnees-lasourcee.json';
    lien.click();
    URL.revokeObjectURL(lien.href);
    toast('Vos données ont été téléchargées.');
  } catch (err) {
    toast(err.message || 'Téléchargement impossible.', 'erreur');
  } finally {
    bouton.disabled = false;
    bouton.textContent = libelle;
  }
}

/* La suppression demande le mot de passe et la recopie d'un mot. Le
   premier écarte celui qui passerait derrière une session laissée
   ouverte, le second le clic accidentel sur un bouton rouge. */
function ouvrirSuppressionCompte() {
  fermerMentionsLegales();
  const fond = document.createElement('div');
  fond.className = 'modale-fond';
  fond.id = 'modaleLegale';
  fond.setAttribute('role', 'dialog');
  fond.setAttribute('aria-modal', 'true');
  fond.innerHTML = `
    <div class="modale-boite">
      <div class="modale-entete">
        <h2>Supprimer votre compte</h2>
        <button class="modale-fermer" onclick="fermerMentionsLegales()" aria-label="Fermer">&times;</button>
      </div>
      <div class="modale-corps">
        <div class="bandeau-alerte" role="alert">
          <strong>Cette action est définitive.</strong> Votre profil, vos
          questions et vos réponses seront effacés. Aucune restauration
          n'est possible.
        </div>
        ${champMotDePasse('supp-mdp', 'Votre mot de passe')}
        <div class="champ">
          <label for="supp-conf">Recopiez <strong>SUPPRIMER</strong> pour confirmer</label>
          <input type="text" id="supp-conf" autocomplete="off" placeholder="SUPPRIMER" />
        </div>
        <button class="btn btn-danger" id="btn-supp-compte"
                onclick="confirmerSuppressionCompte()">Supprimer définitivement</button>
        <button class="btn btn-fantome" onclick="fermerMentionsLegales()">Annuler</button>
      </div>
    </div>`;
  fond.addEventListener('click', (e) => {
    if (e.target === fond) fermerMentionsLegales();
  });
  document.body.appendChild(fond);
  document.body.style.overflow = 'hidden';
}

async function confirmerSuppressionCompte() {
  const mdp = document.getElementById('supp-mdp')?.value || '';
  const conf = document.getElementById('supp-conf')?.value || '';
  const bouton = document.getElementById('btn-supp-compte');

  if (!mdp) return toast('Saisissez votre mot de passe.', 'erreur');
  if (conf.trim().toUpperCase() !== 'SUPPRIMER') {
    return toast('Recopiez le mot SUPPRIMER pour confirmer.', 'erreur');
  }

  if (bouton) { bouton.disabled = true; bouton.textContent = 'Suppression…'; }
  try {
    await API.delete('/profil/moi', { mot_de_passe: mdp, confirmation: conf });
    fermerMentionsLegales();
    toast('Votre compte a été supprimé.');
    setTimeout(() => { window.location.href = '/'; }, 1200);
  } catch (err) {
    toast(err.message || 'Suppression impossible.', 'erreur');
    if (bouton) { bouton.disabled = false; bouton.textContent = 'Supprimer définitivement'; }
  }
}

/* ============================================================
   ADMINISTRATION
   ============================================================ */
async function changerPanAdmin(elem, p) {
  if (!elem) return;
  document.querySelectorAll('.menu-admin button').forEach(b => b.classList.remove('actif'));
  elem.classList.add('actif');
  const c = document.getElementById('contenu-admin');
  c.innerHTML = '<p style="color:var(--texte-doux); padding:20px;">Chargement…</p>';
  try {
    if (p === 'dashboard')     c.innerHTML = await adminDashboard();
    else if (p === 'users')    c.innerHTML = await adminUsers();
    else if (p === 'mentors')  c.innerHTML = await adminMentors();
    else if (p === 'signalements') c.innerHTML = await adminSignalements();
    else if (p === 'categories')   c.innerHTML = await adminCategories();
    else if (p === 'audit')        c.innerHTML = await adminAudit();
    else if (p === 'diagnostic')   c.innerHTML = await adminDiagnostic();
    else if (p === 'administrateurs') c.innerHTML = await adminAdministrateurs();
    else if (p === 'export')       c.innerHTML = await adminExport();
  } catch (err) {
    c.innerHTML = `<div class="carte"><p style="color:var(--rouge);">
      Erreur de chargement : ${echapper(err.message || 'inconnue')}.</p></div>`;
  }
}
async function adminDashboard() {
  const d = await API.get('/admin/dashboard');
  return _rendreDashboardAdmin(d);
}

function _rendreDashboardAdmin(d) {
  const kpis = [
    ['groupe',  'Total inscrits',   d.utilisateurs],
    ['profil',  'Étudiants',        d.etudiants],
    ['trophee', 'Référents',        d.mentors],
    ['bouclier','Administrateurs',  d.admins],
    ['bulle',   'Questions',        d.questions],
    ['etincelle','Réponses',        d.reponses],
    ['drapeau', 'Signalements ouverts', d.signalements_ouverts],
    ['check',   'Référents à vérifier', d.mentors_a_verifier],
  ];
  return `<h2 style="margin-bottom:18px;">Tableau de bord</h2>
    <div class="kpi-grid">
      ${kpis.map(([icone, label, valeur]) => `
        <div class="kpi-carte">
          <div class="kpi-icone">${ic(icone)}</div>
          <div class="label">${label}</div>
          <div class="valeur">${valeur}</div>
        </div>`).join('')}
    </div>
    <div class="carte" style="margin-top:16px;">
      <div class="carte-titre">Comptes suspendus</div>
      <p style="font-size:1.5rem; font-family:'DM Serif Display',serif;">${d.comptes_suspendus || 0}</p>
    </div>`;
}
async function adminUsers() {
  const liste = await API.get('/admin/utilisateurs?limite=200');
  etat.adminUtilisateurs = liste;
  return `<h2 style="margin-bottom:6px;">Gestion des comptes</h2>
    <p class="desc" style="margin-bottom:14px;">${liste.length} compte(s) enregistré(s).</p>
    <div class="barre-filtre">
      <input type="search" id="filtre-users" placeholder="Rechercher un nom, une adresse, un rôle…"
             oninput="filtrerUtilisateurs(this.value)" aria-label="Rechercher un compte" />
      <select id="filtre-role" onchange="filtrerUtilisateurs()" aria-label="Filtrer par rôle">
        <option value="">Tous les rôles</option>
        ${Object.entries(LIBELLES_ROLES).map(([v, l]) =>
          `<option value="${v}">${echapper(l)}</option>`).join('')}
      </select>
    </div>
    <div id="tableau-users">${tableauUtilisateurs(liste)}</div>`;
}

function tableauUtilisateurs(liste) {
  if (!liste.length) {
    return `<div class="carte"><p class="desc">Aucun compte ne correspond.</p></div>`;
  }
  return `<div class="cadre-tableau"><table class="tableau">
      <thead><tr><th>Nom</th><th>E-mail</th><th>Rôle</th><th>Statut</th><th>Actions</th></tr></thead>
      <tbody>${liste.map(u => `<tr>
        <td><strong>${echapper(u.prenom)} ${echapper(u.nom)}</strong></td>
        <td>${echapper(u.email)}</td>
        <td><span class="badge-role ${u.role==='mentor'?'badge-mentor':''}">${echapper(libelleRole(u.role))}</span></td>
        <td><span class="tag ${u.est_actif?'tag-vert':'tag-rose'}">${u.est_actif?'actif':'suspendu'}</span></td>
        <td>
          ${u.est_actif
            ? `<button class="btn btn-secondaire btn-petit" onclick="adminAction('suspendre',${u.id_utilisateur})">Suspendre</button>`
            : `<button class="btn btn-secondaire btn-petit" onclick="adminAction('reactiver',${u.id_utilisateur})">Réactiver</button>`}
          <button class="btn btn-fantome btn-petit" onclick="adminOuvrirRole(${u.id_utilisateur})">Rôle</button>
          <button class="btn btn-danger btn-petit" onclick="adminAction('supprimer',${u.id_utilisateur})">Supprimer</button>
        </td></tr>`).join('')}</tbody>
    </table></div>`;
}

/* Filtrage dans le navigateur : la liste tient en mémoire, et une
   requête au serveur à chaque frappe n'apporterait rien. */
function filtrerUtilisateurs(terme) {
  const champ = document.getElementById('filtre-users');
  const role = document.getElementById('filtre-role')?.value || '';
  const q = (terme !== undefined ? terme : (champ?.value || '')).trim().toLowerCase();
  const zone = document.getElementById('tableau-users');
  if (!zone) return;

  const filtree = (etat.adminUtilisateurs || []).filter(u => {
    if (role && u.role !== role) return false;
    if (!q) return true;
    return [u.prenom, u.nom, u.email, libelleRole(u.role)]
      .filter(Boolean).join(' ').toLowerCase().includes(q);
  });
  zone.innerHTML = tableauUtilisateurs(filtree);
}

/* Action générique sur un utilisateur (suspendre / réactiver / supprimer). */
async function adminAction(action, idUser) {
  const verbes = {
    suspendre: { url: 'POST', chemin: `/admin/utilisateurs/${idUser}/suspendre`,
                 conf: 'Suspendre ce compte ? La personne ne pourra plus se connecter.' },
    reactiver: { url: 'POST', chemin: `/admin/utilisateurs/${idUser}/reactiver`,
                 conf: 'Réactiver ce compte ?' },
    supprimer: { url: 'DELETE', chemin: `/admin/utilisateurs/${idUser}`,
                 conf: 'Supprimer définitivement ce compte, ses questions et ses réponses ? Cette action est irréversible.' },
  };
  const v = verbes[action]; if (!v) return;
  if (!confirm(v.conf)) return;
  try {
    await (v.url === 'DELETE' ? API.delete(v.chemin) : API.post(v.chemin, {}));
    toast('Action réalisée.');
    changerPanAdmin(document.querySelector('[data-adm=users]'), 'users');
  } catch (err) { toast(err.message, 'erreur'); }
}

/* Le changement de rôle passait par un prompt() où il fallait taper la
   valeur technique sans faute : « super_admin » mal orthographié
   renvoyait une erreur, et rien n'indiquait les valeurs acceptées. */
function adminOuvrirRole(idUser) {
  const u = (etat.adminUtilisateurs || [])
    .find(x => x.id_utilisateur === idUser);
  if (!u) return;

  fermerMentionsLegales();
  const fond = document.createElement('div');
  fond.className = 'modale-fond';
  fond.id = 'modaleLegale';
  fond.setAttribute('role', 'dialog');
  fond.setAttribute('aria-modal', 'true');
  fond.innerHTML = `
    <div class="modale-boite">
      <div class="modale-entete">
        <h2>Rôle de ${echapper(u.prenom + ' ' + u.nom)}</h2>
        <button class="modale-fermer" onclick="fermerMentionsLegales()" aria-label="Fermer">&times;</button>
      </div>
      <div class="modale-corps">
        <div class="champ">
          <label for="choix-role">Nouveau rôle</label>
          <select id="choix-role">
            ${Object.entries(LIBELLES_ROLES).map(([v, l]) =>
              `<option value="${v}"${v === u.role ? ' selected' : ''}>${echapper(l)}</option>`).join('')}
          </select>
        </div>
        <p class="desc">Un administrateur accède à la modération et à la
           gestion des comptes. L'administrateur principal peut en outre
           nommer d'autres administrateurs.</p>
        <button class="btn btn-primaire" onclick="adminValiderRole(${idUser})">Appliquer</button>
      </div>
    </div>`;
  fond.addEventListener('click', (e) => {
    if (e.target === fond) fermerMentionsLegales();
  });
  document.body.appendChild(fond);
  document.body.style.overflow = 'hidden';
}

async function adminValiderRole(idUser) {
  const choix = document.getElementById('choix-role')?.value;
  if (!choix) return;
  try {
    await API.post(`/admin/utilisateurs/${idUser}/role`, { role: choix });
    toast(`Rôle mis à jour : ${libelleRole(choix)}.`);
    fermerMentionsLegales();
    changerPanAdmin(document.querySelector('[data-adm=users]'), 'users');
  } catch (err) { toast(err.message, 'erreur'); }
}

async function adminMentors() {
  const att = await API.get('/admin/mentors-a-verifier');
  majCompteurCandidatures(att.length);
  if (!att.length) {
    return `<h2 style="margin-bottom:18px;">Validation des référents</h2>
      <div class="carte"><p style="color:var(--texte-doux);">
        Aucune candidature en attente.</p></div>`;
  }
  return `<h2 style="margin-bottom:6px;">Validation des référents (${att.length})</h2>
    <p class="desc" style="margin-bottom:18px;">Tant qu'une candidature n'est
       pas validée, la personne n'apparaît pas dans l'annuaire et ne porte
       aucun badge. Vérifiez le parcours annoncé avant de valider.</p>
    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap:14px;">
      ${att.map(m => {
        const init = ((m.prenom||'?')[0] + (m.nom||'?')[0]).toUpperCase();
        const poste = [m.profession, m.organisation].filter(Boolean).join(', ');
        const parcours = [m.niveau_etudes, m.domaine, m.etablissement]
          .filter(Boolean).map(echapper).join(' · ');
        return `<div class="carte"><div style="display:flex; gap:12px; align-items:center;">
          ${avatarHTML(init, 'l')}
          <div><strong>${echapper(m.prenom + ' ' + m.nom)}</strong>
            <div style="color:var(--texte-doux); font-size:13px;">
              ${echapper(m.email || '')}</div>
            <div style="color:var(--texte-doux); font-size:13px;">${echapper((m.ville||'') + (m.pays?', '+m.pays:''))}</div></div>
        </div>
        <dl class="dossier-candidature">
          ${poste ? `<dt>Poste</dt><dd>${echapper(poste)}</dd>` : ''}
          ${m.anciennete ? `<dt>Expérience</dt><dd>${echapper(m.anciennete)}</dd>` : ''}
          ${parcours ? `<dt>Parcours</dt><dd>${parcours}</dd>` : ''}
          ${m.lien_pro ? `<dt>Profil professionnel</dt><dd>
             <a href="${echapper(m.lien_pro)}" target="_blank" rel="noopener noreferrer nofollow">Ouvrir le lien</a></dd>` : ''}
          ${m.depose_le ? `<dt>Déposée le</dt><dd>${echapper(formatHorodatage(m.depose_le))}</dd>` : ''}
        </dl>
        ${m.motivation ? `<div class="bloc-motivation">
            <strong>Motivation</strong>
            <p>${echapper(m.motivation)}</p>
          </div>` : `<p class="desc" style="margin:12px 0;">Aucune motivation
            enregistrée : candidature déposée avant la conservation des
            dossiers. Demandez-la avant de valider.</p>`}
        <p style="margin:12px 0; font-size:14px;">${echapper(m.bio || 'Pas de présentation.')}</p>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-primaire btn-petit" onclick="adminMentorAction('verifier',${m.id_utilisateur})">${ic('check','ic ic-s')} Valider</button>
          <button class="btn btn-danger btn-petit" onclick="adminMentorAction('refuser',${m.id_utilisateur})">${ic('croix','ic ic-s')} Refuser</button>
        </div></div>`;
      }).join('')}
    </div>`;
}

/* Compteur sur l'entrée de menu : une candidature qui attend doit se
   voir sans avoir à ouvrir l'onglet pour la découvrir. */
function majCompteurCandidatures(n) {
  const p = document.getElementById('compteur-candidatures');
  if (!p) return;
  p.textContent = n > 99 ? '99+' : String(n);
  p.hidden = !n;
}

async function chargerCompteurCandidatures() {
  if (!etat.utilisateur || !etat.utilisateur.estAdmin) return;
  try {
    majCompteurCandidatures(
      (await API.get('/admin/mentors-a-verifier') || []).length);
  } catch (_) { /* le compteur n'est pas essentiel */ }
}

async function adminMentorAction(action, idMentor) {
  const conf = action === 'verifier' ? 'Valider ce référent ?' : 'Refuser ce référent (revenir au compte bénéficiaire) ?';
  if (!confirm(conf)) return;
  try {
    await API.post(`/admin/mentors/${idMentor}/${action}`, {});
    toast(action === 'verifier' ? 'Référent validé.' : 'Référent refusé.');
    changerPanAdmin(document.querySelector('[data-adm=mentors]'), 'mentors');
  } catch (err) { toast(err.message, 'erreur'); }
}
/* Six décisions plutôt que deux. « Traité » ne disait pas si le contenu
   avait été retiré, l'auteur averti, ou rien du tout : la même étiquette
   couvrait le classement sans suite et la suppression. */
const DECISIONS_SIGNALEMENT = [
  { cle: 'rejeter', libelle: 'Non fondé', classe: 'btn-fantome',
    aide: 'Le contenu reste en place, rien n\'est reproché à son auteur.' },
  { cle: 'classer', libelle: 'Sans suite', classe: 'btn-secondaire',
    aide: 'Examiné, jugé acceptable. Le signalement est clos.' },
  { cle: 'avertir', libelle: 'Avertir', classe: 'btn-secondaire',
    aide: 'Le contenu reste, son auteur reçoit un avertissement.' },
  { cle: 'supprimer', libelle: 'Supprimer', classe: 'btn-danger',
    aide: 'Le contenu est retiré, sans avertissement.' },
  { cle: 'supprimer_avertir', libelle: 'Supprimer et avertir',
    classe: 'btn-danger',
    aide: 'Le contenu est retiré et son auteur en est informé.' },
  { cle: 'suspendre', libelle: 'Suspendre le compte', classe: 'btn-danger',
    aide: 'L\'auteur ne peut plus se connecter. À réserver aux récidives.' },
];

let _filtreSignalements = 'ouvert';

async function adminSignalements(statut) {
  if (!MODE.api) return `<div class="carte"><p style="color:var(--texte-doux);">Ce module est disponible lorsque le serveur LaSourcee est connecté.</p></div>`;
  if (statut) _filtreSignalements = statut;
  const liste = await API.get('/admin/signalements?statut=' + _filtreSignalements);

  const onglets = [['ouvert', 'En attente'], ['traite', 'Traités'],
                   ['rejete', 'Rejetés'], ['tous', 'Tous']];
  const entete = `<h2 style="margin-bottom:6px;">Modération</h2>
    <p class="desc" style="margin-bottom:14px;">Chaque décision est tracée,
       notifiée à l'auteur quand elle le concerne, et confirmée à la
       personne qui a signalé.</p>
    <div class="onglets onglets-scroll" style="margin-bottom:16px;">
      ${onglets.map(([c, l]) => `<div class="onglet ${c === _filtreSignalements ? 'actif' : ''}"
        onclick="rechargerSignalements('${c}')">${l}</div>`).join('')}
    </div>`;

  if (!liste.length) {
    return entete + `<div class="carte"><p style="color:var(--texte-doux);">
      Aucun signalement dans cette catégorie.</p></div>`;
  }
  return entete + liste.map(carteSignalement).join('');
}

function carteSignalement(s) {
  const c = s.contenu || {};
  const traite = s.statut !== 'ouvert';
  const date = s.cree_le
    ? formatHorodatage(s.cree_le)
    : '';

  // Le contenu incriminé, cité. Sans lui, décider revient à croire le
  // signaleur sur parole ou à tout rejeter.
  const extrait = c.supprime
    ? `<p class="contenu-absent">Ce contenu n'existe plus : il a été
         supprimé depuis le signalement.</p>`
    : `<blockquote class="contenu-signale">
         ${c.titre ? `<strong>${echapper(c.titre)}</strong>` : ''}
         <p>${echapper((c.texte || '').slice(0, 600))}${
             (c.texte || '').length > 600 ? '…' : ''}</p>
       </blockquote>`;

  const auteur = c.id_auteur
    ? `<span>Publié par <strong>${echapper((c.prenom || '') + ' ' + (c.nom || ''))}</strong>${
        c.est_actif === 0 ? ' <span class="tag tag-suspendu">compte suspendu</span>' : ''}</span>`
    : '';

  return `<div class="carte carte-signalement ${traite ? 'est-traite' : ''}">
    <div class="signalement-entete">
      <div>
        <span class="tag">${echapper(s.type_contenu)}</span>
        ${s.signalements_contenu > 1
          ? `<span class="tag tag-alerte">${s.signalements_contenu} signalements
             sur ce contenu</span>` : ''}
        ${c.signalements_auteur > 2
          ? `<span class="tag tag-alerte">auteur déjà signalé
             ${c.signalements_auteur} fois</span>` : ''}
      </div>
      <span class="desc">#${s.id_signalement} · ${date}</span>
    </div>

    <div class="signalement-motif">
      <strong>Motif invoqué</strong>
      <p>« ${echapper(s.motif || 'Aucun motif précisé')} »</p>
      <span class="desc">Signalé par ${echapper(s.prenom + ' ' + s.nom)}
        (${echapper(s.email || '')})</span>
    </div>

    ${extrait}
    <div class="signalement-auteur">${auteur}</div>

    ${traite
      ? `<div class="signalement-decision">Décision : <strong>${
           echapper(libelleAction(s.action) || s.statut)}</strong>${
           s.admin_prenom ? ` par ${echapper(s.admin_prenom + ' ' + s.admin_nom)}` : ''}${
           s.traite_le ? ` le ${echapper(formatHorodatage(s.traite_le))}` : ''}</div>`
      : `<div class="signalement-actions">
          ${DECISIONS_SIGNALEMENT.map(d => `<button
             class="btn ${d.classe} btn-petit" title="${echapper(d.aide)}"
             onclick="adminSignalementAction(${s.id_signalement}, '${d.cle}')"
             >${echapper(d.libelle)}</button>`).join('')}
        </div>`}
  </div>`;
}

function libelleAction(cle) {
  const d = DECISIONS_SIGNALEMENT.find(x => x.cle === cle);
  return d ? d.libelle : '';
}

async function rechargerSignalements(statut) {
  const c = document.getElementById('contenu-admin');
  if (c) c.innerHTML = await adminSignalements(statut);
}

async function adminSignalementAction(idSig, action) {
  const d = DECISIONS_SIGNALEMENT.find(x => x.cle === action);
  if (!d) return;
  // Les décisions irréversibles se confirment, et laissent la place à
  // une note : « supprimé » sans motif ne s'explique pas six mois après.
  let note = '';
  if (['supprimer', 'supprimer_avertir', 'suspendre'].includes(action)) {
    note = prompt(`${d.libelle} : ${d.aide}\n\n`
      + 'Motif (transmis à l\'auteur et conservé au journal) :', '');
    if (note === null) return;
  }
  try {
    const r = await API.post(`/admin/signalements/${idSig}`, { action, note });
    toast(r.libelle || 'Signalement traité.');
    rechargerSignalements();
  } catch (err) { toast(err.message, 'erreur'); }
}
async function adminCategories() {
  if (!MODE.api) return `<div class="carte"><p style="color:var(--texte-doux);">Ce module est disponible lorsque le serveur LaSourcee est connecté.</p></div>`;
  const liste = await API.get('/admin/secteurs');
  return `<h2 style="margin-bottom:18px;">Catégories (${liste.length})</h2>
    <div class="carte">
      <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px;">
        ${liste.map(s => `
          <span class="tag" style="display:inline-flex; align-items:center; gap:6px;">
            ${echapper(s.libelle)}
            <span style="cursor:pointer; font-weight:700;" onclick="supprimerCat(${s.id_secteur},'${echapper(s.libelle)}')">×</span>
          </span>`).join('')}
      </div>
      <div style="display:flex; gap:8px;">
        <input id="nouv-cat" placeholder="Nouvelle catégorie…" maxlength="80" />
        <button class="btn btn-primaire" onclick="ajouterCat()">Ajouter</button>
      </div>
    </div>`;
}
async function supprimerCat(id, nom) {
  if (!confirm(`Supprimer la catégorie « ${nom} » ?`)) return;
  try {
    await API.delete(`/admin/secteurs/${id}`);
    toast('Catégorie supprimée.');
    changerPanAdmin(document.querySelector('[data-adm=categories]'), 'categories');
  } catch (err) { toast(err.message, 'erreur'); }
}
async function ajouterCat() {
  const v = (document.getElementById('nouv-cat')?.value || '').trim();
  if (!v) return toast('Saisissez un nom.', 'erreur');
  try {
    await API.post('/admin/secteurs', { libelle: v });
    toast(`Catégorie « ${v} » ajoutée.`);
    changerPanAdmin(document.querySelector('[data-adm=categories]'), 'categories');
  } catch (err) { toast(err.message, 'erreur'); }
}

async function adminAudit() {
  if (!MODE.api) return `<div class="carte"><p style="color:var(--texte-doux);">Ce module est disponible lorsque le serveur LaSourcee est connecté.</p></div>`;
  const liste = await API.get('/admin/audit?limite=50');
  if (!liste.length) {
    return `<h2 style="margin-bottom:18px;">Journal d'audit</h2>
      <div class="carte"><p style="color:var(--texte-doux);">Aucune action enregistrée.</p></div>`;
  }
  return `<h2 style="margin-bottom:18px;">Journal d'audit (${liste.length} dernières actions)</h2>
    <div class="cadre-tableau"><table class="tableau">
      <thead><tr><th>Date</th><th>Acteur</th><th>Action</th><th>Cible</th><th>Détails</th></tr></thead>
      <tbody>${liste.map(a => `<tr>
        <td class="horodatage">${formatHorodatage(a.cree_le, true)}</td>
        <td>${echapper(a.prenom + ' ' + a.nom)}</td>
        <td><span class="tag">${echapper(a.action)}</span></td>
        <td>${a.type_cible ? echapper(a.type_cible) + ' #' + a.id_cible : '·'}</td>
        <td style="font-size:12px; color:var(--texte-doux);">${echapper(a.details || '')}</td>
      </tr>`).join('')}</tbody>
    </table></div>`;
}

/* ============================================================
   TOASTS
   ============================================================ */
function toast(message, type = 'succes') {
  const zone = document.getElementById('zoneToasts');
  const t = document.createElement('div');
  t.className = 'toast' + (type === 'erreur' ? ' erreur' : '');
  // L'icone est du balisage choisi ici, le message ne l'est pas : il
  // contient souvent un nom, un titre de question ou une erreur venue
  // du serveur. Insere en innerHTML, il executait le balisage qu'on y
  // avait glisse. Il passe donc par textContent, qui affiche le texte
  // sans jamais l'interpreter.
  const icone = document.createElement('span');
  icone.className = 'toast-ic';
  icone.innerHTML = type === 'erreur' ? ic('alerte', 'ic ic-s')
                                      : ic('check', 'ic ic-s');
  const texte = document.createElement('span');
  texte.textContent = message == null ? '' : String(message);
  t.append(icone, texte);
  zone.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; }, 3000);
  setTimeout(() => t.remove(), 3400);
}

/* ============================================================
   FERMETURES CLIC EXTÉRIEUR
   ============================================================ */
document.addEventListener('click', (e) => {
  if (!e.target.closest('.nav-profil') && !e.target.closest('.menu-profil'))
    document.getElementById('menuProfil')?.classList.remove('ouvert');
  if (!e.target.closest('[onclick*="basculerNotifs"]') && !e.target.closest('.panneau-notifs'))
    document.getElementById('panneauNotifs')?.classList.remove('ouvert');
  if (!e.target.closest('.nav-recherche'))
    document.getElementById('dropRech')?.classList.remove('ouvert');
});

/* ============================================================
   DÉMARRAGE
   ============================================================ */
/* Messages rapportés par un retour de connexion externe.
   LinkedIn ramène le visiteur sur l'accueil avec ?erreur=... : sans
   cette lecture, l'échec serait totalement silencieux et la personne
   croirait s'être connectée. */
const MESSAGES_RETOUR = {
  linkedin_adresse_non_verifiee:
    "LinkedIn n'a pas confirmé votre adresse e-mail. Validez-la dans "
    + "votre compte LinkedIn, puis réessayez, ou créez un compte avec "
    + 'un mot de passe.',
  linkedin_profil_incomplet:
    "LinkedIn n'a pas transmis votre adresse e-mail. Autorisez le "
    + 'partage de l\'adresse, ou créez un compte avec un mot de passe.',
  linkedin: 'La connexion LinkedIn a échoué. Réessayez dans un instant.',
  access_denied: 'Connexion annulée.',
};

function traiterRetourExterne() {
  const params = new URLSearchParams(window.location.search);
  const erreur = params.get('erreur');
  const connexion = params.get('connexion');
  if (!erreur && !connexion) return;

  if (erreur) {
    toast(MESSAGES_RETOUR[erreur] || 'La connexion externe a échoué.',
          'erreur');
  } else if (connexion) {
    toast('Connexion réussie. Bienvenue !');
  }

  // Nettoie l'adresse : le paramètre ne doit pas survivre à un
  // rechargement ni se retrouver dans un lien partagé.
  const propre = window.location.pathname + window.location.hash;
  window.history.replaceState({}, '', propre);
}

window.addEventListener('DOMContentLoaded', async () => {
  // Bannière cookies (affichée tant qu'aucun choix n'a été fait)
  initialiserCookies();
  traiterRetourExterne();
  chargerAccueil();

  // Contacte le serveur et charge la session courante
  await initialiserApi();
  if (!MODE.api) afficherServeurIndisponible();

  // Charge la configuration OAuth publique (Client ID Google + flag LinkedIn)
  try {
    const cfg = MODE.api ? await API.get('/auth/config')
                         : { google_client_id: '', linkedin_configure: false };
    window.GOOGLE_CLIENT_ID = cfg.google_client_id || null;
    window.LINKEDIN_CONFIGURE = !!cfg.linkedin_configure;
    // Par défaut on suppose l'envoi actif : en cas de doute, mieux vaut
    // le message habituel qu'une alerte alarmante à tort.
    window.ENVOI_EMAIL_ACTIF = cfg.envoi_email_actif !== false;
    majRappelConfirmation();
    // Masquer les boutons sociaux si non configurés (UX honnête)
    document.querySelectorAll('.btn-social').forEach(btn => {
      const t = btn.textContent;
      if (t.includes('Google') && !window.GOOGLE_CLIENT_ID) btn.style.display = 'none';
      if (t.includes('LinkedIn') && !window.LINKEDIN_CONFIGURE) btn.style.display = 'none';
    });
    if (!window.GOOGLE_CLIENT_ID && !window.LINKEDIN_CONFIGURE) {
      document.querySelectorAll('.sep-ou').forEach(s => s.style.display = 'none');
    }
  } catch (_) { /* tolérance */ }

  // Hors du bloc précédent, et sans condition : le thème est posé par le
  // script du <head>, avant que les lignes de menu existent. Placée dans
  // un try qui dépend du réseau, cette synchronisation aurait été sautée
  // dès que la configuration ne répond pas, et les menus auraient
  // annoncé « Clair » sur un site affiché en sombre.
  appliquerTheme(themeActuel());

  // Une session valide ramène dans l'application, jamais sur la page de
  // bienvenue. Auparavant il fallait que l'adresse porte exactement
  // « #app » : toute actualisation renvoyait donc un membre connecté sur
  // la vitrine, alors que sa session était intacte côté serveur.
  if (MODE.utilisateur) {
    appliquerUtilisateur(MODE.utilisateur);
    afficherVue('vue-app');
    initApp();
    // On rouvre la section quittée, si l'adresse en désigne une.
    const section = (window.location.hash || '').replace('#', '');
    // Liste alignée sur les sous-vues réellement présentes dans la page.
    const connues = ['fil', 'profil', 'question', 'parametres', 'admin',
                     'messages',
                     'mentor'];
    if (connues.includes(section) && section !== etat.sectionActive) {
      naviguerApp(section);
    }
  } else {
    afficherVue('vue-accueil');
  }

  // Le voile ne se lève qu'ici : la bonne vue est en place, rien ne
  // défilera devant les yeux du visiteur.
  document.body.classList.remove('demarrage');
});

/* Sécurité : si l'initialisation échoue avant d'avoir levé le voile,
   la page resterait blanche. Au bout de six secondes, on l'affiche
   quoi qu'il arrive. */
setTimeout(() => document.body.classList.remove('demarrage'), 6000);

/* ----- Consentement cookies ----- */
function initialiserCookies() {
  const choix = localStorage.getItem('lasource_cookies');
  const banniere = document.getElementById('cookieBanniere');
  if (!banniere) return;
  if (choix) banniere.classList.add('cache');
  else banniere.classList.remove('cache');
}
function repondreCookies(accepte) {
  localStorage.setItem('lasource_cookies', accepte ? 'accepte' : 'refuse');
  document.getElementById('cookieBanniere')?.classList.add('cache');
  toast(accepte ? 'Préférences enregistrées. Merci !' : 'Seuls les cookies essentiels seront utilisés.');
}


/* ============================================================
   UI : bouton oeil (afficher/masquer mot de passe) + menus burger
   ============================================================ */
function basculerOeil(btn) {
  const wrap = btn.closest('.champ-mdp');
  if (!wrap) return;
  const input = wrap.querySelector('input');
  if (!input) return;
  const affiche = input.type === 'password';
  input.type = affiche ? 'text' : 'password';
  const ouvert = btn.querySelector('.oeil-ouvert');
  const ferme = btn.querySelector('.oeil-ferme');
  if (ouvert && ferme) {
    ouvert.style.display = affiche ? 'none' : '';
    ferme.style.display  = affiche ? '' : 'none';
  }
  btn.setAttribute('aria-label', affiche ? 'Masquer le mot de passe' : 'Afficher le mot de passe');
}
function basculerBurgerHero() {
  const a = document.getElementById('actionsHero');
  const b = document.getElementById('burgerHero');
  if (!a) return;
  a.classList.toggle('ouvert');
  if (b) b.classList.toggle('actif');
}
function basculerBurgerApp() {
  const m = document.getElementById('menuBurgerApp');
  const b = document.getElementById('burgerApp');
  if (!m) return;
  m.classList.toggle('ouvert');
  if (b) b.classList.toggle('actif');
}
function fermerBurgerApp() {
  const m = document.getElementById('menuBurgerApp');
  const b = document.getElementById('burgerApp');
  if (m) m.classList.remove('ouvert');
  if (b) b.classList.remove('actif');
}

/* ============================================================
   DIAGNOSTIC DE CONFIGURATION (administrateurs)
   ------------------------------------------------------------
   Les variables d'environnement d'un hébergement serverless ne sont
   lisibles que depuis son tableau de bord — et celles enregistrées
   comme « secret » n'y sont plus consultables du tout. Ce panneau
   montre ce que le serveur a réellement reçu, sans exposer la moindre
   valeur secrète.
   ============================================================ */

/* Variante « www » d'une adresse. Google compare les origines au
   caractere pres : declarer lasourcee.org sans www.lasourcee.org fait
   echouer la connexion depuis l'une des deux, sans message clair. */
function _avecWww(adresse) {
  if (!adresse) return '';
  try {
    const u = new URL(adresse);
    if (u.hostname.startsWith('www.')) {
      u.hostname = u.hostname.slice(4);
    } else {
      u.hostname = 'www.' + u.hostname;
    }
    return u.origin;
  } catch (_) { return adresse; }
}

function _ligneDiag(libelle, ok, detail, conseil) {
  const etat = ok
    ? '<span class="tag tag-vert">OK</span>'
    : '<span class="tag tag-rose">À corriger</span>';
  return `<div class="ligne-session">
    <div style="flex:1;">
      <strong>${echapper(libelle)}</strong>
      ${detail ? `<div class="desc">${echapper(detail)}</div>` : ''}
      ${!ok && conseil ? `<div class="desc" style="color:var(--rouge-fonce);">${echapper(conseil)}</div>` : ''}
    </div>
    ${etat}
  </div>`;
}

async function adminDiagnostic() {
  let d;
  try {
    d = await API.get('/admin/diagnostic');
  } catch (err) {
    return `<h2 style="margin-bottom:18px;">Diagnostic</h2>
      <div class="carte"><p style="color:var(--rouge-fonce);">
        ${echapper(err.message || 'Diagnostic indisponible.')}</p></div>`;
  }

  const bloquantes = (d.anomalies || []).filter(a => a.gravite === 'bloquant');
  const alertes = (d.anomalies || []).filter(a => a.gravite !== 'bloquant');

  return `<h2 style="margin-bottom:6px;">Diagnostic</h2>
    <p class="desc" style="margin-bottom:18px;">
      Ce que le serveur a réellement reçu. Aucune valeur secrète n'est
      affichée : mots de passe et secrets n'apparaissent jamais, seulement
      le fait qu'ils soient renseignés.</p>

    ${bloquantes.length ? `<div class="bandeau-alerte" role="alert">
      <strong>${bloquantes.length} point(s) bloquant(s).</strong>
      <ul style="margin:8px 0 0 18px;">
        ${bloquantes.map(a => `<li>${echapper(a.message)}</li>`).join('')}
      </ul></div>` : ''}

    ${alertes.length ? `<div class="carte" style="margin-bottom:14px;">
      <strong>Avertissements</strong>
      <ul style="margin:8px 0 0 18px; color:var(--texte-doux); font-size:13px;">
        ${alertes.map(a => `<li>${echapper(a.message)}</li>`).join('')}
      </ul></div>` : ''}

    <div class="carte" style="margin-bottom:14px;">
      <h3 class="titre-param">Base de données</h3>
      ${_ligneDiag('Moteur', d.base.moteur === 'postgres',
                   `${d.base.moteur} · ${d.base.comptes} compte(s), `
                   + `${d.base.administrateurs} administrateur(s)`,
                   'Sur cet hébergement, seul PostgreSQL conserve les données.')}
    </div>

    <div class="carte" style="margin-bottom:14px;">
      <h3 class="titre-param">Envoi des e-mails</h3>
      ${_ligneDiag('Configuration SMTP', d.email.operationnel,
                   d.email.motif,
                   'Sans SMTP, ni confirmation d\'inscription ni '
                   + 'réinitialisation de mot de passe ne partent.')}
      ${_ligneDiag('Un message peut réellement partir', d.email.envoi_effectif,
                   d.email.envoi_effectif ? '' :
                     'Aucune confirmation n\'atteint sa destinataire : '
                     + 'les liens ne sont écrits que dans les journaux.')}
      ${d.email.expediteur ? _ligneDiag('Expéditeur', true, d.email.expediteur) : ''}
      <div class="desc" style="margin-top:10px; line-height:1.7;">
        <strong>Ce que le serveur a lu</strong> (après nettoyage des valeurs) :<br />
        EMAIL_MODE : <code>${echapper(d.email.mode || '(vide)')}</code><br />
        Hôte : <code>${echapper(d.email.hote || '(vide)')}</code>
        &nbsp;Port : <code>${echapper(String(d.email.port ?? ''))}</code>
        &nbsp;Sécurité : <code>${echapper(d.email.securite || '')}</code><br />
        Utilisateur : <code>${echapper(d.email.utilisateur || '(vide)')}</code><br />
        Mot de passe : <code>${d.email.motdepasse_fourni ? 'fourni' : 'absent'}</code>
        &nbsp;Délai : <code>${echapper(String(d.email.delai_secondes ?? ''))} s</code>
      </div>
      <p class="aide-champ">Le port 465 va avec « ssl », le port 587 avec
        « starttls ». Ces valeurs sont celles réellement utilisées, pas
        celles saisies : un écart signale une variable mal orthographiée.</p>
      ${_ligneDiag('Confirmation d\'adresse exigée',
                   d.email.confirmation_obligatoire,
                   d.email.confirmation_obligatoire
                     ? 'Un compte doit confirmer son adresse avant de se connecter.'
                     : 'Un compte est utilisable sans confirmer son adresse.',
                   'S\'active d\'elle-même dès que l\'envoi SMTP fonctionne.')}
      <button class="btn btn-secondaire btn-petit" style="margin-top:10px;"
              onclick="testerEnvoiEmail(this)">M'envoyer un message d'essai</button>
      <div id="resultat-test-email" class="desc" style="margin-top:8px;"></div>
    </div>

    <div class="carte" style="margin-bottom:14px;">
      <h3 class="titre-param">Connexion Google</h3>
      ${_ligneDiag('Identifiant client renseigné', d.google.configure, '',
                   'Sans lui, le bouton Google reste masqué.')}
      ${d.google.configure ? _ligneDiag(
          'Forme de l\'identifiant', d.google.forme_valide,
          d.google.valeur,
          'Un identifiant client se termine par '
          + '« .apps.googleusercontent.com ». Une autre valeur, le secret '
          + 'client par exemple, provoque « invalid_client ».') : ''}
      <div class="desc" style="margin-top:8px;">
        <strong>Origines JavaScript à déclarer</strong> dans la console
        Google Cloud, sous « Identifiants → votre ID client OAuth » :
        <ul class="liste-origines">
          <li><code>${echapper(d.adresse_publique)}</code></li>
          <li><code>${echapper(_avecWww(d.adresse_publique))}</code></li>
        </ul>
        Les deux formes, avec et sans <code>www</code> : Google compare
        l'origine au caractère près, et une seule des deux déclarée fait
        échouer la connexion depuis l'autre. Sans port, sans barre
        oblique finale, sans chemin.
      </div>
    </div>

    <div class="carte">
      <h3 class="titre-param">Divers</h3>
      ${_ligneDiag('Clé de signature fournie', d.cle_signature_fournie, '',
                   'Sans SECRET_KEY fixe, la connexion LinkedIn échoue par intermittence.')}
      ${_ligneDiag('Adresse publique', !!d.adresse_publique, d.adresse_publique)}
      ${_ligneDiag('Environnement', d.environnement === 'production', d.environnement)}
    </div>`;
}

async function testerEnvoiEmail(bouton) {
  const zone = document.getElementById('resultat-test-email');
  bouton.disabled = true;
  const libelle = bouton.textContent;
  bouton.textContent = 'Envoi…';
  try {
    const r = await API.post('/admin/diagnostic/test-email');
    if (r.envoye) {
      zone.style.color = 'var(--vert)';
      zone.textContent = `Message envoyé à ${r.destinataire}. `
        + 'Vérifiez votre boîte, et le dossier des indésirables.';
    } else {
      zone.style.color = 'var(--rouge-fonce)';
      zone.textContent = r.motif || "L'envoi a échoué.";
    }
  } catch (err) {
    zone.style.color = 'var(--rouge-fonce)';
    zone.textContent = err.message || 'Test impossible.';
  } finally {
    bouton.disabled = false;
    bouton.textContent = libelle;
  }
}

/* ============================================================
   PAGE D'ACCUEIL : CHIFFRES ET QUESTIONS RÉELS
   ------------------------------------------------------------
   La page annonçait « +12 000 membres » et trois questions écrites en
   dur, sans rapport avec la base. Sur un site public, des chiffres
   inventés engagent la crédibilité du projet : quelqu'un qui s'inscrit
   après les avoir lus découvre autre chose.
   ============================================================ */

function _formaterNombre(n) {
  return Number(n || 0).toLocaleString('fr-FR');
}

async function chargerAccueil() {
  await Promise.all([chargerStatistiques(), chargerQuestionsAccueil()]);
}

async function chargerStatistiques() {
  const cases = {
    membres: document.getElementById('stat-membres'),
    questions: document.getElementById('stat-questions'),
    reponses: document.getElementById('stat-reponses'),
  };
  if (!cases.membres) return;

  let s;
  try {
    s = await API.get('/profil/statistiques');
  } catch {
    // Serveur injoignable : on retire le bloc plutôt que d'afficher des
    // tirets, qui laisseraient croire à une communauté vide.
    const bloc = document.querySelector('.hero-stats-wrap');
    if (bloc) bloc.style.display = 'none';
    return;
  }

  cases.membres.textContent = _formaterNombre(s.membres);
  cases.questions.textContent = _formaterNombre(s.questions);
  cases.reponses.textContent = _formaterNombre(s.reponses);

  // Une plateforme qui vient d'ouvrir affiche forcément de petits
  // nombres. Les présenter comme « une communauté grandissante »
  // sonnerait faux ; mieux vaut assumer le démarrage, c'est même un
  // argument pour rejoindre les premiers.
  const titre = document.querySelector('.hero-stats-titre');
  if (titre && (s.membres || 0) < 25) {
    titre.textContent = 'Les premiers membres construisent déjà la suite';
  }
}

async function chargerQuestionsAccueil() {
  const zone = document.getElementById('hero-questions');
  if (!zone) return;

  let questions = [];
  try {
    // Route publique : le fil complet exige une session, mais la page
    // d'accueil s'adresse d'abord à des visiteurs non connectés.
    questions = await API.get('/questions/vedette');
  } catch {
    questions = [];
  }

  if (!Array.isArray(questions) || !questions.length) {
    zone.innerHTML = `<p class="hero-vide">
      Aucune question pour l'instant. La première pourrait être la vôtre.
    </p>`;
    return;
  }

  // « aucune réponse » sur trois questions d'affilée donne l'image d'un
  // site désert. Une question sans réponse est présentée pour ce qu'elle
  // est : une occasion d'être le premier à répondre.
  zone.innerHTML = questions.map(q => {
    const auteur = q.auteur || 'Membre';
    const nb = q.nb_reponses || 0;
    const etiquette = nb === 0
      ? '<span class="mini-q-appel">Sans réponse pour l\'instant</span>'
      : `<span class="mini-q-nb">${nb} réponse${nb > 1 ? 's' : ''}</span>`;
    return `<div class="mini-q">
      <strong>${echapper(q.titre || '')}</strong>
      <p><span class="mini-q-auteur">${echapper(auteur)}</span> ${etiquette}</p>
    </div>`;
  }).join('');
}

/* ============================================================
   THÈME CLAIR ET SOMBRE
   ------------------------------------------------------------
   Le thème initial est posé par un script en tête de page, avant le
   premier rendu. Ici on gère seulement la bascule manuelle et sa
   mémorisation.
   ============================================================ */

function themeActuel() {
  return document.documentElement.getAttribute('data-theme') === 'dark'
    ? 'dark' : 'light';
}

function appliquerTheme(theme) {
  if (theme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  // La barre d'adresse des navigateurs mobiles suit cette couleur.
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', theme === 'dark' ? '#0B1220' : '#1E3A8A');
  // Les lignes de menu annoncent le thème en cours, pas celui qu'on
  // obtiendrait : un libellé qui décrit l'état se lit sans hésiter,
  // alors qu'un libellé d'action laisse toujours douter du sens.
  // Il y en a une par menu, celui de l'accueil et celui de
  // l'application : les deux se mettent à jour ensemble.
  document.querySelectorAll('.ligne-theme-etat').forEach(el => {
    el.textContent = (theme === 'dark') ? 'Sombre' : 'Clair';
  });
}

function basculerTheme() {
  const nouveau = themeActuel() === 'dark' ? 'light' : 'dark';
  appliquerTheme(nouveau);
  try {
    // Le choix explicite prime désormais sur la préférence du système.
    localStorage.setItem('lasourcee-theme', nouveau);
  } catch (e) { /* stockage refusé : le choix vaut pour cette visite */ }
}

/* Tant que rien n'a été choisi, la plateforme suit le système : passer
   son téléphone en mode nuit bascule le site aussi. */
if (window.matchMedia) {
  window.matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', (e) => {
      let choix = null;
      try { choix = localStorage.getItem('lasourcee-theme'); } catch (_) {}
      if (!choix) appliquerTheme(e.matches ? 'dark' : 'light');
    });
}

/* ============================================================
   MENTIONS LÉGALES ET CONDITIONS
   ------------------------------------------------------------
   Un site public qui collecte des comptes et des adresses e-mail doit
   dire qui l'édite, ce qu'il conserve et pendant combien de temps.
   Les textes sont volontairement courts et concrets : personne ne lit
   trois pages de formules, et un texte que personne ne lit ne protège
   personne.
   ============================================================ */

const TEXTES_LEGAUX = {
  confidentialite: {
    titre: 'Confidentialité',
    contenu: `
      <p><strong>Ce que nous collectons.</strong> Votre prénom, votre nom,
      votre adresse e-mail, et ce que vous choisissez d'ajouter à votre
      profil : présentation, pays, domaines. Rien d'autre.</p>

      <p><strong>Pourquoi.</strong> L'adresse sert à vous connecter, à
      confirmer votre inscription et à réinitialiser votre mot de passe.
      Elle n'est jamais affichée aux autres membres, ni vendue, ni
      transmise à des tiers.</p>

      <p><strong>Cookies.</strong> Un seul est déposé, celui de votre
      session. Aucun traceur publicitaire, aucune mesure d'audience
      externe.</p>

      <p><strong>Vos publications.</strong> Questions et réponses sont
      visibles des autres membres : c'est ce qui permet à chacun d'en
      profiter. Vous pouvez supprimer les vôtres à tout moment.</p>

      <p><strong>Vos droits.</strong> Vous pouvez à tout moment
      télécharger vos données et supprimer votre compte depuis
      Paramètres, Confidentialité. Pour toute autre demande, écrivez à
      <a href="mailto:djorod@lasourcee.org">djorod@lasourcee.org</a>
      ou appelez le <a href="tel:+2290155040432">+229 01 55 04 04 32</a>.</p>

      <p><strong>Sécurité.</strong> Les mots de passe sont hachés, jamais
      stockés en clair. Les échanges passent par une connexion chiffrée.
      Vous pouvez consulter et déconnecter vos appareils depuis
      Paramètres, Sécurité.</p>`,
  },
  conditions: {
    titre: "Conditions d'utilisation",
    contenu: `
      <p><strong>Ce qu'est LaSourcee.</strong> Un espace où des personnes
      posent des questions d'orientation, de carrière ou d'argent, et où
      d'autres partagent leur expérience.</p>

      <p><strong>Ce qui est attendu.</strong> Des échanges respectueux,
      des informations exactes, et un profil qui vous corresponde
      réellement. Un compte créé au nom de quelqu'un d'autre est
      supprimé.</p>

      <p><strong>Ce qui n'est pas accepté.</strong> Les propos haineux ou
      discriminatoires, le harcèlement, la publicité, et la diffusion de
      données personnelles d'autrui. Tout contenu peut être signalé, et
      les comptes concernés suspendus.</p>

      <p><strong>La portée des conseils.</strong> Les réponses publiées
      sont des témoignages et des avis personnels. Elles ne remplacent ni
      un conseil professionnel, ni un accompagnement juridique, médical
      ou financier.</p>

      <p><strong>Votre compte.</strong> Vous êtes responsable de la
      confidentialité de votre mot de passe. Vous pouvez fermer votre
      compte quand vous le souhaitez.</p>`,
  },
  mentions: {
    titre: 'Mentions légales',
    contenu: `
      <p><strong>Éditeur.</strong> LaSourcee, plateforme de mentorat.
      Contact :
      <a href="mailto:djorod@lasourcee.org">djorod@lasourcee.org</a></p>

      <p><strong>Conception et développement.</strong> Coding_DJOROD,
      2026.</p>

      <p><strong>Hébergement.</strong> Le site est hébergé par Vercel
      Inc., et les données sont conservées sur une base PostgreSQL
      gérée.</p>

      <p><strong>Propriété.</strong> Le nom LaSourcee, le logo et
      l'habillage du site appartiennent à leurs auteurs. Les questions
      et réponses restent la propriété de leurs auteurs respectifs, qui
      en autorisent l'affichage sur la plateforme.</p>

      <p><strong>Signalement.</strong> Pour signaler un contenu ou une
      difficulté, écrivez à
      <a href="mailto:djorod@lasourcee.org">djorod@lasourcee.org</a>.</p>

      <p><strong>Nous joindre.</strong><br>
      Courriel : <a href="mailto:djorod@lasourcee.org">djorod@lasourcee.org</a><br>
      Téléphone : <a href="tel:+2290155040432">+229 01 55 04 04 32</a>
      ou <a href="tel:+2290153581795">+229 01 53 58 17 95</a></p>`,
  },
};

function ouvrirMentionsLegales(cle) {
  const doc = TEXTES_LEGAUX[cle];
  if (!doc) return;

  fermerMentionsLegales();
  const fond = document.createElement('div');
  fond.className = 'modale-fond';
  fond.id = 'modaleLegale';
  fond.setAttribute('role', 'dialog');
  fond.setAttribute('aria-modal', 'true');
  fond.setAttribute('aria-label', doc.titre);
  fond.innerHTML = `
    <div class="modale-boite">
      <div class="modale-entete">
        <h2>${echapper(doc.titre)}</h2>
        <button class="modale-fermer" onclick="fermerMentionsLegales()"
                aria-label="Fermer">&times;</button>
      </div>
      <div class="modale-corps">${doc.contenu}</div>
    </div>`;

  // Un clic hors de la boîte referme, comme partout ailleurs.
  fond.addEventListener('click', (e) => {
    if (e.target === fond) fermerMentionsLegales();
  });
  document.body.appendChild(fond);
  document.body.style.overflow = 'hidden';
}

function fermerMentionsLegales() {
  const m = document.getElementById('modaleLegale');
  if (m) m.remove();
  document.body.style.overflow = '';
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') fermerMentionsLegales();
});

/* ============================================================
   LIBELLÉS DES RÔLES
   ------------------------------------------------------------
   Les rôles restent stockés sous leurs noms techniques ('mentor',
   'etudiant'). Renommer ces valeurs imposerait de migrer une base
   vivante et une trentaine de requêtes, sans rien changer pour
   personne. Seule la traduction affichée compte, et elle est faite
   ici, à un seul endroit.
   ============================================================ */

const LIBELLES_ROLES = {
  visiteur: 'Visiteur',
  etudiant: 'Bénéficiaire',
  mentor: 'Référent',
  admin: 'Administrateur',
  super_admin: 'Administrateur principal',
};

function libelleRole(role) {
  return LIBELLES_ROLES[role] || role || '';
}

/* ============================================================
   COMPLÉTION DU PROFIL
   ------------------------------------------------------------
   Un profil vide n'inspire pas confiance : personne ne s'adresse à
   quelqu'un dont on ne sait rien. Montrer ce qui manque, et ce que
   chaque élément apporte, obtient bien plus qu'une invitation vague
   à « compléter son profil ».
   ============================================================ */

function elementsProfil(u) {
  return [
    { fait: !!(u.prenom && u.nom), libelle: 'Prénom et nom',
      gain: 'Les autres membres savent à qui ils parlent.' },
    { fait: !!u.photo, libelle: 'Photo de profil',
      gain: 'Un profil avec photo reçoit nettement plus de réponses.' },
    { fait: !!(u.bio && u.bio.trim().length >= 40), libelle: 'Présentation',
      gain: 'Quelques lignes sur votre parcours suffisent à situer vos questions.' },
    { fait: !!u.pays, libelle: 'Pays',
      gain: 'Les conseils dépendent souvent du pays où vous étudiez.' },
    { fait: !!(u.secteurs && u.secteurs.length), libelle: "Secteurs d'intérêt",
      gain: 'Ils orientent les référents et les questions qui vous sont proposés.' },
    { fait: !!u.situation, libelle: 'Votre situation',
      gain: 'Savoir où vous en êtes change la réponse qu\'on vous donne.' },
    { fait: !!u.objectif, libelle: 'Ce que vous cherchez',
      gain: 'C\'est ce qui vous rapproche des référents qui peuvent aider.' },
    { fait: !!u.domaine, libelle: 'Domaine ou métier',
      gain: 'Il décide des questions et des référents qu\'on vous propose.' },
    { fait: !!u.niveau_etudes, libelle: 'Niveau d\'études',
      gain: 'Une même question n\'appelle pas la même réponse selon le niveau.' },
  ];
}

/* Part des éléments renseignés, de 0 à 100. */
function completudeProfil(u) {
  const el = elementsProfil(u || etat.utilisateur || {});
  if (!el.length) return 100;
  return Math.round((el.filter(e => e.fait).length / el.length) * 100);
}

/* Rappel affiché dans le fil quand le profil reste très incomplet.

   La carte de complétion vit sur la page du profil, que personne ne
   visite spontanément : celles et ceux qui auraient le plus à gagner à
   la voir sont exactement celles et ceux qui n'y vont jamais. Le rappel
   vient donc à eux, une fois, et se referme.

   Il ne bloque rien et ne se répète pas : un rappel qu'on ne peut pas
   faire taire cesse d'être lu au bout de deux fois. */
const SEUIL_RAPPEL_PROFIL = 60;
const JOURS_AVANT_RELANCE = 7;

function majRappelProfil() {
  const u = etat.utilisateur;
  const zone = document.getElementById('rappel-profil');
  if (!zone) return;
  if (!u || !u.email) { zone.innerHTML = ''; return; }

  const part = completudeProfil(u);
  if (part >= SEUIL_RAPPEL_PROFIL) { zone.innerHTML = ''; return; }

  let masqueJusquA = 0;
  try { masqueJusquA = +(localStorage.getItem('lasourcee-rappel-profil') || 0); }
  catch (_) { /* stockage refusé : le rappel s'affichera à chaque visite */ }
  if (Date.now() < masqueJusquA) { zone.innerHTML = ''; return; }

  const manquants = elementsProfil(u).filter(e => !e.fait).slice(0, 2);
  zone.innerHTML = `<div class="carte rappel-profil">
    <div class="rappel-profil-texte">
      <strong>Votre profil est complété à ${part}&nbsp;%.</strong>
      <p>Les référents répondent d'abord aux profils qu'ils comprennent, et
         vos questions sont proposées aux membres qui partagent votre
         domaine. Un profil renseigné touche donc un public plus large.
         ${manquants.length
           ? 'Il manque surtout : ' + manquants.map(e =>
               echapper(e.libelle.toLowerCase())).join(' et ') + '.'
           : ''}</p>
    </div>
    <div class="rappel-profil-actions">
      <button class="btn btn-primaire btn-petit"
              onclick="naviguerApp('parametres')">Compléter mon profil</button>
      <button class="btn btn-secondaire btn-petit"
              onclick="reporterRappelProfil()">Plus tard</button>
    </div>
  </div>`;
}

function reporterRappelProfil() {
  try {
    localStorage.setItem('lasourcee-rappel-profil',
      String(Date.now() + JOURS_AVANT_RELANCE * 86400000));
  } catch (_) { /* sans stockage, le rappel reviendra : sans gravité */ }
  const zone = document.getElementById('rappel-profil');
  if (zone) zone.innerHTML = '';
}

function carteCompletionProfil() {
  const u = etat.utilisateur;
  if (!u) return '';
  const elements = elementsProfil(u);
  const faits = elements.filter(e => e.fait).length;
  const pourcent = Math.round((faits / elements.length) * 100);
  const manquants = elements.filter(e => !e.fait);

  if (!manquants.length) {
    return `<div class="carte carte-completion complete">
      <div class="completion-entete">
        <strong>Profil complet</strong>
        <span class="completion-valeur">100&nbsp;%</span>
      </div>
      <div class="jauge-completion"><div style="width:100%"></div></div>
      <p class="desc">Tout est renseigné. Vos questions et vos réponses
         partent avec les meilleures chances d'être lues.</p>
    </div>`;
  }

  return `<div class="carte carte-completion">
    <div class="completion-entete">
      <strong>Votre profil est complété à ${pourcent}&nbsp;%</strong>
      <span class="completion-valeur">${faits}/${elements.length}</span>
    </div>
    <div class="jauge-completion"><div style="width:${pourcent}%"></div></div>
    <ul class="completion-liste">
      ${manquants.map(e => `<li>
        <strong>${echapper(e.libelle)}</strong>
        <span>${echapper(e.gain)}</span>
      </li>`).join('')}
    </ul>
    <button class="btn btn-secondaire btn-petit"
            onclick="allerCompleterProfil()">Compléter maintenant</button>
  </div>`;
}

function allerCompleterProfil() {
  naviguerApp('parametres');
  const onglet = document.querySelector('#menu-param button[data-pan="compte"]');
  if (onglet) changerPanParam(onglet, 'compte');
}

/* ============================================================
   CONFIRMATION DE L'ADRESSE E-MAIL
   ------------------------------------------------------------
   Une personne dont le message s'est perdu, ou dont le lien a expiré
   au bout de vingt-quatre heures, se heurtait à un refus sans recours.
   Le refus explique désormais, et propose de renvoyer le lien.
   ============================================================ */

function ouvrirConfirmationAdresse(email) {
  fermerMentionsLegales();
  const fond = document.createElement('div');
  fond.className = 'modale-fond';
  fond.id = 'modaleLegale';
  fond.setAttribute('role', 'dialog');
  fond.setAttribute('aria-modal', 'true');
  fond.innerHTML = `
    <div class="modale-boite">
      <div class="modale-entete">
        <h2>Confirmez votre adresse</h2>
        <button class="modale-fermer" onclick="fermerMentionsLegales()" aria-label="Fermer">&times;</button>
      </div>
      <div class="modale-corps">
        <p>Pour vérifier que cette adresse est bien la vôtre, nous vous
           avons envoyé un message à <strong>${echapper(email)}</strong>.
           Il contient un code à six chiffres.</p>
        <div class="champ">
          <label for="code-confirmation">Code reçu par e-mail</label>
          <input id="code-confirmation" class="saisie-code" inputmode="numeric"
                 autocomplete="one-time-code" maxlength="6" placeholder="000000"
                 onkeydown="if(event.key==='Enter') validerCodeConfirmation('${echapper(email)}', this)" />
          <p class="aide-champ">Le message contient aussi un lien, si vous
             préférez. Code et lien valables vingt-quatre heures.</p>
        </div>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn btn-primaire" id="btn-code"
                  onclick="validerCodeConfirmation('${echapper(email)}', this)">
            Valider mon adresse</button>
          <button class="btn btn-secondaire" id="btn-renvoi"
                  onclick="renvoyerConfirmation('${echapper(email)}')">
            Renvoyer le message</button>
        </div>
        <p class="desc" style="margin-top:10px;">Pensez à regarder dans les
           indésirables : les messages automatiques y atterrissent souvent
           la première fois.</p>
        <p class="note-param" id="etat-renvoi"></p>
      </div>
    </div>`;
  fond.addEventListener('click', (e) => {
    if (e.target === fond) fermerMentionsLegales();
  });
  document.body.appendChild(fond);
  document.body.style.overflow = 'hidden';
}

/* Validation par le code reçu. Elle ne dépend d'aucune URL : c'est
   précisément ce qui manquait quand le lien conduisait vers une adresse
   de déploiement où personne ne pouvait aboutir. */
async function validerCodeConfirmation(email, bouton) {
  const champ = document.getElementById('code-confirmation');
  const info = document.getElementById('etat-renvoi');
  const code = (champ?.value || '').replace(/\D/g, '');
  if (code.length !== 6) {
    if (info) { info.style.color = 'var(--rouge-fonce)';
                info.textContent = 'Saisissez les six chiffres du code.'; }
    champ?.focus();
    return;
  }
  const libelle = bouton.textContent;
  bouton.disabled = true; bouton.textContent = 'Vérification…';
  try {
    const r = await API.post('/auth/verifier-code', { email, code });
    if (info) { info.style.color = 'var(--vert)';
                info.textContent = r.message || 'Adresse vérifiée.'; }
    toast('Adresse vérifiée. Vous pouvez vous connecter.');
    if (etat.utilisateur) etat.utilisateur.email_verifie = true;
    majRappelConfirmation();
    setTimeout(fermerMentionsLegales, 1400);
  } catch (err) {
    if (info) { info.style.color = 'var(--rouge-fonce)';
                info.textContent = err.message || 'Code refusé.'; }
    champ?.select();
  } finally {
    bouton.disabled = false; bouton.textContent = libelle;
  }
}

async function renvoyerConfirmation(email) {
  const bouton = document.getElementById('btn-renvoi');
  const info = document.getElementById('etat-renvoi');
  if (bouton) { bouton.disabled = true; bouton.textContent = 'Envoi…'; }
  try {
    const r = await API.post('/auth/renvoyer-confirmation', { email });
    if (info) info.textContent = r.message || 'Lien renvoyé.';
  } catch (err) {
    if (info) info.textContent = err.message || "L'envoi a échoué.";
  } finally {
    if (bouton) { bouton.disabled = false; bouton.textContent = 'Renvoyer le lien'; }
  }
}

/* Bandeau affiché aux membres connectés dont l'adresse n'est pas encore
   confirmée. Il n'empêche rien, il rappelle : bloquer quelqu'un qui a
   déjà un compte le ferait partir. */
function majRappelConfirmation() {
  const u = etat.utilisateur;
  const existant = document.getElementById('rappel-confirmation');
  if (!u || !u.email || u.email_verifie) return existant && existant.remove();

  const bandeau = existant || document.createElement('div');
  bandeau.id = 'rappel-confirmation';
  bandeau.className = 'bandeau-alerte bandeau-fixe';
  bandeau.setAttribute('role', 'status');

  // Deux situations, deux messages. Inviter à ouvrir un lien reçu par
  // e-mail alors qu'aucun e-mail n'a pu partir envoie chercher dans une
  // boîte où rien n'arrivera, et fait douter de la plateforme plutôt
  // que de sa configuration.
  if (window.ENVOI_EMAIL_ACTIF === false) {
    bandeau.innerHTML =
      '<span><strong>Adresse non confirmée.</strong> '
      + "L'envoi d'e-mails n'est pas encore en service sur la plateforme : "
      + "aucun lien n'a pu vous être adressé. Votre compte reste "
      + 'utilisable, il n\'y a rien à faire de votre côté.</span>';
  } else {
    // Le bouton ouvre la fenêtre de saisie du code plutôt que de
    // renvoyer un message de plus : quelqu'un qui voit ce bandeau a
    // déjà reçu le sien, et c'est le lien qui n'a pas abouti.
    bandeau.innerHTML =
      '<span><strong>Adresse non confirmée.</strong> '
      + 'Saisissez le code reçu par e-mail pour sécuriser votre compte.</span>'
      + '<button class="btn btn-petit" onclick="ouvrirConfirmationAdresse('
      + `'${echapper(u.email)}')">Saisir mon code</button>`;
  }
  if (!existant) document.body.prepend(bandeau);
}

async function renvoyerMaConfirmation(bouton) {
  const libelle = bouton.textContent;
  bouton.disabled = true;
  bouton.textContent = 'Envoi…';
  try {
    const r = await API.post('/auth/confirmation/moi');
    toast(r.message || 'Lien renvoyé.');
  } catch (err) {
    toast(err.message || "L'envoi a échoué.", 'erreur');
  } finally {
    bouton.disabled = false;
    bouton.textContent = libelle;
  }
}

/* ============================================================
   NOTIFICATIONS : RELÈVE PÉRIODIQUE
   ------------------------------------------------------------
   Une connexion permanente serait plus élégante, mais les fonctions
   sans serveur ont une durée de vie bornée : elles ne peuvent pas
   maintenir un canal ouvert. On interroge donc le serveur à
   intervalle régulier.

   Trente secondes quand l'onglet est visible, rien du tout quand il ne
   l'est pas : interroger un onglet en arrière-plan consomme la batterie
   du téléphone sans que personne ne regarde le résultat. La relève
   reprend immédiatement au retour, pour que le compteur soit à jour
   avant même que l'œil ne s'y pose.
   ============================================================ */

const RELEVE_NOTIFS_MS = 30000;
let _minuteurNotifs = null;

async function releverNotifications() {
  if (!etat.utilisateur) return;
  try {
    const r = await API.get('/notifications/non-lues');
    majPastilleNotifications(r && typeof r.non_lues === 'number' ? r.non_lues : 0);
  } catch (err) {
    // Un échec de relève ne doit rien interrompre : le prochain
    // passage réessaiera.
  }
}

function majPastilleNotifications(nb) {
  const bouton = document.querySelector('.nav-bouton[data-section="notifs"]');
  if (!bouton) return;
  let pastille = bouton.querySelector('.pastille-notif');

  if (!nb) {
    if (pastille) pastille.remove();
    bouton.removeAttribute('aria-label');
    bouton.setAttribute('aria-label', 'Notifications');
    return;
  }
  if (!pastille) {
    pastille = document.createElement('span');
    pastille.className = 'pastille-notif';
    bouton.appendChild(pastille);
  }
  pastille.textContent = nb > 9 ? '9+' : String(nb);
  bouton.setAttribute('aria-label',
    `Notifications, ${nb} non lue${nb > 1 ? 's' : ''}`);
}

function demarrerReleveNotifications() {
  arreterReleveNotifications();
  releverNotifications();
  _minuteurNotifs = setInterval(releverNotifications, RELEVE_NOTIFS_MS);
}

function arreterReleveNotifications() {
  if (_minuteurNotifs) {
    clearInterval(_minuteurNotifs);
    _minuteurNotifs = null;
  }
}

document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    arreterReleveNotifications();
  } else if (etat.utilisateur) {
    demarrerReleveNotifications();
  }
});

/* Listes servies par le serveur plutôt qu'écrites ici : la liste
   affichée et celle que le serveur accepte ne peuvent alors pas
   diverger, et un ajout se fait à un seul endroit. */
async function chargerReferentielsProfil() {
  if (etat.referentielsProfil) return etat.referentielsProfil;
  try {
    etat.referentielsProfil = await API.get('/profil/referentiels-profil');
  } catch {
    // Toutes les clés, y compris vides : le rendu du panneau les
    // parcourt, et une clé absente ferait tomber la page entière au
    // lieu de n'afficher qu'une liste vide.
    etat.referentielsProfil = {
      situations: [], objectifs: [],
      niveaux_etudes: [], domaines: [], etablissements: [],
    };
  }
  return etat.referentielsProfil;
}

/* Ligne d'identité affichée sous le nom, sur le profil. Elle réunit ce
   qui situe la personne en un coup d'œil, sans obliger à lire la
   présentation entière. */
function ligneIdentiteProfil(u) {
  const morceaux = [];
  if (u.situation) morceaux.push(echapper(u.situation));
  // Le parcours structuré s'il existe, sinon l'ancien champ libre :
  // les comptes créés avant la séparation en trois champs ne doivent
  // pas voir leur parcours disparaître de leur profil.
  if (u.domaine) morceaux.push(echapper(u.domaine));
  else if (u.etudes) morceaux.push(echapper(u.etudes));
  if (u.pays) morceaux.push(echapper(u.pays));
  if (!morceaux.length) return '';
  return `<div class="profil-identite">${morceaux.join(' · ')}</div>`;
}

function detailsProfil(u) {
  const lignes = [];
  if (u.objectif) {
    lignes.push(['Recherche', echapper(u.objectif)]);
  }
  if (u.niveau_etudes) {
    lignes.push(['Niveau d\'études', echapper(u.niveau_etudes)]);
  }
  if (u.etablissement) {
    lignes.push(['Formation', echapper(u.etablissement)]);
  }
  if (u.langues) {
    lignes.push(['Langues', echapper(u.langues)]);
  }
  if (u.profil_pro) {
    lignes.push(['Profil professionnel',
      `<a href="${echapper(u.profil_pro)}" target="_blank" rel="noopener noreferrer">Consulter</a>`]);
  }
  if (!lignes.length) return '';
  return `<div class="carte profil-details">
    ${lignes.map(([cle, val]) =>
      `<div class="profil-detail"><span>${cle}</span><strong>${val}</strong></div>`).join('')}
  </div>`;
}

/* ============================================================
   ADMINISTRATEURS, DROITS ET EXPORTS
   ============================================================ */

/* Le menu n'affiche que les écrans réellement accessibles. Proposer un
   onglet qui répondra « accès refusé » fait passer un refus de droits
   pour une panne, et pousse à demander de l'aide au lieu de demander
   le droit qui manque. */
async function ajusterMenuAdmin() {
  const menu = document.querySelector('.menu-admin');
  if (!menu) return;
  let droits = [], superAdmin = false;
  try {
    const r = await API.get('/admin/permissions');
    droits = r.les_miennes || [];
    superAdmin = !!r.super_admin;
    etat.droitsAdmin = droits;
    etat.superAdmin = superAdmin;
  } catch (_) { return; }

  menu.querySelectorAll('button[data-adm]').forEach(b => {
    const p = b.dataset.adm;
    // Le tableau de bord reste ouvert : il ne montre que des totaux.
    const requis = { users: 'utilisateurs', mentors: 'referents',
                     signalements: 'signalements', categories: 'categories',
                     audit: 'audit', diagnostic: 'diagnostic',
                     administrateurs: 'administrateurs', export: 'export' }[p];
    b.hidden = !!requis && !droits.includes(requis);
  });
}

async function adminAdministrateurs() {
  const [liste, cat] = await Promise.all([
    API.get('/admin/administrateurs'),
    API.get('/admin/permissions'),
  ]);
  const catalogue = cat.catalogue || [];
  const suis_super = !!cat.super_admin;

  const GROUPES = [
    ['animation', 'Animation de la plateforme',
     "Le travail courant. Ces droits n'exposent ni les adresses des membres ni la configuration."],
    ['sensible', 'Données et configuration',
     'Ces droits donnent accès aux adresses e-mail, au journal des actions ou aux réglages du serveur.'],
    ['critique', 'Contrôle des accès',
     "Ce droit permet d'en accorder d'autres, y compris à soi-même par personne interposée."],
  ];

  /* Une case par droit, avec son nom lisible et ce qu'il ouvre. La
     grille alignait mal parce que les cartes n'avaient pas la même
     hauteur : les descriptions font une, deux ou trois lignes. Elles
     s'étirent maintenant sur toute la rangée. */
  const cases = (prefixe, coches, desactive) => GROUPES.map(([portee, titre, aide]) => {
    const droits = catalogue.filter(d => d.portee === portee);
    if (!droits.length) return '';
    return `<fieldset class="groupe-droits portee-${portee}">
      <legend>${echapper(titre)}</legend>
      <p class="aide-champ" style="margin:0 0 10px;">${echapper(aide)}</p>
      <div class="grille-droits">
        ${droits.map(d => `
          <label class="case-droit ${desactive ? 'fige' : ''}">
            <input type="checkbox" id="${prefixe}-${d.cle}" value="${d.cle}"
                   ${coches.includes(d.cle) ? 'checked' : ''}
                   ${desactive ? 'disabled' : ''} />
            <span>
              <strong>${echapper(d.nom)}</strong>
              <em>${echapper(d.description)}</em>
            </span>
          </label>`).join('')}
      </div>
    </fieldset>`;
  }).join('');

  const formulaire = suis_super ? `
    <div class="carte" style="margin-bottom:18px;">
      <h3 class="titre-param">Nommer un administrateur</h3>
      <p class="desc">Si l'adresse correspond à un membre existant, son
         compte est promu et son mot de passe reste le sien. Sinon un
         compte est créé, et ses accès lui sont envoyés par e-mail.</p>
      <div class="champs-cote">
        <div class="champ"><label for="na-prenom">Prénom</label><input id="na-prenom" placeholder="Chabi" /></div>
        <div class="champ"><label for="na-nom">Nom</label><input id="na-nom" placeholder="Gbaguidi" /></div>
      </div>
      <div class="champ"><label for="na-email">Adresse e-mail</label>
        <input id="na-email" type="email" placeholder="prenom@lasourcee.org" /></div>
      ${cases('na', cat.par_defaut || [], false)}
      <label class="case-droit case-super">
        <input type="checkbox" id="na-super" />
        <span>
          <strong>Super administrateur</strong>
          <em>Tous les droits d'un coup, présents et à venir, sans qu'on
            puisse les lui retirer un par un. À réserver à quelqu'un dont
            vous répondez.</em>
        </span>
      </label>
      <button class="btn btn-primaire" style="margin-top:14px;"
              onclick="creerAdministrateur(this)">Créer le compte</button>
      <p class="note-param" id="na-retour"></p>
    </div>` : `
    <div class="carte" style="margin-bottom:18px;">
      <p class="desc">Seul un super administrateur peut nommer des
         administrateurs ou modifier leurs droits. La liste ci-dessous
         reste consultable.</p>
    </div>`;

  return `<h2 style="margin-bottom:6px;">Administrateurs</h2>
    <p class="desc" style="margin-bottom:16px;">Les droits se donnent un
       par un. Confier la modération ne revient pas à confier le journal
       d'audit, les adresses de tous les membres ou la configuration du
       serveur.</p>
    ${formulaire}
    ${liste.map(a => {
      const est_super = a.role === 'super_admin';
      const droits = a.droits || [];
      const fige = !suis_super || est_super;
      return `<div class="carte carte-admin">
        <div class="entete-admin">
          <div>
            <strong>${echapper(a.prenom + ' ' + a.nom)}</strong>
            <div class="desc">${echapper(a.email)}</div>
          </div>
          <div class="etiquettes-admin">
            <span class="tag ${est_super ? 'tag-terre' : 'tag-ardoise'}">${
              est_super ? 'super administrateur' : 'administrateur'}</span>
            ${a.est_actif ? '' : '<span class="tag tag-suspendu">suspendu</span>'}
            ${a.derniere_co ? `<span class="desc">vu le ${
              echapper(formatHorodatage(a.derniere_co))}</span>` : ''}
          </div>
        </div>
        ${est_super
          ? `<p class="aide-champ">Tous les droits, y compris ceux qui
             seront ajoutés plus tard. Ils ne se restreignent pas.</p>`
          : cases('dr-' + a.id_utilisateur, droits, fige)}
        ${suis_super && !est_super ? `<div class="actions-admin">
          <button class="btn btn-secondaire btn-petit"
                  onclick="enregistrerDroits(${a.id_utilisateur}, this)">Enregistrer les droits</button>
          <button class="btn btn-danger btn-petit"
                  onclick="retirerAdministrateur(${a.id_utilisateur})">Retirer l'administration</button>
        </div>` : ''}
      </div>`;
    }).join('')}`;
}

function _droitsCoches(prefixe) {
  return [...document.querySelectorAll(`[id^="${prefixe}-"]`)]
    .filter(e => e.type === 'checkbox' && e.checked && e.value)
    .map(e => e.value);
}

async function creerAdministrateur(bouton) {
  const retour = document.getElementById('na-retour');
  const corps = {
    prenom: (document.getElementById('na-prenom')?.value || '').trim(),
    nom: (document.getElementById('na-nom')?.value || '').trim(),
    email: (document.getElementById('na-email')?.value || '').trim(),
    permissions: _droitsCoches('na').filter(d => d !== 'super'),
    super_admin: !!document.getElementById('na-super')?.checked,
  };
  bouton.disabled = true;
  try {
    const r = await API.post('/admin/administrateurs', corps);
    if (r.mot_de_passe) {
      // L'e-mail n'est pas parti : sans cela l'accès serait créé sans
      // que personne puisse s'en servir. Affiché une seule fois.
      retour.style.color = 'var(--rouge-fonce)';
      retour.textContent = "L'e-mail n'a pas pu être envoyé. Transmettez ce "
        + `mot de passe provisoire vous-même : ${r.mot_de_passe}`;
    } else {
      retour.style.color = 'var(--texte-doux)';
      retour.textContent = r.cree
        ? 'Compte créé, ses accès viennent de lui être envoyés.'
        : 'Compte existant promu administrateur.';
    }
    toast('Administrateur enregistré.');
    setTimeout(() => changerPanAdmin(
      document.querySelector('[data-adm=administrateurs]'), 'administrateurs'), 1800);
  } catch (err) {
    retour.style.color = 'var(--rouge-fonce)';
    retour.textContent = err.message || 'Création impossible.';
  } finally { bouton.disabled = false; }
}

async function enregistrerDroits(id, bouton) {
  bouton.disabled = true;
  try {
    await API.put(`/admin/administrateurs/${id}`,
                  { permissions: _droitsCoches('dr-' + id) });
    toast('Droits mis à jour.');
  } catch (err) { toast(err.message, 'erreur'); }
  finally { bouton.disabled = false; }
}

async function retirerAdministrateur(id) {
  if (!confirm("Retirer les droits d'administration de ce compte ?\n\n"
      + "Le compte et ses contenus sont conservés : seuls les droits "
      + "sont retirés.")) return;
  try {
    await API.delete(`/admin/administrateurs/${id}`);
    toast('Droits retirés.');
    changerPanAdmin(document.querySelector('[data-adm=administrateurs]'),
                    'administrateurs');
  } catch (err) { toast(err.message, 'erreur'); }
}

async function adminExport() {
  const jeux = await API.get('/admin/export');
  return `<h2 style="margin-bottom:6px;">Export des données</h2>
    <p class="desc" style="margin-bottom:16px;">Pour analyser l'activité,
       préparer un rapport ou garder une copie hors ligne. Le CSV s'ouvre
       dans un tableur, le JSON se traite par programme. Aucun mot de
       passe ni jeton de session n'y figure.</p>
    <div class="carte" style="margin-bottom:18px;">
      <div class="cadre-tableau"><table class="table-export">
        <thead><tr><th>Jeu de données</th><th>Lignes</th><th>Télécharger</th></tr></thead>
        <tbody>
          ${jeux.map(j => `<tr>
            <td><strong>${echapper(j.libelle)}</strong></td>
            <td class="desc">${j.lignes === null ? '' : j.lignes}</td>
            <td style="display:flex; gap:6px;">
              <button class="btn btn-secondaire btn-petit"
                      onclick="telechargerExport('${j.cle}','csv')">CSV</button>
              <button class="btn btn-fantome btn-petit"
                      onclick="telechargerExport('${j.cle}','json')">JSON</button>
            </td></tr>`).join('')}
        </tbody>
      </table></div>
    </div>
    <div class="carte">
      <h3 class="titre-param">Dossier d'une personne</h3>
      <p class="desc">Tout ce que la plateforme conserve sur un compte :
         profil, questions, réponses, signalements émis. Utile pour
         répondre à une demande d'accès ou instruire un signalement.</p>
      <div style="display:flex; gap:8px; align-items:flex-end;">
        <div class="champ" style="flex:1; margin:0;">
          <label>Identifiant du compte</label>
          <input id="exp-id" type="number" min="1" placeholder="Ex : 12" />
        </div>
        <button class="btn btn-secondaire" onclick="telechargerDossier()">Télécharger</button>
      </div>
      <p class="aide-champ">L'identifiant figure dans l'écran Utilisateurs.</p>
    </div>`;
}

/* Le téléchargement passe par une requête authentifiée puis un objet
   Blob : un simple lien n'emporterait pas le cookie de session sur
   toutes les configurations, et renverrait un fichier d'erreur. */
async function _telecharger(url, nomDefaut) {
  try {
    const r = await fetch(API_BASE + url, { credentials: 'same-origin' });
    if (!r.ok) {
      const t = await r.json().catch(() => ({}));
      throw new Error(t.erreur || `Échec (${r.status}).`);
    }
    const nom = (r.headers.get('Content-Disposition') || '')
      .match(/filename="([^"]+)"/)?.[1] || nomDefaut;
    const blob = await r.blob();
    const lien = document.createElement('a');
    lien.href = URL.createObjectURL(blob);
    lien.download = nom;
    document.body.appendChild(lien);
    lien.click();
    lien.remove();
    setTimeout(() => URL.revokeObjectURL(lien.href), 2000);
    toast(`${nom} téléchargé.`);
  } catch (err) { toast(err.message || 'Téléchargement impossible.', 'erreur'); }
}

function telechargerExport(jeu, format) {
  _telecharger(`/admin/export/${jeu}?format=${format}`,
               `lasourcee-${jeu}.${format}`);
}

function telechargerDossier() {
  const id = (document.getElementById('exp-id')?.value || '').trim();
  if (!id) return toast('Indiquez un identifiant de compte.', 'erreur');
  _telecharger(`/admin/export/compte/${encodeURIComponent(id)}`,
               `lasourcee-compte-${id}.json`);
}

/* ============================================================
   PHOTOS ET PROFILS DES AUTRES MEMBRES
   ============================================================ */

/* Agrandissement d'une photo de profil.

   Une vignette de quarante pixels ne montre pas un visage. Cliquer
   dessus affiche l'image entière, ce que tout le monde essaie de faire
   avant même d'y penser. Fermeture au clic à côté ou par Échap. */
function ouvrirPhoto(source, legende) {
  if (!source) return;
  fermerPhoto();
  const fond = document.createElement('div');
  fond.className = 'visionneuse';
  fond.id = 'visionneuse';
  fond.setAttribute('role', 'dialog');
  fond.setAttribute('aria-modal', 'true');
  fond.setAttribute('aria-label', legende || 'Photo de profil');
  fond.innerHTML = `
    <button class="visionneuse-fermer" onclick="fermerPhoto()"
            aria-label="Fermer">&times;</button>
    <figure>
      <img src="${echapper(source)}" alt="${echapper(legende || '')}" />
      ${legende ? `<figcaption>${echapper(legende)}</figcaption>` : ''}
    </figure>`;
  fond.addEventListener('click', (e) => {
    if (e.target === fond) fermerPhoto();
  });
  document.body.appendChild(fond);
  document.body.style.overflow = 'hidden';
  fond.querySelector('.visionneuse-fermer')?.focus();
}

function fermerPhoto() {
  document.getElementById('visionneuse')?.remove();
  if (!document.querySelector('.modale-fond')) document.body.style.overflow = '';
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') fermerPhoto();
});

/* Avatar cliquable : il ouvre le profil de la personne, et la photo en
   grand si l'on clique dessus alors que le profil est déjà ouvert. */
function avatarLien(id, initiales, taille, photo, verifie, nom) {
  const contenu = avatarHTML(initiales, taille, photo, verifie);
  if (!id) return contenu;
  return `<span class="avatar-lien" role="button" tabindex="0"
      title="Voir le profil de ${echapper(nom || '')}"
      onclick="event.stopPropagation(); ouvrirProfilUtilisateur(${id})"
      onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault(); ouvrirProfilUtilisateur(${id});}"
    >${contenu}</span>`;
}

/* Profil public d'un autre membre, chargé depuis le serveur. */
let profilPublic = null;

async function ouvrirProfilUtilisateur(id) {
  if (!id) return;
  if (etat.utilisateur && id === etat.utilisateur.id) {
    profilCible = null; profilPublic = null;
    return naviguerApp('profil');
  }
  try {
    profilPublic = await API.get('/profil/' + id);
    profilCible = null;
    naviguerApp('profil');
  } catch (err) {
    toast(err.message || 'Profil indisponible.', 'erreur');
  }
}

/* Lignes de parcours communes à tous les profils. Le même bloc sert au
   bénéficiaire, au référent et à l'administrateur : ce qui distingue
   les trois est ce qu'ils ont rempli, pas la forme de leur fiche. */
function blocParcoursProfil(u) {
  /* Le parcours en trois blocs, plutôt qu'une liste de dix lignes qui
     mêlait la situation, le diplôme, les langues et un lien. Chacun
     répond à une question différente, et un lecteur qui cherche l'une
     ne devrait pas parcourir les autres :

       où en est cette personne · ce qu'elle a étudié · comment la joindre

     Un bloc vide disparaît : afficher « Formation » suivi de rien
     donne l'impression d'un champ cassé. */
  const objectifs = u.objectifs && u.objectifs.length
    ? u.objectifs
    : (u.objectif ? String(u.objectif).split(',').map(s => s.trim()).filter(Boolean) : []);

  const blocs = [
    { titre: 'Où en est cette personne', lignes: [
        ['Situation', u.situation],
      ], chips: objectifs.length ? { libelle: 'Recherche', valeurs: objectifs } : null },
    { titre: 'Parcours', lignes: [
        ["Niveau d'études", u.niveau_etudes],
        ['Domaine ou métier', u.domaine],
        ['Formation', u.etablissement],
        // Ancien champ libre : affiché seulement si le parcours
        // structuré est vide, sinon la même chose s'écrirait deux fois.
        ...((!u.niveau_etudes && !u.domaine && u.etudes)
            ? [['Études', u.etudes]] : []),
      ] },
    { titre: 'Échanger', lignes: [
        ['Langues', u.langues],
        ['Profil professionnel', u.profil_pro
          ? `<a href="${echapper(u.profil_pro)}" target="_blank"
               rel="noopener noreferrer nofollow">Consulter</a>` : null,
          true],
      ] },
  ];

  const rendu = blocs.map(bloc => {
    const lignes = bloc.lignes.filter(([, valeur]) => valeur);
    if (!lignes.length && !bloc.chips) return '';
    return `<section class="bloc-parcours">
      <h3>${echapper(bloc.titre)}</h3>
      ${bloc.chips ? `<div class="ligne-parcours">
        <span class="cle-parcours">${echapper(bloc.chips.libelle)}</span>
        <span class="chips-parcours">${bloc.chips.valeurs.map(v =>
          `<span class="tag">${echapper(v)}</span>`).join('')}</span>
      </div>` : ''}
      ${lignes.map(([cle, valeur, brut]) => `<div class="ligne-parcours">
        <span class="cle-parcours">${echapper(cle)}</span>
        <span>${brut ? valeur : echapper(valeur)}</span>
      </div>`).join('')}
    </section>`;
  }).filter(Boolean).join('');

  return rendu ? `<div class="parcours-profil">${rendu}</div>` : '';
}

/* Nom du rôle tel qu'il s'affiche. En base, « mentor » et « etudiant »
   sont restés : les renommer aurait imposé de migrer toutes les lignes
   pour un gain nul, personne ne voyant ces chaînes. */
function nomRole(role, verifie) {
  if (role === 'super_admin') return 'Administrateur principal';
  if (role === 'admin') return 'Administrateur';
  if (role === 'mentor') return verifie ? 'Référent vérifié' : 'Référent';
  if (role === 'visiteur') return 'Visiteur';
  return 'Bénéficiaire';
}

function iconeRole(role) {
  if (role === 'admin' || role === 'super_admin') return ic('bouclier', 'ic ic-s');
  if (role === 'mentor') return ic('trophee', 'ic ic-s');
  return ic('diplome', 'ic ic-s');
}

/* Profil d'un autre membre. Même présentation que le sien, sans les
   boutons de modification et sans les informations qui ne regardent que
   la personne : l'adresse e-mail n'est pas renvoyée par le serveur pour
   un profil consulté par quelqu'un d'autre. */
function rendreProfilAutre(u) {
  const nomComplet = `${u.prenom || ''} ${u.nom || ''}`.trim();
  const initiales = ((u.prenom || '?')[0] + (u.nom || '?')[0]).toUpperCase();
  const verifie = !!u.est_verifie;
  const suivi = etat.suivis.has(u.id_utilisateur);

  const entete = document.getElementById('entete-profil');
  entete.innerHTML = `
    <div class="col-avatar">
      <span class="${u.photo_url ? 'avatar-agrandissable' : ''}"
            ${u.photo_url ? `onclick="ouvrirPhoto('${echapper(u.photo_url)}', '${echapper(nomComplet)}')"
            title="Voir la photo en grand" role="button" tabindex="0"` : ''}>
        ${avatarHTML(initiales, 'xl', u.photo_url, verifie)}
      </span>
    </div>
    <div class="col-infos">
      <h2>${echapper(nomComplet)} ${verifie ? badgeMentorVerifie() : ''}</h2>
      <div class="ligne-meta">
        <span class="badge-role">${iconeRole(u.role)} ${
          echapper(nomRole(u.role, verifie))}</span>
        ${u.en_ligne
          ? '<span class="etat-presence en-ligne">En ligne</span>'
          : ''}
        ${u.pays ? `<span>${ic('position','ic ic-s')} ${echapper(u.pays)}</span>` : ''}
        ${u.cree_le ? `<span>Membre depuis le ${
          echapper(formatDate(u.cree_le))}</span>` : ''}
      </div>
      <div class="tags-profil">
        ${(u.secteurs || []).map(s =>
          `<span class="tag">${echapper(s.libelle || s)}</span>`).join('')}
      </div>
      ${u.bio ? `<p class="bio-profil">${echapper(u.bio)}</p>` : ''}
      ${blocParcoursProfil(u)}
    </div>
    <div class="col-actions">
      <button class="btn btn-primaire"
        onclick="ecrireA(${u.id_utilisateur}, '${echapper(nomComplet)}')">Écrire</button>
      ${u.role === 'mentor' ? `<button class="btn ${suivi ? 'btn-secondaire' : 'btn-primaire'}"
        onclick="basculerSuiviProfil(${u.id_utilisateur}, this)">${
        suivi ? 'Suivi' : 'Suivre'}</button>` : ''}
      <button class="btn btn-secondaire" onclick="retourFil()">Retour au fil</button>
    </div>`;

  const stats = document.getElementById('stats-profil');
  if (stats) {
    stats.style.display = '';
    stats.innerHTML = `
      <div class="stat-item">
        <span class="stat-valeur">${u.nb_reponses ?? 0}</span>
        <span class="stat-label">Réponses</span>
      </div>
      ${u.note_moyenne ? `<div class="stat-item">
        <span class="stat-valeur">${u.note_moyenne}</span>
        <span class="stat-label">Note moyenne</span>
      </div>` : ''}
      ${u.anciennete ? `<div class="stat-item">
        <span class="stat-valeur">${echapper(u.anciennete)}</span>
        <span class="stat-label">Expérience</span>
      </div>` : ''}`;
  }
  const onglets = document.getElementById('onglets-profil');
  if (onglets) onglets.style.display = 'none';
  const contenu = document.getElementById('contenu-profil');
  if (contenu) contenu.innerHTML = '';
}

function retourFil() {
  profilPublic = null;
  profilCible = null;
  naviguerApp('fil');
}

async function basculerSuiviProfil(id, bouton) {
  // Une seule route, qui bascule : c'est elle qui dit l'état obtenu.
  // Le déduire ici ferait diverger le bouton de la réalité dès qu'un
  // autre onglet aurait agi entre-temps.
  bouton.disabled = true;
  try {
    const r = await API.post(`/mentors/${id}/suivre`, {});
    if (r.suivi) { etat.suivis.add(id); bouton.textContent = 'Suivi';
                   bouton.className = 'btn btn-secondaire'; }
    else { etat.suivis.delete(id); bouton.textContent = 'Suivre';
           bouton.className = 'btn btn-primaire'; }
  } catch (err) {
    toast(err.message || 'Action impossible.', 'erreur');
  } finally { bouton.disabled = false; }
}

/* Plusieurs objectifs, mais pas tous. Au-delà de quatre, le profil ne
   dit plus rien : quelqu'un qui coche tout n'a rien précisé. La limite
   se voit avant d'être atteinte, plutôt que d'être opposée après coup
   par le serveur. */
const LIMITE_OBJECTIFS = 4;

function limiterObjectifs() {
  const cases = [...document.querySelectorAll('#pc-objectifs input')];
  const coches = cases.filter(c => c.checked);
  cases.forEach(c => { c.disabled = !c.checked && coches.length >= LIMITE_OBJECTIFS; });
  cases.forEach(c => c.closest('.chip-choix')
    ?.classList.toggle('indisponible', c.disabled));

  const info = document.getElementById('compte-objectifs');
  if (!info) return;
  if (!coches.length) {
    info.textContent = 'Aucun choix : votre profil restera muet sur ce point.';
  } else if (coches.length >= LIMITE_OBJECTIFS) {
    info.textContent = `${coches.length} sur ${LIMITE_OBJECTIFS}, le maximum. `
      + 'Décochez pour en changer.';
  } else {
    info.textContent = `${coches.length} choix sur ${LIMITE_OBJECTIFS} possibles.`;
  }
}

/* ============================================================
   MESSAGERIE
   ============================================================
   Le serveur la servait depuis le début, l'accueil la promettait
   « Échangez par messagerie privée avec les référents », et aucun écran
   ne permettait d'y accéder : quatre routes fonctionnelles pour zéro
   point d'entrée. */

let _conversationOuverte = null;
let _minuteurMessages = null;

async function rendreMessagerie() {
  const zone = document.getElementById('liste-conversations');
  if (!zone) return;
  zone.innerHTML = '<p class="desc">Chargement…</p>';
  let liste;
  try {
    liste = await API.get('/messagerie/conversations');
  } catch (err) {
    zone.innerHTML = `<p class="desc">${echapper(err.message
      || 'Conversations indisponibles.')}</p>`;
    return;
  }
  majCompteurMessages(liste.reduce((n, c) => n + (c.non_lus || 0), 0));

  if (!liste.length) {
    zone.innerHTML = `<p class="desc">Aucune conversation. Ouvrez le profil
      d'un référent et écrivez-lui pour commencer.</p>`;
    return;
  }
  zone.innerHTML = liste.map(c => `
    <button class="conversation ${c.id_conversation === _conversationOuverte ? 'active' : ''}"
            onclick="ouvrirConversation(${c.id_conversation}, '${echapper((c.prenom || '') + ' ' + (c.nom || ''))}')">
      <span class="avatar-presence">
        ${avatarHTML(((c.prenom||'?')[0] + (c.nom||'?')[0]).toUpperCase(), 's', c.photo_url)}
        ${pastillePresence(c.en_ligne, c.derniere_activite)}
      </span>
      <span class="conversation-texte">
        <strong>${echapper((c.prenom || '') + ' ' + (c.nom || ''))}</strong>
        <em>${echapper((c.dernier_contenu || 'Aucun message').slice(0, 60))}</em>
      </span>
      ${c.non_lus ? `<span class="pastille-notif">${c.non_lus}</span>` : ''}
    </button>`).join('');
}

async function ouvrirConversation(id, nom) {
  _conversationOuverte = id;
  const fil = document.getElementById('fil-messages');
  if (!fil) return;
  fil.innerHTML = '<p class="desc" style="padding:24px;">Chargement…</p>';
  let messages;
  try {
    messages = await API.get(`/messagerie/conversations/${id}/messages`);
  } catch (err) {
    fil.innerHTML = `<p class="desc" style="padding:24px;">${
      echapper(err.message || 'Messages indisponibles.')}</p>`;
    return;
  }
  const moi = etat.utilisateur?.id;
  fil.innerHTML = `
    <header class="entete-conversation">
      <strong>${echapper(nom || 'Conversation')}</strong>
    </header>
    <div class="messages" id="messages-defilement">
      ${messages.length
        ? messages.map(m => `<div class="message ${m.id_expediteur === moi ? 'de-moi' : ''}">
            <p>${echapper(m.contenu)}</p>
            <time>${echapper(formatHorodatage(m.envoye_le))}</time>
          </div>`).join('')
        : '<p class="desc">Aucun message. Écrivez le premier.</p>'}
    </div>
    <form class="saisie-message" onsubmit="event.preventDefault(); envoyerMessage(${id});">
      <label class="sr-only" for="champ-message">Votre message</label>
      <textarea id="champ-message" rows="2" maxlength="4000"
                placeholder="Écrivez votre message…"
                onkeydown="if(event.key==='Enter' && !event.shiftKey){event.preventDefault(); envoyerMessage(${id});}"></textarea>
      <button class="btn btn-primaire" type="submit">Envoyer</button>
    </form>`;
  // Le fil s'ouvre sur le dernier message : remonter à la main pour lire
  // ce qui vient d'arriver est le contraire de ce qu'on attend.
  const defil = document.getElementById('messages-defilement');
  if (defil) defil.scrollTop = defil.scrollHeight;
  rendreMessagerie();
}

async function envoyerMessage(id) {
  const champ = document.getElementById('champ-message');
  const contenu = (champ?.value || '').trim();
  if (!contenu) return;
  champ.disabled = true;
  try {
    await API.post(`/messagerie/conversations/${id}/messages`, { contenu });
    champ.value = '';
    const nom = document.querySelector('.entete-conversation strong')?.textContent;
    await ouvrirConversation(id, nom);
  } catch (err) {
    toast(err.message || 'Message non envoyé.', 'erreur');
  } finally {
    champ.disabled = false;
    champ.focus();
  }
}

/* Ouvre une conversation avec quelqu'un depuis son profil. */
async function ecrireA(id, nom) {
  try {
    const r = await API.post('/messagerie/conversations',
                             { id_utilisateur: id });
    naviguerApp('messages');
    await rendreMessagerie();
    ouvrirConversation(r.id_conversation, nom);
  } catch (err) {
    toast(err.message || 'Conversation impossible.', 'erreur');
  }
}

function majCompteurMessages(n) {
  const p = document.getElementById('compteur-messages');
  if (!p) return;
  p.textContent = n > 99 ? '99+' : String(n);
  p.hidden = !n;
}

async function chargerCompteurMessages() {
  if (!etat.utilisateur || !etat.utilisateur.email) return;
  try {
    const liste = await API.get('/messagerie/conversations');
    majCompteurMessages(liste.reduce((n, c) => n + (c.non_lus || 0), 0));
  } catch (_) { /* le compteur n'est pas essentiel */ }
}

/* ============================================================
   CONFIRMATION D'ADRESSE PAR CODE
   ============================================================
   L'inscription se terminait sur un message et un lien dans une boîte
   aux lettres. Entre les deux, tout pouvait échouer : l'adresse du
   site, la messagerie qui coupe le lien, le navigateur qui l'ouvre sans
   la session. La confirmation se fait maintenant sur place, avec des
   chiffres recopiés à la main. */

let _adresseAConfirmer = '';

function ouvrirEtapeConfirmation(email) {
  _adresseAConfirmer = email || '';
  const cible = document.getElementById('conf-adresse');
  if (cible) cible.textContent = _adresseAConfirmer;
  const champ = document.getElementById('conf-code');
  if (champ) { champ.value = ''; }
  const retour = document.getElementById('conf-retour');
  if (retour) retour.textContent = '';
  afficherVue('vue-confirmation');
  setTimeout(() => champ?.focus(), 120);
}

/* Un espace après trois chiffres. Six caractères d'affilée se relisent
   mal, et l'on ne sait plus où l'on en est en recopiant. */
function formaterCode(champ) {
  const chiffres = (champ.value || '').replace(/\D/g, '').slice(0, 6);
  champ.value = chiffres.length > 3
    ? chiffres.slice(0, 3) + ' ' + chiffres.slice(3)
    : chiffres;
  // Six chiffres saisis : on valide sans attendre un clic. Personne ne
  // tape un code pour s'arrêter là.
  if (chiffres.length === 6) {
    const bouton = document.querySelector('#vue-confirmation .btn-primaire');
    if (bouton && !bouton.disabled) validerCodeInscription(bouton);
  }
}

async function validerCodeInscription(bouton) {
  const champ = document.getElementById('conf-code');
  const retour = document.getElementById('conf-retour');
  const code = (champ?.value || '').replace(/\D/g, '');
  if (code.length !== 6) {
    if (retour) { retour.style.color = 'var(--rouge-fonce)';
                  retour.textContent = 'Il faut les six chiffres du code.'; }
    champ?.focus();
    return;
  }
  const libelle = bouton.textContent;
  bouton.disabled = true;
  bouton.textContent = 'Vérification…';
  try {
    const r = await API.post('/auth/verifier-code',
                             { email: _adresseAConfirmer, code });
    // Le serveur ouvre la session : saisir le code prouve qu'on relève
    // bien cette adresse, redemander le mot de passe n'ajouterait rien.
    if (r && r.session_ouverte) {
      MODE.utilisateur = await API.get('/profil/moi').catch(() => null);
      if (MODE.utilisateur) appliquerUtilisateur(MODE.utilisateur);
      // Ce que l'accueil guidé avait recueilli part maintenant : il n'y
      // avait pas de session au moment de l'inscription.
      await envoyerProfilEnAttente();
    }
    if (etat.utilisateur) etat.utilisateur.email_verifie = true;
    majRappelConfirmation();
    toast('Adresse confirmée. Bienvenue sur LaSourcee.');
    afficherVue('vue-app');
    initApp();
  } catch (err) {
    if (retour) { retour.style.color = 'var(--rouge-fonce)';
                  retour.textContent = err.message || 'Code refusé.'; }
    champ?.select();
  } finally {
    bouton.disabled = false;
    bouton.textContent = libelle;
  }
}

/* Nouveau code. Le bouton se referme quelques secondes : sans cela on
   le presse trois fois de suite, trois codes partent, et seul le
   dernier vaut quelque chose. Les précédents ayant été effacés, la
   personne saisit celui du premier message et se voit refusée. */
let _attenteNouveauCode = 0;

async function demanderNouveauCode(bouton) {
  const retour = document.getElementById('conf-retour');
  const reste = Math.ceil((_attenteNouveauCode - Date.now()) / 1000);
  if (reste > 0) {
    if (retour) { retour.style.color = 'var(--texte-doux)';
                  retour.textContent = `Patientez ${reste} seconde(s) avant `
                    + 'de redemander un code.'; }
    return;
  }
  bouton.disabled = true;
  const libelle = bouton.textContent;
  bouton.textContent = 'Envoi…';
  try {
    await API.post('/auth/renvoyer-confirmation',
                   { email: _adresseAConfirmer });
    _attenteNouveauCode = Date.now() + 60000;
    if (retour) {
      retour.style.color = 'var(--vert)';
      retour.textContent = 'Un nouveau code vient de partir. Le précédent '
        + "n'est plus valable.";
    }
    _compteARebours(bouton, libelle);
  } catch (err) {
    if (retour) { retour.style.color = 'var(--rouge-fonce)';
                  retour.textContent = err.message || 'Envoi impossible.'; }
    bouton.disabled = false;
    bouton.textContent = libelle;
  }
}

function _compteARebours(bouton, libelle) {
  const tic = () => {
    const reste = Math.ceil((_attenteNouveauCode - Date.now()) / 1000);
    if (reste <= 0) {
      bouton.disabled = false;
      bouton.textContent = libelle;
      return;
    }
    bouton.textContent = `Nouveau code dans ${reste} s`;
    setTimeout(tic, 1000);
  };
  tic();
}

/* Le compte reste utilisable sans confirmation : bloquer quelqu'un qui
   vient de s'inscrire parce qu'un e-mail n'est pas arrivé le ferait
   partir pour de bon. Le rappel subsiste dans l'application. */
async function continuerSansConfirmer() {
  // Sans session, « continuer » menait à une application vide : le
  // compte existe, mais rien ne s'y charge. Dans ce cas on renvoie à la
  // connexion, en le disant.
  const profil = await API.get('/profil/moi').catch(() => null);
  if (!profil) {
    toast('Votre compte est créé. Saisissez le code pour y accéder, ou '
          + 'connectez-vous une fois votre adresse confirmée.');
    afficherVue('vue-connexion');
    const champ = document.getElementById('email-conn');
    if (champ) champ.value = _adresseAConfirmer;
    return;
  }
  MODE.utilisateur = profil;
  appliquerUtilisateur(profil);
  afficherVue('vue-app');
  initApp();
  majRappelConfirmation();
}

/* Saisie du code, atteignable à tout moment depuis la connexion.

   Quelqu'un qui ferme la page après son inscription, ou qui revient le
   lendemain, n'avait aucun chemin vers cet écran : il fallait échouer à
   se connecter pour que l'interface le propose. L'adresse déjà saisie
   dans le formulaire est reprise, pour ne pas la retaper. */
function ouvrirSaisieCode() {
  const saisie = (document.getElementById('email-conn')?.value || '').trim();
  ouvrirEtapeConfirmation(saisie.toLowerCase());
  if (!saisie) {
    const zone = document.getElementById('conf-adresse');
    if (zone) zone.textContent = 'votre adresse';
    // Sans adresse, le code ne peut être rattaché à personne : on la
    // demande avant tout le reste.
    demanderAdresseCode();
  }
}

function demanderAdresseCode() {
  const retour = document.getElementById('conf-retour');
  const adresse = prompt('Quelle adresse e-mail avez-vous utilisée pour '
                         + "vous inscrire ?", '');
  if (adresse === null) { afficherVue('vue-connexion'); return; }
  const propre = adresse.trim().toLowerCase();
  if (!propre.includes('@')) {
    if (retour) { retour.style.color = 'var(--rouge-fonce)';
                  retour.textContent = 'Adresse invalide.'; }
    return;
  }
  _adresseAConfirmer = propre;
  const zone = document.getElementById('conf-adresse');
  if (zone) zone.textContent = propre;
}
