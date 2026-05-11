"""Test per turni_visite.domain."""
import pytest
from turni_visite.domain import (
    Fratello, Famiglia, AssegnazioneSlot, SolverResult,
    TurniVisiteError, EntitaNonTrovata, DuplicatoError,
    ValidazioneError, StoricoConflittoError,
)


class TestFratello:
    def test_capacita_default(self):
        f = Fratello(nome="Mario Rossi")
        assert f.capacita == 1

    def test_capacita_personalizzata(self):
        f = Fratello(nome="Mario Rossi", capacita=3)
        assert f.capacita == 3

    def test_capacita_zero_ammessa(self):
        f = Fratello(nome="Mario Rossi", capacita=0)
        assert f.capacita == 0

    def test_capacita_negativa_errore(self):
        with pytest.raises(ValidazioneError):
            Fratello(nome="Mario Rossi", capacita=-1)

    def test_capacita_troppo_alta_errore(self):
        with pytest.raises(ValidazioneError):
            Fratello(nome="Mario Rossi", capacita=51)


class TestFamiglia:
    def test_frequenza_default(self):
        f = Famiglia(nome="Rossi")
        assert f.frequenza == 2

    def test_frequenze_valide(self):
        for freq in (1, 2, 4):
            f = Famiglia(nome="Rossi", frequenza=freq)
            assert f.frequenza == freq

    def test_frequenza_non_valida(self):
        for freq in (0, 3, 5, -1):
            with pytest.raises(ValidazioneError):
                Famiglia(nome="Rossi", frequenza=freq)


class TestSolverResult:
    def test_infeasible(self):
        r = SolverResult(feasible=False)
        assert not r.feasible
        assert r.solution is None

    def test_feasible(self):
        sol = {"by_month": {}}
        r = SolverResult(feasible=True, solution=sol)
        assert r.feasible
        assert r.solution is sol


class TestGerarchiEccezioni:
    def test_tutte_sottoclassi_di_base(self):
        for cls in (EntitaNonTrovata, DuplicatoError, ValidazioneError, StoricoConflittoError):
            assert issubclass(cls, TurniVisiteError)

    def test_catchable_come_base(self):
        for cls in (EntitaNonTrovata, DuplicatoError, ValidazioneError, StoricoConflittoError):
            with pytest.raises(TurniVisiteError):
                raise cls("test")
