"""Test per turni_visite.whatsapp_export."""
import pytest

from turni_visite.whatsapp_export import format_whatsapp_mesi
from turni_visite.domain import NON_ASSEGNATO


def _soluzione_base(mese: str) -> dict:
    """Costruisce una soluzione minima per un mese con una famiglia e due fratelli."""
    return {
        "by_month": {
            mese: {
                "by_family": {
                    "Famiglia Verdi": ["Mario Rossi", "Luigi Bianchi"],
                },
                "by_brother": {
                    "Mario Rossi": ["Famiglia Verdi"],
                    "Luigi Bianchi": ["Famiglia Verdi"],
                },
            }
        }
    }


class TestFormatWhatsappMesi:
    def test_lista_mesi_vuota_ritorna_stringa_vuota(self):
        result = format_whatsapp_mesi(
            mesi=[],
            solution={"by_month": {}},
            frequenze={},
            week_windows={},
        )
        assert result == ""

    def test_mese_non_presente_in_solution_saltato(self):
        result = format_whatsapp_mesi(
            mesi=["2026-01"],
            solution={"by_month": {}},
            frequenze={},
            week_windows={},
        )
        # Il mese non e' in by_month => il blocco viene saltato => output vuoto
        assert result == ""

    def test_output_con_assegnazioni_normali(self):
        mese = "2026-03"
        sol = _soluzione_base(mese)
        result = format_whatsapp_mesi(
            mesi=[mese],
            solution=sol,
            frequenze={"Famiglia Verdi": 2},
            week_windows={},
        )
        assert "Famiglia Verdi" in result
        assert "Mario Rossi" in result
        assert "Luigi Bianchi" in result

    def test_formato_grassetto_whatsapp(self):
        """L'output deve contenere marcatori grassetto WhatsApp (*testo*)."""
        mese = "2026-03"
        sol = _soluzione_base(mese)
        result = format_whatsapp_mesi(
            mesi=[mese],
            solution=sol,
            frequenze={"Famiglia Verdi": 2},
            week_windows={},
        )
        # Deve esserci almeno un blocco grassetto (*...*) nell'output
        assert "*" in result
        # Piu' specificatamente: la riga del mese usa il grassetto
        assert f"*VISITE DI SOSTEGNO" in result

    def test_intestazione_mese_formattata(self):
        """L'intestazione deve includere il nome del mese in italiano."""
        mese = "2026-03"
        sol = _soluzione_base(mese)
        result = format_whatsapp_mesi(
            mesi=[mese],
            solution=sol,
            frequenze={},
            week_windows={},
        )
        assert "Marzo 2026" in result

    def test_non_assegnato_non_appare_nel_output(self):
        """Le assegnazioni con NON_ASSEGNATO non devono essere riportate."""
        mese = "2026-04"
        sol = {
            "by_month": {
                mese: {
                    "by_family": {
                        "Famiglia Blu": [NON_ASSEGNATO, "Mario Rossi"],
                    },
                    "by_brother": {
                        "Mario Rossi": ["Famiglia Blu"],
                    },
                }
            }
        }
        result = format_whatsapp_mesi(
            mesi=[mese],
            solution=sol,
            frequenze={"Famiglia Blu": 2},
            week_windows={},
        )
        assert NON_ASSEGNATO not in result
        # Ma Mario Rossi deve comparire
        assert "Mario Rossi" in result

    def test_piu_mesi(self):
        """Con piu' mesi l'output deve contenere tutte le sezioni."""
        sol = {
            "by_month": {
                "2026-01": {
                    "by_family": {"Fam A": ["Mario"]},
                    "by_brother": {"Mario": ["Fam A"]},
                },
                "2026-02": {
                    "by_family": {"Fam B": ["Luigi"]},
                    "by_brother": {"Luigi": ["Fam B"]},
                },
            }
        }
        result = format_whatsapp_mesi(
            mesi=["2026-01", "2026-02"],
            solution=sol,
            frequenze={},
            week_windows={},
        )
        assert "Gennaio 2026" in result
        assert "Febbraio 2026" in result
        assert "Fam A" in result
        assert "Fam B" in result
