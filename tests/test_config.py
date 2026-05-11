"""
Test per turni_visite.config.

Verifica che i percorsi derivati da PROJECT_DIR siano assoluti
e coerenti indipendentemente dalla working directory di avvio.
"""
from pathlib import Path
from turni_visite.config import PROJECT_DIR, DATA_FILE, PDF_FILENAME, PDF_MARGINS


class TestProjectDir:
    def test_e_path_assoluto(self):
        assert Path(PROJECT_DIR).is_absolute()

    def test_punta_alla_root_del_progetto(self):
        """PROJECT_DIR deve contenere sia pyproject.toml che la cartella turni_visite/."""
        assert (PROJECT_DIR / "turni_visite").is_dir()
        assert (PROJECT_DIR / "pyproject.toml").exists()

    def test_data_file_assoluto(self):
        assert Path(DATA_FILE).is_absolute()

    def test_pdf_filename_assoluto(self):
        assert Path(PDF_FILENAME).is_absolute()

    def test_margini_pdf_presenti(self):
        for chiave in ("left", "right", "top", "bottom"):
            assert chiave in PDF_MARGINS
            assert isinstance(PDF_MARGINS[chiave], (int, float))
            assert PDF_MARGINS[chiave] >= 0
