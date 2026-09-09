"""Service d'envoi d'e-mails.

Deux modes, pilotés par la variable d'environnement ``EMAIL_MODE`` :

  - ``console`` (défaut en développement) : le message est écrit dans les
    logs du serveur. Pratique pour tester sans configurer de compte.
  - ``smtp`` : envoi réel via un serveur SMTP (Gmail, Outlook, OVH,
    SendGrid, Mailgun… n'importe quel fournisseur compatible SMTP).

Configuration SMTP (backend/.env) :

    EMAIL_MODE=smtp
    SMTP_HOTE=smtp.gmail.com
    SMTP_PORT=587
    SMTP_UTILISATEUR=votre.adresse@gmail.com
    SMTP_MOTDEPASSE=xxxxxxxxxxxxxxxx      # mot de passe d'application
    SMTP_EXPEDITEUR=LaSourcee <votre.adresse@gmail.com>
    SMTP_SECURITE=starttls                # starttls (587) | ssl (465) | aucune

Pour Gmail il faut impérativement un « mot de passe d'application »
(Compte Google → Sécurité → Validation en 2 étapes → Mots de passe
d'application). Le mot de passe habituel du compte est refusé par Google.
"""

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

logger = logging.getLogger("lasource.email")

# Timeout réseau : évite qu'une requête HTTP reste bloquée si le serveur
# SMTP ne répond pas.
# Volontairement sous la limite de l'hébergeur. Une fonction Vercel est
# interrompue au bout de dix secondes par défaut : avec une attente de
# quinze, un serveur SMTP lent faisait tuer la requête d'inscription
# avant que le code ait pu constater l'échec et le dire. Le compte
# existait, la personne voyait une erreur brute, et aucun message
# n'expliquait pourquoi.
TIMEOUT_SMTP = int(os.getenv("SMTP_TIMEOUT", "8") or 8)


def _port(valeur):
    """Port SMTP, en tolérant les espaces et les valeurs aberrantes."""
    try:
        n = int(str(valeur).strip())
        return n if 1 <= n <= 65535 else 587
    except (TypeError, ValueError):
        return 587


def _securite(valeur, port):
    """Mode de chiffrement, le port tranchant ce que le mot laisse ouvert.

    Le port 465 attend du chiffrement dès la poignée de main, le 587 une
    connexion en clair passée en TLS par STARTTLS. S'y tromper ne
    produit pas une erreur nette : la connexion reste suspendue jusqu'au
    délai d'attente.

    « tls » ne départage rien, les deux camps l'emploient. Sur 465 il ne
    peut désigner que le chiffrement immédiat. Seuls « ssl » et
    « starttls », sans équivoque, sont pris au mot.
    """
    v = (valeur or "").strip().lower()
    if v in ("ssl", "smtps", "tls_implicite"):
        return "ssl"
    if v == "starttls":
        return "starttls"
    # « tls », vide, ou valeur inconnue : le port décide.
    return "ssl" if port == 465 else "starttls"


def _config():
    """Lit la configuration SMTP depuis l'environnement."""
    port = _port(os.getenv("SMTP_PORT", "587"))
    return {
        "mode": (os.getenv("EMAIL_MODE", "console") or "console").strip().lower(),
        "hote": os.getenv("SMTP_HOTE", "").strip(),
        "port": port,
        "utilisateur": os.getenv("SMTP_UTILISATEUR", "").strip(),
        "motdepasse": os.getenv("SMTP_MOTDEPASSE", ""),
        "expediteur": (os.getenv("SMTP_EXPEDITEUR", "").strip()
                       or os.getenv("SMTP_UTILISATEUR", "").strip()),
        "securite": _securite(os.getenv("SMTP_SECURITE"), port),
    }


def configuration_valide():
    """Indique si l'envoi réel est possible (utile pour l'interface admin)."""
    c = _config()
    if c["mode"] != "smtp":
        return False, "EMAIL_MODE n'est pas réglé sur « smtp »."
    manquants = [
        nom for nom, cle in (
            ("SMTP_HOTE", "hote"),
            ("SMTP_UTILISATEUR", "utilisateur"),
            ("SMTP_MOTDEPASSE", "motdepasse"),
        ) if not c[cle]
    ]
    if manquants:
        return False, "Variables manquantes : " + ", ".join(manquants)
    return True, "Configuration SMTP complète."


def _construire_message(destinataire, sujet, corps_texte, corps_html, expediteur):
    msg = EmailMessage()
    msg["Subject"] = sujet
    msg["From"] = expediteur
    msg["To"] = destinataire
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="lasource.app")
    msg.set_content(corps_texte)
    if corps_html:
        msg.add_alternative(corps_html, subtype="html")
    return msg


def envoi_operationnel():
    """L'envoi peut-il réellement atteindre une boîte aux lettres ?

    En développement, le mode console suffit : le message s'affiche dans
    le terminal, sous les yeux de la personne qui teste. En production,
    il part dans un journal que personne ne lit, et l'adresse reste sans
    nouvelle. Les deux cas ne doivent donc pas se répondre pareil.
    """
    if _config()["mode"] == "smtp":
        return configuration_valide()[0]
    from config import Config
    return not Config.EST_PRODUCTION


def envoyer(destinataire, sujet, corps, corps_html=None):
    """Envoie un e-mail. Retourne True si l'envoi a réussi.

    Enveloppe de ``envoyer_detaille`` pour les appelants qui n'ont que
    faire du motif : l'immense majorité.
    """
    return envoyer_detaille(destinataire, sujet, corps, corps_html)[0]


def envoyer_detaille(destinataire, sujet, corps, corps_html=None):
    """Envoie un e-mail et retourne ``(réussi, motif)``.

    Le motif compte au moment de brancher un serveur SMTP : « mot de
    passe refusé » et « hôte injoignable » se corrigent différemment,
    et sur un hébergement serverless les journaux ne sont pas à portée
    de main. Il remonte donc jusqu'à l'écran de diagnostic.

    En mode console, retourne True en développement, où le message
    s'affiche dans le terminal, et False en production, où il n'atteint
    personne. Répondre True partout revenait à annoncer « un message
    vient de partir » à quelqu'un qui n'allait jamais rien recevoir, et
    a laissé des comptes attendre un lien de confirmation inexistant.

    En mode smtp, retourne False si l'envoi échoue. L'appelant décide
    s'il doit alerter l'utilisateur ou rester silencieux (cas des
    réinitialisations de mot de passe, où l'on ne révèle jamais si une
    adresse existe).
    """
    c = _config()

    # ---- Mode console ----------------------------------------------------
    if c["mode"] != "smtp":
        from config import Config
        logger.info(
            "\n──────── E-MAIL (mode console) ────────\n"
            "À      : %s\n"
            "Sujet  : %s\n"
            "Corps  :\n%s\n"
            "───────────────────────────────────────",
            destinataire, sujet, corps,
        )
        if Config.EST_PRODUCTION:
            motif = ("EMAIL_MODE vaut « console » en production : le message "
                     "est écrit dans les journaux, il n'est envoyé à "
                     "personne. Réglez EMAIL_MODE=smtp.")
            logger.error("Message NON distribué à %s : %s", destinataire, motif)
            return False, motif
        return True, ""

    # ---- Mode SMTP (production) -----------------------------------------
    ok, raison = configuration_valide()
    if not ok:
        logger.error("Envoi impossible à %s — %s", destinataire, raison)
        return False, raison

    expediteur = c["expediteur"]
    if "<" not in expediteur:
        expediteur = formataddr(("LaSourcee", expediteur))

    msg = _construire_message(destinataire, sujet, corps, corps_html, expediteur)

    try:
        contexte = ssl.create_default_context()
        if c["securite"] == "ssl":
            with smtplib.SMTP_SSL(c["hote"], c["port"],
                                  context=contexte, timeout=TIMEOUT_SMTP) as serveur:
                serveur.login(c["utilisateur"], c["motdepasse"])
                serveur.send_message(msg)
        else:
            with smtplib.SMTP(c["hote"], c["port"], timeout=TIMEOUT_SMTP) as serveur:
                serveur.ehlo()
                if c["securite"] == "starttls":
                    serveur.starttls(context=contexte)
                    serveur.ehlo()
                serveur.login(c["utilisateur"], c["motdepasse"])
                serveur.send_message(msg)
        logger.info("E-mail envoyé à %s — %s", destinataire, sujet)
        return True, ""

    except smtplib.SMTPAuthenticationError:
        motif = (f"Le serveur a refusé les identifiants de "
                 f"{c['utilisateur']}. Vérifiez SMTP_UTILISATEUR (l'adresse "
                 f"complète) et SMTP_MOTDEPASSE (celui de la boîte aux "
                 f"lettres, pas celui du panneau d'hébergement). Avec "
                 f"Gmail, il faut un mot de passe d'application.")
    except smtplib.SMTPRecipientsRefused:
        motif = f"Le serveur a refusé l'adresse destinataire {destinataire}."
    except (smtplib.SMTPException, OSError) as exc:
        motif = (f"Contact impossible avec {c['hote']}:{c['port']} "
                 f"({type(exc).__name__} : {str(exc)[:120]}). Vérifiez "
                 f"SMTP_HOTE, SMTP_PORT et SMTP_SECURITE : le port 465 va "
                 f"avec « ssl », le port 587 avec « starttls ».")
    logger.error("Échec de l'envoi à %s : %s", destinataire, motif)
    return False, motif


# ---------------------------------------------------------------------------
# Gabarit HTML commun à tous les e-mails de la plateforme
# ---------------------------------------------------------------------------

def gabarit_html(titre, paragraphes, bouton_texte=None, bouton_lien=None,
                 note_bas=None):
    """Construit un e-mail HTML sobre aux couleurs de LaSourcee.

    Les styles sont en ligne : c'est la seule méthode fiable dans les
    clients de messagerie (Gmail supprime les feuilles de style).
    """
    corps = "".join(
        f'<p style="margin:0 0 16px;font-size:15px;line-height:1.6;'
        f'color:#333333;">{p}</p>'
        for p in paragraphes
    )

    bouton = ""
    if bouton_texte and bouton_lien:
        bouton = f"""
        <table role="presentation" cellpadding="0" cellspacing="0"
               style="margin:24px 0;">
          <tr><td style="background:#1F3A5F;border-radius:6px;">
            <a href="{bouton_lien}"
               style="display:inline-block;padding:13px 28px;color:#ffffff;
                      font-size:15px;font-weight:600;text-decoration:none;">
              {bouton_texte}
            </a>
          </td></tr>
        </table>
        <p style="margin:0 0 16px;font-size:13px;color:#777777;">
          Si le bouton ne fonctionne pas, copiez ce lien dans votre
          navigateur :<br>
          <span style="color:#1F3A5F;word-break:break-all;">{bouton_lien}</span>
        </p>"""

    bas = ""
    if note_bas:
        bas = (f'<p style="margin:24px 0 0;font-size:13px;color:#777777;'
               f'border-top:1px solid #e6e6e6;padding-top:16px;">{note_bas}</p>')

    return f"""<!DOCTYPE html>
<html lang="fr"><body style="margin:0;padding:0;background:#f4f2ee;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background:#f4f2ee;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="max-width:560px;background:#ffffff;border-radius:10px;
                    border:1px solid #e2dfd8;overflow:hidden;">
        <tr><td style="background:#1F3A5F;padding:22px 32px;">
          <span style="font-size:21px;font-weight:700;color:#ffffff;
                       letter-spacing:-0.3px;">LaSourc<span
                style="color:#16A34A;">e</span></span>
        </td></tr>
        <tr><td style="padding:32px;">
          <h1 style="margin:0 0 20px;font-size:20px;color:#1a1a1a;
                     font-weight:600;">{titre}</h1>
          {corps}{bouton}{bas}
        </td></tr>
        <tr><td style="background:#faf9f7;padding:18px 32px;
                       border-top:1px solid #e6e6e6;">
          <p style="margin:0;font-size:12px;color:#888888;">
            LaSourcee, la plateforme de mentorat qui connecte étudiants
            et professionnels.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""
