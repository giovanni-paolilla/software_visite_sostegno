"""
Modulo notifiche per invio turni via email.

Utilizza smtplib (libreria standard Python) per inviare email
con il piano turni ai fratelli assegnati.

Configurazione SMTP tramite settings del repository:
- smtp_host, smtp_port, smtp_user, smtp_from
- email_fratelli: {fratello: email}

La password SMTP viene letta SOLO dalla variabile d'ambiente
TURNI_SMTP_PASSWORD (mai dal JSON per motivi di sicurezza).
"""
from __future__ import annotations

import logging
import os
import re
import smtplib
import socket
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .repository import JsonRepository


MAX_EMAILS = 100

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_smtp_config(repo: "JsonRepository") -> dict:
    password = os.environ.get("TURNI_SMTP_PASSWORD", "")
    if not password:
        logging.warning(
            "TURNI_SMTP_PASSWORD non impostata. "
            "Imposta la variabile d'ambiente per abilitare l'invio email."
        )
    return {
        "host": os.environ.get("TURNI_SMTP_HOST") or repo.get_setting("smtp_host", ""),
        "port": int(os.environ.get("TURNI_SMTP_PORT", 0)) or int(repo.get_setting("smtp_port", 587)),
        "user": os.environ.get("TURNI_SMTP_USER") or repo.get_setting("smtp_user", ""),
        "password": password,
        "from": repo.get_setting("smtp_from", ""),
    }


def _get_email_fratelli(repo: "JsonRepository") -> dict[str, str]:
    return repo.get_setting("email_fratelli", {})


def _build_message_for_brother(
    fratello: str,
    mesi: list[str],
    solution: dict,
    frequenze: dict[str, int],
    congregazione: str = "Congregazione",
) -> str:
    """Costruisce il testo email per un singolo fratello."""
    lines = [
        f"Caro {fratello},",
        "",
        "ti comunichiamo le tue assegnazioni per le visite di sostegno:",
        "",
    ]
    for mese in sorted(mesi):
        blocco = solution.get("by_month", {}).get(mese)
        if not blocco:
            continue
        fams = blocco.get("by_brother", {}).get(fratello, [])
        if fams:
            lines.append(f"  Mese {mese}:")
            for fam in fams:
                lines.append(f"    - {fam}")
            lines.append("")

    lines.extend([
        "Grazie per la tua disponibilita'.",
        "",
        congregazione,
        "(messaggio automatico)",
    ])
    return "\n".join(lines)


def send_notifications(
    repo: "JsonRepository",
    mesi: list[str],
    solution: dict,
    pdf_path: str | Path | None = None,
) -> dict:
    """
    Invia email ai fratelli con le loro assegnazioni.

    Ritorna: {inviati: [str], errori: [{fratello, errore}], non_configurati: [str]}
    """
    smtp_cfg = _get_smtp_config(repo)
    if not smtp_cfg["host"] or not smtp_cfg["user"]:
        return {
            "inviati": [],
            "errori": [{"fratello": "", "errore": "SMTP non configurato. Imposta smtp_host e smtp_user nelle settings."}],
            "non_configurati": [],
        }

    email_map = _get_email_fratelli(repo)
    result: dict = {"inviati": [], "errori": [], "non_configurati": []}
    frequenze = {fam: repo.frequenze.get(fam, 2) for fam in repo.famiglie}
    congregazione = repo.get_setting("nome_congregazione", "Congregazione")

    if pdf_path:
        p = Path(pdf_path)
        if not p.exists() or p.suffix.lower() != ".pdf":
            pdf_path = None

    # Identifica fratelli con assegnazioni
    fratelli_con_visite: set[str] = set()
    for mese in mesi:
        blocco = solution.get("by_month", {}).get(mese, {})
        for fr, fams in blocco.get("by_brother", {}).items():
            if fams:
                fratelli_con_visite.add(fr)

    if len(fratelli_con_visite) > MAX_EMAILS:
        return {"inviati": [], "errori": [{"fratello": "", "errore": f"Troppi destinatari (max {MAX_EMAILS})"}], "non_configurati": []}

    if not fratelli_con_visite:
        return result

    try:
        context = ssl.create_default_context()
        host = smtp_cfg["host"]
        port = smtp_cfg["port"]
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15, context=context)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls(context=context)
        server.login(smtp_cfg["user"], smtp_cfg["password"])
    except Exception as e:
        logging.error("Connessione SMTP fallita: %s", e)
        return {
            "inviati": [],
            "errori": [{"fratello": "", "errore": f"Connessione SMTP fallita: {e}"}],
            "non_configurati": [],
        }

    try:
        for fratello in sorted(fratelli_con_visite):
            email = email_map.get(fratello)
            if not email:
                result["non_configurati"].append(fratello)
                continue

            if not _EMAIL_RE.match(email) or "\r" in email or "\n" in email:
                result["errori"].append({"fratello": fratello, "errore": "Indirizzo email non valido"})
                continue

            try:
                body = _build_message_for_brother(fratello, mesi, solution, frequenze, congregazione)
                msg = MIMEMultipart()
                msg["From"] = smtp_cfg["from"] or smtp_cfg["user"]
                msg["To"] = email
                msg["Subject"] = f"Turni visite - {', '.join(mesi)}"
                msg.attach(MIMEText(body, "plain", "utf-8"))

                # Allega PDF se disponibile
                if pdf_path and Path(pdf_path).exists():
                    with open(pdf_path, "rb") as f:
                        pdf_attach = MIMEApplication(f.read(), _subtype="pdf")
                        pdf_attach.add_header(
                            "Content-Disposition", "attachment",
                            filename=Path(pdf_path).name,
                        )
                        msg.attach(pdf_attach)

                server.send_message(msg)
                result["inviati"].append(fratello)
                masked = email[:3] + "***" if len(email) > 3 else "***"
                logging.info("Email inviata a %s (%s)", fratello, masked)
            except Exception as e:
                result["errori"].append({"fratello": fratello, "errore": str(e)})
                logging.error("Errore invio email a %s: %s", fratello, e)
    finally:
        try:
            server.quit()
        except Exception:
            pass

    return result
