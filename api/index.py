"""Point d'entrée serverless — Vercel.

Vercel exécute chaque fichier Python du dossier ``api/`` comme une
fonction sans serveur. Lorsque le module expose une variable ``app``
compatible WSGI, la plateforme l'utilise directement : ce fichier se
contente donc de construire l'application Flask de ``backend/``.

Le routage est décrit dans ``vercel.json`` :
  - ``/api/*``  -> cette fonction (l'URL d'origine est conservée, Flask
                   reçoit bien ``/api/auth/connexion`` par exemple) ;
  - le reste    -> fichiers statiques distribués par le CDN.

Rappel important : sur Vercel le système de fichiers est éphémère et en
lecture seule. La base doit être PostgreSQL (``DB_TYPE=postgres`` +
``DATABASE_URL``) ; un fichier SQLite serait perdu à chaque redémarrage.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_BACKEND = RACINE / "backend"

# Les modules du backend s'importent entre eux à plat (``from config
# import Config``) : le dossier doit donc être dans le chemin de
# recherche avant tout import.
if str(DOSSIER_BACKEND) not in sys.path:
    sys.path.insert(0, str(DOSSIER_BACKEND))

from app import creer_application  # noqa: E402

# Construite une seule fois par instance, réutilisée à chaque requête
# tant que l'instance reste chaude.
app = creer_application()
