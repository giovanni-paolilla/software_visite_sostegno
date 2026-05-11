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

import logging
import threading

_i18n_lock = threading.Lock()

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "it": {
        # Dashboard
        "dashboard.titolo": "Dashboard",
        "dashboard.fratelli_attivi": "Fratelli attivi",
        "dashboard.famiglie": "Famiglie",
        "dashboard.capacita_totale": "Capacita' totale",
        "dashboard.domanda_mensile": "Domanda mensile",
        "dashboard.bilancio": "Bilancio (cap-dom)",
        "dashboard.mesi_storico": "Mesi storico",
        "dashboard.tutto_ok": "Tutto in ordine. Il sistema e' pronto per l'ottimizzazione.",
        "dashboard.avvisi": "Avvisi e suggerimenti",
        "dashboard.ultimo_mese": "Ultimo mese pianificato",
        "dashboard.nessun_mese": "Nessun mese nello storico",

        # Anagrafica
        "anagrafica.titolo": "Anagrafica",
        "anagrafica.fratello": "Fratello:",
        "anagrafica.famiglia": "Famiglia:",
        "anagrafica.aggiungi_fratello": "Aggiungi Fratello",
        "anagrafica.aggiungi_famiglia": "Aggiungi Famiglia",
        "anagrafica.associa": "Associa",
        "anagrafica.frequenza": "Frequenza (1/2/4)",
        "anagrafica.capacita": "Capacita' visite mensili",
        "anagrafica.capacita_label": "Cap (0-50):",
        "anagrafica.elimina": "Elimina",
        "anagrafica.elimina_fratello": "Elimina Fratello:",
        "anagrafica.elimina_famiglia": "Elimina Famiglia:",
        "anagrafica.importa_csv": "Importa CSV",
        "anagrafica.per_famiglia": "per famiglia:",
        "anagrafica.imposta": "Imposta",
        "anagrafica.fratelli": "Fratelli:",
        "anagrafica.famiglie": "Famiglie:",

        # Pianificazione
        "pianificazione.titolo": "Pianificazione",
        "pianificazione.mesi": "Mesi (YYYY-MM, virgola):",
        "pianificazione.cooldown": "Cooldown:",
        "pianificazione.timeout": "Timeout (s):",
        "pianificazione.thread": "Thread:",
        "pianificazione.ottimizza": "Ottimizza & Genera PDF",
        "pianificazione.pre_check": "Pre-check fattibilita'",
        "pianificazione.esporta_csv": "Esporta CSV",
        "pianificazione.salva_template": "Salva template settimane",
        "pianificazione.in_corso": "Ottimizzazione in corso...",
        "pianificazione.nessuna_soluzione": "Nessuna soluzione trovata.",
        "pianificazione.conferma": "Conferma piano",
        "pianificazione.conferma_domanda": "Confermare il piano e generare il PDF?",
        "pianificazione.annullata": "Operazione annullata.",

        # Storico
        "storico.titolo": "Storico",
        "storico.mesi_confermati": "Mesi confermati nello storico",
        "storico.aggiorna": "Aggiorna",
        "storico.elimina": "Elimina selezionato",
        "storico.esporta": "Esporta storico CSV",
        "storico.dettaglio": "Dettaglio assegnazioni",

        # Calendario
        "calendario.titolo": "Calendario",
        "calendario.intestazione": "Calendario visite (da storico)",
        "calendario.nessun_dato": "Nessun dato nello storico.",
        "calendario.famiglia": "Famiglia",
        "calendario.legenda": "Legenda:",

        # Avanzate
        "avanzate.titolo": "Avanzate",
        "avanzate.indisponibilita": "Indisponibilita'",
        "avanzate.vincoli": "Vincoli",
        "avanzate.backup": "Backup",
        "avanzate.statistiche": "Statistiche",
        "avanzate.audit": "Audit Trail",
        "avanzate.fratello": "Fratello:",
        "avanzate.mese": "Mese (YYYY-MM):",
        "avanzate.aggiungi": "Aggiungi",
        "avanzate.rimuovi": "Rimuovi",
        "avanzate.fratello_a": "Fratello A:",
        "avanzate.fratello_b": "Fratello B:",
        "avanzate.tipo": "Tipo:",
        "avanzate.rimuovi_selezionato": "Rimuovi selezionato",
        "avanzate.crea_backup": "Crea backup ora",
        "avanzate.ripristina": "Ripristina selezionato",
        "avanzate.aggiorna_lista": "Aggiorna lista",
        "avanzate.carico_fratelli": "Carico fratelli",
        "avanzate.copertura_famiglie": "Copertura famiglie",
        "avanzate.indice_equita": "Indice equita'",
        "avanzate.trend_mensile": "Trend mensile",
        "avanzate.ultimi_eventi": "Ultimi 50 eventi",

        # Notifiche
        "notifiche.titolo": "Notifiche",
        "notifiche.invia_email": "Invia email turni",
        "notifiche.config_smtp": "Configurazione SMTP",
        "notifiche.host": "Host SMTP:",
        "notifiche.porta": "Porta:",
        "notifiche.utente": "Utente:",
        "notifiche.password": "Password:",
        "notifiche.mittente": "Mittente:",
        "notifiche.salva_config": "Salva configurazione",
        "notifiche.email_fratelli": "Email fratelli",

        # Pianificazione estesa
        "pianificazione.copia_whatsapp": "Copia WhatsApp",
        "pianificazione.whatsapp_copiato": "Testo copiato negli appunti!",
        "pianificazione.modifica": "Modifica assegnazione",
        "pianificazione.mese_edit": "Mese:",
        "pianificazione.famiglia_edit": "Famiglia:",
        "pianificazione.slot_edit": "Slot:",
        "pianificazione.nuovo_fratello": "Nuovo fratello:",
        "pianificazione.applica_modifica": "Applica",
        "pianificazione.salva_bozza": "Salva come bozza",
        "pianificazione.conferma_selezionati": "Conferma selezionati",
        "pianificazione.scarta_bozza": "Scarta bozza",
        "pianificazione.accetta_tutti": "Accetta tutti",
        "pianificazione.rifiuta_tutti": "Rifiuta tutti",

        # Sostituzione
        "sostituzione.titolo": "Sostituzione d'emergenza",
        "sostituzione.fratello_malato": "Fratello da sostituire:",
        "sostituzione.cerca": "Cerca sostituto",
        "sostituzione.candidati": "Candidati disponibili:",
        "sostituzione.applica": "Applica sostituzione",
        "sostituzione.nessun_candidato": "Nessun candidato disponibile.",

        # Esecuzione
        "esecuzione.completata": "Completata",
        "esecuzione.annullata": "Annullata",
        "esecuzione.pianificata": "Pianificata",
        "esecuzione.segna_completata": "Segna completata",
        "esecuzione.segna_annullata": "Segna annullata",

        # Affinita'
        "avanzate.affinita": "Affinita'",
        "avanzate.famiglia_aff": "Famiglia:",
        "avanzate.fratello_aff": "Fratello:",
        "avanzate.peso": "Peso (-10..+10):",
        "avanzate.aggiungi_affinita": "Imposta affinita'",
        "avanzate.rimuovi_affinita": "Rimuovi",

        # Generico
        "errore": "Errore",
        "conferma": "Conferma",
        "annulla": "Annulla",
        "info": "Informazione",
        "pronto": "Pronto",
        "aggiorna": "Aggiorna",
        "tema": "Tema:",
        "lingua": "Lingua:",
        "stampa": "Stampa",
        "operazione_riuscita": "Operazione riuscita.",
        "salvato": "Salvato.",
        "aggiunto": "Aggiunto.",
        "rimosso": "Rimosso.",
        "seleziona_fratello_famiglia": "Seleziona sia Fratello sia Famiglia.",
        "nome_vuoto": "Il nome non puo' essere vuoto.",
        "duplicato": "Elemento gia' presente.",
        "nome_fratello": "Nome fratello",
        "nome_famiglia": "Nome famiglia",

        # Tab avanzate extra
        "smtp_configurazione": "Configurazione SMTP salvata.",
        "backup_ripristinato": "Backup ripristinato.",
        "indisponibilita_aggiunta": "Indisponibilita' aggiunta.",

        # Tab pianificazione extra
        "ottimizzazione_corso": "Ottimizzazione in corso...",
        "soluzione_trovata": "Soluzione trovata.",
        "bozza_salvata": "Bozza salvata.",
        "pre_check_ok": "Pre-check OK: nessun problema rilevato.",

        # Tab storico extra
        "stato_esecuzione": "Stato esecuzione:",
        "confermato": "Confermato",
        "mese_label": "Mese:",
        "famiglia_label": "Famiglia:",
        "slot_label": "Slot:",

        # Tab dashboard extra
        "famiglie_senza_fratelli": "Famiglie senza fratelli associati",
        "fratelli_non_associati": "Fratelli non associati",

        # Dialog
        "importa_csv": "Importa CSV",
        "configura_settimane": "Configurazione settimane",
        "import_completato": "Import completato",

        # Stampa
        "documento_inviato": "Documento inviato alla stampante.",
        "riavvia_per_lingua": "Riavvia l'applicazione per applicare la nuova lingua.",
        "nessuna_soluzione_stampa": "Nessuna soluzione da stampare.",
        "errore_stampa": "Errore stampa",
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
        "dashboard.avvisi": "Warnings and suggestions",
        "dashboard.ultimo_mese": "Last planned month",
        "dashboard.nessun_mese": "No months in history",

        # Anagrafica
        "anagrafica.titolo": "Registry",
        "anagrafica.fratello": "Brother:",
        "anagrafica.famiglia": "Family:",
        "anagrafica.aggiungi_fratello": "Add Brother",
        "anagrafica.aggiungi_famiglia": "Add Family",
        "anagrafica.associa": "Associate",
        "anagrafica.frequenza": "Frequency (1/2/4)",
        "anagrafica.capacita": "Monthly visit capacity",
        "anagrafica.capacita_label": "Cap (0-50):",
        "anagrafica.elimina": "Delete",
        "anagrafica.elimina_fratello": "Delete Brother:",
        "anagrafica.elimina_famiglia": "Delete Family:",
        "anagrafica.importa_csv": "Import CSV",
        "anagrafica.per_famiglia": "for family:",
        "anagrafica.imposta": "Set",
        "anagrafica.fratelli": "Brothers:",
        "anagrafica.famiglie": "Families:",

        # Pianificazione
        "pianificazione.titolo": "Planning",
        "pianificazione.mesi": "Months (YYYY-MM, comma):",
        "pianificazione.cooldown": "Cooldown:",
        "pianificazione.timeout": "Timeout (s):",
        "pianificazione.thread": "Thread:",
        "pianificazione.ottimizza": "Optimize & Generate PDF",
        "pianificazione.pre_check": "Feasibility pre-check",
        "pianificazione.esporta_csv": "Export CSV",
        "pianificazione.salva_template": "Save week templates",
        "pianificazione.in_corso": "Optimization in progress...",
        "pianificazione.nessuna_soluzione": "No solution found.",
        "pianificazione.conferma": "Confirm plan",
        "pianificazione.conferma_domanda": "Confirm plan and generate PDF?",
        "pianificazione.annullata": "Operation cancelled.",

        # Storico
        "storico.titolo": "History",
        "storico.mesi_confermati": "Confirmed months in history",
        "storico.aggiorna": "Refresh",
        "storico.elimina": "Delete selected",
        "storico.esporta": "Export history CSV",
        "storico.dettaglio": "Assignment details",

        # Calendario
        "calendario.titolo": "Calendar",
        "calendario.intestazione": "Visit calendar (from history)",
        "calendario.nessun_dato": "No data in history.",
        "calendario.famiglia": "Family",
        "calendario.legenda": "Legend:",

        # Avanzate
        "avanzate.titolo": "Advanced",
        "avanzate.indisponibilita": "Unavailability",
        "avanzate.vincoli": "Constraints",
        "avanzate.backup": "Backup",
        "avanzate.statistiche": "Statistics",
        "avanzate.audit": "Audit Trail",
        "avanzate.fratello": "Brother:",
        "avanzate.mese": "Month (YYYY-MM):",
        "avanzate.aggiungi": "Add",
        "avanzate.rimuovi": "Remove",
        "avanzate.fratello_a": "Brother A:",
        "avanzate.fratello_b": "Brother B:",
        "avanzate.tipo": "Type:",
        "avanzate.rimuovi_selezionato": "Remove selected",
        "avanzate.crea_backup": "Create backup now",
        "avanzate.ripristina": "Restore selected",
        "avanzate.aggiorna_lista": "Refresh list",
        "avanzate.carico_fratelli": "Brother workload",
        "avanzate.copertura_famiglie": "Family coverage",
        "avanzate.indice_equita": "Equity index",
        "avanzate.trend_mensile": "Monthly trend",
        "avanzate.ultimi_eventi": "Last 50 events",

        # Notifiche
        "notifiche.titolo": "Notifications",
        "notifiche.invia_email": "Send shift emails",
        "notifiche.config_smtp": "SMTP Configuration",
        "notifiche.host": "SMTP Host:",
        "notifiche.porta": "Port:",
        "notifiche.utente": "User:",
        "notifiche.password": "Password:",
        "notifiche.mittente": "Sender:",
        "notifiche.salva_config": "Save configuration",
        "notifiche.email_fratelli": "Brother emails",

        # Planning extended
        "pianificazione.copia_whatsapp": "Copy WhatsApp",
        "pianificazione.whatsapp_copiato": "Text copied to clipboard!",
        "pianificazione.modifica": "Edit assignment",
        "pianificazione.mese_edit": "Month:",
        "pianificazione.famiglia_edit": "Family:",
        "pianificazione.slot_edit": "Slot:",
        "pianificazione.nuovo_fratello": "New brother:",
        "pianificazione.applica_modifica": "Apply",
        "pianificazione.salva_bozza": "Save as draft",
        "pianificazione.conferma_selezionati": "Confirm selected",
        "pianificazione.scarta_bozza": "Discard draft",
        "pianificazione.accetta_tutti": "Accept all",
        "pianificazione.rifiuta_tutti": "Reject all",

        # Substitution
        "sostituzione.titolo": "Emergency substitution",
        "sostituzione.fratello_malato": "Brother to replace:",
        "sostituzione.cerca": "Find substitute",
        "sostituzione.candidati": "Available candidates:",
        "sostituzione.applica": "Apply substitution",
        "sostituzione.nessun_candidato": "No candidates available.",

        # Execution
        "esecuzione.completata": "Completed",
        "esecuzione.annullata": "Cancelled",
        "esecuzione.pianificata": "Planned",
        "esecuzione.segna_completata": "Mark completed",
        "esecuzione.segna_annullata": "Mark cancelled",

        # Affinity
        "avanzate.affinita": "Affinity",
        "avanzate.famiglia_aff": "Family:",
        "avanzate.fratello_aff": "Brother:",
        "avanzate.peso": "Weight (-10..+10):",
        "avanzate.aggiungi_affinita": "Set affinity",
        "avanzate.rimuovi_affinita": "Remove",

        # Generic
        "errore": "Error",
        "conferma": "Confirm",
        "annulla": "Cancel",
        "info": "Information",
        "pronto": "Ready",
        "aggiorna": "Refresh",
        "tema": "Theme:",
        "lingua": "Language:",
        "stampa": "Print",
        "operazione_riuscita": "Operation successful.",
        "salvato": "Saved.",
        "aggiunto": "Added.",
        "rimosso": "Removed.",
        "seleziona_fratello_famiglia": "Select both Brother and Family.",
        "nome_vuoto": "Name cannot be empty.",
        "duplicato": "Element already exists.",
        "nome_fratello": "Brother name",
        "nome_famiglia": "Family name",

        # Advanced tab extra
        "smtp_configurazione": "SMTP configuration saved.",
        "backup_ripristinato": "Backup restored.",
        "indisponibilita_aggiunta": "Unavailability added.",

        # Planning tab extra
        "ottimizzazione_corso": "Optimization in progress...",
        "soluzione_trovata": "Solution found.",
        "bozza_salvata": "Draft saved.",
        "pre_check_ok": "Pre-check OK: no issues found.",

        # History tab extra
        "stato_esecuzione": "Execution status:",
        "confermato": "Confirmed",
        "mese_label": "Month:",
        "famiglia_label": "Family:",
        "slot_label": "Slot:",

        # Dashboard tab extra
        "famiglie_senza_fratelli": "Families without associated brothers",
        "fratelli_non_associati": "Unassociated brothers",

        # Dialog
        "importa_csv": "Import CSV",
        "configura_settimane": "Week configuration",
        "import_completato": "Import completed",

        # Print
        "documento_inviato": "Document sent to printer.",
        "riavvia_per_lingua": "Restart the application to apply the new language.",
        "nessuna_soluzione_stampa": "No solution to print.",
        "errore_stampa": "Print error",
    },
}

_current_language = "it"


def set_language(lang: str) -> None:
    """Imposta la lingua corrente (es. 'it', 'en')."""
    global _current_language
    if lang not in _TRANSLATIONS:
        raise ValueError(f"Lingua non supportata: {lang}. Disponibili: {list(_TRANSLATIONS.keys())}")
    with _i18n_lock:
        _current_language = lang


def get_language() -> str:
    with _i18n_lock:
        return _current_language


def get_available_languages() -> list[str]:
    return list(_TRANSLATIONS.keys())


def t(key: str) -> str:
    """Ritorna la traduzione per la chiave data nella lingua corrente."""
    with _i18n_lock:
        lang = _current_language
    translations = _TRANSLATIONS.get(lang, _TRANSLATIONS["it"])
    result = translations.get(key)
    if result is None:
        logging.warning("Chiave i18n mancante per lingua '%s': %s", lang, key)
        return key
    return result


def validate_i18n_completeness() -> dict[str, list[str]]:
    """
    Valida la completezza dei file di traduzione.
    Ritorna un dict {lingua: [chiavi_mancanti]} per lingue incomplete.
    """
    all_keys = set()
    for lang_dict in _TRANSLATIONS.values():
        all_keys.update(lang_dict.keys())
    missing = {}
    for lang, lang_dict in _TRANSLATIONS.items():
        m = [k for k in all_keys if k not in lang_dict]
        if m:
            missing[lang] = sorted(m)
    return missing
