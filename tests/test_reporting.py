"""Test per turni_visite.reporting."""
import pytest
from turni_visite.reporting import print_reports_mesi


def _solution():
    return {
        "by_month": {
            "2026-01": {
                "by_family": {
                    "Fam A": ["Mario", "Luigi"],
                    "Fam B": ["Carla"],
                },
                "by_brother": {
                    "Mario": ["Fam A"],
                    "Luigi": ["Fam A"],
                    "Carla": ["Fam B"],
                    "Anna": [],
                },
            }
        }
    }


class TestPrintReportsMesi:
    def test_stampa_report(self, capsys):
        print_reports_mesi(["2026-01"], _solution(), {"Fam A": 2, "Fam B": 1}, {})
        out = capsys.readouterr().out
        assert "Mese 2026-01" in out
        assert "Fam A" in out
        assert "Fam B" in out
        assert "Mario" in out
        assert "Luigi" in out
        assert "Carla" in out

    def test_stampa_per_fratello(self, capsys):
        print_reports_mesi(["2026-01"], _solution(), {"Fam A": 2, "Fam B": 1}, {})
        out = capsys.readouterr().out
        assert "FRATELLO" in out
        assert "FAMIGLIA" in out

    def test_fratello_senza_visite(self, capsys):
        print_reports_mesi(["2026-01"], _solution(), {"Fam A": 2, "Fam B": 1}, {})
        out = capsys.readouterr().out
        assert "nessuna visita" in out

    def test_solution_vuota(self, capsys):
        print_reports_mesi(["2026-01"], {}, {}, {})
        out = capsys.readouterr().out
        assert "Nessuna soluzione" in out

    def test_solution_none(self, capsys):
        print_reports_mesi(["2026-01"], None, {}, {})
        out = capsys.readouterr().out
        assert "Nessuna soluzione" in out

    def test_mese_non_in_soluzione_ignorato(self, capsys):
        print_reports_mesi(["2026-02"], _solution(), {}, {})
        out = capsys.readouterr().out
        assert "2026-02" not in out or "Nessuna" not in out

    def test_con_week_windows(self, capsys):
        ww = {"2026-01": {2: ["01-07", "15-21"], 1: ["08-14"]}}
        print_reports_mesi(["2026-01"], _solution(), {"Fam A": 2, "Fam B": 1}, ww)
        out = capsys.readouterr().out
        assert "01-07" in out or "slot" in out

    def test_piu_mesi(self, capsys):
        sol = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Fam A": ["Mario"]},
                    "by_brother": {"Mario": ["Fam A"]},
                },
                "2026-02": {
                    "by_family": {"Fam A": ["Luigi"]},
                    "by_brother": {"Luigi": ["Fam A"]},
                },
            }
        }
        print_reports_mesi(["2026-01", "2026-02"], sol, {"Fam A": 1}, {})
        out = capsys.readouterr().out
        assert "2026-01" in out
        assert "2026-02" in out

    def test_fratello_senza_match_in_by_family(self, capsys):
        sol = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Fam A": ["Mario"]},
                    "by_brother": {"Luigi": ["Fam A"]},
                }
            }
        }
        print_reports_mesi(["2026-01"], sol, {"Fam A": 1}, {})
        out = capsys.readouterr().out
        assert "Luigi" in out
