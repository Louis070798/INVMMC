"""Gui email qua SMTP (stdlib smtplib, khong can them dependency).

Cau hinh SMTP uu tien lay tu bang integration_configs (key="email", sua duoc
qua tab Integrations tren dashboard); rong thi lay gia tri mac dinh trong
.env/Settings. Neu ca hai deu rong (SMTP_HOST trong), khong gui that ma chi
log noi dung ra console - de flow quen mat khau van test duoc khong can
tai khoan SMTP that.
"""

from __future__ import annotations

import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from invmmc.core.config import settings


def effective_smtp_config() -> dict[str, Any]:
    from invmmc.core.database import SessionLocal
    from invmmc.persistence.models import IntegrationConfigModel

    config: dict[str, Any] = {
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_username": settings.smtp_username,
        "smtp_password": settings.smtp_password,
        "smtp_from_email": settings.smtp_from_email,
        "smtp_from_name": settings.smtp_from_name,
        "smtp_use_tls": settings.smtp_use_tls,
    }
    with SessionLocal() as db:
        row = db.get(IntegrationConfigModel, "email")
        if row:
            stored = json.loads(row.config_json or "{}")
            for key, value in stored.items():
                if value not in (None, ""):
                    config[key] = value
    return config


def send_email(to_email: str, subject: str, body_text: str) -> None:
    config = effective_smtp_config()
    if not config["smtp_host"]:
        print(f"[email_sender] SMTP chua cau hinh - log thay vi gui that.\nTo: {to_email}\nSubject: {subject}\n{body_text}")
        return

    message = MIMEMultipart()
    from_email = config["smtp_from_email"] or config["smtp_username"]
    message["From"] = f"{config['smtp_from_name']} <{from_email}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body_text, "plain", "utf-8"))

    with smtplib.SMTP(config["smtp_host"], int(config["smtp_port"]), timeout=15) as server:
        if config["smtp_use_tls"]:
            server.starttls()
        if config["smtp_username"]:
            server.login(config["smtp_username"], config["smtp_password"])
        server.sendmail(from_email, [to_email], message.as_string())


def build_reset_password_email(reset_link: str) -> tuple[str, str]:
    subject = "Dat lai mat khau INVMMC Finance"
    body = (
        "Chao ban,\n\n"
        "He thong nhan duoc yeu cau dat lai mat khau cho tai khoan INVMMC Finance cua ban.\n"
        f"Nhan vao lien ket sau de dat mat khau moi (hieu luc trong 30 phut):\n\n{reset_link}\n\n"
        "Neu ban khong yeu cau dieu nay, hay bo qua email nay - mat khau cua ban van an toan.\n\n"
        "Tran trong,\nINVMMC Finance"
    )
    return subject, body
