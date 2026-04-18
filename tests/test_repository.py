"""Test per turni_visite.repository (usa tmp_path di pytest — nessuna I/O globale)."""
import json
import os
import pytest

from turni_visite.repository import JsonRepository
from turni_visite.domain import (
    DuplicatoError, EntitaNonTrovata, ValidazioneError,
    StoricoConflittoError, TurniVisiteError,
)


@pytest.fixture
def repo(tmp_path):
    """Repository fresco su file temporaneo."""
    return JsonRepository(str(tmp_path / "test_dati.json"))


@pytest.fixture
def repo_popolato(tmp_path):
    """Repository con fratelli, famiglie e associazioni precaricate."""
    r = JsonRepository(str(tmp_path / "test_dati.json"))
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_family("Famiglia Verdi")
    r.set_frequency("Famiglia Verdi", 2)
    r.associate("Mario Rossi", "Famiglia Verdi")
    return r


# ---------------------------------------------------------------------------
# add_brother
# ---------------------------------------------------------------------------

class TestAddBrother:
    def test_aggiunge_e_ritorna_canonico(self, repo):
        nome = repo.add_brother("mario rossi")
        assert nome == "Mario Rossi"
        assert "Mario Rossi" in repo.fratelli

    def test_capacita_default_uno(self, repo):
        repo.add_brother("Mario Rossi")
        assert repo.capacita["Mario Rossi"] == 1

    def test_duplicato_errore(self, repo):
        repo.add_brother("Mario Rossi")
        with pytest.raises(DuplicatoError):
            repo.add_brother("mario rossi")

    def test_nome_non_valido_errore(self, repo):
        with pytest.raises(ValidazioneError):
            repo.add_brother("Mario123")

    def test_nome_vuoto_errore(self, repo):
        with pytest.raises(ValidazioneError):
            repo.add_brother("")


# ---------------------------------------------------------------------------
# add_family
# ---------------------------------------------------------------------------

class TestAddFamily:
    def test_aggiunge_e_ritorna_canonico(self, repo):
        nome = repo.add_family("famiglia verdi")
        assert nome == "Famiglia Verdi"
        assert "Famiglia Verdi" in repo.famiglie

    def test_frequenza_default_due(self, repo):
        repo.add_family("Famiglia Verdi")
        assert repo.frequenze["Famiglia Verdi"] == 2

    def test_duplicato_errore(self, repo):
        repo.add_family("Famiglia Verdi")
        with pytest.raises(DuplicatoError):
            repo.add_family("Famiglia Verdi")


# ---------------------------------------------------------------------------
# associate
# ---------------------------------------------------------------------------

class TestAssociate:
    def test_crea_associazione(self, repo_popolato):
        repo = repo_popolato
        repo.add_brother("Carla Neri")
        repo.add_family("Famiglia Blu")
        repo.associate("Carla Neri", "Famiglia Blu")
        assert "Carla Neri" in repo.associazioni["Famiglia Blu"]

    def test_fratello_inesistente_errore(self, repo_popolato):
        with pytest.raises(EntitaNonTrovata):
            repo_popolato.associate("Inesistente", "Famiglia Verdi")

    def test_famiglia_inesistente_errore(self, repo_popolato):
        with pytest.raises(EntitaNonTrovata):
            repo_popolato.associate("Mario Rossi", "Famiglia Inesistente")

    def test_duplicato_errore(self, repo_popolato):
        with pytest.raises(DuplicatoError):
            repo_popolato.associate("Mario Rossi", "Famiglia Verdi")


# ---------------------------------------------------------------------------
# set_frequency
# ---------------------------------------------------------------------------

class TestSetFrequency:
    def test_frequenze_valide(self, repo_popolato):
        for freq in (1, 2, 4):
            repo_popolato.set_frequency("Famiglia Verdi", freq)
            assert repo_popolato.frequenze["Famiglia Verdi"] == freq

    def test_frequenza_non_valida(self, repo_popolato):
        with pytest.raises(ValidazioneError):
            repo_popolato.set_frequency("Famiglia Verdi", 3)

    def test_famiglia_inesistente(self, repo_popolato):
        with pytest.raises(EntitaNonTrovata):
            repo_popolato.set_frequency("Famiglia Inesistente", 2)


# ---------------------------------------------------------------------------
# set_brother_capacity
# ---------------------------------------------------------------------------

class TestSetBrotherCapacity:
    def test_imposta_capacita(self, repo_popolato):
        repo_popolato.set_brother_capacity("Mario Rossi", 3)
        assert repo_popolato.capacita["Mario Rossi"] == 3

    def test_zero_ammesso(self, repo_popolato):
        repo_popolato.set_brother_capacity("Mario Rossi", 0)
        assert repo_popolato.capacita["Mario Rossi"] == 0

    def test_sopra_limite_errore(self, repo_popolato):
        with pytest.raises(ValidazioneError):
            repo_popolato.set_brother_capacity("Mario Rossi", 51)

    def test_negativo_errore(self, repo_popolato):
        with pytest.raises(ValidazioneError):
            repo_popolato.set_brother_capacity("Mario Rossi", -1)

    def test_fratello_inesistente(self, repo_popolato):
        with pytest.raises(EntitaNonTrovata):
            repo_popolato.set_brother_capacity("Inesistente", 2)


# ---------------------------------------------------------------------------
# remove_brother
# ---------------------------------------------------------------------------

class TestRemoveBrother:
    def test_rimuove_fratello(self, repo_popolato):
        repo_popolato.remove_brother("Mario Rossi")
        assert "Mario Rossi" not in repo_popolato.fratelli

    def test_rimuove_da_associazioni(self, repo_popolato):
        repo_popolato.remove_brother("Mario Rossi")
        for frs in repo_popolato.associazioni.values():
            assert "Mario Rossi" not in frs

    def test_rimuove_chiave_vuota_associazioni(self, repo_popolato):
        # Famiglia Verdi ha solo Mario Rossi: dopo rimozione la chiave scompare
        repo_popolato.remove_brother("Mario Rossi")
        assert "Famiglia Verdi" not in repo_popolato.associazioni

    def test_rimuove_capacita(self, repo_popolato):
        repo_popolato.remove_brother("Mario Rossi")
        assert "Mario Rossi" not in repo_popolato.capacita

    def test_inesistente_errore(self, repo_popolato):
        with pytest.raises(EntitaNonTrovata):
            repo_popolato.remove_brother("Inesistente")


# ---------------------------------------------------------------------------
# remove_family
# ---------------------------------------------------------------------------

class TestRemoveFamily:
    def test_rimuove_famiglia(self, repo_popolato):
        repo_popolato.remove_family("Famiglia Verdi")
        assert "Famiglia Verdi" not in repo_popolato.famiglie

    def test_rimuove_associazioni(self, repo_popolato):
        repo_popolato.remove_family("Famiglia Verdi")
        assert "Famiglia Verdi" not in repo_popolato.associazioni

    def test_rimuove_frequenza(self, repo_popolato):
        repo_popolato.remove_family("Famiglia Verdi")
        assert "Famiglia Verdi" not in repo_popolato.frequenze

    def test_inesistente_errore(self, repo_popolato):
        with pytest.raises(EntitaNonTrovata):
            repo_popolato.remove_family("Famiglia Inesistente")


# ---------------------------------------------------------------------------
# Storico turni
# ---------------------------------------------------------------------------

class TestStoricoTurni:
    def _assegnazioni(self):
        return [{"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0}]

    def test_append_e_has_mese(self, repo_popolato):
        repo_popolato.append_storico_turni("2025-03", self._assegnazioni())
        assert repo_popolato.storico_has_mese("2025-03")

    def test_duplicato_mese_errore(self, repo_popolato):
        repo_popolato.append_storico_turni("2025-03", self._assegnazioni())
        with pytest.raises(StoricoConflittoError):
            repo_popolato.append_storico_turni("2025-03", self._assegnazioni())

    def test_delete_mese(self, repo_popolato):
        repo_popolato.append_storico_turni("2025-03", self._assegnazioni())
        repo_popolato.delete_storico_mese("2025-03")
        assert not repo_popolato.storico_has_mese("2025-03")

    def test_delete_mese_inesistente_errore(self, repo_popolato):
        with pytest.raises(EntitaNonTrovata):
            repo_popolato.delete_storico_mese("2099-01")

    def test_mese_non_valido_errore(self, repo_popolato):
        with pytest.raises(ValidazioneError):
            repo_popolato.append_storico_turni("", self._assegnazioni())


# ---------------------------------------------------------------------------
# Save atomica e load
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_save_crea_json_valido(self, repo_popolato, tmp_path):
        fname = repo_popolato.filename
        assert os.path.exists(fname)
        with open(fname, encoding="utf-8") as f:
            data = json.load(f)
        assert "Mario Rossi" in data["fratelli"]
        assert "Famiglia Verdi" in data["famiglie"]

    def test_associazioni_ordinate(self, tmp_path):
        r = JsonRepository(str(tmp_path / "ord.json"))
        r.add_brother("Zara")
        r.add_brother("Anna")
        r.add_family("Fam Test")
        r.associate("Zara", "Fam Test")
        r.associate("Anna", "Fam Test")
        with open(r.filename, encoding="utf-8") as f:
            data = json.load(f)
        assert data["associazioni"]["Fam Test"] == ["Anna", "Zara"]  # ordinato

    def test_load_ricarica_dati(self, repo_popolato):
        fname = repo_popolato.filename
        r2 = JsonRepository(fname)
        assert "Mario Rossi" in r2.fratelli
        assert "Famiglia Verdi" in r2.famiglie
        assert "Mario Rossi" in r2.associazioni.get("Famiglia Verdi", [])

    def test_load_file_corrotto_errore(self, tmp_path):
        f = tmp_path / "corrotto.json"
        f.write_text("{questo non e' json valido}", encoding="utf-8")
        with pytest.raises(TurniVisiteError):
            JsonRepository(str(f))

    def test_no_file_avvio_vuoto(self, tmp_path):
        r = JsonRepository(str(tmp_path / "non_esiste.json"))
        assert len(r.fratelli) == 0
        assert len(r.famiglie) == 0

    def test_save_atomica_no_file_parziale(self, repo_popolato, monkeypatch):
        """Se json.dump fallisce, il file originale deve rimanere intatto."""
        import tempfile as _tmpmod
        fname = repo_popolato.filename

        original_mkstemp = _tmpmod.mkstemp
        def mkstemp_fallisce(*args, **kwargs):
            fd, path = original_mkstemp(*args, **kwargs)
            os.close(fd)
            raise OSError("Disco pieno simulato")
        monkeypatch.setattr(_tmpmod, "mkstemp", mkstemp_fallisce)

        with pytest.raises(OSError):
            repo_popolato.save()

        # Il file originale e' ancora valido
        with open(fname, encoding="utf-8") as f:
            data = json.load(f)
        assert "Mario Rossi" in data["fratelli"]
