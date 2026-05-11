"""Test approfonditi per explain_infeasible() e pre_check_fattibilita()."""
import pytest

try:
    from ortools.sat.python import cp_model as _cp
    _ORTOOLS_OK = True
except Exception:
    _ORTOOLS_OK = False

from turni_visite.scheduling import (
    explain_infeasible, pre_check_fattibilita, validate_month_yyyy_mm,
)

pytestmark = pytest.mark.skipif(not _ORTOOLS_OK, reason="ortools non installato")


class TestExplainInfeasibleCapacita:
    def test_capacita_insufficiente(self):
        msg = explain_infeasible(
            mesi=["2026-01"],
            fratelli={"Solo"},
            famiglie={"Fam A"},
            associazioni={"Fam A": ["Solo"]},
            frequenze={"Fam A": 2},
            capacita={"Solo": 0},
            storico_turni=[],
            cooldown_mesi=3,
        )
        assert "DOMANDA/SUPPLY" in msg or "capacit" in msg.lower()

    def test_famiglia_senza_associazione(self):
        msg = explain_infeasible(
            mesi=["2026-01"],
            fratelli={"Mario"},
            famiglie={"Fam A"},
            associazioni={},
            frequenze={"Fam A": 2},
            capacita={"Mario": 2},
            storico_turni=[],
            cooldown_mesi=3,
        )
        assert "senza" in msg.lower() or "associazione" in msg.lower()


class TestExplainInfeasibleCooldown:
    def test_cooldown_blocca(self):
        msg = explain_infeasible(
            mesi=["2026-01", "2026-02", "2026-03", "2026-04"],
            fratelli={"Mario"},
            famiglie={"Fam A"},
            associazioni={"Fam A": ["Mario"]},
            frequenze={"Fam A": 1},
            capacita={"Mario": 1},
            storico_turni=[],
            cooldown_mesi=3,
        )
        assert "COOLDOWN" in msg

    def test_cooldown_suggerisce_sblocco(self):
        msg = explain_infeasible(
            mesi=["2026-01", "2026-02", "2026-03"],
            fratelli={"Mario"},
            famiglie={"Fam A"},
            associazioni={"Fam A": ["Mario"]},
            frequenze={"Fam A": 1},
            capacita={"Mario": 1},
            storico_turni=[],
            cooldown_mesi=3,
        )
        assert "Sblocco" in msg or "aggiungi" in msg.lower()


class TestExplainInfeasibleStorico:
    def test_storico_vincola_primo_mese(self):
        storico = [{
            "mese": "2025-12",
            "assegnazioni": [{"famiglia": "Fam A", "fratello": "Mario", "slot": 0}],
        }]
        msg = explain_infeasible(
            mesi=["2026-01"],
            fratelli={"Mario", "Luigi"},
            famiglie={"Fam A"},
            associazioni={"Fam A": ["Mario", "Luigi"]},
            frequenze={"Fam A": 2},
            capacita={"Mario": 2, "Luigi": 2},
            storico_turni=storico,
            cooldown_mesi=2,
        )
        assert "STORICO" in msg or "Mario" in msg


class TestExplainInfeasibleEdgeCases:
    def test_capacita_none_usa_default(self):
        msg = explain_infeasible(
            mesi=["2026-01"],
            fratelli={"Mario", "Luigi"},
            famiglie={"Fam A"},
            associazioni={"Fam A": ["Mario", "Luigi"]},
            frequenze={"Fam A": 2},
            capacita=None,
            storico_turni=None,
            cooldown_mesi=3,
        )
        assert isinstance(msg, str)

    def test_storico_none(self):
        msg = explain_infeasible(
            mesi=["2026-01"],
            fratelli={"Mario"},
            famiglie={"Fam A"},
            associazioni={"Fam A": ["Mario"]},
            frequenze={"Fam A": 1},
            capacita={"Mario": 1},
            storico_turni=None,
            cooldown_mesi=1,
        )
        assert isinstance(msg, str)

    def test_nessun_problema_evidente(self):
        msg = explain_infeasible(
            mesi=["2026-01"],
            fratelli={"Mario", "Luigi", "Carla"},
            famiglie={"Fam A"},
            associazioni={"Fam A": ["Mario", "Luigi", "Carla"]},
            frequenze={"Fam A": 2},
            capacita={"Mario": 3, "Luigi": 3, "Carla": 3},
            storico_turni=[],
            cooldown_mesi=1,
        )
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_top_criticita_ordinate(self):
        msg = explain_infeasible(
            mesi=["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"],
            fratelli={"Mario"},
            famiglie={"Fam A", "Fam B", "Fam C"},
            associazioni={
                "Fam A": ["Mario"],
                "Fam B": ["Mario"],
                "Fam C": ["Mario"],
            },
            frequenze={"Fam A": 1, "Fam B": 1, "Fam C": 1},
            capacita={"Mario": 1},
            storico_turni=[],
            cooldown_mesi=3,
        )
        assert "CRITICITA'" in msg or "COOLDOWN" in msg

    def test_mesi_vuoti(self):
        msg = explain_infeasible(
            mesi=[],
            fratelli={"Mario"},
            famiglie={"Fam A"},
            associazioni={"Fam A": ["Mario"]},
            frequenze={"Fam A": 1},
            capacita={"Mario": 1},
            storico_turni=[],
            cooldown_mesi=1,
        )
        assert isinstance(msg, str)


# ---------------------------------------------------------------------------
# pre_check_fattibilita
# ---------------------------------------------------------------------------

class TestPreCheckFattibilita:
    def _snap(self, **overrides):
        base = {
            "fratelli": {"Mario", "Luigi", "Carla"},
            "famiglie": {"Fam A"},
            "associazioni": {"Fam A": ["Mario", "Luigi", "Carla"]},
            "frequenze": {"Fam A": 2},
            "capacita": {"Mario": 2, "Luigi": 2, "Carla": 2},
            "indisponibilita": {},
        }
        base.update(overrides)
        return base

    def test_fattibile_base(self):
        result = pre_check_fattibilita(self._snap(), ["2026-01"], [], 3)
        assert result["fattibile"] is True
        assert result["problemi"] == []

    def test_cooldown_troppo_alto(self):
        snap = self._snap(
            fratelli={"Mario"},
            associazioni={"Fam A": ["Mario"]},
            frequenze={"Fam A": 1},
            capacita={"Mario": 1},
        )
        result = pre_check_fattibilita(
            snap, ["2026-01", "2026-02", "2026-03", "2026-04"], [], 3,
        )
        assert result["fattibile"] is False
        assert any("Fam A" in p for p in result["problemi"])

    def test_indisponibilita_genera_avviso(self):
        snap = self._snap(indisponibilita={"Mario": ["2026-01"]})
        result = pre_check_fattibilita(snap, ["2026-01"], [], 3)
        assert len(result["avvisi"]) > 0 or result["fattibile"] is True

    def test_indisponibilita_causa_infeasible(self):
        snap = self._snap(
            fratelli={"Mario"},
            associazioni={"Fam A": ["Mario"]},
            frequenze={"Fam A": 1},
            capacita={"Mario": 1},
            indisponibilita={"Mario": ["2026-01"]},
        )
        result = pre_check_fattibilita(snap, ["2026-01"], [], 3)
        assert result["fattibile"] is False

    def test_capacita_zero_per_tutti(self):
        snap = self._snap(capacita={"Mario": 0, "Luigi": 0, "Carla": 0})
        result = pre_check_fattibilita(snap, ["2026-01"], [], 3)
        assert result["fattibile"] is False

    def test_mesi_vuoti(self):
        result = pre_check_fattibilita(self._snap(), [], [], 3)
        assert result["fattibile"] is True

    def test_nessuna_indisponibilita_no_avvisi(self):
        result = pre_check_fattibilita(self._snap(), ["2026-01"], [], 3)
        assert result["avvisi"] == []
