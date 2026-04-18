import logging
import re
import math
import os
from collections import defaultdict

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
        if len(assegnati) != len(set(assegnati)):
            errori.append(
                f"Famiglia '{fam}' ha fratelli duplicati nella stessa famiglia/mese."
            )
    return errori


def _somma_capacita(fr_set: set[str], capacita: dict[str, int]) -> int:
    return sum(max(0, int(capacita.get(fr, 1))) for fr in fr_set)


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
    for mese in mesi:
        indisponibili = [fr for fr, mesi_ind in indisponibilita.items() if mese in mesi_ind]
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
                    f"Mese {mese}: capacita' insufficiente dopo indisponibilita' "
                    f"({', '.join(indisponibili)})"
                )
            else:
                avvisi.append(
                    f"Mese {mese}: {len(indisponibili)} fratello/i indisponibile/i "
                    f"({', '.join(indisponibili)})"
                )

    # Check cooldown
    M = len(mesi)
    if M:
        max_per_brother = (M + cooldown) // (cooldown + 1) if M else 0
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
    cooldown_mesi = max(1, int(cooldown_mesi))

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
    max_per_brother = (M + cooldown_mesi) // (cooldown_mesi + 1) if M else 0
    if M:
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
        first_idx = month_to_idx(mesi_sorted[0])
        hist_by_fam = _build_history_for_family(storico_turni)
        for fam in sorted(famiglie):
            seq = hist_by_fam.get(fam, [])
            if not seq:
                continue
            last_by_fr: dict[str, tuple[str, int]] = {}
            for mh, _slot, fr in seq:
                last_by_fr[fr] = (mh, month_to_idx(mh))
            for fr, (mh_last, last_idx) in last_by_fr.items():
                dist = first_idx - last_idx
                if 1 <= dist <= cooldown_mesi:
                    lines.append(
                        f"- STORICO/COOLDOWN: '{fr}' ha visitato '{fam}' a {mh_last} "
                        f"(distanza {dist} mesi) -> vietato nel primo mese pianificato."
                    )
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
    mesi = sorted(validate_month_yyyy_mm(m) for m in mesi)
    capacita = capacita or {fr: 1 for fr in fratelli}
    storico_turni = storico_turni or []
    cooldown_mesi = max(1, int(cooldown_mesi))
    indisponibilita = indisponibilita or {}
    vincoli_personalizzati = vincoli_personalizzati or []
    timeout = solver_timeout or SOLVER_TIMEOUT_SECONDS
    workers = solver_workers or _SOLVER_WORKERS

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

    # Vincolo storico: vieta fratello nel primo mese se distanza <= cooldown
    if mesi:
        first = mesi[0]
        first_idx = idx_map[first]
        for fam in famiglie:
            seq = hist_by_fam.get(fam, [])
            if not seq:
                continue
            last_by_fr: dict[str, int] = {}
            for mh, _slot, frh in seq:
                last_by_fr[frh] = month_to_idx(mh)
            for fr in associazioni.get(fam, []):
                if fr in last_by_fr:
                    dist = first_idx - last_by_fr[fr]
                    if 1 <= dist <= cooldown_mesi:
                        model.Add(y[(first, fam, fr)] == 0)

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
            # Soft: preferisci che visitino la stessa famiglia nello stesso mese
            # (gestito come soft constraint nell'obiettivo)
            pass  # gestito nell'obiettivo sotto

    # Obiettivo: minimizza il carico massimo mensile (distribuzione equa)
    load: dict = {}
    for mese in mesi:
        for fr in fratelli:
            terms = [
                y[(mese, fam, fr)]
                for fam in famiglie
                if fr in associazioni.get(fam, [])
            ]
            if terms:
                load[(mese, fr)] = model.NewIntVar(0, 999, f"load_{mese}_{fr}")
                model.Add(load[(mese, fr)] == sum(terms))

    max_load = model.NewIntVar(0, 999, "max_load")
    for v in load.values():
        model.Add(v <= max_load)

    # Obiettivo composito: minimizza max_load + bonus per preferenze coppia
    objective_terms = [max_load * 100]  # peso principale

    for vincolo in (vincoli_personalizzati or []):
        if vincolo.get("tipo") == "preferenza_coppia":
            fa = vincolo.get("fratello_a", "")
            fb = vincolo.get("fratello_b", "")
            for mese in mesi:
                for fam in famiglie:
                    assoc = associazioni.get(fam, [])
                    if fa in assoc and fb in assoc:
                        # Bonus: -1 se entrambi assegnati alla stessa famiglia
                        bonus = model.NewBoolVar(f"coppia_{mese}_{fam}_{fa}_{fb}")
                        model.Add(y[(mese, fam, fa)] + y[(mese, fam, fb)] >= 2).OnlyEnforceIf(bonus)
                        model.Add(y[(mese, fam, fa)] + y[(mese, fam, fb)] <= 1).OnlyEnforceIf(bonus.Not())
                        objective_terms.append(-bonus)

    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout
    solver.parameters.num_search_workers = workers

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        logging.warning("Solver: nessuna soluzione trovata (infeasible).")
        return None

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

    return {"by_month": by_month}
