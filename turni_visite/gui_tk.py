"""
Interfaccia grafica CustomTkinter per il programma Turni Visite.

Richiede: Python 3.10+, customtkinter, ortools, reportlab.
"""
from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox

from .config import DATA_FILE
from .logging_cfg import setup_logging
from .repository import JsonRepository
from .gui.themes import set_appearance, set_color_theme
from .gui.tab_dashboard import TabDashboard
from .gui.tab_anagrafica import TabAnagrafica
from .gui.tab_pianificazione import TabPianificazione
from .gui.tab_storico import TabStorico
from .gui.tab_calendario import TabCalendario
from .gui.tab_avanzate import TabAvanzate


class TurniVisiteApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        # Configura tema
        set_appearance("System")  # segue il tema del sistema operativo
        set_color_theme("blue")

        self.title("Turni Visite v0.2.0")
        self.geometry("1150x780")
        self.minsize(900, 600)

        self.repo = JsonRepository(DATA_FILE)

        # Tabview principale
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(12, 4))

        # Crea le tab
        self.tabview.add("Dashboard")
        self.tabview.add("Anagrafica")
        self.tabview.add("Pianificazione")
        self.tabview.add("Storico")
        self.tabview.add("Calendario")
        self.tabview.add("Avanzate")

        # Popola le tab con i moduli
        self.tab_dashboard = TabDashboard(self.tabview.tab("Dashboard"), self.repo)
        self.tab_dashboard.pack(fill="both", expand=True)

        self.tab_anagrafica = TabAnagrafica(
            self.tabview.tab("Anagrafica"), self.repo,
            on_change=self._on_data_change,
        )
        self.tab_anagrafica.pack(fill="both", expand=True)

        self.tab_pianifica = TabPianificazione(
            self.tabview.tab("Pianificazione"), self.repo,
            set_status=self.set_status,
            on_storico_change=self._on_storico_change,
        )
        self.tab_pianifica.pack(fill="both", expand=True)

        self.tab_storico = TabStorico(
            self.tabview.tab("Storico"), self.repo,
            set_status=self.set_status,
        )
        self.tab_storico.pack(fill="both", expand=True)

        self.tab_calendario = TabCalendario(
            self.tabview.tab("Calendario"), self.repo,
        )
        self.tab_calendario.pack(fill="both", expand=True)

        self.tab_avanzate = TabAvanzate(
            self.tabview.tab("Avanzate"), self.repo,
            set_status=self.set_status,
            on_change=self._on_data_change,
        )
        self.tab_avanzate.pack(fill="both", expand=True)

        # Barra inferiore: status + tema
        bottom = ctk.CTkFrame(self, fg_color="transparent", height=36)
        bottom.pack(fill="x", padx=12, pady=(0, 8))

        self.status_var = ctk.StringVar(value="Pronto")
        ctk.CTkLabel(bottom, textvariable=self.status_var, anchor="w").pack(side="left")

        # Switch tema
        self._dark_mode = ctk.StringVar(value="System")
        ctk.CTkLabel(bottom, text="Tema:").pack(side="right", padx=(8, 4))
        theme_menu = ctk.CTkOptionMenu(
            bottom, values=["Light", "Dark", "System"],
            variable=self._dark_mode, width=100,
            command=self._change_theme,
        )
        theme_menu.pack(side="right")

        # Shortcut stampa
        self.bind_all("<Control-p>", lambda e: self._print())

        # Refresh iniziale
        self.tab_anagrafica.refresh_lists()

        # Binding tab change
        self.tabview.configure(command=self._on_tab_changed)

    def _on_tab_changed(self) -> None:
        current = self.tabview.get()
        if current == "Dashboard":
            self.tab_dashboard.refresh()
        elif current == "Storico":
            self.tab_storico.refresh()
        elif current == "Calendario":
            self.tab_calendario.refresh()
        elif current == "Avanzate":
            self.tab_avanzate.refresh_all()

    def _on_data_change(self) -> None:
        self.tab_anagrafica.refresh_lists()
        self.tab_dashboard.refresh()

    def _on_storico_change(self) -> None:
        self.tab_storico.refresh()
        self.tab_dashboard.refresh()

    def _change_theme(self, mode: str) -> None:
        set_appearance(mode)
        self.set_status(f"Tema: {mode}")

    def _print(self) -> None:
        import subprocess
        import platform
        import tempfile
        from .pdf_export import export_pdf_mesi

        tab_p = self.tab_pianifica
        if not tab_p._last_result or not tab_p._last_result.solution:
            messagebox.showinfo("Stampa", "Nessuna soluzione da stampare.")
            return
        try:
            tmp_fd, tmp_pdf = tempfile.mkstemp(suffix=".pdf", prefix="turni_stampa_")
            import os
            os.close(tmp_fd)
            export_pdf_mesi(
                tab_p._last_mesi, tab_p._last_result.solution,
                tab_p._last_snap["frequenze"], tab_p._last_week_windows,
                output_path=tmp_pdf,
            )
            system = platform.system()
            if system == "Linux":
                subprocess.Popen(["lp", tmp_pdf])
            elif system == "Darwin":
                subprocess.Popen(["lp", tmp_pdf])
            elif system == "Windows":
                os.startfile(tmp_pdf, "print")  # type: ignore[attr-defined]
            self.set_status("Documento inviato alla stampante.")
        except Exception as e:
            messagebox.showerror("Errore stampa", str(e))

    def set_status(self, msg: str) -> None:
        self.status_var.set(msg)


def main() -> None:
    setup_logging()
    app = TurniVisiteApp()
    app.mainloop()


if __name__ == "__main__":
    main()
