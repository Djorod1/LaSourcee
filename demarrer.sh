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
#   ./demarrer.sh tests       Lance la suite de tests d'intégration
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
  ./demarrer.sh tests       lance la suite de tests d'intégration
  ./demarrer.sh aide        affiche cette aide

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

lancer_tests() {
  if [ ! -d "$VENV" ]; then
    err "venv manquant. Lancez d'abord : ./demarrer.sh installer"
    exit 1
  fi
  cd "$DOSSIER/backend"
  exec "$VENV/bin/python" tests_integration.py
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
