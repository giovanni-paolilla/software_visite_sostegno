"""
Modulo notifiche per invio turni via email.

Utilizza smtplib (libreria standard Python) per inviare email
con il piano turni ai fratelli assegnati.

Configurazione SMTP tramite settings del repository:
- smtp_host, smtp_port, smtp_user, smtp_password, smtp_from
- email_fratelli: {fratello: email}
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .repository import JsonRepository


def _get_smtp_config(repo: "JsonRepository") -> dict:
    return {
        "host": repo.get_setting("smtp_host", ""),
        "port": int(repo.get_setting("smtp_port", 587)),
        "user": repo.get_setting("smtp_user", ""),
        "password": repo.get_setting("smtp_password", ""),
        "from": repo.get_setting("smtp_from", ""),
    }


def _get_email_fratelli(repo: "JsonRepository") -> dict[str, str]:
    return repo.get_setting("email_fratelli", {})


def _build_message_for_brother(
    fratello: str,
    mesi: list[str],
    solution: dict,
    frequenze: dict[str, int],
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
        "Congregazione Messina-Ganzirri",
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

    # Identifica fratelli con assegnazioni
    fratelli_con_visite: set[str] = set()
    for mese in mesi:
        blocco = solution.get("by_month", {}).get(mese, {})
        for fr, fams in blocco.get("by_brother", {}).items():
            if fams:
                fratelli_con_visite.add(fr)

    try:
        server = smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"])
        server.starttls()
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

            try:
                body = _build_message_for_brother(fratello, mesi, solution, frequenze)
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
                logging.info("Email inviata a %s (%s)", fratello, email)
            except Exception as e:
                result["errori"].append({"fratello": fratello, "errore": str(e)})
                logging.error("Errore invio email a %s: %s", fratello, e)
    finally:
        try:
            server.quit()
        except Exception:
            pass

    return result
