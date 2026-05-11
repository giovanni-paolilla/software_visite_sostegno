"""Tab Avanzate: indisponibilita', vincoli, backup, statistiche, audit."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import TYPE_CHECKING

from .widgets import FilterableComboBox, CTkListbox
from .themes import BUTTON_COLORS
from ..domain import TurniVisiteError
from ..backup import create_backup, list_backups, restore_backup
from ..config import DATA_FILE
from ..i18n import t
from ..notifications import send_notifications
from ..scheduling import validate_month_yyyy_mm
from ..stats import (
    report_carico_fratelli, report_copertura_famiglie,
    calcola_indice_equita, trend_mensile,
)

if TYPE_CHECKING:
    from ..repository import JsonRepository


class TabAvanzate(ctk.CTkFrame):
    def __init__(self, parent, repo: "JsonRepository",
                 set_status=None, on_change=None,
                 on_invalidate_pianificazione=None, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self._set_status = set_status
        self._on_change = on_change
        self._on_invalidate_pianificazione = on_invalidate_pianificazione
        self._build()

    def _build(self) -> None:
        # Sub-tabview
        self.sub_tabs = ctk.CTkTabview(self, corner_radius=8)
        self.sub_tabs.pack(fill="both", expand=True, padx=6, pady=6)

        self._build_indisponibilita()
        self._build_vincoli()
        self._build_affinita()
        self._build_notifiche()
        self._build_backup()
        self._build_statistiche()
        self._build_audit()

    # ------------------------------------------------------------------
    # INDISPONIBILITA'
    # ------------------------------------------------------------------

    def _build_indisponibilita(self) -> None:
        tab = self.sub_tabs.add(t("avanzate.indisponibilita"))

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(top, text=t("avanzate.fratello")).pack(side="left")
        self.combo_ind_bro = FilterableComboBox(top, width=200, values=[])
        self.combo_ind_bro.pack(side="left", padx=6)
        ctk.CTkLabel(top, text=t("avanzate.mese")).pack(side="left", padx=(8, 4))
        self.entry_ind_mese = ctk.CTkEntry(top, width=120, placeholder_text="2026-05")
        self.entry_ind_mese.pack(side="left", padx=4)
        ctk.CTkButton(top, text=t("avanzate.aggiungi"), width=100,
                       command=self._add_indisponibilita).pack(side="left", padx=4)
        ctk.CTkButton(top, text=t("avanzate.rimuovi"), width=100,
                       fg_color=BUTTON_COLORS["danger"],
                       hover_color=BUTTON_COLORS["danger_hover"],
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
            messagebox.showerror(t("errore"), "Seleziona fratello e mese.")
            return
        try:
            mese = validate_month_yyyy_mm(mese)
            self.repo.add_indisponibilita(bro, mese)
            self._refresh_indisponibilita()
            if self._set_status:
                self._set_status(f"Indisponibilita' aggiunta: {bro} per {mese}")
        except (ValueError, TurniVisiteError) as e:
            messagebox.showerror(t("errore"), str(e))

    def _remove_indisponibilita(self) -> None:
        bro = self.combo_ind_bro.get().strip()
        mese = self.entry_ind_mese.get().strip()
        if not bro or not mese:
            messagebox.showerror(t("errore"), "Seleziona fratello e mese.")
            return
        try:
            self.repo.remove_indisponibilita(bro, mese)
            self._refresh_indisponibilita()
        except TurniVisiteError as e:
            messagebox.showerror(t("errore"), str(e))

    # ------------------------------------------------------------------
    # VINCOLI
    # ------------------------------------------------------------------

    def _build_vincoli(self) -> None:
        tab = self.sub_tabs.add(t("avanzate.vincoli"))

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(top, text=t("avanzate.fratello_a")).pack(side="left")
        self.combo_vinc_a = FilterableComboBox(top, width=160, values=[])
        self.combo_vinc_a.pack(side="left", padx=4)
        ctk.CTkLabel(top, text=t("avanzate.fratello_b")).pack(side="left")
        self.combo_vinc_b = FilterableComboBox(top, width=160, values=[])
        self.combo_vinc_b.pack(side="left", padx=4)
        ctk.CTkLabel(top, text=t("avanzate.tipo")).pack(side="left")
        self.combo_vinc_tipo = ctk.CTkComboBox(
            top, values=["incompatibile", "preferenza_coppia"], width=160)
        self.combo_vinc_tipo.pack(side="left", padx=4)
        ctk.CTkButton(top, text=t("avanzate.aggiungi"), width=100,
                       command=self._add_vincolo).pack(side="left", padx=4)

        bottom = ctk.CTkFrame(tab, fg_color="transparent")
        bottom.pack(fill="x", padx=8, pady=2)
        ctk.CTkButton(bottom, text=t("avanzate.rimuovi_selezionato"), width=160,
                       fg_color=BUTTON_COLORS["danger"],
                       hover_color=BUTTON_COLORS["danger_hover"],
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
                f"{v.get('fratello_a', '?')} ↔ {v.get('fratello_b', '?')} "
                f"[{v.get('tipo', '?')}] {v.get('descrizione', '')}"
            )

    def _add_vincolo(self) -> None:
        fa = self.combo_vinc_a.get().strip()
        fb = self.combo_vinc_b.get().strip()
        tipo = self.combo_vinc_tipo.get().strip()
        if not fa or not fb or not tipo:
            messagebox.showerror(t("errore"), "Compila tutti i campi.")
            return
        try:
            self.repo.add_vincolo(fa, fb, tipo)
            self._refresh_vincoli()
        except TurniVisiteError as e:
            messagebox.showerror(t("errore"), str(e))

    def _remove_vincolo(self) -> None:
        sel = self.list_vincoli.curselection()
        if not sel:
            messagebox.showerror(t("errore"), "Seleziona un vincolo.")
            return
        idx = sel[0]
        if idx >= len(self.repo.vincoli_personalizzati):
            return
        v = self.repo.vincoli_personalizzati[idx]
        try:
            self.repo.remove_vincolo(v["fratello_a"], v["fratello_b"], v["tipo"])
            self._refresh_vincoli()
        except TurniVisiteError as e:
            messagebox.showerror(t("errore"), str(e))

    # ------------------------------------------------------------------
    # AFFINITA' FRATELLO-FAMIGLIA
    # ------------------------------------------------------------------

    def _build_affinita(self) -> None:
        tab = self.sub_tabs.add(t("avanzate.affinita"))

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(top, text=t("avanzate.famiglia_aff")).pack(side="left")
        self.combo_aff_fam = FilterableComboBox(top, width=160, values=[])
        self.combo_aff_fam.pack(side="left", padx=4)
        ctk.CTkLabel(top, text=t("avanzate.fratello_aff")).pack(side="left", padx=(8, 2))
        self.combo_aff_bro = FilterableComboBox(top, width=160, values=[])
        self.combo_aff_bro.pack(side="left", padx=4)
        ctk.CTkLabel(top, text=t("avanzate.peso")).pack(side="left", padx=(8, 2))
        self.entry_aff_peso = ctk.CTkEntry(top, width=60, placeholder_text="0")
        self.entry_aff_peso.pack(side="left", padx=4)
        ctk.CTkButton(top, text=t("avanzate.aggiungi_affinita"), width=120,
                       command=self._add_affinita).pack(side="left", padx=4)
        ctk.CTkButton(top, text=t("avanzate.rimuovi_affinita"), width=100,
                       fg_color=BUTTON_COLORS["danger"],
                       hover_color=BUTTON_COLORS["danger_hover"],
                       command=self._remove_affinita).pack(side="left", padx=4)

        self.list_affinita = CTkListbox(tab, height=200)
        self.list_affinita.pack(fill="both", expand=True, padx=8, pady=4)

    def _refresh_affinita(self) -> None:
        self.combo_aff_fam.configure(values=sorted(self.repo.famiglie))
        self.combo_aff_bro.configure(values=sorted(self.repo.fratelli))
        self.list_affinita.delete(0, "end")
        for a in self.repo.get_affinita():
            peso = a.get("peso", 0)
            icon = "+" if peso > 0 else ("-" if peso < 0 else "=")
            self.list_affinita.insert(
                "end",
                f"{a.get('fratello', '?')} → {a.get('famiglia', '?')} [{icon}{abs(peso)}]"
            )

    def _add_affinita(self) -> None:
        fam = self.combo_aff_fam.get().strip()
        bro = self.combo_aff_bro.get().strip()
        try:
            peso = int(self.entry_aff_peso.get().strip() or "0")
        except ValueError:
            messagebox.showerror(t("errore"), "Peso deve essere un numero intero.")
            return
        if not fam or not bro:
            messagebox.showerror(t("errore"), "Seleziona famiglia e fratello.")
            return
        try:
            self.repo.add_affinita(fam, bro, peso)
            self._refresh_affinita()
            if self._set_status:
                self._set_status(f"Affinita' impostata: {bro} → {fam} = {peso}")
        except TurniVisiteError as e:
            messagebox.showerror(t("errore"), str(e))

    def _remove_affinita(self) -> None:
        sel = self.list_affinita.curselection()
        if not sel:
            messagebox.showerror(t("errore"), "Seleziona un'affinita'.")
            return
        idx = sel[0]
        affinita = self.repo.get_affinita()
        if idx >= len(affinita):
            return
        a = affinita[idx]
        try:
            self.repo.remove_affinita(a["famiglia"], a["fratello"])
            self._refresh_affinita()
        except TurniVisiteError as e:
            messagebox.showerror(t("errore"), str(e))

    # ------------------------------------------------------------------
    # NOTIFICHE EMAIL
    # ------------------------------------------------------------------

    def _build_notifiche(self) -> None:
        tab = self.sub_tabs.add(t("notifiche.titolo"))

        # Config SMTP
        cfg_frame = ctk.CTkFrame(tab, corner_radius=8)
        cfg_frame.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(cfg_frame, text=t("notifiche.config_smtp"),
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(6, 2))

        smtp_grid = ctk.CTkFrame(cfg_frame, fg_color="transparent")
        smtp_grid.pack(fill="x", padx=8, pady=4)

        fields = [
            ("smtp_host", t("notifiche.host"), 250),
            ("smtp_port", t("notifiche.porta"), 80),
            ("smtp_user", t("notifiche.utente"), 200),
            ("smtp_from", t("notifiche.mittente"), 250),
        ]
        self._smtp_entries: dict[str, ctk.CTkEntry] = {}
        for row, (key, label, width) in enumerate(fields):
            ctk.CTkLabel(smtp_grid, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            entry = ctk.CTkEntry(smtp_grid, width=width)
            entry.grid(row=row, column=1, sticky="w", padx=4, pady=2)
            val = self.repo.get_setting(key, "")
            if val:
                entry.insert(0, str(val))
            self._smtp_entries[key] = entry

        # Password SMTP: avviso variabile d'ambiente (non salvata nel JSON)
        pwd_row = len(fields)
        ctk.CTkLabel(smtp_grid, text=t("notifiche.password")).grid(
            row=pwd_row, column=0, sticky="w", padx=4, pady=2)
        ctk.CTkLabel(
            smtp_grid,
            text="Imposta la variabile d'ambiente TURNI_SMTP_PASSWORD",
            text_color=("gray40", "gray60"),
        ).grid(row=pwd_row, column=1, sticky="w", padx=4, pady=2)

        btn_row = ctk.CTkFrame(cfg_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(btn_row, text=t("notifiche.salva_config"), width=180,
                       command=self._save_smtp_config).pack(side="left", padx=4)

        # Email fratelli
        email_frame = ctk.CTkFrame(tab, corner_radius=8)
        email_frame.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(email_frame, text=t("notifiche.email_fratelli"),
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(6, 2))

        email_row = ctk.CTkFrame(email_frame, fg_color="transparent")
        email_row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(email_row, text=t("avanzate.fratello")).pack(side="left")
        self.combo_email_bro = FilterableComboBox(email_row, width=180, values=[])
        self.combo_email_bro.pack(side="left", padx=4)
        ctk.CTkLabel(email_row, text="Email:").pack(side="left", padx=(8, 4))
        self.entry_email = ctk.CTkEntry(email_row, width=250, placeholder_text="email@esempio.it")
        self.entry_email.pack(side="left", padx=4)
        ctk.CTkButton(email_row, text=t("anagrafica.imposta"), width=100,
                       command=self._save_email_fratello).pack(side="left", padx=4)

        self.list_emails = CTkListbox(email_frame, height=120)
        self.list_emails.pack(fill="x", padx=8, pady=4)

    def _save_smtp_config(self) -> None:
        for key, entry in self._smtp_entries.items():
            if key == "smtp_password":
                # Password non viene mai salvata nel JSON
                continue
            val = entry.get().strip()
            if key == "smtp_port":
                try:
                    val = int(val) if val else 587
                except ValueError:
                    messagebox.showerror(t("errore"), "Porta deve essere un numero.")
                    return
            self.repo.set_setting(key, val)
        # Rimuovi eventuale password residua dal repository
        try:
            self.repo.set_setting("smtp_password", "")
        except Exception:
            pass
        if self._set_status:
            self._set_status(t("smtp_configurazione"))

    def _save_email_fratello(self) -> None:
        bro = self.combo_email_bro.get().strip()
        email = self.entry_email.get().strip()
        if not bro or not email:
            messagebox.showerror(t("errore"), "Seleziona fratello e inserisci email.")
            return
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            messagebox.showerror(t("errore"), "Indirizzo email non valido")
            return
        email_map = self.repo.get_setting("email_fratelli", {})
        email_map[bro] = email
        self.repo.set_setting("email_fratelli", email_map)
        self._refresh_notifiche()

    def _refresh_notifiche(self) -> None:
        self.combo_email_bro.configure(values=sorted(self.repo.fratelli))
        self.list_emails.delete(0, "end")
        email_map = self.repo.get_setting("email_fratelli", {})
        for fr in sorted(email_map.keys()):
            self.list_emails.insert("end", f"{fr}: {email_map[fr]}")

    # ------------------------------------------------------------------
    # BACKUP
    # ------------------------------------------------------------------

    def _build_backup(self) -> None:
        tab = self.sub_tabs.add(t("avanzate.backup"))

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=6)
        ctk.CTkButton(top, text=t("avanzate.crea_backup"), width=160,
                       command=self._create_backup).pack(side="left", padx=4)
        ctk.CTkButton(top, text=t("avanzate.ripristina"), width=180,
                       command=self._restore_backup).pack(side="left", padx=4)
        ctk.CTkButton(top, text=t("avanzate.aggiorna_lista"), width=140,
                       command=self._refresh_backups).pack(side="right", padx=4)

        self.list_backups = CTkListbox(tab, height=250)
        self.list_backups.pack(fill="both", expand=True, padx=8, pady=4)

    def _refresh_backups(self) -> None:
        self.list_backups.delete(0, "end")
        for b in list_backups():
            self.list_backups.insert("end",
                                      f"{b['filename']}  ({b['size_kb']} KB, {b['modified']})")

    def _create_backup(self) -> None:
        import threading

        def _do() -> None:
            try:
                path = create_backup(DATA_FILE)
                if path:
                    self.after(0, lambda: (
                        self._refresh_backups(),
                        self._set_status(f"Backup creato.") if self._set_status else None,
                    ))
                else:
                    self.after(0, lambda: messagebox.showinfo(t("info"), "Nessun file dati da salvare in backup."))
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror(t("errore"), str(err)))

        threading.Thread(target=_do, daemon=True).start()

    def _restore_backup(self) -> None:
        import threading
        sel = self.list_backups.curselection()
        if not sel:
            messagebox.showerror(t("errore"), "Seleziona un backup.")
            return
        backups = list_backups()
        if sel[0] >= len(backups):
            return
        b = backups[sel[0]]
        if not messagebox.askyesno(t("conferma"), f"Ripristinare '{b['filename']}'?"):
            return

        def _do() -> None:
            try:
                restore_backup(b["path"], DATA_FILE)
                self.after(0, self._finish_restore)
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror(t("errore"), str(err)))

        threading.Thread(target=_do, daemon=True).start()

    def _finish_restore(self) -> None:
        self.repo.load()
        self._invalidate_pianificazione()
        if self._on_change:
            self._on_change()
        self._refresh_backups()
        messagebox.showinfo(t("info"), t("backup_ripristinato"))

    # ------------------------------------------------------------------
    # STATISTICHE
    # ------------------------------------------------------------------

    def _build_statistiche(self) -> None:
        tab = self.sub_tabs.add(t("avanzate.statistiche"))

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=6)
        ctk.CTkButton(top, text=t("avanzate.carico_fratelli"), width=140,
                       command=self._report_carico).pack(side="left", padx=3)
        ctk.CTkButton(top, text=t("avanzate.copertura_famiglie"), width=150,
                       command=self._report_copertura).pack(side="left", padx=3)
        ctk.CTkButton(top, text=t("avanzate.indice_equita"), width=130,
                       command=self._report_equita).pack(side="left", padx=3)
        ctk.CTkButton(top, text=t("avanzate.trend_mensile"), width=130,
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
        tab = self.sub_tabs.add(t("avanzate.audit"))

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=6)
        ctk.CTkButton(top, text=t("aggiorna"), width=100,
                       command=self._refresh_audit).pack(side="left", padx=4)
        ctk.CTkLabel(top, text=t("avanzate.ultimi_eventi"),
                      text_color=("gray40", "gray60")).pack(side="left", padx=8)

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
    # Helpers
    # ------------------------------------------------------------------

    def _invalidate_pianificazione(self) -> None:
        if self._on_invalidate_pianificazione:
            try:
                self._on_invalidate_pianificazione()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Refresh globale
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        self._refresh_indisponibilita()
        self._refresh_vincoli()
        self._refresh_affinita()
        self._refresh_notifiche()
        self._refresh_backups()
