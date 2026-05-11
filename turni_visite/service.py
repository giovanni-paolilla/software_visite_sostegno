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

from .domain import SolverResult, StoricoConflittoError, ValidazioneError, NON_ASSEGNATO
from .scheduling import ottimizza_turni_mesi, explain_infeasible, pre_check_fattibilita, month_to_idx
from .backup import create_backup
from .stats import report_carico_fratelli

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
    kwargs: dict = dict(
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
        affinita=snap.get("affinita"),
        solver_timeout=solver_timeout,
        solver_workers=solver_workers,
    )
    raw = ottimizza_turni_mesi(**kwargs)
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
    if not mesi:
        return []

    duplicati = [m for m in mesi if repo.storico_has_mese(m)]
    if duplicati:
        raise StoricoConflittoError(
            "Mesi gia' presenti nello storico: " + ", ".join(duplicati) + ".\n"
            "Rimuovili prima se vuoi rigenerarli."
        )

    records: list[tuple[str, list[dict]]] = [
        (mese, _estrai_assegnazioni(mese, solution)) for mese in mesi
    ]

    avvisi: list[str] = []
    try:
        create_backup(repo.filename)
    except Exception as exc:
        avvisi.append(f"Backup fallito: {exc}")
        logging.error("Backup fallito prima del salvataggio: %s", exc)

    salvati = repo.extend_storico_turni(records)
    for mese in salvati:
        logging.info("Turni mese %s salvati nello storico.", mese)
    if avvisi:
        logging.error(
            "Salvataggio completato con %d avviso/i: %s",
            len(avvisi),
            "; ".join(avvisi),
        )
    return salvati


def modifica_assegnazione(
    solution: dict,
    mese: str,
    famiglia: str,
    slot: int,
    nuovo_fratello: str,
    repo: "JsonRepository | None" = None,
) -> dict:
    """
    Modifica manualmente una singola assegnazione nella soluzione.

    Ritorna la soluzione aggiornata.  Eventuali warning non bloccanti
    vengono inseriti in ``solution["_warnings"]`` (lista di stringhe).
    """
    import copy
    solution = copy.deepcopy(solution)
    solution.pop("_warnings", None)
    warnings: list[str] = []

    if repo is not None:
        if nuovo_fratello not in repo.associazioni.get(famiglia, []):
            raise ValidazioneError(
                f"Il fratello '{nuovo_fratello}' non e' associato alla famiglia '{famiglia}'."
            )
        if mese in repo.indisponibilita.get(nuovo_fratello, []):
            raise ValidazioneError(
                f"Il fratello '{nuovo_fratello}' e' indisponibile nel mese '{mese}'."
            )

    if "by_month" not in solution or mese not in solution["by_month"]:
        raise ValidazioneError(f"Mese {mese} non trovato nella soluzione.")
    blocco = solution["by_month"][mese]
    if "by_family" not in blocco:
        raise ValidazioneError(f"Struttura soluzione mancante per mese {mese}.")
    if famiglia not in blocco["by_family"]:
        raise ValidazioneError(f"Famiglia {famiglia} non trovata nel mese {mese}.")
    fr_list = blocco["by_family"][famiglia]
    if slot < 0 or slot >= len(fr_list):
        raise ValidazioneError(f"Slot {slot} non valido per famiglia {famiglia}.")

    # --- Warning non bloccanti (solo per fratelli reali) ---
    if nuovo_fratello and nuovo_fratello != NON_ASSEGNATO:

        # 1) Duplicato: fratello gia' assegnato alla stessa famiglia in altro slot
        for i, fr in enumerate(fr_list):
            if i != slot and fr == nuovo_fratello:
                warnings.append(
                    f"Duplicato: '{nuovo_fratello}' e' gia' assegnato a "
                    f"'{famiglia}' nello slot {i} dello stesso mese."
                )
                break

        if repo is not None:
            # 2) Cooldown: fratello ha visitato la famiglia in un mese vicino
            try:
                cooldown = int(repo.get_setting("cooldown_mesi", 3))
                mese_idx = month_to_idx(mese)
                for rec in repo.get_storico_turni():
                    if not isinstance(rec, dict):
                        continue
                    m = rec.get("mese", "")
                    try:
                        m_idx = month_to_idx(m)
                    except (ValueError, TypeError):
                        continue
                    if 1 <= abs(mese_idx - m_idx) <= cooldown:
                        if any(
                            a.get("fratello") == nuovo_fratello
                            and a.get("famiglia") == famiglia
                            for a in rec.get("assegnazioni", [])
                        ):
                            warnings.append(
                                f"Cooldown: '{nuovo_fratello}' ha gia' visitato "
                                f"'{famiglia}' nel mese {m} (entro {cooldown} mesi)."
                            )
                            break
            except Exception:
                pass  # storico non disponibile, skip

            # 3) Capacita': fratello supera il limite di visite per il mese
            cap = repo.capacita.get(nuovo_fratello, 1)
            visite_nel_mese = sum(
                1 for fam_k, slots_k in blocco.get("by_family", {}).items()
                for j, fr in enumerate(slots_k)
                if fr == nuovo_fratello and not (fam_k == famiglia and j == slot)
            )
            # +1 perche' stiamo per aggiungere questa assegnazione
            if visite_nel_mese + 1 > cap:
                warnings.append(
                    f"Capacita': '{nuovo_fratello}' avra' {visite_nel_mese + 1} "
                    f"visite nel mese {mese} (capacita' configurata: {cap})."
                )

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

    if warnings:
        solution["_warnings"] = warnings
        for w in warnings:
            logging.warning("modifica_assegnazione: %s", w)

    return solution


def trova_sostituto(
    repo: "JsonRepository",
    mese: str,
    fratello_malato: str,
    famiglia: str | None = None,
) -> list[dict]:
    """
    Trova candidati sostituti per un fratello indisponibile in un mese confermato.
    Ritorna lista di candidati ordinati per preferenza: [{fratello, carico_attuale, score}].
    """
    storico = repo.get_storico_turni()
    rec = next((r for r in storico if isinstance(r, dict) and r.get("mese") == mese), None)
    if not rec:
        return []

    assegnazioni_malato = [
        a for a in rec.get("assegnazioni", [])
        if a.get("fratello") == fratello_malato
        and (famiglia is None or a.get("famiglia") == famiglia)
    ]
    if not assegnazioni_malato:
        return []

    carico = report_carico_fratelli(storico, mesi_filtro=[mese])
    carico_map = {r["fratello"]: r["visite_totali"] for r in carico}

    cooldown = int(repo.get_setting("cooldown_mesi", 3))
    mese_idx = month_to_idx(mese)

    hist_recent: dict[str, dict[str, int]] = {}
    for r in storico:
        if not isinstance(r, dict):
            continue
        m = r.get("mese", "")
        try:
            m_idx = month_to_idx(m)
        except (ValueError, TypeError):
            continue
        if 1 <= abs(mese_idx - m_idx) <= cooldown:
            for a in r.get("assegnazioni", []):
                fr = a.get("fratello", "")
                fam = a.get("famiglia", "")
                if fr and fam:
                    hist_recent.setdefault(fr, {}).setdefault(fam, m_idx)

    # Coppia simmetrica di fratelli incompatibili (vincoli hard)
    incompatibili: set[tuple[str, str]] = set()
    for v in repo.get_vincoli():
        if v.get("tipo") == "incompatibile":
            fa, fb = v.get("fratello_a", ""), v.get("fratello_b", "")
            if fa and fb:
                incompatibili.add((fa, fb))
                incompatibili.add((fb, fa))

    # Mappa: per ogni fratello, l'insieme di compagni con cui condivide
    # una famiglia nel mese corrente (qualunque famiglia).
    compagni_per_fratello: dict[str, set[str]] = {}
    for fam_iter in {a.get("famiglia", "") for a in rec.get("assegnazioni", [])}:
        membri = {
            a.get("fratello", "") for a in rec.get("assegnazioni", [])
            if a.get("famiglia") == fam_iter and a.get("fratello")
        }
        for fr_m in membri:
            compagni_per_fratello.setdefault(fr_m, set()).update(
                m for m in membri if m and m != fr_m
            )

    candidati: list[dict] = []
    for ass in assegnazioni_malato:
        fam = ass.get("famiglia", "")
        slot = ass.get("slot", 0)
        associati = repo.associazioni.get(fam, [])
        indisponibili_mese = {
            fr for fr, mesi_ind in repo.indisponibilita.items() if mese in mesi_ind
        }
        # Fratelli già assegnati alla stessa famiglia nello stesso mese
        # (il vincolo incompatibile nel solver vieta la co-presenza per famiglia/mese, non per slot)
        compagni_fam = {
            a.get("fratello") for a in rec.get("assegnazioni", [])
            if a.get("famiglia") == fam
            and a.get("fratello") != fratello_malato
        }

        for fr in associati:
            if fr == fratello_malato:
                continue
            if fr in indisponibili_mese:
                continue
            if fr in hist_recent and fam in hist_recent[fr]:
                continue
            # Skip candidato già assegnato alla stessa famiglia in un altro slot del mese
            if fr in compagni_fam:
                continue
            # Compagni effettivi del candidato: quelli della famiglia target
            # piu' quelli di tutte le altre famiglie a cui il candidato e'
            # gia' assegnato nello stesso mese (vincolo cross-famiglia).
            compagni_effettivi = set(compagni_fam) | compagni_per_fratello.get(fr, set())
            compagni_effettivi.discard(fratello_malato)
            compagni_effettivi.discard(fr)
            if any((fr, c) in incompatibili for c in compagni_effettivi):
                continue

            load = carico_map.get(fr, 0)
            cap = repo.capacita.get(fr, 1)
            fr_visite_mese = sum(1 for a2 in rec.get("assegnazioni", [])
                                 if a2.get("fratello") == fr)
            if fr_visite_mese >= cap:
                continue

            candidati.append({
                "fratello": fr,
                "famiglia": fam,
                "slot": slot,
                "carico_attuale": load,
                "score": -load,
            })

    candidati.sort(key=lambda c: c["score"], reverse=True)
    return candidati


def open_file(filepath: str | Path) -> bool:
    """
    Apre un file con l'applicazione predefinita del sistema operativo.
    Ritorna True se il comando e' stato lanciato, False in caso di errore.
    """
    filepath = str(filepath)
    if any(filepath.startswith(s) for s in ("http://", "https://", "ftp://")):
        raise ValidazioneError("Apertura URL non consentita")
    p = Path(filepath).resolve()
    if not p.exists():
        raise ValidazioneError(f"File non trovato: {filepath}")
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Windows":
            os.startfile(str(p))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info("Aperto file: %s", filepath)
        return True
    except Exception as e:
        logging.warning("Impossibile aprire il file '%s': %s", filepath, e)
        return False


def _estrai_assegnazioni(mese: str, solution: dict) -> list[dict]:
    """Estrae le assegnazioni da una soluzione per un singolo mese."""
    assegnazioni: list[dict] = []
    by_month = solution.get("by_month")
    if not by_month or mese not in by_month:
        raise ValidazioneError(f"Mese {mese} non trovato nella soluzione.")
    blocco = by_month[mese].get("by_family", {})
    for fam, slots in blocco.items():
        for k, fr in enumerate(slots):
            if fr and fr != NON_ASSEGNATO:
                assegnazioni.append({"famiglia": fam, "fratello": fr, "slot": k})
    return assegnazioni
