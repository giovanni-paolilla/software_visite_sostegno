"""Test per le nuove funzionalita' del repository v2 (indisponibilita', vincoli, audit, etc.)."""
import pytest
from turni_visite.repository import JsonRepository
from turni_visite.domain import (
    DuplicatoError, EntitaNonTrovata, ValidazioneError,
)


@pytest.fixture
def repo(tmp_path):
    r = JsonRepository(str(tmp_path / "test_v2.json"))
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_family("Famiglia Verdi")
    r.associate("Mario Rossi", "Famiglia Verdi")
    r.associate("Luigi Bianchi", "Famiglia Verdi")
    return r


# ---------------------------------------------------------------------------
# Indisponibilita'
# ---------------------------------------------------------------------------

class TestIndisponibilita:
    def test_add_indisponibilita(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        assert "2026-03" in repo.get_indisponibilita("Mario Rossi")

    def test_remove_indisponibilita(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        repo.remove_indisponibilita("Mario Rossi", "2026-03")
        assert "2026-03" not in repo.get_indisponibilita("Mario Rossi")

    def test_set_indisponibilita(self, repo):
        repo.set_indisponibilita("Mario Rossi", ["2026-01", "2026-02"])
        assert repo.get_indisponibilita("Mario Rossi") == ["2026-01", "2026-02"]

    def test_indisponibilita_fratello_inesistente(self, repo):
        with pytest.raises(EntitaNonTrovata):
            repo.add_indisponibilita("Inesistente", "2026-03")

    def test_rimuovi_fratello_pulisce_indisponibilita(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        repo.remove_brother("Mario Rossi")
        assert "Mario Rossi" not in repo.indisponibilita

    def test_persistenza(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        r2 = JsonRepository(repo.filename)
        assert "2026-03" in r2.indisponibilita.get("Mario Rossi", [])


# ---------------------------------------------------------------------------
# Vincoli personalizzati
# ---------------------------------------------------------------------------

class TestVincoliPersonalizzati:
    def test_add_vincolo_incompatibile(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        vincoli = repo.get_vincoli("incompatibile")
        assert len(vincoli) == 1
        assert vincoli[0]["fratello_a"] == "Mario Rossi"

    def test_add_vincolo_coppia(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "preferenza_coppia")
        assert len(repo.get_vincoli("preferenza_coppia")) == 1

    def test_tipo_non_valido(self, repo):
        with pytest.raises(ValidazioneError):
            repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "tipo_invalido")

    def test_vincolo_con_se_stesso(self, repo):
        with pytest.raises(ValidazioneError):
            repo.add_vincolo("Mario Rossi", "Mario Rossi", "incompatibile")

    def test_vincolo_duplicato(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        with pytest.raises(DuplicatoError):
            repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")

    def test_remove_vincolo(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        repo.remove_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        assert len(repo.get_vincoli()) == 0

    def test_remove_vincolo_inesistente(self, repo):
        with pytest.raises(EntitaNonTrovata):
            repo.remove_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")

    def test_rimuovi_fratello_pulisce_vincoli(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        repo.remove_brother("Mario Rossi")
        assert len(repo.vincoli_personalizzati) == 0

    def test_persistenza(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile", "test")
        r2 = JsonRepository(repo.filename)
        assert len(r2.vincoli_personalizzati) == 1


# ---------------------------------------------------------------------------
# Week templates
# ---------------------------------------------------------------------------

class TestWeekTemplates:
    def test_set_e_get(self, repo):
        repo.set_week_template(2, ["01-07", "15-21"])
        assert repo.get_week_template(2) == ["01-07", "15-21"]

    def test_freq_non_valida(self, repo):
        with pytest.raises(ValidazioneError):
            repo.set_week_template(3, ["01-07"])

    def test_persistenza(self, repo):
        repo.set_week_template(1, ["08-14"])
        r2 = JsonRepository(repo.filename)
        assert r2.get_week_template(1) == ["08-14"]


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    def test_audit_su_add_brother(self, repo):
        repo.add_brother("Nuovo Fratello")
        log = repo.get_audit_log(1)
        assert len(log) >= 1
        assert "aggiungi_fratello" in log[0]["azione"]

    def test_audit_limit(self, repo):
        for i in range(10):
            repo.add_brother(f"Fratello {i}")
        log = repo.get_audit_log(5)
        assert len(log) == 5


# ---------------------------------------------------------------------------
# Disassociate
# ---------------------------------------------------------------------------

class TestDisassociate:
    def test_disassocia(self, repo):
        repo.disassociate("Mario Rossi", "Famiglia Verdi")
        assert "Mario Rossi" not in repo.associazioni.get("Famiglia Verdi", [])

    def test_disassocia_non_associato(self, repo):
        repo.add_brother("Carla Neri")
        with pytest.raises(EntitaNonTrovata):
            repo.disassociate("Carla Neri", "Famiglia Verdi")


# ---------------------------------------------------------------------------
# Dashboard KPI
# ---------------------------------------------------------------------------

class TestDashboardKPI:
    def test_kpi_base(self, repo):
        kpi = repo.get_dashboard_kpi()
        assert kpi["n_fratelli"] == 2
        assert kpi["n_famiglie"] == 1
        assert kpi["n_fratelli_attivi"] == 2
        assert kpi["capacita_totale"] == 2
        assert kpi["domanda_totale"] == 2

    def test_kpi_bilancio(self, repo):
        kpi = repo.get_dashboard_kpi()
        assert kpi["bilancio"] == 0  # cap=2, dom=2

    def test_kpi_fratelli_senza_assoc(self, repo):
        repo.add_brother("Isolato")
        kpi = repo.get_dashboard_kpi()
        assert "Isolato" in kpi["fratelli_senza_associazione"]


# ---------------------------------------------------------------------------
# Data snapshot include nuovi campi
# ---------------------------------------------------------------------------

class TestDataSnapshot:
    def test_include_indisponibilita(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        snap = repo.data_snapshot()
        assert "2026-03" in snap["indisponibilita"]["Mario Rossi"]

    def test_include_vincoli(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        snap = repo.data_snapshot()
        assert len(snap["vincoli_personalizzati"]) == 1
