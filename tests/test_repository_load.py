"""Test per JsonRepository.load() — retrocompatibilità, campi malformati, schema v1."""
import json
import pytest
from turni_visite.repository import JsonRepository
from turni_visite.domain import TurniVisiteError


class TestLoadSchemaV1:
    def test_carica_senza_schema_version(self, tmp_path):
        data = {
            "fratelli": ["Mario Rossi"],
            "famiglie": ["Famiglia Verdi"],
            "associazioni": {"Famiglia Verdi": ["Mario Rossi"]},
            "frequenze": {"Famiglia Verdi": 2},
            "capacita": {"Mario Rossi": 1},
            "settings": {"cooldown_mesi": 3},
            "storico_turni": [],
        }
        f = tmp_path / "v1.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert "Mario Rossi" in repo.fratelli
        assert repo.indisponibilita == {}
        assert repo.vincoli_personalizzati == []
        assert repo.week_templates == {}
        assert repo.audit_log == []

    def test_carica_schema_version_zero(self, tmp_path):
        data = {
            "schema_version": 0,
            "fratelli": ["Mario"],
            "famiglie": [],
            "associazioni": {},
            "frequenze": {},
            "capacita": {},
            "settings": {},
            "storico_turni": [],
        }
        f = tmp_path / "v0.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert "Mario" in repo.fratelli


class TestLoadMalformedFields:
    def test_storico_turni_non_lista(self, tmp_path):
        data = {
            "schema_version": 2,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {}, "settings": {},
            "storico_turni": "non_una_lista",
        }
        f = tmp_path / "bad_storico.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert repo.storico_turni == []

    def test_settings_non_dict(self, tmp_path):
        data = {
            "schema_version": 2,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {},
            "settings": "non_un_dict",
            "storico_turni": [],
        }
        f = tmp_path / "bad_settings.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert repo.settings == {"cooldown_mesi": 3}  # default ricostruito

    def test_indisponibilita_non_dict(self, tmp_path):
        data = {
            "schema_version": 2,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {}, "settings": {},
            "storico_turni": [],
            "indisponibilita": [1, 2, 3],
        }
        f = tmp_path / "bad_indisp.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert repo.indisponibilita == {}

    def test_vincoli_non_lista(self, tmp_path):
        data = {
            "schema_version": 2,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {}, "settings": {},
            "storico_turni": [],
            "vincoli_personalizzati": {"bad": True},
        }
        f = tmp_path / "bad_vincoli.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert repo.vincoli_personalizzati == []

    def test_week_templates_non_dict(self, tmp_path):
        data = {
            "schema_version": 2,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {}, "settings": {},
            "storico_turni": [],
            "week_templates": "bad",
        }
        f = tmp_path / "bad_wt.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert repo.week_templates == {}

    def test_audit_log_non_lista(self, tmp_path):
        data = {
            "schema_version": 2,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {}, "settings": {},
            "storico_turni": [],
            "audit_log": 42,
        }
        f = tmp_path / "bad_audit.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert repo.audit_log == []

    def test_cooldown_non_numerico(self, tmp_path):
        data = {
            "schema_version": 2,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {},
            "settings": {"cooldown_mesi": "abc"},
            "storico_turni": [],
        }
        f = tmp_path / "bad_cooldown.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert repo.settings["cooldown_mesi"] == 3


class TestLoadRetrocompat:
    def test_reload_scarta_stato_in_memoria(self, tmp_path):
        f = tmp_path / "data.json"
        repo = JsonRepository(str(f))
        repo.add_brother("Mario")
        repo.fratelli.add("Fantasma")

        repo.reload()

        assert "Mario" in repo.fratelli
        assert "Fantasma" not in repo.fratelli

    def test_capacita_default_per_fratelli_senza(self, tmp_path):
        data = {
            "schema_version": 2,
            "fratelli": ["Mario", "Luigi"],
            "famiglie": [],
            "associazioni": {},
            "frequenze": {},
            "capacita": {"Mario": 5},
            "settings": {},
            "storico_turni": [],
        }
        f = tmp_path / "partial_cap.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert repo.capacita["Mario"] == 5
        assert repo.capacita["Luigi"] == 1

    def test_frequenza_default_per_famiglie_senza(self, tmp_path):
        data = {
            "schema_version": 2,
            "fratelli": [],
            "famiglie": ["Fam A", "Fam B"],
            "associazioni": {},
            "frequenze": {"Fam A": 4},
            "capacita": {},
            "settings": {},
            "storico_turni": [],
        }
        f = tmp_path / "partial_freq.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert repo.frequenze["Fam A"] == 4
        assert repo.frequenze["Fam B"] == 2

    def test_campi_nuovi_assenti_in_file_vecchio(self, tmp_path):
        data = {
            "fratelli": ["Mario"],
            "famiglie": [],
            "associazioni": {},
            "frequenze": {},
            "capacita": {"Mario": 1},
            "settings": {},
            "storico_turni": [],
        }
        f = tmp_path / "old.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(str(f))
        assert repo.indisponibilita == {}
        assert repo.vincoli_personalizzati == []
        assert repo.week_templates == {}
        assert repo.audit_log == []

    def test_json_corrotto_errore(self, tmp_path):
        f = tmp_path / "corrupted.json"
        f.write_text("{broken json", encoding="utf-8")
        with pytest.raises(TurniVisiteError, match="corrotto"):
            JsonRepository(str(f))

    def test_file_non_leggibile(self, tmp_path):
        import os
        f = tmp_path / "noperm.json"
        f.write_text('{"fratelli":[]}')
        os.chmod(str(f), 0o000)
        try:
            with pytest.raises(TurniVisiteError):
                JsonRepository(str(f))
        finally:
            os.chmod(str(f), 0o644)
