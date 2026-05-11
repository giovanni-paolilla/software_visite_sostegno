"""Test per turni_visite.pdf_export."""
import os
import pytest

from turni_visite.pdf_export import export_pdf_mesi, _make_table_compact, _make_header_footer


def _solution(mese="2026-01"):
    return {
        "by_month": {
            mese: {
                "by_family": {
                    "Fam A": ["Mario", "Luigi"],
                    "Fam B": ["Carla"],
                },
                "by_brother": {
                    "Mario": ["Fam A"],
                    "Luigi": ["Fam A"],
                    "Carla": ["Fam B"],
                },
            }
        }
    }


def _frequenze():
    return {"Fam A": 2, "Fam B": 1}


class TestExportPdfMesi:
    def test_crea_file_pdf(self, tmp_path):
        out = tmp_path / "turni.pdf"
        export_pdf_mesi(["2026-01"], _solution(), _frequenze(), {}, str(out))
        assert out.exists()
        assert out.stat().st_size > 0

    def test_contenuto_pdf_valido(self, tmp_path):
        out = tmp_path / "turni.pdf"
        export_pdf_mesi(["2026-01"], _solution(), _frequenze(), {}, str(out))
        with open(out, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    def test_solution_vuota_non_crea_file(self, tmp_path):
        out = tmp_path / "vuoto.pdf"
        export_pdf_mesi(["2026-01"], {}, {}, {}, str(out))
        assert not out.exists()

    def test_solution_by_month_vuoto(self, tmp_path):
        out = tmp_path / "vuoto.pdf"
        export_pdf_mesi(["2026-01"], {"by_month": {}}, {}, {}, str(out))
        assert not out.exists()

    def test_solution_none(self, tmp_path):
        out = tmp_path / "vuoto.pdf"
        export_pdf_mesi(["2026-01"], None, {}, {}, str(out))
        assert not out.exists()

    def test_piu_mesi_con_page_break(self, tmp_path):
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
        out = tmp_path / "multi.pdf"
        export_pdf_mesi(["2026-01", "2026-02"], sol, {"Fam A": 1}, {}, str(out))
        assert out.exists()
        assert out.stat().st_size > 0

    def test_mese_non_presente_in_solution_ignorato(self, tmp_path):
        out = tmp_path / "skip.pdf"
        export_pdf_mesi(["2026-01", "2026-03"], _solution("2026-01"), _frequenze(), {}, str(out))
        assert out.exists()

    def test_con_week_windows(self, tmp_path):
        ww = {"2026-01": {2: ["01-07", "15-21"], 1: ["08-14"]}}
        out = tmp_path / "ww.pdf"
        export_pdf_mesi(["2026-01"], _solution(), _frequenze(), ww, str(out))
        assert out.exists()

    def test_output_path_default_usa_config(self, tmp_path, monkeypatch):
        import turni_visite.pdf_export as mod
        default_path = tmp_path / "default.pdf"
        monkeypatch.setattr(mod, "PDF_FILENAME", str(default_path))
        export_pdf_mesi(["2026-01"], _solution(), _frequenze(), {})
        assert default_path.exists()

    def test_tight_layout_molte_righe(self, tmp_path):
        fams = {f"Fam{i}": [f"Fr{i}"] for i in range(30)}
        bros = {f"Fr{i}": [f"Fam{i}"] for i in range(30)}
        sol = {"by_month": {"2026-01": {"by_family": fams, "by_brother": bros}}}
        freq = {f"Fam{i}": 1 for i in range(30)}
        out = tmp_path / "tight.pdf"
        export_pdf_mesi(["2026-01"], sol, freq, {}, str(out))
        assert out.exists()

    def test_fratello_non_trovato_in_by_family(self, tmp_path):
        sol = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Fam A": ["Mario"]},
                    "by_brother": {"Luigi": ["Fam A"]},
                }
            }
        }
        out = tmp_path / "mismatch.pdf"
        export_pdf_mesi(["2026-01"], sol, {"Fam A": 1}, {}, str(out))
        assert out.exists()

    def test_errore_scrittura(self, tmp_path):
        bad_path = "/path/assolutamente/inesistente/turni.pdf"
        with pytest.raises(OSError):
            export_pdf_mesi(["2026-01"], _solution(), _frequenze(), {}, bad_path)


class TestMakeTableCompact:
    def test_crea_tabella(self):
        data = [["Col1", "Col2"], ["a", "b"]]
        t = _make_table_compact(data)
        assert t is not None

    def test_con_custom_params(self):
        data = [["Col1"], ["a"]]
        t = _make_table_compact(data, header_font=8, body_font=7, padding=1)
        assert t is not None


class TestMakeHeaderFooter:
    def test_ritorna_callable(self):
        cb = _make_header_footer("Titolo Test", "2026-01-01 10:00")
        assert callable(cb)
