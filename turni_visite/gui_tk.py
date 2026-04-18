"""
Interfaccia grafica Tkinter per il programma Turni Visite.

Richiede: Python 3.10+, ortools, reportlab, Tkinter.
Su Linux installare python3-tk se non incluso nella distribuzione.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from .config import DATA_FILE
from .domain import TurniVisiteError, StoricoConflittoError
from .logging_cfg import setup_logging
from .pdf_export import export_pdf_mesi
from .repository import JsonRepository
from .scheduling import validate_month_yyyy_mm
from .service import conferma_e_salva_turni, diagnosi_infeasible, esegui_ottimizzazione
from .weeks import parse_settimane_lista, slot_label_with_month


# ---------------------------------------------------------------------------
# Utilita' di validazione settimane
# ---------------------------------------------------------------------------

def validate_week_ranges(text: str | None, attese: int) -> tuple[bool, list[str] | str]:
    """
    Valida una stringa tipo '01-07, 15-21' per 'attese' intervalli.
    Ritorna (True, ['01-07', '15-21']) oppure (False, 'messaggio errore').
    """
    if text is None:
        return False, "Operazione annullata."
    raw = text.strip()
    if not raw:
        return False, "Campo vuoto."
    result, err = parse_settimane_lista(raw, attese)
    if result is not None:
        return True, result
    return False, err


def ask_week_windows_for_months(
    root: tk.Tk,
    mesi: list[str],
    frequenze: dict,
    famiglie: set,
) -> dict | None:
    """
    Per ogni mese e frequenza presente (1/2/4) chiede le settimane via dialog.
    Ritorna week_windows o None se l'utente annulla.
    """
    defaults = {1: "08-14", 2: "01-07, 15-21", 4: "01-07, 08-14, 15-21, 22-28"}
    week_windows: dict = {}
    freqs_presenti = sorted(
        {freq for f in famiglie if (freq := frequenze.get(f, 2)) in (1, 2, 4)}
    )

    for mese in mesi:
        week_windows[mese] = {}
        for freq in freqs_presenti:
            fam_con_freq = [f for f in famiglie if frequenze.get(f, 2) == freq]
            if not fam_con_freq:
                continue
            while True:
                msg = (
                    f"Inserisci gli intervalli settimanali per famiglie con frequenza {freq} "
                    f"(mese {mese}).\nFormato: gg-gg separati da virgola\n"
                    f"Esempio: {defaults[freq]}\n\nAttesi {freq} intervalli."
                )
                s = simpledialog.askstring(
                    f"Settimane per {mese} (frequenza {freq})",
                    msg,
                    parent=root,
                    initialvalue=defaults[freq],
                )
                if s is None:
                    return None
                ok, res = validate_week_ranges(s, freq)
                if ok:
                    week_windows[mese][freq] = res
                    break
                messagebox.showerror("Errore di validazione", res, parent=root)

    return week_windows


# ---------------------------------------------------------------------------
# Type-ahead per Combobox
# ---------------------------------------------------------------------------

def bind_typeahead(
    cb: ttk.Combobox,
    open_dropdown_on_match: bool = True,
    reset_ms: int = 800,
) -> None:
    """
    Aggiunge type-ahead (prefisso multiplo + ciclo) a una Combobox.
    - Buffer di prefisso con reset automatico dopo reset_ms.
    - Ripetendo la stessa lettera scorre ciclicamente i match.
    """
    cb._ta_prefix = ""
    cb._ta_idx = 0
    cb._ta_after_id = None
    cb._ta_last_values_hash = None

    def _values_list() -> list[str]:
        try:
            return [str(v) for v in list(cb.cget("values"))]
        except Exception:
            return []

    def _matches(prefix: str) -> list[str]:
        pref = prefix.lower()
        return [v for v in _values_list() if v.lower().startswith(pref)]

    def _reset_buffer() -> None:
        cb._ta_prefix = ""
        cb._ta_idx = 0
        cb._ta_after_id = None

    def _start_reset_timer() -> None:
        if cb._ta_after_id is not None:
            try:
                cb.after_cancel(cb._ta_after_id)
            except Exception:
                pass
        cb._ta_after_id = cb.after(reset_ms, _reset_buffer)

    def _open_dropdown() -> None:
        if not open_dropdown_on_match:
            return
        try:
            cb.tk.call(cb._w, "post")
            return
        except Exception:
            pass
        cb.event_generate("<Down>")

    def _select_current(prefix: str, idx: int) -> bool:
        matches = _matches(prefix)
        if not matches:
            return False
        cb._ta_idx = idx % len(matches)
        cb._ta_prefix = prefix
        cb.set(matches[cb._ta_idx])
        _open_dropdown()
        return True

    def _on_key(event) -> str | None:
        fg = cb.focus_get()
        if not fg or not str(fg).startswith(str(cb)):
            return None

        new_hash = hash(tuple(_values_list()))
        if new_hash != cb._ta_last_values_hash:
            cb._ta_last_values_hash = new_hash
            _reset_buffer()

        if event.keysym == "BackSpace":
            if cb._ta_prefix:
                cb._ta_prefix = cb._ta_prefix[:-1]
                cb._ta_idx = 0
                if cb._ta_prefix:
                    _select_current(cb._ta_prefix, 0)
                _start_reset_timer()
            return "break"
        if event.keysym in ("Escape", "Cancel"):
            _reset_buffer()
            return "break"

        ch = event.char
        if ch and len(ch) == 1 and (ch.isalnum() or ch in " .'-"):
            if len(cb._ta_prefix) == 1 and cb._ta_prefix.lower() == ch.lower():
                matches = _matches(cb._ta_prefix)
                if matches:
                    cb._ta_idx = (cb._ta_idx + 1) % len(matches)
                    cb.set(matches[cb._ta_idx])
                    _open_dropdown()
                    _start_reset_timer()
                    return "break"
            new_prefix = cb._ta_prefix + ch
            if _select_current(new_prefix, 0):
                _start_reset_timer()
                return "break"
            if _select_current(ch, 0):
                _start_reset_timer()
                return "break"
            _start_reset_timer()
            return "break"
        return None

    cb.bind("<KeyPress>", _on_key, add="+")
    cb.bind("<FocusOut>", lambda _e: _reset_buffer(), add="+")


# ---------------------------------------------------------------------------
# Applicazione principale
# ---------------------------------------------------------------------------

class TurniVisiteApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Turni Visite - GUI (Tkinter)")
        self.geometry("1020x680")

        self.repo = JsonRepository(DATA_FILE)

        # Riferimento diretto al pulsante Ottimizza (fix #9)
        self._btn_ottimizza: ttk.Button | None = None

        self.notebook = ttk.Notebook(self)
        self.tab_anagrafica = ttk.Frame(self.notebook)
        self.tab_pianifica = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_anagrafica, text="Anagrafica")
        self.notebook.add(self.tab_pianifica, text="Pianificazione")
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_tab_anagrafica()
        self._build_tab_pianifica()

        self.status_var = tk.StringVar(value="")
        status_bar = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status_bar.pack(fill="x", side="bottom", padx=8, pady=(0, 6))

        self.refresh_lists()

    # ------------------------------------------------------------------
    # TAB: ANAGRAFICA
    # ------------------------------------------------------------------

    def _build_tab_anagrafica(self) -> None:
        pad = {"padx": 6, "pady": 6}

        fr_frame = ttk.Frame(self.tab_anagrafica)
        fr_frame.pack(fill="x", **pad)
        ttk.Label(fr_frame, text="Fratello:").pack(side="left")
        self.entry_bro = ttk.Entry(fr_frame, width=30)
        self.entry_bro.pack(side="left", padx=6)
        ttk.Button(fr_frame, text="Aggiungi Fratello", command=self.add_brother).pack(side="left")

        fam_frame = ttk.Frame(self.tab_anagrafica)
        fam_frame.pack(fill="x", **pad)
        ttk.Label(fam_frame, text="Famiglia:").pack(side="left")
        self.entry_fam = ttk.Entry(fam_frame, width=30)
        self.entry_fam.pack(side="left", padx=6)
        ttk.Button(fam_frame, text="Aggiungi Famiglia", command=self.add_family).pack(side="left")

        assoc_frame = ttk.Frame(self.tab_anagrafica)
        assoc_frame.pack(fill="x", **pad)
        ttk.Label(assoc_frame, text="Associa:").pack(side="left")
        self.combo_assoc_bro = ttk.Combobox(
            assoc_frame, values=sorted(self.repo.fratelli), width=28, state="readonly"
        )
        self.combo_assoc_bro.pack(side="left", padx=4)
        bind_typeahead(self.combo_assoc_bro)
        ttk.Label(assoc_frame, text="→").pack(side="left", padx=4)
        self.combo_assoc_fam = ttk.Combobox(
            assoc_frame, values=sorted(self.repo.famiglie), width=28, state="readonly"
        )
        self.combo_assoc_fam.pack(side="left", padx=4)
        bind_typeahead(self.combo_assoc_fam)
        ttk.Button(assoc_frame, text="Associa", command=self.associate).pack(side="left", padx=6)

        freq_frame = ttk.Frame(self.tab_anagrafica)
        freq_frame.pack(fill="x", **pad)
        ttk.Label(freq_frame, text="Frequenza (1/2/4):").pack(side="left")
        self.combo_freq = ttk.Combobox(freq_frame, values=[1, 2, 4], width=5, state="readonly")
        self.combo_freq.pack(side="left", padx=4)
        bind_typeahead(self.combo_freq)
        ttk.Label(freq_frame, text="per famiglia:").pack(side="left")
        self.combo_freq_fam = ttk.Combobox(
            freq_frame, values=sorted(self.repo.famiglie), width=28, state="readonly"
        )
        self.combo_freq_fam.pack(side="left", padx=4)
        bind_typeahead(self.combo_freq_fam)
        ttk.Button(freq_frame, text="Imposta Frequenza", command=self.set_frequency).pack(
            side="left", padx=6
        )

        ttk.Separator(self.tab_anagrafica, orient="horizontal").pack(fill="x", **pad)

        cap_frame = ttk.LabelFrame(self.tab_anagrafica, text="Capacita' visite mensili (massimo)")
        cap_frame.pack(fill="x", **pad)
        ttk.Label(cap_frame, text="Fratello:").pack(side="left")
        self.combo_cap_bro = ttk.Combobox(
            cap_frame, values=sorted(self.repo.fratelli), width=28, state="readonly"
        )
        self.combo_cap_bro.pack(side="left", padx=4)
        bind_typeahead(self.combo_cap_bro)
        ttk.Label(cap_frame, text="Capacita' (0..50):").pack(side="left", padx=(8, 4))
        self.spin_cap = tk.Spinbox(cap_frame, from_=0, to=50, width=5)
        self.spin_cap.pack(side="left", padx=4)
        ttk.Button(cap_frame, text="Imposta Capacita'", command=self.set_capacity).pack(
            side="left", padx=8
        )
        self.combo_cap_bro.bind("<<ComboboxSelected>>", self.on_select_cap_bro)

        ttk.Separator(self.tab_anagrafica, orient="horizontal").pack(fill="x", **pad)

        del_frame = ttk.Frame(self.tab_anagrafica)
        del_frame.pack(fill="x", **pad)
        ttk.Label(del_frame, text="Elimina Fratello:").pack(side="left")
        self.combo_del_bro = ttk.Combobox(
            del_frame, values=sorted(self.repo.fratelli), width=28, state="readonly"
        )
        self.combo_del_bro.pack(side="left", padx=4)
        bind_typeahead(self.combo_del_bro)
        ttk.Button(del_frame, text="Elimina", command=self.delete_brother).pack(
            side="left", padx=(4, 12)
        )
        ttk.Label(del_frame, text="Elimina Famiglia:").pack(side="left")
        self.combo_del_fam = ttk.Combobox(
            del_frame, values=sorted(self.repo.famiglie), width=28, state="readonly"
        )
        self.combo_del_fam.pack(side="left", padx=4)
        bind_typeahead(self.combo_del_fam)
        ttk.Button(del_frame, text="Elimina", command=self.delete_family).pack(side="left")

        ttk.Separator(self.tab_anagrafica, orient="horizontal").pack(fill="x", **pad)

        lists_frame = ttk.Frame(self.tab_anagrafica)
        lists_frame.pack(fill="both", expand=True, **pad)
        left = ttk.Frame(lists_frame)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Fratelli:").pack(anchor="w")
        self.list_bro = tk.Listbox(left, height=12)
        self.list_bro.pack(fill="both", expand=True, padx=4, pady=4)

        right = ttk.Frame(lists_frame)
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="Famiglie:").pack(anchor="w")
        self.list_fam = tk.Listbox(right, height=12)
        self.list_fam.pack(fill="both", expand=True, padx=4, pady=4)

    # ------------------------------------------------------------------
    # TAB: PIANIFICAZIONE
    # ------------------------------------------------------------------

    def _build_tab_pianifica(self) -> None:
        pad = {"padx": 6, "pady": 6}
        top = ttk.Frame(self.tab_pianifica)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Mesi (YYYY-MM) separati da virgola:").pack(side="left")
        self.entry_mesi = ttk.Entry(top)
        self.entry_mesi.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Label(top, text="Cooldown (mesi):").pack(side="left", padx=(8, 2))
        self.var_cooldown = tk.IntVar(value=int(self.repo.get_setting("cooldown_mesi", 3)))
        ttk.Spinbox(top, from_=1, to=6, textvariable=self.var_cooldown, width=3).pack(side="left")

        # Riferimento diretto → nessun tree-walk fragile in _btn_ottimizza_set_enabled
        self._btn_ottimizza = ttk.Button(
            top, text="Ottimizza & Genera PDF", command=self.optimize_and_export
        )
        self._btn_ottimizza.pack(side="left", padx=(8, 0))

        self.txt_output = ScrolledText(self.tab_pianifica, wrap="word", height=20)
        self.txt_output.pack(fill="both", expand=True, **pad)

    # ------------------------------------------------------------------
    # Handler anagrafica
    # ------------------------------------------------------------------

    def add_brother(self) -> None:
        nome = self.entry_bro.get().strip()
        try:
            canonical = self.repo.add_brother(nome)
            self.entry_bro.delete(0, tk.END)
            self.refresh_lists()
            self.set_status(f"Fratello '{canonical}' aggiunto.")
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def add_family(self) -> None:
        nome = self.entry_fam.get().strip()
        try:
            canonical = self.repo.add_family(nome)
            self.entry_fam.delete(0, tk.END)
            self.refresh_lists()
            self.set_status(f"Famiglia '{canonical}' aggiunta.")
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
            self.set_status(f"Associato '{bro}' -> '{fam}'.")
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def set_frequency(self) -> None:
        fam = self.combo_freq_fam.get().strip()
        val = self.combo_freq.get().strip()
        if not fam or not val:
            messagebox.showerror(
                "Errore", "Seleziona famiglia e frequenza (1/2/4).", parent=self
            )
            return
        try:
            freq = int(val)
            self.repo.set_frequency(fam, freq)
            self.set_status(f"Frequenza {freq}/mese impostata per '{fam}'.")
        except ValueError:
            messagebox.showerror("Errore", "Frequenza non numerica.", parent=self)
        except TurniVisiteError as e:
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
            self.set_status(f"Capacita' {cap}/mese impostata per '{bro}'.")
        except ValueError:
            messagebox.showerror("Errore", "Capacita' non numerica.", parent=self)
        except TurniVisiteError as e:
            messagebox.showerror("Errore", str(e), parent=self)

    def delete_brother(self) -> None:
        bro = self.combo_del_bro.get().strip()
        if not bro:
            messagebox.showerror("Errore", "Seleziona un fratello da eliminare.", parent=self)
            return
        if messagebox.askyesno(
            "Conferma",
            f"Eliminare il fratello '{bro}'?\nSara' rimosso anche da tutte le associazioni.",
            parent=self,
        ):
            try:
                self.repo.remove_brother(bro)
                self.refresh_lists()
                self.set_status(f"Fratello '{bro}' eliminato.")
            except TurniVisiteError as e:
                messagebox.showerror("Errore", str(e), parent=self)

    def delete_family(self) -> None:
        fam = self.combo_del_fam.get().strip()
        if not fam:
            messagebox.showerror("Errore", "Seleziona una famiglia da eliminare.", parent=self)
            return
        if messagebox.askyesno(
            "Conferma",
            f"Eliminare la famiglia '{fam}'?\nSaranno rimosse associazioni e frequenza.",
            parent=self,
        ):
            try:
                self.repo.remove_family(fam)
                self.refresh_lists()
                self.set_status(f"Famiglia '{fam}' eliminata.")
            except TurniVisiteError as e:
                messagebox.showerror("Errore", str(e), parent=self)

    # ------------------------------------------------------------------
    # Ottimizzazione (threaded)
    # ------------------------------------------------------------------

    def optimize_and_export(self) -> None:
        raw = self.entry_mesi.get().strip()
        if not raw:
            messagebox.showerror(
                "Errore",
                "Inserisci almeno un mese (es. 2025-11 o 2025-11, 2025-12).",
                parent=self,
            )
            return
        mesi = [m.strip() for m in raw.split(",") if m.strip()]
        try:
            mesi = [validate_month_yyyy_mm(m) for m in mesi]
            cooldown = int(self.var_cooldown.get() or 3)
            self.repo.set_setting("cooldown_mesi", cooldown)
        except ValueError as e:
            messagebox.showerror("Errore", str(e), parent=self)
            return

        snap = self.repo.data_snapshot()
        week_windows = ask_week_windows_for_months(self, mesi, snap["frequenze"], snap["famiglie"])
        if week_windows is None:
            self.set_status("Operazione annullata.")
            return

        self.set_status("Ottimizzazione in corso (fino a 20s)…")
        self._btn_ottimizza_set_enabled(False)

        def _run() -> None:
            try:
                result = esegui_ottimizzazione(
                    snap=snap,
                    mesi=mesi,
                    storico_turni=self.repo.get_storico_turni(),
                    cooldown=cooldown,
                )
                self.after(0, lambda: self._on_solve_done(result, mesi, snap, cooldown, week_windows))
            except RuntimeError as e:
                err = str(e)
                self.after(
                    0,
                    lambda: (
                        messagebox.showerror("Errore", err, parent=self),
                        self._btn_ottimizza_set_enabled(True),
                        self.set_status("Errore durante l'ottimizzazione."),
                    ),
                )

        threading.Thread(target=_run, daemon=True).start()

    def _btn_ottimizza_set_enabled(self, enabled: bool) -> None:
        """Abilita/disabilita il pulsante Ottimizza tramite riferimento diretto."""
        if self._btn_ottimizza is not None:
            self._btn_ottimizza.configure(state="normal" if enabled else "disabled")

    def _on_solve_done(self, result, mesi, snap, cooldown, week_windows) -> None:
        """Callback eseguito nel main thread al termine del solver."""
        self._btn_ottimizza_set_enabled(True)

        if not result.feasible:
            msg = diagnosi_infeasible(
                snap=snap,
                mesi=mesi,
                storico_turni=self.repo.get_storico_turni(),
                cooldown=cooldown,
            )
            self.txt_output.insert(
                tk.END, "Nessuna soluzione trovata (infeasible).\n\n" + msg + "\n"
            )
            self.txt_output.see(tk.END)
            self.set_status("Nessuna soluzione trovata.")
            return

        # Mostra il piano nell'area di testo
        self.txt_output.delete("1.0", tk.END)
        for mese in mesi:
            blocco = result.solution["by_month"][mese]
            self.txt_output.insert(tk.END, f"\n=== {mese} - Visite per FRATELLO ===\n")
            for fr in sorted(blocco["by_brother"].keys()):
                for fam in (blocco["by_brother"][fr] or []):
                    fr_list = blocco["by_family"][fam]
                    k_found = next(
                        (k for k, name in enumerate(fr_list) if name == fr), None
                    )
                    freq = snap["frequenze"].get(fam, 2)
                    label = (
                        slot_label_with_month(mese, freq, k_found, week_windows)
                        if k_found is not None else ""
                    )
                    self.txt_output.insert(tk.END, f"[{label}] {fr} — {fam}\n")
        self.txt_output.see(tk.END)

        # Chiede conferma con anteprima scrollabile
        preview = self.txt_output.get("1.0", tk.END).strip()
        if not self._confirm_plan_scrollable(preview):
            self.set_status("Operazione annullata. Nessun PDF generato, storico invariato.")
            return

        # Chiede dove salvare il PDF (filedialog)
        nome_file = "turni_" + "-".join(mesi) + ".pdf"
        pdf_path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf"), ("Tutti i file", "*.*")],
            initialfile=nome_file,
            title="Salva PDF turni",
        )
        if not pdf_path:
            self.set_status("PDF non salvato (operazione annullata).")
            return

        try:
            export_pdf_mesi(mesi, result.solution, snap["frequenze"], week_windows, output_path=pdf_path)
        except OSError as e:
            messagebox.showerror("Errore PDF", str(e), parent=self)
            self.set_status("Errore nel salvataggio del PDF.")
            return

        # Salva nello storico
        try:
            salvati = conferma_e_salva_turni(self.repo, mesi, result.solution)
            self.set_status(
                f"PDF creato. Turni salvati: {', '.join(salvati)}."
            )
        except StoricoConflittoError as e:
            messagebox.showwarning("Storico gia' presente", str(e), parent=self)
            self.set_status("PDF creato, ma salvataggio storico NON eseguito (mesi duplicati).")

    def _confirm_plan_scrollable(self, content: str) -> bool:
        """Finestra di conferma con testo scrollabile. Ritorna True se confermato."""
        result: list[bool] = [False]

        top = tk.Toplevel(self)
        top.title("Conferma piano turni")
        top.grab_set()

        txt = ScrolledText(top, wrap="word", width=80, height=24)
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert(tk.END, content)
        txt.configure(state="disabled")

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))

        def _ok() -> None:
            result[0] = True
            top.destroy()

        def _cancel() -> None:
            top.destroy()

        ttk.Button(btn_frame, text="Conferma e salva", command=_ok).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Annulla", command=_cancel).pack(side="right")

        top.wait_window()
        return result[0]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def refresh_lists(self) -> None:
        self.list_bro.delete(0, tk.END)
        for x in sorted(self.repo.fratelli):
            cap = self.repo.capacita.get(x, 1)
            self.list_bro.insert(tk.END, f"{x}  (cap={cap})")

        self.list_fam.delete(0, tk.END)
        for x in sorted(self.repo.famiglie):
            self.list_fam.insert(tk.END, x)

        bros = sorted(self.repo.fratelli)
        fams = sorted(self.repo.famiglie)
        self.combo_assoc_bro["values"] = bros
        self.combo_assoc_fam["values"] = fams
        self.combo_freq_fam["values"] = fams
        self.combo_del_bro["values"] = bros
        self.combo_del_fam["values"] = fams
        self.combo_cap_bro["values"] = bros

        for cb in (
            self.combo_assoc_bro, self.combo_assoc_fam, self.combo_freq_fam,
            self.combo_del_bro, self.combo_del_fam, self.combo_cap_bro,
        ):
            vals = list(cb.cget("values") or [])
            if cb.get() and cb.get() not in vals:
                cb.set("")

    def set_status(self, msg: str) -> None:
        self.status_var.set(msg)

    def on_select_cap_bro(self, _event=None) -> None:
        bro = self.combo_cap_bro.get().strip()
        if not bro:
            return
        cap_attuale = int(self.repo.capacita.get(bro, 1))
        try:
            self.spin_cap.delete(0, tk.END)
            self.spin_cap.insert(0, str(cap_attuale))
        except Exception:
            pass


def main() -> None:
    setup_logging()
    app = TurniVisiteApp()
    app.mainloop()


if __name__ == "__main__":
    main()
