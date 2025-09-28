# app/services/mailer.py
import smtplib, ssl
from email.message import EmailMessage as MimeEmail
from email.utils import formataddr
from typing import Optional, List
from app_lia_web.core.config import settings

class Attachment:
    def __init__(self, filename: str, content: bytes, mimetype: str = "application/octet-stream"):
        self.filename = filename
        self.content = content
        self.mimetype = mimetype

class EmailContent:
    def __init__(self, subject: str, html: Optional[str] = None, text: Optional[str] = None):
        self.subject = subject
        self.html = html
        self.text = text

class EmailMessage:
    def __init__(self,
                 to: List[str],
                 subject: str,
                 html: Optional[str] = None,
                 text: Optional[str] = None,
                 cc: Optional[List[str]] = None,
                 bcc: Optional[List[str]] = None,
                 attachments: Optional[List[Attachment]] = None,
                 reply_to: Optional[str] = None):
        self.to = to
        self.cc = cc or []
        self.bcc = bcc or []
        self.content = EmailContent(subject=subject, html=html, text=text)
        self.attachments = attachments or []
        self.reply_to = reply_to

class SmtpMailer:
    def send(self, msg: EmailMessage) -> None:
        mime = MimeEmail()
        from_display = formataddr((settings.MAIL_FROM_NAME, settings.MAIL_FROM))
        mime["From"] = from_display
        mime["To"] = ", ".join(msg.to)
        if msg.cc: mime["Cc"] = ", ".join(msg.cc)
        if msg.bcc: mime["Bcc"] = ", ".join(msg.bcc)
        if msg.reply_to: mime["Reply-To"] = msg.reply_to
        mime["Subject"] = msg.content.subject

        # Corps : multipart texte + HTML
        if msg.content.text and msg.content.html:
            mime.set_content(msg.content.text)
            mime.add_alternative(msg.content.html, subtype="html")
        elif msg.content.html:
            mime.add_alternative(msg.content.html, subtype="html")
        elif msg.content.text:
            mime.set_content(msg.content.text)
        else:
            mime.set_content("(vide)")

        # Pièces jointes
        for a in msg.attachments:
            maintype, _, subtype = (a.mimetype.partition("/"))
            mime.add_attachment(
                a.content,
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=a.filename
            )

        # Connexion SMTP
        if settings.SMTP_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context) as server:
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(mime)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.ehlo()
                if settings.SMTP_TLS:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(mime)
