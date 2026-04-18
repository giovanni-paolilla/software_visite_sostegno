"""
turni_visite — pianificazione turni di visita con OR-Tools e export PDF.

Versione corrente: vedere ``__version__``.
Entry points:
  - CLI:  ``turni_visite.cli:main``
  - GUI:  ``turni_visite.gui_tk:main``
"""
__version__ = "0.1.0"

__all__ = [
    # Repository e persistenza
    "JsonRepository",
    # Service layer
    "esegui_ottimizzazione",
    "conferma_e_salva_turni",
    "diagnosi_infeasible",
    # Export
    "export_pdf_mesi",
    # Eccezioni di dominio
    "TurniVisiteError",
    "EntitaNonTrovata",
    "DuplicatoError",
    "ValidazioneError",
    "StoricoConflittoError",
    "SolverResult",
]

from .repository import JsonRepository
from .service import esegui_ottimizzazione, conferma_e_salva_turni, diagnosi_infeasible
from .pdf_export import export_pdf_mesi
from .domain import (
    TurniVisiteError,
    EntitaNonTrovata,
    DuplicatoError,
    ValidazioneError,
    StoricoConflittoError,
    SolverResult,
)
