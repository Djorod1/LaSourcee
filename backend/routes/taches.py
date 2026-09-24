"""Tâches déclenchées par l'ordonnanceur de l'hébergeur.

Un hébergement serverless n'exécute rien de lui-même : il n'y a ni
démon, ni crontab, ni processus qui survit à une requête. Ce qui doit
arriver régulièrement arrive donc par un appel HTTP que la plateforme
déclenche à heure dite (``crons`` dans vercel.json).

Une route publique qui envoie des e-mails est une arme : n'importe qui
la déclencherait en boucle. Elle exige donc un secret partagé, et le
refuse plutôt que de l'ignorer, pour qu'une mauvaise configuration se
voie tout de suite au lieu de passer pour une panne d'envoi.
"""

import hmac
import logging
import os

from flask import Blueprint, jsonify, request

logger = logging.getLogger("lasourcee.taches")

bp_taches = Blueprint("taches", __name__, url_prefix="/api/taches")


def _autorise():
    """Le secret partagé est-il présent et juste ?

    Vercel envoie ``Authorization: Bearer $CRON_SECRET``. On accepte
    aussi un en-tête dédié, pour un ordonnanceur externe qui n'aurait
    pas la même convention.
    """
    attendu = os.getenv("CRON_SECRET") or ""
    if not attendu:
        return False
    entete = request.headers.get("Authorization", "")
    recu = entete[7:] if entete.startswith("Bearer ") else ""
    recu = recu or request.headers.get("X-Cron-Secret", "")
    return bool(recu) and hmac.compare_digest(recu, attendu)


@bp_taches.get("/resume")
@bp_taches.post("/resume")
def resume():
    """Envoie le résumé périodique aux membres qui y ont droit.

    La route n'acceptait que POST. Or l'ordonnanceur de l'hébergeur
    appelle en GET : il aurait reçu « 405 Method Not Allowed » à chaque
    passage, et le résumé ne serait jamais parti en production. Rien ne
    l'aurait signalé — ni erreur, ni e-mail, juste un silence qu'on
    aurait mis des semaines à remarquer, et qu'on aurait d'abord attribué
    au serveur d'envoi. Les deux verbes sont acceptés : GET pour
    l'ordonnanceur, POST pour un déclenchement à la main. Le secret
    partagé protège les deux de la même façon.
    """
    if not _autorise():
        if not os.getenv("CRON_SECRET"):
            logger.warning(
                "Tâche refusée : CRON_SECRET n'est pas défini sur ce "
                "déploiement, aucun résumé ne partira.")
        return jsonify({"erreur": "Tâche non autorisée."}), 403

    # En mode « console », rien ne part vraiment : envoyer des resumes
    # reviendrait a marquer des comptes comme prevenus sans qu'ils
    # l'aient ete, et ils ne le seraient plus avant deux jours.
    if (os.getenv("EMAIL_MODE", "console") or "console").lower() != "smtp":
        return jsonify({"ignore": "EMAIL_MODE n'est pas « smtp »"}), 200

    from services.resume import envoyer_resumes
    try:
        return jsonify(envoyer_resumes())
    except Exception as exc:                 # pragma: no cover
        logger.error("Envoi des résumés interrompu : %s", exc)
        return jsonify({"erreur": "Envoi interrompu."}), 500
