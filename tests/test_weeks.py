"""Test per turni_visite.weeks."""
import pytest
from turni_visite.weeks import month_sigla, slot_label, slot_label_with_month


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
