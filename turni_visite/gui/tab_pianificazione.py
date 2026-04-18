"""Tab Pianificazione: ottimizzazione turni, export PDF/CSV, modifica manuale."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from typing import TYPE_CHECKING

from ..config import DEFAULT_WEEK_TEMPLATES
from ..domain import TurniVisiteError, StoricoConflittoError
from ..pdf_export import export_pdf_mesi
from ..csv_export import export_csv_mesi
from ..scheduling import validate_month_yyyy_mm
from ..service import (
    conferma_e_salva_turni, diagnosi_infeasible, esegui_ottimizzazione,
    modifica_assegnazione, open_file, quick_check,
)
from ..weeks import parse_settimane_lista, slot_label_with_month

if TYPE_CHECKING:
    from ..repository import JsonRepository


def _validate_week_ranges(text: str | None, attese: int) -> tuple[bool, list[str] | str]:
    if text is None:
        return False, "Operazione annullata."
    raw = text.strip()
    if not raw:
        return False, "Campo vuoto."
    result, err = parse_settimane_lista(raw, attese)
    if result is not None:
        return True, result
    return False, err


def _ask_week_windows(
    mesi: list[str], frequenze: dict, famiglie: set,
    saved_templates: dict[str, list[str]],
) -> dict | None:
    """Chiede le finestre settimanali con CTkInputDialog."""
    week_windows: dict = {}
    freqs_presenti = sorted(
        {freq for f in famiglie if (freq := frequenze.get(f, 2)) in (1, 2, 4)}
    )
    defaults_map = {}
    for freq in freqs_presenti:
        template = saved_templates.get(str(freq))
        if template:
            defaults_map[freq] = ", ".join(template)
        else:
            defaults_map[freq] = ", ".join(DEFAULT_WEEK_TEMPLATES.get(freq, []))

    for mese in mesi:
        week_windows[mese] = {}
        for freq in freqs_presenti:
            fam_con_freq = [f for f in famiglie if frequenze.get(f, 2) == freq]
            if not fam_con_freq:
                continue
            while True:
                dialog = ctk.CTkInputDialog(
                    title=f"Settimane {mese} (freq {freq})",
                    text=f"Intervalli gg-gg per frequenza {freq}\n"
                         f"(attesi {freq} intervalli, es: {defaults_map[freq]}):",
                )
                s = dialog.get_input()
                if s is None:
                    return None
                if not s.strip():
                    s = defaults_map[freq]
                ok, res = _validate_week_ranges(s, freq)
                if ok:
                    week_windows[mese][freq] = res
                    break
                messagebox.showerror("Errore", res)

    return week_windows


class TabPianificazione(ctk.CTkFrame):
    def __init__(self, parent, repo: "JsonRepository",
                 set_status=None, on_storico_change=None, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self._set_status = set_status
        self._on_storico_change = on_storico_change
        self._btn_ottimizza: ctk.CTkButton | None = None
        self._last_result = None
        self._last_mesi: list[str] = []
        self._last_snap: dict = {}
        self._last_week_windows: dict = {}
        self._build()

    def _build(self) -> None:
        # Mesi + cooldown
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(top, text="Mesi (YYYY-MM, virgola):").pack(side="left")
        self.entry_mesi = ctk.CTkEntry(top, width=350, placeholder_text="2026-05, 2026-06")
        self.entry_mesi.pack(side="left", padx=8)
        ctk.CTkLabel(top, text="Cooldown:").pack(side="left", padx=(12, 4))
        self.entry_cooldown = ctk.CTkEntry(top, width=50)
        self.entry_cooldown.pack(side="left")
        self.entry_cooldown.insert(0, str(self.repo.get_setting("cooldown_mesi", 3)))

        # Solver settings
        settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        settings_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(settings_frame, text="Timeout (s):").pack(side="left")
        self.entry_timeout = ctk.CTkEntry(settings_frame, width=60)
        self.entry_timeout.pack(side="left", padx=4)
        self.entry_timeout.insert(0, str(self.repo.get_setting("solver_timeout", 20)))
        ctk.CTkLabel(settings_frame, text="Thread:").pack(side="left", padx=(12, 4))
        self.entry_workers = ctk.CTkEntry(settings_frame, width=50)
        self.entry_workers.pack(side="left", padx=4)
        self.entry_workers.insert(0, str(self.repo.get_setting("solver_workers", 8)))

        # Pulsanti
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=6)
        ctk.CTkButton(btn_frame, text="Pre-check fattibilita'", width=180,
                       command=self._pre_check).pack(side="left", padx=4)
        self._btn_ottimizza = ctk.CTkButton(
            btn_frame, text="Ottimizza & Genera PDF", width=200,
            command=self.optimize_and_export,
        )
        self._btn_ottimizza.pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Esporta CSV", width=120,
                       command=self._export_csv).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Salva template settimane", width=200,
                       command=self._save_week_templates).pack(side="right", padx=4)

        # Output
        self.txt_output = ctk.CTkTextbox(self, corner_radius=8)
        self.txt_output.pack(fill="both", expand=True, padx=10, pady=6)

    def _status(self, msg: str) -> None:
        if self._set_status:
            self._set_status(msg)

    def _parse_mesi(self) -> list[str] | None:
        raw = self.entry_mesi.get().strip()
        if not raw:
            messagebox.showerror("Errore", "Inserisci almeno un mese.")
            return None
        mesi = [m.strip() for m in raw.split(",") if m.strip()]
        try:
            return [validate_month_yyyy_mm(m) for m in mesi]
        except ValueError as e:
            messagebox.showerror("Errore", str(e))
            return None

    def _pre_check(self) -> None:
        mesi = self._parse_mesi()
        if not mesi:
            return
        snap = self.repo.data_snapshot()
        cooldown = int(self.entry_cooldown.get() or 3)
        result = quick_check(snap, mesi, self.repo.get_storico_turni(), cooldown)

        self.txt_output.delete("1.0", "end")
        if result["fattibile"]:
            self.txt_output.insert("end", "Pre-check OK: nessun problema rilevato.\n\n")
        else:
            self.txt_output.insert("end", "Pre-check: PROBLEMI RILEVATI\n\n")
            for p in result["problemi"]:
                self.txt_output.insert("end", f"  PROBLEMA: {p}\n")
        if result["avvisi"]:
            self.txt_output.insert("end", "\nAvvisi:\n")
            for a in result["avvisi"]:
                self.txt_output.insert("end", f"  {a}\n")

    def optimize_and_export(self) -> None:
        mesi = self._parse_mesi()
        if not mesi:
            return
        try:
            cooldown = int(self.entry_cooldown.get() or 3)
            self.repo.set_setting("cooldown_mesi", cooldown)
            timeout = float(self.entry_timeout.get() or 20)
            workers = int(self.entry_workers.get() or 8)
            self.repo.set_setting("solver_timeout", timeout)
            self.repo.set_setting("solver_workers", workers)
        except (ValueError, TurniVisiteError) as e:
            messagebox.showerror("Errore", str(e))
            return

        snap = self.repo.data_snapshot()
        week_windows = _ask_week_windows(mesi, snap["frequenze"], snap["famiglie"],
                                          self.repo.week_templates)
        if week_windows is None:
            self._status("Operazione annullata.")
            return

        self._status("Ottimizzazione in corso...")
        self._btn_ottimizza.configure(state="disabled")

        def _run() -> None:
            try:
                result = esegui_ottimizzazione(
                    snap=snap, mesi=mesi,
                    storico_turni=self.repo.get_storico_turni(),
                    cooldown=cooldown, solver_timeout=timeout, solver_workers=workers,
                )
                self.after(0, lambda: self._on_solve_done(result, mesi, snap, cooldown, week_windows))
            except RuntimeError as e:
                err = str(e)
                self.after(0, lambda: self._on_solve_error(err))

        threading.Thread(target=_run, daemon=True).start()

    def _on_solve_error(self, err: str) -> None:
        messagebox.showerror("Errore", err)
        self._btn_ottimizza.configure(state="normal")
        self._status("Errore durante l'ottimizzazione.")

    def _on_solve_done(self, result, mesi, snap, cooldown, week_windows) -> None:
        self._btn_ottimizza.configure(state="normal")

        if not result.feasible:
            msg = diagnosi_infeasible(
                snap=snap, mesi=mesi,
                storico_turni=self.repo.get_storico_turni(), cooldown=cooldown,
            )
            self.txt_output.delete("1.0", "end")
            self.txt_output.insert("end", "Nessuna soluzione trovata.\n\n" + msg + "\n")
            self._status("Nessuna soluzione trovata.")
            return

        self._last_result = result
        self._last_mesi = mesi
        self._last_snap = snap
        self._last_week_windows = week_windows
        self._show_solution(result, mesi, snap, week_windows)

        # Conferma
        if not messagebox.askyesno("Conferma piano", "Confermare il piano e generare il PDF?"):
            self._status("Operazione annullata.")
            return

        # Salva PDF
        nome_file = "turni_" + "-".join(mesi) + ".pdf"
        pdf_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf"), ("Tutti", "*.*")],
            initialfile=nome_file, title="Salva PDF turni",
        )
        if not pdf_path:
            self._status("PDF non salvato.")
            return

        try:
            export_pdf_mesi(mesi, result.solution, snap["frequenze"], week_windows, output_path=pdf_path)
        except OSError as e:
            messagebox.showerror("Errore PDF", str(e))
            return

        open_file(pdf_path)

        try:
            salvati = conferma_e_salva_turni(self.repo, mesi, result.solution)
            self._status(f"PDF creato. Turni salvati: {', '.join(salvati)}.")
            if self._on_storico_change:
                self._on_storico_change()
        except StoricoConflittoError as e:
            messagebox.showwarning("Storico", str(e))
            self._status("PDF creato, storico NON salvato.")

    def _show_solution(self, result, mesi, snap, week_windows) -> None:
        self.txt_output.delete("1.0", "end")
        for mese in mesi:
            blocco = result.solution["by_month"][mese]
            self.txt_output.insert("end", f"\n=== {mese} - Visite per FRATELLO ===\n")
            for fr in sorted(blocco["by_brother"].keys()):
                for fam in (blocco["by_brother"][fr] or []):
                    fr_list = blocco["by_family"][fam]
                    k_found = next((k for k, name in enumerate(fr_list) if name == fr), None)
                    freq = snap["frequenze"].get(fam, 2)
                    label = (
                        slot_label_with_month(mese, freq, k_found, week_windows)
                        if k_found is not None else ""
                    )
                    self.txt_output.insert("end", f"  [{label}] {fr} -- {fam}\n")

    def _export_csv(self) -> None:
        if not self._last_result or not self._last_result.solution:
            messagebox.showinfo("Info", "Esegui prima l'ottimizzazione.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tutti", "*.*")],
            initialfile="turni_" + "-".join(self._last_mesi) + ".csv",
        )
        if not path:
            return
        try:
            export_csv_mesi(self._last_mesi, self._last_result.solution,
                            self._last_snap["frequenze"], self._last_week_windows, path)
            open_file(path)
            self._status(f"CSV esportato: {path}")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def _save_week_templates(self) -> None:
        for freq in (1, 2, 4):
            current = self.repo.get_week_template(freq)
            default = ", ".join(current) if current else ", ".join(DEFAULT_WEEK_TEMPLATES.get(freq, []))
            dialog = ctk.CTkInputDialog(
                title=f"Template freq {freq}",
                text=f"Intervalli per frequenza {freq} (gg-gg, virgola):",
            )
            val = dialog.get_input()
            if val is None:
                return
            if not val.strip():
                val = default
            ok, res = _validate_week_ranges(val, freq)
            if ok:
                self.repo.set_week_template(freq, res)
            else:
                messagebox.showerror("Errore", f"Frequenza {freq}: {res}")
                return
        self._status("Template settimane salvati.")
