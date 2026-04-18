"""Test per turni_visite.service."""
import pytest
from turni_visite.domain import StoricoConflittoError
from turni_visite.service import conferma_e_salva_turni, _estrai_assegnazioni

try:
    from ortools.sat.python import cp_model as _cp
    _ORTOOLS_OK = True
except Exception:
    _ORTOOLS_OK = False


# ---------------------------------------------------------------------------
# _estrai_assegnazioni (funzione pura, nessun I/O)
# ---------------------------------------------------------------------------

class TestEstraiAssegnazioni:
    def _sol(self, slots):
        return {
            "by_month": {
                "2025-03": {
                    "by_family": {"Fam A": slots},
                    "by_brother": {},
                }
            }
        }

    def test_estrae_correttamente(self):
        result = _estrai_assegnazioni("2025-03", self._sol(["Mario", "Luigi"]))
        assert len(result) == 2
        nomi = {a["fratello"] for a in result}
        assert nomi == {"Mario", "Luigi"}

    def test_salta_non_assegnato(self):
        result = _estrai_assegnazioni("2025-03", self._sol(["Mario", "(non assegnato)"]))
        assert len(result) == 1
        assert result[0]["fratello"] == "Mario"

    def test_slot_index_corretto(self):
        result = _estrai_assegnazioni("2025-03", self._sol(["Mario", "Luigi"]))
        slots = {a["fratello"]: a["slot"] for a in result}
        assert slots["Mario"] == 0
        assert slots["Luigi"] == 1


# ---------------------------------------------------------------------------
# conferma_e_salva_turni (richiede repo reale su file temporaneo)
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
