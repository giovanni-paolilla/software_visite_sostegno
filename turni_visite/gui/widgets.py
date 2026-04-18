"""Widget riutilizzabili per CustomTkinter."""
from __future__ import annotations

import tkinter as tk
import customtkinter as ctk


class CTkListbox(ctk.CTkScrollableFrame):
    """
    Listbox custom basata su CTkScrollableFrame con CTkButton per ogni riga.
    Supporta selezione singola, insert, delete, get, curselection.
    """

    def __init__(self, master=None, height: int = 200, width: int = 300,
                 command=None, **kwargs) -> None:
        super().__init__(master, height=height, width=width, **kwargs)
        self._items: list[str] = []
        self._buttons: list[ctk.CTkButton] = []
        self._selected: int | None = None
        self._command = command
        self._normal_color = "transparent"
        self._selected_color = ("gray70", "gray30")

    def insert(self, index: int | str, text: str) -> None:
        if index == tk.END or index == "end":
            idx = len(self._items)
        else:
            idx = int(index)
        self._items.insert(idx, text)
        self._rebuild()

    def delete(self, first: int | str, last: int | str | None = None) -> None:
        if first == 0 and last == tk.END:
            self._items.clear()
            self._selected = None
            self._rebuild()
            return
        start = int(first)
        end = int(last) + 1 if last is not None else start + 1
        del self._items[start:end]
        self._selected = None
        self._rebuild()

    def get(self, index: int) -> str:
        return self._items[index]

    def curselection(self) -> tuple[int, ...]:
        if self._selected is not None:
            return (self._selected,)
        return ()

    def size(self) -> int:
        return len(self._items)

    def _rebuild(self) -> None:
        for btn in self._buttons:
            btn.destroy()
        self._buttons.clear()
        for i, text in enumerate(self._items):
            btn = ctk.CTkButton(
                self, text=text, anchor="w",
                fg_color=self._selected_color if i == self._selected else self._normal_color,
                text_color=("gray10", "gray90"),
                hover_color=("gray80", "gray25"),
                height=28, corner_radius=4,
                command=lambda idx=i: self._on_click(idx),
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._buttons.append(btn)

    def _on_click(self, index: int) -> None:
        self._selected = index
        for i, btn in enumerate(self._buttons):
            btn.configure(
                fg_color=self._selected_color if i == index else self._normal_color,
            )
        if self._command:
            self._command()
        self.event_generate("<<ListboxSelect>>")


class FilterableComboBox(ctk.CTkComboBox):
    """
    ComboBox con ricerca per prefisso: digitando si filtrano i valori
    e si cicla tra i match ripetendo la stessa lettera.
    """

    def __init__(self, master=None, reset_ms: int = 800, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._all_values: list[str] = list(kwargs.get("values", []))
        self._prefix: str = ""
        self._prefix_idx: int = 0
        self._after_id: str | None = None
        self._reset_ms = reset_ms
        # Bind keyboard — CTkComboBox espone _entry internamente
        try:
            entry = self._entry
        except AttributeError:
            entry = self
        entry.bind("<KeyPress>", self._on_key, add="+")
        entry.bind("<FocusOut>", lambda _e: self._reset(), add="+")

    def configure(self, **kwargs) -> None:
        if "values" in kwargs:
            self._all_values = list(kwargs["values"])
        super().configure(**kwargs)

    def _reset(self) -> None:
        self._prefix = ""
        self._prefix_idx = 0
        self._after_id = None

    def _start_timer(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.after(self._reset_ms, self._reset)

    def _matches(self, prefix: str) -> list[str]:
        p = prefix.lower()
        return [v for v in self._all_values if v.lower().startswith(p)]

    def _on_key(self, event) -> str | None:
        if event.keysym == "BackSpace":
            if self._prefix:
                self._prefix = self._prefix[:-1]
                self._prefix_idx = 0
                if self._prefix:
                    m = self._matches(self._prefix)
                    if m:
                        self.set(m[0])
                self._start_timer()
            return None

        if event.keysym in ("Escape", "Cancel"):
            self._reset()
            return None

        ch = event.char
        if not ch or len(ch) != 1 or not (ch.isalnum() or ch in " .'-"):
            return None

        # Stessa lettera ripetuta: cicla tra match
        if len(self._prefix) == 1 and self._prefix.lower() == ch.lower():
            m = self._matches(self._prefix)
            if m:
                self._prefix_idx = (self._prefix_idx + 1) % len(m)
                self.set(m[self._prefix_idx])
                self._start_timer()
                return "break"

        new_prefix = self._prefix + ch
        m = self._matches(new_prefix)
        if m:
            self._prefix = new_prefix
            self._prefix_idx = 0
            self.set(m[0])
            self._start_timer()
            return "break"

        # Fallback: riprova con solo il carattere
        m = self._matches(ch)
        if m:
            self._prefix = ch
            self._prefix_idx = 0
            self.set(m[0])
            self._start_timer()
            return "break"

        self._start_timer()
        return "break"
