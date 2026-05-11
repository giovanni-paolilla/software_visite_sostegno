"""Tab Pianificazione: ottimizzazione turni, export PDF/CSV/WhatsApp, modifica manuale, bozza."""
from __future__ import annotations

import threading
from tkinter import filedialog, messagebox
import customtkinter as ctk
from typing import TYPE_CHECKING, Any

from ..config import DEFAULT_WEEK_TEMPLATES
from ..domain import (
    TurniVisiteError, StoricoConflittoError, NON_ASSEGNATO,
    STATO_BOZZA_PROPOSTO, STATO_BOZZA_ACCETTATO, STATO_BOZZA_RIFIUTATO,
)
from ..pdf_export import export_pdf_mesi
from ..csv_export import export_csv_mesi
from ..notifications import send_notifications
from ..whatsapp_export import format_whatsapp_mesi
from ..service import (
    diagnosi_infeasible, esegui_ottimizzazione,
    modifica_assegnazione, open_file, quick_check,
)
from ..weeks import parse_settimane_lista, slot_label_with_month
from ..i18n import t
from .themes import BUTTON_COLORS

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


def _compute_month_weeks(mese: str) -> list[str]:
    """Return Monday-Sunday week intervals (DD-DD) covering *mese* (YYYY-MM)."""
    from datetime import date, timedelta
    year, month = int(mese[:4]), int(mese[5:7])
    first_day = date(year, month, 1)
    last_day = date(year + (month // 12), (month % 12) + 1, 1) - timedelta(days=1)
    monday = first_day - timedelta(days=first_day.weekday())
    weeks: list[str] = []
    while monday <= last_day:
        sunday = monday + timedelta(days=6)
        weeks.append(f"{monday.day:02d}-{sunday.day:02d}")
        monday += timedelta(days=7)
    return weeks


def _ask_week_windows(
    mesi: list[str], frequenze: dict, famiglie: set,
    saved_templates: dict[str, list[str]],
    parent=None,
) -> dict | None:
    """Show dialog with dropdown menus for week selection per month/freq."""
    freqs_presenti = sorted(
        {freq for f in famiglie if (freq := frequenze.get(f, 2)) in (1, 2, 4)}
    )
    freqs_presenti = [
        freq for freq in freqs_presenti
        if any(frequenze.get(f, 2) == freq for f in famiglie)
    ]
    if not freqs_presenti:
        return {m: {} for m in mesi}

    result_container: list[dict | None] = [None]
    parent_window = parent.winfo_toplevel() if parent is not None else None
    dialog = ctk.CTkToplevel(parent_window) if parent_window is not None else ctk.CTkToplevel()
    dialog.withdraw()
    dialog.title(t("configura_settimane"))
    dialog.geometry("700x500")
    dialog.minsize(600, 360)
    dialog.resizable(True, True)
    if (
        parent_window is not None
        and parent_window.winfo_exists()
        and parent_window.winfo_viewable()
    ):
        try:
            dialog.transient(parent_window)
        except Exception:
            pass

    scroll = ctk.CTkScrollableFrame(dialog)
    scroll.pack(fill="both", expand=True, padx=10, pady=10)

    menus: dict[tuple[str, int], list[ctk.CTkOptionMenu]] = {}

    for mese in mesi:
        ctk.CTkLabel(scroll, text=f"--- {mese} ---",
                      font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=4, pady=(10, 4))
        weeks = _compute_month_weeks(mese)

        for freq in freqs_presenti:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row,
                          text=f"Freq {freq} ({freq} intervalli):").pack(
                side="left", padx=(0, 8))

            saved = saved_templates.get(str(freq), [])
            menu_list: list[ctk.CTkOptionMenu] = []
            n_weeks = len(weeks)
            for slot_idx in range(freq):
                menu = ctk.CTkOptionMenu(row, width=90, values=weeks)
                menu.pack(side="left", padx=4)
                if slot_idx < len(saved) and saved[slot_idx] in weeks:
                    menu.set(saved[slot_idx])
                elif n_weeks > 0:
                    pick = min(int(slot_idx * n_weeks / freq), n_weeks - 1)
                    menu.set(weeks[pick])
                menu_list.append(menu)
            menus[(mese, freq)] = menu_list

    def _on_confirm():
        week_windows: dict = {}
        for mese in mesi:
            week_windows[mese] = {}
            for freq in freqs_presenti:
                week_windows[mese][freq] = [m.get() for m in menus[(mese, freq)]]
        result_container[0] = week_windows
        try:
            dialog.grab_release()
        except Exception:
            pass
        dialog.destroy()

    def _on_cancel():
        result_container[0] = None
        try:
            dialog.grab_release()
        except Exception:
            pass
        dialog.destroy()

    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(fill="x", padx=10, pady=(0, 10))
    ctk.CTkButton(btn_frame, text=t("conferma"), width=120,
                   command=_on_confirm).pack(side="right", padx=4)
    ctk.CTkButton(btn_frame, text=t("annulla"), width=120,
                   fg_color=BUTTON_COLORS["danger"],
                   hover_color=BUTTON_COLORS["danger_hover"],
                   command=_on_cancel).pack(side="right", padx=4)

    dialog.protocol("WM_DELETE_WINDOW", _on_cancel)
    dialog.update_idletasks()
    dialog.deiconify()
    dialog.lift()
    dialog.focus_force()
    dialog.grab_set()

    dialog.wait_window()
    return result_container[0]


class TabPianificazione(ctk.CTkFrame):
    def __init__(self, parent, repo: "JsonRepository",
                 set_status=None, on_storico_change=None, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self._set_status = set_status
        self._on_storico_change = on_storico_change
        self._btn_ottimizza: ctk.CTkButton | None = None
        self._lock = threading.Lock()
        self._last_result: Any = None
        self._last_mesi: list[str] = []
        self._last_snap: dict = {}
        self._last_week_windows: dict = {}
        self._alive = threading.Event()
        self._alive.set()
        self._build()

    def destroy(self) -> None:
        self._alive.clear()
        super().destroy()

    def reset_solution(self) -> None:
        with self._lock:
            self._last_result = None
            self._last_snap = {}
            self._last_mesi = []
            self._last_week_windows = {}
        self.txt_output.configure(state="normal")
        self.txt_output.delete("1.0", "end")
        self.txt_output.configure(state="disabled")
        if hasattr(self, "_review_scroll"):
            for w in self._review_scroll.winfo_children():
                w.destroy()
            self._row_widgets = []
        if hasattr(self, "_btn_export_csv"):
            self._btn_export_csv.configure(state="disabled")
        if hasattr(self, "_btn_whatsapp"):
            self._btn_whatsapp.configure(state="disabled")

    _MESI_BREVI = [
        "Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
        "Lug", "Ago", "Set", "Ott", "Nov", "Dic",
    ]

    def _build(self) -> None:
        # Selettore mesi: Anno + Da mese + A mese
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=6)

        from datetime import date
        cur_year = date.today().year
        anni = [str(y) for y in range(cur_year - 2, cur_year + 11)]
        mesi_labels = [f"{i:02d} - {self._MESI_BREVI[i - 1]}" for i in range(1, 13)]

        ctk.CTkLabel(top, text="Anno:").pack(side="left", padx=(0, 4))
        self._combo_anno = ctk.CTkOptionMenu(top, width=80, values=anni)
        self._combo_anno.pack(side="left", padx=2)
        self._combo_anno.set(str(cur_year))

        ctk.CTkLabel(top, text="Da:").pack(side="left", padx=(12, 4))
        self._combo_da = ctk.CTkOptionMenu(top, width=120, values=mesi_labels)
        self._combo_da.pack(side="left", padx=2)
        cur_m = date.today().month
        self._combo_da.set(mesi_labels[cur_m - 1])

        ctk.CTkLabel(top, text="A:").pack(side="left", padx=(12, 4))
        self._combo_a = ctk.CTkOptionMenu(top, width=120, values=mesi_labels)
        self._combo_a.pack(side="left", padx=2)
        self._combo_a.set(mesi_labels[cur_m - 1])

        # Solver settings
        settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        settings_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(settings_frame, text=t("pianificazione.cooldown")).pack(side="left")
        self.entry_cooldown = ctk.CTkEntry(settings_frame, width=50)
        self.entry_cooldown.pack(side="left", padx=4)
        self.entry_cooldown.insert(0, str(self.repo.get_setting("cooldown_mesi", 3)))
        ctk.CTkLabel(settings_frame, text=t("pianificazione.timeout")).pack(side="left", padx=(12, 4))
        self.entry_timeout = ctk.CTkEntry(settings_frame, width=60)
        self.entry_timeout.pack(side="left", padx=4)
        self.entry_timeout.insert(0, str(self.repo.get_setting("solver_timeout", 20)))
        ctk.CTkLabel(settings_frame, text=t("pianificazione.thread")).pack(side="left", padx=(12, 4))
        self.entry_workers = ctk.CTkEntry(settings_frame, width=50)
        self.entry_workers.pack(side="left", padx=4)
        self.entry_workers.insert(0, str(self.repo.get_setting("solver_workers", 8)))

        # Pulsanti principali
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=6)
        ctk.CTkButton(btn_frame, text=t("pianificazione.pre_check"), width=180,
                       command=self._pre_check).pack(side="left", padx=4)
        self._btn_ottimizza = ctk.CTkButton(
            btn_frame, text=t("pianificazione.ottimizza"), width=200,
            command=self.optimize_and_export,
        )
        self._btn_ottimizza.pack(side="left", padx=4)
        self._btn_export_csv = ctk.CTkButton(
            btn_frame, text=t("pianificazione.esporta_csv"), width=120,
            command=self._export_csv, state="disabled")
        self._btn_export_csv.pack(side="left", padx=4)
        self._btn_whatsapp = ctk.CTkButton(
            btn_frame, text=t("pianificazione.copia_whatsapp"), width=140,
            command=self._copy_whatsapp, state="disabled")
        self._btn_whatsapp.pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text=t("pianificazione.salva_template"), width=200,
                       command=self._save_week_templates).pack(side="right", padx=4)

        # Progress bar (indeterminate, hidden by default)
        self._progress = ctk.CTkProgressBar(self, mode="indeterminate", height=6)
        # Not packed initially — shown during optimization

        # Pulsanti bozza/conferma
        draft_frame = ctk.CTkFrame(self, fg_color="transparent")
        draft_frame.pack(fill="x", padx=10, pady=4)
        self._btn_save_draft = ctk.CTkButton(
            draft_frame, text=t("pianificazione.salva_bozza"), width=140,
            command=self._save_draft)
        self._btn_save_draft.pack(side="left", padx=4)
        self._btn_accept_all = ctk.CTkButton(
            draft_frame, text=t("pianificazione.accetta_tutti"), width=120,
            command=self._accept_all)
        self._btn_accept_all.pack(side="left", padx=4)
        self._btn_confirm = ctk.CTkButton(
            draft_frame, text=t("pianificazione.conferma_selezionati"), width=180,
            fg_color="#107c10", hover_color="#0b5e0b",
            command=self._confirm_draft)
        self._btn_confirm.pack(side="left", padx=4)
        self._btn_discard = ctk.CTkButton(
            draft_frame, text=t("pianificazione.scarta_bozza"), width=120,
            fg_color=BUTTON_COLORS["danger"],
            hover_color=BUTTON_COLORS["danger_hover"],
            command=self._discard_draft)
        self._btn_discard.pack(side="left", padx=4)

        # === Area principale: Revisione interattiva + Dettaglio testo ===
        self._tabview = ctk.CTkTabview(self, corner_radius=8)
        self._tabview.pack(fill="both", expand=True, padx=10, pady=6)
        self._tab_review_name = t("pianificazione.tab_revisione")
        self._tab_text_name = t("pianificazione.tab_dettaglio")
        tab_review = self._tabview.add(self._tab_review_name)
        tab_text = self._tabview.add(self._tab_text_name)
        self._build_review_tab(tab_review)
        self.txt_output = ctk.CTkTextbox(tab_text, corner_radius=8)
        self.txt_output.pack(fill="both", expand=True)
        self.txt_output.configure(state="disabled")

    def _status(self, msg: str) -> None:
        if self._set_status:
            self._set_status(msg)

    def _parse_mesi(self) -> list[str] | None:
        try:
            anno = int(self._combo_anno.get())
            da_m = int(self._combo_da.get().split(" - ")[0])
            a_m = int(self._combo_a.get().split(" - ")[0])
        except (ValueError, IndexError):
            messagebox.showerror(t("errore"), "Seleziona anno e mesi validi.")
            return None
        if da_m > a_m:
            da_m, a_m = a_m, da_m
        return [f"{anno}-{m:02d}" for m in range(da_m, a_m + 1)]

    def _pre_check(self) -> None:
        mesi = self._parse_mesi()
        if not mesi:
            return
        snap = self.repo.data_snapshot()
        try:
            cooldown = int(self.entry_cooldown.get() or 3)
        except ValueError:
            messagebox.showerror(t("errore"), "Cooldown deve essere un numero intero.")
            return
        result = quick_check(snap, mesi, self.repo.get_storico_turni(), cooldown)

        self.txt_output.configure(state="normal")
        self.txt_output.delete("1.0", "end")
        if result["fattibile"]:
            self.txt_output.insert("end", t("pre_check_ok") + "\n\n")
        else:
            self.txt_output.insert("end", "Pre-check: PROBLEMI RILEVATI\n\n")
            for p in result["problemi"]:
                self.txt_output.insert("end", f"  PROBLEMA: {p}\n")
        if result["avvisi"]:
            self.txt_output.insert("end", "\nAvvisi:\n")
            for a in result["avvisi"]:
                self.txt_output.insert("end", f"  {a}\n")
        self.txt_output.configure(state="disabled")

    def optimize_and_export(self) -> None:
        mesi = self._parse_mesi()
        if not mesi:
            return
        try:
            cooldown = max(1, int(self.entry_cooldown.get() or 3))
            self.repo.set_setting("cooldown_mesi", cooldown)
            timeout = float(self.entry_timeout.get() or 20)
            if not (1 <= timeout <= 300):
                messagebox.showerror(t("errore"), "Timeout deve essere tra 1 e 300 secondi.")
                return
            workers = int(self.entry_workers.get() or 8)
            import os
            max_w = min(16, os.cpu_count() or 4)
            if not (1 <= workers <= max_w):
                messagebox.showerror(t("errore"), f"Thread deve essere tra 1 e {max_w}.")
                return
            self.repo.set_setting("solver_timeout", timeout)
            self.repo.set_setting("solver_workers", workers)
        except (ValueError, TurniVisiteError) as e:
            messagebox.showerror(t("errore"), str(e))
            return

        snap = self.repo.data_snapshot()
        week_windows = _ask_week_windows(mesi, snap["frequenze"], snap["famiglie"],
                                          self.repo.week_templates, parent=self)
        if week_windows is None:
            self._status("Operazione annullata.")
            return

        first_month = week_windows.get(mesi[0], {})
        for freq, intervalli in first_month.items():
            self.repo.set_week_template(freq, intervalli)

        self._status(t("pianificazione.in_corso"))
        if self._btn_ottimizza:
            self._btn_ottimizza.configure(state="disabled")
        # Show progress bar
        self._progress.pack(fill="x", padx=10, pady=(0, 2))
        self._progress.start()

        storico_snapshot = self.repo.get_storico_turni()

        def _run() -> None:
            try:
                result = esegui_ottimizzazione(
                    snap=snap, mesi=mesi,
                    storico_turni=storico_snapshot,
                    cooldown=cooldown, solver_timeout=timeout, solver_workers=workers,
                )
                self.after(0, lambda: self._alive.is_set() and self._on_solve_done(result, mesi, snap, cooldown, week_windows))
            except RuntimeError as e:
                err = str(e)
                self.after(0, lambda: self._alive.is_set() and self._on_solve_error(err))

        threading.Thread(target=_run, daemon=True).start()

    def _on_solve_error(self, err: str) -> None:
        self._progress.stop()
        self._progress.pack_forget()
        messagebox.showerror(t("errore"), err)
        if self._btn_ottimizza:
            self._btn_ottimizza.configure(state="normal")
        self._status("Errore durante l'ottimizzazione.")

    def _on_solve_done(self, result, mesi, snap, cooldown, week_windows) -> None:
        self._progress.stop()
        self._progress.pack_forget()
        if self._btn_ottimizza:
            self._btn_ottimizza.configure(state="normal")

        if not result.feasible:
            msg = diagnosi_infeasible(
                snap=snap, mesi=mesi,
                storico_turni=self.repo.get_storico_turni(), cooldown=cooldown,
            )
            self.txt_output.configure(state="normal")
            self.txt_output.delete("1.0", "end")
            self.txt_output.insert("end", t("pianificazione.nessuna_soluzione") + "\n\n" + msg + "\n")
            self.txt_output.configure(state="disabled")
            self._status(t("pianificazione.nessuna_soluzione"))
            return

        with self._lock:
            self._last_result = result
            self._last_mesi = mesi
            self._last_snap = snap
            self._last_week_windows = week_windows
        self._show_solution(result, mesi, snap, week_windows)
        self._populate_review_tab()
        # Enable export buttons (M4)
        self._btn_export_csv.configure(state="normal")
        self._btn_whatsapp.configure(state="normal")
        self._status(t("soluzione_trovata") + " Modifica o salva come bozza.")

    def _show_solution(self, result, mesi, snap, week_windows) -> None:
        self.txt_output.configure(state="normal")
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
        self.txt_output.configure(state="disabled")

    # ------------------------------------------------------------------
    # Tabella interattiva di revisione assegnazioni
    # ------------------------------------------------------------------

    def _build_review_tab(self, parent) -> None:
        filter_frame = ctk.CTkFrame(parent, fg_color="transparent")
        filter_frame.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(filter_frame, text=t("pianificazione.mese_edit")).pack(side="left", padx=(0, 4))
        self._review_mese = ctk.CTkComboBox(
            filter_frame, width=110, values=[],
            command=self._on_review_mese_change,
        )
        self._review_mese.pack(side="left", padx=4)

        self._review_mode_var = "famiglia"
        self._review_mode_btn = ctk.CTkSegmentedButton(
            filter_frame,
            values=[t("pianificazione.per_famiglia"), t("pianificazione.per_fratello")],
            command=self._on_review_mode_change,
        )
        self._review_mode_btn.pack(side="left", padx=12)
        self._review_mode_btn.set(t("pianificazione.per_famiglia"))

        self._filter_fr_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        ctk.CTkLabel(self._filter_fr_frame, text=t("pianificazione.nuovo_fratello")).pack(
            side="left", padx=(0, 4))
        self._filter_fr_combo = ctk.CTkComboBox(
            self._filter_fr_frame, width=180, values=[],
            command=self._on_filter_fratello_change,
        )
        self._filter_fr_combo.pack(side="left")

        self._review_count = ctk.CTkLabel(filter_frame, text="", text_color="gray")
        self._review_count.pack(side="right", padx=4)

        self._review_scroll = ctk.CTkScrollableFrame(parent)
        self._review_scroll.pack(fill="both", expand=True, padx=4, pady=4)
        self._row_widgets: list[dict] = []

    def _populate_review_tab(self) -> None:
        with self._lock:
            result = self._last_result
            mesi = list(self._last_mesi)
        if not result or not result.solution:
            return
        self._review_mese.configure(values=mesi)
        if mesi:
            self._review_mese.set(mesi[0])
        fratelli = sorted(self.repo.fratelli)
        self._filter_fr_combo.configure(
            values=[t("pianificazione.tutti_fratelli")] + fratelli)
        self._filter_fr_combo.set(t("pianificazione.tutti_fratelli"))
        self._refresh_review_table()
        self._tabview.set(self._tab_review_name)

    def _on_review_mese_change(self, _value: str = "") -> None:
        self._refresh_review_table()

    def _on_review_mode_change(self, value: str) -> None:
        if value == t("pianificazione.per_fratello"):
            self._review_mode_var = "fratello"
            self._filter_fr_frame.pack(side="left", padx=8)
        else:
            self._review_mode_var = "famiglia"
            self._filter_fr_frame.pack_forget()
        self._refresh_review_table()

    def _on_filter_fratello_change(self, _value: str = "") -> None:
        self._refresh_review_table()

    def _refresh_review_table(self) -> None:
        for w in self._review_scroll.winfo_children():
            w.destroy()
        self._row_widgets = []

        with self._lock:
            result = self._last_result
            snap = self._last_snap
            ww = self._last_week_windows
        if not result or not result.solution:
            return

        mese = self._review_mese.get()
        if not mese or mese not in result.solution.get("by_month", {}):
            return

        if self._review_mode_var == "fratello":
            self._build_fratello_rows(mese, result, snap, ww)
        else:
            self._build_family_rows(mese, result, snap, ww)

    def _build_family_rows(self, mese: str, result, snap: dict, ww: dict) -> None:
        blocco = result.solution["by_month"][mese]

        header = ctk.CTkFrame(self._review_scroll, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(header, text=t("pianificazione.famiglia_edit"),
                      width=200, anchor="w",
                      font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(header, text=t("pianificazione.slot_edit"),
                      width=100, anchor="w",
                      font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(header, text=t("pianificazione.nuovo_fratello"),
                      width=200, anchor="w",
                      font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)

        sep = ctk.CTkFrame(self._review_scroll, height=2, fg_color="gray60")
        sep.pack(fill="x", pady=2)

        count = 0
        for fam in sorted(blocco["by_family"].keys()):
            slots = blocco["by_family"][fam]
            freq = snap.get("frequenze", {}).get(fam, 2)
            valid_fratelli = sorted(self.repo.associazioni.get(fam, []))
            if NON_ASSEGNATO not in valid_fratelli:
                valid_fratelli.append(NON_ASSEGNATO)

            for k, current_fr in enumerate(slots):
                row = ctk.CTkFrame(self._review_scroll, fg_color="transparent")
                row.pack(fill="x", pady=1)

                fam_text = fam if k == 0 else ""
                ctk.CTkLabel(row, text=fam_text, width=200, anchor="w").pack(
                    side="left", padx=4)

                label = slot_label_with_month(mese, freq, k, ww)
                ctk.CTkLabel(row, text=label, width=100, anchor="w").pack(
                    side="left", padx=4)

                combo = ctk.CTkComboBox(row, width=200, values=valid_fratelli)
                combo.set(current_fr)
                combo.pack(side="left", padx=4)

                warn_label = ctk.CTkLabel(row, text="",
                                           text_color=("orange", "#ce9178"))
                warn_label.pack(side="left", padx=4, fill="x", expand=True)

                combo.configure(
                    command=lambda val, m=mese, f=fam, s=k, wl=warn_label:
                    self._on_table_edit(m, f, s, val, wl))

                self._row_widgets.append({
                    "mese": mese, "famiglia": fam, "slot": k,
                    "combo": combo, "warning": warn_label, "frame": row,
                })
                count += 1

            fam_sep = ctk.CTkFrame(self._review_scroll, height=1,
                                    fg_color="gray75")
            fam_sep.pack(fill="x", pady=1)

        self._review_count.configure(text=f"{count} assegnazioni")

    def _build_fratello_rows(self, mese: str, result, snap: dict, ww: dict) -> None:
        blocco = result.solution["by_month"][mese]

        reverse_assoc: dict[str, list[str]] = {}
        for fam, fr_list in self.repo.associazioni.items():
            for fr in fr_list:
                reverse_assoc.setdefault(fr, []).append(fam)
        for fr in reverse_assoc:
            reverse_assoc[fr] = sorted(set(reverse_assoc[fr]))

        selected_fr = self._filter_fr_combo.get()
        tutti_label = t("pianificazione.tutti_fratelli")
        if selected_fr and selected_fr != tutti_label:
            fratelli_to_show = [selected_fr]
        else:
            fratelli_to_show = sorted(
                f for f in blocco.get("by_brother", {}) if f != NON_ASSEGNATO
            )

        header = ctk.CTkFrame(self._review_scroll, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(header, text=t("pianificazione.nuovo_fratello"),
                      width=200, anchor="w",
                      font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(header, text=t("pianificazione.slot_edit"),
                      width=100, anchor="w",
                      font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(header, text=t("pianificazione.famiglia_edit"),
                      width=220, anchor="w",
                      font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)

        sep = ctk.CTkFrame(self._review_scroll, height=2, fg_color="gray60")
        sep.pack(fill="x", pady=2)

        count = 0
        for fr in fratelli_to_show:
            famiglie_visitate = blocco.get("by_brother", {}).get(fr, [])
            visitable = reverse_assoc.get(fr, [])
            family_options = visitable + [NON_ASSEGNATO]

            if not famiglie_visitate:
                row = ctk.CTkFrame(self._review_scroll, fg_color="transparent")
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(row, text=fr, width=200, anchor="w",
                              font=ctk.CTkFont(weight="bold")).pack(
                    side="left", padx=4)
                ctk.CTkLabel(row, text="—", width=100, anchor="w").pack(
                    side="left", padx=4)
                ctk.CTkLabel(row, text=t("pianificazione.nessuna_assegnazione"),
                              text_color="gray").pack(side="left", padx=4)
                count += 1

                fr_sep = ctk.CTkFrame(self._review_scroll, height=1,
                                       fg_color="gray75")
                fr_sep.pack(fill="x", pady=1)
                continue

            first_row = True
            for fam in famiglie_visitate:
                freq = snap.get("frequenze", {}).get(fam, 2)
                slots = blocco["by_family"].get(fam, [])
                k = next((i for i, name in enumerate(slots) if name == fr), 0)

                row = ctk.CTkFrame(self._review_scroll, fg_color="transparent")
                row.pack(fill="x", pady=1)

                fr_text = fr if first_row else ""
                ctk.CTkLabel(row, text=fr_text, width=200, anchor="w",
                              font=ctk.CTkFont(weight="bold")).pack(
                    side="left", padx=4)
                first_row = False

                label = slot_label_with_month(mese, freq, k, ww)
                ctk.CTkLabel(row, text=label, width=100, anchor="w").pack(
                    side="left", padx=4)

                combo = ctk.CTkComboBox(row, width=220, values=family_options)
                combo.set(fam)
                combo.pack(side="left", padx=4)

                warn_label = ctk.CTkLabel(row, text="",
                                           text_color=("orange", "#ce9178"))
                warn_label.pack(side="left", padx=4, fill="x", expand=True)

                combo.configure(
                    command=lambda val, m=mese, f=fr, old_fam=fam, s=k, wl=warn_label:
                    self._on_fratello_reassign(m, f, old_fam, s, val, wl))

                self._row_widgets.append({
                    "mese": mese, "fratello": fr, "famiglia": fam, "slot": k,
                    "combo": combo, "warning": warn_label, "frame": row,
                })
                count += 1

            fr_sep = ctk.CTkFrame(self._review_scroll, height=1,
                                   fg_color="gray75")
            fr_sep.pack(fill="x", pady=1)

        self._review_count.configure(text=f"{count} assegnazioni")

    def _on_table_edit(self, mese: str, famiglia: str, slot: int,
                       nuovo_fratello: str, warn_label) -> None:
        with self._lock:
            result = self._last_result
            mesi = self._last_mesi
            snap = self._last_snap
            ww = self._last_week_windows
        if not result or not result.solution:
            return
        try:
            new_solution = modifica_assegnazione(
                result.solution, mese, famiglia, slot, nuovo_fratello,
                repo=self.repo,
            )
            warnings = new_solution.pop("_warnings", [])
            with self._lock:
                result.solution = new_solution
                self._last_result = result
            if warnings:
                warn_label.configure(text="; ".join(warnings))
            else:
                warn_label.configure(text="")
            self._show_solution(result, mesi, snap, ww)
            self._status(f"Modificato: {famiglia} slot {slot} → {nuovo_fratello}")
        except (ValueError, KeyError, TurniVisiteError) as e:
            self._status(str(e))
            self._refresh_review_table()

    def _on_fratello_reassign(self, mese: str, fratello: str,
                              old_famiglia: str, old_slot: int,
                              new_famiglia: str, warn_label) -> None:
        if new_famiglia == old_famiglia:
            return
        with self._lock:
            result = self._last_result
            mesi = self._last_mesi
            snap = self._last_snap
            ww = self._last_week_windows
        if not result or not result.solution:
            return
        try:
            warnings: list[str] = []

            if new_famiglia == NON_ASSEGNATO:
                sol = modifica_assegnazione(
                    result.solution, mese, old_famiglia, old_slot,
                    NON_ASSEGNATO, repo=self.repo,
                )
                sol.pop("_warnings", None)
                with self._lock:
                    result.solution = sol
                    self._last_result = result
                self._show_solution(result, mesi, snap, ww)
                self._refresh_review_table()
                self._status(f"Rimosso: {fratello} da {old_famiglia}")
                return

            blocco = result.solution["by_month"][mese]
            new_slots = blocco["by_family"].get(new_famiglia, [])
            target_slot = next(
                (i for i, fr in enumerate(new_slots) if fr == NON_ASSEGNATO),
                None,
            )

            if target_slot is not None:
                sol = modifica_assegnazione(
                    result.solution, mese, old_famiglia, old_slot,
                    NON_ASSEGNATO, repo=self.repo,
                )
                sol.pop("_warnings", None)
                sol = modifica_assegnazione(
                    sol, mese, new_famiglia, target_slot, fratello,
                    repo=self.repo,
                )
                warnings = sol.pop("_warnings", [])
                msg = f"Spostato: {fratello} da {old_famiglia} a {new_famiglia}"
            else:
                if not new_slots:
                    raise TurniVisiteError(
                        f"Famiglia '{new_famiglia}' non ha slot nel mese {mese}."
                    )
                target_slot = 0
                displaced = new_slots[target_slot]

                sol = modifica_assegnazione(
                    result.solution, mese, new_famiglia, target_slot,
                    fratello, repo=self.repo,
                )
                sol.pop("_warnings", None)
                # Scambio: il fratello spostato va nella famiglia
                # liberata — skip validazione associazione (override manuale)
                sol = modifica_assegnazione(
                    sol, mese, old_famiglia, old_slot,
                    displaced, repo=None,
                )
                swap_w = sol.pop("_warnings", [])
                warnings.extend(swap_w)
                if displaced not in self.repo.associazioni.get(old_famiglia, []):
                    warnings.append(
                        f"{displaced} non era associato a {old_famiglia}"
                    )
                msg = (
                    f"Scambiato: {fratello} → {new_famiglia}, "
                    f"{displaced} → {old_famiglia}"
                )

            with self._lock:
                result.solution = sol
                self._last_result = result

            self._show_solution(result, mesi, snap, ww)
            self._refresh_review_table()
            if warnings:
                msg += f" ({'; '.join(warnings)})"
            self._status(msg)
        except (ValueError, KeyError, TurniVisiteError) as e:
            messagebox.showerror(t("errore"), str(e))
            self._refresh_review_table()

    # ------------------------------------------------------------------
    # Bozza / Conferma parziale
    # ------------------------------------------------------------------

    def _save_draft(self) -> None:
        with self._lock:
            result = self._last_result
            mesi = self._last_mesi
        if not result or not result.solution:
            messagebox.showinfo(t("info"), "Esegui prima l'ottimizzazione.")
            return

        self.repo.save_bozza(mesi, result.solution)
        self._status("Bozza salvata. Modifica, accetta e conferma quando pronto.")

        if messagebox.askyesno(t("conferma"), "Bozza salvata. Vuoi esportare anche il PDF?"):
            nome_file = "turni_" + "-".join(mesi) + ".pdf"
            pdf_path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf"), ("Tutti", "*.*")],
                initialfile=nome_file, title="Salva PDF turni",
            )
            if pdf_path:
                try:
                    with self._lock:
                        snap = self._last_snap
                        ww = self._last_week_windows
                    export_pdf_mesi(mesi, result.solution, snap["frequenze"], ww, output_path=pdf_path)
                    open_file(pdf_path)
                    self._status("Bozza salvata. Export PDF completato.")
                except OSError as e:
                    messagebox.showerror(t("errore"), str(e))

    def _accept_all(self) -> None:
        bozza = self.repo.get_bozza()
        if not bozza:
            messagebox.showinfo(t("info"), "Nessuna bozza attiva. Salva prima una bozza.")
            return
        for a in bozza["assegnazioni"]:
            a["stato"] = STATO_BOZZA_ACCETTATO
        self.repo.bozza_turni = bozza
        self.repo.save()
        self._status(f"Tutte le {len(bozza['assegnazioni'])} assegnazioni accettate.")

    def _confirm_draft(self) -> None:
        bozza = self.repo.get_bozza()
        if not bozza:
            messagebox.showinfo(t("info"), "Nessuna bozza attiva.")
            return
        n_acc = sum(1 for a in bozza["assegnazioni"] if a["stato"] == STATO_BOZZA_ACCETTATO)
        n_rif = sum(1 for a in bozza["assegnazioni"] if a["stato"] == STATO_BOZZA_RIFIUTATO)
        n_prop = sum(1 for a in bozza["assegnazioni"] if a["stato"] == STATO_BOZZA_PROPOSTO)

        if n_acc == 0:
            messagebox.showwarning("Attenzione", "Nessuna assegnazione accettata. Usa 'Accetta tutti' prima.")
            return

        msg = (f"Accettate: {n_acc}\nRifiutate: {n_rif}\nIn attesa: {n_prop}\n\n"
               f"Le assegnazioni in attesa verranno scartate.\nConfermare?")
        if not messagebox.askyesno(t("pianificazione.conferma"), msg):
            return

        try:
            from ..backup import create_backup
            create_backup(self.repo.filename)
            result_bozza = self.repo.conferma_bozza()
            salvati = result_bozza["salvati"]
            self._status(f"Turni confermati: {', '.join(salvati) or 'nessuno'}.")
            if self._on_storico_change and salvati:
                self._on_storico_change()
            # Offri invio email
            smtp_host = self.repo.get_setting("smtp_host", "")
            with self._lock:
                last_result = self._last_result
            if smtp_host and salvati and last_result and messagebox.askyesno(
                t("notifiche.titolo"), t("notifiche.invia_email") + "?",
            ):
                self._status("Invio notifiche in corso...")
                _repo = self.repo
                _salvati = list(salvati)
                _solution = last_result.solution

                def _invia_notifiche() -> None:
                    try:
                        notif = send_notifications(_repo, _salvati, _solution, None)
                        parts = []
                        if notif["inviati"]:
                            parts.append(f"Inviati: {len(notif['inviati'])}")
                        if notif["non_configurati"]:
                            parts.append(f"Senza email: {len(notif['non_configurati'])}")
                        if notif["errori"]:
                            parts.append(f"Errori: {len(notif['errori'])}")
                        msg = "\n".join(parts) if parts else "Nessun invio."
                        self.after(0, lambda: self._alive.is_set() and messagebox.showinfo(t("notifiche.titolo"), msg))
                        self.after(0, lambda: self._alive.is_set() and self._status(f"Notifiche: {msg.replace(chr(10), ', ')}"))
                    except Exception as e:
                        self.after(0, lambda: self._alive.is_set() and self._status(f"Errore notifiche: {e}"))

                threading.Thread(target=_invia_notifiche, daemon=True).start()
        except StoricoConflittoError as e:
            messagebox.showwarning(t("storico.titolo"), str(e))

    def _discard_draft(self) -> None:
        if not self.repo.get_bozza():
            return
        if messagebox.askyesno(t("conferma"), "Scartare la bozza corrente?"):
            self.repo.discard_bozza()
            self._status("Bozza scartata.")

    # ------------------------------------------------------------------
    # WhatsApp export
    # ------------------------------------------------------------------

    def _copy_whatsapp(self) -> None:
        with self._lock:
            result = self._last_result
            mesi = list(self._last_mesi)
            snap = dict(self._last_snap)
            ww = dict(self._last_week_windows)
        if not result or not result.solution:
            messagebox.showinfo(t("info"), "Esegui prima l'ottimizzazione.")
            return
        text = format_whatsapp_mesi(mesi, result.solution, snap.get("frequenze", {}), ww)
        self.clipboard_clear()
        self.clipboard_append(text)
        self._status(t("pianificazione.whatsapp_copiato"))
        messagebox.showinfo(t("info"), t("pianificazione.whatsapp_copiato"))

    # ------------------------------------------------------------------
    # CSV / Templates
    # ------------------------------------------------------------------

    def _export_csv(self) -> None:
        with self._lock:
            result = self._last_result
            mesi = list(self._last_mesi)
            snap = dict(self._last_snap)
            ww = dict(self._last_week_windows)
        if not result or not result.solution:
            messagebox.showinfo(t("info"), "Esegui prima l'ottimizzazione.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tutti", "*.*")],
            initialfile="turni_" + "-".join(mesi) + ".csv",
        )
        if not path:
            return
        try:
            export_csv_mesi(mesi, result.solution, snap["frequenze"], ww, path)
            open_file(path)
            self._status(f"CSV esportato: {path}")
        except Exception as e:
            messagebox.showerror(t("errore"), str(e))

    def _save_week_templates(self) -> None:
        results = {}
        for freq in (1, 2, 4):
            current = self.repo.get_week_template(freq)
            default = ", ".join(current) if current else ", ".join(DEFAULT_WEEK_TEMPLATES.get(freq, []))
            dialog = ctk.CTkInputDialog(
                title=f"Template freq {freq}",
                text=f"Intervalli per frequenza {freq} (gg-gg, virgola):",
            )
            val = dialog.get_input()
            if val is None:
                return  # annullato, non salvare nulla
            if not val.strip():
                val = default
            ok, res = _validate_week_ranges(val, freq)
            if not ok:
                messagebox.showerror(t("errore"), f"Frequenza {freq}: {res}")
                return
            results[freq] = res

        # salva tutto atomicamente
        for freq, res in results.items():
            self.repo.set_week_template(freq, res)
        self._status("Template settimane salvati.")
