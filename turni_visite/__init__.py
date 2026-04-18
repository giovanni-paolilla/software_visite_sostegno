"""
turni_visite — pianificazione turni di visita con OR-Tools e export PDF.

Versione corrente: vedere ``__version__``.
Entry points:
  - CLI:  ``turni_visite.cli:main``
  - GUI:  ``turni_visite.gui_tk:main``
  - API:  ``turni_visite.api:main``
"""
__version__ = "0.2.0"

__all__ = [
    # Repository e persistenza
    "JsonRepository",
    # Service layer
    "esegui_ottimizzazione",
    "conferma_e_salva_turni",
    "diagnosi_infeasible",
    "quick_check",
    "modifica_assegnazione",
    "open_file",
    # Export
    "export_pdf_mesi",
    "export_csv_mesi",
    # Backup
    "create_backup",
    "list_backups",
    "restore_backup",
    # Stats
    "report_carico_fratelli",
    "calcola_indice_equita",
    # i18n
    "t",
    "set_language",
    # Eccezioni di dominio
    "TurniVisiteError",
    "EntitaNonTrovata",
    "DuplicatoError",
    "ValidazioneError",
    "StoricoConflittoError",
    "SolverResult",
]

from .repository import JsonRepository
from .service import (
    esegui_ottimizzazione, conferma_e_salva_turni, diagnosi_infeasible,
    quick_check, modifica_assegnazione, open_file,
)
from .pdf_export import export_pdf_mesi
from .csv_export import export_csv_mesi
from .backup import create_backup, list_backups, restore_backup
from .stats import report_carico_fratelli, calcola_indice_equita
from .i18n import t, set_language
from .domain import (
    TurniVisiteError,
    EntitaNonTrovata,
    DuplicatoError,
    ValidazioneError,
    StoricoConflittoError,
    SolverResult,
)
