/* =========================================================
   LaSourcee — Logique applicative (vanilla JS)
   ========================================================= */

/* ---------- État global ---------- */
const etat = {
  utilisateur: {
    prenom: 'Marie', nom: 'Dupont', initiales: 'MD',
    role: 'etudiant', pays: 'France', etudes: 'Master 2 — Sciences Po Paris',
    bio: "Étudiante curieuse, passionnée par la finance durable et l'entrepreneuriat à impact.",
    secteurs: ['Finance', 'Entrepreneuriat', 'Technologie'],
    estAdmin: true,
    questionsPosees: 12, mentorsSuivis: 5,
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
function avatarHTML(initiales, taille = '', photo = null, mentorVerifie = false) {
  const cls = 'avatar' + (taille ? ' avatar-' + taille : '') + (mentorVerifie ? ' mentor-verifie' : '');
  if (photo) return `<div class="${cls}"><img src="${photo}" class="photo-avatar" alt=""></div>`;
  return `<div class="${cls}">${initiales}</div>`;
}
/* Badge mentor vérifié (innovation : couleur vert du logo, lecture immédiate) */
function badgeMentorVerifie() {
  return `<span class="badge-mentor-verifie">${ic('check','ic ic-s')} Mentor vérifié</span>`;
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
  tendance:   '<path d="M3.5 16.5 9 11l3.5 3.5L20 7"/><path d="M16 7h4v4"/>',
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
  if (panneau === 'fil') rendreFil();
  if (panneau === 'profil') rendreProfil();
  if (panneau === 'mentor') rendreEspaceMentor();
  if (panneau === 'parametres') changerPanParam(document.querySelector('#menu-param button.actif'), 'compte');
  if (panneau === 'admin') changerPanAdmin(document.querySelector('.menu-admin button.actif'), 'dashboard');
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
    toast(err.message || 'Identifiants incorrects.', 'erreur');
  }
}

/* ----- Connexion OAuth Google -----
   Utilise Google Identity Services (chargé dans index.html).
   Demande un ID token, puis l'envoie au backend pour vérification. */
async function connecterGoogle() {
  const clientId = window.GOOGLE_CLIENT_ID;
  if (!clientId) {
    return toast(
      'Google OAuth non configuré. Ajoutez GOOGLE_CLIENT_ID dans backend/.env '
      + '(voir README).', 'erreur'
    );
  }
  if (!window.google || !window.google.accounts) {
    return toast('Bibliothèque Google non chargée. Vérifiez votre connexion.', 'erreur');
  }
  window.google.accounts.id.initialize({
    client_id: clientId,
    callback: async (reponse) => {
      try {
        await API.post('/auth/google', { credential: reponse.credential });
        SESSION.utilisateur = await API.get('/profil/moi');
        appliquerUtilisateur(SESSION.utilisateur);
        toast('Connexion Google réussie.');
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
  };
  majRappelMotDePasse();
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

  etat.etapeOnboarding = 1;
  majEtapeOnboarding();
  afficherVue('vue-onboarding');
  remplirSelectPays();
}
async function naviguerEtape(delta) {
  // Validation des champs OBLIGATOIRES avant d'avancer
  if (delta > 0 && !validerEtapeOnboarding(etat.etapeOnboarding)) return;

  const nouv = etat.etapeOnboarding + delta;
  if (nouv < 1) return;
  if (nouv > 4) {
    const ok = await finaliserInscription();
    if (!ok) return;   // on reste sur l'étape pour corriger
    afficherVue('vue-app'); initApp(); return;
  }
  etat.etapeOnboarding = nouv;
  majEtapeOnboarding();
}

/* Vérifie que les informations obligatoires d'une étape sont remplies. */
function validerEtapeOnboarding(etape) {
  if (etape === 1) {
    const pays = document.querySelector('#etape-1 select')?.value;
    const etudes = (document.querySelector('#etape-1 input')?.value || '').trim();
    if (!pays) { toast('Le pays est obligatoire.', 'erreur'); return false; }
    if (!etudes) { toast('Le niveau d\'études / la profession est obligatoire.', 'erreur'); return false; }
  }
  if (etape === 2) {
    const n = document.querySelectorAll('#etape-2 .chip-select.actif').length;
    if (n < 2) { toast('Choisissez au moins 2 secteurs d\'intérêt.', 'erreur'); return false; }
  }
  return true;
}

/* Crée le compte sur le serveur avec toutes les informations
   collectées à l'inscription puis pendant l'accueil guidé. */
async function finaliserInscription() {
  const prenom = (document.getElementById('prenom-ins')?.value || '').trim();
  const nom = (document.getElementById('nom-ins')?.value || '').trim();
  const email = (document.getElementById('email-ins')?.value || '').trim().toLowerCase();
  const mdp = document.getElementById('mdp-ins')?.value || '';

  // Données collectées pendant l'onboarding
  const secteurs = [...document.querySelectorAll('#etape-2 .chip-select.actif')]
    .map(c => c.textContent.trim().replace(/\s*×$/, '').replace(/^\+\s*Autre$/, '')).filter(Boolean);
  const pays = document.querySelector('#etape-1 select')?.value || '';
  const etudes = (document.querySelector('#etape-1 input')?.value || '').trim();
  const bio = (document.querySelector('#etape-1 textarea')?.value || '').trim();

  try {
    const photoOnboarding = etat.utilisateur && etat.utilisateur.photo;
    await API.post('/auth/inscription', {
      prenom, nom, email, mot_de_passe: mdp,
      role: etat.roleChoisi || 'etudiant',
    });
    MODE.utilisateur = await API.get('/profil/moi');
    if (pays || etudes || bio) {
      await API.put('/profil/moi', { bio, etudes }).catch(() => {});
      MODE.utilisateur = await API.get('/profil/moi');
    }
    appliquerUtilisateur(MODE.utilisateur);
    if (photoOnboarding) etat.utilisateur.photo = photoOnboarding;
    toast('Inscription terminée. Bienvenue sur LaSourcee !');
    return true;
  } catch (err) {
    toast(err.message || 'Inscription impossible.', 'erreur');
    afficherVue('vue-inscription'); return false;
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
  sel.innerHTML = '<option value="">— Sélectionnez votre pays —</option>' +
    LISTE_PAYS.map(p => `<option value="${p}">${p}</option>`).join('');
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
      <div><strong>${u.mentorsSuivis}</strong><span>Mentors suivis</span></div>
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
    console.warn('Annuaire des mentors indisponible :', err.message);
  }
}

function _tempsRelatif(dateIso) {
  if (!dateIso) return '';
  const d = new Date(dateIso);
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return "à l'instant";
  if (sec < 3600) return `il y a ${Math.floor(sec/60)} min`;
  if (sec < 86400) return `il y a ${Math.floor(sec/3600)} h`;
  if (sec < 86400 * 7) return `il y a ${Math.floor(sec/86400)} j`;
  return d.toLocaleDateString('fr-FR');
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
         <span>Résultats pour <strong>« ${echapper(etat.rechercheTerme)} »</strong> — ${liste.length} question(s)</span>
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
        ${avatarHTML(q.initiales, 's')}
        <div class="info"><strong>${echapper(q.auteur)}</strong> · <span>${echapper(q.pays)}</span><time>${echapper(q.temps)}</time></div>
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
         ${ic('etincelle','ic ic-s')} Seuls les mentors peuvent répondre aux questions. Devenez mentor pour partager votre expertise.
       </div>`;
  document.getElementById('contenu-question').innerHTML = `
    <article class="carte-question">
      <div class="q-entete">
        ${avatarHTML(q.initiales, 's')}
        <div class="info"><strong>${echapper(q.auteur)}</strong> · <span>${echapper(q.pays)}</span><time>${echapper(q.temps)}</time></div>
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
    ? `<span class="badge-verifie">${ic('check','ic ic-s')} Mentor vérifié</span>`
    : (r.mentor ? `<span class="badge-mentor badge-role">${ic('trophee','ic ic-s')} Mentor</span>` : '');
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
  if (!estMentor()) return toast('Seuls les mentors peuvent répondre.', 'erreur');
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
    `<li>• <a href="#" onclick="event.preventDefault(); fermerModal('modalPublier'); ouvrirQuestion(${q.id});">${q.titre}</a>
       <span style="color:var(--texte-doux); font-size:12px;"> — ${q.repCount} réponse(s)</span></li>`
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
  if (profilCible) return rendreProfilMentor(profilCible);
  const u = etat.utilisateur;
  const estMentorVerifie = estMentor() && u.verifie;
  const entete = document.getElementById('entete-profil');
  entete.innerHTML = `
    <div class="col-avatar">
      ${avatarHTML(u.initiales, 'xl', u.photo, estMentorVerifie)}
    </div>
    <div class="col-infos">
      <h2>${echapper(u.prenom + ' ' + u.nom)}
        ${estMentorVerifie ? badgeMentorVerifie() : ''}
      </h2>
      <div class="ligne-meta">
        <span class="badge-role">${estMentor() ? ic('trophee','ic ic-s') + ' Mentor' : ic('diplome','ic ic-s') + ' Étudiant'}</span>
        ${u.pays ? `<span>${ic('position','ic ic-s')} ${echapper(u.pays)}</span>` : ''}
        ${u.etudes ? `<span>${ic('ecole','ic ic-s')} ${echapper(u.etudes)}</span>` : ''}
      </div>
      <div class="tags-profil">
        ${u.secteurs.map(s => `<span class="tag">${echapper(s)}</span>`).join('')}
      </div>
      ${u.bio ? `<p class="bio-profil">${echapper(u.bio)}</p>` : ''}
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
      <span class="stat-label">Mentors suivis</span>
    </div>
    ${estMentor() ? `<div class="stat-item accent">
      <span class="stat-valeur">12</span>
      <span class="stat-label">Réponses publiées</span>
    </div>` : ''}`;
  document.getElementById('tabs-profil').innerHTML = `
    <div class="tab-profil actif" onclick="ongletProfil(this, 'questions')">Mes questions</div>
    <div class="tab-profil" onclick="ongletProfil(this, 'sauvees')">Questions sauvegardées</div>
    <div class="tab-profil" onclick="ongletProfil(this, 'mentors')">Mentors suivis</div>`;
  ongletProfil(document.querySelector('.tab-profil.actif'), 'questions');
}
function ongletProfil(elem, t) {
  document.querySelectorAll('.tab-profil').forEach(o => o.classList.remove('actif'));
  elem.classList.add('actif');
  const c = document.getElementById('contenu-profil');
  if (t === 'questions') {
    c.innerHTML = questions.slice(0,3).map(q => carteQuestionHTML(q)).join('');
  } else if (t === 'sauvees') {
    const liste = questions.filter(q => etat.sauvegardees.has(q.id));
    c.innerHTML = liste.length
      ? liste.map(q => carteQuestionHTML(q)).join('')
      : `<div class="etat-vide carte"><div class="illu">${ic('marque','ic ic-l')}</div><h3>Aucune question sauvegardée</h3><p>Sauvegardez les questions intéressantes pour les retrouver ici.</p></div>`;
  } else {
    const ids = [...etat.suivis];
    const suiv = ids.length ? mentors.filter(m => etat.suivis.has(m.id)) : mentors.slice(0, 4);
    c.innerHTML = `<div class="carte"><div class="carte-titre">Mes mentors suivis</div>${suiv.map(m => `
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
        <span class="badge-role badge-mentor">${ic('trophee','ic ic-s')} Mentor</span>
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
   et questions sans réponse dans les secteurs d'expertise du mentor.
   ============================================================ */
function rendreEspaceMentor() {
  const u = etat.utilisateur;
  const c = document.getElementById('contenu-mentor');

  if (u.role !== 'mentor') {
    c.innerHTML = `
      <div class="etat-vide carte" style="text-align:center;">
        <div class="illu">${ic('trophee','ic ic-l')}</div>
        <h3>Devenez mentor vérifié</h3>
        <p>Partagez votre expérience professionnelle avec les étudiants.
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
          <h2>Espace mentor</h2>
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
          badge <b>Mentor vérifié</b> apparaîtra sur vos réponses une fois la
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
        <h2>Espace mentor</h2>
        <p style="color:var(--texte-doux);">Suivez votre activité et repérez les étudiants à aider.</p>
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
        <h2>Devenir mentor vérifié</h2>
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
        <label for="cm-motivation">Pourquoi souhaitez-vous mentorer ? <span class="obligatoire">*</span></label>
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
function rechercher(terme) {
  const drop = document.getElementById('dropRech');
  if (!terme || terme.length < 2) { drop.classList.remove('ouvert'); return; }
  const t = terme.toLowerCase();
  const mres = mentors.filter(m => (m.prenom+' '+m.nom+' '+m.secteur).toLowerCase().includes(t));
  const qres = questions.filter(q => q.titre.toLowerCase().includes(t) || q.secteur.toLowerCase().includes(t));
  let html = '';
  if (mres.length) {
    html += '<h5>Mentors</h5>';
    html += mres.slice(0,4).map(m => `<div class="item-resultat" onmousedown="ouvrirProfilMentor(${m.id}); document.getElementById('dropRech').classList.remove('ouvert');">${avatarHTML(m.initiales, 's')}<div><strong>${echapper(m.prenom + ' ' + m.nom)}</strong><div style="font-size:12px; color:var(--texte-doux);">${echapper(m.secteur + ' · ' + m.pays)}</div></div></div>`).join('');
  }
  if (qres.length) {
    html += '<h5>Questions</h5>';
    html += qres.slice(0,4).map(q => `<div class="item-resultat" onmousedown="ouvrirQuestion(${q.id}); document.getElementById('dropRech').classList.remove('ouvert');">${ic('bulle','ic ic-s')} ${echapper(q.titre)}</div>`).join('');
  }
  if (!html) html = '<div style="padding:14px; color:var(--texte-doux); font-size:14px;">Aucun résultat</div>';
  html += `<div style="padding:10px 14px; border-top:1px solid var(--bordure); text-align:right;">
    <button class="btn btn-primaire btn-petit" onmousedown="lancerRecherche()">Voir tous les résultats →</button>
  </div>`;
  drop.innerHTML = html;
  drop.classList.add('ouvert');
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
  if (p === 'compte') c.innerHTML = panneauCompte();
  if (p === 'notifs') c.innerHTML = panneauNotifsParam();
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
    <div class="champ"><label>Pays</label>
      <select id="pc-pays"><option value="">— Sélectionnez votre pays —</option>${optsPays}</select>
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

function panneauNotifsParam() {
  const lignes = [
    ['Nouvelle réponse à mes questions', true],
    ['Réactions sur mes publications', true],
    ['Nouvelles questions dans mes secteurs', false],
    ['Réponses des mentors que je suis', true],
    ['Newsletter hebdomadaire', false],
  ];
  return `<div class="section-param"><h2>Notifications</h2>
    <h3 style="font-family:'DM Sans'; font-size:14px; margin:14px 0 4px; color:var(--texte-doux);">Dans l'application</h3>
    ${lignes.map(([l, on]) => `<div class="ligne-toggle"><div><strong>${l}</strong></div><div class="toggle ${on?'on':''}" onclick="this.classList.toggle('on'); toast('Préférence mise à jour.')"></div></div>`).join('')}
    <h3 style="font-family:'DM Sans'; font-size:14px; margin:20px 0 4px; color:var(--texte-doux);">Par e-mail</h3>
    ${lignes.slice(0,3).map(([l, on]) => `<div class="ligne-toggle"><div><strong>${l}</strong></div><div class="toggle ${on?'on':''}" onclick="this.classList.toggle('on'); toast('Préférence mise à jour.')"></div></div>`).join('')}
  </div>`;
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
  return `<div class="section-param"><h2>Confidentialité</h2>
    <p class="desc" style="margin-bottom:16px;">
      Ce que LaSourcee fait de vos données, en clair.</p>

    <div class="ligne-session"><div>
      <strong>Votre profil</strong>
      <div class="desc">Prénom, nom, photo, présentation et domaines sont
        visibles par les membres connectés. Votre adresse e-mail ne l'est
        jamais.</div></div></div>

    <div class="ligne-session"><div>
      <strong>Cookies</strong>
      <div class="desc">Un seul cookie est déposé, celui de votre session.
        Aucun traceur publicitaire, aucun partage avec des tiers.</div></div></div>

    <div class="ligne-session"><div>
      <strong>Vos publications</strong>
      <div class="desc">Questions et réponses sont publiques : c'est ce qui
        permet à d'autres d'en profiter. Vous pouvez supprimer les vôtres à
        tout moment.</div></div></div>

    <div class="ligne-session"><div>
      <strong>Suppression du compte</strong>
      <div class="desc">Écrivez à un administrateur : le compte et les
        données associées sont effacés.</div></div></div>
  </div>`;
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
    ['trophee', 'Mentors',          d.mentors],
    ['bouclier','Administrateurs',  d.admins],
    ['bulle',   'Questions',        d.questions],
    ['etincelle','Réponses',        d.reponses],
    ['drapeau', 'Signalements ouverts', d.signalements_ouverts],
    ['check',   'Mentors à vérifier',   d.mentors_a_verifier],
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
  return `<h2 style="margin-bottom:18px;">Gestion des utilisateurs (${liste.length})</h2>
    <table class="tableau">
      <thead><tr><th>Nom</th><th>E-mail</th><th>Rôle</th><th>Statut</th><th>Actions</th></tr></thead>
      <tbody>${liste.map(u => `<tr>
        <td><strong>${echapper(u.prenom)} ${echapper(u.nom)}</strong></td>
        <td>${echapper(u.email)}</td>
        <td><span class="badge-role ${u.role==='mentor'?'badge-mentor':''}">${echapper(u.role)}</span></td>
        <td><span class="tag ${u.est_actif?'tag-vert':'tag-rose'}">${u.est_actif?'actif':'suspendu'}</span></td>
        <td>
          ${u.est_actif
            ? `<button class="btn btn-secondaire btn-petit" onclick="adminAction('suspendre',${u.id_utilisateur})">Suspendre</button>`
            : `<button class="btn btn-secondaire btn-petit" onclick="adminAction('reactiver',${u.id_utilisateur})">Réactiver</button>`}
          <button class="btn btn-fantome btn-petit" onclick="adminChangerRole(${u.id_utilisateur},'${u.role}')">Rôle</button>
          <button class="btn btn-danger btn-petit" onclick="adminAction('supprimer',${u.id_utilisateur})">Supprimer</button>
        </td></tr>`).join('')}</tbody>
    </table>`;
}

/* Action générique sur un utilisateur (suspendre / réactiver / supprimer). */
async function adminAction(action, idUser) {
  const verbes = {
    suspendre: { url: 'POST', chemin: `/admin/utilisateurs/${idUser}/suspendre`, conf: 'Suspendre cet utilisateur ?' },
    reactiver: { url: 'POST', chemin: `/admin/utilisateurs/${idUser}/reactiver`, conf: 'Réactiver cet utilisateur ?' },
    supprimer: { url: 'DELETE', chemin: `/admin/utilisateurs/${idUser}`, conf: 'Supprimer définitivement ?' },
  };
  const v = verbes[action]; if (!v) return;
  if (!confirm(v.conf)) return;
  try {
    await (v.url === 'DELETE' ? API.delete(v.chemin) : API.post(v.chemin, {}));
    toast('Action réalisée.');
    changerPanAdmin(document.querySelector('[data-adm=users]'), 'users');
  } catch (err) { toast(err.message, 'erreur'); }
}

async function adminChangerRole(idUser, roleActuel) {
  const choix = prompt(
    `Rôle actuel : ${roleActuel}\nNouveau rôle ?\n(visiteur / etudiant / mentor / admin / super_admin)`,
    roleActuel
  );
  if (!choix) return;
  try {
    await API.post(`/admin/utilisateurs/${idUser}/role`, { role: choix.trim() });
    toast(`Rôle mis à jour : ${choix.trim()}.`);
    changerPanAdmin(document.querySelector('[data-adm=users]'), 'users');
  } catch (err) { toast(err.message, 'erreur'); }
}
async function adminMentors() {
  if (!MODE.api) return `<div class="carte"><p style="color:var(--texte-doux);">Ce module est disponible lorsque le serveur LaSourcee est connecté.</p></div>`;
  const att = await API.get('/admin/mentors-a-verifier');
  if (!att.length) {
    return `<h2 style="margin-bottom:18px;">Validation des mentors</h2>
      <div class="carte"><p style="color:var(--texte-doux);">
        Aucun mentor en attente de vérification.</p></div>`;
  }
  return `<h2 style="margin-bottom:18px;">Validation des mentors (${att.length})</h2>
    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap:14px;">
      ${att.map(m => {
        const init = ((m.prenom||'?')[0] + (m.nom||'?')[0]).toUpperCase();
        return `<div class="carte"><div style="display:flex; gap:12px; align-items:center;">
          ${avatarHTML(init, 'l')}
          <div><strong>${echapper(m.prenom + ' ' + m.nom)}</strong>
            <div style="color:var(--texte-doux); font-size:13px;">${echapper((m.ville||'') + (m.pays?', '+m.pays:''))}</div></div>
        </div>
        <p style="margin:12px 0; font-size:14px;">${echapper(m.bio || 'Pas de biographie.')}</p>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-primaire btn-petit" onclick="adminMentorAction('verifier',${m.id_utilisateur})">${ic('check','ic ic-s')} Valider</button>
          <button class="btn btn-danger btn-petit" onclick="adminMentorAction('refuser',${m.id_utilisateur})">${ic('croix','ic ic-s')} Refuser</button>
        </div></div>`;
      }).join('')}
    </div>`;
}

async function adminMentorAction(action, idMentor) {
  const conf = action === 'verifier' ? 'Valider ce mentor ?' : 'Refuser ce mentor (rétrograder en étudiant) ?';
  if (!confirm(conf)) return;
  try {
    await API.post(`/admin/mentors/${idMentor}/${action}`, {});
    toast(action === 'verifier' ? 'Mentor validé.' : 'Mentor refusé.');
    changerPanAdmin(document.querySelector('[data-adm=mentors]'), 'mentors');
  } catch (err) { toast(err.message, 'erreur'); }
}
async function adminSignalements() {
  if (!MODE.api) return `<div class="carte"><p style="color:var(--texte-doux);">Ce module est disponible lorsque le serveur LaSourcee est connecté.</p></div>`;
  const liste = await API.get('/admin/signalements?statut=ouvert');
  if (!liste.length) {
    return `<h2 style="margin-bottom:18px;">Signalements</h2>
      <div class="carte"><p style="color:var(--texte-doux);">
        Aucun signalement en attente.</p></div>`;
  }
  return `<h2 style="margin-bottom:18px;">Signalements (${liste.length})</h2>
    ${liste.map(s => `<div class="carte" style="margin-bottom:12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <strong>Signalement #${s.id_signalement}</strong>
        <span class="tag tag-rose">${echapper(s.type_contenu)} #${s.id_contenu}</span>
      </div>
      <p style="color:var(--texte); font-size:14px;">« ${echapper(s.motif || 'Sans motif précisé')} »</p>
      <div style="margin-top:8px; font-size:13px; color:var(--texte-doux);">
        Signalé par <strong>${echapper(s.prenom + ' ' + s.nom)}</strong>
        le ${new Date(s.cree_le).toLocaleDateString('fr-FR')}
      </div>
      <div style="display:flex; gap:8px; margin-top:12px;">
        <button class="btn btn-primaire btn-petit" onclick="adminSignalementAction(${s.id_signalement},'traite')">${ic('check','ic ic-s')} Marquer traité</button>
        <button class="btn btn-fantome btn-petit" onclick="adminSignalementAction(${s.id_signalement},'rejete')">Rejeter</button>
      </div></div>`).join('')}`;
}

async function adminSignalementAction(idSig, decision) {
  try {
    await API.post(`/admin/signalements/${idSig}`, { statut: decision });
    toast('Signalement mis à jour.');
    changerPanAdmin(document.querySelector('[data-adm=signalements]'), 'signalements');
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
    <table class="tableau">
      <thead><tr><th>Date</th><th>Acteur</th><th>Action</th><th>Cible</th><th>Détails</th></tr></thead>
      <tbody>${liste.map(a => `<tr>
        <td>${new Date(a.cree_le).toLocaleString('fr-FR')}</td>
        <td>${echapper(a.prenom + ' ' + a.nom)}</td>
        <td><span class="tag">${echapper(a.action)}</span></td>
        <td>${a.type_cible ? echapper(a.type_cible) + ' #' + a.id_cible : '—'}</td>
        <td style="font-size:12px; color:var(--texte-doux);">${echapper(a.details || '')}</td>
      </tr>`).join('')}</tbody>
    </table>`;
}

/* ============================================================
   TOASTS
   ============================================================ */
function toast(message, type = 'succes') {
  const zone = document.getElementById('zoneToasts');
  const t = document.createElement('div');
  t.className = 'toast' + (type === 'erreur' ? ' erreur' : '');
  t.innerHTML = `<span class="toast-ic">${type === 'erreur' ? ic('alerte','ic ic-s') : ic('check','ic ic-s')}</span><span>${message}</span>`;
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
    + "votre compte LinkedIn, puis réessayez — ou créez un compte avec "
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

  // Contacte le serveur et charge la session courante
  await initialiserApi();
  if (!MODE.api) afficherServeurIndisponible();

  // Charge la configuration OAuth publique (Client ID Google + flag LinkedIn)
  try {
    const cfg = MODE.api ? await API.get('/auth/config')
                         : { google_client_id: '', linkedin_configure: false };
    window.GOOGLE_CLIENT_ID = cfg.google_client_id || null;
    window.LINKEDIN_CONFIGURE = !!cfg.linkedin_configure;
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

  // Toujours afficher la page de bienvenue au chargement, sauf si l'URL
  // contient `#app` (alors on bascule directement dans l'application si
  // une session est encore active).
  const veutApp = window.location.hash === '#app';
  if (MODE.utilisateur && veutApp) {
    appliquerUtilisateur(MODE.utilisateur);
    afficherVue('vue-app');
    initApp();
  } else {
    afficherVue('vue-accueil');
  }
});

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
