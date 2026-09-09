/* ============================================================
   LaSourcee — Client API
   ------------------------------------------------------------
   Toutes les données proviennent du serveur LaSourcee : comptes,
   questions, réponses, mentors, administration. Il n'existe aucun
   compte de démonstration ni stockage local de substitution — si le
   serveur est injoignable, l'interface le dit clairement plutôt que
   de simuler un fonctionnement.
   ============================================================ */

const API_BASE = '/api';

/* État de la connexion au serveur, déterminé au démarrage. */
const Backend = { verifie: false, disponible: false, raison: '' };

class ApiErreur extends Error {
  constructor(statut, message, donnees) {
    super(message);
    this.statut = statut;
    this.donnees = donnees;
  }
}

const API = {
  async _appel(methode, chemin, corps) {
    const opts = {
      method: methode,
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin',
    };
    if (corps !== undefined && corps !== null) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(corps);
    }

    let reponse;
    try {
      reponse = await fetch(API_BASE + chemin, opts);
    } catch (err) {
      Backend.disponible = false;
      throw new ApiErreur(0,
        "Le serveur LaSourcee est injoignable. Vérifiez votre connexion "
        + "internet, puis réessayez.");
    }

    let donnees = null;
    const type = reponse.headers.get('Content-Type') || '';
    if (type.includes('application/json')) {
      try { donnees = await reponse.json(); } catch { donnees = null; }
    }

    if (!reponse.ok) {
      const message = (donnees && donnees.erreur)
        || _messageParDefaut(reponse.status);
      throw new ApiErreur(reponse.status, message, donnees);
    }
    return donnees;
  },

  get(chemin)          { return this._appel('GET',    chemin); },
  post(chemin, corps)  { return this._appel('POST',   chemin, corps); },
  put(chemin, corps)   { return this._appel('PUT',    chemin, corps); },
  // Un corps est accepté sur DELETE : la suppression d'un compte
  // exige le mot de passe, qui n'a rien à faire dans l'adresse.
  delete(chemin, corps) { return this._appel('DELETE', chemin, corps); },
};

/* Messages lisibles pour les codes HTTP courants. */
function _messageParDefaut(statut) {
  switch (statut) {
    case 401: return "Vous devez être connecté pour effectuer cette action.";
    case 403: return "Vous n'avez pas les droits nécessaires.";
    case 404: return "Ressource introuvable.";
    case 409: return "Cette donnée existe déjà.";
    case 429: return "Trop de tentatives. Patientez quelques minutes.";
    case 500: return "Une erreur interne est survenue. Réessayez plus tard.";
    case 503: return "Ce service n'est pas disponible actuellement.";
    default:  return `Erreur ${statut}.`;
  }
}

/* Session courante, chargée depuis le serveur au démarrage. */
const SESSION = { utilisateur: null };

/* Conservé pour la lisibilité du code applicatif :
   MODE.api indique si le serveur répond. */
const MODE = {
  get api() { return Backend.disponible; },
  get utilisateur() { return SESSION.utilisateur; },
  set utilisateur(v) { SESSION.utilisateur = v; },
};

/* Vérifie que le serveur répond, et retient pourquoi il ne répond pas.
   Sans ce détail, un diagnostic exige d'ouvrir /api/sante à la main. */
async function verifierServeur() {
  Backend.raison = '';
  try {
    const r = await fetch(API_BASE + '/sante', { credentials: 'same-origin' });
    let j = null;
    try { j = await r.json(); } catch { j = null; }

    Backend.disponible = !!(j && j.statut === 'ok');
    if (!Backend.disponible) {
      if (j && j.erreur) {
        Backend.raison = j.erreur;
      } else if (!j) {
        // Réponse non-JSON : la fonction serveur n'a pas été atteinte.
        Backend.raison = "L'API n'est pas déployée sur ce domaine "
          + `(réponse ${r.status} sans contenu JSON).`;
      } else {
        Backend.raison = `Le serveur répond « ${j.statut} ».`;
      }
    }
  } catch (err) {
    Backend.disponible = false;
    Backend.raison = 'Le serveur est injoignable depuis ce navigateur.';
  }
  Backend.verifie = true;
  return Backend.disponible;
}

/* Initialisation appelée une fois au chargement de la page. */
async function initialiserApi() {
  await verifierServeur();
  if (Backend.disponible) {
    try {
      SESSION.utilisateur = await API.get('/profil/moi');
    } catch (err) {
      SESSION.utilisateur = null;   // 401 = simple visiteur, cas normal
    }
  }
  return MODE;
}

/* Bandeau affiché lorsque le serveur ne répond pas. */
function afficherServeurIndisponible() {
  if (document.getElementById('bandeauServeur')) return;
  const b = document.createElement('div');
  b.id = 'bandeauServeur';
  b.className = 'bandeau-serveur';
  b.setAttribute('role', 'alert');
  const detail = Backend.raison ? ' ' + Backend.raison : '';
  b.textContent = '';
  const titre = document.createElement('strong');
  titre.textContent = 'Serveur indisponible.';
  b.appendChild(titre);
  b.appendChild(document.createTextNode(
    " La connexion et l'inscription sont momentanément impossibles."
    + " Réessayez dans quelques instants." + detail));
  document.body.prepend(b);
}
