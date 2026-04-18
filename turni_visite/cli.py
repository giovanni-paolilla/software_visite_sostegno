"""
Interfaccia a riga di comando (CLI) per il programma Turni Visite.
"""
from __future__ import annotations

import difflib
import re

from .logging_cfg import setup_logging
from .config import DATA_FILE
from .repository import JsonRepository
from .normalization import canonicalizza_nome, trova_alias_simili
from .weeks import parse_settimane_lista
from .reporting import print_reports_mesi
from .pdf_export import export_pdf_mesi
from .service import esegui_ottimizzazione, conferma_e_salva_turni, diagnosi_infeasible
from .domain import TurniVisiteError, DuplicatoError, EntitaNonTrovata, StoricoConflittoError


# ---------------------------------------------------------------------------
# Funzioni IO per inserimento dati (CLI-only)
# ---------------------------------------------------------------------------

def _parse_lista_mesi_interattiva() -> list[str]:
    """Chiede all'utente i mesi da pianificare (formato YYYY-MM), uno alla volta."""
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
) -> None:
    """
    Chiede e memorizza le finestre settimanali per le frequenze
    effettivamente presenti in quel mese (CLI).
    Le finestre già presenti vengono riutilizzate senza chiedere di nuovo.
    """
    freqs_presenti = sorted(set(frequenze.get(f, 2) for f in famiglie))
    week_windows.setdefault(mese, {})

    for freq in freqs_presenti:
        if freq not in (1, 2, 4):
            continue
        fam_con_freq = [f for f in famiglie if frequenze.get(f, 2) == freq]
        if not fam_con_freq:
            continue
        if freq in week_windows[mese]:
            continue  # già inserito: riusa

        default_msg = {
            1: "es. 08-14",
            2: "es. 01-07, 15-21",
            4: "es. 01-07, 08-14, 15-21, 22-28",
        }[freq]
        while True:
            raw = input(
                f"[{mese}] Settimane per famiglie frequenza {freq} "
                f"(formato gg-gg, separate da virgola, {default_msg}): "
            ).strip()
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
            print(f" - {n} (cap={cap})")
    else:
        print("\n(Nessun fratello in elenco)")

    if repo.famiglie:
        print("\nFamiglie attuali:")
        for n in sorted(repo.famiglie):
            print(" -", n)
    else:
        print("\n(Nessuna famiglia in elenco)")


def _ask_fuzzy_name(
    raw: str, candidates: list[str], cosa: str, cutoff: float = 0.72
) -> str | None:
    """
    Normalizza 'raw' e cerca tra 'candidates'.
    Se non c'è match esatto propone suggerimenti fuzzy (max 5).
    Ritorna il nome scelto o None se annullato.
    """
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
        print("Suggerimenti non disponibili (nessuna corrispondenza sufficientemente simile).")
        return None

    print(f"\n'{raw}' non trovato tra i {cosa}. Forse intendevi:")
    for i, s in enumerate(sugg, 1):
        print(f"  {i}. {s}")
    print("  0. Annulla")
    while True:
        sel = input(
            "Digita il numero corrispondente oppure premi Invio per riscrivere il nome: "
        ).strip()
        if sel == "":
            sing = {"fratelli": "fratello", "famiglie": "famiglia"}.get(cosa, "nome")
            new_raw = input(
                f"Inserisci {sing} (testo libero, Invio vuoto per annullare): "
            ).strip()
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
        print("Scelta non valida. Riprova.")


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
    else:
        print("Scelta non valida.")


def _cmd_capacita(repo: JsonRepository) -> None:
    _stampa_elenco(repo)
    fr_raw = input("\nNome fratello: ").strip()
    fr = _ask_fuzzy_name(fr_raw, sorted(repo.fratelli), "fratelli")
    if not fr:
        print("Operazione annullata.")
        return
    az = input("Vuoi (V)isualizzare o (I)mpostare la capacità? [V/I]: ").strip().upper()
    if az == "V":
        cap = repo.capacita.get(fr, 1)
        print(f"Capacità attuale per '{fr}': {cap} visite/mese.")
    elif az == "I":
        try:
            cap = int(input("Inserisci capacità (intero 0..50): "))
            repo.set_brother_capacity(fr, cap)
            print(f"Impostata capacità {cap}/mese per '{fr}'.")
        except ValueError:
            print("Valore non numerico.")
        except TurniVisiteError as e:
            print(f"Errore: {e}")
    else:
        print("Scelta non valida.")


def _cmd_ottimizza(repo: JsonRepository, week_windows: dict) -> None:
    mesi = _parse_lista_mesi_interattiva()
    if not mesi:
        print("Nessun mese inserito.")
        return

    for mese in mesi:
        _ensure_week_windows_for_month(mese, repo.frequenze, repo.famiglie, week_windows)

    snap = repo.data_snapshot()
    cooldown = repo.get_setting("cooldown_mesi", 3)

    try:
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=cooldown,
        )
    except RuntimeError as e:
        print(str(e))
        return

    if not result.feasible:
        print("\nNessuna soluzione trovata (infeasible).\n")
        msg = diagnosi_infeasible(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=cooldown,
        )
        print(msg)
        return

    print_reports_mesi(mesi, result.solution, snap["frequenze"], week_windows)
    try:
        export_pdf_mesi(mesi, result.solution, snap["frequenze"], week_windows)
        print("PDF creato.")
    except OSError as e:
        print(f"Errore nel salvataggio del PDF: {e}")

    conferma = input(
        "\nConfermi questi turni e vuoi salvarli nello storico? [s/N]: "
    ).strip().lower()
    if conferma != "s":
        print("Bozza non salvata: nessuna modifica allo storico.")
        return

    try:
        salvati = conferma_e_salva_turni(repo, mesi, result.solution)
        print(f"Turni salvati nello storico: {', '.join(salvati)}.")
    except StoricoConflittoError as e:
        print(f"Non posso salvare: {e}")


def _cmd_sanifica(repo: JsonRepository) -> None:
    print("\nInserisci mappature alias (facoltative) nel formato 'sorgente -> canonico'.")
    print("Esempio: Smegile G -> Smedile G")
    print("Premi Invio su riga vuota per terminare.")
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
            print("Nomi non validi dopo normalizzazione, riprova.")
            continue
        mappa[src_c] = dst_c
    try:
        repo.sanitize(mappa)
        print(f"Dati sanificati e salvati in '{DATA_FILE}'.")
        groups = trova_alias_simili(list(repo.fratelli), soglia=0.88)
        if groups:
            print("\nAttenzione: possibili alias/typo residui:")
            for a, sims in groups:
                print(f" - '{a}' ~ {', '.join(sims)}")
    except TurniVisiteError as e:
        print(f"Errore sanificazione: {e}")


def _cmd_elimina_fratello(repo: JsonRepository) -> None:
    _stampa_elenco(repo)
    nome = input("\nNome del fratello da eliminare: ").strip()
    pick = _ask_fuzzy_name(nome, sorted(repo.fratelli), "fratelli")
    if not pick:
        print("Operazione annullata.")
        return
    conferma = input(
        f"Confermi l'eliminazione del fratello '{pick}'? [s/N]: "
    ).strip().lower()
    if conferma == "s":
        try:
            repo.remove_brother(pick)
            print(f"Fratello '{pick}' eliminato.")
        except TurniVisiteError as e:
            print(f"Errore: {e}")
    else:
        print("Operazione annullata.")


def _cmd_elimina_famiglia(repo: JsonRepository) -> None:
    _stampa_elenco(repo)
    nome = input("\nNome della famiglia da eliminare: ").strip()
    pick = _ask_fuzzy_name(nome, sorted(repo.famiglie), "famiglie")
    if not pick:
        print("Operazione annullata.")
        return
    conferma = input(
        f"Confermi l'eliminazione della famiglia '{pick}'? [s/N]: "
    ).strip().lower()
    if conferma == "s":
        try:
            repo.remove_family(pick)
            print(f"Famiglia '{pick}' eliminata.")
        except TurniVisiteError as e:
            print(f"Errore: {e}")
    else:
        print("Operazione annullata.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_MENU = """
Menu:
1.  Aggiungi un fratello qualificato
2.  Aggiungi una famiglia bisognosa di visita
3.  Associa un fratello a una famiglia
4.  Imposta/mostra frequenza visite per una famiglia (1,2,4)
5.  Imposta/mostra capacità visite per un fratello (0..50)
6.  Ottimizza i turni di visita (uno o più mesi)
7.  Sanifica dati (normalizza + alias)
8.  Elimina un fratello
9.  Elimina una famiglia
10. Esci"""

_HANDLERS = {
    1: _cmd_aggiungi_fratello,
    2: _cmd_aggiungi_famiglia,
    3: _cmd_associa,
    4: _cmd_frequenza,
    5: _cmd_capacita,
    8: _cmd_elimina_fratello,
    9: _cmd_elimina_famiglia,
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
            scelta = int(input("Scegli un'opzione (1-10): "))
        except ValueError:
            print("Opzione non valida. Devi inserire un numero.")
            continue

        if scelta == 10:
            print("Uscita.")
            break
        elif scelta == 6:
            _cmd_ottimizza(repo, week_windows)
        elif scelta == 7:
            _cmd_sanifica(repo)
        elif scelta in _HANDLERS:
            _handlers = _HANDLERS  # evita lookup ripetuto
            _HANDLERS[scelta](repo)
        else:
            print("Opzione non valida.")


if __name__ == "__main__":
    main()
