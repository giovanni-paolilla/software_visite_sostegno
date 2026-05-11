"""
Utilità per settimane, slot e mesi — funzioni pure, senza IO.

Le funzioni che richiedono input/print (CLI) sono in cli.py.
"""
import re


def parse_settimane_lista(raw: str, attese: int) -> tuple[list[str] | None, str]:
    """
    Analizza una stringa tipo '01-07, 15-21' e verifica che contenga
    esattamente 'attese' intervalli gg-gg validi.

    Returns:
        (lista_normalizzata, "") se valida
        (None, messaggio_errore) se non valida
    """
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) != attese:
        return None, f"Numero di intervalli errato: attesi {attese}, forniti {len(parts)}."
    ok: list[str] = []
    for p in parts:
        if not re.match(r"^\d{2}-\d{2}$", p):
            return None, f"Intervallo non valido (usa gg-gg): {p}"
        a, b = p.split("-")
        try:
            ia, ib = int(a), int(b)
        except ValueError:
            return None, f"Intervallo non numerico: {p}"
        if not (1 <= ia <= 31 and 1 <= ib <= 31 and ia <= ib):
            return None, f"Giorni fuori range o invertiti: {p}"
        ok.append(f"{ia:02d}-{ib:02d}")
    sorted_intervals = sorted(ok, key=lambda p: int(p.split("-")[0]))
    for i in range(len(sorted_intervals) - 1):
        end_cur = int(sorted_intervals[i].split("-")[1])
        start_next = int(sorted_intervals[i + 1].split("-")[0])
        if end_cur >= start_next:
            return None, f"Intervalli sovrapposti: {sorted_intervals[i]} e {sorted_intervals[i+1]}"
    return sorted_intervals, ""


def month_sigla(mese: str) -> str:
    """Converte 'YYYY-MM' nella sigla italiana del mese (es. 'Gen')."""
    if not mese:
        return ""
    sigle = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
    try:
        m = int(mese.split("-")[1])
        if not (1 <= m <= 12):
            return ""
        return sigle[m - 1]
    except (IndexError, ValueError, AttributeError):
        return ""


def slot_label(mese: str, freq: int, k: int, week_windows: dict) -> str:
    try:
        return week_windows[mese][freq][k]
    except (KeyError, IndexError):
        return f"slot {k + 1}"


def slot_label_with_month(mese: str, freq: int, k: int, week_windows: dict) -> str:
    base = slot_label(mese, freq, k, week_windows)
    sig = month_sigla(mese)
    return f"{base} {sig}".strip()
