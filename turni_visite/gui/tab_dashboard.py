"""Tab Dashboard: panoramica KPI e stato del sistema."""
from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING

from .themes import get_colors
from ..i18n import t

if TYPE_CHECKING:
    from ..repository import JsonRepository


class TabDashboard(ctk.CTkFrame):
    def __init__(self, parent, repo: "JsonRepository", **kw) -> None:
        super().__init__(parent, **kw)
        self.repo = repo
        self._build()
        self.refresh()

    def _build(self) -> None:
        # Titolo
        ctk.CTkLabel(self, text=t("dashboard.titolo"), font=ctk.CTkFont(size=20, weight="bold")).pack(
            anchor="w", padx=16, pady=(12, 4))

        # Griglia KPI
        kpi_frame = ctk.CTkFrame(self, fg_color="transparent")
        kpi_frame.pack(fill="x", padx=16, pady=8)

        self.kpi_cards: dict[str, tuple[ctk.CTkLabel, ctk.CTkLabel]] = {}
        kpi_defs = [
            ("n_fratelli_attivi", t("dashboard.fratelli_attivi")),
            ("n_famiglie", t("dashboard.famiglie")),
            ("capacita_totale", t("dashboard.capacita_totale")),
            ("domanda_totale", t("dashboard.domanda_mensile")),
            ("bilancio", t("dashboard.bilancio")),
            ("n_mesi_storico", t("dashboard.mesi_storico")),
        ]
        for col, (key, label) in enumerate(kpi_defs):
            card = ctk.CTkFrame(kpi_frame, corner_radius=10)
            card.grid(row=0, column=col, padx=6, pady=6, sticky="nsew")
            kpi_frame.columnconfigure(col, weight=1)

            val_lbl = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=24, weight="bold"))
            val_lbl.pack(pady=(12, 2))
            title_lbl = ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=11),
                                      text_color=("gray40", "gray60"))
            title_lbl.pack(pady=(0, 10))
            self.kpi_cards[key] = (val_lbl, title_lbl)

        # Avvisi
        avvisi_label = ctk.CTkLabel(self, text=t("dashboard.avvisi"),
                                     font=ctk.CTkFont(size=14, weight="bold"))
        avvisi_label.pack(anchor="w", padx=16, pady=(12, 4))

        self.txt_avvisi = ctk.CTkTextbox(self, height=180, corner_radius=8)
        self.txt_avvisi.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.txt_avvisi.configure(state="disabled")

        # Footer
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=(0, 12))
        self.lbl_ultimo_mese = ctk.CTkLabel(bottom, text="")
        self.lbl_ultimo_mese.pack(side="left")
        ctk.CTkButton(bottom, text=t("aggiorna"), width=100, command=self.refresh).pack(side="right")

    def refresh(self) -> None:
        kpi = self.repo.get_dashboard_kpi()
        colors = get_colors()

        for key, (val_lbl, _) in self.kpi_cards.items():
            val = kpi.get(key, 0)
            val_lbl.configure(text=str(val))

        # Colora il bilancio
        bilancio = kpi.get("bilancio", 0)
        bil_lbl = self.kpi_cards["bilancio"][0]
        if bilancio < 0:
            bil_lbl.configure(text_color=colors["danger"])
        elif bilancio == 0:
            bil_lbl.configure(text_color=colors["warning"])
        else:
            bil_lbl.configure(text_color=colors["success"])

        # Ultimo mese
        ultimo = kpi.get("ultimo_mese_storico")
        self.lbl_ultimo_mese.configure(
            text=f"{t('dashboard.ultimo_mese')}: {ultimo}" if ultimo else t("dashboard.nessun_mese")
        )

        # Avvisi
        avvisi: list[str] = []
        if kpi["famiglie_senza_associazione"]:
            avvisi.append(
                f"{t('famiglie_senza_fratelli')}: "
                f"{', '.join(kpi['famiglie_senza_associazione'])}"
            )
        if kpi["fratelli_senza_associazione"]:
            avvisi.append(
                f"{t('fratelli_non_associati')}: "
                f"{', '.join(kpi['fratelli_senza_associazione'])}"
            )
        if bilancio < 0:
            avvisi.append(
                f"ATTENZIONE: capacita' ({kpi['capacita_totale']}) < "
                f"domanda ({kpi['domanda_totale']}). Aumenta capacita' o riduci frequenze."
            )
        if kpi.get("n_indisponibilita", 0) > 0:
            avvisi.append(f"{kpi['n_indisponibilita']} indisponibilita' registrate.")
        if kpi.get("n_vincoli", 0) > 0:
            avvisi.append(f"{kpi['n_vincoli']} vincolo/i personalizzato/i attivi.")
        if not avvisi:
            avvisi.append(t("dashboard.tutto_ok"))

        self.txt_avvisi.configure(state="normal")
        self.txt_avvisi.delete("1.0", "end")
        for a in avvisi:
            self.txt_avvisi.insert("end", f"  {a}\n\n")
        self.txt_avvisi.configure(state="disabled")
