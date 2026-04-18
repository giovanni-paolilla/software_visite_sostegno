"""
Strato di servizio (use-cases applicativi).

Contiene la logica condivisa tra CLI e GUI per:
- eseguire il solver
- diagnosticare infeasibility
- salvare i turni confermati nello storico
- pre-check di fattibilita'
- report di carico

Nessun output a video: le funzioni ritornano valori o sollevano eccezioni;
e' compito del layer di presentazione (CLI / GUI) gestire la comunicazione
all'utente.
"""
from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from .domain import SolverResult, StoricoConflittoError, NON_ASSEGNATO
from .scheduling import ottimizza_turni_mesi, explain_infeasible, pre_check_fattibilita
from .backup import create_backup

if TYPE_CHECKING:
    from .repository import JsonRepository


def esegui_ottimizzazione(
    snap: dict,
    mesi: list[str],
    storico_turni: list[dict],
    cooldown: int,
    solver_timeout: float | None = None,
    solver_workers: int | None = None,
) -> SolverResult:
    """
    Esegue il solver OR-Tools sullo snapshot corrente.

    Args:
        snap: dizionario prodotto da ``JsonRepository.data_snapshot()``.
        mesi: lista di mesi YYYY-MM da pianificare.
        storico_turni: storico confermato da ``JsonRepository.get_storico_turni()``.
        cooldown: numero di mesi di anti-ravvicinato.
        solver_timeout: timeout del solver in secondi (opzionale).
        solver_workers: numero di thread del solver (opzionale).

    Returns:
        SolverResult con ``feasible=True`` e ``solution`` valorizzata,
        oppure ``feasible=False`` se il solver non trova soluzione.
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
        indisponibilita=snap.get("indisponibilita"),
        vincoli_personalizzati=snap.get("vincoli_personalizzati"),
        solver_timeout=solver_timeout,
        solver_workers=solver_workers,
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


def quick_check(
    snap: dict,
    mesi: list[str],
    storico_turni: list[dict],
    cooldown: int,
) -> dict:
    """Pre-check rapido di fattibilita' senza invocare il solver."""
    return pre_check_fattibilita(snap, mesi, storico_turni, cooldown)


def conferma_e_salva_turni(
    repo: "JsonRepository",
    mesi: list[str],
    solution: dict,
) -> list[str]:
    """
    Salva i turni della soluzione nello storico del repository.
    Crea un backup automatico prima del salvataggio.
    """
    duplicati = [m for m in mesi if repo.storico_has_mese(m)]
    if duplicati:
        raise StoricoConflittoError(
            "Mesi gia' presenti nello storico: " + ", ".join(duplicati) + ".\n"
            "Rimuovili prima se vuoi rigenerarli."
        )

    # Backup automatico prima del salvataggio
    create_backup(repo.filename)

    salvati: list[str] = []
    for mese in mesi:
        assegnazioni = _estrai_assegnazioni(mese, solution)
        repo.append_storico_turni(mese, assegnazioni)
        salvati.append(mese)
        logging.info("Turni mese %s salvati nello storico.", mese)
    return salvati


def modifica_assegnazione(
    solution: dict,
    mese: str,
    famiglia: str,
    slot: int,
    nuovo_fratello: str,
) -> dict:
    """
    Modifica manualmente una singola assegnazione nella soluzione.
    Ritorna la soluzione aggiornata.
    """
    if "by_month" not in solution or mese not in solution["by_month"]:
        raise ValueError(f"Mese {mese} non trovato nella soluzione.")
    blocco = solution["by_month"][mese]
    if famiglia not in blocco["by_family"]:
        raise ValueError(f"Famiglia {famiglia} non trovata nel mese {mese}.")
    fr_list = blocco["by_family"][famiglia]
    if slot < 0 or slot >= len(fr_list):
        raise ValueError(f"Slot {slot} non valido per famiglia {famiglia}.")

    vecchio = fr_list[slot]
    fr_list[slot] = nuovo_fratello

    # Aggiorna anche by_brother
    if vecchio and vecchio != NON_ASSEGNATO:
        if famiglia in blocco["by_brother"].get(vecchio, []):
            blocco["by_brother"][vecchio].remove(famiglia)
    if nuovo_fratello and nuovo_fratello != NON_ASSEGNATO:
        blocco["by_brother"].setdefault(nuovo_fratello, [])
        if famiglia not in blocco["by_brother"][nuovo_fratello]:
            blocco["by_brother"][nuovo_fratello].append(famiglia)

    return solution


def open_file(filepath: str | Path) -> bool:
    """
    Apre un file con l'applicazione predefinita del sistema operativo.
    Ritorna True se il comando e' stato lanciato, False in caso di errore.
    """
    filepath = str(filepath)
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", filepath])
        elif system == "Windows":
            os.startfile(filepath)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", filepath])
        logging.info("Aperto file: %s", filepath)
        return True
    except Exception as e:
        logging.warning("Impossibile aprire il file '%s': %s", filepath, e)
        return False


def _estrai_assegnazioni(mese: str, solution: dict) -> list[dict]:
    """Estrae le assegnazioni da una soluzione per un singolo mese."""
    assegnazioni: list[dict] = []
    blocco = solution["by_month"][mese]["by_family"]
    for fam, slots in blocco.items():
        for k, fr in enumerate(slots):
            if fr and fr != NON_ASSEGNATO:
                assegnazioni.append({"famiglia": fam, "fratello": fr, "slot": k})
    return assegnazioni
