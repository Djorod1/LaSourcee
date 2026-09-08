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
TIMEOUT_SMTP = 15


def _config():
    """Lit la configuration SMTP depuis l'environnement."""
    return {
        "mode": (os.getenv("EMAIL_MODE", "console") or "console").lower(),
        "hote": os.getenv("SMTP_HOTE", ""),
        "port": int(os.getenv("SMTP_PORT", "587") or 587),
        "utilisateur": os.getenv("SMTP_UTILISATEUR", ""),
        "motdepasse": os.getenv("SMTP_MOTDEPASSE", ""),
        "expediteur": os.getenv("SMTP_EXPEDITEUR", "") or os.getenv("SMTP_UTILISATEUR", ""),
        "securite": (os.getenv("SMTP_SECURITE", "starttls") or "starttls").lower(),
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


def envoyer(destinataire, sujet, corps, corps_html=None):
    """Envoie un e-mail. Retourne True si l'envoi a réussi.

    En mode console, retourne toujours True (le message est journalisé).
    En mode smtp, retourne False si l'envoi échoue — l'appelant décide
    s'il doit alerter l'utilisateur ou rester silencieux (cas des
    réinitialisations de mot de passe, où l'on ne révèle jamais si une
    adresse existe).
    """
    c = _config()

    # ---- Mode console (développement) -----------------------------------
    if c["mode"] != "smtp":
        logger.info(
            "\n──────── E-MAIL (mode console) ────────\n"
            "À      : %s\n"
            "Sujet  : %s\n"
            "Corps  :\n%s\n"
            "───────────────────────────────────────",
            destinataire, sujet, corps,
        )
        return True

    # ---- Mode SMTP (production) -----------------------------------------
    ok, raison = configuration_valide()
    if not ok:
        logger.error("Envoi impossible à %s — %s", destinataire, raison)
        return False

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
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Authentification SMTP refusée pour %s. "
            "Avec Gmail, utilisez un mot de passe d'application, "
            "pas le mot de passe du compte.", c["utilisateur"],
        )
    except smtplib.SMTPRecipientsRefused:
        logger.error("Adresse destinataire refusée : %s", destinataire)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Échec de l'envoi à %s : %s", destinataire, exc)
    return False


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
            LaSourcee — la plateforme de mentorat qui connecte étudiants
            et professionnels.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""
