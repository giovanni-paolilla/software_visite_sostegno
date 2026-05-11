"""Test per il troncamento audit log e comportamento _log_audit."""
import pytest
from turni_visite.repository import JsonRepository


@pytest.fixture
def repo(tmp_path):
    return JsonRepository(str(tmp_path / "audit_test.json"))


class TestAuditLogTruncation:
    def test_troncamento_a_500(self, repo):
        repo.audit_log = [
            {"timestamp": f"2026-01-01T00:00:{i:02d}", "azione": f"test_{i}", "dettagli": ""}
            for i in range(499)
        ]
        repo.add_brother("Trigger")
        assert len(repo.audit_log) == 500

    def test_oltre_500_tronca(self, repo):
        repo.audit_log = [
            {"timestamp": f"2026-01-01T00:00:{i:02d}", "azione": f"test_{i}", "dettagli": ""}
            for i in range(500)
        ]
        repo.add_brother("Trigger")
        assert len(repo.audit_log) == 500
        assert repo.audit_log[-1]["azione"] == "aggiungi_fratello"

    def test_mantiene_ultimi_500(self, repo):
        repo.audit_log = [
            {"timestamp": "2026-01-01", "azione": f"old_{i}", "dettagli": ""}
            for i in range(510)
        ]
        repo.add_brother("Nuovo")
        assert len(repo.audit_log) == 500
        assert repo.audit_log[0]["azione"] != "old_0"
        assert repo.audit_log[-1]["azione"] == "aggiungi_fratello"


class TestAuditLogContent:
    def test_add_brother_registrato(self, repo):
        repo.add_brother("Mario Rossi")
        log = repo.get_audit_log(1)
        assert log[0]["azione"] == "aggiungi_fratello"
        assert "Mario Rossi" in log[0]["dettagli"]

    def test_remove_brother_registrato(self, repo):
        repo.add_brother("Mario Rossi")
        repo.remove_brother("Mario Rossi")
        log = repo.get_audit_log(1)
        assert log[0]["azione"] == "rimuovi_fratello"

    def test_add_family_registrato(self, repo):
        repo.add_family("Fam Test")
        log = repo.get_audit_log(1)
        assert log[0]["azione"] == "aggiungi_famiglia"

    def test_associate_registrato(self, repo):
        repo.add_brother("Mario")
        repo.add_family("Fam A")
        repo.associate("Mario", "Fam A")
        log = repo.get_audit_log(1)
        assert log[0]["azione"] == "associazione"

    def test_disassociate_registrato(self, repo):
        repo.add_brother("Mario")
        repo.add_family("Fam A")
        repo.associate("Mario", "Fam A")
        repo.disassociate("Mario", "Fam A")
        log = repo.get_audit_log(1)
        assert log[0]["azione"] == "disassociazione"

    def test_modifica_capacita_registrato(self, repo):
        repo.add_brother("Mario")
        repo.set_brother_capacity("Mario", 5)
        log = repo.get_audit_log(1)
        assert log[0]["azione"] == "modifica_capacita"
        assert "5" in log[0]["dettagli"]

    def test_modifica_frequenza_registrato(self, repo):
        repo.add_family("Fam A")
        repo.set_frequency("Fam A", 4)
        log = repo.get_audit_log(1)
        assert log[0]["azione"] == "modifica_frequenza"

    def test_conferma_turni_registrato(self, repo):
        repo.add_brother("Mario")
        repo.add_family("Fam A")
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Fam A", "fratello": "Mario", "slot": 0},
        ])
        log = repo.get_audit_log(1)
        assert log[0]["azione"] == "conferma_turni"

    def test_elimina_storico_registrato(self, repo):
        repo.add_brother("Mario")
        repo.add_family("Fam A")
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Fam A", "fratello": "Mario", "slot": 0},
        ])
        repo.delete_storico_mese("2026-01")
        log = repo.get_audit_log(1)
        assert log[0]["azione"] == "elimina_storico"

    def test_add_vincolo_registrato(self, repo):
        repo.add_brother("Mario")
        repo.add_brother("Luigi")
        repo.add_vincolo("Mario", "Luigi", "incompatibile")
        log = repo.get_audit_log(1)
        assert log[0]["azione"] == "aggiungi_vincolo"

    def test_indisponibilita_registrata(self, repo):
        repo.add_brother("Mario")
        repo.add_indisponibilita("Mario", "2026-05")
        log = repo.get_audit_log(2)
        indisp = [e for e in log if "indisponibilita" in e["azione"]]
        assert len(indisp) >= 1

    def test_timestamp_presente(self, repo):
        repo.add_brother("Test")
        log = repo.get_audit_log(1)
        assert "timestamp" in log[0]
        assert "T" in log[0]["timestamp"]

    def test_get_audit_log_ordine_inverso(self, repo):
        repo.add_brother("Primo")
        repo.add_brother("Secondo")
        log = repo.get_audit_log(2)
        assert "Secondo" in log[0]["dettagli"]
        assert "Primo" in log[1]["dettagli"]

    def test_persistenza_audit(self, repo):
        repo.add_brother("Test")
        r2 = JsonRepository(repo.filename)
        log = r2.get_audit_log(1)
        assert len(log) >= 1
