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
from ..scheduling import validate_month_yyyy_mm
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


def _ask_week_windows(
    mesi: list[str], frequenze: dict, famiglie: set,
    saved_templates: dict[str, list[str]],
    parent=None,
) -> dict | None:
    """Show a single CTkToplevel form for all month/frequency week windows."""
    freqs_presenti = sorted(
        {freq for f in famiglie if (freq := frequenze.get(f, 2)) in (1, 2, 4)}
    )
    # Pre-filter: only frequencies that actually have families
    freqs_presenti = [
        freq for freq in freqs_presenti
        if any(frequenze.get(f, 2) == freq for f in famiglie)
    ]
    if not freqs_presenti:
        return {m: {} for m in mesi}

    defaults_map = {}
    for freq in freqs_presenti:
        template = saved_templates.get(str(freq))
        if template:
            defaults_map[freq] = ", ".join(template)
        else:
            defaults_map[freq] = ", ".join(DEFAULT_WEEK_TEMPLATES.get(freq, []))

    # Build single dialog
    result_container: list[dict | None] = [None]
    dialog = ctk.CTkToplevel()
    dialog.title(t("configura_settimane"))
    dialog.geometry("600x500")
    dialog.resizable(True, True)
    dialog.grab_set()
    dialog.transient(parent.winfo_toplevel() if parent is not None else "")

    scroll = ctk.CTkScrollableFrame(dialog)
    scroll.pack(fill="both", expand=True, padx=10, pady=10)

    entries: dict[tuple[str, int], ctk.CTkEntry] = {}

    for mese in mesi:
        ctk.CTkLabel(scroll, text=f"--- {mese} ---",
                      font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=4, pady=(10, 4))
        for freq in freqs_presenti:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row,
                          text=f"Freq {freq} ({freq} intervalli):").pack(
                side="left", padx=(0, 8))
            entry = ctk.CTkEntry(row, width=300,
                                  placeholder_text=defaults_map[freq])
            entry.insert(0, defaults_map[freq])
            entry.pack(side="left", fill="x", expand=True)
            entries[(mese, freq)] = entry

    def _on_confirm():
        week_windows: dict = {}
        for mese in mesi:
            week_windows[mese] = {}
            for freq in freqs_presenti:
                entry = entries[(mese, freq)]
                s = entry.get().strip()
                if not s:
                    s = defaults_map[freq]
                ok, res = _validate_week_ranges(s, freq)
                if not ok:
                    messagebox.showerror(t("errore"),
                                          f"{mese} freq {freq}: {res}")
                    return
                week_windows[mese][freq] = res
        result_container[0] = week_windows
        dialog.destroy()

    def _on_cancel():
        result_container[0] = None
        dialog.destroy()

    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(fill="x", padx=10, pady=(0, 10))
    ctk.CTkButton(btn_frame, text=t("conferma"), width=120,
                   command=_on_confirm).pack(side="right", padx=4)
    ctk.CTkButton(btn_frame, text=t("annulla"), width=120,
                   fg_color=BUTTON_COLORS["danger"],
                   hover_color=BUTTON_COLORS["danger_hover"],
                   command=_on_cancel).pack(side="right", padx=4)

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
        # Disable export buttons (M4)
        if hasattr(self, "_btn_export_csv"):
            self._btn_export_csv.configure(state="disabled")
        if hasattr(self, "_btn_whatsapp"):
            self._btn_whatsapp.configure(state="disabled")

    def _build(self) -> None:
        # Mesi + cooldown
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(top, text=t("pianificazione.mesi")).pack(side="left")
        self.entry_mesi = ctk.CTkEntry(top, width=350, placeholder_text="2026-05, 2026-06")
        self.entry_mesi.pack(side="left", padx=8)
        ctk.CTkLabel(top, text=t("pianificazione.cooldown")).pack(side="left", padx=(12, 4))
        self.entry_cooldown = ctk.CTkEntry(top, width=50)
        self.entry_cooldown.pack(side="left")
        self.entry_cooldown.insert(0, str(self.repo.get_setting("cooldown_mesi", 3)))

        # Solver settings
        settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        settings_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(settings_frame, text=t("pianificazione.timeout")).pack(side="left")
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

        # Pannello modifica manuale
        edit_frame = ctk.CTkFrame(self, corner_radius=8)
        edit_frame.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(edit_frame, text=t("pianificazione.modifica"),
                      font=ctk.CTkFont(weight="bold", size=12)).pack(side="left", padx=8)
        ctk.CTkLabel(edit_frame, text=t("pianificazione.mese_edit")).pack(side="left", padx=(8, 2))
        self.combo_edit_mese = ctk.CTkComboBox(edit_frame, width=100, values=[])
        self.combo_edit_mese.pack(side="left", padx=2)
        self.combo_edit_mese.configure(command=self._on_edit_mese_change)
        ctk.CTkLabel(edit_frame, text=t("pianificazione.famiglia_edit")).pack(side="left", padx=(8, 2))
        self.combo_edit_fam = ctk.CTkComboBox(edit_frame, width=150, values=[])
        self.combo_edit_fam.pack(side="left", padx=2)
        self.combo_edit_fam.configure(command=self._on_edit_fam_change)
        ctk.CTkLabel(edit_frame, text=t("pianificazione.slot_edit")).pack(side="left", padx=(8, 2))
        self.combo_edit_slot = ctk.CTkComboBox(edit_frame, width=60, values=[])
        self.combo_edit_slot.pack(side="left", padx=2)
        ctk.CTkLabel(edit_frame, text=t("pianificazione.nuovo_fratello")).pack(side="left", padx=(8, 2))
        self.combo_edit_fr = ctk.CTkComboBox(edit_frame, width=160, values=[])
        self.combo_edit_fr.pack(side="left", padx=2)
        ctk.CTkButton(edit_frame, text=t("pianificazione.applica_modifica"), width=80,
                       command=self._apply_edit).pack(side="left", padx=6)

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

        # Output (readonly)
        self.txt_output = ctk.CTkTextbox(self, corner_radius=8)
        self.txt_output.pack(fill="both", expand=True, padx=10, pady=6)
        self.txt_output.configure(state="disabled")

    def _status(self, msg: str) -> None:
        if self._set_status:
            self._set_status(msg)

    def _parse_mesi(self) -> list[str] | None:
        raw = self.entry_mesi.get().strip()
        if not raw:
            messagebox.showerror(t("errore"), "Inserisci almeno un mese.")
            return None
        mesi = [m.strip() for m in raw.split(",") if m.strip()]
        try:
            return [validate_month_yyyy_mm(m) for m in mesi]
        except ValueError as e:
            messagebox.showerror(t("errore"), str(e))
            return None

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
        self._populate_edit_combos()
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

    def _populate_edit_combos(self) -> None:
        with self._lock:
            result = self._last_result
            mesi = list(self._last_mesi)
        if not result or not result.solution:
            return
        self.combo_edit_mese.configure(values=mesi)
        if mesi:
            self.combo_edit_mese.set(mesi[0])
            self._on_edit_mese_change(mesi[0])
        fratelli = sorted(self.repo.fratelli | {NON_ASSEGNATO})
        self.combo_edit_fr.configure(values=fratelli)

    def _on_edit_mese_change(self, mese: str) -> None:
        with self._lock:
            result = self._last_result
        if not result or not result.solution:
            return
        blocco = result.solution.get("by_month", {}).get(mese, {})
        famiglie = sorted(blocco.get("by_family", {}).keys())
        self.combo_edit_fam.configure(values=famiglie)
        if famiglie:
            self.combo_edit_fam.set(famiglie[0])
            self._on_edit_fam_change(famiglie[0])

    def _on_edit_fam_change(self, fam: str) -> None:
        with self._lock:
            result = self._last_result
            snap = self._last_snap
        if not result or not result.solution:
            return
        mese = self.combo_edit_mese.get()
        blocco = result.solution.get("by_month", {}).get(mese, {})
        slots = blocco.get("by_family", {}).get(fam, [])
        freq = snap.get("frequenze", {}).get(fam, 2)
        slot_values = [str(i) for i in range(len(slots))]
        self.combo_edit_slot.configure(values=slot_values)
        if slot_values:
            self.combo_edit_slot.set(slot_values[0])

    def _apply_edit(self) -> None:
        with self._lock:
            result = self._last_result
            mesi = self._last_mesi
            snap = self._last_snap
            ww = self._last_week_windows
        if not result or not result.solution:
            messagebox.showinfo(t("info"), "Esegui prima l'ottimizzazione.")
            return
        mese = self.combo_edit_mese.get()
        fam = self.combo_edit_fam.get()
        try:
            slot = int(self.combo_edit_slot.get())
        except ValueError:
            messagebox.showerror(t("errore"), "Slot non valido.")
            return
        nuovo = self.combo_edit_fr.get().strip()
        if not nuovo:
            return
        try:
            new_solution = modifica_assegnazione(result.solution, mese, fam, slot, nuovo, repo=self.repo)
            with self._lock:
                result.solution = new_solution
                self._last_result = result
            self._show_solution(result, mesi, snap, ww)
            self._status(f"Modificato: {fam} slot {slot} → {nuovo}")
        except (ValueError, KeyError, TurniVisiteError) as e:
            messagebox.showerror(t("errore"), str(e))

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
