"""
Interfaccia grafica CustomTkinter per il programma Turni Visite.

Richiede: Python 3.10+, customtkinter, ortools, reportlab.
"""
from __future__ import annotations

import sys

try:
    import customtkinter as ctk
except ImportError:
    ctk = None  # type: ignore
from tkinter import messagebox

from .config import DATA_FILE
from .i18n import t, set_language, get_available_languages, get_language
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
    def __init__(self, repo: "JsonRepository") -> None:
        super().__init__()

        # Configura tema
        set_appearance("System")  # segue il tema del sistema operativo
        set_color_theme("blue")

        self.title("Turni Visite v0.3.0")
        self.geometry("1150x780")
        self.minsize(900, 600)

        self.repo = repo

        # Tabview principale
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(12, 4))

        # Crea le tab
        self.tabview.add(t("dashboard.titolo"))
        self.tabview.add(t("anagrafica.titolo"))
        self.tabview.add(t("pianificazione.titolo"))
        self.tabview.add(t("storico.titolo"))
        self.tabview.add(t("calendario.titolo"))
        self.tabview.add(t("avanzate.titolo"))

        # Popola le tab con i moduli
        self.tab_dashboard = TabDashboard(self.tabview.tab(t("dashboard.titolo")), self.repo)
        self.tab_dashboard.pack(fill="both", expand=True)

        self.tab_anagrafica = TabAnagrafica(
            self.tabview.tab(t("anagrafica.titolo")), self.repo,
            on_change=self._on_data_change,
            set_status=self.set_status,
        )
        self.tab_anagrafica.pack(fill="both", expand=True)

        self.tab_pianifica = TabPianificazione(
            self.tabview.tab(t("pianificazione.titolo")), self.repo,
            set_status=self.set_status,
            on_storico_change=self._on_storico_change,
        )
        self.tab_pianifica.pack(fill="both", expand=True)

        self.tab_storico = TabStorico(
            self.tabview.tab(t("storico.titolo")), self.repo,
            set_status=self.set_status,
        )
        self.tab_storico.pack(fill="both", expand=True)

        self.tab_calendario = TabCalendario(
            self.tabview.tab(t("calendario.titolo")), self.repo,
        )
        self.tab_calendario.pack(fill="both", expand=True)

        self.tab_avanzate = TabAvanzate(
            self.tabview.tab(t("avanzate.titolo")), self.repo,
            set_status=self.set_status,
            on_change=self._on_data_change,
            on_invalidate_pianificazione=lambda: self.tab_pianifica.reset_solution(),
        )
        self.tab_avanzate.pack(fill="both", expand=True)

        # Barra inferiore: status + tema
        bottom = ctk.CTkFrame(self, fg_color="transparent", height=36)
        bottom.pack(fill="x", padx=12, pady=(0, 8))

        self.status_var = ctk.StringVar(value=t("pronto"))
        ctk.CTkLabel(bottom, textvariable=self.status_var, anchor="w").pack(side="left")

        # Switch lingua
        ctk.CTkLabel(bottom, text=t("lingua")).pack(side="right", padx=(8, 4))
        lang_menu = ctk.CTkOptionMenu(
            bottom, values=get_available_languages(), width=70,
            command=self._change_language,
        )
        lang_menu.set(get_language())
        lang_menu.pack(side="right")

        # Switch tema
        self._dark_mode = ctk.StringVar(value="System")
        ctk.CTkLabel(bottom, text=t("tema")).pack(side="right", padx=(8, 4))
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

        # Gestione chiusura sicura
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_tab_changed(self) -> None:
        current = self.tabview.get()
        if current == t("dashboard.titolo"):
            self.tab_dashboard.refresh()
        elif current == t("storico.titolo"):
            self.tab_storico.refresh()
        elif current == t("calendario.titolo"):
            self.tab_calendario.refresh()
        elif current == t("avanzate.titolo"):
            self.tab_avanzate.refresh_all()

    def _on_data_change(self) -> None:
        self.tab_anagrafica.refresh_lists()
        self.tab_dashboard.refresh()

    def _on_storico_change(self) -> None:
        self.tab_storico.refresh()
        self.tab_dashboard.refresh()

    def _change_language(self, lang: str) -> None:
        set_language(lang)
        self.repo.set_setting("lingua", lang)
        messagebox.showinfo(t("info"), t("riavvia_per_lingua"))

    def _change_theme(self, mode: str) -> None:
        set_appearance(mode)
        self.set_status(f"{t('tema')} {mode}")

    def _print(self) -> None:
        import threading

        tab_p = self.tab_pianifica
        with tab_p._lock:
            result = tab_p._last_result
            mesi = list(tab_p._last_mesi)
            snap = dict(tab_p._last_snap)
            week_windows = dict(tab_p._last_week_windows)
        if not result or not result.solution:
            messagebox.showinfo(t("stampa"), t("nessuna_soluzione_stampa"))
            return

        solution = result.solution

        def _do_print():
            import subprocess
            import platform
            import tempfile
            import os
            from .pdf_export import export_pdf_mesi

            try:
                tmp_fd, tmp_pdf = tempfile.mkstemp(suffix=".pdf", prefix="turni_stampa_")
                os.close(tmp_fd)
                export_pdf_mesi(
                    mesi, solution,
                    snap["frequenze"], week_windows,
                    output_path=tmp_pdf,
                )
                system = platform.system()
                if system == "Linux":
                    subprocess.Popen(["lp", tmp_pdf])
                    _timer = threading.Timer(60, lambda p=tmp_pdf: os.unlink(p) if os.path.exists(p) else None)
                    _timer.daemon = True
                    _timer.start()
                elif system == "Darwin":
                    subprocess.Popen(["lp", tmp_pdf])
                    _timer = threading.Timer(60, lambda p=tmp_pdf: os.unlink(p) if os.path.exists(p) else None)
                    _timer.daemon = True
                    _timer.start()
                elif system == "Windows":
                    os.startfile(tmp_pdf, "print")  # type: ignore[attr-defined]
                    _timer = threading.Timer(60, lambda p=tmp_pdf: os.unlink(p) if os.path.exists(p) else None)
                    _timer.daemon = True
                    _timer.start()
                self.after(0, lambda: self.set_status(t("documento_inviato")))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(t("errore_stampa"), str(e)))

        threading.Thread(target=_do_print, daemon=True).start()

    def _on_close(self) -> None:
        if hasattr(self, 'tab_pianifica') and hasattr(self.tab_pianifica, '_alive'):
            self.tab_pianifica._alive.clear()
        self.destroy()

    def set_status(self, msg: str) -> None:
        self.status_var.set(msg)


def main() -> None:
    if ctk is None:
        print("customtkinter non installato. Installa con: pip install turni-visite[gui]")
        sys.exit(1)
    setup_logging()
    repo = JsonRepository(DATA_FILE)
    saved_lang = repo.get_setting("lingua", "it")
    if saved_lang in get_available_languages():
        set_language(saved_lang)
    app = TurniVisiteApp(repo)
    app.mainloop()


if __name__ == "__main__":
    main()
