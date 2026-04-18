"""Test per turni_visite.stats."""
import pytest
from turni_visite.stats import (
    report_carico_fratelli, report_copertura_famiglie,
    calcola_indice_equita, trend_mensile,
)


def _storico():
    return [
        {
            "mese": "2026-01",
            "confirmed_at": "2026-01-15",
            "assegnazioni": [
                {"famiglia": "Fam A", "fratello": "Mario", "slot": 0},
                {"famiglia": "Fam B", "fratello": "Mario", "slot": 0},
                {"famiglia": "Fam A", "fratello": "Luigi", "slot": 1},
            ],
        },
        {
            "mese": "2026-02",
            "confirmed_at": "2026-02-15",
            "assegnazioni": [
                {"famiglia": "Fam A", "fratello": "Luigi", "slot": 0},
                {"famiglia": "Fam B", "fratello": "Luigi", "slot": 0},
            ],
        },
    ]


class TestReportCaricoFratelli:
    def test_report_completo(self):
        report = report_carico_fratelli(_storico())
        assert len(report) == 2
        mario = next(r for r in report if r["fratello"] == "Mario")
        assert mario["visite_totali"] == 2
        assert mario["mesi_attivi"] == 1

    def test_storico_vuoto(self):
        assert report_carico_fratelli([]) == []

    def test_filtro_mesi(self):
        report = report_carico_fratelli(_storico(), mesi_filtro=["2026-01"])
        mario = next(r for r in report if r["fratello"] == "Mario")
        assert mario["visite_totali"] == 2
        luigi = next(r for r in report if r["fratello"] == "Luigi")
        assert luigi["visite_totali"] == 1

    def test_ordine_decrescente(self):
        report = report_carico_fratelli(_storico())
        assert report[0]["visite_totali"] >= report[-1]["visite_totali"]


class TestReportCoperturaFamiglie:
    def test_report_completo(self):
        report = report_copertura_famiglie(_storico())
        assert len(report) == 2
        fam_a = next(r for r in report if r["famiglia"] == "Fam A")
        assert fam_a["visite_totali"] == 3

    def test_famiglia_non_coperta(self):
        report = report_copertura_famiglie([], famiglie_attive={"Fam X"})
        assert len(report) == 1
        assert report[0]["visite_totali"] == 0


class TestCalcolaIndiceEquita:
    def test_con_dati(self):
        eq = calcola_indice_equita(_storico())
        assert eq["media"] > 0
        assert 0 <= eq["indice_gini"] <= 1
        assert eq["fratello_min"] in ("Mario", "Luigi")
        assert eq["fratello_max"] in ("Mario", "Luigi")

    def test_storico_vuoto(self):
        eq = calcola_indice_equita([])
        assert eq["media"] == 0
        assert eq["indice_gini"] == 0


class TestTrendMensile:
    def test_trend(self):
        data = trend_mensile(_storico())
        assert len(data) == 2
        assert data[0]["mese"] == "2026-01"
        assert data[0]["n_visite"] == 3
        assert data[1]["mese"] == "2026-02"
        assert data[1]["n_visite"] == 2

    def test_vuoto(self):
        assert trend_mensile([]) == []
