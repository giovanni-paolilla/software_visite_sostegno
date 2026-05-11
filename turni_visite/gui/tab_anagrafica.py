"""Tab Anagrafica: gestione fratelli, famiglie, associazioni, frequenze, capacita'."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from typing import TYPE_CHECKING

from .widgets import FilterableComboBox, CTkListbox
from .themes import BUTTON_COLORS
from ..domain import TurniVisiteError
from ..csv_export import import_csv_anagrafica
from ..i18n import t

if TYPE_CHECKING:
    from ..repository import JsonRepository


class TabAnagrafica(ctk.CTkFrame):
    def __init__(self, parent, repo: "JsonRepository",
                 on_change=None, set_status=None, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self._on_change = on_change
        self._set_status = set_status
        self._build()

    def _notify(self) -> None:
        if self._on_change:
            self._on_change()

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 4}

        # --- Aggiungi fratello ---
        fr_frame = ctk.CTkFrame(self, fg_color="transparent")
        fr_frame.pack(fill="x", **pad)
        ctk.CTkLabel(fr_frame, text=t("anagrafica.fratello")).pack(side="left")
        self.entry_bro = ctk.CTkEntry(fr_frame, width=250, placeholder_text=t("nome_fratello"))
        self.entry_bro.pack(side="left", padx=8)
        self.entry_bro.bind("<Return>", lambda e: self.add_brother())
        ctk.CTkButton(fr_frame, text=t("anagrafica.aggiungi_fratello"), width=160,
                       command=self.add_brother).pack(side="left")

        # --- Aggiungi famiglia ---
        fam_frame = ctk.CTkFrame(self, fg_color="transparent")
        fam_frame.pack(fill="x", **pad)
        ctk.CTkLabel(fam_frame, text=t("anagrafica.famiglia")).pack(side="left")
        self.entry_fam = ctk.CTkEntry(fam_frame, width=250, placeholder_text=t("nome_famiglia"))
        self.entry_fam.pack(side="left", padx=8)
        self.entry_fam.bind("<Return>", lambda e: self.add_family())
        ctk.CTkButton(fam_frame, text=t("anagrafica.aggiungi_famiglia"), width=160,
                       command=self.add_family).pack(side="left")

        # --- Associa ---
        assoc_frame = ctk.CTkFrame(self, fg_color="transparent")
        assoc_frame.pack(fill="x", **pad)
        ctk.CTkLabel(assoc_frame, text=t("anagrafica.associa") + ":").pack(side="left")
        self.combo_assoc_bro = FilterableComboBox(assoc_frame, width=200, values=[])
        self.combo_assoc_bro.pack(side="left", padx=6)
        ctk.CTkLabel(assoc_frame, text="→").pack(side="left", padx=4)
        self.combo_assoc_fam = FilterableComboBox(assoc_frame, width=200, values=[])
        self.combo_assoc_fam.pack(side="left", padx=6)
        ctk.CTkButton(assoc_frame, text=t("anagrafica.associa"), width=100,
                       command=self.associate).pack(side="left", padx=6)

        # --- Frequenza ---
        freq_frame = ctk.CTkFrame(self, fg_color="transparent")
        freq_frame.pack(fill="x", **pad)
        ctk.CTkLabel(freq_frame, text=t("anagrafica.frequenza") + ":").pack(side="left")
        self.combo_freq = ctk.CTkComboBox(freq_frame, values=["1", "2", "4"], width=80)
        self.combo_freq.pack(side="left", padx=6)
        ctk.CTkLabel(freq_frame, text=t("anagrafica.per_famiglia")).pack(side="left")
        self.combo_freq_fam = FilterableComboBox(freq_frame, width=200, values=[])
        self.combo_freq_fam.pack(side="left", padx=6)
        ctk.CTkButton(freq_frame, text=t("anagrafica.imposta"), width=100,
                       command=self.set_frequency).pack(side="left", padx=6)

        # --- Capacita' ---
        cap_frame = ctk.CTkFrame(self, corner_radius=8)
        cap_frame.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(cap_frame, text=t("anagrafica.capacita"),
                      font=ctk.CTkFont(weight="bold")).pack(side="left", padx=8)
        ctk.CTkLabel(cap_frame, text=t("anagrafica.fratello")).pack(side="left", padx=(12, 4))
        self.combo_cap_bro = FilterableComboBox(cap_frame, width=200, values=[],
                                                 command=self._on_select_cap_bro)
        self.combo_cap_bro.pack(side="left", padx=4)
        ctk.CTkLabel(cap_frame, text=t("anagrafica.capacita_label")).pack(side="left", padx=(12, 4))
        self.entry_cap = ctk.CTkEntry(cap_frame, width=60, placeholder_text="1")
        self.entry_cap.pack(side="left", padx=4)
        ctk.CTkButton(cap_frame, text=t("anagrafica.imposta"), width=100,
                       command=self.set_capacity).pack(side="left", padx=8)

        # --- Elimina + Import ---
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(fill="x", **pad)
        ctk.CTkLabel(action_frame, text=t("anagrafica.elimina_fratello")).pack(side="left")
        self.combo_del_bro = FilterableComboBox(action_frame, width=180, values=[])
        self.combo_del_bro.pack(side="left", padx=4)
        ctk.CTkButton(action_frame, text=t("anagrafica.elimina"), width=80,
                       fg_color=BUTTON_COLORS["danger"],
                       hover_color=BUTTON_COLORS["danger_hover"],
                       command=self.delete_brother).pack(side="left", padx=(4, 16))
        ctk.CTkLabel(action_frame, text=t("anagrafica.elimina_famiglia")).pack(side="left")
        self.combo_del_fam = FilterableComboBox(action_frame, width=180, values=[])
        self.combo_del_fam.pack(side="left", padx=4)
        ctk.CTkButton(action_frame, text=t("anagrafica.elimina"), width=80,
                       fg_color=BUTTON_COLORS["danger"],
                       hover_color=BUTTON_COLORS["danger_hover"],
                       command=self.delete_family).pack(side="left", padx=4)
        ctk.CTkButton(action_frame, text=t("anagrafica.importa_csv"), width=120,
                       command=self.import_csv).pack(side="right")

        # --- Liste ---
        lists_frame = ctk.CTkFrame(self, fg_color="transparent")
        lists_frame.pack(fill="both", expand=True, padx=10, pady=6)
        lists_frame.columnconfigure(0, weight=1)
        lists_frame.columnconfigure(1, weight=1)
        lists_frame.rowconfigure(1, weight=1)

        ctk.CTkLabel(lists_frame, text=t("anagrafica.fratelli"), font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=4)
        self.list_bro = CTkListbox(lists_frame, height=200)
        self.list_bro.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

        ctk.CTkLabel(lists_frame, text=t("anagrafica.famiglie"), font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, sticky="w", padx=4)
        self.list_fam = CTkListbox(lists_frame, height=200)
        self.list_fam.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def add_brother(self) -> None:
        nome = self.entry_bro.get().strip()
        try:
            self.repo.add_brother(nome)
            self.entry_bro.delete(0, "end")
            self.refresh_lists()
            self._notify()
            if self._set_status:
                self._set_status(f"{t('aggiunto')} {nome}")
        except TurniVisiteError as e:
            messagebox.showerror(t("errore"), str(e))

    def add_family(self) -> None:
        nome = self.entry_fam.get().strip()
        try:
            self.repo.add_family(nome)
            self.entry_fam.delete(0, "end")
            self.refresh_lists()
            self._notify()
            if self._set_status:
                self._set_status(f"{t('aggiunto')} {nome}")
        except TurniVisiteError as e:
            messagebox.showerror(t("errore"), str(e))

    def associate(self) -> None:
        bro = self.combo_assoc_bro.get().strip()
        fam = self.combo_assoc_fam.get().strip()
        if not bro or not fam:
            messagebox.showerror(t("errore"), t("seleziona_fratello_famiglia"))
            return
        try:
            self.repo.associate(bro, fam)
            self._notify()
            if self._set_status:
                self._set_status(t("operazione_riuscita"))
        except TurniVisiteError as e:
            messagebox.showerror(t("errore"), str(e))

    def set_frequency(self) -> None:
        fam = self.combo_freq_fam.get().strip()
        val = self.combo_freq.get().strip()
        if not fam or not val:
            messagebox.showerror(t("errore"), "Seleziona famiglia e frequenza.")
            return
        try:
            self.repo.set_frequency(fam, int(val))
            self._notify()
            if self._set_status:
                self._set_status(t("operazione_riuscita"))
        except (ValueError, TurniVisiteError) as e:
            messagebox.showerror(t("errore"), str(e))

    def set_capacity(self) -> None:
        bro = self.combo_cap_bro.get().strip()
        if not bro:
            messagebox.showerror(t("errore"), "Seleziona un fratello.")
            return
        try:
            cap = int(self.entry_cap.get())
            self.repo.set_brother_capacity(bro, cap)
            self.refresh_lists()
            self._notify()
            if self._set_status:
                self._set_status(t("operazione_riuscita"))
        except (ValueError, TurniVisiteError) as e:
            messagebox.showerror(t("errore"), str(e))

    def delete_brother(self) -> None:
        bro = self.combo_del_bro.get().strip()
        if not bro:
            messagebox.showerror(t("errore"), "Seleziona un fratello.")
            return
        if messagebox.askyesno(t("conferma"), f"Eliminare il fratello '{bro}'?"):
            try:
                self.repo.remove_brother(bro)
                for cb in (self.combo_assoc_bro, self.combo_cap_bro, self.combo_del_bro):
                    cb.set("")
                self.entry_cap.delete(0, "end")
                self.refresh_lists()
                self._notify()
                if self._set_status:
                    self._set_status(f"{t('rimosso')} {bro}")
            except TurniVisiteError as e:
                messagebox.showerror(t("errore"), str(e))

    def delete_family(self) -> None:
        fam = self.combo_del_fam.get().strip()
        if not fam:
            messagebox.showerror(t("errore"), "Seleziona una famiglia.")
            return
        if messagebox.askyesno(t("conferma"), f"Eliminare la famiglia '{fam}'?"):
            try:
                self.repo.remove_family(fam)
                for cb in (self.combo_assoc_fam, self.combo_freq_fam, self.combo_del_fam):
                    cb.set("")
                self.refresh_lists()
                self._notify()
                if self._set_status:
                    self._set_status(f"{t('rimosso')} {fam}")
            except TurniVisiteError as e:
                messagebox.showerror(t("errore"), str(e))

    def import_csv(self) -> None:
        path = filedialog.askopenfilename(
            title=t("importa_csv"),
            filetypes=[("CSV", "*.csv"), ("Tutti", "*.*")],
        )
        if not path:
            return
        try:
            result = import_csv_anagrafica(path)
        except Exception as e:
            messagebox.showerror(t("errore"), f"Errore lettura CSV: {e}")
            return
        n_fr = n_fam = 0
        errori_import: list[str] = []
        for nome, cap in result["fratelli"]:
            try:
                self.repo.add_brother(nome)
                self.repo.set_brother_capacity(nome, cap)
                n_fr += 1
            except TurniVisiteError as e:
                errori_import.append(f"Fratello '{nome}': {e}")
        for nome, freq in result["famiglie"]:
            try:
                self.repo.add_family(nome)
                self.repo.set_frequency(nome, freq)
                n_fam += 1
            except TurniVisiteError as e:
                errori_import.append(f"Famiglia '{nome}': {e}")
        self.refresh_lists()
        self._notify()
        msg = f"Importati: {n_fr} fratelli, {n_fam} famiglie."
        if errori_import:
            msg += f"\n\nErrori ({len(errori_import)}):\n" + "\n".join(errori_import[:10])
        if result["errori"]:
            msg += f"\n\nErrori CSV ({len(result['errori'])}):\n" + "\n".join(result["errori"][:5])
        messagebox.showinfo(t("import_completato"), msg)

    def _on_select_cap_bro(self, choice: str) -> None:
        if not choice:
            return
        try:
            cap_attuale = int(self.repo.capacita.get(choice, 1))
            self.entry_cap.delete(0, "end")
            self.entry_cap.insert(0, str(cap_attuale))
        except (ValueError, KeyError) as e:
            messagebox.showerror(t("errore"), str(e))

    def refresh_lists(self) -> None:
        try:
            bro_labels = []
            for x in sorted(self.repo.fratelli):
                cap = self.repo.capacita.get(x, 1)
                indisp = self.repo.indisponibilita.get(x, [])
                label = f"{x}  (cap={cap})"
                if indisp:
                    label += f"  [indisp: {', '.join(indisp)}]"
                bro_labels.append(label)

            self.list_bro.delete(0, "end")
            self.list_bro.batch_insert(bro_labels)

            fam_labels = []
            for x in sorted(self.repo.famiglie):
                freq = self.repo.frequenze.get(x, 2)
                n_assoc = len(self.repo.associazioni.get(x, []))
                fam_labels.append(f"{x}  (freq={freq}, assoc={n_assoc})")

            self.list_fam.delete(0, "end")
            self.list_fam.batch_insert(fam_labels)

            bros = sorted(self.repo.fratelli)
            fams = sorted(self.repo.famiglie)
            for cb in (self.combo_assoc_bro, self.combo_cap_bro, self.combo_del_bro):
                cb.configure(values=bros)
            for cb in (self.combo_assoc_fam, self.combo_freq_fam, self.combo_del_fam):
                cb.configure(values=fams)
        except Exception as e:
            messagebox.showerror(t("errore"), f"Errore aggiornamento liste: {e}")
