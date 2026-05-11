"""Test per la logica GUI testabile senza display — widgets.py, themes.py e i18n wiring."""
import pytest
from unittest.mock import patch, MagicMock

# Skip dei test GUI se customtkinter non e' installato in questo ambiente.
customtkinter = pytest.importorskip(
    "customtkinter", reason="customtkinter non installato"
)


# ---------------------------------------------------------------------------
# themes.py — puro wrapper, testabile senza display
# ---------------------------------------------------------------------------

class TestThemes:
    def test_colors_dict_completo(self):
        from turni_visite.gui.themes import COLORS
        for mode in ("light", "dark"):
            assert mode in COLORS
            for key in ("success", "warning", "danger", "muted", "accent", "cal_bg", "cal_fg", "cal_header"):
                assert key in COLORS[mode]

    def test_set_appearance(self):
        with patch("turni_visite.gui.themes.ctk") as mock_ctk:
            from turni_visite.gui.themes import set_appearance
            set_appearance("Dark")
            mock_ctk.set_appearance_mode.assert_called_with("Dark")

    def test_set_color_theme(self):
        with patch("turni_visite.gui.themes.ctk") as mock_ctk:
            from turni_visite.gui.themes import set_color_theme
            set_color_theme("green")
            mock_ctk.set_default_color_theme.assert_called_with("green")

    def test_get_colors_light(self):
        with patch("turni_visite.gui.themes.ctk") as mock_ctk:
            mock_ctk.get_appearance_mode.return_value = "Light"
            from turni_visite.gui.themes import get_colors
            colors = get_colors()
            assert colors["accent"] == "#0078d4"

    def test_get_colors_dark(self):
        with patch("turni_visite.gui.themes.ctk") as mock_ctk:
            mock_ctk.get_appearance_mode.return_value = "Dark"
            from turni_visite.gui.themes import get_colors
            colors = get_colors()
            assert colors["accent"] == "#569cd6"

    def test_get_colors_unknown_fallback(self):
        with patch("turni_visite.gui.themes.ctk") as mock_ctk:
            mock_ctk.get_appearance_mode.return_value = "Unknown"
            from turni_visite.gui.themes import get_colors
            colors = get_colors()
            assert "accent" in colors


# ---------------------------------------------------------------------------
# i18n — copertura completa lingue e edge case
# ---------------------------------------------------------------------------

class TestI18nCoverage:
    def test_tutte_chiavi_it_presenti_in_en(self):
        from turni_visite.i18n import _TRANSLATIONS
        it_keys = set(_TRANSLATIONS["it"].keys())
        en_keys = set(_TRANSLATIONS["en"].keys())
        missing = it_keys - en_keys
        assert missing == set(), f"Chiavi IT mancanti in EN: {missing}"

    def test_tutte_chiavi_en_presenti_in_it(self):
        from turni_visite.i18n import _TRANSLATIONS
        it_keys = set(_TRANSLATIONS["it"].keys())
        en_keys = set(_TRANSLATIONS["en"].keys())
        missing = en_keys - it_keys
        assert missing == set(), f"Chiavi EN mancanti in IT: {missing}"

    def test_set_language_invalida(self):
        from turni_visite.i18n import set_language
        with pytest.raises(ValueError, match="non supportata"):
            set_language("xx")

    def test_get_available_languages(self):
        from turni_visite.i18n import get_available_languages
        langs = get_available_languages()
        assert "it" in langs
        assert "en" in langs

    def test_t_chiave_mancante_ritorna_chiave(self):
        from turni_visite.i18n import t, set_language, get_language
        old = get_language()
        set_language("it")
        result = t("chiave.inesistente.totalmente")
        assert result == "chiave.inesistente.totalmente"
        set_language(old)

    def test_t_lingua_en(self):
        from turni_visite.i18n import t, set_language, get_language
        old = get_language()
        set_language("en")
        assert t("dashboard.titolo") == "Dashboard"
        assert t("anagrafica.titolo") == "Registry"
        set_language(old)

    def test_persistenza_lingua(self):
        from turni_visite.i18n import set_language, get_language
        old = get_language()
        set_language("en")
        assert get_language() == "en"
        set_language("it")
        assert get_language() == "it"
        set_language(old)


# ---------------------------------------------------------------------------
# widgets.py — CTkListbox logica interna (senza rendering)
# ---------------------------------------------------------------------------

class TestCTkListboxLogic:
    """Test logica di CTkListbox senza necessità di display."""

    @pytest.fixture
    def listbox_mock(self):
        """Crea una CTkListbox mockata (bypass tkinter)."""
        with patch("turni_visite.gui.widgets.ctk.CTkScrollableFrame.__init__", return_value=None):
            with patch("turni_visite.gui.widgets.ctk.CTkScrollableFrame.event_generate"):
                from turni_visite.gui.widgets import CTkListbox
                lb = CTkListbox.__new__(CTkListbox)
                lb._items = []
                lb._buttons = []
                lb._selected = None
                lb._command = None
                lb._normal_color = "transparent"
                lb._selected_color = ("gray70", "gray30")
                lb._rebuild_after_id = None
                return lb

    def test_insert_e_size(self, listbox_mock):
        lb = listbox_mock
        # Patcha _schedule_rebuild (chiamato da insert/delete) per evitare tkinter.after()
        with patch.object(lb, "_schedule_rebuild"):
            lb.insert("end", "Item 1")
            lb.insert("end", "Item 2")
        assert lb.size() == 2
        assert lb.get(0) == "Item 1"
        assert lb.get(1) == "Item 2"

    def test_insert_at_index(self, listbox_mock):
        lb = listbox_mock
        with patch.object(lb, "_schedule_rebuild"):
            lb.insert("end", "A")
            lb.insert("end", "C")
            lb.insert(1, "B")
        assert lb._items == ["A", "B", "C"]

    def test_delete_singolo(self, listbox_mock):
        lb = listbox_mock
        with patch.object(lb, "_schedule_rebuild"):
            lb.insert("end", "A")
            lb.insert("end", "B")
            lb.insert("end", "C")
            lb.delete(1)
        assert lb._items == ["A", "C"]

    def test_delete_range(self, listbox_mock):
        lb = listbox_mock
        with patch.object(lb, "_schedule_rebuild"):
            lb.insert("end", "A")
            lb.insert("end", "B")
            lb.insert("end", "C")
            lb.delete(0, "end")
        assert lb._items == []

    def test_curselection_nessuna(self, listbox_mock):
        assert listbox_mock.curselection() == ()

    def test_curselection_con_selezione(self, listbox_mock):
        listbox_mock._selected = 2
        assert listbox_mock.curselection() == (2,)


# ---------------------------------------------------------------------------
# FilterableComboBox logica interna
# ---------------------------------------------------------------------------

class TestFilterableComboBoxLogic:
    def test_matches_filtra_per_prefisso(self):
        with patch("turni_visite.gui.widgets.ctk.CTkComboBox.__init__", return_value=None):
            with patch("turni_visite.gui.widgets.ctk.CTkComboBox.set"):
                from turni_visite.gui.widgets import FilterableComboBox
                cb = FilterableComboBox.__new__(FilterableComboBox)
                cb._all_values = ["Mario Rossi", "Marco Bianchi", "Luigi Neri"]
                cb._prefix = ""
                cb._prefix_idx = 0
                cb._after_id = None
                cb._reset_ms = 800
                matches = cb._matches("Mar")
        assert "Mario Rossi" in matches
        assert "Marco Bianchi" in matches
        assert "Luigi Neri" not in matches

    def test_matches_case_insensitive(self):
        with patch("turni_visite.gui.widgets.ctk.CTkComboBox.__init__", return_value=None):
            with patch("turni_visite.gui.widgets.ctk.CTkComboBox.set"):
                from turni_visite.gui.widgets import FilterableComboBox
                cb = FilterableComboBox.__new__(FilterableComboBox)
                cb._all_values = ["Mario Rossi"]
                matches = cb._matches("mario")
        assert matches == ["Mario Rossi"]

    def test_configure_aggiorna_values(self):
        with patch("turni_visite.gui.widgets.ctk.CTkComboBox.__init__", return_value=None):
            with patch("turni_visite.gui.widgets.ctk.CTkComboBox.set"):
                with patch("turni_visite.gui.widgets.ctk.CTkComboBox.configure"):
                    from turni_visite.gui.widgets import FilterableComboBox
                    cb = FilterableComboBox.__new__(FilterableComboBox)
                    cb._all_values = ["Old"]
                    cb.configure(values=["New1", "New2"])
        assert cb._all_values == ["New1", "New2"]
