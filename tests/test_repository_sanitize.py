"""Test per JsonRepository.sanitize() — normalizzazione e alias dati."""
import pytest
from turni_visite.repository import JsonRepository
from turni_visite.domain import TurniVisiteError


@pytest.fixture
def repo(tmp_path):
    r = JsonRepository(str(tmp_path / "sanitize.json"))
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_brother("Carla Neri")
    r.add_family("Famiglia Verdi")
    r.add_family("Famiglia Blu")
    r.associate("Mario Rossi", "Famiglia Verdi")
    r.associate("Luigi Bianchi", "Famiglia Verdi")
    r.associate("Carla Neri", "Famiglia Blu")
    return r


class TestSanitizeBasic:
    def test_noop_senza_alias(self, repo):
        n_fr = len(repo.fratelli)
        n_fam = len(repo.famiglie)
        repo.sanitize({})
        assert len(repo.fratelli) == n_fr
        assert len(repo.famiglie) == n_fam

    def test_rinomina_fratello(self, repo):
        repo.sanitize({"Mario Rossi": "Marco Rossi"})
        assert "Marco Rossi" in repo.fratelli
        assert "Mario Rossi" not in repo.fratelli

    def test_rinomina_famiglia(self, repo):
        repo.sanitize({"Famiglia Verdi": "Famiglia Verde"})
        assert "Famiglia Verde" in repo.famiglie
        assert "Famiglia Verdi" not in repo.famiglie

    def test_associazioni_aggiornate(self, repo):
        repo.sanitize({"Mario Rossi": "Marco Rossi"})
        assert "Marco Rossi" in repo.associazioni.get("Famiglia Verdi", [])
        assert "Mario Rossi" not in repo.associazioni.get("Famiglia Verdi", [])

    def test_associazioni_famiglia_rinominata(self, repo):
        repo.sanitize({"Famiglia Verdi": "Famiglia Verde"})
        assert "Famiglia Verde" in repo.associazioni
        assert "Famiglia Verdi" not in repo.associazioni

    def test_frequenze_preservate_senza_alias(self, repo):
        repo.set_frequency("Famiglia Verdi", 4)
        repo.sanitize({})
        assert repo.frequenze.get("Famiglia Verdi") == 4

    def test_frequenza_non_valida_normalizzata_a_default(self, repo):
        repo.frequenze["Famiglia Verdi"] = 5
        repo.sanitize({})
        assert repo.frequenze.get("Famiglia Verdi") == 2

    def test_capacita_preservata_senza_alias(self, repo):
        repo.set_brother_capacity("Mario Rossi", 5)
        repo.sanitize({})
        assert repo.capacita.get("Mario Rossi") == 5


class TestSanitizeIndisponibilita:
    def test_indisponibilita_rinominata(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        repo.sanitize({"Mario Rossi": "Marco Rossi"})
        assert "Marco Rossi" in repo.indisponibilita
        assert "2026-03" in repo.indisponibilita["Marco Rossi"]
        assert "Mario Rossi" not in repo.indisponibilita

    def test_indisponibilita_fratello_rimosso_pulita(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        repo.indisponibilita["Nome Inesistente"] = ["2026-01"]
        repo.sanitize({})
        assert "Nome Inesistente" not in repo.indisponibilita
        assert "Mario Rossi" in repo.indisponibilita


class TestSanitizeVincoli:
    def test_vincoli_rinominati(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        repo.sanitize({"Mario Rossi": "Marco Rossi"})
        vincoli = repo.get_vincoli()
        assert len(vincoli) == 1
        nomi = {vincoli[0]["fratello_a"], vincoli[0]["fratello_b"]}
        assert "Marco Rossi" in nomi
        assert "Mario Rossi" not in nomi

    def test_vincoli_orfani_rimossi(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        repo.fratelli.discard("Luigi Bianchi")
        repo.sanitize({})
        assert len(repo.vincoli_personalizzati) == 0


class TestSanitizeStorico:
    def test_storico_rinominato(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        repo.sanitize({"Mario Rossi": "Marco Rossi"})
        ass = repo.storico_turni[0]["assegnazioni"]
        assert ass[0]["fratello"] == "Marco Rossi"

    def test_storico_famiglia_rinominata(self, repo):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        repo.sanitize({"Famiglia Verdi": "Famiglia Verde"})
        ass = repo.storico_turni[0]["assegnazioni"]
        assert ass[0]["famiglia"] == "Famiglia Verde"

    def test_storico_record_non_dict_ignorato(self, repo):
        repo.storico_turni.append("invalid")
        repo.sanitize({})
        for rec in repo.storico_turni:
            assert isinstance(rec, dict)

    def test_storico_assegnazione_non_dict_ignorata(self, repo):
        repo.storico_turni.append({
            "mese": "2026-01",
            "created_at": "2026-01-01",
            "confirmed_at": "2026-01-01",
            "assegnazioni": ["invalid", 42],
        })
        repo.sanitize({})
        last_rec = repo.storico_turni[-1]
        assert all(isinstance(a, dict) for a in last_rec["assegnazioni"])


class TestSanitizeEdgeCases:
    def test_associazione_orfana_rimossa(self, repo):
        repo.associazioni["Fam Inesistente"] = ["Mario Rossi"]
        repo.sanitize({})
        assert "Fam Inesistente" not in repo.associazioni

    def test_fratello_orfano_in_associazione_rimosso(self, repo):
        repo.associazioni["Famiglia Verdi"].append("Fantasma")
        repo.sanitize({})
        for frs in repo.associazioni.values():
            assert "Fantasma" not in frs

    def test_frequenza_non_valida_normalizzata(self, repo):
        repo.frequenze["Famiglia Verdi"] = 5
        repo.sanitize({})
        assert repo.frequenze["Famiglia Verdi"] == 2

    def test_capacita_fuori_range_normalizzata(self, repo):
        repo.capacita["Mario Rossi"] = 100
        repo.sanitize({})
        assert repo.capacita["Mario Rossi"] == 1

    def test_capacita_negativa_normalizzata(self, repo):
        repo.capacita["Mario Rossi"] = -5
        repo.sanitize({})
        assert repo.capacita["Mario Rossi"] == 1

    def test_salva_dopo_sanitize(self, repo):
        repo.sanitize({"Mario Rossi": "Marco Rossi"})
        r2 = JsonRepository(repo.filename)
        assert "Marco Rossi" in r2.fratelli
        assert "Mario Rossi" not in r2.fratelli

    def test_audit_log_registrato(self, repo):
        n_before = len(repo.audit_log)
        repo.sanitize({"Mario Rossi": "Marco Rossi"})
        assert len(repo.audit_log) > n_before
        last = repo.audit_log[-1]
        assert "sanificazione" in last["azione"]

    def test_duplicati_alias_unificati(self, repo):
        repo.sanitize({
            "Mario Rossi": "Unico Nome",
            "Luigi Bianchi": "Unico Nome",
        })
        assert "Unico Nome" in repo.fratelli
        assert len(repo.fratelli) < 4
