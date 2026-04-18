"""
Interfaccia a riga di comando (CLI) per il programma Turni Visite.
"""
from __future__ import annotations

import difflib
import re

from .logging_cfg import setup_logging
from .config import DATA_FILE, DEFAULT_WEEK_TEMPLATES
from .repository import JsonRepository
from .normalization import canonicalizza_nome, trova_alias_simili
from .weeks import parse_settimane_lista
from .reporting import print_reports_mesi
from .pdf_export import export_pdf_mesi
from .csv_export import export_csv_mesi, export_csv_per_fratello, import_csv_anagrafica
from .backup import create_backup, list_backups, restore_backup
from .stats import report_carico_fratelli, calcola_indice_equita
from .service import (
    esegui_ottimizzazione, conferma_e_salva_turni, diagnosi_infeasible,
    quick_check, open_file,
)
from .domain import TurniVisiteError, StoricoConflittoError
from .scheduling import validate_month_yyyy_mm


# ---------------------------------------------------------------------------
# Funzioni IO per inserimento dati (CLI-only)
# ---------------------------------------------------------------------------

def _parse_lista_mesi_interattiva() -> list[str]:
    mesi: list[str] = []
    visti: set[str] = set()
    while True:
        s = input("Inserisci un mese (YYYY-MM). Invio vuoto per terminare: ").strip()
        if not s:
            break
        if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", s):
            if s not in visti:
                visti.add(s)
                mesi.append(s)
        else:
            print("Formato mese non valido. Usa YYYY-MM (es. 2025-01).")
    return sorted(mesi)


def _ensure_week_windows_for_month(
    mese: str,
    frequenze: dict[str, int],
    famiglie: set[str],
    week_windows: dict,
    week_templates: dict[str, list[str]],
) -> None:
    freqs_presenti = sorted(set(frequenze.get(f, 2) for f in famiglie))
    week_windows.setdefault(mese, {})

    for freq in freqs_presenti:
        if freq not in (1, 2, 4):
            continue
        fam_con_freq = [f for f in famiglie if frequenze.get(f, 2) == freq]
        if not fam_con_freq:
            continue
        if freq in week_windows[mese]:
            continue

        # Usa template salvato come default
        template = week_templates.get(str(freq))
        if template:
            default_msg = ", ".join(template)
        else:
            default_msg = ", ".join(DEFAULT_WEEK_TEMPLATES.get(freq, []))

        while True:
            raw = input(
                f"[{mese}] Settimane per famiglie frequenza {freq} "
                f"(gg-gg, virgola; default: {default_msg}): "
            ).strip()
            if not raw:
                raw = default_msg
            parsed, err = parse_settimane_lista(raw, freq)
            if parsed is not None:
                week_windows[mese][freq] = parsed
                break
            print(err)


# ---------------------------------------------------------------------------
# Helpers di presentazione
# ---------------------------------------------------------------------------

def _stampa_elenco(repo: JsonRepository) -> None:
    if repo.fratelli:
        print("\nFratelli attuali:")
        for n in sorted(repo.fratelli):
            cap = repo.capacita.get(n, 1)
            indisp = repo.indisponibilita.get(n, [])
            label = f" - {n} (cap={cap})"
            if indisp:
                label += f"  [indisponibile: {', '.join(indisp)}]"
            print(label)
    else:
        print("\n(Nessun fratello in elenco)")

    if repo.famiglie:
        print("\nFamiglie attuali:")
        for n in sorted(repo.famiglie):
            freq = repo.frequenze.get(n, 2)
            n_assoc = len(repo.associazioni.get(n, []))
            print(f" - {n} (freq={freq}, assoc={n_assoc})")
    else:
        print("\n(Nessuna famiglia in elenco)")


def _ask_fuzzy_name(
    raw: str, candidates: list[str], cosa: str, cutoff: float = 0.72
) -> str | None:
    if not candidates:
        print(f"(Non ci sono {cosa} registrati.)")
        return None
    norm = canonicalizza_nome(raw) if raw else None
    if norm and norm in candidates:
        return norm
    probe = norm if norm else (raw or "")
    sugg = difflib.get_close_matches(probe, candidates, n=5, cutoff=cutoff)
    if not sugg:
        print(f"'{raw}' non trovato tra i {cosa}.")
        return None
    print(f"\n'{raw}' non trovato. Forse intendevi:")
    for i, s in enumerate(sugg, 1):
        print(f"  {i}. {s}")
    print("  0. Annulla")
    while True:
        sel = input("Numero o Invio per riscrivere: ").strip()
        if sel == "":
            new_raw = input(f"Inserisci nome (Invio vuoto per annullare): ").strip()
            if not new_raw:
                return None
            norm2 = canonicalizza_nome(new_raw)
            if norm2 in candidates:
                return norm2
            return _ask_fuzzy_name(new_raw, candidates, cosa, cutoff)
        if sel == "0":
            return None
        if sel.isdigit():
            idx = int(sel)
            if 1 <= idx <= len(sugg):
                return sugg[idx - 1]
        print("Scelta non valida.")


# ---------------------------------------------------------------------------
# Handler dei comandi del menu
# ---------------------------------------------------------------------------

def _cmd_aggiungi_fratello(repo: JsonRepository) -> None:
    _stampa_elenco(repo)
    raw = input("\nNome fratello da aggiungere: ").strip()
    try:
        nome_ok = repo.add_brother(raw)
        print(f"Fratello '{nome_ok}' aggiunto.")
    except TurniVisiteError as e:
        print(f"Errore: {e}")


def _cmd_aggiungi_famiglia(repo: JsonRepository) -> None:
    _stampa_elenco(repo)
    raw = input("\nNome famiglia da aggiungere: ").strip()
    try:
        nome_ok = repo.add_family(raw)
        print(f"Famiglia '{nome_ok}' aggiunta.")
    except TurniVisiteError as e:
        print(f"Errore: {e}")


def _cmd_associa(repo: JsonRepository) -> None:
    _stampa_elenco(repo)
    raw_fr = input("\nNome fratello da associare: ").strip()
    fr = _ask_fuzzy_name(raw_fr, sorted(repo.fratelli), "fratelli")
    if not fr:
        print("Operazione annullata.")
        return
    raw_fam = input("Nome famiglia a cui associarlo: ").strip()
    fam = _ask_fuzzy_name(raw_fam, sorted(repo.famiglie), "famiglie")
    if not fam:
        print("Operazione annullata.")
        return
    try:
        repo.associate(fr, fam)
        print(f"Associato '{fr}' -> '{fam}'.")
    except TurniVisiteError as e:
        print(f"Errore: {e}")


def _cmd_frequenza(repo: JsonRepository) -> None:
    _stampa_elenco(repo)
    fam_raw = input("\nNome famiglia: ").strip()
    fam = _ask_fuzzy_name(fam_raw, sorted(repo.famiglie), "famiglie")
    if not fam:
        print("Operazione annullata.")
        return
    az = input("Vuoi (V)isualizzare o (I)mpostare la frequenza? [V/I]: ").strip().upper()
    if az == "V":
        freq = repo.frequenze.get(fam, 2)
        print(f"Frequenza attuale per '{fam}': {freq} visite/mese")
    elif az == "I":
        try:
            freq = int(input("Inserisci frequenza (1, 2 o 4): "))
            repo.set_frequency(fam, freq)
            print(f"Frequenza '{fam}' impostata a {freq}/mese.")
        except ValueError:
            print("Valore non numerico.")
        except TurniVisiteError as e:
            print(f"Errore: {e}")


def _cmd_capacita(repo: JsonRepository) -> None:
    _stampa_elenco(repo)
    fr_raw = input("\nNome fratello: ").strip()
    fr = _ask_fuzzy_name(fr_raw, sorted(repo.fratelli), "fratelli")
    if not fr:
        print("Operazione annullata.")
        return
    az = input("Vuoi (V)isualizzare o (I)mpostare la capacita'? [V/I]: ").strip().upper()
    if az == "V":
        cap = repo.capacita.get(fr, 1)
        print(f"Capacita' attuale per '{fr}': {cap} visite/mese.")
    elif az == "I":
        try:
            cap = int(input("Inserisci capacita' (intero 0..50): "))
            repo.set_brother_capacity(fr, cap)
            print(f"Capacita' {cap}/mese impostata per '{fr}'.")
        except ValueError:
            print("Valore non numerico.")
        except TurniVisiteError as e:
            print(f"Errore: {e}")


def _cmd_ottimizza(repo: JsonRepository, week_windows: dict) -> None:
    mesi = _parse_lista_mesi_interattiva()
    if not mesi:
        print("Nessun mese inserito.")
        return

    for mese in mesi:
        _ensure_week_windows_for_month(
            mese, repo.frequenze, repo.famiglie, week_windows, repo.week_templates
        )

    snap = repo.data_snapshot()
    cooldown = repo.get_setting("cooldown_mesi", 3)

    # Pre-check rapido
    check = quick_check(snap, mesi, repo.get_storico_turni(), cooldown)
    if not check["fattibile"]:
        print("\nPre-check: PROBLEMI RILEVATI")
        for p in check["problemi"]:
            print(f"  - {p}")
        conferma_precheck = input("Vuoi tentare comunque l'ottimizzazione? [s/N]: ").strip().lower()
        if conferma_precheck != "s":
            return
    if check["avvisi"]:
        for a in check["avvisi"]:
            print(f"  Avviso: {a}")

    try:
        result = esegui_ottimizzazione(
            snap=snap, mesi=mesi,
            storico_turni=repo.get_storico_turni(), cooldown=cooldown,
        )
    except RuntimeError as e:
        print(str(e))
        return

    if not result.feasible:
        print("\nNessuna soluzione trovata (infeasible).\n")
        msg = diagnosi_infeasible(
            snap=snap, mesi=mesi,
            storico_turni=repo.get_storico_turni(), cooldown=cooldown,
        )
        print(msg)
        return

    print_reports_mesi(mesi, result.solution, snap["frequenze"], week_windows)

    # PDF
    pdf_ok = True
    try:
        export_pdf_mesi(mesi, result.solution, snap["frequenze"], week_windows)
        print("PDF creato.")
        open_file(str(DATA_FILE.parent / "turni_visite.pdf"))
    except OSError as e:
        print(f"Errore nel salvataggio del PDF: {e}")
        pdf_ok = False

    # CSV opzionale
    csv_choice = input("Vuoi esportare anche in CSV? [s/N]: ").strip().lower()
    if csv_choice == "s":
        csv_path = str(DATA_FILE.parent / ("turni_" + "-".join(mesi) + ".csv"))
        try:
            export_csv_mesi(mesi, result.solution, snap["frequenze"], week_windows, csv_path)
            print(f"CSV esportato: {csv_path}")
        except Exception as e:
            print(f"Errore CSV: {e}")

    if pdf_ok:
        domanda = "\nConfermi questi turni e vuoi salvarli nello storico? [s/N]: "
    else:
        domanda = "\nPDF non generato. Salvare comunque nello storico? [s/N]: "

    conferma = input(domanda).strip().lower()
    if conferma != "s":
        print("Bozza non salvata.")
        return

    try:
        salvati = conferma_e_salva_turni(repo, mesi, result.solution)
        print(f"Turni salvati nello storico: {', '.join(salvati)}.")
    except StoricoConflittoError as e:
        print(f"Non posso salvare: {e}")


def _cmd_sanifica(repo: JsonRepository) -> None:
    print("\nMappature alias (facoltative) nel formato 'sorgente -> canonico'.")
    print("Invio vuoto per terminare.")
    mappa: dict[str, str] = {}
    while True:
        r = input("Alias: ").strip()
        if not r:
            break
        if "->" not in r:
            print("Formato non valido. Usa 'sorgente -> canonico'.")
            continue
        src, dst = [p.strip() for p in r.split("->", 1)]
        src_c = canonicalizza_nome(src)
        dst_c = canonicalizza_nome(dst)
        if not src_c or not dst_c:
            print("Nomi non validi.")
            continue
        mappa[src_c] = dst_c
    try:
        repo.sanitize(mappa)
        print(f"Dati sanificati e salvati.")
        groups = trova_alias_simili(list(repo.fratelli), soglia=0.88)
        if groups:
            print("\nPossibili alias residui:")
            for a, sims in groups:
                print(f" - '{a}' ~ {', '.join(sims)}")
    except TurniVisiteError as e:
        print(f"Errore: {e}")


def _cmd_elimina_fratello(repo: JsonRepository) -> None:
    _stampa_elenco(repo)
    nome = input("\nNome fratello da eliminare: ").strip()
    pick = _ask_fuzzy_name(nome, sorted(repo.fratelli), "fratelli")
    if not pick:
        print("Operazione annullata.")
        return
    conferma = input(f"Confermi l'eliminazione di '{pick}'? [s/N]: ").strip().lower()
    if conferma == "s":
        try:
            repo.remove_brother(pick)
            print(f"Fratello '{pick}' eliminato.")
        except TurniVisiteError as e:
            print(f"Errore: {e}")


def _cmd_elimina_famiglia(repo: JsonRepository) -> None:
    _stampa_elenco(repo)
    nome = input("\nNome famiglia da eliminare: ").strip()
    pick = _ask_fuzzy_name(nome, sorted(repo.famiglie), "famiglie")
    if not pick:
        print("Operazione annullata.")
        return
    conferma = input(f"Confermi l'eliminazione di '{pick}'? [s/N]: ").strip().lower()
    if conferma == "s":
        try:
            repo.remove_family(pick)
            print(f"Famiglia '{pick}' eliminata.")
        except TurniVisiteError as e:
            print(f"Errore: {e}")


def _cmd_storico(repo: JsonRepository) -> None:
    storico = repo.get_storico_turni()
    if not storico:
        print("\n(Nessun mese nello storico.)")
        return
    print("\nStorico turni confermati:")
    for rec in storico:
        mese = rec.get("mese", "?")
        n = len(rec.get("assegnazioni", []))
        confirmed = rec.get("confirmed_at", "")
        print(f" - {mese}  ({n} assegnazioni, confermato {confirmed})")
    az = input("\n(E)limina un mese, (D)ettaglio, (I)ndietro? [E/D/I]: ").strip().upper()
    if az == "E":
        mese = input("Mese da eliminare (YYYY-MM): ").strip()
        conferma = input(f"Confermi l'eliminazione di '{mese}'? [s/N]: ").strip().lower()
        if conferma == "s":
            try:
                repo.delete_storico_mese(mese)
                print(f"Mese '{mese}' rimosso.")
            except TurniVisiteError as e:
                print(f"Errore: {e}")
    elif az == "D":
        mese = input("Mese da visualizzare (YYYY-MM): ").strip()
        rec = next((r for r in storico if r.get("mese") == mese), None)
        if not rec:
            print("Mese non trovato.")
            return
        per_fam: dict[str, list[str]] = {}
        for a in rec.get("assegnazioni", []):
            fam = a.get("famiglia", "?")
            per_fam.setdefault(fam, []).append(a.get("fratello", "?"))
        for fam in sorted(per_fam.keys()):
            print(f"  {fam}: {', '.join(per_fam[fam])}")


def _cmd_indisponibilita(repo: JsonRepository) -> None:
    _stampa_elenco(repo)
    fr_raw = input("\nNome fratello: ").strip()
    fr = _ask_fuzzy_name(fr_raw, sorted(repo.fratelli), "fratelli")
    if not fr:
        print("Operazione annullata.")
        return
    current = repo.get_indisponibilita(fr)
    if current:
        print(f"Indisponibilita' attuali per '{fr}': {', '.join(current)}")
    else:
        print(f"'{fr}' non ha indisponibilita' registrate.")
    az = input("(A)ggiungi, (R)imuovi, (I)ndietro? [A/R/I]: ").strip().upper()
    if az == "A":
        mese = input("Mese di indisponibilita' (YYYY-MM): ").strip()
        try:
            mese = validate_month_yyyy_mm(mese)
            repo.add_indisponibilita(fr, mese)
            print(f"Indisponibilita' aggiunta: {fr} per {mese}")
        except (ValueError, TurniVisiteError) as e:
            print(f"Errore: {e}")
    elif az == "R":
        mese = input("Mese da rimuovere (YYYY-MM): ").strip()
        try:
            repo.remove_indisponibilita(fr, mese)
            print(f"Indisponibilita' rimossa: {fr} per {mese}")
        except TurniVisiteError as e:
            print(f"Errore: {e}")


def _cmd_vincoli(repo: JsonRepository) -> None:
    vincoli = repo.get_vincoli()
    if vincoli:
        print("\nVincoli personalizzati attuali:")
        for i, v in enumerate(vincoli, 1):
            print(f"  {i}. {v['fratello_a']} <-> {v['fratello_b']} [{v['tipo']}] {v.get('descrizione', '')}")
    else:
        print("\n(Nessun vincolo personalizzato.)")
    az = input("(A)ggiungi, (R)imuovi, (I)ndietro? [A/R/I]: ").strip().upper()
    if az == "A":
        fa = _ask_fuzzy_name(input("Fratello A: ").strip(), sorted(repo.fratelli), "fratelli")
        if not fa:
            return
        fb = _ask_fuzzy_name(input("Fratello B: ").strip(), sorted(repo.fratelli), "fratelli")
        if not fb:
            return
        tipo = input("Tipo (incompatibile/preferenza_coppia): ").strip()
        desc = input("Descrizione (opzionale): ").strip()
        try:
            repo.add_vincolo(fa, fb, tipo, desc)
            print(f"Vincolo {tipo} aggiunto: {fa} <-> {fb}")
        except TurniVisiteError as e:
            print(f"Errore: {e}")
    elif az == "R":
        if not vincoli:
            return
        try:
            n = int(input("Numero vincolo da rimuovere: "))
            v = vincoli[n - 1]
            repo.remove_vincolo(v["fratello_a"], v["fratello_b"], v["tipo"])
            print("Vincolo rimosso.")
        except (ValueError, IndexError, TurniVisiteError) as e:
            print(f"Errore: {e}")


def _cmd_backup(repo: JsonRepository) -> None:
    print("\nBackup:")
    print("  1. Crea backup ora")
    print("  2. Lista backup disponibili")
    print("  3. Ripristina un backup")
    print("  0. Indietro")
    az = input("Scelta: ").strip()
    if az == "1":
        path = create_backup(DATA_FILE)
        if path:
            print(f"Backup creato: {path}")
        else:
            print("Nessun file dati da backuppare.")
    elif az == "2":
        backups = list_backups()
        if not backups:
            print("Nessun backup disponibile.")
        else:
            for i, b in enumerate(backups, 1):
                print(f"  {i}. {b['filename']}  ({b['size_kb']} KB, {b['modified']})")
    elif az == "3":
        backups = list_backups()
        if not backups:
            print("Nessun backup disponibile.")
            return
        for i, b in enumerate(backups, 1):
            print(f"  {i}. {b['filename']}  ({b['modified']})")
        try:
            n = int(input("Numero backup: "))
            b = backups[n - 1]
            conferma = input(f"Ripristinare '{b['filename']}'? [s/N]: ").strip().lower()
            if conferma == "s":
                restore_backup(b["path"], DATA_FILE)
                repo.load()
                print("Backup ripristinato. Dati ricaricati.")
        except (ValueError, IndexError, FileNotFoundError) as e:
            print(f"Errore: {e}")


def _cmd_statistiche(repo: JsonRepository) -> None:
    storico = repo.get_storico_turni()
    if not storico:
        print("\nNessun dato nello storico per le statistiche.")
        return
    print("\nStatistiche:")
    print("  1. Report carico fratelli")
    print("  2. Indice di equita'")
    print("  0. Indietro")
    az = input("Scelta: ").strip()
    if az == "1":
        report = report_carico_fratelli(storico)
        for r in report:
            print(f"\n{r['fratello']}:")
            print(f"  Visite totali: {r['visite_totali']}, Mesi: {r['mesi_attivi']}")
            print(f"  Famiglie: {', '.join(r['famiglie_visitate'])}")
    elif az == "2":
        eq = calcola_indice_equita(storico)
        print(f"\nMedia visite: {eq['media']}")
        print(f"Dev. std: {eq['deviazione_standard']}")
        print(f"Min: {eq['min']} ({eq['fratello_min']})")
        print(f"Max: {eq['max']} ({eq['fratello_max']})")
        print(f"Gini: {eq['indice_gini']} (0=equo, 1=disuguale)")


def _cmd_import_csv(repo: JsonRepository) -> None:
    path = input("Percorso file CSV: ").strip()
    if not path:
        return
    try:
        result = import_csv_anagrafica(path)
    except Exception as e:
        print(f"Errore lettura CSV: {e}")
        return
    n_fr = n_fam = 0
    for nome, cap in result["fratelli"]:
        try:
            repo.add_brother(nome)
            repo.set_brother_capacity(nome, cap)
            n_fr += 1
        except TurniVisiteError as e:
            print(f"  Fratello '{nome}': {e}")
    for nome, freq in result["famiglie"]:
        try:
            repo.add_family(nome)
            repo.set_frequency(nome, freq)
            n_fam += 1
        except TurniVisiteError as e:
            print(f"  Famiglia '{nome}': {e}")
    print(f"Importati: {n_fr} fratelli, {n_fam} famiglie.")
    if result["errori"]:
        print(f"Errori CSV: {len(result['errori'])}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_MENU = """
Menu:
 1.  Aggiungi un fratello
 2.  Aggiungi una famiglia
 3.  Associa un fratello a una famiglia
 4.  Imposta/mostra frequenza (1,2,4)
 5.  Imposta/mostra capacita' (0..50)
 6.  Ottimizza i turni (con pre-check, PDF, CSV)
 7.  Sanifica dati (normalizza + alias)
 8.  Elimina un fratello
 9.  Elimina una famiglia
10.  Storico turni (visualizza/elimina/dettaglio)
11.  Indisponibilita' temporanee
12.  Vincoli personalizzati
13.  Backup e ripristino
14.  Statistiche e report
15.  Import da CSV
16.  Dashboard KPI
17.  Esci"""


def _cmd_dashboard(repo: JsonRepository) -> None:
    kpi = repo.get_dashboard_kpi()
    print(f"\n{'='*50}")
    print("DASHBOARD")
    print(f"{'='*50}")
    print(f"  Fratelli attivi:    {kpi['n_fratelli_attivi']}/{kpi['n_fratelli']}")
    print(f"  Famiglie:           {kpi['n_famiglie']}")
    print(f"  Capacita' totale:   {kpi['capacita_totale']}")
    print(f"  Domanda mensile:    {kpi['domanda_totale']}")
    bilancio = kpi['bilancio']
    stato = "OK" if bilancio >= 0 else "INSUFFICIENTE"
    print(f"  Bilancio:           {bilancio:+d} ({stato})")
    print(f"  Mesi nello storico: {kpi['n_mesi_storico']}")
    if kpi['ultimo_mese_storico']:
        print(f"  Ultimo mese:        {kpi['ultimo_mese_storico']}")
    if kpi['famiglie_senza_associazione']:
        print(f"  Famiglie senza assoc: {', '.join(kpi['famiglie_senza_associazione'])}")
    if kpi['fratelli_senza_associazione']:
        print(f"  Fratelli senza assoc: {', '.join(kpi['fratelli_senza_associazione'])}")
    print(f"  Vincoli attivi:     {kpi['n_vincoli']}")
    print(f"  Indisponibilita':   {kpi['n_indisponibilita']}")


_HANDLERS = {
    1: _cmd_aggiungi_fratello,
    2: _cmd_aggiungi_famiglia,
    3: _cmd_associa,
    4: _cmd_frequenza,
    5: _cmd_capacita,
    8: _cmd_elimina_fratello,
    9: _cmd_elimina_famiglia,
    10: _cmd_storico,
    11: _cmd_indisponibilita,
    12: _cmd_vincoli,
    13: _cmd_backup,
    14: _cmd_statistiche,
    15: _cmd_import_csv,
    16: _cmd_dashboard,
}


def main() -> None:
    setup_logging()
    repo = JsonRepository(DATA_FILE)
    week_windows: dict[str, dict[int, list[str]]] = {}

    groups = trova_alias_simili(list(repo.fratelli), soglia=0.88)
    if groups:
        print("\nAttenzione: possibili alias/typo tra i fratelli:")
        for a, sims in groups:
            print(f" - '{a}' ~ {', '.join(sims)}")

    while True:
        print(_MENU)
        try:
            scelta = int(input("Scegli un'opzione (1-17): "))
        except ValueError:
            print("Opzione non valida.")
            continue

        if scelta == 17:
            print("Uscita.")
            break
        elif scelta == 6:
            _cmd_ottimizza(repo, week_windows)
        elif scelta == 7:
            _cmd_sanifica(repo)
        elif scelta in _HANDLERS:
            _HANDLERS[scelta](repo)
        else:
            print("Opzione non valida.")


if __name__ == "__main__":
    main()
