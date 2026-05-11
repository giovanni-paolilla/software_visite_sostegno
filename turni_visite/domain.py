"""
Modelli di dominio e gerarchia di eccezioni.

Questo modulo non importa nulla dal pacchetto per evitare dipendenze circolari.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Gerarchia di eccezioni
# ---------------------------------------------------------------------------

NON_ASSEGNATO = "(non assegnato)"


class TurniVisiteError(Exception):
    """Errore base del dominio — cattura tutte le eccezioni applicative."""


class EntitaNonTrovata(TurniVisiteError):
    """Fratello o famiglia richiesta non esiste nel repository."""


class DuplicatoError(TurniVisiteError):
    """Tentativo di inserire un'entità già presente."""


class ValidazioneError(TurniVisiteError):
    """Dato fornito non supera la validazione di dominio."""


class StoricoConflittoError(TurniVisiteError):
    """Mese già presente nello storico: impossibile sovrascrivere."""


# ---------------------------------------------------------------------------
# Modelli di dominio (usati da service layer e test)
# ---------------------------------------------------------------------------

@dataclass
class Fratello:
    nome: str
    capacita: int = 1

    def __post_init__(self) -> None:
        self.nome = self.nome.strip()
        if not self.nome:
            raise ValidazioneError("Il nome non può essere vuoto")
        if not isinstance(self.capacita, int) or not (0 <= self.capacita <= 50):
            raise ValidazioneError(
                f"Capacita non valida per '{self.nome}': deve essere un intero 0..50."
            )


@dataclass
class Famiglia:
    nome: str
    frequenza: int = 2
    fratelli_associati: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.nome = self.nome.strip()
        if not self.nome:
            raise ValidazioneError("Il nome non può essere vuoto")
        if self.frequenza not in (1, 2, 4):
            raise ValidazioneError(
                f"Frequenza non valida per '{self.nome}': usa 1, 2 o 4."
            )


@dataclass
class AssegnazioneSlot:
    """Singola assegnazione fratello -> famiglia per uno slot mensile."""
    famiglia: str
    fratello: str
    slot: int


@dataclass
class SolverResult:
    """
    Risultato del solver OR-Tools.

    - ``feasible``: True se il solver ha trovato almeno una soluzione.
    - ``solution``: dizionario ``{by_month: {mese: {by_family, by_brother}}}``
      prodotto da ``ottimizza_turni_mesi``; None se infeasible.
    - ``warnings``: messaggi diagnostici (es. preferenze ignorate per fattibilita').
    - ``affinita_ignorate``: True se la soluzione e' stata trovata scartando
      le preferenze di affinita'.
    """
    feasible: bool
    solution: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    affinita_ignorate: bool = False


@dataclass
class AuditEvent:
    """Singolo evento di audit trail."""
    timestamp: str
    azione: str
    dettagli: str
    utente: str = "sistema"


@dataclass
class VincoloPersonalizzato:
    """Vincolo personalizzato tra due fratelli."""
    fratello_a: str
    fratello_b: str
    tipo: str  # "incompatibile" | "preferenza_coppia"
    descrizione: str = ""


@dataclass
class AffinitaFamiglia:
    """Affinita' fratello-famiglia: peso positivo = preferenza, negativo = evitare."""
    famiglia: str
    fratello: str
    peso: int  # -10..+10

    def __post_init__(self) -> None:
        if not isinstance(self.peso, int) or not (-10 <= self.peso <= 10):
            raise ValidazioneError(
                f"Peso affinita' deve essere un intero tra -10 e +10, ricevuto: {self.peso}"
            )


STATO_BOZZA_PROPOSTO = "proposto"
STATO_BOZZA_ACCETTATO = "accettato"
STATO_BOZZA_RIFIUTATO = "rifiutato"

STATO_ESECUZIONE_PIANIFICATO = "pianificato"
STATO_ESECUZIONE_COMPLETATO = "completato"
STATO_ESECUZIONE_ANNULLATO = "annullato"
