"""Tab Storico: visualizzazione e gestione turni confermati."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from typing import TYPE_CHECKING

from .widgets import CTkListbox
from ..domain import EntitaNonTrovata
from ..csv_export import export_storico_csv
from ..service import open_file

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
        ctk.CTkLabel(top, text="Mesi confermati nello storico",
                      font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Aggiorna", width=100, command=self.refresh).pack(side="left", padx=8)
        ctk.CTkButton(top, text="Elimina selezionato", width=160,
                       fg_color="#d13438", hover_color="#a4262c",
                       command=self.delete_selected).pack(side="left")
        ctk.CTkButton(top, text="Esporta storico CSV", width=160,
                       command=self._export_csv).pack(side="right")

        # Lista storico
        self.list_storico = CTkListbox(self, height=180, command=self._on_select)
        self.list_storico.pack(fill="x", padx=10, pady=4)

        # Dettaglio
        ctk.CTkLabel(self, text="Dettaglio assegnazioni",
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.txt_dettaglio = ctk.CTkTextbox(self, height=200, corner_radius=8)
        self.txt_dettaglio.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt_dettaglio.configure(state="disabled")

    def refresh(self) -> None:
        self.list_storico.delete(0, "end")
        for rec in self.repo.get_storico_turni():
            mese = rec.get("mese", "?")
            n = len(rec.get("assegnazioni", []))
            confirmed = rec.get("confirmed_at", "")[:10]
            self.list_storico.insert("end", f"{mese}  ({n} assegnazioni, {confirmed})")

    def _on_select(self) -> None:
        sel = self.list_storico.curselection()
        if not sel:
            return
        text = self.list_storico.get(sel[0])
        mese = text.split()[0]

        storico = self.repo.get_storico_turni()
        rec = next((r for r in storico if r.get("mese") == mese), None)
        if not rec:
            return

        self.txt_dettaglio.configure(state="normal")
        self.txt_dettaglio.delete("1.0", "end")
        self.txt_dettaglio.insert("end", f"Mese: {mese}\n")
        self.txt_dettaglio.insert("end", f"Confermato: {rec.get('confirmed_at', '')}\n\n")

        per_fam: dict[str, list[str]] = {}
        for a in rec.get("assegnazioni", []):
            fam = a.get("famiglia", "?")
            fr = a.get("fratello", "?")
            per_fam.setdefault(fam, []).append(fr)
        for fam in sorted(per_fam.keys()):
            self.txt_dettaglio.insert("end", f"  {fam}: {', '.join(per_fam[fam])}\n")
        self.txt_dettaglio.configure(state="disabled")

    def delete_selected(self) -> None:
        sel = self.list_storico.curselection()
        if not sel:
            messagebox.showerror("Errore", "Seleziona un mese.")
            return
        text = self.list_storico.get(sel[0])
        mese = text.split()[0]
        if not messagebox.askyesno("Conferma", f"Eliminare '{mese}' dallo storico?"):
            return
        try:
            self.repo.delete_storico_mese(mese)
            self.refresh()
            if self._set_status:
                self._set_status(f"Mese '{mese}' rimosso.")
        except EntitaNonTrovata as e:
            messagebox.showerror("Errore", str(e))

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
            messagebox.showerror("Errore", str(e))
