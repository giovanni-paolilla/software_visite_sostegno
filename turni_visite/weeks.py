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
    return ok, ""


def month_sigla(mese: str) -> str:
    """Converte 'YYYY-MM' nella sigla italiana del mese (es. 'Gen')."""
    sigle = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
    try:
        m = int(mese.split("-")[1])
        return sigle[m - 1]
    except (IndexError, ValueError):
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
