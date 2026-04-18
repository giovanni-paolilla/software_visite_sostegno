"""Test per turni_visite.csv_export."""
import csv
import pytest
from turni_visite.csv_export import (
    export_csv_mesi, export_csv_per_fratello, export_storico_csv, import_csv_anagrafica,
)


def _solution():
    return {
        "by_month": {
            "2026-01": {
                "by_family": {"Fam A": ["Mario Rossi"], "Fam B": ["Luigi Bianchi"]},
                "by_brother": {"Mario Rossi": ["Fam A"], "Luigi Bianchi": ["Fam B"]},
            }
        }
    }


class TestExportCsvMesi:
    def test_crea_file(self, tmp_path):
        out = tmp_path / "turni.csv"
        export_csv_mesi(["2026-01"], _solution(), {"Fam A": 1, "Fam B": 1}, {}, out)
        assert out.exists()
        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.reader(f, delimiter=";"))
        assert len(rows) >= 3  # header + 2 righe

    def test_nessuna_soluzione(self, tmp_path):
        out = tmp_path / "vuoto.csv"
        export_csv_mesi([], {}, {}, {}, out)
        assert not out.exists()


class TestExportCsvPerFratello:
    def test_crea_file(self, tmp_path):
        out = tmp_path / "fratelli.csv"
        export_csv_per_fratello(["2026-01"], _solution(), {"Fam A": 1, "Fam B": 1}, {}, out)
        assert out.exists()


class TestExportStoricoCsv:
    def test_crea_file(self, tmp_path):
        storico = [
            {"mese": "2026-01", "confirmed_at": "2026-01-15",
             "assegnazioni": [{"famiglia": "Fam A", "fratello": "Mario", "slot": 0}]}
        ]
        out = tmp_path / "storico.csv"
        export_storico_csv(storico, out)
        assert out.exists()


class TestImportCsvAnagrafica:
    def test_import_valido(self, tmp_path):
        csv_file = tmp_path / "import.csv"
        csv_file.write_text(
            "tipo;nome;valore\nfratello;Mario Rossi;3\nfamiglia;Fam A;4\n",
            encoding="utf-8",
        )
        result = import_csv_anagrafica(csv_file)
        assert len(result["fratelli"]) == 1
        assert result["fratelli"][0] == ("Mario Rossi", 3)
        assert len(result["famiglie"]) == 1
        assert result["famiglie"][0] == ("Fam A", 4)
        assert len(result["errori"]) == 0

    def test_tipo_sconosciuto(self, tmp_path):
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text("tipo;nome\nsconosciuto;Test\n", encoding="utf-8")
        result = import_csv_anagrafica(csv_file)
        assert len(result["errori"]) == 1

    def test_capacita_default(self, tmp_path):
        csv_file = tmp_path / "novalue.csv"
        csv_file.write_text("tipo;nome\nfratello;Mario\n", encoding="utf-8")
        result = import_csv_anagrafica(csv_file)
        assert result["fratelli"][0][1] == 1  # default cap=1
