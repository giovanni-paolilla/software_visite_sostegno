"""Test per turni_visite.normalization."""
import pytest
from turni_visite.normalization import canonicalizza_nome, trova_alias_simili


class TestCanonicalizzaNome:
    def test_none_ritorna_none(self):
        assert canonicalizza_nome(None) is None

    def test_stringa_vuota_ritorna_none(self):
        assert canonicalizza_nome("") is None
        assert canonicalizza_nome("   ") is None

    def test_title_case(self):
        assert canonicalizza_nome("mario rossi") == "Mario Rossi"
        assert canonicalizza_nome("LUIGI BIANCHI") == "Luigi Bianchi"

    def test_spazi_multipli_ridotti(self):
        assert canonicalizza_nome("Mario  Rossi") == "Mario Rossi"
        assert canonicalizza_nome("  Mario  Rossi  ") == "Mario Rossi"

    def test_nbsp_normalizzato(self):
        assert canonicalizza_nome("Mario\u00A0Rossi") == "Mario Rossi"

    def test_apostrofo_curvo_normalizzato(self):
        assert canonicalizza_nome("D\u2019Andrea") == "D'Andrea"
        assert canonicalizza_nome("D\u2018Andrea") == "D'Andrea"

    def test_caratteri_accentati_ammessi(self):
        assert canonicalizza_nome("Jose\u0301") is not None  # NFKC normalize
        result = canonicalizza_nome("Mele\u00E0")
        assert result is not None

    def test_caratteri_non_ammessi_ritorna_none(self):
        assert canonicalizza_nome("Mario123") is None
        assert canonicalizza_nome("Mario@Rossi") is None

    def test_trattino_ammesso(self):
        assert canonicalizza_nome("Pio-Antonio") == "Pio-Antonio"

    def test_punto_ammesso(self):
        result = canonicalizza_nome("G. Rossi")
        assert result is not None


class TestTrovaAliasSimilari:
    def test_nessun_simile(self):
        nomi = ["Mario", "Luigi", "Carla"]
        assert trova_alias_simili(nomi) == []

    def test_typo_rilevato(self):
        nomi = ["Smedile Giovanni", "Smegile Giovanni"]
        gruppi = trova_alias_simili(nomi, soglia=0.88)
        assert len(gruppi) == 1
        riferimento, simili = gruppi[0]
        tutti = {riferimento} | set(simili)
        assert "Smedile Giovanni" in tutti
        assert "Smegile Giovanni" in tutti

    def test_duplicati_ignorati(self):
        nomi = ["Mario", "Mario", "Luigi"]
        gruppi = trova_alias_simili(nomi)
        assert len(gruppi) == 0  # nessuna coppia simile distinta

    def test_soglia_personalizzata(self):
        nomi = ["Aaa", "Aab"]
        # soglia alta: nessun match
        assert trova_alias_simili(nomi, soglia=0.99) == []
        # soglia bassa: trovato
        assert len(trova_alias_simili(nomi, soglia=0.5)) == 1
