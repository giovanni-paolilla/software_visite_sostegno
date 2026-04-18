"""
Gestione backup automatici del file dati JSON.

Crea backup con rotazione prima di operazioni distruttive,
e permette il ripristino da backup precedenti.
"""
from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from .config import BACKUP_DIR, MAX_BACKUPS


def create_backup(data_file: str | Path) -> str | None:
    """
    Crea un backup del file dati con timestamp.
    Ritorna il percorso del backup creato, o None se il file sorgente non esiste.
    """
    src = Path(data_file)
    if not src.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"dati_turni_{ts}.json"
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
        old.unlink()
        logging.info("Backup vecchio rimosso (rotazione): %s", old.name)


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
    """
    src = Path(backup_path)
    if not src.exists():
        raise FileNotFoundError(f"Backup non trovato: {src}")
    # Safety: backup del file attuale prima del ripristino
    create_backup(data_file)
    shutil.copy2(str(src), str(data_file))
    logging.info("Ripristinato backup da: %s", src)
