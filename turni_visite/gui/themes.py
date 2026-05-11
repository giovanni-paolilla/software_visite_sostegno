"""Gestione temi per CustomTkinter — wrapper semplice."""
from __future__ import annotations

import customtkinter as ctk

# Colori accessori (per widget custom non gestiti da CTk)
COLORS = {
    "light": {
        "success": "#107c10",
        "warning": "#ca5010",
        "danger": "#d13438",
        "muted": "#666666",
        "accent": "#0078d4",
        "cal_bg": "#ffffff",
        "cal_fg": "#1a1a1a",
        "cal_header": "#e0e0e0",
    },
    "dark": {
        "success": "#6a9955",
        "warning": "#ce9178",
        "danger": "#f44747",
        "muted": "#808080",
        "accent": "#569cd6",
        "cal_bg": "#2b2b2b",
        "cal_fg": "#d4d4d4",
        "cal_header": "#333333",
    },
}

# Colori centralizzati per pulsanti con semantica (tuple light/dark per CTk)
BUTTON_COLORS = {
    "danger": ("#d13438", "#c50f1f"),
    "danger_hover": ("#a4262c", "#8b0000"),
    "success": ("#107c10", "#0b5e0b"),
    "success_hover": ("#0b5e0b", "#084c08"),
}


def set_appearance(mode: str = "System") -> None:
    """Imposta il tema: 'Light', 'Dark' o 'System'."""
    ctk.set_appearance_mode(mode)


def set_color_theme(theme: str = "blue") -> None:
    """Imposta il tema colore: 'blue', 'green', 'dark-blue'."""
    ctk.set_default_color_theme(theme)


def get_colors() -> dict:
    """Ritorna i colori accessori in base al tema corrente (risolve anche 'System')."""
    mode = ctk.get_appearance_mode().lower()
    # ctk.get_appearance_mode() può restituire 'System' se il tema non è ancora risolto:
    # in quel caso fallback a 'light'.
    if mode == "system":
        mode = ctk.get_appearance_mode().lower()
        if mode not in ("dark", "light"):
            mode = "light"
    return COLORS.get(mode, COLORS["light"])
