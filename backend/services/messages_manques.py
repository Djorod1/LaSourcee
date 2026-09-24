"""Prévenir par e-mail quelqu'un dont un message privé reste non lu.

Un message privé déposait une notification dans la cloche, et rien de
plus. Quelqu'un qui ne revient pas sur le site ne l'apprenait donc
jamais : sur une plateforme de mise en relation, c'est l'échange lui-même
qui meurt, pas seulement la notification. Un bénéficiaire écrit à un
référent, le référent ne repasse pas de la semaine, et le bénéficiaire
en conclut qu'on ne lui a pas répondu.

Quatre règles, et chacune existe pour une raison précise :

  - **Douze heures de grâce.** On n'écrit pas à quelqu'un qui allait
    voir le message de lui-même. Ce délai distingue « pas encore vu » de
    « raté ». LaSourcee n'est pas une messagerie instantanée : la
    réponse d'un référent n'a pas d'urgence à la minute.
  - **Au plus un e-mail par conversation et par jour.** Un échange vif
    de cinq messages ne doit pas produire cinq e-mails — c'est le plus
    sûr moyen de finir classé indésirable, et d'y emmener tout le
    domaine expéditeur.
  - **Le contenu du message ne part pas.** L'e-mail dit qui a écrit et
    invite à venir lire. Recopier un message privé dans un e-mail, c'est
    le sortir de l'endroit où son auteur a accepté de le mettre.
  - **Un lien de désinscription dans chaque message.** Il ne demande ni
    de se connecter ni de retrouver un réglage.

Le passage est quotidien, à midi heure du Bénin : l'hébergement actuel
n'accorde qu'un déclenchement par jour et par tâche. Avec douze heures
de grâce, ce passage ramasse tout ce qui a été écrit jusqu'à minuit la
veille — autrement dit l'intégralité d'une journée est couverte par le
passage du lendemain. Un message déposé après minuit attend le
surlendemain ; c'est le prix d'un seul passage, et il est assumé : ces
avertissements ne sont pas des notifications instantanées.

Rien ne lève : un avertissement perdu est regrettable, une tâche
interrompue qui laisse la moitié des gens non prévenus l'est davantage.
"""

import logging
from datetime import datetime, timedelta

from models.db import recuperer_tous, executer
from services.resume import jeton_desinscription
from utils.urls import url_publique

logger = logging.getLogger("lasourcee.messages_manques")

# Délai de grâce avant d'écrire. En dessous, on parlerait à quelqu'un
# qui n'a simplement pas encore ouvert son onglet.
DELAI_HEURES = 12

# Jamais deux e-mails pour la même conversation dans la même journée.
#
# Vingt-trois et non vingt-quatre. L'hébergement n'accorde qu'un passage
# par jour : la fenêtre de repos vaudrait alors exactement l'intervalle
# entre deux passages, et l'ordonnanceur ne déclenche pas à la seconde
# près. Un passage avancé de trois secondes trouverait un prevenu_le
# vieux de 23 h 59 min 57 s, jugerait le repos inachevé, et sauterait la
# journée — un avertissement en retard d'un jour, sans rien dans les
# journaux pour le dire. Une heure de marge absorbe cette dérive, et la
# règle tient toujours : un seul passage quotidien ne peut pas écrire
# deux fois.
REPOS_HEURES = 23

# Garde-fou : un envoi en masse sur une fonction sans serveur limitée à
# quelques secondes n'aboutirait pas. Les suivants partent au passage
# suivant, la colonne prevenu_le faisant office de curseur.
MAX_PAR_PASSAGE = 30


def _il_y_a(heures):
    return (datetime.utcnow() - timedelta(hours=heures)
            ).strftime("%Y-%m-%d %H:%M:%S")


def _a_prevenir():
    """Les personnes dont un message reçu dort depuis assez longtemps.

    Une seule requête plutôt qu'une par conversation : la tâche tourne
    sur une base distante, où chaque aller-retour se paie.
    """
    return recuperer_tous(
        """SELECT cp.id_conversation,
                  cp.id_utilisateur,
                  u.prenom, u.email, u.preferences_notif,
                  autre.prenom AS prenom_autre,
                  autre.nom    AS nom_autre,
                  COUNT(m.id_message) AS nb_messages,
                  MAX(m.envoye_le)    AS dernier_le
             FROM conversation_participant cp
             JOIN utilisateur u
               ON u.id_utilisateur = cp.id_utilisateur
              AND u.est_actif = 1
              AND u.email_verifie = 1
             JOIN message m
               ON m.id_conversation = cp.id_conversation
              AND m.id_expediteur <> cp.id_utilisateur
              AND (cp.lu_jusqua IS NULL OR m.envoye_le > cp.lu_jusqua)
             JOIN utilisateur autre
               ON autre.id_utilisateur = m.id_expediteur
            WHERE m.envoye_le <= %s
              AND (cp.prevenu_le IS NULL OR cp.prevenu_le <= %s)
         GROUP BY cp.id_conversation, cp.id_utilisateur,
                  u.prenom, u.email, u.preferences_notif,
                  autre.prenom, autre.nom
         ORDER BY MAX(m.envoye_le) ASC
            LIMIT %s""",
        (_il_y_a(DELAI_HEURES), _il_y_a(REPOS_HEURES), MAX_PAR_PASSAGE),
    )


def _accepte_les_e_mails(preferences_brutes):
    """Cette personne accepte-t-elle d'être prévenue par e-mail ?

    Un réglage jamais touché vaut « oui » : quelqu'un qui reçoit un
    message veut l'apprendre. C'est le décochage qui doit être explicite,
    pas l'acceptation.
    """
    import json
    if not preferences_brutes:
        return True
    try:
        reglages = json.loads(preferences_brutes)
    except (ValueError, TypeError):
        return True
    return bool(reglages.get("email", {}).get("message", True))


def _corps(prenom, qui, nb, lien, lien_stop):
    bonjour = f"Bonjour {prenom}," if prenom else "Bonjour,"
    quoi = ("un message vous attend" if nb == 1
            else f"{nb} messages vous attendent")
    return (
        f"{bonjour}\n\n"
        f"Sur LaSourcee, {quoi} de la part de {qui}.\n\n"
        f"Pour le lire et y répondre :\n{lien}\n\n"
        "Nous ne recopions pas le contenu ici : il reste là où son auteur\n"
        "l'a écrit.\n\n"
        "L'équipe LaSourcee\n\n"
        f"Ne plus recevoir ces avertissements : {lien_stop}"
    )


def _html(prenom, qui, nb, lien, lien_stop):
    from utils.email import gabarit_html
    bonjour = f"Bonjour {prenom}," if prenom else "Bonjour,"
    quoi = ("Un message vous attend" if nb == 1
            else f"{nb} messages vous attendent")
    return gabarit_html(
        "Un message vous attend",
        [bonjour,
         f"Sur LaSourcee, <b>{quoi}</b> de la part de {qui}.",
         "Nous ne recopions pas le contenu ici : il reste là où son "
         "auteur l'a écrit."],
        bouton_texte="Lire le message", bouton_lien=lien,
        note_bas=f'Ne plus recevoir ces avertissements : '
                 f'<a href="{lien_stop}">se désinscrire</a>.',
    )


def prevenir_messages_non_lus():
    """Écrit à ceux dont un message dort depuis plus de douze heures."""
    from utils.email import envoyer

    envoyes, ignores = 0, 0
    for ligne in _a_prevenir():
        if not _accepte_les_e_mails(ligne.get("preferences_notif")):
            ignores += 1
            # On pose quand même le curseur : sans cela, cette
            # conversation serait réexaminée à chaque passage pour rien.
            _marquer(ligne["id_conversation"], ligne["id_utilisateur"])
            continue

        adresse = (ligne.get("email") or "").strip()
        if not adresse:
            ignores += 1
            _marquer(ligne["id_conversation"], ligne["id_utilisateur"])
            continue

        qui = (f"{ligne.get('prenom_autre') or ''} "
               f"{(ligne.get('nom_autre') or '')[:1]}.").strip() or "un membre"
        nb = int(ligne.get("nb_messages") or 1)
        jeton = jeton_desinscription(ligne["id_utilisateur"])
        lien = url_publique("/index.html")
        lien_stop = url_publique(
            f"/api/profil/resume/stop?u={ligne['id_utilisateur']}&j={jeton}")

        parti = envoyer(
            adresse,
            "Un message vous attend sur LaSourcee",
            _corps(ligne.get("prenom"), qui, nb, lien, lien_stop),
            corps_html=_html(ligne.get("prenom"), qui, nb, lien, lien_stop),
        )
        # Le curseur avance dans les deux cas : un serveur d'envoi qui
        # refuse une adresse la refuserait aussi au passage suivant, et
        # la tâche tournerait indéfiniment sur la même ligne.
        _marquer(ligne["id_conversation"], ligne["id_utilisateur"])
        if parti:
            envoyes += 1
        else:
            ignores += 1
            logger.warning("Avertissement de message non remis à %s", adresse)

    return {"envoyes": envoyes, "ignores": ignores}


def _marquer(id_conversation, id_utilisateur):
    """Note qu'on vient de prévenir, pour ne pas y revenir demain."""
    try:
        executer(
            """UPDATE conversation_participant SET prevenu_le = %s
                WHERE id_conversation = %s AND id_utilisateur = %s""",
            (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
             id_conversation, id_utilisateur), commit=True)
    except Exception as exc:                       # pragma: no cover
        logger.warning("Curseur d'avertissement non posé : %s", exc)
