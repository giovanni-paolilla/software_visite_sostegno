"""Test per turni_visite.i18n."""
import pytest
from turni_visite.i18n import t, set_language, get_language, get_available_languages


class TestI18n:
    def setup_method(self):
        set_language("it")

    def test_lingua_default_it(self):
        assert get_language() == "it"

    def test_traduzione_it(self):
        assert t("dashboard.titolo") == "Dashboard"
        assert t("anagrafica.fratello") == "Fratello"

    def test_traduzione_en(self):
        set_language("en")
        assert t("dashboard.titolo") == "Dashboard"
        assert t("anagrafica.fratello") == "Brother"

    def test_chiave_non_trovata(self):
        assert t("chiave.inesistente") == "chiave.inesistente"

    def test_lingua_non_supportata(self):
        with pytest.raises(ValueError):
            set_language("xx")

    def test_lingue_disponibili(self):
        langs = get_available_languages()
        assert "it" in langs
        assert "en" in langs
