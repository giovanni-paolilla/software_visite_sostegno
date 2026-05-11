"""Test per turni_visite.normalization (include edge case unificati)."""
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
        assert canonicalizza_nome("MARIO ROSSI") == "Mario Rossi"

    def test_spazi_multipli_ridotti(self):
        assert canonicalizza_nome("Mario  Rossi") == "Mario Rossi"
        assert canonicalizza_nome("  Mario  Rossi  ") == "Mario Rossi"
        assert canonicalizza_nome("Mario   Rossi") == "Mario Rossi"

    def test_spazi_leading_trailing(self):
        assert canonicalizza_nome("  Mario Rossi  ") == "Mario Rossi"

    def test_nbsp_normalizzato(self):
        assert canonicalizza_nome("Mario\u00A0Rossi") == "Mario Rossi"

    def test_apostrofo_curvo_normalizzato(self):
        assert canonicalizza_nome("D\u2019Andrea") == "D'Andrea"
        assert canonicalizza_nome("D\u2018Andrea") == "D'Andrea"

    def test_apostrofo_singolo_sinistro(self):
        result = canonicalizza_nome("D'Andrea")
        assert result == "D'Andrea"

    def test_nome_con_apostrofo_valido(self):
        result = canonicalizza_nome("D'Angelo")
        assert result == "D'Angelo"

    def test_caratteri_accentati_ammessi(self):
        assert canonicalizza_nome("Jose\u0301") is not None  # NFKC normalize
        result = canonicalizza_nome("Mele\u00E0")
        assert result is not None

    def test_accenti(self):
        result = canonicalizza_nome("Andr\u00E9 Fran\u00E7ois")
        assert result == "Andr\u00E9 Fran\u00E7ois"

    def test_caratteri_non_ammessi_ritorna_none(self):
        assert canonicalizza_nome("Mario123") is None
        assert canonicalizza_nome("Mario@Rossi") is None
        assert canonicalizza_nome("@mario!") is None
        assert canonicalizza_nome("mario#rossi") is None

    def test_solo_numeri_ritorna_none(self):
        assert canonicalizza_nome("12345") is None

    def test_trattino_ammesso(self):
        assert canonicalizza_nome("Pio-Antonio") == "Pio-Antonio"
        assert canonicalizza_nome("Jean-Pierre") == "Jean-Pierre"

    def test_punto_ammesso(self):
        result = canonicalizza_nome("G. Rossi")
        assert result is not None
        assert canonicalizza_nome("Dr. Mario") == "Dr. Mario"

    def test_unicode_nfkc(self):
        result = canonicalizza_nome("\uFF2Dario")
        assert result is not None


class TestTrovaAliasSimilari:
    def test_nessun_simile(self):
        nomi = ["Mario", "Luigi", "Carla"]
        assert trova_alias_simili(nomi) == []

    def test_lista_vuota(self):
        assert trova_alias_simili([]) == []

    def test_singolo_nome(self):
        assert trova_alias_simili(["Mario Rossi"]) == []

    def test_nomi_identici(self):
        result = trova_alias_simili(["Mario Rossi", "Mario Rossi"])
        assert result == []

    def test_typo_rilevato(self):
        nomi = ["Smedile Giovanni", "Smegile Giovanni"]
        gruppi = trova_alias_simili(nomi, soglia=0.88)
        assert len(gruppi) == 1
        riferimento, simili = gruppi[0]
        tutti = {riferimento} | set(simili)
        assert "Smedile Giovanni" in tutti
        assert "Smegile Giovanni" in tutti

    def test_nomi_simili(self):
        result = trova_alias_simili(["Mario Rossi", "Mario Rosi"])
        assert len(result) == 1
        ref, sims = result[0]
        assert "Mario Rossi" in [ref] + sims
        assert "Mario Rosi" in [ref] + sims

    def test_nomi_diversi(self):
        result = trova_alias_simili(["Mario Rossi", "Luigi Bianchi"])
        assert result == []

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

    def test_soglia_zero_tutti_match(self):
        result = trova_alias_simili(["Abc", "Xyz"], soglia=0.0)
        assert len(result) == 1

    def test_soglia_uno_nessun_match(self):
        result = trova_alias_simili(["Mario Rossi", "Mario Rosi"], soglia=1.0)
        assert result == []

    def test_gruppi_multipli(self):
        result = trova_alias_simili([
            "Mario Rossi", "Mario Rosi",
            "Luigi Bianchi", "Lugi Bianchi",
        ])
        assert len(result) >= 2

    def test_non_doppio_conteggio(self):
        result = trova_alias_simili(["Abc", "Abd", "Abe"], soglia=0.5)
        seen = set()
        for ref, sims in result:
            assert ref not in seen
            for s in sims:
                assert s not in seen
            seen.add(ref)
            seen.update(sims)
