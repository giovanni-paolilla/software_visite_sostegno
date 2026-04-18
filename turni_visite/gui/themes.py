"""Gestione temi chiaro/scuro per Tkinter."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Colori tema chiaro
LIGHT = {
    "bg": "#f0f0f0",
    "fg": "#1a1a1a",
    "accent": "#0078d4",
    "card_bg": "#ffffff",
    "card_border": "#d0d0d0",
    "success": "#107c10",
    "warning": "#ca5010",
    "danger": "#d13438",
    "muted": "#666666",
    "list_bg": "#ffffff",
    "list_fg": "#1a1a1a",
    "list_select_bg": "#0078d4",
    "list_select_fg": "#ffffff",
    "entry_bg": "#ffffff",
    "entry_fg": "#1a1a1a",
    "text_bg": "#ffffff",
    "text_fg": "#1a1a1a",
    "header_bg": "#e0e0e0",
    "separator": "#c0c0c0",
}

# Colori tema scuro
DARK = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
    "accent": "#569cd6",
    "card_bg": "#252526",
    "card_border": "#3c3c3c",
    "success": "#6a9955",
    "warning": "#ce9178",
    "danger": "#f44747",
    "muted": "#808080",
    "list_bg": "#252526",
    "list_fg": "#d4d4d4",
    "list_select_bg": "#264f78",
    "list_select_fg": "#ffffff",
    "entry_bg": "#3c3c3c",
    "entry_fg": "#d4d4d4",
    "text_bg": "#1e1e1e",
    "text_fg": "#d4d4d4",
    "header_bg": "#333333",
    "separator": "#404040",
}


def apply_theme(root: tk.Tk, theme: dict) -> None:
    """Applica un tema a tutta l'applicazione."""
    root.configure(bg=theme["bg"])

    style = ttk.Style()
    style.theme_use("clam")

    style.configure(".", background=theme["bg"], foreground=theme["fg"],
                    fieldbackground=theme["entry_bg"])
    style.configure("TFrame", background=theme["bg"])
    style.configure("TLabel", background=theme["bg"], foreground=theme["fg"])
    style.configure("TLabelframe", background=theme["bg"], foreground=theme["fg"])
    style.configure("TLabelframe.Label", background=theme["bg"], foreground=theme["fg"])
    style.configure("TButton", background=theme["card_bg"], foreground=theme["fg"])
    style.map("TButton", background=[("active", theme["accent"])],
              foreground=[("active", "#ffffff")])
    style.configure("TEntry", fieldbackground=theme["entry_bg"], foreground=theme["entry_fg"])
    style.configure("TCombobox", fieldbackground=theme["entry_bg"],
                    foreground=theme["entry_fg"], selectbackground=theme["list_select_bg"])
    style.configure("TNotebook", background=theme["bg"])
    style.configure("TNotebook.Tab", background=theme["card_bg"], foreground=theme["fg"],
                    padding=[12, 4])
    style.map("TNotebook.Tab", background=[("selected", theme["accent"])],
              foreground=[("selected", "#ffffff")])
    style.configure("TSeparator", background=theme["separator"])
    style.configure("TSpinbox", fieldbackground=theme["entry_bg"], foreground=theme["entry_fg"])

    # Stili personalizzati per la dashboard
    style.configure("Dashboard.TLabel", font=("Helvetica", 11))
    style.configure("KPI.TLabel", font=("Helvetica", 18, "bold"), foreground=theme["accent"])
    style.configure("KPITitle.TLabel", font=("Helvetica", 9), foreground=theme["muted"])
    style.configure("Success.TLabel", foreground=theme["success"])
    style.configure("Warning.TLabel", foreground=theme["warning"])
    style.configure("Danger.TLabel", foreground=theme["danger"])

    # Stile per il calendario
    style.configure("Cal.TLabel", font=("Helvetica", 8), padding=2)
    style.configure("CalHeader.TLabel", font=("Helvetica", 9, "bold"),
                    background=theme["header_bg"])


def get_theme(dark: bool = False) -> dict:
    return DARK if dark else LIGHT
