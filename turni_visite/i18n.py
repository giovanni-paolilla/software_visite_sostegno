"""
Supporto internazionalizzazione (i18n) per turni-visite.

Sistema semplice basato su dizionari. Permette di cambiare lingua
senza librerie esterne.

Uso:
    from turni_visite.i18n import t, set_language
    set_language("en")
    print(t("dashboard.titolo"))  # -> "Dashboard"
"""
from __future__ import annotations

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "it": {
        # Dashboard
        "dashboard.titolo": "Dashboard",
        "dashboard.fratelli_attivi": "Fratelli attivi",
        "dashboard.famiglie": "Famiglie",
        "dashboard.capacita_totale": "Capacita' totale",
        "dashboard.domanda_mensile": "Domanda mensile",
        "dashboard.bilancio": "Bilancio (cap-dom)",
        "dashboard.mesi_storico": "Mesi nello storico",
        "dashboard.tutto_ok": "Tutto in ordine. Il sistema e' pronto per l'ottimizzazione.",

        # Anagrafica
        "anagrafica.titolo": "Anagrafica",
        "anagrafica.fratello": "Fratello",
        "anagrafica.famiglia": "Famiglia",
        "anagrafica.aggiungi_fratello": "Aggiungi Fratello",
        "anagrafica.aggiungi_famiglia": "Aggiungi Famiglia",
        "anagrafica.associa": "Associa",
        "anagrafica.frequenza": "Frequenza (1/2/4)",
        "anagrafica.capacita": "Capacita' visite mensili (massimo)",
        "anagrafica.elimina": "Elimina",
        "anagrafica.importa_csv": "Importa CSV",

        # Pianificazione
        "pianificazione.titolo": "Pianificazione",
        "pianificazione.mesi": "Mesi (YYYY-MM) separati da virgola",
        "pianificazione.cooldown": "Cooldown (mesi)",
        "pianificazione.ottimizza": "Ottimizza & Genera PDF",
        "pianificazione.pre_check": "Pre-check fattibilita'",
        "pianificazione.esporta_csv": "Esporta CSV",
        "pianificazione.in_corso": "Ottimizzazione in corso...",
        "pianificazione.nessuna_soluzione": "Nessuna soluzione trovata.",
        "pianificazione.conferma": "Conferma e salva",
        "pianificazione.annulla": "Annulla",

        # Storico
        "storico.titolo": "Storico",
        "storico.aggiorna": "Aggiorna",
        "storico.elimina": "Elimina selezionato",
        "storico.esporta": "Esporta storico CSV",
        "storico.dettaglio": "Dettaglio assegnazioni",

        # Avanzate
        "avanzate.titolo": "Avanzate",
        "avanzate.indisponibilita": "Indisponibilita'",
        "avanzate.vincoli": "Vincoli",
        "avanzate.backup": "Backup",
        "avanzate.statistiche": "Statistiche",
        "avanzate.audit": "Audit Trail",

        # Generico
        "errore": "Errore",
        "conferma": "Conferma",
        "info": "Informazione",
        "pronto": "Pronto",
    },
    "en": {
        # Dashboard
        "dashboard.titolo": "Dashboard",
        "dashboard.fratelli_attivi": "Active brothers",
        "dashboard.famiglie": "Families",
        "dashboard.capacita_totale": "Total capacity",
        "dashboard.domanda_mensile": "Monthly demand",
        "dashboard.bilancio": "Balance (cap-dem)",
        "dashboard.mesi_storico": "History months",
        "dashboard.tutto_ok": "All good. The system is ready for optimization.",

        # Anagrafica
        "anagrafica.titolo": "Registry",
        "anagrafica.fratello": "Brother",
        "anagrafica.famiglia": "Family",
        "anagrafica.aggiungi_fratello": "Add Brother",
        "anagrafica.aggiungi_famiglia": "Add Family",
        "anagrafica.associa": "Associate",
        "anagrafica.frequenza": "Frequency (1/2/4)",
        "anagrafica.capacita": "Monthly visit capacity (max)",
        "anagrafica.elimina": "Delete",
        "anagrafica.importa_csv": "Import CSV",

        # Pianificazione
        "pianificazione.titolo": "Planning",
        "pianificazione.mesi": "Months (YYYY-MM) comma-separated",
        "pianificazione.cooldown": "Cooldown (months)",
        "pianificazione.ottimizza": "Optimize & Generate PDF",
        "pianificazione.pre_check": "Feasibility pre-check",
        "pianificazione.esporta_csv": "Export CSV",
        "pianificazione.in_corso": "Optimization in progress...",
        "pianificazione.nessuna_soluzione": "No solution found.",
        "pianificazione.conferma": "Confirm and save",
        "pianificazione.annulla": "Cancel",

        # Storico
        "storico.titolo": "History",
        "storico.aggiorna": "Refresh",
        "storico.elimina": "Delete selected",
        "storico.esporta": "Export history CSV",
        "storico.dettaglio": "Assignment details",

        # Avanzate
        "avanzate.titolo": "Advanced",
        "avanzate.indisponibilita": "Unavailability",
        "avanzate.vincoli": "Constraints",
        "avanzate.backup": "Backup",
        "avanzate.statistiche": "Statistics",
        "avanzate.audit": "Audit Trail",

        # Generic
        "errore": "Error",
        "conferma": "Confirm",
        "info": "Information",
        "pronto": "Ready",
    },
}

_current_language = "it"


def set_language(lang: str) -> None:
    """Imposta la lingua corrente (es. 'it', 'en')."""
    global _current_language
    if lang not in _TRANSLATIONS:
        raise ValueError(f"Lingua non supportata: {lang}. Disponibili: {list(_TRANSLATIONS.keys())}")
    _current_language = lang


def get_language() -> str:
    return _current_language


def get_available_languages() -> list[str]:
    return list(_TRANSLATIONS.keys())


def t(key: str) -> str:
    """Ritorna la traduzione per la chiave data nella lingua corrente."""
    translations = _TRANSLATIONS.get(_current_language, _TRANSLATIONS["it"])
    return translations.get(key, key)
