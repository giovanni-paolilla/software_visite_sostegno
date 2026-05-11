"""
Gestione backup automatici del file dati JSON.

Crea backup con rotazione prima di operazioni distruttive,
e permette il ripristino da backup precedenti.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from .config import BACKUP_DIR, MAX_BACKUPS
from .domain import TurniVisiteError


def create_backup(data_file: str | Path) -> str | None:
    """
    Crea un backup del file dati con timestamp.
    Ritorna il percorso del backup creato, o None se il file sorgente non esiste.
    """
    src = Path(data_file)
    if not src.exists():
        return None

    try:
        with open(src, "r", encoding="utf-8") as f:
            json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.warning("File dati con JSON non valido, backup comunque in corso: %s", e)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(BACKUP_DIR), 0o700)
    except OSError as e:
        logging.warning("Impossibile impostare permessi su backup dir: %s", e)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"dati_turni_{ts}"
    filename = f"{base_name}.json"
    counter = 1
    while (BACKUP_DIR / filename).exists():
        filename = f"{base_name}_{counter:03d}.json"
        counter += 1
    dest = BACKUP_DIR / filename
    shutil.copy2(str(src), str(dest))
    logging.info("Backup creato: %s", dest)

    _rotate_backups()
    return str(dest)


def _rotate_backups() -> None:
    """Mantieni solo gli ultimi MAX_BACKUPS file di backup."""
    if not BACKUP_DIR.exists():
        return
    backups = sorted(BACKUP_DIR.glob("dati_turni_*.json"))
    while len(backups) > MAX_BACKUPS:
        old = backups.pop(0)
        try:
            old.unlink()
            logging.info("Backup vecchio rimosso (rotazione): %s", old.name)
        except OSError as e:
            logging.warning("Impossibile rimuovere backup %s: %s", old, e)


def list_backups() -> list[dict]:
    """Elenca i backup disponibili, dal piu' recente al piu' vecchio."""
    if not BACKUP_DIR.exists():
        return []
    backups = sorted(BACKUP_DIR.glob("dati_turni_*.json"), reverse=True)
    result = []
    for b in backups:
        stat = b.stat()
        result.append({
            "path": str(b),
            "filename": b.name,
            "size_kb": round(stat.st_size / 1024, 1),
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return result


def restore_backup(backup_path: str | Path, data_file: str | Path) -> None:
    """
    Ripristina un backup sovrascrivendo il file dati corrente.
    Crea prima un backup del file attuale come safety net.
    Usa scrittura atomica per evitare corruzione in caso di errore.
    """
    import json

    src = Path(backup_path)
    if not src.exists():
        raise FileNotFoundError(f"Backup non trovato: {src}")

    # Path traversal validation
    resolved = src.resolve()
    backup_dir_resolved = Path(BACKUP_DIR).resolve()
    if not resolved.is_relative_to(backup_dir_resolved):
        raise TurniVisiteError("Percorso backup non valido")

    # JSON validation
    try:
        with open(src, "r", encoding="utf-8") as f:
            json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise TurniVisiteError("File di backup corrotto") from e

    # Safety: backup del file attuale prima del ripristino
    create_backup(data_file)

    # Atomic restore
    data_file = Path(data_file)
    fd, tmp = tempfile.mkstemp(dir=str(data_file.parent), suffix=".tmp")
    try:
        os.close(fd)
        shutil.copy2(str(src), tmp)
        os.replace(tmp, str(data_file))
        os.chmod(str(data_file), 0o600)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

    logging.info("Ripristinato backup da: %s", src)
