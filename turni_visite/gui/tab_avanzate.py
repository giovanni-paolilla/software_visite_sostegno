"""Tab Avanzate: indisponibilita', vincoli personalizzati, backup, statistiche, audit."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from tkinter.scrolledtext import ScrolledText
from typing import TYPE_CHECKING

from .widgets import TypeaheadCombobox
from ..domain import TurniVisiteError
from ..backup import create_backup, list_backups, restore_backup
from ..config import DATA_FILE
from ..scheduling import validate_month_yyyy_mm
from ..stats import report_carico_fratelli, report_copertura_famiglie, calcola_indice_equita, trend_mensile

if TYPE_CHECKING:
    from ..repository import JsonRepository


class TabAvanzate(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, repo: "JsonRepository",
                 theme: dict, set_status=None, on_change=None, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self.theme = theme
        self._set_status = set_status
        self._on_change = on_change
        self._build()

    def _build(self) -> None:
        pad = {"padx": 6, "pady": 4}

        # Sub-notebook per organizzare le sezioni avanzate
        sub_nb = ttk.Notebook(self)
        sub_nb.pack(fill="both", expand=True, padx=4, pady=4)

        self._build_indisponibilita(sub_nb, pad)
        self._build_vincoli(sub_nb, pad)
        self._build_backup(sub_nb, pad)
        self._build_statistiche(sub_nb, pad)
        self._build_audit(sub_nb, pad)

    # ------------------------------------------------------------------
    # INDISPONIBILITA'
    # ------------------------------------------------------------------

    def _build_indisponibilita(self, nb: ttk.Notebook, pad: dict) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Indisponibilita'")

        top = ttk.Frame(frame)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Fratello:").pack(side="left")
        self.combo_ind_bro = TypeaheadCombobox(top, width=28, state="readonly")
        self.combo_ind_bro.pack(side="left", padx=4)
        ttk.Label(top, text="Mese (YYYY-MM):").pack(side="left", padx=(8, 2))
        self.entry_ind_mese = ttk.Entry(top, width=12)
        self.entry_ind_mese.pack(side="left", padx=4)
        ttk.Button(top, text="Aggiungi", command=self._add_indisponibilita).pack(side="left", padx=4)
        ttk.Button(top, text="Rimuovi", command=self._remove_indisponibilita).pack(side="left", padx=4)

        self.list_ind = tk.Listbox(frame, height=10,
                                    bg=self.theme.get("list_bg", "#fff"),
                                    fg=self.theme.get("list_fg", "#000"))
        self.list_ind.pack(fill="both", expand=True, **pad)

        ttk.Button(frame, text="Aggiorna lista", command=self._refresh_indisponibilita).pack(**pad)

    def _refresh_indisponibilita(self) -> None:
        self.combo_ind_bro["values"] = sorted(self.repo.fratelli)
        self.list_ind.delete(0, tk.END)
        for fr in sorted(self.repo.fratelli):
            mesi = self.repo.indisponibilita.get(fr, [])
            if mesi:
                self.list_ind.insert(tk.END, f"{fr}: {', '.join(mesi)}")

    def _add_indisponibilita(self) -> None:
        bro = self.combo_ind_bro.get().strip()
        mese = self.entry_ind_mese.get().strip()
        if not bro or not mese:
            messagebox.showerror("Errore", "Seleziona fratello e inserisci mese.", parent=self)
            return
        try:
            mese = validate_month_yyyy_mm(mese)
            self.repo.add_indisponibilita(bro, mese)
            self._refresh_indisponibilita()
            if self._set_status:
                self._set_status(f"Indisponibilita' aggiunta: {bro} per {mese}")
        except (ValueError, TurniVisiteError) as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def _remove_indisponibilita(self) -> None:
        bro = self.combo_ind_bro.get().strip()
        mese = self.entry_ind_mese.get().strip()
        if not bro or not mese:
            messagebox.showerror("Errore", "Seleziona fratello e inserisci mese.", parent=self)
            return
        try:
            self.repo.remove_indisponibilita(bro, mese)
            self._refresh_indisponibilita()
            if self._set_status:
                self._set_status(f"Indisponibilita' rimossa: {bro} per {mese}")
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e), parent=self)

    # ------------------------------------------------------------------
    # VINCOLI PERSONALIZZATI
    # ------------------------------------------------------------------

    def _build_vincoli(self, nb: ttk.Notebook, pad: dict) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Vincoli")

        top = ttk.Frame(frame)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Fratello A:").pack(side="left")
        self.combo_vinc_a = TypeaheadCombobox(top, width=22, state="readonly")
        self.combo_vinc_a.pack(side="left", padx=4)
        ttk.Label(top, text="Fratello B:").pack(side="left")
        self.combo_vinc_b = TypeaheadCombobox(top, width=22, state="readonly")
        self.combo_vinc_b.pack(side="left", padx=4)
        ttk.Label(top, text="Tipo:").pack(side="left")
        self.combo_vinc_tipo = TypeaheadCombobox(
            top, values=["incompatibile", "preferenza_coppia"], width=18, state="readonly"
        )
        self.combo_vinc_tipo.pack(side="left", padx=4)
        ttk.Button(top, text="Aggiungi", command=self._add_vincolo).pack(side="left", padx=4)

        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", **pad)
        ttk.Button(bottom, text="Rimuovi selezionato", command=self._remove_vincolo).pack(side="left")

        self.list_vincoli = tk.Listbox(frame, height=8,
                                        bg=self.theme.get("list_bg", "#fff"),
                                        fg=self.theme.get("list_fg", "#000"))
        self.list_vincoli.pack(fill="both", expand=True, **pad)

    def _refresh_vincoli(self) -> None:
        bros = sorted(self.repo.fratelli)
        self.combo_vinc_a["values"] = bros
        self.combo_vinc_b["values"] = bros
        self.list_vincoli.delete(0, tk.END)
        for v in self.repo.vincoli_personalizzati:
            self.list_vincoli.insert(
                tk.END,
                f"{v.get('fratello_a', '?')} <-> {v.get('fratello_b', '?')} [{v.get('tipo', '?')}] "
                f"{v.get('descrizione', '')}"
            )

    def _add_vincolo(self) -> None:
        fa = self.combo_vinc_a.get().strip()
        fb = self.combo_vinc_b.get().strip()
        tipo = self.combo_vinc_tipo.get().strip()
        if not fa or not fb or not tipo:
            messagebox.showerror("Errore", "Compila tutti i campi.", parent=self)
            return
        try:
            self.repo.add_vincolo(fa, fb, tipo)
            self._refresh_vincoli()
            if self._set_status:
                self._set_status(f"Vincolo {tipo} aggiunto: {fa} <-> {fb}")
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def _remove_vincolo(self) -> None:
        sel = self.list_vincoli.curselection()
        if not sel:
            messagebox.showerror("Errore", "Seleziona un vincolo.", parent=self)
            return
        v = self.repo.vincoli_personalizzati[sel[0]]
        try:
            self.repo.remove_vincolo(v["fratello_a"], v["fratello_b"], v["tipo"])
            self._refresh_vincoli()
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e), parent=self)

    # ------------------------------------------------------------------
    # BACKUP
    # ------------------------------------------------------------------

    def _build_backup(self, nb: ttk.Notebook, pad: dict) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Backup")

        top = ttk.Frame(frame)
        top.pack(fill="x", **pad)
        ttk.Button(top, text="Crea backup ora", command=self._create_backup).pack(side="left", padx=4)
        ttk.Button(top, text="Ripristina selezionato", command=self._restore_backup).pack(side="left", padx=4)
        ttk.Button(top, text="Aggiorna lista", command=self._refresh_backups).pack(side="right", padx=4)

        self.list_backups = tk.Listbox(frame, height=10,
                                        bg=self.theme.get("list_bg", "#fff"),
                                        fg=self.theme.get("list_fg", "#000"))
        self.list_backups.pack(fill="both", expand=True, **pad)

    def _refresh_backups(self) -> None:
        self.list_backups.delete(0, tk.END)
        for b in list_backups():
            self.list_backups.insert(
                tk.END,
                f"{b['filename']}  ({b['size_kb']} KB, {b['modified']})"
            )

    def _create_backup(self) -> None:
        path = create_backup(DATA_FILE)
        if path:
            self._refresh_backups()
            if self._set_status:
                self._set_status(f"Backup creato: {path}")
        else:
            messagebox.showinfo("Info", "Nessun file dati da backuppare.", parent=self)

    def _restore_backup(self) -> None:
        sel = self.list_backups.curselection()
        if not sel:
            messagebox.showerror("Errore", "Seleziona un backup da ripristinare.", parent=self)
            return
        backups = list_backups()
        if sel[0] >= len(backups):
            return
        b = backups[sel[0]]
        if not messagebox.askyesno(
            "Conferma ripristino",
            f"Ripristinare il backup '{b['filename']}'?\n"
            "Il file dati attuale sara' salvato come backup prima del ripristino.",
            parent=self,
        ):
            return
        try:
            restore_backup(b["path"], DATA_FILE)
            self.repo.load()
            if self._on_change:
                self._on_change()
            self._refresh_backups()
            if self._set_status:
                self._set_status(f"Backup ripristinato: {b['filename']}")
            messagebox.showinfo("Ripristino", "Backup ripristinato. Le liste sono state aggiornate.", parent=self)
        except Exception as e:
            messagebox.showerror("Errore", str(e), parent=self)

    # ------------------------------------------------------------------
    # STATISTICHE
    # ------------------------------------------------------------------

    def _build_statistiche(self, nb: ttk.Notebook, pad: dict) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Statistiche")

        top = ttk.Frame(frame)
        top.pack(fill="x", **pad)
        ttk.Button(top, text="Report carico fratelli", command=self._report_carico).pack(side="left", padx=4)
        ttk.Button(top, text="Report copertura famiglie", command=self._report_copertura).pack(side="left", padx=4)
        ttk.Button(top, text="Indice equita'", command=self._report_equita).pack(side="left", padx=4)
        ttk.Button(top, text="Trend mensile", command=self._report_trend).pack(side="left", padx=4)

        self.txt_stats = ScrolledText(frame, wrap="word", height=16,
                                       bg=self.theme.get("text_bg", "#fff"),
                                       fg=self.theme.get("text_fg", "#000"))
        self.txt_stats.pack(fill="both", expand=True, **pad)

    def _report_carico(self) -> None:
        report = report_carico_fratelli(self.repo.get_storico_turni())
        self.txt_stats.delete("1.0", tk.END)
        if not report:
            self.txt_stats.insert(tk.END, "Nessun dato nello storico.\n")
            return
        self.txt_stats.insert(tk.END, "REPORT CARICO FRATELLI\n")
        self.txt_stats.insert(tk.END, "=" * 60 + "\n\n")
        for r in report:
            self.txt_stats.insert(
                tk.END,
                f"{r['fratello']}\n"
                f"  Visite totali: {r['visite_totali']}\n"
                f"  Mesi attivi: {r['mesi_attivi']}\n"
                f"  Famiglie visitate ({r['n_famiglie_visitate']}): "
                f"{', '.join(r['famiglie_visitate'])}\n"
                f"  Dettaglio mensile: {r['dettaglio_mensile']}\n\n"
            )

    def _report_copertura(self) -> None:
        report = report_copertura_famiglie(self.repo.get_storico_turni(), self.repo.famiglie)
        self.txt_stats.delete("1.0", tk.END)
        if not report:
            self.txt_stats.insert(tk.END, "Nessun dato.\n")
            return
        self.txt_stats.insert(tk.END, "REPORT COPERTURA FAMIGLIE\n")
        self.txt_stats.insert(tk.END, "=" * 60 + "\n\n")
        for r in report:
            self.txt_stats.insert(
                tk.END,
                f"{r['famiglia']}\n"
                f"  Visite totali: {r['visite_totali']}\n"
                f"  Mesi coperti: {r['mesi_coperti']}\n"
                f"  Fratelli coinvolti ({r['n_fratelli_coinvolti']}): "
                f"{', '.join(r['fratelli_coinvolti'])}\n\n"
            )

    def _report_equita(self) -> None:
        eq = calcola_indice_equita(self.repo.get_storico_turni())
        self.txt_stats.delete("1.0", tk.END)
        self.txt_stats.insert(tk.END, "INDICE DI EQUITA'\n")
        self.txt_stats.insert(tk.END, "=" * 60 + "\n\n")
        self.txt_stats.insert(tk.END, f"Media visite per fratello: {eq['media']}\n")
        self.txt_stats.insert(tk.END, f"Deviazione standard: {eq['deviazione_standard']}\n")
        self.txt_stats.insert(tk.END, f"Minimo: {eq['min']} ({eq['fratello_min']})\n")
        self.txt_stats.insert(tk.END, f"Massimo: {eq['max']} ({eq['fratello_max']})\n")
        self.txt_stats.insert(tk.END, f"Indice di Gini: {eq['indice_gini']}\n")
        self.txt_stats.insert(tk.END, f"  (0 = perfetta equita', 1 = massima disuguaglianza)\n\n")
        if eq['indice_gini'] < 0.2:
            self.txt_stats.insert(tk.END, "Distribuzione: OTTIMA\n")
        elif eq['indice_gini'] < 0.4:
            self.txt_stats.insert(tk.END, "Distribuzione: BUONA\n")
        else:
            self.txt_stats.insert(tk.END, "Distribuzione: MIGLIORABILE\n")

    def _report_trend(self) -> None:
        data = trend_mensile(self.repo.get_storico_turni())
        self.txt_stats.delete("1.0", tk.END)
        if not data:
            self.txt_stats.insert(tk.END, "Nessun dato nello storico.\n")
            return
        self.txt_stats.insert(tk.END, "TREND MENSILE\n")
        self.txt_stats.insert(tk.END, "=" * 60 + "\n\n")
        self.txt_stats.insert(tk.END, f"{'Mese':<12} {'Visite':>8} {'Fratelli':>10} {'Famiglie':>10}\n")
        self.txt_stats.insert(tk.END, "-" * 42 + "\n")
        for d in data:
            self.txt_stats.insert(
                tk.END,
                f"{d['mese']:<12} {d['n_visite']:>8} {d['n_fratelli']:>10} {d['n_famiglie']:>10}\n"
            )

        # Grafico ASCII semplice
        if data:
            max_v = max(d["n_visite"] for d in data) or 1
            self.txt_stats.insert(tk.END, "\n\nIstogramma visite:\n")
            for d in data:
                bar_len = int(40 * d["n_visite"] / max_v)
                bar = "#" * bar_len
                self.txt_stats.insert(tk.END, f"  {d['mese']}: {bar} ({d['n_visite']})\n")

    # ------------------------------------------------------------------
    # AUDIT TRAIL
    # ------------------------------------------------------------------

    def _build_audit(self, nb: ttk.Notebook, pad: dict) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Audit Trail")

        top = ttk.Frame(frame)
        top.pack(fill="x", **pad)
        ttk.Button(top, text="Aggiorna", command=self._refresh_audit).pack(side="left", padx=4)
        ttk.Label(top, text="Ultimi 50 eventi").pack(side="left", padx=4)

        self.txt_audit = ScrolledText(frame, wrap="word", height=16,
                                       bg=self.theme.get("text_bg", "#fff"),
                                       fg=self.theme.get("text_fg", "#000"))
        self.txt_audit.pack(fill="both", expand=True, **pad)

    def _refresh_audit(self) -> None:
        events = self.repo.get_audit_log(50)
        self.txt_audit.delete("1.0", tk.END)
        if not events:
            self.txt_audit.insert(tk.END, "Nessun evento registrato.\n")
            return
        for e in events:
            self.txt_audit.insert(
                tk.END,
                f"[{e.get('timestamp', '?')}] {e.get('azione', '?')}: {e.get('dettagli', '')}\n"
            )

    # ------------------------------------------------------------------
    # Refresh globale (chiamato dal main)
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        self._refresh_indisponibilita()
        self._refresh_vincoli()
        self._refresh_backups()
