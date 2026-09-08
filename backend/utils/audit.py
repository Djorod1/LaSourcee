"""Journal d'audit des actions admin (table audit_admin).

Appelé via `journaliser(...)` après une action de modération réussie.
Échoue silencieusement si la table n'existe pas encore (compatibilité
descendante avec un schéma v1).
"""

import logging
from flask import request

from models.db import executer

logger = logging.getLogger("lasource.audit")


def journaliser(id_acteur: int, action: str,
                type_cible: str = None, id_cible: int = None,
                details: str = None) -> None:
    try:
        ip = request.remote_addr if request else None
        executer(
            """INSERT INTO audit_admin
                  (id_acteur, action, type_cible, id_cible, details, ip)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (id_acteur, action[:80],
             type_cible[:40] if type_cible else None,
             id_cible,
             details[:500] if details else None,
             ip),
            commit=True,
        )
    except Exception as exc:
        # Ne casse jamais l'opération métier juste parce que l'audit échoue
        logger.warning("Audit non enregistré pour %s : %s", action, exc)
