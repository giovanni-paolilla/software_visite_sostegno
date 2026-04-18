"""
Strato di servizio (use-cases applicativi).

Contiene la logica condivisa tra CLI e GUI per:
- eseguire il solver
- diagnosticare infeasibility
- salvare i turni confermati nello storico

Nessun output a video: le funzioni ritornano valori o sollevano eccezioni;
e' compito del layer di presentazione (CLI / GUI) gestire la comunicazione
all'utente.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .domain import SolverResult, StoricoConflittoError
from .scheduling import ottimizza_turni_mesi, explain_infeasible

if TYPE_CHECKING:
    from .repository import JsonRepository

_NON_ASSEGNATO = "(non assegnato)"


def esegui_ottimizzazione(
    snap: dict,
    mesi: list[str],
    storico_turni: list[dict],
    cooldown: int,
) -> SolverResult:
    """
    Esegue il solver OR-Tools sullo snapshot corrente.

    Args:
        snap: dizionario prodotto da ``JsonRepository.data_snapshot()``.
        mesi: lista di mesi YYYY-MM da pianificare.
        storico_turni: storico confermato da ``JsonRepository.get_storico_turni()``.
        cooldown: numero di mesi di anti-ravvicinato.

    Returns:
        SolverResult con ``feasible=True`` e ``solution`` valorizzata,
        oppure ``feasible=False`` se il solver non trova soluzione.

    Raises:
        RuntimeError: se ortools non e' installato.
        ValueError: se un mese ha formato errato.
    """
    raw = ottimizza_turni_mesi(
        mesi=mesi,
        fratelli=snap["fratelli"],
        famiglie=snap["famiglie"],
        associazioni=snap["associazioni"],
        frequenze=snap["frequenze"],
        capacita=snap["capacita"],
        storico_turni=storico_turni,
        cooldown_mesi=cooldown,
    )
    if raw is None:
        return SolverResult(feasible=False)
    return SolverResult(feasible=True, solution=raw)


def diagnosi_infeasible(
    snap: dict,
    mesi: list[str],
    storico_turni: list[dict],
    cooldown: int,
) -> str:
    """
    Produce una stringa diagnostica leggibile quando il solver e' infeasible.

    Args:
        snap: dizionario prodotto da ``JsonRepository.data_snapshot()``.
        mesi, storico_turni, cooldown: stessi parametri di ``esegui_ottimizzazione``.
    """
    return explain_infeasible(
        mesi=mesi,
        fratelli=snap["fratelli"],
        famiglie=snap["famiglie"],
        associazioni=snap["associazioni"],
        frequenze=snap["frequenze"],
        capacita=snap["capacita"],
        storico_turni=storico_turni,
        cooldown_mesi=cooldown,
    )


def conferma_e_salva_turni(
    repo: "JsonRepository",
    mesi: list[str],
    solution: dict,
) -> list[str]:
    """
    Salva i turni della soluzione nello storico del repository.

    Args:
        repo: istanza del repository su cui scrivere.
        mesi: lista di mesi da salvare.
        solution: dizionario ``{by_month: ...}`` prodotto dal solver.

    Returns:
        Lista dei mesi effettivamente salvati.

    Raises:
        StoricoConflittoError: se uno o piu' mesi sono gia' nello storico
            (in questo caso non viene salvato nulla).
    """
    duplicati = [m for m in mesi if repo.storico_has_mese(m)]
    if duplicati:
        raise StoricoConflittoError(
            "Mesi gia' presenti nello storico: " + ", ".join(duplicati) + ".\n"
            "Rimuovili prima se vuoi rigenerarli."
        )

    salvati: list[str] = []
    for mese in mesi:
        assegnazioni = _estrai_assegnazioni(mese, solution)
        repo.append_storico_turni(mese, assegnazioni)
        salvati.append(mese)
        logging.info("Turni mese %s salvati nello storico.", mese)
    return salvati


def _estrai_assegnazioni(mese: str, solution: dict) -> list[dict]:
    """Estrae le assegnazioni da una soluzione per un singolo mese."""
    assegnazioni: list[dict] = []
    blocco = solution["by_month"][mese]["by_family"]
    for fam, slots in blocco.items():
        for k, fr in enumerate(slots):
            if fr and fr != _NON_ASSEGNATO:
                assegnazioni.append({"famiglia": fam, "fratello": fr, "slot": k})
    return assegnazioni
