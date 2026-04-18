"""Tab Calendario: visualizzazione calendario dei turni storico."""
from __future__ import annotations

import tkinter as tk
import customtkinter as ctk
from collections import defaultdict
from typing import TYPE_CHECKING

from .themes import get_colors

if TYPE_CHECKING:
    from ..repository import JsonRepository

_PALETTE = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#86bcb6", "#d37295", "#a0cbe8", "#ffbe7d", "#8cd17d",
]


class TabCalendario(ctk.CTkFrame):
    def __init__(self, parent, repo: "JsonRepository", **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self._build()

    def _build(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(top, text="Calendario visite (da storico)",
                      font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Aggiorna", width=100, command=self.refresh).pack(side="right")

        # Scrollable area per il calendario
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=4)

        # Legenda
        self.legend_frame = ctk.CTkFrame(self, fg_color="transparent", height=40)
        self.legend_frame.pack(fill="x", padx=10, pady=(0, 8))

    def refresh(self) -> None:
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        for w in self.legend_frame.winfo_children():
            w.destroy()

        storico = self.repo.get_storico_turni()
        if not storico:
            ctk.CTkLabel(self.scroll_frame, text="Nessun dato nello storico.",
                          text_color="gray50").pack(pady=20)
            return

        colors = get_colors()
        mesi = sorted(set(r.get("mese", "") for r in storico if isinstance(r, dict)))
        famiglie = sorted(self.repo.famiglie)
        tutti_fratelli = sorted(self.repo.fratelli)
        color_map = {fr: _PALETTE[i % len(_PALETTE)] for i, fr in enumerate(tutti_fratelli)}

        # Header mesi
        header = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(header, text="Famiglia", width=160, anchor="w",
                      font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=2)
        for col, mese in enumerate(mesi, 1):
            ctk.CTkLabel(header, text=mese, width=120, anchor="center",
                          font=ctk.CTkFont(weight="bold")).grid(row=0, column=col, padx=2)

        # Dati
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

        # Righe
        for row_idx, fam in enumerate(famiglie):
            row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=1)

            ctk.CTkLabel(row_frame, text=fam, width=160, anchor="w",
                          font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=2, sticky="w")

            for col, mese in enumerate(mesi, 1):
                cell = ctk.CTkFrame(row_frame, width=120, height=36, corner_radius=6)
                cell.grid(row=0, column=col, padx=2, pady=1, sticky="nsew")
                cell.grid_propagate(False)

                fratelli = per_mese_fam[mese].get(fam, [])
                if fratelli:
                    names = ", ".join(fr[:10] for fr in fratelli)
                    color = color_map.get(fratelli[0], "#999")
                    lbl = ctk.CTkLabel(cell, text=names, font=ctk.CTkFont(size=10),
                                        text_color="white", fg_color=color,
                                        corner_radius=4, height=28)
                    lbl.pack(fill="both", expand=True, padx=2, pady=2)
                else:
                    ctk.CTkLabel(cell, text="-", text_color="gray50",
                                  font=ctk.CTkFont(size=10)).pack(expand=True)

        # Legenda
        ctk.CTkLabel(self.legend_frame, text="Legenda:",
                      font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=4)
        for fr in tutti_fratelli[:15]:
            color = color_map.get(fr, "#999")
            lbl = ctk.CTkLabel(self.legend_frame, text=f" {fr} ",
                                font=ctk.CTkFont(size=10), text_color="white",
                                fg_color=color, corner_radius=4, height=24)
            lbl.pack(side="left", padx=2)
