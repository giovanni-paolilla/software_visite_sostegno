"""
Statistiche e report di carico per fratelli e famiglie.

Fornisce analisi di distribuzione del carico di lavoro,
copertura storica e trend nel tempo.
"""
from __future__ import annotations

from collections import defaultdict


def report_carico_fratelli(
    storico_turni: list[dict],
    mesi_filtro: list[str] | None = None,
) -> list[dict]:
    """
    Genera un report di carico per ogni fratello basato sullo storico.

    Ritorna una lista di dizionari ordinata per visite totali (decrescente):
    [{fratello, visite_totali, mesi_attivi, famiglie_visitate, dettaglio_mensile}]
    """
    carico: dict[str, dict] = defaultdict(lambda: {
        "visite_totali": 0,
        "mesi": set(),
        "famiglie": set(),
        "dettaglio_mensile": defaultdict(int),
    })

    for rec in storico_turni:
        if not isinstance(rec, dict):
            continue
        mese = rec.get("mese", "")
        if mesi_filtro and mese not in mesi_filtro:
            continue
        for a in rec.get("assegnazioni", []):
            if not isinstance(a, dict):
                continue
            fr = a.get("fratello", "")
            fam = a.get("famiglia", "")
            if fr and fam:
                carico[fr]["visite_totali"] += 1
                carico[fr]["mesi"].add(mese)
                carico[fr]["famiglie"].add(fam)
                carico[fr]["dettaglio_mensile"][mese] += 1

    result = []
    for fr, dati in sorted(carico.items()):
        result.append({
            "fratello": fr,
            "visite_totali": dati["visite_totali"],
            "mesi_attivi": len(dati["mesi"]),
            "famiglie_visitate": sorted(dati["famiglie"]),
            "n_famiglie_visitate": len(dati["famiglie"]),
            "dettaglio_mensile": dict(sorted(dati["dettaglio_mensile"].items())),
        })
    result.sort(key=lambda x: x["visite_totali"], reverse=True)
    return result


def report_copertura_famiglie(
    storico_turni: list[dict],
    famiglie_attive: set[str] | None = None,
) -> list[dict]:
    """
    Genera un report di copertura per ogni famiglia.

    Ritorna: [{famiglia, visite_totali, mesi_coperti, fratelli_coinvolti, dettaglio_mensile}]
    """
    copertura: dict[str, dict] = defaultdict(lambda: {
        "visite_totali": 0,
        "mesi": set(),
        "fratelli": set(),
        "dettaglio_mensile": defaultdict(int),
    })

    for rec in storico_turni:
        if not isinstance(rec, dict):
            continue
        mese = rec.get("mese", "")
        for a in rec.get("assegnazioni", []):
            if not isinstance(a, dict):
                continue
            fam = a.get("famiglia", "")
            fr = a.get("fratello", "")
            if fam and fr:
                copertura[fam]["visite_totali"] += 1
                copertura[fam]["mesi"].add(mese)
                copertura[fam]["fratelli"].add(fr)
                copertura[fam]["dettaglio_mensile"][mese] += 1

    result = []
    target_fam = famiglie_attive or set(copertura.keys())
    for fam in sorted(target_fam):
        dati = copertura.get(fam)
        if dati:
            result.append({
                "famiglia": fam,
                "visite_totali": dati["visite_totali"],
                "mesi_coperti": len(dati["mesi"]),
                "fratelli_coinvolti": sorted(dati["fratelli"]),
                "n_fratelli_coinvolti": len(dati["fratelli"]),
                "dettaglio_mensile": dict(sorted(dati["dettaglio_mensile"].items())),
            })
        else:
            result.append({
                "famiglia": fam,
                "visite_totali": 0,
                "mesi_coperti": 0,
                "fratelli_coinvolti": [],
                "n_fratelli_coinvolti": 0,
                "dettaglio_mensile": {},
            })
    return result


def calcola_indice_equita(storico_turni: list[dict]) -> dict:
    """
    Calcola un indice di equita' nella distribuzione del carico.

    Ritorna: {media, deviazione_standard, min, max, fratello_min, fratello_max, indice_gini}
    """
    report = report_carico_fratelli(storico_turni)
    if not report:
        return {"media": 0, "deviazione_standard": 0, "min": 0, "max": 0,
                "fratello_min": "", "fratello_max": "", "indice_gini": 0}

    visite = [r["visite_totali"] for r in report]
    n = len(visite)
    media = sum(visite) / n
    varianza = sum((v - media) ** 2 for v in visite) / n
    dev_std = varianza ** 0.5

    fr_min = min(report, key=lambda x: x["visite_totali"])
    fr_max = max(report, key=lambda x: x["visite_totali"])

    # Coefficiente di Gini (0 = perfetta equita', 1 = massima disuguaglianza)
    sorted_v = sorted(visite)
    total = sum(sorted_v)
    if total == 0:
        gini = 0.0
    else:
        cum = 0
        area = 0
        for v in sorted_v:
            cum += v
            area += cum
        gini = 1 - (2 * area) / (n * total) + 1 / n

    return {
        "media": round(media, 2),
        "deviazione_standard": round(dev_std, 2),
        "min": fr_min["visite_totali"],
        "max": fr_max["visite_totali"],
        "fratello_min": fr_min["fratello"],
        "fratello_max": fr_max["fratello"],
        "indice_gini": round(gini, 3),
    }


def trend_mensile(storico_turni: list[dict]) -> list[dict]:
    """
    Genera il trend mensile di visite.
    Ritorna: [{mese, n_visite, n_fratelli, n_famiglie}]
    """
    per_mese: dict[str, dict] = defaultdict(lambda: {
        "n_visite": 0, "fratelli": set(), "famiglie": set()
    })
    for rec in storico_turni:
        if not isinstance(rec, dict):
            continue
        mese = rec.get("mese", "")
        for a in rec.get("assegnazioni", []):
            if not isinstance(a, dict):
                continue
            fr = a.get("fratello", "")
            fam = a.get("famiglia", "")
            if fr and fam:
                per_mese[mese]["n_visite"] += 1
                per_mese[mese]["fratelli"].add(fr)
                per_mese[mese]["famiglie"].add(fam)

    result = []
    for mese in sorted(per_mese.keys()):
        d = per_mese[mese]
        result.append({
            "mese": mese,
            "n_visite": d["n_visite"],
            "n_fratelli": len(d["fratelli"]),
            "n_famiglie": len(d["famiglie"]),
        })
    return result
