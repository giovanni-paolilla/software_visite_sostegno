"""Test per repository — metodi e error paths non coperti."""
import json
import pytest
from turni_visite.repository import JsonRepository
from turni_visite.domain import (
    EntitaNonTrovata, ValidazioneError, DuplicatoError,
    StoricoConflittoError, TurniVisiteError,
)


@pytest.fixture
def repo(tmp_path):
    r = JsonRepository(str(tmp_path / "repo_gaps.json"))
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_family("Famiglia Verdi")
    r.add_family("Famiglia Blu")
    r.associate("Mario Rossi", "Famiglia Verdi")
    r.associate("Luigi Bianchi", "Famiglia Verdi")
    return r


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettings:
    def test_get_setting_default(self, repo):
        assert repo.get_setting("nonexistent", 42) == 42

    def test_get_setting_existing(self, repo):
        assert repo.get_setting("cooldown_mesi") == 3

    def test_set_setting(self, repo):
        repo.set_setting("custom_key", "custom_value")
        assert repo.get_setting("custom_key") == "custom_value"

    def test_set_setting_persisted(self, repo):
        repo.set_setting("test_persist", True)
        r2 = JsonRepository(repo.filename)
        assert r2.get_setting("test_persist") is True

    def test_set_setting_overwrite(self, repo):
        repo.set_setting("key", "v1")
        repo.set_setting("key", "v2")
        assert repo.get_setting("key") == "v2"


# ---------------------------------------------------------------------------
# Week templates
# ---------------------------------------------------------------------------

class TestWeekTemplates:
    def test_get_template_non_esistente(self, repo):
        assert repo.get_week_template(1) is None

    def test_set_e_get_template(self, repo):
        repo.set_week_template(2, ["01-07", "15-21"])
        assert repo.get_week_template(2) == ["01-07", "15-21"]

    def test_set_template_freq_non_valida(self, repo):
        with pytest.raises(ValidazioneError):
            repo.set_week_template(3, ["01-07"])

    def test_template_persistito(self, repo):
        repo.set_week_template(4, ["01-07", "08-14", "15-21", "22-28"])
        r2 = JsonRepository(repo.filename)
        assert r2.get_week_template(4) == ["01-07", "08-14", "15-21", "22-28"]


# ---------------------------------------------------------------------------
# Bozza turni
# ---------------------------------------------------------------------------

class TestBozzaTurni:
    def test_get_bozza_vuota(self, repo):
        assert repo.get_bozza() is None

    def test_save_bozza(self, repo):
        solution = {
            "by_month": {
                "2026-01": {
                    "by_family": {
                        "Famiglia Verdi": ["Mario Rossi", "Luigi Bianchi"],
                    }
                }
            }
        }
        repo.save_bozza(["2026-01"], solution)
        bozza = repo.get_bozza()
        assert bozza is not None
        assert bozza["mesi"] == ["2026-01"]
        assert len(bozza["assegnazioni"]) == 2
        assert all(a["stato"] == "proposto" for a in bozza["assegnazioni"])

    def test_save_bozza_ignora_non_assegnato(self, repo):
        from turni_visite.domain import NON_ASSEGNATO
        solution = {
            "by_month": {
                "2026-01": {
                    "by_family": {
                        "Famiglia Verdi": [NON_ASSEGNATO, "Mario Rossi"],
                    }
                }
            }
        }
        repo.save_bozza(["2026-01"], solution)
        bozza = repo.get_bozza()
        assert len(bozza["assegnazioni"]) == 1
        assert bozza["assegnazioni"][0]["fratello"] == "Mario Rossi"

    def test_update_bozza_stato(self, repo):
        solution = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi"]}
                }
            }
        }
        repo.save_bozza(["2026-01"], solution)
        repo.update_bozza_stato("2026-01", "Famiglia Verdi", 0, "accettato")
        bozza = repo.get_bozza()
        assert bozza["assegnazioni"][0]["stato"] == "accettato"

    def test_update_bozza_stato_invalido(self, repo):
        solution = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi"]}
                }
            }
        }
        repo.save_bozza(["2026-01"], solution)
        with pytest.raises(ValidazioneError, match="Stato bozza non valido"):
            repo.update_bozza_stato("2026-01", "Famiglia Verdi", 0, "invalido")

    def test_update_bozza_senza_bozza(self, repo):
        with pytest.raises(EntitaNonTrovata, match="Nessuna bozza"):
            repo.update_bozza_stato("2026-01", "F", 0, "accettato")

    def test_update_bozza_assegnazione_non_trovata(self, repo):
        solution = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi"]}
                }
            }
        }
        repo.save_bozza(["2026-01"], solution)
        with pytest.raises(EntitaNonTrovata, match="non trovata in bozza"):
            repo.update_bozza_stato("2026-01", "Famiglia Verdi", 99, "accettato")

    def test_conferma_bozza_tutto_accettato(self, repo):
        solution = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi"]}
                }
            }
        }
        repo.save_bozza(["2026-01"], solution)
        repo.update_bozza_stato("2026-01", "Famiglia Verdi", 0, "accettato")
        result = repo.conferma_bozza()
        assert "2026-01" in result["salvati"]
        assert repo.get_bozza() is None
        assert repo.storico_has_mese("2026-01")

    def test_conferma_bozza_tutto_rifiutato(self, repo):
        solution = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi"]}
                }
            }
        }
        repo.save_bozza(["2026-01"], solution)
        repo.update_bozza_stato("2026-01", "Famiglia Verdi", 0, "rifiutato")
        result = repo.conferma_bozza()
        assert result == {"salvati": [], "saltati": []}
        assert repo.get_bozza() is None

    def test_conferma_bozza_senza_bozza(self, repo):
        with pytest.raises(EntitaNonTrovata, match="Nessuna bozza"):
            repo.conferma_bozza()

    def test_conferma_bozza_mese_gia_in_storico(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        solution = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Famiglia Verdi": ["Luigi Bianchi"]}
                }
            }
        }
        repo.save_bozza(["2026-01"], solution)
        repo.update_bozza_stato("2026-01", "Famiglia Verdi", 0, "accettato")
        result = repo.conferma_bozza()
        assert "2026-01" not in result["salvati"]

    def test_discard_bozza(self, repo):
        solution = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi"]}
                }
            }
        }
        repo.save_bozza(["2026-01"], solution)
        repo.discard_bozza()
        assert repo.get_bozza() is None

    def test_bozza_persistita(self, repo):
        solution = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi"]}
                }
            }
        }
        repo.save_bozza(["2026-01"], solution)
        r2 = JsonRepository(repo.filename)
        assert r2.get_bozza() is not None

    def test_save_bozza_multi_mese(self, repo):
        solution = {
            "by_month": {
                "2026-01": {"by_family": {"Famiglia Verdi": ["Mario Rossi"]}},
                "2026-02": {"by_family": {"Famiglia Verdi": ["Luigi Bianchi"]}},
            }
        }
        repo.save_bozza(["2026-01", "2026-02"], solution)
        bozza = repo.get_bozza()
        assert len(bozza["assegnazioni"]) == 2
        mesi = {a["mese"] for a in bozza["assegnazioni"]}
        assert mesi == {"2026-01", "2026-02"}


# ---------------------------------------------------------------------------
# Stato esecuzione
# ---------------------------------------------------------------------------

class TestStatoEsecuzione:
    def test_set_completato(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        repo.set_stato_esecuzione("2026-01", "Famiglia Verdi", 0, "completato")
        storico = repo.get_storico_turni()
        a = storico[0]["assegnazioni"][0]
        assert a["stato_esecuzione"] == "completato"

    def test_set_annullato(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        repo.set_stato_esecuzione("2026-01", "Famiglia Verdi", 0, "annullato")
        storico = repo.get_storico_turni()
        assert storico[0]["assegnazioni"][0]["stato_esecuzione"] == "annullato"

    def test_stato_invalido(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with pytest.raises(ValidazioneError, match="non valido"):
            repo.set_stato_esecuzione("2026-01", "Famiglia Verdi", 0, "invalido")

    def test_assegnazione_non_trovata(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with pytest.raises(EntitaNonTrovata):
            repo.set_stato_esecuzione("2026-01", "Famiglia Verdi", 99, "completato")

    def test_mese_non_trovato(self, repo):
        with pytest.raises(EntitaNonTrovata):
            repo.set_stato_esecuzione("2099-01", "Famiglia Verdi", 0, "completato")

    def test_transizione_stato(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        repo.set_stato_esecuzione("2026-01", "Famiglia Verdi", 0, "completato")
        repo.set_stato_esecuzione("2026-01", "Famiglia Verdi", 0, "pianificato")
        storico = repo.get_storico_turni()
        assert storico[0]["assegnazioni"][0]["stato_esecuzione"] == "pianificato"

    def test_persistenza_stato(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        repo.set_stato_esecuzione("2026-01", "Famiglia Verdi", 0, "completato")
        r2 = JsonRepository(repo.filename)
        storico = r2.get_storico_turni()
        assert storico[0]["assegnazioni"][0]["stato_esecuzione"] == "completato"


# ---------------------------------------------------------------------------
# update_storico_assegnazione (sostituzione)
# ---------------------------------------------------------------------------

class TestUpdateStoricoAssegnazione:
    def test_sostituzione_ok(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        repo.update_storico_assegnazione("2026-01", "Famiglia Verdi", 0,
                                          "Mario Rossi", "Luigi Bianchi")
        storico = repo.get_storico_turni()
        assert storico[0]["assegnazioni"][0]["fratello"] == "Luigi Bianchi"

    def test_sostituzione_assegnazione_non_trovata(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with pytest.raises(EntitaNonTrovata):
            repo.update_storico_assegnazione("2026-01", "Famiglia Verdi", 99,
                                              "Mario Rossi", "Luigi Bianchi")

    def test_sostituzione_nuovo_fratello_non_esiste(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with pytest.raises(EntitaNonTrovata, match="Fratello non trovato"):
            repo.update_storico_assegnazione("2026-01", "Famiglia Verdi", 0,
                                              "Mario Rossi", "Fantasma")

    def test_sostituzione_mese_non_trovato(self, repo):
        with pytest.raises(EntitaNonTrovata):
            repo.update_storico_assegnazione("2099-01", "Famiglia Verdi", 0,
                                              "Mario Rossi", "Luigi Bianchi")

    def test_sostituzione_fallback_slot_zero(self, repo):
        # Il fallback "slot==0 quando non trovato" e' stato rimosso:
        # ora viene sollevata EntitaNonTrovata se non c'e' match esatto.
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 1},
        ])
        with pytest.raises(EntitaNonTrovata):
            repo.update_storico_assegnazione("2026-01", "Famiglia Verdi", 0,
                                              "Mario Rossi", "Luigi Bianchi")
        # L'assegnazione originale resta invariata
        storico = repo.get_storico_turni()
        assert storico[0]["assegnazioni"][0]["fratello"] == "Mario Rossi"
        assert storico[0]["assegnazioni"][0]["slot"] == 1

    def test_audit_log_sostituzione(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        repo.update_storico_assegnazione("2026-01", "Famiglia Verdi", 0,
                                          "Mario Rossi", "Luigi Bianchi")
        log = repo.get_audit_log(1)
        assert log[0]["azione"] == "sostituzione"


# ---------------------------------------------------------------------------
# Affinita
# ---------------------------------------------------------------------------

class TestAffinitaCRUD:
    def test_add_affinita(self, repo):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 5)
        affinita = repo.get_affinita()
        assert len(affinita) == 1
        assert affinita[0]["peso"] == 5

    def test_add_affinita_update_existing(self, repo):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 5)
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", -3)
        affinita = repo.get_affinita()
        assert len(affinita) == 1
        assert affinita[0]["peso"] == -3

    def test_add_affinita_peso_fuori_range(self, repo):
        with pytest.raises(ValidazioneError, match="(?i)peso"):
            repo.add_affinita("Famiglia Verdi", "Mario Rossi", 15)

    def test_add_affinita_peso_meno_11(self, repo):
        with pytest.raises(ValidazioneError):
            repo.add_affinita("Famiglia Verdi", "Mario Rossi", -11)

    def test_add_affinita_boundary_valid(self, repo):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 10)
        repo.add_affinita("Famiglia Verdi", "Luigi Bianchi", -10)
        affinita = repo.get_affinita()
        pesi = {a["peso"] for a in affinita}
        assert pesi == {10, -10}

    def test_remove_affinita(self, repo):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 5)
        repo.remove_affinita("Famiglia Verdi", "Mario Rossi")
        assert repo.get_affinita() == []

    def test_remove_affinita_non_trovata(self, repo):
        with pytest.raises(EntitaNonTrovata, match="non trovata"):
            repo.remove_affinita("Famiglia Verdi", "Mario Rossi")

    def test_affinita_persisted(self, repo):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 7)
        r2 = JsonRepository(repo.filename)
        assert len(r2.get_affinita()) == 1

    def test_remove_brother_cleans_affinita(self, repo):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 5)
        repo.remove_brother("Mario Rossi")
        assert repo.get_affinita() == []

    def test_remove_family_cleans_affinita(self, repo):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 5)
        repo.remove_family("Famiglia Verdi")
        assert repo.get_affinita() == []

    def test_get_affinita_vuota(self, repo):
        assert repo.get_affinita() == []


# ---------------------------------------------------------------------------
# remove_indisponibilita
# ---------------------------------------------------------------------------

class TestRemoveIndisponibilita:
    def test_remove_ok(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-05")
        repo.remove_indisponibilita("Mario Rossi", "2026-05")
        assert "2026-05" not in repo.get_indisponibilita("Mario Rossi")

    def test_remove_mese_non_presente(self, repo):
        repo.remove_indisponibilita("Mario Rossi", "2026-05")

    def test_remove_fratello_non_esistente(self, repo):
        with pytest.raises(EntitaNonTrovata):
            repo.remove_indisponibilita("Fantasma", "2026-05")


# ---------------------------------------------------------------------------
# data_snapshot
# ---------------------------------------------------------------------------

class TestDataSnapshot:
    def test_snapshot_contiene_tutti_i_campi(self, repo):
        snap = repo.data_snapshot()
        assert "fratelli" in snap
        assert "famiglie" in snap
        assert "associazioni" in snap
        assert "frequenze" in snap
        assert "capacita" in snap
        assert "indisponibilita" in snap
        assert "vincoli_personalizzati" in snap
        assert "affinita" in snap

    def test_snapshot_isolato(self, repo):
        snap = repo.data_snapshot()
        snap["fratelli"].add("Intruso")
        assert "Intruso" not in repo.fratelli

    def test_snapshot_con_affinita(self, repo):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 3)
        snap = repo.data_snapshot()
        assert len(snap["affinita"]) == 1
        snap["affinita"].append({"test": True})
        assert len(repo.get_affinita()) == 1


# ---------------------------------------------------------------------------
# disassociate edge — cancella chiave se lista vuota
# ---------------------------------------------------------------------------

class TestDisassociateCleanup:
    def test_disassociate_rimuove_chiave_vuota(self, repo):
        repo.associate("Mario Rossi", "Famiglia Blu")
        repo.disassociate("Mario Rossi", "Famiglia Blu")
        assert "Famiglia Blu" not in repo.associazioni

    def test_disassociate_mantiene_altri(self, repo):
        repo.associate("Mario Rossi", "Famiglia Blu")
        repo.associate("Luigi Bianchi", "Famiglia Blu")
        repo.disassociate("Mario Rossi", "Famiglia Blu")
        assert "Famiglia Blu" in repo.associazioni
        assert "Luigi Bianchi" in repo.associazioni["Famiglia Blu"]


# ---------------------------------------------------------------------------
# reload
# ---------------------------------------------------------------------------

class TestReload:
    def test_reload_ripristina_stato(self, repo):
        repo.add_brother("Nuovo")
        repo.reload()
        assert "Nuovo" in repo.fratelli

    def test_reload_dopo_modifica_esterna(self, repo, tmp_path):
        data = json.loads(open(repo.filename).read())
        data["fratelli"].append("Esterno")
        data["capacita"]["Esterno"] = 1
        with open(repo.filename, "w") as f:
            json.dump(data, f)
        repo.reload()
        assert "Esterno" in repo.fratelli


# ---------------------------------------------------------------------------
# Load edge cases
# ---------------------------------------------------------------------------

class TestLoadEdge:
    def test_load_storico_non_lista(self, tmp_path):
        f = tmp_path / "edge.json"
        f.write_text(json.dumps({
            "schema_version": 3,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {}, "settings": {},
            "storico_turni": "not_a_list",
            "indisponibilita": {}, "vincoli_personalizzati": [],
            "week_templates": {}, "audit_log": [],
            "affinita": [], "bozza_turni": None,
        }))
        r = JsonRepository(str(f))
        assert r.storico_turni == []

    def test_load_settings_non_dict(self, tmp_path):
        f = tmp_path / "edge2.json"
        f.write_text(json.dumps({
            "schema_version": 3,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {}, "settings": "invalid",
            "storico_turni": [],
            "indisponibilita": {}, "vincoli_personalizzati": [],
            "week_templates": {}, "audit_log": [],
            "affinita": [], "bozza_turni": None,
        }))
        r = JsonRepository(str(f))
        assert isinstance(r.settings, dict)
        assert r.settings["cooldown_mesi"] == 3

    def test_load_affinita_non_lista(self, tmp_path):
        f = tmp_path / "edge3.json"
        f.write_text(json.dumps({
            "schema_version": 3,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {}, "settings": {},
            "storico_turni": [],
            "indisponibilita": {}, "vincoli_personalizzati": [],
            "week_templates": {}, "audit_log": [],
            "affinita": "not_list", "bozza_turni": None,
        }))
        r = JsonRepository(str(f))
        assert r.affinita == []

    def test_load_bozza_non_dict(self, tmp_path):
        f = tmp_path / "edge4.json"
        f.write_text(json.dumps({
            "schema_version": 3,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {}, "settings": {},
            "storico_turni": [],
            "indisponibilita": {}, "vincoli_personalizzati": [],
            "week_templates": {}, "audit_log": [],
            "affinita": [], "bozza_turni": "not_dict",
        }))
        r = JsonRepository(str(f))
        assert r.bozza_turni is None

    def test_load_cooldown_non_numerico(self, tmp_path):
        f = tmp_path / "edge5.json"
        f.write_text(json.dumps({
            "schema_version": 3,
            "fratelli": [], "famiglie": [], "associazioni": {},
            "frequenze": {}, "capacita": {}, "settings": {"cooldown_mesi": "abc"},
            "storico_turni": [],
            "indisponibilita": {}, "vincoli_personalizzati": [],
            "week_templates": {}, "audit_log": [],
            "affinita": [], "bozza_turni": None,
        }))
        r = JsonRepository(str(f))
        assert r.settings["cooldown_mesi"] == 3


# ---------------------------------------------------------------------------
# Dashboard KPI edge cases
# ---------------------------------------------------------------------------

class TestDashboardKPI:
    def test_kpi_vuoto(self, tmp_path):
        r = JsonRepository(str(tmp_path / "kpi_vuoto.json"))
        kpi = r.get_dashboard_kpi()
        assert kpi["n_fratelli"] == 0
        assert kpi["bilancio"] == 0
        assert kpi["ultimo_mese_storico"] is None

    def test_kpi_con_fratello_cap_zero(self, repo):
        repo.set_brother_capacity("Mario Rossi", 0)
        kpi = repo.get_dashboard_kpi()
        assert kpi["n_fratelli_attivi"] < kpi["n_fratelli"]

    def test_kpi_famiglie_senza_assoc(self, repo):
        kpi = repo.get_dashboard_kpi()
        assert "Famiglia Blu" in kpi["famiglie_senza_associazione"]

    def test_kpi_ultimo_mese(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        kpi = repo.get_dashboard_kpi()
        assert kpi["ultimo_mese_storico"] == "2026-01"
        assert kpi["n_mesi_storico"] == 1


# ---------------------------------------------------------------------------
# Sanitize affinita
# ---------------------------------------------------------------------------

class TestSanitizeAffinita:
    def test_sanitize_aggiorna_affinita(self, repo):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 5)
        repo.sanitize({"Mario Rossi": "Marco Rossi"})
        affinita = repo.get_affinita()
        assert len(affinita) == 1
        assert affinita[0]["fratello"] == "Marco Rossi"

    def test_sanitize_rimuove_affinita_orfana(self, repo):
        repo.affinita = [{"famiglia": "Inesistente", "fratello": "Mario Rossi", "peso": 3}]
        repo.sanitize({})
        assert repo.get_affinita() == []
