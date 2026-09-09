#!/usr/bin/env bash
# =====================================================================
# LaSourcee — Script de démarrage
#
# Par défaut : SQLite local, zéro installation serveur requise.
# Le schéma est créé automatiquement au premier lancement ; la base ne
# contient que les référentiels (secteurs, pays), aucun compte factice.
#
# Sous-commandes :
#   ./demarrer.sh             Démarre le serveur (SQLite par défaut)
#   ./demarrer.sh installer   Crée le venv + installe les dépendances Python
#   ./demarrer.sh reset       Supprime la base SQLite et la recharge
#   ./demarrer.sh postgres    Démarre en mode PostgreSQL (DATABASE_URL requis)
#   ./demarrer.sh mysql       Démarre en mode MySQL (DB_TYPE=mysql)
#   ./demarrer.sh tests       Lance toutes les suites de vérification
#   ./demarrer.sh aide        Affiche cette aide
# =====================================================================

set -euo pipefail

VERT='\033[0;32m'; ROUGE='\033[0;31m'; JAUNE='\033[0;33m'; FIN='\033[0m'
ok()   { echo -e "${VERT}✓${FIN} $*"; }
err()  { echo -e "${ROUGE}✗${FIN} $*" >&2; }
info() { echo -e "${JAUNE}→${FIN} $*"; }

DOSSIER="$(cd "$(dirname "$0")" && pwd)"
cd "$DOSSIER"
VENV="$DOSSIER/.venv"
DB_FICHIER="$DOSSIER/lasource.db"

afficher_aide() {
  cat <<'AIDE'
LaSourcee — démarrage en quelques secondes

  ./demarrer.sh installer   (1 fois) crée le venv + installe Flask, etc.
  ./demarrer.sh             démarre le serveur sur http://localhost:5000
  ./demarrer.sh reset       supprime la base et la recrée (perte des données)
  ./demarrer.sh postgres    mode PostgreSQL (DATABASE_URL requis)
  ./demarrer.sh mysql       mode MySQL (nécessite serveur MySQL + .env configuré)
  ./demarrer.sh tests       lance toutes les vérifications (voir plus bas)
  ./demarrer.sh aide        affiche cette aide

Ce que « tests » vérifie :
  rédaction des textes visibles, contraste des couleurs, et les
  198 tests d'intégration sur SQLite. Ajoutez DATABASE_URL pour lancer
  en plus l'intégration sur PostgreSQL et les 70 vérifications de mise
  en ligne :
      DATABASE_URL=postgresql://... ./demarrer.sh tests

Premier lancement (3 commandes suffisent) :
  1. ./demarrer.sh installer
  2. ./demarrer.sh
  3. Ouvrez http://localhost:5000

Créer les comptes administrateurs (une seule fois) :
  cd backend && python gerer_admins.py creer

Les identifiants sont envoyés par e-mail aux quatre administrateurs
et affichés dans la console. Aucun compte de démonstration n'existe :
tous les comptes sont créés par inscription réelle.
AIDE
}

installer() {
  if ! command -v python3 >/dev/null; then
    err "python3 introuvable. Installez Python 3.10+."
    exit 1
  fi
  info "Création de l'environnement virtuel Python..."
  if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
    ok "venv créé"
  else
    info "venv déjà présent"
  fi
  info "Installation des dépendances..."
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -r backend/requirements.txt
  ok "Dépendances installées"
  echo
  echo "Tout est prêt. Lancez maintenant : ./demarrer.sh"
}

reset_sqlite() {
  if [ -f "$DB_FICHIER" ]; then
    info "Suppression de la base : $DB_FICHIER"
    rm -f "$DB_FICHIER"
    ok "Base supprimée — sera recréée au prochain démarrage"
  else
    info "Aucune base à supprimer."
  fi
}

demarrer_sqlite() {
  if [ ! -d "$VENV" ]; then
    err "venv manquant. Lancez d'abord : ./demarrer.sh installer"
    exit 1
  fi

  # Copie automatique du .env.example si .env absent (config par défaut OK)
  if [ ! -f "backend/.env" ]; then
    info "Création de backend/.env (configuration par défaut SQLite)..."
    cp backend/.env.example backend/.env
    ok "backend/.env créé — la config par défaut SQLite est prête"
  fi

  echo
  echo "──────────────────────────────────────────────────────────"
  echo "  LaSourcee — serveur en cours de démarrage"
  echo "  → http://localhost:5000"
  echo "  Base : SQLite ($DB_FICHIER)"
  if [ ! -f "$DB_FICHIER" ]; then
    echo "  Le schéma sera créé automatiquement au démarrage"
  fi
  echo
  echo "  Créez les comptes admin : python gerer_admins.py creer"
  echo
  echo "  Arrêter : Ctrl+C"
  echo "──────────────────────────────────────────────────────────"
  echo
  cd "$DOSSIER/backend"
  export DB_TYPE=sqlite
  exec "$VENV/bin/python" app.py
}

demarrer_postgres() {
  if [ ! -d "$VENV" ]; then
    err "venv manquant. Lancez d'abord : ./demarrer.sh installer"
    exit 1
  fi
  if [ -z "${DATABASE_URL:-}" ] && [ ! -f "backend/.env" ]; then
    err "DATABASE_URL manquant. Exemple :"
    err "  DATABASE_URL=postgresql://user:mdp@hote:5432/lasource ./demarrer.sh postgres"
    exit 1
  fi
  echo
  echo "──────────────────────────────────────────────────────────"
  echo "  LaSourcee — serveur en cours de démarrage"
  echo "  → http://localhost:5000"
  echo "  Base : PostgreSQL"
  echo "──────────────────────────────────────────────────────────"
  echo
  cd "$DOSSIER/backend"
  export DB_TYPE=postgres
  exec "$VENV/bin/python" app.py
}

# Une verification que personne ne lance n'en est pas une. Les quatre
# suites tournent donc ensemble : la redaction et le contraste sont
# instantanes, et ce sont precisement ceux qu'on oublierait.
lancer_tests() {
  if [ ! -d "$VENV" ]; then
    err "venv manquant. Lancez d'abord : ./demarrer.sh installer"
    exit 1
  fi
  cd "$DOSSIER/backend"

  local python="$VENV/bin/python"

  # Les echecs s'accumulent dans une chaine et non un tableau : sous
  # « set -u », lire un tableau vide fait echouer bash 3.2, celui que
  # macOS installe encore par defaut.
  ECHECS=""

  lancer() {                     # $1 = libelle, reste = commande
    local libelle="$1"; shift
    echo
    info "$libelle"
    if "$@"; then
      ok "$libelle"
    else
      err "$libelle : echec"
      ECHECS="$ECHECS
  - $libelle"
    fi
  }

  lancer "Redaction des textes visibles" "$python" tests_redaction.py
  lancer "Contraste des couleurs"        "$python" tests_contraste.py

  # DB_TYPE est impose a chaque appel plutot que laisse a l'environnement.
  # La suite choisit son moteur d'apres cette seule variable et retombe sur
  # SQLite quand elle est absente : un DATABASE_URL exporte donnerait alors
  # deux passages SQLite annonces comme SQLite puis PostgreSQL.
  lancer "Integration (SQLite)" env DB_TYPE=sqlite "$python" tests_integration.py

  # Les deux dernieres exigent une vraie base PostgreSQL. Sans
  # DATABASE_URL on le dit clairement plutot que de faire croire que
  # tout a ete verifie.
  if [ -n "${DATABASE_URL:-}" ]; then
    lancer "Integration (PostgreSQL)" env DB_TYPE=postgres "$python" tests_integration.py
    lancer "Mise en ligne"            "$python" tests_deploiement.py
  else
    echo
    info "PostgreSQL non verifie : definissez DATABASE_URL pour lancer"
    info "les suites PostgreSQL et de mise en ligne."
  fi

  echo
  echo "──────────────────────────────────────────────────────────"
  if [ -z "$ECHECS" ]; then
    ok "Toutes les suites lancees sont passees."
  else
    err "Suites en echec :$ECHECS"
    exit 1
  fi
}

demarrer_mysql() {
  if [ ! -f "backend/.env" ]; then
    err "backend/.env manquant. Copiez backend/.env.example, mettez DB_TYPE=mysql et configurez DB_PASSWORD."
    exit 1
  fi
  cd "$DOSSIER/backend"
  export DB_TYPE=mysql
  exec "$VENV/bin/python" app.py
}

case "${1:-demarrer}" in
  installer)       installer ;;
  reset|reset-db)  reset_sqlite ;;
  postgres|pg)     demarrer_postgres ;;
  tests|test)      lancer_tests ;;
  mysql)           demarrer_mysql ;;
  aide|--help|-h)  afficher_aide ;;
  demarrer|"")     demarrer_sqlite ;;
  *)
    err "Sous-commande inconnue : $1"
    afficher_aide; exit 1 ;;
esac
