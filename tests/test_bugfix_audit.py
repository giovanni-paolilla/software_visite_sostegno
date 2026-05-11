"""Test per i bug trovati dall'audit del codice e corretti."""
import json
import pytest
from unittest.mock import patch, MagicMock

from turni_visite.repository import JsonRepository
from turni_visite.domain import EntitaNonTrovata, ValidazioneError
from turni_visite.service import (
    modifica_assegnazione, _estrai_assegnazioni, conferma_e_salva_turni,
)

try:
    from ortools.sat.python import cp_model  # type: ignore  # noqa: F401
    _HAS_ORTOOLS = True
except ImportError:
    _HAS_ORTOOLS = False

skip_no_ortools = pytest.mark.skipif(
    not _HAS_ORTOOLS, reason="ortools non installato"
)


@pytest.fixture
def repo(tmp_path):
    r = JsonRepository(str(tmp_path / "audit.json"))
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_family("Famiglia Verdi")
    r.associate("Mario Rossi", "Famiglia Verdi")
    r.associate("Luigi Bianchi", "Famiglia Verdi")
    return r


# ---------------------------------------------------------------------------
# Bug 1: service.modifica_assegnazione — KeyError on missing "by_family"
# ---------------------------------------------------------------------------

class TestModificaAssegnazioneMissingByFamily:
    def test_missing_by_family_key(self):
        solution = {"by_month": {"2025-01": {}}}
        with pytest.raises(ValidazioneError, match="Struttura soluzione mancante"):
            modifica_assegnazione(solution, "2025-01", "Famiglia Verdi", 0, "Luigi Bianchi")

    def test_valid_by_family_key(self):
        solution = {
            "by_month": {
                "2025-01": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi", "Luigi Bianchi"]},
                    "by_brother": {"Mario Rossi": ["Famiglia Verdi"], "Luigi Bianchi": ["Famiglia Verdi"]},
                }
            }
        }
        result = modifica_assegnazione(solution, "2025-01", "Famiglia Verdi", 0, "Luigi Bianchi")
        assert result["by_month"]["2025-01"]["by_family"]["Famiglia Verdi"][0] == "Luigi Bianchi"


# ---------------------------------------------------------------------------
# Bug 2: service._estrai_assegnazioni — unprotected nested access
# ---------------------------------------------------------------------------

class TestEstiaiAssegnazioniSafety:
    def test_missing_by_month(self):
        with pytest.raises(ValidazioneError, match="non trovato nella soluzione"):
            _estrai_assegnazioni("2025-01", {})

    def test_missing_mese_in_by_month(self):
        with pytest.raises(ValidazioneError, match="non trovato nella soluzione"):
            _estrai_assegnazioni("2025-01", {"by_month": {"2025-02": {}}})

    def test_missing_by_family_uses_empty(self):
        result = _estrai_assegnazioni("2025-01", {"by_month": {"2025-01": {}}})
        assert result == []

    def test_valid_extraction(self):
        solution = {
            "by_month": {
                "2025-01": {
                    "by_family": {"Fam A": ["Mario Rossi"]}
                }
            }
        }
        result = _estrai_assegnazioni("2025-01", solution)
        assert len(result) == 1
        assert result[0]["famiglia"] == "Fam A"
        assert result[0]["fratello"] == "Mario Rossi"
        assert result[0]["slot"] == 0

    def test_conferma_e_salva_with_bad_solution(self, repo):
        with pytest.raises(ValidazioneError, match="non trovato nella soluzione"):
            conferma_e_salva_turni(repo, ["2025-06"], {"by_month": {}})


# ---------------------------------------------------------------------------
# Bug 3: repository.update_storico_assegnazione — fallback slot mutation
# ---------------------------------------------------------------------------

class TestFallbackSlotNoMutation:
    def test_fallback_preserves_original_slot(self, repo):
        # Il fallback "slot==0 quando non trovato" e' stato rimosso:
        # ora viene sollevata EntitaNonTrovata se non c'e' match esatto.
        repo.append_storico_turni("2025-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 5},
        ])
        with pytest.raises(EntitaNonTrovata):
            repo.update_storico_assegnazione(
                "2025-01", "Famiglia Verdi", 0, "Mario Rossi", "Luigi Bianchi"
            )
        # Lo slot originale NON deve essere stato modificato
        rec = next(r for r in repo.storico_turni if r["mese"] == "2025-01")
        a = rec["assegnazioni"][0]
        assert a["fratello"] == "Mario Rossi"
        assert a["slot"] == 5

    def test_exact_match_works_normally(self, repo):
        repo.append_storico_turni("2025-02", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        repo.update_storico_assegnazione(
            "2025-02", "Famiglia Verdi", 0, "Mario Rossi", "Luigi Bianchi"
        )
        rec = next(r for r in repo.storico_turni if r["mese"] == "2025-02")
        a = rec["assegnazioni"][0]
        assert a["fratello"] == "Luigi Bianchi"
        assert a["slot"] == 0

    def test_fallback_not_used_when_exact_match_exists(self, repo):
        repo.append_storico_turni("2025-03", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 1},
        ])
        repo.update_storico_assegnazione(
            "2025-03", "Famiglia Verdi", 1, "Mario Rossi", "Luigi Bianchi"
        )
        rec = next(r for r in repo.storico_turni if r["mese"] == "2025-03")
        assert rec["assegnazioni"][0]["fratello"] == "Mario Rossi"
        assert rec["assegnazioni"][0]["slot"] == 0
        assert rec["assegnazioni"][1]["fratello"] == "Luigi Bianchi"
        assert rec["assegnazioni"][1]["slot"] == 1


# ---------------------------------------------------------------------------
# Bug 6: scheduling — invalid peso type in affinita
# ---------------------------------------------------------------------------

class TestSchedulingInvalidPeso:
    @skip_no_ortools
    def test_invalid_peso_type_skipped(self):
        from turni_visite.scheduling import ottimizza_turni_mesi
        result = ottimizza_turni_mesi(
            mesi=["2025-01"],
            fratelli={"Mario Rossi"},
            famiglie={"Famiglia Verdi"},
            associazioni={"Famiglia Verdi": ["Mario Rossi"]},
            frequenze={"Famiglia Verdi": 1},
            capacita={"Mario Rossi": 2},
            storico_turni=[],
            cooldown_mesi=3,
            affinita=[{"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "peso": "not_a_number"}],
        )
        assert result is not None

    @skip_no_ortools
    def test_none_peso_skipped(self):
        from turni_visite.scheduling import ottimizza_turni_mesi
        result = ottimizza_turni_mesi(
            mesi=["2025-01"],
            fratelli={"Mario Rossi"},
            famiglie={"Famiglia Verdi"},
            associazioni={"Famiglia Verdi": ["Mario Rossi"]},
            frequenze={"Famiglia Verdi": 1},
            capacita={"Mario Rossi": 2},
            storico_turni=[],
            cooldown_mesi=3,
            affinita=[{"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "peso": None}],
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Bug 7: cli — vincoli[n-1] negative index when n=0
# ---------------------------------------------------------------------------

class TestCLIVincoliNegativeIndex:
    def test_vincoli_rimuovi_zero(self, repo, capsys):
        from turni_visite.cli import _cmd_vincoli
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        with patch("builtins.input", side_effect=["R", "0"]):
            _cmd_vincoli(repo)
        out = capsys.readouterr().out
        # Input <= 0: la CLI annulla l'operazione (non e' un errore).
        assert "Annullato" in out

    def test_vincoli_rimuovi_negative(self, repo, capsys):
        from turni_visite.cli import _cmd_vincoli
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        with patch("builtins.input", side_effect=[" R ", "-1"]):
            _cmd_vincoli(repo)
        out = capsys.readouterr().out
        # Input <= 0: la CLI annulla l'operazione (non e' un errore).
        assert "Annullato" in out

    def test_vincoli_rimuovi_valid(self, repo, capsys):
        from turni_visite.cli import _cmd_vincoli
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        with patch("builtins.input", side_effect=["R", "1"]):
            _cmd_vincoli(repo)
        out = capsys.readouterr().out
        assert "Vincolo rimosso" in out
