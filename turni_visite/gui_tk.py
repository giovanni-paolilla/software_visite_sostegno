"""
Interfaccia grafica Tkinter per il programma Turni Visite.

Richiede: Python 3.10+, ortools, reportlab, Tkinter.
Su Linux installare python3-tk se non incluso nella distribuzione.

Architettura: ogni tab e' un modulo separato in turni_visite/gui/.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .config import DATA_FILE
from .logging_cfg import setup_logging
from .repository import JsonRepository
from .gui.themes import apply_theme, get_theme
from .gui.tab_dashboard import TabDashboard
from .gui.tab_anagrafica import TabAnagrafica
from .gui.tab_pianificazione import TabPianificazione
from .gui.tab_storico import TabStorico
from .gui.tab_calendario import TabCalendario
from .gui.tab_avanzate import TabAvanzate


class TurniVisiteApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Turni Visite v0.2.0")
        self.geometry("1120x750")

        self.repo = JsonRepository(DATA_FILE)
        self._dark_mode = False
        self._theme = get_theme(dark=False)

        # Applica tema
        apply_theme(self, self._theme)

        # Menu barra
        self._build_menu()

        # Notebook principale
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab
        self.tab_dashboard = TabDashboard(self.notebook, self.repo, self._theme)
        self.notebook.add(self.tab_dashboard, text="Dashboard")

        self.tab_anagrafica = TabAnagrafica(
            self.notebook, self.repo, self._theme,
            on_change=self._on_data_change,
        )
        self.notebook.add(self.tab_anagrafica, text="Anagrafica")

        self.tab_pianifica = TabPianificazione(
            self.notebook, self.repo, self._theme,
            set_status=self.set_status,
            on_storico_change=self._on_storico_change,
        )
        self.notebook.add(self.tab_pianifica, text="Pianificazione")

        self.tab_storico = TabStorico(
            self.notebook, self.repo, self._theme,
            set_status=self.set_status,
        )
        self.notebook.add(self.tab_storico, text="Storico")

        self.tab_calendario = TabCalendario(self.notebook, self.repo, self._theme)
        self.notebook.add(self.tab_calendario, text="Calendario")

        self.tab_avanzate = TabAvanzate(
            self.notebook, self.repo, self._theme,
            set_status=self.set_status,
            on_change=self._on_data_change,
        )
        self.notebook.add(self.tab_avanzate, text="Avanzate")

        # Status bar
        self.status_var = tk.StringVar(value="Pronto")
        status_bar = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status_bar.pack(fill="x", side="bottom", padx=8, pady=(0, 6))

        # Binding per refresh al cambio tab
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Refresh iniziale
        self.tab_anagrafica.refresh_lists()

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # Menu Vista
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Vista", menu=view_menu)
        view_menu.add_command(label="Tema chiaro", command=lambda: self._set_theme(False))
        view_menu.add_command(label="Tema scuro", command=lambda: self._set_theme(True))
        view_menu.add_separator()
        view_menu.add_command(label="Stampa (Ctrl+P)", command=self._print_dialog)

        # Menu Aiuto
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Aiuto", menu=help_menu)
        help_menu.add_command(label="Informazioni", command=self._show_about)

        # Shortcut stampa
        self.bind_all("<Control-p>", lambda e: self._print_dialog())

    def _set_theme(self, dark: bool) -> None:
        self._dark_mode = dark
        self._theme = get_theme(dark=dark)
        apply_theme(self, self._theme)
        self.set_status(f"Tema {'scuro' if dark else 'chiaro'} applicato.")

    def _print_dialog(self) -> None:
        """Stampa diretta: genera un PDF temporaneo e lo invia al sistema di stampa."""
        import subprocess
        import platform
        import tempfile

        from .pdf_export import export_pdf_mesi

        # Cerca se c'e' una soluzione recente nel tab pianificazione
        tab_p = self.tab_pianifica
        if not tab_p._last_result or not tab_p._last_result.solution:
            from tkinter import messagebox
            messagebox.showinfo(
                "Stampa",
                "Nessuna soluzione da stampare. Esegui prima l'ottimizzazione.",
                parent=self,
            )
            return

        # Genera PDF temporaneo
        tmp_dir = tempfile.mkdtemp()
        tmp_pdf = f"{tmp_dir}/turni_stampa.pdf"
        try:
            export_pdf_mesi(
                tab_p._last_mesi, tab_p._last_result.solution,
                tab_p._last_snap["frequenze"], tab_p._last_week_windows,
                output_path=tmp_pdf,
            )
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Errore stampa", str(e), parent=self)
            return

        # Invia alla stampante
        system = platform.system()
        try:
            if system == "Linux":
                subprocess.Popen(["lp", tmp_pdf])
            elif system == "Darwin":
                subprocess.Popen(["lp", tmp_pdf])
            elif system == "Windows":
                import os
                os.startfile(tmp_pdf, "print")
            self.set_status("Documento inviato alla stampante.")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Errore stampa", f"Impossibile stampare: {e}", parent=self)

    def _show_about(self) -> None:
        from tkinter import messagebox
        messagebox.showinfo(
            "Turni Visite",
            "Turni Visite v0.2.0\n\n"
            "Programma per l'assegnazione dei turni di visite di sostegno.\n"
            "Congregazione Messina-Ganzirri\n\n"
            "Tecnologie: Python, OR-Tools, ReportLab, Tkinter",
            parent=self,
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_tab_changed(self, _event=None) -> None:
        idx = self.notebook.index(self.notebook.select())
        if idx == 0:  # Dashboard
            self.tab_dashboard.refresh()
        elif idx == 3:  # Storico
            self.tab_storico.refresh()
        elif idx == 4:  # Calendario
            self.tab_calendario.refresh()
        elif idx == 5:  # Avanzate
            self.tab_avanzate.refresh_all()

    def _on_data_change(self) -> None:
        """Callback globale quando i dati cambiano (anagrafica, backup restore, ecc)."""
        self.tab_anagrafica.refresh_lists()
        self.tab_dashboard.refresh()

    def _on_storico_change(self) -> None:
        self.tab_storico.refresh()
        self.tab_dashboard.refresh()

    def set_status(self, msg: str) -> None:
        self.status_var.set(msg)


def main() -> None:
    setup_logging()
    app = TurniVisiteApp()
    app.mainloop()


if __name__ == "__main__":
    main()
