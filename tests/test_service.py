"""Test per turni_visite.service."""
import pytest
from turni_visite.domain import StoricoConflittoError
from turni_visite.service import conferma_e_salva_turni

try:
    from ortools.sat.python import cp_model as _cp
    _ORTOOLS_OK = True
except Exception:
    _ORTOOLS_OK = False


# ---------------------------------------------------------------------------
# Fixture e helper
# ---------------------------------------------------------------------------

@pytest.fixture
def repo_con_dati(tmp_path):
    from turni_visite.repository import JsonRepository
    r = JsonRepository(str(tmp_path / "svc_test.json"))
    r.add_brother("Mario Rossi")
    r.add_family("Famiglia Verdi")
    r.associate("Mario Rossi", "Famiglia Verdi")
    return r


def _sol_semplice(mese, fr="Mario Rossi", fam="Famiglia Verdi"):
    return {
        "by_month": {
            mese: {
                "by_family": {fam: [fr]},
                "by_brother": {fr: [fam]},
            }
        }
    }


# ---------------------------------------------------------------------------
# conferma_e_salva_turni (API pubblica)
# ---------------------------------------------------------------------------

class TestConfermaESalvaTurni:
    def test_salva_correttamente(self, repo_con_dati):
        sol = _sol_semplice("2025-03")
        salvati = conferma_e_salva_turni(repo_con_dati, ["2025-03"], sol)
        assert salvati == ["2025-03"]
        assert repo_con_dati.storico_has_mese("2025-03")

    def test_salva_piu_mesi(self, repo_con_dati):
        sol = {
            "by_month": {
                "2025-03": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi"]},
                    "by_brother": {"Mario Rossi": ["Famiglia Verdi"]},
                },
                "2025-04": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi"]},
                    "by_brother": {"Mario Rossi": ["Famiglia Verdi"]},
                },
            }
        }
        salvati = conferma_e_salva_turni(repo_con_dati, ["2025-03", "2025-04"], sol)
        assert set(salvati) == {"2025-03", "2025-04"}

    def test_conflitto_storico_blocca_tutto(self, repo_con_dati):
        sol = _sol_semplice("2025-03")
        conferma_e_salva_turni(repo_con_dati, ["2025-03"], sol)
        sol2 = _sol_semplice("2025-03")
        with pytest.raises(StoricoConflittoError):
            conferma_e_salva_turni(repo_con_dati, ["2025-03"], sol2)

    def test_slot_index_salvato_correttamente(self, repo_con_dati):
        """Verifica che gli slot index vengano estratti e salvati in ordine."""
        sol = {
            "by_month": {
                "2025-05": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi"]},
                    "by_brother": {"Mario Rossi": ["Famiglia Verdi"]},
                }
            }
        }
        conferma_e_salva_turni(repo_con_dati, ["2025-05"], sol)
        storico = repo_con_dati.get_storico_turni()
        rec = next(r for r in storico if r["mese"] == "2025-05")
        assert len(rec["assegnazioni"]) == 1
        a = rec["assegnazioni"][0]
        assert a["fratello"] == "Mario Rossi"
        assert a["famiglia"] == "Famiglia Verdi"
        assert a["slot"] == 0

    def test_non_assegnato_non_salvato(self, repo_con_dati):
        """Le voci '(non assegnato)' non devono entrare nello storico."""
        sol = {
            "by_month": {
                "2025-06": {
                    "by_family": {"Famiglia Verdi": ["Mario Rossi", "(non assegnato)"]},
                    "by_brother": {"Mario Rossi": ["Famiglia Verdi"]},
                }
            }
        }
        conferma_e_salva_turni(repo_con_dati, ["2025-06"], sol)
        storico = repo_con_dati.get_storico_turni()
        rec = next(r for r in storico if r["mese"] == "2025-06")
        fratelli_salvati = [a["fratello"] for a in rec["assegnazioni"]]
        assert "(non assegnato)" not in fratelli_salvati
        assert "Mario Rossi" in fratelli_salvati
