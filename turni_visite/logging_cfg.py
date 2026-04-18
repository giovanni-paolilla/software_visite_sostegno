import logging
import os
from pathlib import Path


def setup_logging() -> None:
    """
    Configura il logger radice.

    Il file di log e' scritto in <PROJECT_DIR>/logs/turni_visite.log
    (percorso assoluto, indipendente dalla working directory al momento
    dell'avvio). In caso di errore I/O si ricade su stderr.
    """
    from .config import PROJECT_DIR  # import locale per evitare circolarita' all'import del package

    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    root = logging.getLogger()

    # Rimuove handler preesistenti per idempotenza (utile nei test)
    for h in list(root.handlers):
        root.removeHandler(h)

    log_dir = PROJECT_DIR / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / "turni_visite.log")
        logging.basicConfig(filename=log_file, level=logging.DEBUG, format=fmt)
        logging.debug("Logger inizializzato su file: %s", log_file)
    except OSError:
        logging.basicConfig(level=logging.DEBUG, format=fmt)
        logging.warning(
            "Impossibile creare la directory di log '%s'. Uso stderr come fallback.", log_dir
        )
