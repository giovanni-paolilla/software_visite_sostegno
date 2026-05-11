import logging
import logging.handlers
import os
from pathlib import Path

LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3


def setup_logging() -> None:
    from .config import PROJECT_DIR

    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    root = logging.getLogger()

    for h in list(root.handlers):
        root.removeHandler(h)

    level_name = os.environ.get("TURNI_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)

    log_dir = PROJECT_DIR / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / "turni_visite.log")
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(handler)
        logging.debug("Logger inizializzato su file: %s", log_file)
    except OSError:
        for h in root.handlers[:]:
            root.removeHandler(h)
            h.close()
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(handler)
        logging.warning(
            "Impossibile creare la directory di log '%s'. Uso stderr come fallback.", log_dir
        )
