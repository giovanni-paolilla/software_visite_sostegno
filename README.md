# PROGRAMMA VISITE DI SOSTEGNO — Messina Ganzirri

Gestione **anagrafica fratelli/famiglie**, associazioni, **pianificazione visite** multi-mese
con **ottimizzazione OR-Tools**, **report** testuali e **export PDF**.
Interfacce: **CLI** (testuale) e **GUI Tkinter** (desktop).

---

## Requisiti

- **Python 3.10+** (il progetto usa gli union type `X | Y` nei type hints)
- **Dipendenze runtime** (vedi `requirements.txt`):
  - `ortools >= 9.9, < 10`
  - `reportlab >= 4.0, < 5`
- **Tkinter** (solo per la GUI):
  - Windows / macOS: incluso nella distribuzione standard di Python.
  - Linux: `sudo apt install python3-tk`
- **Dipendenze di sviluppo** (opzionali):
  - `pytest >= 8.0, < 9`

---

## Installazione rapida

```bash
# 1) Clona o scarica il progetto
git clone <URL_DEL_REPO>
cd your-project

# 2) Crea e attiva un virtualenv (consigliato)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3) Installa le dipendenze runtime
pip install -r requirements.txt

# 4) (Opzionale) Installa anche le dipendenze di sviluppo (pytest)
pip install -r requirements.txt pytest
```

---

## Struttura del progetto

```
your-project/
├─ turni_visite/             # Package principale
│  ├─ __init__.py            # Versione e API pubblica del package
│  ├─ domain.py              # Modelli di dominio ed eccezioni custom
│  ├─ config.py              # Costanti e percorsi (DATA_FILE, PDF, margini)
│  ├─ logging_cfg.py         # Setup logger su file (percorso assoluto)
│  ├─ normalization.py       # Canonicalizzazione nomi + ricerca alias
│  ├─ repository.py          # Persistenza JSON + CRUD (salvataggio atomico)
│  ├─ service.py             # Strato servizi: ottimizza / salva / diagnostica
│  ├─ scheduling.py          # Modello OR-Tools e validazioni solver
│  ├─ weeks.py               # Utility mesi, settimane ed etichette slot
│  ├─ reporting.py           # Report testuali a video
│  ├─ pdf_export.py          # Export PDF con ReportLab
│  ├─ cli.py                 # Interfaccia a riga di comando
│  └─ gui_tk.py              # Interfaccia grafica Tkinter
├─ tests/
│  ├─ conftest.py            # Setup pytest (sys.path automatico)
│  ├─ test_config.py         # Test percorsi e costanti
│  ├─ test_domain.py         # Test modelli e gerarchia eccezioni
│  ├─ test_normalization.py  # Test canonicalizzazione e alias
│  ├─ test_weeks.py          # Test etichette settimana/mese
│  ├─ test_repository.py     # Test CRUD, storico, I/O atomica
│  ├─ test_scheduling.py     # Test solver (skip se ortools assente)
│  └─ test_service.py        # Test strato servizi
├─ .gitattributes            # Normalizzazione line endings (LF)
├─ pyproject.toml            # Metadati pacchetto e entry points
├─ requirements.txt          # Dipendenze runtime
└─ dati_turni.json           # Dati (creato/aggiornato dal programma)
```

---

## Avvio

### GUI (Tkinter)

```bash
# Con entry point installato:
turni-gui

# Oppure direttamente:
python -m turni_visite.gui_tk
```

### CLI (testuale)

```bash
# Con entry point installato:
turni

# Oppure direttamente:
python -m turni_visite.cli
```

---

## Uso — GUI

### Tab Anagrafica

| Operazione | Come |
|---|---|
| Aggiungi fratello | Campo testo + pulsante **Aggiungi Fratello** |
| Aggiungi famiglia | Campo testo + pulsante **Aggiungi Famiglia** |
| Associa fratello → famiglia | Due menu a tendina + pulsante **Associa** |
| Imposta frequenza (1/2/4) | Tendina frequenza + tendina famiglia + **Imposta Frequenza** |
| Imposta capacità (0..50) | Tendina fratello + Spinbox + **Imposta Capacità** |
| Elimina fratello | Tendina + pulsante **Elimina** (pulisce le associazioni) |
| Elimina famiglia | Tendina + pulsante **Elimina** (pulisce frequenza e associazioni) |

### Tab Pianificazione

1. Inserisci i **mesi** (es. `2025-11, 2025-12`).
2. Imposta il **cooldown** (mesi di anti-ravvicinamento, default 3).
3. Clicca **Ottimizza & Genera PDF**:
   - Un dialog chiede gli **intervalli settimanali** per ogni frequenza presente.
   - Il solver gira in background (max 20 s); l'UI rimane reattiva.
   - Il risultato appare nell'area di testo.
4. Nella finestra di conferma: **Conferma e salva** per salvare nello storico
   e scegliere il percorso del PDF con un dialog di sistema.

### Type-ahead nelle tendine

- Digita una o più lettere: salta al **primo valore** che inizia con quel prefisso.
- Ripeti la **stessa lettera** per **ciclare** tra i match.
- **Backspace** rimuove l'ultimo carattere del prefisso; **Esc** azzera il buffer.
- Il buffer si resetta automaticamente dopo ~800 ms di inattività.

---

## Uso — CLI

```
Menu:
1.  Aggiungi un fratello qualificato
2.  Aggiungi una famiglia bisognosa di visita
3.  Associa un fratello a una famiglia         (con ricerca fuzzy)
4.  Imposta/mostra frequenza per una famiglia  (1, 2, 4 — con fuzzy)
5.  Imposta/mostra capacita' per un fratello   (0..50 — con fuzzy)
6.  Ottimizza i turni di visita                (uno o piu' mesi)
7.  Sanifica dati                              (normalizza + alias)
8.  Elimina un fratello                        (con fuzzy)
9.  Elimina una famiglia                       (con fuzzy)
10. Esci
```

**Ricerca fuzzy**: se il nome digitato non corrisponde esattamente, vengono
proposti fino a 5 candidati simili; scegli con il numero o riscrivi il nome.

**Ottimizzazione (voce 6)**:
1. Inserisci i mesi uno alla volta (formato `YYYY-MM`, Invio vuoto per terminare).
2. Definisci gli intervalli settimanali per ciascuna frequenza.
3. Il piano viene stampato a video e il PDF è generato nella cartella del progetto.
4. Conferma con `s` per salvare nello storico (impedisce rigenerazioni accidentali).

---

## Architettura

```
CLI / GUI  →  service.py  →  scheduling.py  (OR-Tools)
                         →  repository.py  (JSON atomico)
                         →  pdf_export.py  (ReportLab)
```

- **`domain.py`**: modelli (`Fratello`, `Famiglia`, `SolverResult`) e gerarchia di
  eccezioni (`TurniVisiteError` → `EntitaNonTrovata`, `DuplicatoError`,
  `ValidazioneError`, `StoricoConflittoError`).
- **`service.py`**: strato di use-case condiviso tra CLI e GUI — nessuna logica di
  business è duplicata tra le due interfacce.
- **`repository.py`**: salvataggio **atomico** (`tempfile` + `os.replace`); i metodi
  CRUD sollevano eccezioni invece di stampare su stdout — completamente testabile.
- **`scheduling.py`**: modello CP-SAT con cooldown hard, vincoli di capacità per
  fratello, storico confermato e obiettivo di minimizzazione del carico massimo mensile.

---

## Ottimizzazione (OR-Tools CP-SAT)

### Vincoli hard
- Ogni famiglia con frequenza *f* ha esattamente *f* slot mensili.
- Ogni slot è assegnato a **esattamente un fratello** tra quelli associati.
- Un fratello non compare **due volte** nella stessa famiglia nello stesso mese.
- Un fratello non supera la propria **capacità mensile** (numero max di visite).
- **Cooldown**: un fratello non può visitare la stessa famiglia in due mesi
  entro la finestra di *cooldown_mesi* (vincolo esteso anche allo storico confermato).

### Obiettivo soft
Minimizza il carico massimo mensile (distribuzione equa tra i fratelli).

### Diagnostica infeasible
Se il solver non trova soluzioni, `explain_infeasible` produce un messaggio leggibile
che identifica: capacità insufficiente, famiglie sotto-associate, blocchi da storico/cooldown,
e indica i miglioramenti minimi necessari.

---

## Esportazione PDF

- Il percorso viene **scelto dall'utente** tramite dialog (GUI) oppure scritto nella
  cartella del progetto come `turni_visite.pdf` (CLI e path di fallback in `config.py`).
- Per **ogni mese** pianificato (su pagina separata):
  - Tabella **per Famiglia**: frequenza e fratelli assegnati con etichetta settimana.
  - Tabella **per Fratello**: una riga per ogni assegnazione, con data/slot e famiglia.
- Layout **compattato** automaticamente (font e padding ridotti) quando le righe totali
  superano `ROWS_THRESHOLD_TIGHT` (configurabile in `config.py`).

---

## Persistenza e integrità dati

- **File**: `dati_turni.json` nella cartella root del progetto (percorso assoluto,
  indipendente dalla working directory).
- **Scrittura atomica**: i dati vengono scritti su un file temporaneo e poi
  spostati con `os.replace()` — il file principale non è mai in stato parziale.
- **Storico turni**: i turni confermati vengono memorizzati con timestamp e non
  possono essere sovrascritti per errore (richiede eliminazione esplicita del mese).
- **Log**: `logs/turni_visite.log` nella cartella root, con fallback su stderr.

---

## Test

```bash
# Esegui tutti i test dalla root del progetto
pytest

# Con output dettagliato
pytest -v

# Solo una categoria
pytest tests/test_repository.py -v
```

I test di integrazione del solver (`test_scheduling.py`) vengono saltati
automaticamente se `ortools` non è installato.

---

## Configurazione (`turni_visite/config.py`)

| Costante | Descrizione |
|---|---|
| `TITLE_TEXT` | Intestazione del PDF e dei log |
| `DATA_FILE` | Percorso assoluto del file JSON dati |
| `PDF_FILENAME` | Percorso PDF di fallback (usato dalla CLI) |
| `PDF_MARGINS` | Margini PDF in punti (`left`, `right`, `top`, `bottom`) |
| `ROWS_THRESHOLD_TIGHT` | Soglia righe oltre cui compattare il PDF |
| `HEADER_FONT` / `BODY_FONT` / `PADDING` | Stile normale |
| `HEADER_FONT_TIGHT` / `BODY_FONT_TIGHT` / `PADDING_TIGHT` | Stile compatto |

---

## Troubleshooting

**GUI non parte / Tkinter mancante**
```bash
# Debian/Ubuntu/Linux Mint
sudo apt install python3-tk
# Fedora
sudo dnf install python3-tkinter
```

**"Nessuna soluzione trovata"**
Il solver diagnostica automaticamente la causa (capacità, associazioni,
cooldown). Leggere il messaggio di diagnostica e seguire i suggerimenti di sblocco.

**Python < 3.10**
Aggiorna Python: il progetto usa `X | Y` nei type hints (PEP 604).

**PDF non si apre / è vuoto**
Verifica che l'ottimizzazione abbia prodotto una soluzione prima di aprire il PDF.

---

## Changelog

### v0.1.0 (corrente)
- **Architettura**: aggiunto `service.py` come strato condiviso tra CLI e GUI;
  rimosso codice duplicato di salvataggio storico.
- **Dominio**: `domain.py` popolato con modelli (`Fratello`, `Famiglia`,
  `SolverResult`) e gerarchia di eccezioni custom.
- **Repository**: salvataggio **atomico** (`os.replace`); metodi CRUD sollevano
  eccezioni invece di stampare su stdout; associazioni salvate ordinate.
- **GUI**: `gui_tk.py` spostato nel package; riferimento diretto al pulsante
  Ottimizza; `filedialog` per la scelta del percorso PDF.
- **Logging**: percorso log assoluto (non dipende dalla working directory).
- **Scheduling**: numero di worker del solver adattato ai core disponibili.
- **PDF**: parametro `output_path` su `export_pdf_mesi` (path scelto dall'utente).
- **Test**: suite completa in `tests/` con `conftest.py` automatico.
- **Progetto**: aggiunto `.gitattributes` per line endings LF uniformi;
  entry point `turni-gui` in `pyproject.toml`.

---

## Licenza

MIT — vedi `LICENSE` (da aggiungere se mancante).

## Contatti / Supporto

Per segnalazioni o richieste, apri una issue nel repository o contatta
direttamente i manutentori.
