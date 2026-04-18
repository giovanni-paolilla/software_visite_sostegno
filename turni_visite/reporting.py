from .weeks import slot_label_with_month


def print_reports_mesi(
    mesi: list[str],
    solution: dict,
    frequenze: dict[str, int],
    week_windows: dict,
) -> None:
    """Stampa a video i report testuali per ogni mese pianificato."""
    if not solution or "by_month" not in solution or not solution["by_month"]:
        print("\nNessuna soluzione memorizzata.")
        return

    for mese in mesi:
        blocco = solution["by_month"].get(mese)
        if not blocco:
            continue

        print(f"\n=== Mese {mese} — Visite per FAMIGLIA ===")
        for fam in sorted(blocco["by_family"].keys()):
            fr_list = blocco["by_family"][fam]
            freq = frequenze.get(fam, 2)
            items = [
                f"{fr} [{slot_label_with_month(mese, freq, k, week_windows)}]"
                for k, fr in enumerate(fr_list)
            ]
            print(f"- {fam} (freq {freq}/mese): {', '.join(items)}")

        print(f"\n=== Mese {mese} — Visite per FRATELLO ===")
        for fr in sorted(blocco["by_brother"].keys()):
            fams = blocco["by_brother"][fr] or []
            if not fams:
                print(f"- {fr}: (nessuna visita)")
                continue
            for fam in fams:
                fr_list = blocco["by_family"][fam]
                k_found = next(
                    (k for k, name in enumerate(fr_list) if name == fr),
                    None,
                )
                if k_found is not None:
                    freq = frequenze.get(fam, 2)
                    lab = slot_label_with_month(mese, freq, k_found, week_windows)
                    print(f"- {fr}: {fam} [{lab}]")
                else:
                    print(f"- {fr}: {fam}")
