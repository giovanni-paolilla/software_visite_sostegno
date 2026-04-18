"""
Repository JSON per fratelli, famiglie, associazioni, frequenze, capacita,
storico turni confermati, indisponibilita', vincoli personalizzati e
template settimane.

Tutti i metodi CRUD sollevano eccezioni di dominio (da .domain) invece
di stampare su stdout, rendendo il repository testabile e disaccoppiato
dalla UI.

Il metodo ``save()`` usa una scrittura atomica (write + os.replace) per
garantire che il file JSON non venga mai lasciato in stato parzialmente
scritto in caso di interruzione del processo.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from .domain import (
    TurniVisiteError,
    EntitaNonTrovata,
    DuplicatoError,
    ValidazioneError,
    StoricoConflittoError,
)
from .normalization import canonicalizza_nome


class JsonRepository:
    def __init__(self, filename: str | Path) -> None:
        self.filename: str | Path = filename
        self.fratelli: set[str] = set()
        self.famiglie: set[str] = set()
        self.associazioni: dict[str, list[str]] = {}
        self.frequenze: dict[str, int] = {}
        self.capacita: dict[str, int] = {}
        # record: {mese, created_at, confirmed_at, assegnazioni:[{famiglia, fratello, slot}]}
        self.storico_turni: list[dict] = []
        self.settings: dict = {"cooldown_mesi": 3}
        # Indisponibilita' temporanee: {fratello: [lista mesi YYYY-MM]}
        self.indisponibilita: dict[str, list[str]] = {}
        # Vincoli personalizzati: [{fratello_a, fratello_b, tipo, descrizione}]
        self.vincoli_personalizzati: list[dict] = []
        # Template finestre settimanali per frequenza: {freq: [intervalli]}
        self.week_templates: dict[str, list[str]] = {}
        # Audit trail: [{timestamp, azione, dettagli, utente}]
        self.audit_log: list[dict] = []
        self.load()

    # ------------------------------------------------------------------
    # Utilita' interne
    # ------------------------------------------------------------------

    @staticmethod
    def _now_iso() -> str:
        return datetime.now().replace(microsecond=0).isoformat()

    def _require_fratello(self, nome: str) -> str:
        """Ritorna il nome canonico o solleva EntitaNonTrovata."""
        nf = canonicalizza_nome(nome)
        if not nf or nf not in self.fratelli:
            raise EntitaNonTrovata(f"Fratello non trovato: '{nome}'.")
        return nf

    def _require_famiglia(self, nome: str) -> str:
        """Ritorna il nome canonico o solleva EntitaNonTrovata."""
        fam = canonicalizza_nome(nome)
        if not fam or fam not in self.famiglie:
            raise EntitaNonTrovata(f"Famiglia non trovata: '{nome}'.")
        return fam

    def _log_audit(self, azione: str, dettagli: str) -> None:
        """Registra un evento nell'audit trail."""
        self.audit_log.append({
            "timestamp": self._now_iso(),
            "azione": azione,
            "dettagli": dettagli,
        })
        # Mantieni solo gli ultimi 500 eventi
        if len(self.audit_log) > 500:
            self.audit_log = self.audit_log[-500:]

    # ------------------------------------------------------------------
    # Storico turni
    # ------------------------------------------------------------------

    def get_storico_turni(self) -> list[dict]:
        return list(self.storico_turni)

    def storico_has_mese(self, mese: str) -> bool:
        return any(
            isinstance(r, dict) and r.get("mese") == mese
            for r in self.storico_turni
        )

    def append_storico_turni(self, mese: str, assegnazioni: list[dict]) -> None:
        if not mese or not isinstance(mese, str):
            raise ValidazioneError("Mese non valido.")
        if self.storico_has_mese(mese):
            raise StoricoConflittoError(
                f"Il mese {mese} e' gia' nello storico. "
                "Rimuovilo prima se vuoi rigenerarlo."
            )
        cleaned: list[dict] = []
        for a in assegnazioni or []:
            fam = canonicalizza_nome(a.get("famiglia", ""))
            fr = canonicalizza_nome(a.get("fratello", ""))
            try:
                slot = int(a.get("slot", 0))
            except (TypeError, ValueError):
                slot = 0
            if fam and fr:
                cleaned.append({"famiglia": fam, "fratello": fr, "slot": slot})

        rec = {
            "mese": mese,
            "created_at": self._now_iso(),
            "confirmed_at": self._now_iso(),
            "assegnazioni": cleaned,
        }
        self.storico_turni.append(rec)
        self._log_audit("conferma_turni", f"Confermati turni mese {mese} ({len(cleaned)} assegnazioni)")
        self.save()
        logging.info("Turni confermati salvati nello storico: %s (n=%d)", mese, len(cleaned))

    def delete_storico_mese(self, mese: str) -> None:
        before = len(self.storico_turni)
        self.storico_turni = [
            r for r in self.storico_turni
            if not (isinstance(r, dict) and r.get("mese") == mese)
        ]
        if len(self.storico_turni) == before:
            raise EntitaNonTrovata(f"Mese {mese} non trovato nello storico.")
        self._log_audit("elimina_storico", f"Rimosso mese {mese} dallo storico")
        self.save()
        logging.info("Rimosso mese dallo storico: %s", mese)

    # ------------------------------------------------------------------
    # CRUD — fratelli
    # ------------------------------------------------------------------

    def add_brother(self, nome: str) -> str:
        nf = canonicalizza_nome(nome)
        if not nf:
            raise ValidazioneError(f"Nome fratello non valido: '{nome}'.")
        if nf in self.fratelli:
            raise DuplicatoError(f"Fratello gia' presente: '{nf}'.")
        self.fratelli.add(nf)
        self.capacita.setdefault(nf, 1)
        self._log_audit("aggiungi_fratello", f"Aggiunto fratello: {nf}")
        self.save()
        logging.info("Aggiunto fratello: %s (cap=1)", nf)
        return nf

    def remove_brother(self, nome: str) -> None:
        nf = self._require_fratello(nome)
        self.fratelli.remove(nf)
        self.capacita.pop(nf, None)
        self.indisponibilita.pop(nf, None)
        # Rimuovi dai vincoli personalizzati
        self.vincoli_personalizzati = [
            v for v in self.vincoli_personalizzati
            if v.get("fratello_a") != nf and v.get("fratello_b") != nf
        ]
        for fam, lst in list(self.associazioni.items()):
            if nf in lst:
                nuova = [x for x in lst if x != nf]
                if nuova:
                    self.associazioni[fam] = nuova
                else:
                    del self.associazioni[fam]
        self._log_audit("rimuovi_fratello", f"Rimosso fratello: {nf}")
        self.save()
        logging.info("Rimosso fratello: %s (associazioni ripulite)", nf)

    def set_brother_capacity(self, nome: str, cap: int) -> None:
        nf = self._require_fratello(nome)
        if not isinstance(cap, int) or not (0 <= cap <= 50):
            raise ValidazioneError(
                f"Capacita' non valida per '{nf}': usa un intero 0..50."
            )
        old_cap = self.capacita.get(nf, 1)
        self.capacita[nf] = cap
        self._log_audit("modifica_capacita", f"Capacita' {nf}: {old_cap} -> {cap}")
        self.save()
        logging.info("Capacita' %s = %d visite/mese", nf, cap)

    # ------------------------------------------------------------------
    # CRUD — famiglie
    # ------------------------------------------------------------------

    def add_family(self, nome: str) -> str:
        fam = canonicalizza_nome(nome)
        if not fam:
            raise ValidazioneError(f"Nome famiglia non valido: '{nome}'.")
        if fam in self.famiglie:
            raise DuplicatoError(f"Famiglia gia' presente: '{fam}'.")
        self.famiglie.add(fam)
        self.frequenze.setdefault(fam, 2)
        self._log_audit("aggiungi_famiglia", f"Aggiunta famiglia: {fam}")
        self.save()
        logging.info("Aggiunta famiglia: %s (freq 2)", fam)
        return fam

    def remove_family(self, nome: str) -> None:
        fam = self._require_famiglia(nome)
        self.famiglie.remove(fam)
        self.associazioni.pop(fam, None)
        self.frequenze.pop(fam, None)
        self._log_audit("rimuovi_famiglia", f"Rimossa famiglia: {fam}")
        self.save()
        logging.info("Rimossa famiglia: %s", fam)

    def set_frequency(self, famiglia: str, freq: int) -> None:
        fam = self._require_famiglia(famiglia)
        if freq not in (1, 2, 4):
            raise ValidazioneError(
                f"Frequenza non valida per '{fam}': usa 1, 2 o 4."
            )
        old_freq = self.frequenze.get(fam, 2)
        self.frequenze[fam] = freq
        self._log_audit("modifica_frequenza", f"Frequenza {fam}: {old_freq} -> {freq}")
        self.save()
        logging.info("Frequenza %s = %d/mese", fam, freq)

    # ------------------------------------------------------------------
    # CRUD — associazioni
    # ------------------------------------------------------------------

    def associate(self, nome_fratello: str, nome_famiglia: str) -> None:
        nf = self._require_fratello(nome_fratello)
        fam = self._require_famiglia(nome_famiglia)
        self.associazioni.setdefault(fam, [])
        if nf in self.associazioni[fam]:
            raise DuplicatoError(
                f"'{nf}' e' gia' associato alla famiglia '{fam}'."
            )
        self.associazioni[fam].append(nf)
        self._log_audit("associazione", f"Associato {nf} -> {fam}")
        self.save()
        logging.info("Associato %s -> %s", nf, fam)

    def disassociate(self, nome_fratello: str, nome_famiglia: str) -> None:
        """Rimuove l'associazione tra un fratello e una famiglia."""
        nf = self._require_fratello(nome_fratello)
        fam = self._require_famiglia(nome_famiglia)
        if fam not in self.associazioni or nf not in self.associazioni[fam]:
            raise EntitaNonTrovata(
                f"'{nf}' non e' associato alla famiglia '{fam}'."
            )
        self.associazioni[fam].remove(nf)
        if not self.associazioni[fam]:
            del self.associazioni[fam]
        self._log_audit("disassociazione", f"Rimossa associazione {nf} -> {fam}")
        self.save()
        logging.info("Disassociato %s da %s", nf, fam)

    # ------------------------------------------------------------------
    # Indisponibilita' temporanee
    # ------------------------------------------------------------------

    def set_indisponibilita(self, nome: str, mesi: list[str]) -> None:
        """Imposta i mesi di indisponibilita' per un fratello."""
        nf = self._require_fratello(nome)
        self.indisponibilita[nf] = sorted(set(mesi))
        self._log_audit("indisponibilita", f"Indisponibilita' {nf}: {', '.join(mesi) if mesi else 'nessuna'}")
        self.save()
        logging.info("Indisponibilita' %s: %s", nf, mesi)

    def get_indisponibilita(self, nome: str) -> list[str]:
        nf = self._require_fratello(nome)
        return list(self.indisponibilita.get(nf, []))

    def add_indisponibilita(self, nome: str, mese: str) -> None:
        """Aggiunge un mese di indisponibilita'."""
        nf = self._require_fratello(nome)
        current = self.indisponibilita.get(nf, [])
        if mese not in current:
            current.append(mese)
            self.indisponibilita[nf] = sorted(current)
            self._log_audit("aggiungi_indisponibilita", f"Indisponibilita' aggiunta: {nf} per {mese}")
            self.save()

    def remove_indisponibilita(self, nome: str, mese: str) -> None:
        """Rimuove un mese di indisponibilita'."""
        nf = self._require_fratello(nome)
        current = self.indisponibilita.get(nf, [])
        if mese in current:
            current.remove(mese)
            self.indisponibilita[nf] = current
            self._log_audit("rimuovi_indisponibilita", f"Indisponibilita' rimossa: {nf} per {mese}")
            self.save()

    # ------------------------------------------------------------------
    # Vincoli personalizzati
    # ------------------------------------------------------------------

    def add_vincolo(self, fratello_a: str, fratello_b: str, tipo: str, descrizione: str = "") -> None:
        """Aggiunge un vincolo personalizzato tra due fratelli."""
        fa = self._require_fratello(fratello_a)
        fb = self._require_fratello(fratello_b)
        if fa == fb:
            raise ValidazioneError("Non puoi creare un vincolo di un fratello con se stesso.")
        if tipo not in ("incompatibile", "preferenza_coppia"):
            raise ValidazioneError(f"Tipo vincolo non valido: '{tipo}'. Usa 'incompatibile' o 'preferenza_coppia'.")
        # Controlla duplicati
        for v in self.vincoli_personalizzati:
            if {v.get("fratello_a"), v.get("fratello_b")} == {fa, fb} and v.get("tipo") == tipo:
                raise DuplicatoError(f"Vincolo gia' esistente tra '{fa}' e '{fb}' ({tipo}).")
        self.vincoli_personalizzati.append({
            "fratello_a": fa,
            "fratello_b": fb,
            "tipo": tipo,
            "descrizione": descrizione,
        })
        self._log_audit("aggiungi_vincolo", f"Vincolo {tipo}: {fa} <-> {fb}")
        self.save()
        logging.info("Vincolo %s aggiunto: %s <-> %s", tipo, fa, fb)

    def remove_vincolo(self, fratello_a: str, fratello_b: str, tipo: str) -> None:
        """Rimuove un vincolo personalizzato."""
        fa = self._require_fratello(fratello_a)
        fb = self._require_fratello(fratello_b)
        before = len(self.vincoli_personalizzati)
        self.vincoli_personalizzati = [
            v for v in self.vincoli_personalizzati
            if not ({v.get("fratello_a"), v.get("fratello_b")} == {fa, fb} and v.get("tipo") == tipo)
        ]
        if len(self.vincoli_personalizzati) == before:
            raise EntitaNonTrovata(f"Vincolo {tipo} tra '{fa}' e '{fb}' non trovato.")
        self._log_audit("rimuovi_vincolo", f"Rimosso vincolo {tipo}: {fa} <-> {fb}")
        self.save()

    def get_vincoli(self, tipo: str | None = None) -> list[dict]:
        if tipo:
            return [v for v in self.vincoli_personalizzati if v.get("tipo") == tipo]
        return list(self.vincoli_personalizzati)

    # ------------------------------------------------------------------
    # Week templates
    # ------------------------------------------------------------------

    def set_week_template(self, freq: int, intervalli: list[str]) -> None:
        """Salva il template di finestre settimanali per una frequenza."""
        if freq not in (1, 2, 4):
            raise ValidazioneError(f"Frequenza non valida: {freq}")
        self.week_templates[str(freq)] = intervalli
        self.save()
        logging.info("Template settimane freq %d: %s", freq, intervalli)

    def get_week_template(self, freq: int) -> list[str] | None:
        return self.week_templates.get(str(freq))

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        return list(reversed(self.audit_log[-limit:]))

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def get_setting(self, key: str, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key: str, value) -> None:
        self.settings[key] = value
        self.save()

    # ------------------------------------------------------------------
    # Persistenza (atomica)
    # ------------------------------------------------------------------

    def save(self) -> None:
        dati = {
            "schema_version": 2,
            "fratelli": sorted(self.fratelli),
            "famiglie": sorted(self.famiglie),
            "associazioni": {
                k: sorted(self.associazioni[k])
                for k in sorted(self.associazioni)
            },
            "frequenze": self.frequenze,
            "capacita": self.capacita,
            "settings": self.settings,
            "storico_turni": self.storico_turni,
            "indisponibilita": self.indisponibilita,
            "vincoli_personalizzati": self.vincoli_personalizzati,
            "week_templates": self.week_templates,
            "audit_log": self.audit_log,
        }
        dir_ = os.path.dirname(os.path.abspath(self.filename))
        fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp", prefix=".turni_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(dati, f, indent=4, ensure_ascii=False)
            os.replace(tmp_path, self.filename)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def load(self) -> None:
        if not os.path.exists(self.filename):
            logging.warning("%s assente: avvio con dataset vuoto.", self.filename)
            return
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                dati = json.load(f)
            schema_version = dati.get("schema_version", 0)
            if schema_version < 1:
                logging.warning(
                    "File dati senza schema_version: formato legacy, caricamento compatibile."
                )
            self.fratelli = set(dati.get("fratelli", []))
            self.famiglie = set(dati.get("famiglie", []))
            self.associazioni = dati.get("associazioni", {})
            self.frequenze = dati.get("frequenze", {})
            self.capacita = dati.get("capacita", {})
            raw_storico = dati.get("storico_turni", [])
            self.storico_turni = raw_storico if isinstance(raw_storico, list) else []
            raw_settings = dati.get("settings", {})
            self.settings = raw_settings if isinstance(raw_settings, dict) else {}
            try:
                self.settings["cooldown_mesi"] = int(self.settings.get("cooldown_mesi", 3))
            except (TypeError, ValueError):
                self.settings["cooldown_mesi"] = 3
            # Nuovi campi (schema v2, compatibilita' con v1)
            raw_indisp = dati.get("indisponibilita", {})
            self.indisponibilita = raw_indisp if isinstance(raw_indisp, dict) else {}
            raw_vincoli = dati.get("vincoli_personalizzati", [])
            self.vincoli_personalizzati = raw_vincoli if isinstance(raw_vincoli, list) else []
            raw_wt = dati.get("week_templates", {})
            self.week_templates = raw_wt if isinstance(raw_wt, dict) else {}
            raw_audit = dati.get("audit_log", [])
            self.audit_log = raw_audit if isinstance(raw_audit, list) else []
            # default per retrocompatibilita'
            for fr in self.fratelli:
                self.capacita.setdefault(fr, 1)
            for fam in self.famiglie:
                self.frequenze.setdefault(fam, 2)
        except json.JSONDecodeError as e:
            logging.error("Errore di parsing JSON in %s: %s", self.filename, e)
            raise TurniVisiteError(
                f"Il file dati '{self.filename}' e' corrotto (JSON non valido): {e}"
            ) from e
        except OSError as e:
            logging.error("Errore I/O caricamento %s: %s", self.filename, e)
            raise TurniVisiteError(
                f"Impossibile leggere il file dati '{self.filename}': {e}"
            ) from e

    # ------------------------------------------------------------------
    # Sanificazione (normalizzazione + alias)
    # ------------------------------------------------------------------

    def sanitize(self, alias_map: dict[str, str]) -> None:
        try:
            fr_new: set[str] = set()
            for n in self.fratelli:
                c = canonicalizza_nome(n)
                if c:
                    fr_new.add(alias_map.get(c, c))

            fam_new: set[str] = set()
            for n in self.famiglie:
                c = canonicalizza_nome(n)
                if c:
                    fam_new.add(alias_map.get(c, c))

            assoc_new: dict[str, list[str]] = {}
            for fam, frs in self.associazioni.items():
                fam_c = canonicalizza_nome(fam)
                fam_c = alias_map.get(fam_c, fam_c) if fam_c else None
                if not fam_c or fam_c not in fam_new:
                    continue
                dest: list[str] = []
                for fr in frs:
                    fr_c = canonicalizza_nome(fr)
                    fr_c = alias_map.get(fr_c, fr_c) if fr_c else None
                    if fr_c and fr_c in fr_new and fr_c not in dest:
                        dest.append(fr_c)
                if dest:
                    assoc_new[fam_c] = sorted(dest)

            freq_new = {
                fam: (v if v in (1, 2, 4) else 2)
                for fam in fam_new
                for v in (self.frequenze.get(fam, 2),)
            }

            cap_new: dict[str, int] = {}
            for fr in fr_new:
                try:
                    v = int(self.capacita.get(fr, 1))
                    cap_new[fr] = v if 0 <= v <= 50 else 1
                except (TypeError, ValueError):
                    cap_new[fr] = 1

            # Aggiorna i nomi nelle indisponibilita'
            indisp_new: dict[str, list[str]] = {}
            for fr, mesi in self.indisponibilita.items():
                fr_c = canonicalizza_nome(fr)
                fr_c = alias_map.get(fr_c, fr_c) if fr_c else None
                if fr_c and fr_c in fr_new:
                    indisp_new[fr_c] = mesi

            # Aggiorna i nomi nei vincoli
            vincoli_new: list[dict] = []
            for v in self.vincoli_personalizzati:
                fa = canonicalizza_nome(v.get("fratello_a", ""))
                fa = alias_map.get(fa, fa) if fa else None
                fb = canonicalizza_nome(v.get("fratello_b", ""))
                fb = alias_map.get(fb, fb) if fb else None
                if fa and fb and fa in fr_new and fb in fr_new:
                    vincoli_new.append({
                        "fratello_a": fa, "fratello_b": fb,
                        "tipo": v.get("tipo", "incompatibile"),
                        "descrizione": v.get("descrizione", ""),
                    })

            # Aggiorna i nomi nello storico turni
            storico_new: list[dict] = []
            for rec in self.storico_turni:
                if not isinstance(rec, dict):
                    continue
                ass_new_list: list[dict] = []
                for a in rec.get("assegnazioni", []) or []:
                    if not isinstance(a, dict):
                        continue
                    fam_a = canonicalizza_nome(a.get("famiglia", ""))
                    fam_a = alias_map.get(fam_a, fam_a) if fam_a else None
                    fr_a = canonicalizza_nome(a.get("fratello", ""))
                    fr_a = alias_map.get(fr_a, fr_a) if fr_a else None
                    if fam_a and fr_a:
                        try:
                            slot = int(a.get("slot", 0))
                        except (TypeError, ValueError):
                            slot = 0
                        ass_new_list.append({"famiglia": fam_a, "fratello": fr_a, "slot": slot})
                storico_new.append({
                    "mese": rec.get("mese"),
                    "created_at": rec.get("created_at"),
                    "confirmed_at": rec.get("confirmed_at"),
                    "assegnazioni": ass_new_list,
                })

            self.fratelli = fr_new
            self.famiglie = fam_new
            self.associazioni = assoc_new
            self.frequenze = freq_new
            self.capacita = cap_new
            self.indisponibilita = indisp_new
            self.vincoli_personalizzati = vincoli_new
            self.storico_turni = storico_new
            self._log_audit("sanificazione", f"Dati sanificati con {len(alias_map)} alias")
            self.save()
            logging.info("Dati sanificati e salvati in %s.", self.filename)
        except (TurniVisiteError, OSError):
            raise
        except Exception as e:
            logging.error("Sanificazione fallita: %s", e)
            raise TurniVisiteError(f"Errore durante la sanificazione: {e}") from e

    # ------------------------------------------------------------------
    # Snapshot (snapshot isolato per il solver)
    # ------------------------------------------------------------------

    def data_snapshot(self) -> dict:
        """Ritorna una copia profonda dei dati correnti, sicura per thread separati."""
        return {
            "fratelli": set(self.fratelli),
            "famiglie": set(self.famiglie),
            "associazioni": {k: list(v) for k, v in self.associazioni.items()},
            "frequenze": dict(self.frequenze),
            "capacita": dict(self.capacita),
            "indisponibilita": {k: list(v) for k, v in self.indisponibilita.items()},
            "vincoli_personalizzati": [dict(v) for v in self.vincoli_personalizzati],
        }

    # ------------------------------------------------------------------
    # Dashboard KPI
    # ------------------------------------------------------------------

    def get_dashboard_kpi(self) -> dict:
        """Calcola i KPI per la dashboard."""
        fratelli_attivi = [f for f in self.fratelli if self.capacita.get(f, 1) > 0]
        cap_totale = sum(self.capacita.get(f, 1) for f in fratelli_attivi)
        domanda_totale = sum(self.frequenze.get(f, 2) for f in self.famiglie)
        fam_senza_assoc = [f for f in self.famiglie if not self.associazioni.get(f)]
        fratelli_senza_assoc = [
            f for f in self.fratelli
            if not any(f in lst for lst in self.associazioni.values())
        ]
        mesi_storico = sorted(
            r.get("mese", "") for r in self.storico_turni if isinstance(r, dict)
        )
        return {
            "n_fratelli": len(self.fratelli),
            "n_fratelli_attivi": len(fratelli_attivi),
            "n_famiglie": len(self.famiglie),
            "capacita_totale": cap_totale,
            "domanda_totale": domanda_totale,
            "bilancio": cap_totale - domanda_totale,
            "famiglie_senza_associazione": fam_senza_assoc,
            "fratelli_senza_associazione": fratelli_senza_assoc,
            "n_mesi_storico": len(mesi_storico),
            "ultimo_mese_storico": mesi_storico[-1] if mesi_storico else None,
            "n_vincoli": len(self.vincoli_personalizzati),
            "n_indisponibilita": sum(len(v) for v in self.indisponibilita.values()),
        }
