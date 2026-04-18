from pathlib import Path

TITLE_TEXT = "PROGRAMMA VISITE DI SOSTEGNO - MESSINA GANZIRRI"

# Directory del progetto (vis_sost_app)
PROJECT_DIR = Path(__file__).resolve().parent.parent

# Percorsi stabili (evita problemi se avvii da una cartella diversa)
DATA_FILE = PROJECT_DIR / "dati_turni.json"
PDF_FILENAME = PROJECT_DIR / "turni_visite.pdf"

# PDF base margins (pt)
PDF_MARGINS = {
    "left": 30,
    "right": 30,
    "top": 54,
    "bottom": 30,
}

# Compact style thresholds
ROWS_THRESHOLD_TIGHT = 48  # somma righe fam + fratelli oltre cui stringere ancora

# Fonts/padding (compact defaults)
HEADER_FONT = 10
BODY_FONT = 9
PADDING = 3
HEADER_FONT_TIGHT = 9
BODY_FONT_TIGHT = 8
PADDING_TIGHT = 2
