"""
Esportazione turni in formato CSV e Excel (openpyxl).

Genera file tabellari con le assegnazioni per famiglia e per fratello,
compatibili con fogli di calcolo per condivisione e modifica.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from .weeks import slot_label_with_month


def export_csv_mesi(
    mesi: list[str],
    solution: dict,
    frequenze: dict[str, int],
    week_windows: dict,
    output_path: str | Path,
) -> None:
    """Esporta i turni in un file CSV."""
    if not solution or "by_month" not in solution:
        logging.warning("Nessuna soluzione da esportare in CSV.")
        return

    path = Path(output_path)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Mese", "Famiglia", "Frequenza", "Slot", "Fratello", "Settimana"])

        for mese in sorted(mesi):
            blocco = solution["by_month"].get(mese)
            if not blocco:
                continue
            for fam in sorted(blocco["by_family"].keys()):
                fr_list = blocco["by_family"][fam]
                freq = frequenze.get(fam, 2)
                for k, fr in enumerate(fr_list):
                    label = slot_label_with_month(mese, freq, k, week_windows)
                    writer.writerow([mese, fam, freq, k + 1, fr, label])

    logging.info("CSV esportato: %s", path)


def export_csv_per_fratello(
    mesi: list[str],
    solution: dict,
    frequenze: dict[str, int],
    week_windows: dict,
    output_path: str | Path,
) -> None:
    """Esporta i turni raggruppati per fratello in CSV."""
    if not solution or "by_month" not in solution:
        return

    path = Path(output_path)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Fratello", "Mese", "Famiglia", "Settimana"])

        for mese in sorted(mesi):
            blocco = solution["by_month"].get(mese)
            if not blocco:
                continue
            for fr in sorted(blocco["by_brother"].keys()):
                for fam in (blocco["by_brother"][fr] or []):
                    fr_list = blocco["by_family"][fam]
                    k_found = next(
                        (k for k, name in enumerate(fr_list) if name == fr), None
                    )
                    freq = frequenze.get(fam, 2)
                    label = (
                        slot_label_with_month(mese, freq, k_found, week_windows)
                        if k_found is not None else ""
                    )
                    writer.writerow([fr, mese, fam, label])

    logging.info("CSV per fratello esportato: %s", path)


def export_storico_csv(storico_turni: list[dict], output_path: str | Path) -> None:
    """Esporta lo storico completo in CSV."""
    path = Path(output_path)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Mese", "Confermato", "Famiglia", "Fratello", "Slot"])
        for rec in storico_turni:
            if not isinstance(rec, dict):
                continue
            mese = rec.get("mese", "")
            confirmed = rec.get("confirmed_at", "")
            for a in rec.get("assegnazioni", []):
                if isinstance(a, dict):
                    writer.writerow([
                        mese, confirmed,
                        a.get("famiglia", ""), a.get("fratello", ""),
                        a.get("slot", 0),
                    ])
    logging.info("Storico CSV esportato: %s", path)


def import_csv_anagrafica(csv_path: str | Path) -> dict:
    """
    Importa fratelli e famiglie da un CSV.
    Formato atteso: tipo;nome;[capacita_o_frequenza]
    tipo: 'fratello' o 'famiglia'

    Ritorna {'fratelli': [(nome, cap)], 'famiglie': [(nome, freq)], 'errori': [str]}
    """
    path = Path(csv_path)
    result: dict = {"fratelli": [], "famiglie": [], "errori": []}

    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        for i, row in enumerate(reader, 1):
            if not row or (i == 1 and row[0].lower().startswith("tipo")):
                continue  # skip header
            if len(row) < 2:
                result["errori"].append(f"Riga {i}: campi insufficienti")
                continue
            tipo = row[0].strip().lower()
            nome = row[1].strip()
            valore = int(row[2].strip()) if len(row) > 2 and row[2].strip().isdigit() else None

            if tipo == "fratello":
                cap = valore if valore is not None and 0 <= valore <= 50 else 1
                result["fratelli"].append((nome, cap))
            elif tipo == "famiglia":
                freq = valore if valore in (1, 2, 4) else 2
                result["famiglie"].append((nome, freq))
            else:
                result["errori"].append(f"Riga {i}: tipo sconosciuto '{tipo}'")

    return result
