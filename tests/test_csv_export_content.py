"""Test per il contenuto effettivo dei CSV esportati."""
import csv
import pytest
from turni_visite.csv_export import (
    export_csv_mesi, export_csv_per_fratello, export_storico_csv, import_csv_anagrafica,
)


def _solution():
    return {
        "by_month": {
            "2026-01": {
                "by_family": {
                    "Fam A": ["Mario Rossi", "Luigi Bianchi"],
                    "Fam B": ["Carla Neri"],
                },
                "by_brother": {
                    "Mario Rossi": ["Fam A"],
                    "Luigi Bianchi": ["Fam A"],
                    "Carla Neri": ["Fam B"],
                },
            },
            "2026-02": {
                "by_family": {
                    "Fam A": ["Carla Neri", "Mario Rossi"],
                },
                "by_brother": {
                    "Mario Rossi": ["Fam A"],
                    "Carla Neri": ["Fam A"],
                },
            },
        }
    }


def _frequenze():
    return {"Fam A": 2, "Fam B": 1}


def _read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.reader(f, delimiter=";"))


class TestExportCsvMesiContent:
    def test_header_corretto(self, tmp_path):
        out = tmp_path / "turni.csv"
        export_csv_mesi(["2026-01"], _solution(), _frequenze(), {}, out)
        rows = _read_csv(out)
        assert rows[0] == ["Mese", "Famiglia", "Frequenza", "Slot", "Fratello", "Settimana"]

    def test_righe_dati_corrette(self, tmp_path):
        out = tmp_path / "turni.csv"
        export_csv_mesi(["2026-01"], _solution(), _frequenze(), {}, out)
        rows = _read_csv(out)
        data_rows = rows[1:]
        assert len(data_rows) == 3  # 2 per Fam A + 1 per Fam B
        mesi = {r[0] for r in data_rows}
        assert mesi == {"2026-01"}
        famiglie = {r[1] for r in data_rows}
        assert "Fam A" in famiglie
        assert "Fam B" in famiglie

    def test_piu_mesi(self, tmp_path):
        out = tmp_path / "multi.csv"
        export_csv_mesi(["2026-01", "2026-02"], _solution(), _frequenze(), {}, out)
        rows = _read_csv(out)
        data_rows = rows[1:]
        mesi = {r[0] for r in data_rows}
        assert "2026-01" in mesi
        assert "2026-02" in mesi

    def test_con_week_windows(self, tmp_path):
        ww = {"2026-01": {2: ["01-07", "15-21"], 1: ["08-14"]}}
        out = tmp_path / "ww.csv"
        export_csv_mesi(["2026-01"], _solution(), _frequenze(), ww, out)
        rows = _read_csv(out)
        settimane = [r[5] for r in rows[1:]]
        assert any("01-07" in s or "15-21" in s or "08-14" in s for s in settimane)

    def test_encoding_utf8_bom(self, tmp_path):
        out = tmp_path / "bom.csv"
        export_csv_mesi(["2026-01"], _solution(), _frequenze(), {}, out)
        with open(out, "rb") as f:
            header = f.read(3)
        assert header == b"\xef\xbb\xbf"

    def test_mese_senza_dati_ignorato(self, tmp_path):
        out = tmp_path / "skip.csv"
        export_csv_mesi(["2026-01", "2026-12"], _solution(), _frequenze(), {}, out)
        rows = _read_csv(out)
        mesi = {r[0] for r in rows[1:]}
        assert "2026-12" not in mesi


class TestExportCsvPerFratelloContent:
    def test_header_corretto(self, tmp_path):
        out = tmp_path / "fratelli.csv"
        export_csv_per_fratello(["2026-01"], _solution(), _frequenze(), {}, out)
        rows = _read_csv(out)
        assert rows[0] == ["Fratello", "Mese", "Famiglia", "Settimana"]

    def test_contenuto_per_fratello(self, tmp_path):
        out = tmp_path / "fratelli.csv"
        export_csv_per_fratello(["2026-01"], _solution(), _frequenze(), {}, out)
        rows = _read_csv(out)
        data_rows = rows[1:]
        fratelli = {r[0] for r in data_rows}
        assert "Mario Rossi" in fratelli
        assert "Luigi Bianchi" in fratelli
        assert "Carla Neri" in fratelli

    def test_nessuna_soluzione(self, tmp_path):
        out = tmp_path / "vuoto.csv"
        export_csv_per_fratello([], {}, {}, {}, out)
        assert not out.exists()


class TestExportStoricoCsvContent:
    def test_header_e_dati(self, tmp_path):
        storico = [
            {
                "mese": "2026-01",
                "confirmed_at": "2026-01-15T10:00:00",
                "assegnazioni": [
                    {"famiglia": "Fam A", "fratello": "Mario", "slot": 0},
                    {"famiglia": "Fam A", "fratello": "Luigi", "slot": 1},
                ],
            },
        ]
        out = tmp_path / "storico.csv"
        export_storico_csv(storico, out)
        rows = _read_csv(out)
        assert rows[0] == ["Mese", "Confermato", "Famiglia", "Fratello", "Slot"]
        assert len(rows) == 3

    def test_record_non_dict_ignorato(self, tmp_path):
        storico = ["invalid", 42, {"mese": "2026-01", "confirmed_at": "", "assegnazioni": []}]
        out = tmp_path / "storico.csv"
        export_storico_csv(storico, out)
        rows = _read_csv(out)
        assert len(rows) == 1  # solo header

    def test_storico_vuoto(self, tmp_path):
        out = tmp_path / "vuoto.csv"
        export_storico_csv([], out)
        rows = _read_csv(out)
        assert len(rows) == 1  # solo header


class TestImportCsvAnagraficaContent:
    def test_fratello_capacita_fuori_range(self, tmp_path):
        csv_file = tmp_path / "import.csv"
        csv_file.write_text("tipo;nome;valore\nfratello;Mario;100\n", encoding="utf-8")
        result = import_csv_anagrafica(csv_file)
        assert result["fratelli"][0][1] == 1  # clampato a default

    def test_famiglia_frequenza_non_valida(self, tmp_path):
        csv_file = tmp_path / "import.csv"
        csv_file.write_text("tipo;nome;valore\nfamiglia;Fam A;3\n", encoding="utf-8")
        result = import_csv_anagrafica(csv_file)
        assert result["famiglie"][0][1] == 2  # default

    def test_riga_campi_insufficienti(self, tmp_path):
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text("tipo;nome\nfratello\n", encoding="utf-8")
        result = import_csv_anagrafica(csv_file)
        assert len(result["errori"]) == 1
        assert "insufficienti" in result["errori"][0]

    def test_header_ignorato(self, tmp_path):
        csv_file = tmp_path / "with_header.csv"
        csv_file.write_text(
            "tipo;nome;valore\nfratello;Mario;2\nfamiglia;Fam A;2\n",
            encoding="utf-8",
        )
        result = import_csv_anagrafica(csv_file)
        assert len(result["fratelli"]) == 1
        assert len(result["famiglie"]) == 1
        assert len(result["errori"]) == 0

    def test_righe_vuote_ignorate(self, tmp_path):
        csv_file = tmp_path / "empty_rows.csv"
        csv_file.write_text("tipo;nome;valore\n\nfratello;Mario;1\n\n", encoding="utf-8")
        result = import_csv_anagrafica(csv_file)
        assert len(result["fratelli"]) == 1
        assert len(result["errori"]) == 0

    def test_encoding_bom(self, tmp_path):
        csv_file = tmp_path / "bom.csv"
        csv_file.write_bytes(b"\xef\xbb\xbftipo;nome;valore\nfratello;Mario;1\n")
        result = import_csv_anagrafica(csv_file)
        assert len(result["fratelli"]) == 1
