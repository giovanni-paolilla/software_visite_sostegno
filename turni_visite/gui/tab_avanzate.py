"""Tab Avanzate: indisponibilita', vincoli, backup, statistiche, audit."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import TYPE_CHECKING

from .widgets import FilterableComboBox, CTkListbox
from ..domain import TurniVisiteError
from ..backup import create_backup, list_backups, restore_backup
from ..config import DATA_FILE
from ..scheduling import validate_month_yyyy_mm
from ..stats import (
    report_carico_fratelli, report_copertura_famiglie,
    calcola_indice_equita, trend_mensile,
)

if TYPE_CHECKING:
    from ..repository import JsonRepository


class TabAvanzate(ctk.CTkFrame):
    def __init__(self, parent, repo: "JsonRepository",
                 set_status=None, on_change=None, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self._set_status = set_status
        self._on_change = on_change
        self._build()

    def _build(self) -> None:
        # Sub-tabview
        self.sub_tabs = ctk.CTkTabview(self, corner_radius=8)
        self.sub_tabs.pack(fill="both", expand=True, padx=6, pady=6)

        self._build_indisponibilita()
        self._build_vincoli()
        self._build_backup()
        self._build_statistiche()
        self._build_audit()

    # ------------------------------------------------------------------
    # INDISPONIBILITA'
    # ------------------------------------------------------------------

    def _build_indisponibilita(self) -> None:
        tab = self.sub_tabs.add("Indisponibilita'")

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(top, text="Fratello:").pack(side="left")
        self.combo_ind_bro = FilterableComboBox(top, width=200, values=[])
        self.combo_ind_bro.pack(side="left", padx=6)
        ctk.CTkLabel(top, text="Mese (YYYY-MM):").pack(side="left", padx=(8, 4))
        self.entry_ind_mese = ctk.CTkEntry(top, width=120, placeholder_text="2026-05")
        self.entry_ind_mese.pack(side="left", padx=4)
        ctk.CTkButton(top, text="Aggiungi", width=100,
                       command=self._add_indisponibilita).pack(side="left", padx=4)
        ctk.CTkButton(top, text="Rimuovi", width=100, fg_color="#d13438",
                       hover_color="#a4262c",
                       command=self._remove_indisponibilita).pack(side="left", padx=4)

        self.list_ind = CTkListbox(tab, height=200)
        self.list_ind.pack(fill="both", expand=True, padx=8, pady=4)

    def _refresh_indisponibilita(self) -> None:
        self.combo_ind_bro.configure(values=sorted(self.repo.fratelli))
        self.list_ind.delete(0, "end")
        for fr in sorted(self.repo.fratelli):
            mesi = self.repo.indisponibilita.get(fr, [])
            if mesi:
                self.list_ind.insert("end", f"{fr}: {', '.join(mesi)}")

    def _add_indisponibilita(self) -> None:
        bro = self.combo_ind_bro.get().strip()
        mese = self.entry_ind_mese.get().strip()
        if not bro or not mese:
            messagebox.showerror("Errore", "Seleziona fratello e mese.")
            return
        try:
            mese = validate_month_yyyy_mm(mese)
            self.repo.add_indisponibilita(bro, mese)
            self._refresh_indisponibilita()
            if self._set_status:
                self._set_status(f"Indisponibilita' aggiunta: {bro} per {mese}")
        except (ValueError, TurniVisiteError) as e:
            messagebox.showerror("Errore", str(e))

    def _remove_indisponibilita(self) -> None:
        bro = self.combo_ind_bro.get().strip()
        mese = self.entry_ind_mese.get().strip()
        if not bro or not mese:
            messagebox.showerror("Errore", "Seleziona fratello e mese.")
            return
        try:
            self.repo.remove_indisponibilita(bro, mese)
            self._refresh_indisponibilita()
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e))

    # ------------------------------------------------------------------
    # VINCOLI
    # ------------------------------------------------------------------

    def _build_vincoli(self) -> None:
        tab = self.sub_tabs.add("Vincoli")

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(top, text="Fratello A:").pack(side="left")
        self.combo_vinc_a = FilterableComboBox(top, width=160, values=[])
        self.combo_vinc_a.pack(side="left", padx=4)
        ctk.CTkLabel(top, text="Fratello B:").pack(side="left")
        self.combo_vinc_b = FilterableComboBox(top, width=160, values=[])
        self.combo_vinc_b.pack(side="left", padx=4)
        ctk.CTkLabel(top, text="Tipo:").pack(side="left")
        self.combo_vinc_tipo = ctk.CTkComboBox(
            top, values=["incompatibile", "preferenza_coppia"], width=160)
        self.combo_vinc_tipo.pack(side="left", padx=4)
        ctk.CTkButton(top, text="Aggiungi", width=100,
                       command=self._add_vincolo).pack(side="left", padx=4)

        bottom = ctk.CTkFrame(tab, fg_color="transparent")
        bottom.pack(fill="x", padx=8, pady=2)
        ctk.CTkButton(bottom, text="Rimuovi selezionato", width=160,
                       fg_color="#d13438", hover_color="#a4262c",
                       command=self._remove_vincolo).pack(side="left")

        self.list_vincoli = CTkListbox(tab, height=200)
        self.list_vincoli.pack(fill="both", expand=True, padx=8, pady=4)

    def _refresh_vincoli(self) -> None:
        bros = sorted(self.repo.fratelli)
        self.combo_vinc_a.configure(values=bros)
        self.combo_vinc_b.configure(values=bros)
        self.list_vincoli.delete(0, "end")
        for v in self.repo.vincoli_personalizzati:
            self.list_vincoli.insert(
                "end",
                f"{v.get('fratello_a', '?')} <-> {v.get('fratello_b', '?')} "
                f"[{v.get('tipo', '?')}] {v.get('descrizione', '')}"
            )

    def _add_vincolo(self) -> None:
        fa = self.combo_vinc_a.get().strip()
        fb = self.combo_vinc_b.get().strip()
        tipo = self.combo_vinc_tipo.get().strip()
        if not fa or not fb or not tipo:
            messagebox.showerror("Errore", "Compila tutti i campi.")
            return
        try:
            self.repo.add_vincolo(fa, fb, tipo)
            self._refresh_vincoli()
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e))

    def _remove_vincolo(self) -> None:
        sel = self.list_vincoli.curselection()
        if not sel:
            messagebox.showerror("Errore", "Seleziona un vincolo.")
            return
        idx = sel[0]
        if idx >= len(self.repo.vincoli_personalizzati):
            return
        v = self.repo.vincoli_personalizzati[idx]
        try:
            self.repo.remove_vincolo(v["fratello_a"], v["fratello_b"], v["tipo"])
            self._refresh_vincoli()
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e))

    # ------------------------------------------------------------------
    # BACKUP
    # ------------------------------------------------------------------

    def _build_backup(self) -> None:
        tab = self.sub_tabs.add("Backup")

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=6)
        ctk.CTkButton(top, text="Crea backup ora", width=160,
                       command=self._create_backup).pack(side="left", padx=4)
        ctk.CTkButton(top, text="Ripristina selezionato", width=180,
                       command=self._restore_backup).pack(side="left", padx=4)
        ctk.CTkButton(top, text="Aggiorna lista", width=140,
                       command=self._refresh_backups).pack(side="right", padx=4)

        self.list_backups = CTkListbox(tab, height=250)
        self.list_backups.pack(fill="both", expand=True, padx=8, pady=4)

    def _refresh_backups(self) -> None:
        self.list_backups.delete(0, "end")
        for b in list_backups():
            self.list_backups.insert("end",
                                      f"{b['filename']}  ({b['size_kb']} KB, {b['modified']})")

    def _create_backup(self) -> None:
        path = create_backup(DATA_FILE)
        if path:
            self._refresh_backups()
            if self._set_status:
                self._set_status(f"Backup creato.")
        else:
            messagebox.showinfo("Info", "Nessun file dati da backuppare.")

    def _restore_backup(self) -> None:
        sel = self.list_backups.curselection()
        if not sel:
            messagebox.showerror("Errore", "Seleziona un backup.")
            return
        backups = list_backups()
        if sel[0] >= len(backups):
            return
        b = backups[sel[0]]
        if not messagebox.askyesno("Conferma", f"Ripristinare '{b['filename']}'?"):
            return
        try:
            restore_backup(b["path"], DATA_FILE)
            self.repo.load()
            if self._on_change:
                self._on_change()
            self._refresh_backups()
            messagebox.showinfo("Ripristino", "Backup ripristinato.")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    # ------------------------------------------------------------------
    # STATISTICHE
    # ------------------------------------------------------------------

    def _build_statistiche(self) -> None:
        tab = self.sub_tabs.add("Statistiche")

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=6)
        ctk.CTkButton(top, text="Carico fratelli", width=140,
                       command=self._report_carico).pack(side="left", padx=3)
        ctk.CTkButton(top, text="Copertura famiglie", width=150,
                       command=self._report_copertura).pack(side="left", padx=3)
        ctk.CTkButton(top, text="Indice equita'", width=130,
                       command=self._report_equita).pack(side="left", padx=3)
        ctk.CTkButton(top, text="Trend mensile", width=130,
                       command=self._report_trend).pack(side="left", padx=3)

        self.txt_stats = ctk.CTkTextbox(tab, corner_radius=8)
        self.txt_stats.pack(fill="both", expand=True, padx=8, pady=4)

    def _report_carico(self) -> None:
        report = report_carico_fratelli(self.repo.get_storico_turni())
        self.txt_stats.delete("1.0", "end")
        if not report:
            self.txt_stats.insert("end", "Nessun dato nello storico.\n")
            return
        self.txt_stats.insert("end", "REPORT CARICO FRATELLI\n" + "=" * 50 + "\n\n")
        for r in report:
            self.txt_stats.insert("end",
                f"{r['fratello']}\n"
                f"  Visite totali: {r['visite_totali']}\n"
                f"  Mesi attivi: {r['mesi_attivi']}\n"
                f"  Famiglie ({r['n_famiglie_visitate']}): {', '.join(r['famiglie_visitate'])}\n\n")

    def _report_copertura(self) -> None:
        report = report_copertura_famiglie(self.repo.get_storico_turni(), self.repo.famiglie)
        self.txt_stats.delete("1.0", "end")
        if not report:
            self.txt_stats.insert("end", "Nessun dato.\n")
            return
        self.txt_stats.insert("end", "REPORT COPERTURA FAMIGLIE\n" + "=" * 50 + "\n\n")
        for r in report:
            self.txt_stats.insert("end",
                f"{r['famiglia']}\n"
                f"  Visite totali: {r['visite_totali']}, Mesi: {r['mesi_coperti']}\n"
                f"  Fratelli ({r['n_fratelli_coinvolti']}): {', '.join(r['fratelli_coinvolti'])}\n\n")

    def _report_equita(self) -> None:
        eq = calcola_indice_equita(self.repo.get_storico_turni())
        self.txt_stats.delete("1.0", "end")
        self.txt_stats.insert("end", "INDICE DI EQUITA'\n" + "=" * 50 + "\n\n")
        self.txt_stats.insert("end", f"Media visite: {eq['media']}\n")
        self.txt_stats.insert("end", f"Deviazione standard: {eq['deviazione_standard']}\n")
        self.txt_stats.insert("end", f"Min: {eq['min']} ({eq['fratello_min']})\n")
        self.txt_stats.insert("end", f"Max: {eq['max']} ({eq['fratello_max']})\n")
        self.txt_stats.insert("end", f"Gini: {eq['indice_gini']} (0=equo, 1=disuguale)\n\n")
        if eq['indice_gini'] < 0.2:
            self.txt_stats.insert("end", "Distribuzione: OTTIMA\n")
        elif eq['indice_gini'] < 0.4:
            self.txt_stats.insert("end", "Distribuzione: BUONA\n")
        else:
            self.txt_stats.insert("end", "Distribuzione: MIGLIORABILE\n")

    def _report_trend(self) -> None:
        data = trend_mensile(self.repo.get_storico_turni())
        self.txt_stats.delete("1.0", "end")
        if not data:
            self.txt_stats.insert("end", "Nessun dato nello storico.\n")
            return
        self.txt_stats.insert("end", "TREND MENSILE\n" + "=" * 50 + "\n\n")
        self.txt_stats.insert("end", f"{'Mese':<12} {'Visite':>8} {'Fratelli':>10} {'Famiglie':>10}\n")
        self.txt_stats.insert("end", "-" * 42 + "\n")
        for d in data:
            self.txt_stats.insert("end",
                f"{d['mese']:<12} {d['n_visite']:>8} {d['n_fratelli']:>10} {d['n_famiglie']:>10}\n")
        # Istogramma ASCII
        if data:
            max_v = max(d["n_visite"] for d in data) or 1
            self.txt_stats.insert("end", "\n\nIstogramma visite:\n")
            for d in data:
                bar = "#" * int(40 * d["n_visite"] / max_v)
                self.txt_stats.insert("end", f"  {d['mese']}: {bar} ({d['n_visite']})\n")

    # ------------------------------------------------------------------
    # AUDIT TRAIL
    # ------------------------------------------------------------------

    def _build_audit(self) -> None:
        tab = self.sub_tabs.add("Audit Trail")

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=6)
        ctk.CTkButton(top, text="Aggiorna", width=100,
                       command=self._refresh_audit).pack(side="left", padx=4)
        ctk.CTkLabel(top, text="Ultimi 50 eventi", text_color="gray50").pack(side="left", padx=8)

        self.txt_audit = ctk.CTkTextbox(tab, corner_radius=8)
        self.txt_audit.pack(fill="both", expand=True, padx=8, pady=4)

    def _refresh_audit(self) -> None:
        events = self.repo.get_audit_log(50)
        self.txt_audit.delete("1.0", "end")
        if not events:
            self.txt_audit.insert("end", "Nessun evento registrato.\n")
            return
        for e in events:
            self.txt_audit.insert("end",
                f"[{e.get('timestamp', '?')}] {e.get('azione', '?')}: {e.get('dettagli', '')}\n")

    # ------------------------------------------------------------------
    # Refresh globale
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        self._refresh_indisponibilita()
        self._refresh_vincoli()
        self._refresh_backups()
