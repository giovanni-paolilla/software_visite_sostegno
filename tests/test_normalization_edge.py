"""Test edge case per normalization.py — canonicalizza_nome e trova_alias_simili."""
import pytest
from turni_visite.normalization import canonicalizza_nome, trova_alias_simili


class TestCanonicalizzaNomeEdgeCases:
    def test_none(self):
        assert canonicalizza_nome(None) is None

    def test_stringa_vuota(self):
        assert canonicalizza_nome("") is None

    def test_solo_spazi(self):
        assert canonicalizza_nome("   ") is None

    def test_solo_numeri(self):
        assert canonicalizza_nome("12345") is None

    def test_caratteri_speciali_invalidi(self):
        assert canonicalizza_nome("@mario!") is None
        assert canonicalizza_nome("mario#rossi") is None

    def test_apostrofo_curvo_normalizzato(self):
        result = canonicalizza_nome("D’Andrea")
        assert result == "D'Andrea"

    def test_apostrofo_singolo_sinistro(self):
        result = canonicalizza_nome("D‘Andrea")
        assert result == "D'Andrea"

    def test_spazi_multipli_normalizzati(self):
        result = canonicalizza_nome("Mario   Rossi")
        assert result == "Mario Rossi"

    def test_nbsp_normalizzato(self):
        result = canonicalizza_nome("Mario Rossi")
        assert result == "Mario Rossi"

    def test_title_case(self):
        assert canonicalizza_nome("mario rossi") == "Mario Rossi"
        assert canonicalizza_nome("MARIO ROSSI") == "Mario Rossi"

    def test_accenti(self):
        result = canonicalizza_nome("André François")
        assert result == "André François"

    def test_trattino(self):
        result = canonicalizza_nome("Jean-Pierre")
        assert result == "Jean-Pierre"

    def test_punto_nel_nome(self):
        result = canonicalizza_nome("Dr. Mario")
        assert result == "Dr. Mario"

    def test_unicode_nfkc(self):
        result = canonicalizza_nome("Ｍario")
        assert result is not None

    def test_nome_con_apostrofo_valido(self):
        result = canonicalizza_nome("D'Angelo")
        assert result == "D'Angelo"

    def test_spazi_leading_trailing(self):
        result = canonicalizza_nome("  Mario Rossi  ")
        assert result == "Mario Rossi"


class TestTrovaAliasSimili:
    def test_lista_vuota(self):
        assert trova_alias_simili([]) == []

    def test_singolo_nome(self):
        assert trova_alias_simili(["Mario Rossi"]) == []

    def test_nomi_identici(self):
        result = trova_alias_simili(["Mario Rossi", "Mario Rossi"])
        assert result == []

    def test_nomi_simili(self):
        result = trova_alias_simili(["Mario Rossi", "Mario Rosi"])
        assert len(result) == 1
        ref, sims = result[0]
        assert "Mario Rossi" in [ref] + sims
        assert "Mario Rosi" in [ref] + sims

    def test_nomi_diversi(self):
        result = trova_alias_simili(["Mario Rossi", "Luigi Bianchi"])
        assert result == []

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
