import logging
import re
import math
import os
from collections import defaultdict
from typing import Any

from .config import SOLVER_TIMEOUT_SECONDS, SOLVER_MAX_WORKERS
from .domain import NON_ASSEGNATO

_ORTOOLS_IMPORT_ERROR: Exception | None = None
try:
    from ortools.sat.python import cp_model  # type: ignore
except Exception as _e:
    cp_model = None  # type: ignore
    _ORTOOLS_IMPORT_ERROR = _e


_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# Numero di worker del solver: usa tutti i core disponibili, max configurato.
_SOLVER_WORKERS = min(SOLVER_MAX_WORKERS, os.cpu_count() or 4)


def _require_ortools() -> None:
    if cp_model is None:
        raise RuntimeError(
            "Dipendenza mancante: ortools.\n"
            "Installa le dipendenze con: pip install -r requirements.txt\n"
            f"Dettaglio: {_ORTOOLS_IMPORT_ERROR!r}"
        )


def validate_month_yyyy_mm(mese: str | None) -> str:
    """Valida e normalizza un mese in formato YYYY-MM."""
    if mese is None:
        raise ValueError("Mese mancante")
    mese = str(mese).strip()
    if not _MONTH_RE.match(mese):
        raise ValueError(
            f"Formato mese non valido: {mese!r}. Usa YYYY-MM (es. 2026-03)."
        )
    return mese


def month_to_idx(mese: str) -> int:
    """Converte 'YYYY-MM' in indice intero (anno*12 + mese)."""
    mese = validate_month_yyyy_mm(mese)
    y, m = mese.split("-")
    return int(y) * 12 + int(m)


def _build_history_for_family(
    storico_turni: list[dict],
) -> dict[str, list[tuple[str, int, str]]]:
    """Per famiglia: lista ordinata di (mese, slot, fratello) dallo storico."""
    per_fam: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for rec in storico_turni or []:
        if not isinstance(rec, dict):
            continue
        mese = rec.get("mese")
        if not isinstance(mese, str):
            continue
        try:
            mese = validate_month_yyyy_mm(mese)
        except ValueError:
            continue
        for a in rec.get("assegnazioni", []) or []:
            if not isinstance(a, dict):
                continue
            fam = a.get("famiglia")
            fr = a.get("fratello")
            try:
                slot = int(a.get("slot", 0))
            except (TypeError, ValueError):
                slot = 0
            if isinstance(fam, str) and isinstance(fr, str):
                per_fam[fam].append((mese, slot, fr))
    for fam, lst in per_fam.items():
        lst.sort(key=lambda t: (month_to_idx(t[0]), t[1]))
    return per_fam


def valida_soluzione(
    by_family: dict[str, list[str]], frequenze: dict[str, int]
) -> list[str]:
    """Check post-solve: conteggio slot e assenza di duplicati per famiglia/mese."""
    errori: list[str] = []
    for fam, assegnati in by_family.items():
        attese = frequenze.get(fam, 2)
        if len(assegnati) != attese:
            errori.append(
                f"Famiglia '{fam}' ha {len(assegnati)} visite (attese {attese})."
            )
        reali = [fr for fr in assegnati if fr and fr != NON_ASSEGNATO]
        if len(reali) != len(set(reali)):
            errori.append(
                f"Famiglia '{fam}' ha fratelli duplicati nella stessa famiglia/mese."
            )
    return errori


def _somma_capacita(fr_set: set[str], capacita: dict[str, int]) -> int:
    return sum(max(0, int(capacita.get(fr, 1))) for fr in fr_set)


def _max_visits_one_brother(idxs: list[int], cd: int) -> int:
    count = 0
    last = -999999
    for idx in idxs:
        if cd == 0 or idx - last > cd:
            count += 1
            last = idx
    return count


def verifica_fattibilita(
    fratelli: set[str],
    famiglie: set[str],
    associazioni: dict[str, list[str]],
    frequenze: dict[str, int],
    capacita: dict[str, int],
) -> list[str]:
    """Check di fattibilita' base (senza storico/cooldown)."""
    problemi: list[str] = []

    fam_no_assoc = [fam for fam in famiglie if not associazioni.get(fam)]
    if fam_no_assoc:
        problemi.append(
            "Famiglie senza alcuna associazione: " + ", ".join(sorted(fam_no_assoc)) + "."
        )

    fam_meno_di_freq = [
        fam for fam in famiglie
        if len(associazioni.get(fam, [])) < frequenze.get(fam, 2)
    ]
    if fam_meno_di_freq:
        problemi.append(
            "Famiglie con meno fratelli associati della frequenza richiesta: "
            + ", ".join(
                f"{fam} (associati={len(associazioni.get(fam, []))}, "
                f"freq={frequenze.get(fam, 2)})"
                for fam in sorted(fam_meno_di_freq)
            )
        )

    somma_freq = sum(frequenze.get(fam, 2) for fam in famiglie)
    fratelli_coinvolti = {b for lst in associazioni.values() for b in lst}
    cap_coinvolta = _somma_capacita(fratelli_coinvolti, capacita)
    if cap_coinvolta < somma_freq:
        problemi.append(
            f"Capacita' fratelli insufficiente: capacita' totale associati = "
            f"{cap_coinvolta}, richieste mensili = {somma_freq}."
        )

    return problemi


def pre_check_fattibilita(
    snap: dict,
    mesi: list[str],
    storico_turni: list[dict],
    cooldown: int,
) -> dict:
    """
    Pre-check rapido di fattibilita' senza invocare il solver.
    Ritorna {fattibile: bool, problemi: [str], avvisi: [str]}
    """
    problemi: list[str] = []
    avvisi: list[str] = []

    base = verifica_fattibilita(
        snap["fratelli"], snap["famiglie"],
        snap["associazioni"], snap["frequenze"], snap["capacita"],
    )
    problemi.extend(base)

    # Check indisponibilita'
    indisponibilita = snap.get("indisponibilita", {})
    for mese_corrente in mesi:
        indisponibili = [fr for fr, mesi_ind in indisponibilita.items() if mese_corrente in mesi_ind]
        if indisponibili:
            # Ricalcola capacita' effettiva
            cap_eff = dict(snap["capacita"])
            for fr in indisponibili:
                cap_eff[fr] = 0
            fratelli_coinvolti = {b for lst in snap["associazioni"].values() for b in lst}
            cap_totale = _somma_capacita(fratelli_coinvolti, cap_eff)
            domanda = sum(snap["frequenze"].get(f, 2) for f in snap["famiglie"])
            if cap_totale < domanda:
                problemi.append(
                    f"Mese {mese_corrente}: capacita' insufficiente dopo indisponibilita' "
                    f"({', '.join(indisponibili)})"
                )
            else:
                avvisi.append(
                    f"Mese {mese_corrente}: {len(indisponibili)} fratello/i indisponibile/i "
                    f"({', '.join(indisponibili)})"
                )

    M = len(mesi)
    if M:
        mesi_idxs = sorted(month_to_idx(m) for m in mesi)
        max_per_brother = _max_visits_one_brother(mesi_idxs, cooldown)
        for fam in snap["famiglie"]:
            n = len(snap["associazioni"].get(fam, []))
            freq = snap["frequenze"].get(fam, 2)
            required = freq * M
            max_possible = n * max_per_brother
            if required > max_possible:
                problemi.append(
                    f"Famiglia '{fam}': richiede {required} visite in {M} mesi, "
                    f"max teorico {max_possible} (cooldown={cooldown}, {n} fratelli)"
                )

    return {
        "fattibile": len(problemi) == 0,
        "problemi": problemi,
        "avvisi": avvisi,
    }


def explain_infeasible(
    mesi: list[str],
    fratelli: set[str],
    famiglie: set[str],
    associazioni: dict[str, list[str]],
    frequenze: dict[str, int],
    capacita: dict[str, int] | None,
    storico_turni: list[dict] | None,
    cooldown_mesi: int,
) -> str:
    """Messaggio diagnostico leggibile quando il solver e' infeasible."""
    _require_ortools()

    capacita = capacita or {fr: 1 for fr in fratelli}
    storico_turni = storico_turni or []
    cooldown_mesi = max(0, int(cooldown_mesi))

    lines: list[str] = []
    base = verifica_fattibilita(fratelli, famiglie, associazioni, frequenze, capacita)
    if base:
        lines.append("Problemi di fattibilita' (base):")
        lines.extend(f"- {p}" for p in base)

    mesi = [validate_month_yyyy_mm(m) for m in mesi]
    mesi_sorted = sorted(mesi)
    idxs = [month_to_idx(m) for m in mesi_sorted]
    if idxs and any(idxs[i + 1] <= idxs[i] for i in range(len(idxs) - 1)):
        lines.append("- Elenco mesi non ordinabile correttamente (duplicati o formato errato).")

    req_per_month = sum(frequenze.get(fam, 2) for fam in famiglie)
    fratelli_coinvolti = {b for lst in associazioni.values() for b in lst}
    supply_per_month = _somma_capacita(fratelli_coinvolti, capacita)
    if supply_per_month < req_per_month:
        lines.append(
            f"- DOMANDA/SUPPLY: richieste per mese={req_per_month}, "
            f"capacita' totale per mese={supply_per_month}."
        )
        lines.append(
            "  Sblocco: aumenta capacita' di uno o piu' fratelli, oppure riduci frequenze."
        )

    M = len(mesi_sorted)
    if M:
        sorted_idxs = [month_to_idx(m) for m in mesi_sorted]
        max_per_brother = _max_visits_one_brother(sorted_idxs, cooldown_mesi)
        for fam in sorted(famiglie):
            n = len(associazioni.get(fam, []))
            freq = frequenze.get(fam, 2)
            required = freq * M
            max_possible = n * max_per_brother
            if required > max_possible:
                lines.append(
                    f"- COOLDOWN: famiglia '{fam}' richiede {required} visite in {M} mesi, "
                    f"ma con cooldown={cooldown_mesi} e {n} fratelli il massimo teorico e' "
                    f"{max_possible}."
                )
                lines.append(
                    "  Sblocco: aggiungi fratelli associati, riduci frequenza o cooldown."
                )

    if mesi_sorted:
        planned_idxs = [month_to_idx(m) for m in mesi_sorted]
        hist_by_fam = _build_history_for_family(storico_turni)
        for fam in sorted(famiglie):
            seq = hist_by_fam.get(fam, [])
            if not seq:
                continue
            last_by_fr: dict[str, tuple[str, int]] = {}
            for mh, _slot, fr in seq:
                last_by_fr[fr] = (mh, month_to_idx(mh))
            reported = False
            for fr, (mh_last, last_idx) in last_by_fr.items():
                for i, p_idx in enumerate(planned_idxs):
                    dist = p_idx - last_idx
                    if 1 <= dist <= cooldown_mesi:
                        lines.append(
                            f"- STORICO/COOLDOWN: '{fr}' ha visitato '{fam}' a {mh_last} "
                            f"(distanza {dist} mesi) -> vietato nel mese {mesi_sorted[i]}."
                        )
                        reported = True
                        break
                if reported:
                    break

    crit: list[tuple[int, str, int, int, int]] = []
    if M:
        for fam in sorted(famiglie):
            n = len(associazioni.get(fam, []))
            freq = frequenze.get(fam, 2)
            required = freq * M
            max_possible = n * max_per_brother
            gap = required - max_possible
            if gap > 0:
                needed = math.ceil(required / max_per_brother) - n
                crit.append((gap, fam, needed, required, max_possible))

    if crit:
        lines.append("")
        lines.append("TOP CRITICITA' (famiglie piu' problematiche):")
        for gap, fam, needed, required, max_possible in sorted(crit, reverse=True)[:3]:
            lines.append(
                f"- '{fam}': richieste={required}, max_possible~={max_possible} (gap {gap}). "
                f"Sblocco minimo: aggiungi ~{needed} fratello/i, oppure riduci frequenza/cooldown."
            )

    if not lines:
        return (
            "Il solver non trova una soluzione (infeasible), "
            "ma i controlli rapidi non individuano una causa unica.\n"
            "Possibili sblocchi: aggiungere fratelli associati alle famiglie piu' critiche, "
            "aumentare capacita' mensile, ridurre frequenze o cooldown."
        )
    return "\n".join(lines)


def ottimizza_turni_mesi(
    mesi: list[str],
    fratelli: set[str],
    famiglie: set[str],
    associazioni: dict[str, list[str]],
    frequenze: dict[str, int],
    capacita: dict[str, int] | None = None,
    storico_turni: list[dict] | None = None,
    cooldown_mesi: int = 3,
    indisponibilita: dict[str, list[str]] | None = None,
    vincoli_personalizzati: list[dict] | None = None,
    affinita: list[dict] | None = None,
    solver_timeout: float | None = None,
    solver_workers: int | None = None,
) -> dict | None:
    """
    Ottimizza i turni su piu' mesi con vincoli di capacita', anti-ravvicinato,
    indisponibilita' e vincoli personalizzati.

    Ritorna il dizionario della soluzione, oppure None se infeasible.
    Solleva RuntimeError se ortools non e' disponibile.
    """
    _require_ortools()
    mesi_validati = [validate_month_yyyy_mm(m) for m in mesi]
    visti: set[str] = set()
    duplicati: list[str] = []
    for m in mesi_validati:
        if m in visti:
            if m not in duplicati:
                duplicati.append(m)
        else:
            visti.add(m)
    if duplicati:
        raise ValueError(f"Mesi duplicati nella richiesta: {duplicati}")
    mesi = sorted(mesi_validati)
    capacita = capacita or {fr: 1 for fr in fratelli}
    storico_turni = storico_turni or []
    cooldown_mesi = max(0, int(cooldown_mesi))
    indisponibilita = indisponibilita or {}
    vincoli_personalizzati = vincoli_personalizzati or []
    affinita = affinita or []
    timeout = solver_timeout if solver_timeout is not None else SOLVER_TIMEOUT_SECONDS
    workers = solver_workers if solver_workers is not None else _SOLVER_WORKERS

    problemi = verifica_fattibilita(fratelli, famiglie, associazioni, frequenze, capacita)
    if problemi:
        logging.warning("Pre-check fattibilita': %s", " | ".join(problemi))

    hist_by_fam = _build_history_for_family(storico_turni)

    model = cp_model.CpModel()

    x: dict = {}   # x[(mese, fam, fr, k)] = BoolVar slot k di fam assegnato a fr
    y: dict = {}   # y[(mese, fam, fr)] = BoolVar fr visita fam nel mese

    for mese in mesi:
        for fam in famiglie:
            freq = frequenze.get(fam, 2)
            assoc = associazioni.get(fam, [])
            for fr in assoc:
                y[(mese, fam, fr)] = model.NewBoolVar(f"y_{mese}_{fam}_{fr}")
            for k in range(freq):
                for fr in assoc:
                    x[(mese, fam, fr, k)] = model.NewBoolVar(f"x_{mese}_{fam}_{fr}_{k}")

    # Ogni slot assegnato esattamente a un fratello
    for mese in mesi:
        for fam in famiglie:
            freq = frequenze.get(fam, 2)
            assoc = associazioni.get(fam, [])
            for k in range(freq):
                model.Add(sum(x[(mese, fam, fr, k)] for fr in assoc) == 1)
            # Niente duplicati nella stessa famiglia/mese
            for fr in assoc:
                model.Add(sum(x[(mese, fam, fr, k)] for k in range(freq)) <= 1)
            # Link y <-> somma degli x
            for fr in assoc:
                model.Add(y[(mese, fam, fr)] == sum(x[(mese, fam, fr, k)] for k in range(freq)))

    # Capacita' fratello per mese
    for mese in mesi:
        for fr in fratelli:
            cap = max(0, int(capacita.get(fr, 1)))
            terms = [
                y[(mese, fam, fr)]
                for fam in famiglie
                if fr in associazioni.get(fam, [])
            ]
            if terms:
                model.Add(sum(terms) <= cap)

    # Vincolo hard anti-ravvicinato (cooldown)
    idx_map = {mese: month_to_idx(mese) for mese in mesi}
    idx_to_month = {v: k for k, v in idx_map.items()}

    for fam in famiglie:
        for fr in associazioni.get(fam, []):
            for m1 in mesi:
                i1 = idx_map[m1]
                for delta in range(1, cooldown_mesi + 1):
                    m2 = idx_to_month.get(i1 + delta)
                    if m2 is not None:
                        model.Add(y[(m1, fam, fr)] + y[(m2, fam, fr)] <= 1)

    # Vincolo storico: vieta fratello in ogni mese pianificato se distanza <= cooldown
    if mesi:
        for fam in famiglie:
            seq = hist_by_fam.get(fam, [])
            if not seq:
                continue
            assoc_fam = associazioni.get(fam, [])
            fr_index = {fr: j for j, fr in enumerate(assoc_fam)}
            for mh, _slot, frh in seq:
                hist_idx = month_to_idx(mh)
                if frh in fr_index:
                    for m_plan_idx, m_plan in enumerate(mesi):
                        plan_idx = month_to_idx(m_plan)
                        if 1 <= abs(plan_idx - hist_idx) <= cooldown_mesi:
                            model.Add(y[(m_plan, fam, frh)] == 0)

    # NUOVO: Vincolo indisponibilita' temporanee
    for fr, mesi_ind in indisponibilita.items():
        for mese in mesi:
            if mese in mesi_ind:
                # Fratello non puo' fare visite in questo mese
                terms = [
                    y[(mese, fam, fr)]
                    for fam in famiglie
                    if fr in associazioni.get(fam, [])
                ]
                for term in terms:
                    model.Add(term == 0)

    # NUOVO: Vincoli personalizzati
    for vincolo in vincoli_personalizzati:
        fa = vincolo.get("fratello_a", "")
        fb = vincolo.get("fratello_b", "")
        tipo = vincolo.get("tipo", "")

        if tipo == "incompatibile":
            # Fratelli incompatibili: non possono visitare la stessa famiglia nello stesso mese
            for mese in mesi:
                for fam in famiglie:
                    assoc = associazioni.get(fam, [])
                    if fa in assoc and fb in assoc:
                        model.Add(y[(mese, fam, fa)] + y[(mese, fam, fb)] <= 1)

        elif tipo == "preferenza_coppia":
            pass

    # Obiettivo: minimizza il carico massimo mensile (distribuzione equa)
    n_famiglie = max(1, len(famiglie))
    n_mesi = max(1, len(mesi))
    _ub_load = n_famiglie
    _ub_total = n_famiglie * n_mesi

    load: dict = {}
    for mese in mesi:
        for fr in fratelli:
            terms = [
                y[(mese, fam, fr)]
                for fam in famiglie
                if fr in associazioni.get(fam, [])
            ]
            if terms:
                load[(mese, fr)] = model.NewIntVar(0, _ub_load, f"load_{mese}_{fr}")
                model.Add(load[(mese, fr)] == sum(terms))

    max_load = model.NewIntVar(0, _ub_load, "max_load")
    for v in load.values():
        model.Add(v <= max_load)

    # Equita' cumulativa multi-periodo: bilancia il carico totale tra fratelli
    total_load: dict[str, Any] = {}
    for fr in fratelli:
        month_loads = [load[(m, fr)] for m in mesi if (m, fr) in load]
        if month_loads:
            total_load[fr] = model.NewIntVar(0, _ub_total, f"total_load_{fr}")
            model.Add(total_load[fr] == sum(month_loads))

    max_total = model.NewIntVar(0, _ub_total, "max_total_load")
    min_total = model.NewIntVar(0, _ub_total, "min_total_load")
    for v in total_load.values():
        model.Add(v <= max_total)
        model.Add(v >= min_total)

    # Obiettivo composito: minimizza max_load + spread cumulativo + bonus coppia
    objective_terms = [max_load * 100, (max_total - min_total) * 50]

    for vincolo in (vincoli_personalizzati or []):
        if vincolo.get("tipo") == "preferenza_coppia":
            fa = vincolo.get("fratello_a", "")
            fb = vincolo.get("fratello_b", "")
            for mese in mesi:
                for fam in famiglie:
                    assoc = associazioni.get(fam, [])
                    if fa in assoc and fb in assoc:
                        bonus = model.NewBoolVar(f"coppia_{mese}_{fam}_{fa}_{fb}")
                        model.AddBoolAnd([y[(mese, fam, fa)], y[(mese, fam, fb)]]).OnlyEnforceIf(bonus)
                        model.AddBoolOr([y[(mese, fam, fa)].Not(), y[(mese, fam, fb)].Not()]).OnlyEnforceIf(bonus.Not())
                        objective_terms.append(-10 * bonus)

    # Affinita' fratello-famiglia (soft)
    for aff in affinita:
        fam_a = aff.get("famiglia", "")
        fr_a = aff.get("fratello", "")
        try:
            peso = int(aff.get("peso", 0))
        except (TypeError, ValueError):
            continue
        if not peso:
            continue
        for mese in mesi:
            key = (mese, fam_a, fr_a)
            if key in y:
                # peso>0: incentiva assegnazione (negativo in minimizzazione)
                # peso<0: penalizza assegnazione (positivo in minimizzazione)
                objective_terms.append(y[key] * (-peso))

    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout
    solver.parameters.num_search_workers = workers

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        logging.warning("Solver: nessuna soluzione trovata (infeasible).")
        return None

    warnings: list[str] = []
    if status == cp_model.FEASIBLE:
        warnings.append("Soluzione trovata ma non provata ottima (timeout raggiunto)")

    # Costruisce la soluzione
    by_month: dict = {}
    for mese in mesi:
        fam_map: dict[str, list[str]] = {}
        bro_map: dict[str, list[str]] = {fr: [] for fr in fratelli}
        for fam in famiglie:
            freq = frequenze.get(fam, 2)
            slots: list[str] = []
            for k in range(freq):
                chosen = next(
                    (fr for fr in associazioni.get(fam, [])
                     if solver.Value(x[(mese, fam, fr, k)]) == 1),
                    None,
                )
                slots.append(chosen or NON_ASSEGNATO)
            fam_map[fam] = slots
            for fr in slots:
                if fr and fr != NON_ASSEGNATO:
                    bro_map[fr].append(fam)

        by_month[mese] = {"by_family": fam_map, "by_brother": bro_map}

        errori = valida_soluzione(fam_map, frequenze)
        if errori:
            logging.warning(
                "Anomalie nella soluzione per %s: %s", mese, " | ".join(errori)
            )

    result: dict[str, Any] = {"by_month": by_month}
    if warnings:
        result["warnings"] = warnings
    return result
