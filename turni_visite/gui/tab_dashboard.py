"""Tab Dashboard: panoramica KPI e stato del sistema."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..repository import JsonRepository


class TabDashboard(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, repo: "JsonRepository", theme: dict, **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self.theme = theme
        self._build()
        self.refresh()

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 6}

        # Titolo
        ttk.Label(self, text="Dashboard", font=("Helvetica", 16, "bold")).pack(anchor="w", **pad)
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10)

        # Griglia KPI
        kpi_frame = ttk.Frame(self)
        kpi_frame.pack(fill="x", **pad)

        self.kpi_labels: dict[str, tuple[ttk.Label, ttk.Label]] = {}
        kpi_defs = [
            ("n_fratelli_attivi", "Fratelli attivi"),
            ("n_famiglie", "Famiglie"),
            ("capacita_totale", "Capacita' totale"),
            ("domanda_totale", "Domanda mensile"),
            ("bilancio", "Bilancio (cap-dom)"),
            ("n_mesi_storico", "Mesi nello storico"),
        ]
        for col, (key, label) in enumerate(kpi_defs):
            frame = ttk.Frame(kpi_frame, relief="solid", borderwidth=1, padding=10)
            frame.grid(row=0, column=col, padx=6, pady=6, sticky="nsew")
            kpi_frame.columnconfigure(col, weight=1)

            val_lbl = ttk.Label(frame, text="0", style="KPI.TLabel")
            val_lbl.pack()
            title_lbl = ttk.Label(frame, text=label, style="KPITitle.TLabel")
            title_lbl.pack()
            self.kpi_labels[key] = (val_lbl, title_lbl)

        # Avvisi
        avvisi_frame = ttk.LabelFrame(self, text="Avvisi e suggerimenti")
        avvisi_frame.pack(fill="both", expand=True, **pad)
        self.txt_avvisi = tk.Text(avvisi_frame, height=10, wrap="word", state="disabled",
                                  bg=self.theme.get("text_bg", "#fff"),
                                  fg=self.theme.get("text_fg", "#000"))
        self.txt_avvisi.pack(fill="both", expand=True, padx=4, pady=4)

        # Ultimo mese storico
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", **pad)
        self.lbl_ultimo_mese = ttk.Label(bottom, text="")
        self.lbl_ultimo_mese.pack(side="left")
        ttk.Button(bottom, text="Aggiorna", command=self.refresh).pack(side="right")

    def refresh(self) -> None:
        kpi = self.repo.get_dashboard_kpi()

        for key, (val_lbl, _) in self.kpi_labels.items():
            val = kpi.get(key, 0)
            val_lbl.configure(text=str(val))

        # Colora il bilancio
        bilancio = kpi.get("bilancio", 0)
        bil_lbl = self.kpi_labels["bilancio"][0]
        if bilancio < 0:
            bil_lbl.configure(foreground=self.theme.get("danger", "red"))
        elif bilancio == 0:
            bil_lbl.configure(foreground=self.theme.get("warning", "orange"))
        else:
            bil_lbl.configure(foreground=self.theme.get("success", "green"))

        # Ultimo mese
        ultimo = kpi.get("ultimo_mese_storico")
        if ultimo:
            self.lbl_ultimo_mese.configure(text=f"Ultimo mese pianificato: {ultimo}")
        else:
            self.lbl_ultimo_mese.configure(text="Nessun mese nello storico")

        # Avvisi
        avvisi: list[str] = []
        if kpi["famiglie_senza_associazione"]:
            avvisi.append(
                f"Famiglie senza fratelli associati: "
                f"{', '.join(kpi['famiglie_senza_associazione'])}"
            )
        if kpi["fratelli_senza_associazione"]:
            avvisi.append(
                f"Fratelli non associati a nessuna famiglia: "
                f"{', '.join(kpi['fratelli_senza_associazione'])}"
            )
        if bilancio < 0:
            avvisi.append(
                f"ATTENZIONE: la capacita' totale ({kpi['capacita_totale']}) e' inferiore "
                f"alla domanda mensile ({kpi['domanda_totale']}). "
                f"Aumenta la capacita' dei fratelli o riduci le frequenze."
            )
        if kpi.get("n_indisponibilita", 0) > 0:
            avvisi.append(f"{kpi['n_indisponibilita']} indisponibilita' temporanea/e registrate.")
        if kpi.get("n_vincoli", 0) > 0:
            avvisi.append(f"{kpi['n_vincoli']} vincolo/i personalizzato/i attivi.")

        if not avvisi:
            avvisi.append("Tutto in ordine. Il sistema e' pronto per l'ottimizzazione.")

        self.txt_avvisi.configure(state="normal")
        self.txt_avvisi.delete("1.0", tk.END)
        for a in avvisi:
            self.txt_avvisi.insert(tk.END, f"  {a}\n\n")
        self.txt_avvisi.configure(state="disabled")
