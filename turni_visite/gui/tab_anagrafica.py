"""Tab Anagrafica: gestione fratelli, famiglie, associazioni, frequenze, capacita'."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from typing import TYPE_CHECKING

from .widgets import TypeaheadCombobox
from ..domain import TurniVisiteError
from ..csv_export import import_csv_anagrafica

if TYPE_CHECKING:
    from ..repository import JsonRepository


class TabAnagrafica(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, repo: "JsonRepository",
                 theme: dict, on_change=None, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self.theme = theme
        self._on_change = on_change
        self._build()

    def _notify_change(self) -> None:
        if self._on_change:
            self._on_change()

    def _build(self) -> None:
        pad = {"padx": 6, "pady": 6}

        # Riga: aggiungi fratello
        fr_frame = ttk.Frame(self)
        fr_frame.pack(fill="x", **pad)
        ttk.Label(fr_frame, text="Fratello:").pack(side="left")
        self.entry_bro = ttk.Entry(fr_frame, width=30)
        self.entry_bro.pack(side="left", padx=6)
        ttk.Button(fr_frame, text="Aggiungi Fratello", command=self.add_brother).pack(side="left")

        # Riga: aggiungi famiglia
        fam_frame = ttk.Frame(self)
        fam_frame.pack(fill="x", **pad)
        ttk.Label(fam_frame, text="Famiglia:").pack(side="left")
        self.entry_fam = ttk.Entry(fam_frame, width=30)
        self.entry_fam.pack(side="left", padx=6)
        ttk.Button(fam_frame, text="Aggiungi Famiglia", command=self.add_family).pack(side="left")

        # Riga: associa
        assoc_frame = ttk.Frame(self)
        assoc_frame.pack(fill="x", **pad)
        ttk.Label(assoc_frame, text="Associa:").pack(side="left")
        self.combo_assoc_bro = TypeaheadCombobox(assoc_frame, width=28, state="readonly")
        self.combo_assoc_bro.pack(side="left", padx=4)
        ttk.Label(assoc_frame, text="->").pack(side="left", padx=4)
        self.combo_assoc_fam = TypeaheadCombobox(assoc_frame, width=28, state="readonly")
        self.combo_assoc_fam.pack(side="left", padx=4)
        ttk.Button(assoc_frame, text="Associa", command=self.associate).pack(side="left", padx=6)

        # Riga: frequenza
        freq_frame = ttk.Frame(self)
        freq_frame.pack(fill="x", **pad)
        ttk.Label(freq_frame, text="Frequenza (1/2/4):").pack(side="left")
        self.combo_freq = TypeaheadCombobox(freq_frame, values=[1, 2, 4], width=5, state="readonly")
        self.combo_freq.pack(side="left", padx=4)
        ttk.Label(freq_frame, text="per famiglia:").pack(side="left")
        self.combo_freq_fam = TypeaheadCombobox(freq_frame, width=28, state="readonly")
        self.combo_freq_fam.pack(side="left", padx=4)
        ttk.Button(freq_frame, text="Imposta Frequenza", command=self.set_frequency).pack(side="left", padx=6)

        ttk.Separator(self, orient="horizontal").pack(fill="x", **pad)

        # Capacita'
        cap_frame = ttk.LabelFrame(self, text="Capacita' visite mensili (massimo)")
        cap_frame.pack(fill="x", **pad)
        ttk.Label(cap_frame, text="Fratello:").pack(side="left")
        self.combo_cap_bro = TypeaheadCombobox(cap_frame, width=28, state="readonly")
        self.combo_cap_bro.pack(side="left", padx=4)
        ttk.Label(cap_frame, text="Capacita' (0..50):").pack(side="left", padx=(8, 4))
        self.spin_cap = tk.Spinbox(cap_frame, from_=0, to=50, width=5)
        self.spin_cap.pack(side="left", padx=4)
        ttk.Button(cap_frame, text="Imposta Capacita'", command=self.set_capacity).pack(side="left", padx=8)
        self.combo_cap_bro.bind("<<ComboboxSelected>>", self._on_select_cap_bro)

        ttk.Separator(self, orient="horizontal").pack(fill="x", **pad)

        # Elimina + Import
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **pad)

        ttk.Label(action_frame, text="Elimina Fratello:").pack(side="left")
        self.combo_del_bro = TypeaheadCombobox(action_frame, width=24, state="readonly")
        self.combo_del_bro.pack(side="left", padx=4)
        ttk.Button(action_frame, text="Elimina", command=self.delete_brother).pack(side="left", padx=(4, 12))

        ttk.Label(action_frame, text="Elimina Famiglia:").pack(side="left")
        self.combo_del_fam = TypeaheadCombobox(action_frame, width=24, state="readonly")
        self.combo_del_fam.pack(side="left", padx=4)
        ttk.Button(action_frame, text="Elimina", command=self.delete_family).pack(side="left", padx=(4, 12))

        ttk.Button(action_frame, text="Importa CSV", command=self.import_csv).pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x", **pad)

        # Liste
        lists_frame = ttk.Frame(self)
        lists_frame.pack(fill="both", expand=True, **pad)

        left = ttk.Frame(lists_frame)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Fratelli:").pack(anchor="w")
        self.list_bro = tk.Listbox(left, height=12,
                                    bg=self.theme.get("list_bg", "#fff"),
                                    fg=self.theme.get("list_fg", "#000"),
                                    selectbackground=self.theme.get("list_select_bg", "#0078d4"))
        self.list_bro.pack(fill="both", expand=True, padx=4, pady=4)

        right = ttk.Frame(lists_frame)
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="Famiglie:").pack(anchor="w")
        self.list_fam = tk.Listbox(right, height=12,
                                    bg=self.theme.get("list_bg", "#fff"),
                                    fg=self.theme.get("list_fg", "#000"),
                                    selectbackground=self.theme.get("list_select_bg", "#0078d4"))
        self.list_fam.pack(fill="both", expand=True, padx=4, pady=4)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def add_brother(self) -> None:
        nome = self.entry_bro.get().strip()
        try:
            canonical = self.repo.add_brother(nome)
            self.entry_bro.delete(0, tk.END)
            self.refresh_lists()
            self._notify_change()
            return canonical
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def add_family(self) -> None:
        nome = self.entry_fam.get().strip()
        try:
            canonical = self.repo.add_family(nome)
            self.entry_fam.delete(0, tk.END)
            self.refresh_lists()
            self._notify_change()
            return canonical
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def associate(self) -> None:
        bro = self.combo_assoc_bro.get().strip()
        fam = self.combo_assoc_fam.get().strip()
        if not bro or not fam:
            messagebox.showerror("Errore", "Seleziona sia Fratello sia Famiglia.", parent=self)
            return
        try:
            self.repo.associate(bro, fam)
            self._notify_change()
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def set_frequency(self) -> None:
        fam = self.combo_freq_fam.get().strip()
        val = self.combo_freq.get().strip()
        if not fam or not val:
            messagebox.showerror("Errore", "Seleziona famiglia e frequenza (1/2/4).", parent=self)
            return
        try:
            self.repo.set_frequency(fam, int(val))
            self._notify_change()
        except (ValueError, TurniVisiteError) as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def set_capacity(self) -> None:
        bro = self.combo_cap_bro.get().strip()
        if not bro:
            messagebox.showerror("Errore", "Seleziona un fratello.", parent=self)
            return
        try:
            cap = int(self.spin_cap.get())
            self.repo.set_brother_capacity(bro, cap)
            self.refresh_lists()
            self._notify_change()
        except (ValueError, TurniVisiteError) as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def delete_brother(self) -> None:
        bro = self.combo_del_bro.get().strip()
        if not bro:
            messagebox.showerror("Errore", "Seleziona un fratello da eliminare.", parent=self)
            return
        if messagebox.askyesno("Conferma", f"Eliminare il fratello '{bro}'?", parent=self):
            try:
                self.repo.remove_brother(bro)
                self.refresh_lists()
                self._notify_change()
            except TurniVisiteError as e:
                messagebox.showerror("Errore", str(e), parent=self)

    def delete_family(self) -> None:
        fam = self.combo_del_fam.get().strip()
        if not fam:
            messagebox.showerror("Errore", "Seleziona una famiglia da eliminare.", parent=self)
            return
        if messagebox.askyesno("Conferma", f"Eliminare la famiglia '{fam}'?", parent=self):
            try:
                self.repo.remove_family(fam)
                self.refresh_lists()
                self._notify_change()
            except TurniVisiteError as e:
                messagebox.showerror("Errore", str(e), parent=self)

    def import_csv(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="Importa anagrafica da CSV",
            filetypes=[("CSV", "*.csv"), ("Tutti", "*.*")],
        )
        if not path:
            return
        try:
            result = import_csv_anagrafica(path)
        except Exception as e:
            messagebox.showerror("Errore", f"Errore lettura CSV: {e}", parent=self)
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
        self._notify_change()

        msg = f"Importati: {n_fr} fratelli, {n_fam} famiglie."
        if result["errori"]:
            msg += f"\nErrori CSV: {len(result['errori'])}"
        if errori_import:
            msg += f"\nErrori import: {len(errori_import)}"
            msg += "\n" + "\n".join(errori_import[:5])
        messagebox.showinfo("Import completato", msg, parent=self)

    def _on_select_cap_bro(self, _event=None) -> None:
        bro = self.combo_cap_bro.get().strip()
        if not bro:
            return
        cap_attuale = int(self.repo.capacita.get(bro, 1))
        try:
            self.spin_cap.delete(0, tk.END)
            self.spin_cap.insert(0, str(cap_attuale))
        except Exception:
            pass

    def refresh_lists(self) -> None:
        self.list_bro.delete(0, tk.END)
        for x in sorted(self.repo.fratelli):
            cap = self.repo.capacita.get(x, 1)
            indisp = self.repo.indisponibilita.get(x, [])
            label = f"{x}  (cap={cap})"
            if indisp:
                label += f"  [indisponibile: {', '.join(indisp)}]"
            self.list_bro.insert(tk.END, label)

        self.list_fam.delete(0, tk.END)
        for x in sorted(self.repo.famiglie):
            freq = self.repo.frequenze.get(x, 2)
            n_assoc = len(self.repo.associazioni.get(x, []))
            self.list_fam.insert(tk.END, f"{x}  (freq={freq}, assoc={n_assoc})")

        bros = sorted(self.repo.fratelli)
        fams = sorted(self.repo.famiglie)
        for cb in (self.combo_assoc_bro, self.combo_cap_bro, self.combo_del_bro):
            cb["values"] = bros
        for cb in (self.combo_assoc_fam, self.combo_freq_fam, self.combo_del_fam):
            cb["values"] = fams

        for cb in (self.combo_assoc_bro, self.combo_assoc_fam, self.combo_freq_fam,
                   self.combo_del_bro, self.combo_del_fam, self.combo_cap_bro):
            vals = list(cb.cget("values") or [])
            if cb.get() and cb.get() not in [str(v) for v in vals]:
                cb.set("")
