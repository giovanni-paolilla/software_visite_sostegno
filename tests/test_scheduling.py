"""Test per turni_visite.scheduling."""
import pytest
from turni_visite.scheduling import (
    validate_month_yyyy_mm,
    _month_to_idx,
    valida_soluzione,
    verifica_fattibilita,
    ottimizza_turni_mesi,
)


class TestValidateMonthYyyyMm:
    def test_formato_valido(self):
        assert validate_month_yyyy_mm("2025-03") == "2025-03"
        assert validate_month_yyyy_mm("2025-12") == "2025-12"
        assert validate_month_yyyy_mm("2025-01") == "2025-01"

    def test_strip_spazi(self):
        assert validate_month_yyyy_mm("  2025-03  ") == "2025-03"

    def test_formato_non_valido(self):
        for bad in ("2025-00", "2025-13", "202-03", "2025/03", "", "abc"):
            with pytest.raises(ValueError):
                validate_month_yyyy_mm(bad)

    def test_none_errore(self):
        with pytest.raises(ValueError):
            validate_month_yyyy_mm(None)


class TestMonthToIdx:
    def test_ordinamento_corretto(self):
        assert _month_to_idx("2025-01") < _month_to_idx("2025-02")
        assert _month_to_idx("2025-12") < _month_to_idx("2026-01")

    def test_distanza_un_mese(self):
        assert _month_to_idx("2025-02") - _month_to_idx("2025-01") == 1
        assert _month_to_idx("2026-01") - _month_to_idx("2025-12") == 1


class TestValidaSoluzione:
    def test_nessun_errore(self):
        by_family = {"Fam A": ["Mario", "Luigi"]}
        frequenze = {"Fam A": 2}
        assert valida_soluzione(by_family, frequenze) == []

    def test_slot_errati(self):
        by_family = {"Fam A": ["Mario"]}
        frequenze = {"Fam A": 2}
        errori = valida_soluzione(by_family, frequenze)
        assert len(errori) == 1
        assert "Fam A" in errori[0]

    def test_duplicato_rilevato(self):
        by_family = {"Fam A": ["Mario", "Mario"]}
        frequenze = {"Fam A": 2}
        errori = valida_soluzione(by_family, frequenze)
        assert any("duplicat" in e.lower() for e in errori)


class TestVerificaFattibilita:
    def _base(self):
        return (
            {"Mario", "Luigi"},
            {"Fam A"},
            {"Fam A": ["Mario", "Luigi"]},
            {"Fam A": 2},
            {"Mario": 1, "Luigi": 1},
        )

    def test_ok(self):
        assert verifica_fattibilita(*self._base()) == []

    def test_famiglia_senza_associati(self):
        fratelli, famiglie, assoc, freq, cap = self._base()
        assoc = {}
        problemi = verifica_fattibilita(fratelli, famiglie, assoc, freq, cap)
        assert any("senza" in p.lower() for p in problemi)

    def test_capacita_insufficiente(self):
        fratelli, famiglie, assoc, freq, cap = self._base()
        cap = {"Mario": 0, "Luigi": 0}
        problemi = verifica_fattibilita(fratelli, famiglie, assoc, freq, cap)
        assert any("capacit" in p.lower() for p in problemi)

    def test_meno_associati_della_frequenza(self):
        fratelli, famiglie, assoc, freq, cap = self._base()
        freq = {"Fam A": 4}   # richiede 4 slot ma ci sono solo 2 associati
        problemi = verifica_fattibilita(fratelli, famiglie, assoc, freq, cap)
        assert any("meno" in p.lower() for p in problemi)


# ---------------------------------------------------------------------------
# Test integrazione solver (saltato se ortools non disponibile)
# ---------------------------------------------------------------------------

try:
    from ortools.sat.python import cp_model as _cp
    _ORTOOLS_OK = True
except Exception:
    _ORTOOLS_OK = False

pytestmark_ortools = pytest.mark.skipif(
    not _ORTOOLS_OK, reason="ortools non installato"
)


@pytestmark_ortools
class TestOttimizzaTurniMesi:
    def _params_base(self):
        fratelli = {"Mario", "Luigi", "Carla", "Anna"}
        famiglie = {"Fam A", "Fam B"}
        associazioni = {
            "Fam A": ["Mario", "Luigi", "Carla"],
            "Fam B": ["Luigi", "Carla", "Anna"],
        }
        frequenze = {"Fam A": 2, "Fam B": 2}
        capacita = {fr: 2 for fr in fratelli}
        return fratelli, famiglie, associazioni, frequenze, capacita

    def test_soluzione_trovata(self):
        fr, fam, assoc, freq, cap = self._params_base()
        sol = ottimizza_turni_mesi(
            mesi=["2025-03"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=1,
        )
        assert sol is not None
        assert "by_month" in sol
        assert "2025-03" in sol["by_month"]

    def test_slot_corretti(self):
        fr, fam, assoc, freq, cap = self._params_base()
        sol = ottimizza_turni_mesi(
            mesi=["2025-03"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=1,
        )
        blocco = sol["by_month"]["2025-03"]["by_family"]
        for famiglia, slots in blocco.items():
            assert len(slots) == freq[famiglia]
            assert len(slots) == len(set(slots))  # niente duplicati

    def test_cooldown_rispettato(self):
        """Con cooldown=2 su 2 mesi consecutivi, nessun fratello puo' comparire in entrambi."""
        fr, fam, assoc, freq, cap = self._params_base()
        sol = ottimizza_turni_mesi(
            mesi=["2025-03", "2025-04"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=2,
        )
        assert sol is not None
        for famiglia in fam:
            slots_mar = set(sol["by_month"]["2025-03"]["by_family"].get(famiglia, []))
            slots_apr = set(sol["by_month"]["2025-04"]["by_family"].get(famiglia, []))
            assert slots_mar.isdisjoint(slots_apr), (
                f"Cooldown violato per {famiglia}: {slots_mar} ∩ {slots_apr}"
            )

    def test_infeasible_ritorna_none(self):
        """Un solo fratello con capacita' 0 non puo' coprire nessuna famiglia."""
        sol = ottimizza_turni_mesi(
            mesi=["2025-03"],
            fratelli={"Solo"},
            famiglie={"Fam A"},
            associazioni={"Fam A": ["Solo"]},
            frequenze={"Fam A": 2},
            capacita={"Solo": 0},
            cooldown_mesi=1,
        )
        assert sol is None

    def test_mesi_ordinati_automaticamente(self):
        """Passare mesi in ordine inverso deve produrre lo stesso risultato."""
        fr, fam, assoc, freq, cap = self._params_base()
        sol = ottimizza_turni_mesi(
            mesi=["2025-04", "2025-03"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=1,
        )
        assert sol is not None
        assert set(sol["by_month"].keys()) == {"2025-03", "2025-04"}

    def test_storico_vincola_primo_mese(self):
        """Se Mario ha visitato Fam A a 2025-02 con cooldown=2, non puo' farlo a 2025-03."""
        fr, fam, assoc, freq, cap = self._params_base()
        storico = [{
            "mese": "2025-02",
            "assegnazioni": [
                {"famiglia": "Fam A", "fratello": "Mario", "slot": 0},
                {"famiglia": "Fam A", "fratello": "Luigi", "slot": 1},
            ],
        }]
        sol = ottimizza_turni_mesi(
            mesi=["2025-03"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            storico_turni=storico,
            cooldown_mesi=2,
        )
        if sol is not None:
            slots_mar = sol["by_month"]["2025-03"]["by_family"].get("Fam A", [])
            assert "Mario" not in slots_mar
            assert "Luigi" not in slots_mar
