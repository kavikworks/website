"""
Email helper — send emails with attachments via Google Workspace SMTP.

Uses an App Password from your Google Workspace account. This is simpler than
the Gmail API and requires no service account delegation or key files.

Setup (one-time):
  1. Go to myaccount.google.com → Security → 2-Step Verification (must be on)
  2. Search for "App passwords" → create one named "Kavik Intake Pipeline"
  3. Copy the 16-character password into your .env as GMAIL_APP_PASSWORD
"""

import mimetypes
import smtplib
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_email(
    sender: str,
    app_password: str,
    to: str,
    subject: str,
    html_body: str,
    attachments: list[dict] | None = None,
):
    """
    Send an email via Google Workspace SMTP with an App Password.

    Args:
        sender:       The "from" address, e.g. "contact@kavikworks.com"
        app_password: 16-character Google App Password (from GMAIL_APP_PASSWORD env var)
        to:           Recipient address
        subject:      Email subject line
        html_body:    HTML content of the email body
        attachments:  Optional list of {"path": "/path/to/file.pdf", "filename": "report.pdf"}
    """
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject

    msg.attach(MIMEText(html_body, "html"))

    for att in (attachments or []):
        filepath = Path(att["path"])
        filename = att.get("filename", filepath.name)
        content_type, _ = mimetypes.guess_type(str(filepath))
        content_type = content_type or "application/octet-stream"
        main_type, sub_type = content_type.split("/", 1)

        with open(filepath, "rb") as f:
            part = MIMEBase(main_type, sub_type)
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(sender, app_password)
        server.sendmail(sender, to, msg.as_string())
