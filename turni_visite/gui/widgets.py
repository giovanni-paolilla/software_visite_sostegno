"""Widget riutilizzabili: TypeaheadCombobox e altri."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class TypeaheadCombobox(ttk.Combobox):
    """
    Combobox con type-ahead: digita un prefisso per filtrare i valori,
    ripeti la stessa lettera per scorrere i match, Backspace cancella,
    Esc azzera il buffer.
    """

    def __init__(self, master=None, open_dropdown_on_match: bool = True,
                 reset_ms: int = 800, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._ta_prefix: str = ""
        self._ta_idx: int = 0
        self._ta_after_id: str | None = None
        self._ta_last_values_hash: int | None = None
        self._ta_open_dropdown = open_dropdown_on_match
        self._ta_reset_ms = reset_ms
        self.bind("<KeyPress>", self._on_key, add="+")
        self.bind("<FocusOut>", lambda _e: self._reset_buffer(), add="+")

    def _reset_buffer(self) -> None:
        self._ta_prefix = ""
        self._ta_idx = 0
        self._ta_after_id = None

    def _start_reset_timer(self) -> None:
        if self._ta_after_id is not None:
            try:
                self.after_cancel(self._ta_after_id)
            except Exception:
                pass
        self._ta_after_id = self.after(self._ta_reset_ms, self._reset_buffer)

    def _values_list(self) -> list[str]:
        try:
            return [str(v) for v in list(self.cget("values"))]
        except Exception:
            return []

    def _matches(self, prefix: str) -> list[str]:
        pref = prefix.lower()
        return [v for v in self._values_list() if v.lower().startswith(pref)]

    def _open_dropdown(self) -> None:
        if not self._ta_open_dropdown:
            return
        try:
            self.tk.call(self._w, "post")
            return
        except Exception:
            pass
        self.event_generate("<Down>")

    def _select_current(self, prefix: str, idx: int) -> bool:
        matches = self._matches(prefix)
        if not matches:
            return False
        self._ta_idx = idx % len(matches)
        self._ta_prefix = prefix
        self.set(matches[self._ta_idx])
        self._open_dropdown()
        return True

    def _on_key(self, event) -> str | None:
        fg = self.focus_get()
        if not fg or not str(fg).startswith(str(self)):
            return None

        new_hash = hash(tuple(self._values_list()))
        if new_hash != self._ta_last_values_hash:
            self._ta_last_values_hash = new_hash
            self._reset_buffer()

        if event.keysym == "BackSpace":
            if self._ta_prefix:
                self._ta_prefix = self._ta_prefix[:-1]
                self._ta_idx = 0
                if self._ta_prefix:
                    self._select_current(self._ta_prefix, 0)
                self._start_reset_timer()
            return "break"

        if event.keysym in ("Escape", "Cancel"):
            self._reset_buffer()
            return "break"

        ch = event.char
        if ch and len(ch) == 1 and (ch.isalnum() or ch in " .'-"):
            if len(self._ta_prefix) == 1 and self._ta_prefix.lower() == ch.lower():
                matches = self._matches(self._ta_prefix)
                if matches:
                    self._ta_idx = (self._ta_idx + 1) % len(matches)
                    self.set(matches[self._ta_idx])
                    self._open_dropdown()
                    self._start_reset_timer()
                    return "break"
            new_prefix = self._ta_prefix + ch
            if self._select_current(new_prefix, 0):
                self._start_reset_timer()
                return "break"
            if self._select_current(ch, 0):
                self._start_reset_timer()
                return "break"
            self._start_reset_timer()
            return "break"

        return None
