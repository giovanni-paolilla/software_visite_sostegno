"""Test per turni_visite.weeks."""
import pytest
from turni_visite.weeks import month_sigla, parse_settimane_lista, slot_label, slot_label_with_month


class TestParseSettimanaLista:
    def test_valida_due_intervalli(self):
        result, err = parse_settimane_lista("01-07, 15-21", 2)
        assert result == ["01-07", "15-21"]
        assert err == ""

    def test_valida_un_intervallo(self):
        result, err = parse_settimane_lista("08-14", 1)
        assert result == ["08-14"]
        assert err == ""

    def test_valida_quattro_intervalli(self):
        result, err = parse_settimane_lista("01-07, 08-14, 15-21, 22-28", 4)
        assert result == ["01-07", "08-14", "15-21", "22-28"]
        assert err == ""

    def test_numero_intervalli_errato(self):
        result, err = parse_settimane_lista("01-07", 2)
        assert result is None
        assert "errato" in err

    def test_formato_non_valido(self):
        result, err = parse_settimane_lista("1-7, 15-21", 2)
        assert result is None
        assert err != ""

    def test_giorni_fuori_range(self):
        result, err = parse_settimane_lista("99-01", 1)
        assert result is None
        assert "fuori range" in err or "invertit" in err

    def test_giorni_invertiti(self):
        result, err = parse_settimane_lista("21-01", 1)
        assert result is None

    def test_stringa_vuota(self):
        result, err = parse_settimane_lista("", 1)
        assert result is None

    def test_normalizza_zeri(self):
        result, err = parse_settimane_lista("01-07", 1)
        assert result == ["01-07"]
        assert err == ""


class TestMonthSigla:
    def test_gennaio(self):
        assert month_sigla("2025-01") == "Gen"

    def test_dicembre(self):
        assert month_sigla("2025-12") == "Dic"

    def test_tutti_i_mesi(self):
        attese = ["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"]
        for i, sigla in enumerate(attese, 1):
            assert month_sigla(f"2025-{i:02d}") == sigla

    def test_formato_errato_ritorna_stringa_vuota(self):
        assert month_sigla("2025") == ""
        assert month_sigla("invalid") == ""


class TestSlotLabel:
    def _ww(self):
        return {"2025-03": {2: ["01-07", "15-21"]}}

    def test_slot_esistente(self):
        assert slot_label("2025-03", 2, 0, self._ww()) == "01-07"
        assert slot_label("2025-03", 2, 1, self._ww()) == "15-21"

    def test_slot_mancante_fallback(self):
        assert slot_label("2025-03", 2, 5, self._ww()) == "slot 6"

    def test_mese_mancante_fallback(self):
        assert slot_label("2025-99", 2, 0, self._ww()) == "slot 1"


class TestSlotLabelWithMonth:
    def _ww(self):
        return {"2025-03": {2: ["01-07", "15-21"]}}

    def test_include_sigla(self):
        label = slot_label_with_month("2025-03", 2, 0, self._ww())
        assert label == "01-07 Mar"

    def test_fallback_con_sigla(self):
        label = slot_label_with_month("2025-03", 2, 5, self._ww())
        assert label == "slot 6 Mar"
