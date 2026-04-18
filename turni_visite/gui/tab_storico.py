"""Tab Storico: visualizzazione e gestione turni confermati."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from typing import TYPE_CHECKING

from ..domain import EntitaNonTrovata
from ..csv_export import export_storico_csv
from ..service import open_file

if TYPE_CHECKING:
    from ..repository import JsonRepository


class TabStorico(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, repo: "JsonRepository",
                 theme: dict, set_status=None, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self.theme = theme
        self._set_status = set_status
        self._build()

    def _build(self) -> None:
        pad = {"padx": 6, "pady": 6}

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Mesi confermati nello storico:").pack(side="left")
        ttk.Button(top, text="Aggiorna", command=self.refresh).pack(side="left", padx=6)
        ttk.Button(top, text="Elimina selezionato", command=self.delete_selected).pack(side="left")
        ttk.Button(top, text="Esporta storico CSV", command=self._export_csv).pack(side="right")

        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, **pad)

        sb = ttk.Scrollbar(list_frame, orient="vertical")
        self.list_storico = tk.Listbox(
            list_frame, yscrollcommand=sb.set, height=12,
            bg=self.theme.get("list_bg", "#fff"),
            fg=self.theme.get("list_fg", "#000"),
            selectbackground=self.theme.get("list_select_bg", "#0078d4"),
        )
        sb.config(command=self.list_storico.yview)
        self.list_storico.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

        # Dettaglio assegnazioni del mese selezionato
        detail_frame = ttk.LabelFrame(self, text="Dettaglio assegnazioni")
        detail_frame.pack(fill="both", expand=True, **pad)

        self.txt_dettaglio = tk.Text(
            detail_frame, height=10, wrap="word", state="disabled",
            bg=self.theme.get("text_bg", "#fff"),
            fg=self.theme.get("text_fg", "#000"),
        )
        self.txt_dettaglio.pack(fill="both", expand=True, padx=4, pady=4)

        self.list_storico.bind("<<ListboxSelect>>", self._on_select)

    def refresh(self) -> None:
        self.list_storico.delete(0, tk.END)
        for rec in self.repo.get_storico_turni():
            mese = rec.get("mese", "?")
            n = len(rec.get("assegnazioni", []))
            confirmed = rec.get("confirmed_at", "")[:10]
            self.list_storico.insert(tk.END, f"{mese}  ({n} assegnazioni, {confirmed})")

    def _on_select(self, _event=None) -> None:
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
        self.txt_dettaglio.delete("1.0", tk.END)
        self.txt_dettaglio.insert(tk.END, f"Mese: {mese}\n")
        self.txt_dettaglio.insert(tk.END, f"Confermato: {rec.get('confirmed_at', '')}\n\n")

        # Raggruppa per famiglia
        per_fam: dict[str, list[str]] = {}
        for a in rec.get("assegnazioni", []):
            fam = a.get("famiglia", "?")
            fr = a.get("fratello", "?")
            per_fam.setdefault(fam, []).append(fr)

        for fam in sorted(per_fam.keys()):
            fratelli = ", ".join(per_fam[fam])
            self.txt_dettaglio.insert(tk.END, f"  {fam}: {fratelli}\n")

        self.txt_dettaglio.configure(state="disabled")

    def delete_selected(self) -> None:
        sel = self.list_storico.curselection()
        if not sel:
            messagebox.showerror("Errore", "Seleziona un mese dallo storico.", parent=self)
            return
        text = self.list_storico.get(sel[0])
        mese = text.split()[0]
        if not messagebox.askyesno("Conferma", f"Eliminare '{mese}' dallo storico?", parent=self):
            return
        try:
            self.repo.delete_storico_mese(mese)
            self.refresh()
            if self._set_status:
                self._set_status(f"Mese '{mese}' rimosso dallo storico.")
        except EntitaNonTrovata as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tutti", "*.*")],
            initialfile="storico_turni.csv",
            title="Esporta storico CSV",
        )
        if not path:
            return
        try:
            export_storico_csv(self.repo.get_storico_turni(), path)
            open_file(path)
            if self._set_status:
                self._set_status(f"Storico esportato: {path}")
        except Exception as e:
            messagebox.showerror("Errore", str(e), parent=self)
