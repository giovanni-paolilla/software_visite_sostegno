"""Tab Calendario: visualizzazione calendario dei turni storico."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..repository import JsonRepository

# Colori per fratelli (palette)
_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#86bcb6", "#d37295", "#a0cbe8", "#ffbe7d", "#8cd17d",
]


class TabCalendario(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, repo: "JsonRepository",
                 theme: dict, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self.theme = theme
        self._build()

    def _build(self) -> None:
        pad = {"padx": 6, "pady": 6}

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Calendario visite (da storico)").pack(side="left")
        ttk.Button(top, text="Aggiorna", command=self.refresh).pack(side="right")

        # Canvas scrollabile per il calendario
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, **pad)

        self.canvas = tk.Canvas(container,
                                 bg=self.theme.get("bg", "#f0f0f0"),
                                 highlightthickness=0)
        v_scroll = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        h_scroll = ttk.Scrollbar(container, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.inner_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")

        self.canvas.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")

        self.inner_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))

        # Legenda
        self.legend_frame = ttk.Frame(self)
        self.legend_frame.pack(fill="x", **pad)

    def refresh(self) -> None:
        # Pulisci
        for w in self.inner_frame.winfo_children():
            w.destroy()
        for w in self.legend_frame.winfo_children():
            w.destroy()

        storico = self.repo.get_storico_turni()
        if not storico:
            ttk.Label(self.inner_frame, text="Nessun dato nello storico.").pack()
            return

        # Raccogli dati
        mesi = sorted(set(r.get("mese", "") for r in storico if isinstance(r, dict)))
        famiglie = sorted(self.repo.famiglie)

        # Mappa fratello -> colore
        tutti_fratelli = sorted(self.repo.fratelli)
        color_map = {fr: _COLORS[i % len(_COLORS)] for i, fr in enumerate(tutti_fratelli)}

        # Crea griglia: righe = famiglie, colonne = mesi
        # Header mesi
        ttk.Label(self.inner_frame, text="Famiglia", style="CalHeader.TLabel",
                  width=20, anchor="w", relief="solid").grid(row=0, column=0, sticky="nsew")
        for col, mese in enumerate(mesi, 1):
            ttk.Label(self.inner_frame, text=mese, style="CalHeader.TLabel",
                      width=12, anchor="center", relief="solid").grid(row=0, column=col, sticky="nsew")

        # Dati per cella
        per_mese_fam: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for rec in storico:
            if not isinstance(rec, dict):
                continue
            mese = rec.get("mese", "")
            for a in rec.get("assegnazioni", []):
                if isinstance(a, dict):
                    fam = a.get("famiglia", "")
                    fr = a.get("fratello", "")
                    if fam and fr:
                        per_mese_fam[mese][fam].append(fr)

        # Celle
        for row, fam in enumerate(famiglie, 1):
            ttk.Label(self.inner_frame, text=fam, style="Cal.TLabel",
                      width=20, anchor="w", relief="solid").grid(row=row, column=0, sticky="nsew")
            for col, mese in enumerate(mesi, 1):
                fratelli = per_mese_fam[mese].get(fam, [])
                cell_frame = tk.Frame(self.inner_frame, relief="solid", borderwidth=1,
                                       bg=self.theme.get("card_bg", "#fff"))
                cell_frame.grid(row=row, column=col, sticky="nsew")

                for fr in fratelli:
                    color = color_map.get(fr, "#999")
                    lbl = tk.Label(cell_frame, text=fr[:12], font=("Helvetica", 7),
                                    bg=color, fg="white", padx=2, pady=1)
                    lbl.pack(fill="x", padx=1, pady=1)

                if not fratelli:
                    tk.Label(cell_frame, text="-", font=("Helvetica", 7),
                              bg=self.theme.get("card_bg", "#fff"),
                              fg=self.theme.get("muted", "#999")).pack()

        # Legenda
        ttk.Label(self.legend_frame, text="Legenda: ").pack(side="left")
        for fr in tutti_fratelli[:15]:
            color = color_map.get(fr, "#999")
            lbl = tk.Label(self.legend_frame, text=f" {fr} ", font=("Helvetica", 8),
                            bg=color, fg="white", padx=3, pady=1)
            lbl.pack(side="left", padx=2)
