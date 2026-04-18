"""Test per le nuove funzionalita' del service layer v2."""
import pytest
from turni_visite.service import modifica_assegnazione, quick_check


class TestModificaAssegnazione:
    def _solution(self):
        return {
            "by_month": {
                "2026-01": {
                    "by_family": {"Fam A": ["Mario", "Luigi"]},
                    "by_brother": {"Mario": ["Fam A"], "Luigi": ["Fam A"]},
                }
            }
        }

    def test_modifica_slot(self):
        sol = self._solution()
        modifica_assegnazione(sol, "2026-01", "Fam A", 0, "Carla")
        assert sol["by_month"]["2026-01"]["by_family"]["Fam A"][0] == "Carla"
        assert "Fam A" in sol["by_month"]["2026-01"]["by_brother"]["Carla"]
        assert "Fam A" not in sol["by_month"]["2026-01"]["by_brother"]["Mario"]

    def test_mese_non_trovato(self):
        with pytest.raises(ValueError):
            modifica_assegnazione(self._solution(), "2099-01", "Fam A", 0, "X")

    def test_famiglia_non_trovata(self):
        with pytest.raises(ValueError):
            modifica_assegnazione(self._solution(), "2026-01", "Fam Z", 0, "X")

    def test_slot_non_valido(self):
        with pytest.raises(ValueError):
            modifica_assegnazione(self._solution(), "2026-01", "Fam A", 99, "X")


class TestQuickCheck:
    def _snap(self):
        return {
            "fratelli": {"Mario", "Luigi"},
            "famiglie": {"Fam A"},
            "associazioni": {"Fam A": ["Mario", "Luigi"]},
            "frequenze": {"Fam A": 2},
            "capacita": {"Mario": 2, "Luigi": 2},
            "indisponibilita": {},
            "vincoli_personalizzati": [],
        }

    def test_fattibile(self):
        result = quick_check(self._snap(), ["2026-01"], [], 3)
        assert result["fattibile"] is True

    def test_capacita_insufficiente(self):
        snap = self._snap()
        snap["capacita"] = {"Mario": 0, "Luigi": 0}
        result = quick_check(snap, ["2026-01"], [], 3)
        assert result["fattibile"] is False
        assert any("Capacita'" in p for p in result["problemi"])

    def test_indisponibilita_segnalata(self):
        snap = self._snap()
        snap["indisponibilita"] = {"Mario": ["2026-01"]}
        result = quick_check(snap, ["2026-01"], [], 3)
        assert len(result["avvisi"]) > 0 or len(result["problemi"]) > 0
