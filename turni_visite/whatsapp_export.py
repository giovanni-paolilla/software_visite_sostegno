"""
Export testo plain-text ottimizzato per WhatsApp (copia-incolla).

Usa asterischi per il grassetto WhatsApp e struttura leggibile su mobile.
"""
from __future__ import annotations

import re

from .weeks import month_sigla, slot_label_with_month
from .domain import NON_ASSEGNATO

_MESI_NOME = {
    "01": "Gennaio", "02": "Febbraio", "03": "Marzo", "04": "Aprile",
    "05": "Maggio", "06": "Giugno", "07": "Luglio", "08": "Agosto",
    "09": "Settembre", "10": "Ottobre", "11": "Novembre", "12": "Dicembre",
}


def _nome_mese(mese: str) -> str:
    if not re.match(r"^\d{4}-\d{2}$", mese):
        return mese
    parts = mese.split("-")
    anno = parts[0]
    nome = _MESI_NOME.get(parts[1], parts[1])
    return f"{nome} {anno}"


def format_whatsapp_mesi(
    mesi: list[str],
    solution: dict,
    frequenze: dict[str, int],
    week_windows: dict,
) -> str:
    lines: list[str] = []

    for mese in mesi:
        blocco = solution.get("by_month", {}).get(mese)
        if not blocco:
            continue

        lines.append(f"*VISITE DI SOSTEGNO — {_nome_mese(mese)}*")
        lines.append("")

        by_fam = blocco.get("by_family") or {}
        if not isinstance(by_fam, dict):
            by_fam = {}

        # Per fratello
        lines.append("*Per Fratello:*")
        by_brother = blocco.get("by_brother", {})
        for fr in sorted(by_brother.keys()):
            fam_list = by_brother[fr]
            if not fam_list:
                continue
            lines.append(f"_{fr}_")
            for fam in fam_list:
                fr_slots = by_fam.get(fam, [])
                k_found = next((k for k, name in enumerate(fr_slots) if name == fr), None)
                freq = frequenze.get(fam, 2)
                label = slot_label_with_month(mese, freq, k_found, week_windows) if k_found is not None else ""
                lines.append(f"  • {fam} ({label})")
            lines.append("")

        # Per famiglia
        lines.append("*Per Famiglia:*")
        for fam in sorted(by_fam.keys()):
            freq = frequenze.get(fam, 2)
            slots = by_fam[fam]
            lines.append(f"_{fam}_")
            for k, fr in enumerate(slots):
                if fr is not None and fr != NON_ASSEGNATO and str(fr).strip():
                    label = slot_label_with_month(mese, freq, k, week_windows)
                    lines.append(f"  • {label}: {fr}")
            lines.append("")

        lines.append("—" * 25)
        lines.append("")

    return "\n".join(lines).rstrip()
