"""
Repository JSON per fratelli, famiglie, associazioni, frequenze, capacita
e storico turni confermati.

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
        """
        Salva le assegnazioni di un mese nello storico.
        Solleva ValidazioneError se il mese e' malformato,
        StoricoConflittoError se il mese e' gia' presente.
        """
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
        self.save()
        logging.info("Turni confermati salvati nello storico: %s (n=%d)", mese, len(cleaned))

    def delete_storico_mese(self, mese: str) -> None:
        """Rimuove un mese dallo storico. Solleva EntitaNonTrovata se assente."""
        before = len(self.storico_turni)
        self.storico_turni = [
            r for r in self.storico_turni
            if not (isinstance(r, dict) and r.get("mese") == mese)
        ]
        if len(self.storico_turni) == before:
            raise EntitaNonTrovata(f"Mese {mese} non trovato nello storico.")
        self.save()
        logging.info("Rimosso mese dallo storico: %s", mese)

    # ------------------------------------------------------------------
    # CRUD — fratelli
    # ------------------------------------------------------------------

    def add_brother(self, nome: str) -> str:
        """
        Aggiunge un fratello. Ritorna il nome canonico.
        Solleva ValidazioneError se il nome non e' valido,
        DuplicatoError se gia' presente.
        """
        nf = canonicalizza_nome(nome)
        if not nf:
            raise ValidazioneError(f"Nome fratello non valido: '{nome}'.")
        if nf in self.fratelli:
            raise DuplicatoError(f"Fratello gia' presente: '{nf}'.")
        self.fratelli.add(nf)
        self.capacita.setdefault(nf, 1)
        self.save()
        logging.info("Aggiunto fratello: %s (cap=1)", nf)
        return nf

    def remove_brother(self, nome: str) -> None:
        """Rimuove un fratello e ripulisce le associazioni. Solleva EntitaNonTrovata."""
        nf = self._require_fratello(nome)
        self.fratelli.remove(nf)
        self.capacita.pop(nf, None)
        for fam, lst in list(self.associazioni.items()):
            if nf in lst:
                nuova = [x for x in lst if x != nf]
                if nuova:
                    self.associazioni[fam] = nuova
                else:
                    del self.associazioni[fam]
        self.save()
        logging.info("Rimosso fratello: %s (associazioni ripulite)", nf)

    def set_brother_capacity(self, nome: str, cap: int) -> None:
        """Imposta la capacita' mensile del fratello. Solleva ValidazioneError."""
        nf = self._require_fratello(nome)
        if not isinstance(cap, int) or not (0 <= cap <= 50):
            raise ValidazioneError(
                f"Capacita' non valida per '{nf}': usa un intero 0..50."
            )
        self.capacita[nf] = cap
        self.save()
        logging.info("Capacita' %s = %d visite/mese", nf, cap)

    # ------------------------------------------------------------------
    # CRUD — famiglie
    # ------------------------------------------------------------------

    def add_family(self, nome: str) -> str:
        """
        Aggiunge una famiglia. Ritorna il nome canonico.
        Solleva ValidazioneError se il nome non e' valido,
        DuplicatoError se gia' presente.
        """
        fam = canonicalizza_nome(nome)
        if not fam:
            raise ValidazioneError(f"Nome famiglia non valido: '{nome}'.")
        if fam in self.famiglie:
            raise DuplicatoError(f"Famiglia gia' presente: '{fam}'.")
        self.famiglie.add(fam)
        self.frequenze.setdefault(fam, 2)
        self.save()
        logging.info("Aggiunta famiglia: %s (freq 2)", fam)
        return fam

    def remove_family(self, nome: str) -> None:
        """Rimuove una famiglia e le sue associazioni/frequenza. Solleva EntitaNonTrovata."""
        fam = self._require_famiglia(nome)
        self.famiglie.remove(fam)
        self.associazioni.pop(fam, None)
        self.frequenze.pop(fam, None)
        self.save()
        logging.info("Rimossa famiglia: %s", fam)

    def set_frequency(self, famiglia: str, freq: int) -> None:
        """Imposta la frequenza mensile della famiglia. Solleva ValidazioneError."""
        fam = self._require_famiglia(famiglia)
        if freq not in (1, 2, 4):
            raise ValidazioneError(
                f"Frequenza non valida per '{fam}': usa 1, 2 o 4."
            )
        self.frequenze[fam] = freq
        self.save()
        logging.info("Frequenza %s = %d/mese", fam, freq)

    # ------------------------------------------------------------------
    # CRUD — associazioni
    # ------------------------------------------------------------------

    def associate(self, nome_fratello: str, nome_famiglia: str) -> None:
        """
        Associa un fratello a una famiglia.
        Solleva EntitaNonTrovata se l'uno o l'altro non esiste,
        DuplicatoError se l'associazione e' gia' presente.
        """
        nf = self._require_fratello(nome_fratello)
        fam = self._require_famiglia(nome_famiglia)
        self.associazioni.setdefault(fam, [])
        if nf in self.associazioni[fam]:
            raise DuplicatoError(
                f"'{nf}' e' gia' associato alla famiglia '{fam}'."
            )
        self.associazioni[fam].append(nf)
        self.save()
        logging.info("Associato %s -> %s", nf, fam)

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
        """
        Scrive il JSON su disco in modo atomico: scrive prima su un file
        temporaneo nella stessa directory e poi lo sostituisce con os.replace().
        Questo garantisce che il file principale non sia mai in stato parziale.
        """
        dati = {
            "schema_version": 1,
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
        }
        dir_ = os.path.dirname(os.path.abspath(self.filename))
        fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp", prefix=".turni_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(dati, f, indent=4, ensure_ascii=False)
            os.replace(tmp_path, self.filename)
        except Exception:
            # Pulizia del file temporaneo in caso di errore
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
        """
        Normalizza tutti i nomi e applica le mappature alias.
        Solleva TurniVisiteError in caso di errore interno.
        """
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

            # Aggiorna i nomi anche nello storico turni
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
            self.storico_turni = storico_new
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
        }
