"""Tab Storico: visualizzazione, gestione turni confermati, sostituzione, esecuzione."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from typing import TYPE_CHECKING

from .widgets import CTkListbox, FilterableComboBox
from .themes import BUTTON_COLORS
from ..domain import EntitaNonTrovata, TurniVisiteError
from ..csv_export import export_storico_csv
from ..i18n import t
from ..service import open_file, trova_sostituto

if TYPE_CHECKING:
    from ..repository import JsonRepository


class TabStorico(ctk.CTkFrame):
    def __init__(self, parent, repo: "JsonRepository",
                 set_status=None, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self._set_status = set_status
        self._build()

    def _build(self) -> None:
        # Top bar
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(top, text=t("storico.mesi_confermati"),
                      font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(top, text=t("storico.aggiorna"), width=100, command=self.refresh).pack(side="left", padx=8)
        ctk.CTkButton(top, text=t("storico.elimina"), width=160,
                       fg_color=BUTTON_COLORS["danger"],
                       hover_color=BUTTON_COLORS["danger_hover"],
                       command=self.delete_selected).pack(side="left")
        ctk.CTkButton(top, text=t("storico.esporta"), width=160,
                       command=self._export_csv).pack(side="right")

        # Lista storico
        self.list_storico = CTkListbox(self, height=140, command=self._on_select)
        self.list_storico.pack(fill="x", padx=10, pady=4)

        # Dettaglio con stato esecuzione
        ctk.CTkLabel(self, text=t("storico.dettaglio"),
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.txt_dettaglio = ctk.CTkTextbox(self, height=160, corner_radius=8)
        self.txt_dettaglio.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        self.txt_dettaglio.configure(state="disabled")

        # Pannello esecuzione
        exec_frame = ctk.CTkFrame(self, corner_radius=8)
        exec_frame.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(exec_frame, text=t("stato_esecuzione"),
                      font=ctk.CTkFont(weight="bold", size=12)).pack(side="left", padx=8)
        ctk.CTkLabel(exec_frame, text=t("famiglia_label")).pack(side="left", padx=(8, 2))
        self.combo_exec_fam = ctk.CTkComboBox(exec_frame, width=150, values=[],
                                               command=self._update_slots_for_family)
        self.combo_exec_fam.pack(side="left", padx=2)
        ctk.CTkLabel(exec_frame, text=t("slot_label")).pack(side="left", padx=(8, 2))
        self.combo_exec_slot = ctk.CTkComboBox(exec_frame, width=60, values=[])
        self.combo_exec_slot.pack(side="left", padx=2)
        ctk.CTkButton(exec_frame, text=t("esecuzione.segna_completata"), width=140,
                       fg_color="#107c10", hover_color="#0b5e0b",
                       command=lambda: self._set_esecuzione("completato")).pack(side="left", padx=4)
        ctk.CTkButton(exec_frame, text=t("esecuzione.segna_annullata"), width=140,
                       fg_color=BUTTON_COLORS["danger"],
                       hover_color=BUTTON_COLORS["danger_hover"],
                       command=lambda: self._set_esecuzione("annullato")).pack(side="left", padx=4)

        # Pannello sostituzione
        sub_frame = ctk.CTkFrame(self, corner_radius=8)
        sub_frame.pack(fill="x", padx=10, pady=(4, 8))
        ctk.CTkLabel(sub_frame, text=t("sostituzione.titolo"),
                      font=ctk.CTkFont(weight="bold", size=12)).pack(side="left", padx=8)
        ctk.CTkLabel(sub_frame, text=t("sostituzione.fratello_malato")).pack(side="left", padx=(8, 2))
        self.combo_sub_bro = FilterableComboBox(sub_frame, width=160, values=[])
        self.combo_sub_bro.pack(side="left", padx=2)
        ctk.CTkButton(sub_frame, text=t("sostituzione.cerca"), width=140,
                       command=self._find_substitute).pack(side="left", padx=4)
        self.combo_sub_cand = ctk.CTkComboBox(sub_frame, width=200, values=[])
        self.combo_sub_cand.pack(side="left", padx=4)
        ctk.CTkButton(sub_frame, text=t("sostituzione.applica"), width=120,
                       fg_color="#107c10", hover_color="#0b5e0b",
                       command=self._apply_substitute).pack(side="left", padx=4)

        self._candidates: list[dict] = []
        self._current_per_fam: dict[str, list[tuple[str, int, str]]] = {}
        self._mesi_list: list[str] = []

    def refresh(self) -> None:
        self.list_storico.delete(0, "end")
        self._mesi_list = []
        for rec in self.repo.get_storico_turni():
            mese = rec.get("mese", "?")
            ass = rec.get("assegnazioni", [])
            n = len(ass)
            n_done = sum(1 for a in ass if a.get("stato_esecuzione") == "completato")
            confirmed = rec.get("confirmed_at", "")[:10]
            label = f"{mese}  ({n} assegnazioni, {n_done} completate, {confirmed})"
            self._mesi_list.append(mese)
            self.list_storico.insert("end", label)

    def _get_selected_mese(self) -> str | None:
        sel = self.list_storico.curselection()
        if not sel:
            return None
        idx = sel[0]
        if idx < len(self._mesi_list):
            return self._mesi_list[idx]
        return None

    def _on_select(self) -> None:
        mese = self._get_selected_mese()
        if not mese:
            return

        storico = self.repo.get_storico_turni()
        rec = next((r for r in storico if r.get("mese") == mese), None)
        if not rec:
            return

        self.txt_dettaglio.configure(state="normal")
        self.txt_dettaglio.delete("1.0", "end")
        self.txt_dettaglio.insert("end", f"{t('mese_label')} {mese}\n")
        self.txt_dettaglio.insert("end", f"{t('confermato')}: {rec.get('confirmed_at', '')}\n\n")

        per_fam: dict[str, list[tuple[str, int, str]]] = {}
        for a in rec.get("assegnazioni", []):
            fam = a.get("famiglia", "?")
            fr = a.get("fratello", "?")
            slot = a.get("slot", 0)
            stato = a.get("stato_esecuzione", "pianificato")
            per_fam.setdefault(fam, []).append((fr, slot, stato))

        self._current_per_fam = per_fam
        famiglie_list = []
        for fam in sorted(per_fam.keys()):
            entries = per_fam[fam]
            parts = []
            for fr, slot, stato in entries:
                stato_icon = {"completato": "V", "annullato": "X"}.get(stato, "-")
                parts.append(f"{fr} [slot {slot}] ({stato_icon})")
            self.txt_dettaglio.insert("end", f"  {fam}: {', '.join(parts)}\n")
            famiglie_list.append(fam)

        self.txt_dettaglio.configure(state="disabled")

        self.combo_exec_fam.configure(values=famiglie_list)
        if famiglie_list:
            self.combo_exec_fam.set(famiglie_list[0])
        self._update_slots_for_family()

        fratelli_mese = sorted({a.get("fratello", "") for a in rec.get("assegnazioni", [])})
        self.combo_sub_bro.configure(values=fratelli_mese)

    def _update_slots_for_family(self, _=None) -> None:
        fam = self.combo_exec_fam.get().strip()
        entries = self._current_per_fam.get(fam, [])
        slots = sorted({str(slot) for _, slot, _ in entries})
        self.combo_exec_slot.configure(values=slots)
        if slots:
            self.combo_exec_slot.set(slots[0])

    def delete_selected(self) -> None:
        mese = self._get_selected_mese()
        if not mese:
            messagebox.showerror(t("errore"), "Seleziona un mese.")
            return
        if not messagebox.askyesno(t("conferma"), f"Eliminare '{mese}' dallo storico?"):
            return
        try:
            self.repo.delete_storico_mese(mese)
            self.refresh()
            if self._set_status:
                self._set_status(f"Mese '{mese}' rimosso.")
        except EntitaNonTrovata as e:
            messagebox.showerror(t("errore"), str(e))

    def _set_esecuzione(self, stato: str) -> None:
        mese = self._get_selected_mese()
        if not mese:
            messagebox.showerror(t("errore"), "Seleziona un mese.")
            return
        fam = self.combo_exec_fam.get().strip()
        try:
            slot = int(self.combo_exec_slot.get())
        except ValueError:
            messagebox.showerror(t("errore"), "Seleziona famiglia e slot.")
            return
        try:
            self.repo.set_stato_esecuzione(mese, fam, slot, stato)
            self._on_select()
            if self._set_status:
                self._set_status(f"{fam} slot {slot}: {stato}")
        except TurniVisiteError as e:
            messagebox.showerror(t("errore"), str(e))

    def _find_substitute(self) -> None:
        mese = self._get_selected_mese()
        if not mese:
            messagebox.showerror(t("errore"), "Seleziona un mese.")
            return
        bro = self.combo_sub_bro.get().strip()
        if not bro:
            messagebox.showerror(t("errore"), t("sostituzione.fratello_malato"))
            return

        self._candidates = trova_sostituto(self.repo, mese, bro)
        if not self._candidates:
            messagebox.showinfo(t("info"), t("sostituzione.nessun_candidato"))
            self.combo_sub_cand.configure(values=[])
            return

        labels = [
            f"{c['fratello']} → {c['famiglia']} slot {c['slot']} (carico: {c['carico_attuale']})"
            for c in self._candidates
        ]
        self.combo_sub_cand.configure(values=labels)
        if labels:
            self.combo_sub_cand.set(labels[0])

    def _apply_substitute(self) -> None:
        mese = self._get_selected_mese()
        if not mese or not self._candidates:
            return
        sel_text = self.combo_sub_cand.get()
        idx = next((i for i, c in enumerate(self._candidates)
                     if f"{c['fratello']} → {c['famiglia']} slot {c['slot']}" in sel_text), None)
        if idx is None:
            return
        cand = self._candidates[idx]
        bro_malato = self.combo_sub_bro.get().strip()

        if not messagebox.askyesno(t("conferma"),
                                    f"Sostituire {bro_malato} con {cand['fratello']} "
                                    f"per {cand['famiglia']} slot {cand['slot']}?"):
            return
        try:
            self.repo.update_storico_assegnazione(
                mese, cand["famiglia"], cand["slot"], bro_malato, cand["fratello"])
            self.refresh()
            self._on_select()
            if self._set_status:
                self._set_status(f"Sostituzione: {bro_malato} → {cand['fratello']}")
        except TurniVisiteError as e:
            messagebox.showerror(t("errore"), str(e))

    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tutti", "*.*")],
            initialfile="storico_turni.csv",
        )
        if not path:
            return
        try:
            export_storico_csv(self.repo.get_storico_turni(), path)
            open_file(path)
            if self._set_status:
                self._set_status(f"Storico esportato: {path}")
        except Exception as e:
            messagebox.showerror(t("errore"), str(e))
