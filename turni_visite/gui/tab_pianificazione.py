"""Tab Pianificazione: ottimizzazione turni, export PDF/CSV, modifica manuale."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText
from typing import TYPE_CHECKING

from ..config import DEFAULT_WEEK_TEMPLATES
from ..domain import TurniVisiteError, StoricoConflittoError
from ..pdf_export import export_pdf_mesi
from ..csv_export import export_csv_mesi, export_csv_per_fratello
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
    root: tk.Widget,
    mesi: list[str],
    frequenze: dict,
    famiglie: set,
    saved_templates: dict[str, list[str]],
) -> dict | None:
    """Chiede le finestre settimanali, usando i template salvati come default."""
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
                msg = (
                    f"Intervalli settimanali per famiglie con frequenza {freq} "
                    f"(mese {mese}).\nFormato: gg-gg separati da virgola\n"
                    f"Attesi {freq} intervalli."
                )
                s = simpledialog.askstring(
                    f"Settimane per {mese} (frequenza {freq})",
                    msg, parent=root, initialvalue=defaults_map[freq],
                )
                if s is None:
                    return None
                ok, res = _validate_week_ranges(s, freq)
                if ok:
                    week_windows[mese][freq] = res
                    break
                messagebox.showerror("Errore di validazione", res, parent=root)

    return week_windows


class TabPianificazione(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, repo: "JsonRepository",
                 theme: dict, set_status=None, on_storico_change=None, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self.theme = theme
        self._set_status = set_status
        self._on_storico_change = on_storico_change
        self._btn_ottimizza: ttk.Button | None = None
        self._last_result = None
        self._last_mesi: list[str] = []
        self._last_snap: dict = {}
        self._last_week_windows: dict = {}
        self._build()

    def _build(self) -> None:
        pad = {"padx": 6, "pady": 6}

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Mesi (YYYY-MM) separati da virgola:").pack(side="left")
        self.entry_mesi = ttk.Entry(top)
        self.entry_mesi.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Label(top, text="Cooldown:").pack(side="left", padx=(8, 2))
        self.var_cooldown = tk.IntVar(value=int(self.repo.get_setting("cooldown_mesi", 3)))
        ttk.Spinbox(top, from_=1, to=6, textvariable=self.var_cooldown, width=3).pack(side="left")

        # Solver settings
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill="x", **pad)
        ttk.Label(settings_frame, text="Timeout solver (s):").pack(side="left")
        self.var_timeout = tk.DoubleVar(value=float(self.repo.get_setting("solver_timeout", 20.0)))
        ttk.Spinbox(settings_frame, from_=5, to=120, textvariable=self.var_timeout, width=5).pack(side="left", padx=4)
        ttk.Label(settings_frame, text="Thread solver:").pack(side="left", padx=(8, 2))
        self.var_workers = tk.IntVar(value=int(self.repo.get_setting("solver_workers", 8)))
        ttk.Spinbox(settings_frame, from_=1, to=16, textvariable=self.var_workers, width=3).pack(side="left", padx=4)

        # Pulsanti azione
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", **pad)

        ttk.Button(btn_frame, text="Pre-check fattibilita'", command=self._pre_check).pack(side="left", padx=4)
        self._btn_ottimizza = ttk.Button(btn_frame, text="Ottimizza & Genera PDF", command=self.optimize_and_export)
        self._btn_ottimizza.pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Esporta CSV", command=self._export_csv).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Salva template settimane", command=self._save_week_templates).pack(side="right", padx=4)

        # Output
        self.txt_output = ScrolledText(self, wrap="word", height=20,
                                        bg=self.theme.get("text_bg", "#fff"),
                                        fg=self.theme.get("text_fg", "#000"))
        self.txt_output.pack(fill="both", expand=True, **pad)

    def _status(self, msg: str) -> None:
        if self._set_status:
            self._set_status(msg)

    def _parse_mesi(self) -> list[str] | None:
        raw = self.entry_mesi.get().strip()
        if not raw:
            messagebox.showerror("Errore", "Inserisci almeno un mese (es. 2026-05).", parent=self)
            return None
        mesi = [m.strip() for m in raw.split(",") if m.strip()]
        try:
            return [validate_month_yyyy_mm(m) for m in mesi]
        except ValueError as e:
            messagebox.showerror("Errore", str(e), parent=self)
            return None

    def _pre_check(self) -> None:
        mesi = self._parse_mesi()
        if not mesi:
            return
        snap = self.repo.data_snapshot()
        cooldown = int(self.var_cooldown.get() or 3)
        result = quick_check(snap, mesi, self.repo.get_storico_turni(), cooldown)

        self.txt_output.delete("1.0", tk.END)
        if result["fattibile"]:
            self.txt_output.insert(tk.END, "Pre-check OK: nessun problema rilevato.\n\n")
        else:
            self.txt_output.insert(tk.END, "Pre-check: PROBLEMI RILEVATI\n\n")
            for p in result["problemi"]:
                self.txt_output.insert(tk.END, f"  PROBLEMA: {p}\n")
        if result["avvisi"]:
            self.txt_output.insert(tk.END, "\nAvvisi:\n")
            for a in result["avvisi"]:
                self.txt_output.insert(tk.END, f"  {a}\n")
        self.txt_output.see(tk.END)

    def optimize_and_export(self) -> None:
        mesi = self._parse_mesi()
        if not mesi:
            return
        try:
            cooldown = int(self.var_cooldown.get() or 3)
            self.repo.set_setting("cooldown_mesi", cooldown)
            self.repo.set_setting("solver_timeout", float(self.var_timeout.get()))
            self.repo.set_setting("solver_workers", int(self.var_workers.get()))
        except (ValueError, TurniVisiteError) as e:
            messagebox.showerror("Errore", str(e), parent=self)
            return

        snap = self.repo.data_snapshot()
        week_windows = _ask_week_windows(
            self, mesi, snap["frequenze"], snap["famiglie"],
            self.repo.week_templates,
        )
        if week_windows is None:
            self._status("Operazione annullata.")
            return

        self._status("Ottimizzazione in corso...")
        self._btn_ottimizza.configure(state="disabled")

        timeout = float(self.var_timeout.get())
        workers = int(self.var_workers.get())

        def _run() -> None:
            try:
                result = esegui_ottimizzazione(
                    snap=snap, mesi=mesi,
                    storico_turni=self.repo.get_storico_turni(),
                    cooldown=cooldown,
                    solver_timeout=timeout,
                    solver_workers=workers,
                )
                self.after(0, lambda: self._on_solve_done(result, mesi, snap, cooldown, week_windows))
            except RuntimeError as e:
                err = str(e)
                self.after(0, lambda: self._on_solve_error(err))

        threading.Thread(target=_run, daemon=True).start()

    def _on_solve_error(self, err: str) -> None:
        messagebox.showerror("Errore", err, parent=self)
        self._btn_ottimizza.configure(state="normal")
        self._status("Errore durante l'ottimizzazione.")

    def _on_solve_done(self, result, mesi, snap, cooldown, week_windows) -> None:
        self._btn_ottimizza.configure(state="normal")

        if not result.feasible:
            msg = diagnosi_infeasible(
                snap=snap, mesi=mesi,
                storico_turni=self.repo.get_storico_turni(),
                cooldown=cooldown,
            )
            self.txt_output.delete("1.0", tk.END)
            self.txt_output.insert(tk.END, "Nessuna soluzione trovata (infeasible).\n\n" + msg + "\n")
            self.txt_output.see(tk.END)
            self._status("Nessuna soluzione trovata.")
            return

        self._last_result = result
        self._last_mesi = mesi
        self._last_snap = snap
        self._last_week_windows = week_windows

        self._show_solution(result, mesi, snap, week_windows)

        # Conferma con anteprima
        preview = self.txt_output.get("1.0", tk.END).strip()
        if not self._confirm_plan(preview):
            self._status("Operazione annullata.")
            return

        # Salva PDF
        nome_file = "turni_" + "-".join(mesi) + ".pdf"
        pdf_path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf"), ("Tutti", "*.*")],
            initialfile=nome_file, title="Salva PDF turni",
        )
        if not pdf_path:
            self._status("PDF non salvato.")
            return

        try:
            export_pdf_mesi(mesi, result.solution, snap["frequenze"], week_windows, output_path=pdf_path)
        except OSError as e:
            messagebox.showerror("Errore PDF", str(e), parent=self)
            self._status("Errore nel salvataggio del PDF.")
            return

        # Apertura automatica PDF
        open_file(pdf_path)

        # Salva storico
        try:
            salvati = conferma_e_salva_turni(self.repo, mesi, result.solution)
            self._status(f"PDF creato e aperto. Turni salvati: {', '.join(salvati)}.")
            if self._on_storico_change:
                self._on_storico_change()
        except StoricoConflittoError as e:
            messagebox.showwarning("Storico gia' presente", str(e), parent=self)
            self._status("PDF creato, storico NON salvato (mesi duplicati).")

    def _show_solution(self, result, mesi, snap, week_windows) -> None:
        self.txt_output.delete("1.0", tk.END)
        for mese in mesi:
            blocco = result.solution["by_month"][mese]
            self.txt_output.insert(tk.END, f"\n=== {mese} - Visite per FRATELLO ===\n")
            for fr in sorted(blocco["by_brother"].keys()):
                for fam in (blocco["by_brother"][fr] or []):
                    fr_list = blocco["by_family"][fam]
                    k_found = next((k for k, name in enumerate(fr_list) if name == fr), None)
                    freq = snap["frequenze"].get(fam, 2)
                    label = (
                        slot_label_with_month(mese, freq, k_found, week_windows)
                        if k_found is not None else ""
                    )
                    self.txt_output.insert(tk.END, f"  [{label}] {fr} -- {fam}\n")
        self.txt_output.see(tk.END)

    def _confirm_plan(self, content: str) -> bool:
        result_holder: list[bool] = [False]
        top = tk.Toplevel(self)
        top.title("Conferma piano turni")
        top.grab_set()

        txt = ScrolledText(top, wrap="word", width=80, height=24)
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert(tk.END, content)
        txt.configure(state="disabled")

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Label(btn_frame, text="Puoi modificare assegnazioni prima di confermare:").pack(side="left")

        def _modify():
            self._modify_assignment_dialog(top)
            # Aggiorna preview
            txt.configure(state="normal")
            txt.delete("1.0", tk.END)
            self._show_solution(self._last_result, self._last_mesi, self._last_snap, self._last_week_windows)
            txt.insert(tk.END, self.txt_output.get("1.0", tk.END))
            txt.configure(state="disabled")

        def _ok():
            result_holder[0] = True
            top.destroy()

        ttk.Button(btn_frame, text="Modifica assegnazione", command=_modify).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Conferma e salva", command=_ok).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Annulla", command=top.destroy).pack(side="right")

        top.wait_window()
        return result_holder[0]

    def _modify_assignment_dialog(self, parent_win) -> None:
        """Dialog per modificare manualmente una singola assegnazione."""
        if not self._last_result or not self._last_result.solution:
            return
        sol = self._last_result.solution
        mesi = self._last_mesi
        snap = self._last_snap

        # Seleziona mese
        mese = simpledialog.askstring("Mese", "Mese da modificare:", parent=parent_win,
                                       initialvalue=mesi[0] if mesi else "")
        if not mese or mese not in [m for m in mesi]:
            return

        # Seleziona famiglia
        famiglie = sorted(sol["by_month"][mese]["by_family"].keys())
        fam = simpledialog.askstring("Famiglia", f"Famiglia ({', '.join(famiglie)}):",
                                      parent=parent_win)
        if not fam or fam not in famiglie:
            messagebox.showerror("Errore", "Famiglia non valida.", parent=parent_win)
            return

        # Mostra slot attuali
        fr_list = sol["by_month"][mese]["by_family"][fam]
        slot_info = "\n".join(f"  Slot {k}: {fr}" for k, fr in enumerate(fr_list))
        slot_str = simpledialog.askstring(
            "Slot", f"Assegnazioni attuali:\n{slot_info}\n\nNumero slot da modificare (0-{len(fr_list)-1}):",
            parent=parent_win,
        )
        if slot_str is None:
            return
        try:
            slot = int(slot_str)
        except ValueError:
            messagebox.showerror("Errore", "Numero slot non valido.", parent=parent_win)
            return

        # Seleziona nuovo fratello
        assoc = snap["associazioni"].get(fam, [])
        nuovo = simpledialog.askstring(
            "Fratello", f"Fratelli disponibili: {', '.join(assoc)}\nNuovo fratello per slot {slot}:",
            parent=parent_win,
        )
        if not nuovo:
            return

        try:
            modifica_assegnazione(sol, mese, fam, slot, nuovo)
        except ValueError as e:
            messagebox.showerror("Errore", str(e), parent=parent_win)

    def _export_csv(self) -> None:
        if not self._last_result or not self._last_result.solution:
            messagebox.showinfo("Info", "Nessuna soluzione da esportare. Esegui prima l'ottimizzazione.", parent=self)
            return

        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tutti", "*.*")],
            initialfile="turni_" + "-".join(self._last_mesi) + ".csv",
            title="Esporta turni CSV",
        )
        if not path:
            return
        try:
            export_csv_mesi(
                self._last_mesi, self._last_result.solution,
                self._last_snap["frequenze"], self._last_week_windows, path,
            )
            open_file(path)
            self._status(f"CSV esportato: {path}")
        except Exception as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def _save_week_templates(self) -> None:
        """Salva i template delle finestre settimanali nel repository."""
        for freq in (1, 2, 4):
            default = ", ".join(DEFAULT_WEEK_TEMPLATES.get(freq, []))
            current = self.repo.get_week_template(freq)
            if current:
                default = ", ".join(current)
            val = simpledialog.askstring(
                f"Template freq {freq}",
                f"Intervalli per frequenza {freq} (gg-gg, virgola):",
                parent=self, initialvalue=default,
            )
            if val is None:
                return
            ok, res = _validate_week_ranges(val, freq)
            if ok:
                self.repo.set_week_template(freq, res)
            else:
                messagebox.showerror("Errore", f"Frequenza {freq}: {res}", parent=self)
                return
        self._status("Template settimane salvati.")
