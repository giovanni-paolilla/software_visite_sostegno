"""
Test dettagliati per CLI commands (sostituzione, affinita') e repository error paths.

Copre:
- CLI _cmd_sostituzione e _cmd_affinita con mock I/O
- Repository bozza error paths
- Repository esecuzione error paths
- Repository affinita error paths
- AffinitaFamiglia dataclass validation
- trova_sostituto detail
- tasso_completamento / report_carico_fratelli stats
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock, call

from turni_visite.cli import _cmd_sostituzione, _cmd_affinita
from turni_visite.domain import (
    AffinitaFamiglia,
    ValidazioneError,
    EntitaNonTrovata,
    NON_ASSEGNATO,
    STATO_BOZZA_PROPOSTO,
    STATO_BOZZA_ACCETTATO,
    STATO_ESECUZIONE_PIANIFICATO,
    STATO_ESECUZIONE_COMPLETATO,
)
from turni_visite.repository import JsonRepository
from turni_visite.service import trova_sostituto
from turni_visite.stats import tasso_completamento, report_carico_fratelli


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path):
    """Repository di test con dati minimali per CLI e repository tests."""
    f = tmp_path / "detail_test.json"
    r = JsonRepository(f)
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_brother("Paolo Verdi")
    r.add_family("Famiglia Neri")
    r.add_family("Famiglia Gialli")
    r.associate("Mario Rossi", "Famiglia Neri")
    r.associate("Luigi Bianchi", "Famiglia Neri")
    r.associate("Paolo Verdi", "Famiglia Neri")
    r.associate("Mario Rossi", "Famiglia Gialli")
    r.associate("Luigi Bianchi", "Famiglia Gialli")
    r.associate("Paolo Verdi", "Famiglia Gialli")
    r.set_brother_capacity("Mario Rossi", 3)
    r.set_brother_capacity("Luigi Bianchi", 3)
    r.set_brother_capacity("Paolo Verdi", 3)
    return r


def _add_storico(repo):
    """Helper: aggiunge storico turni di esempio."""
    repo.append_storico_turni("2026-05", [
        {"famiglia": "Famiglia Neri", "fratello": "Mario Rossi", "slot": 0},
        {"famiglia": "Famiglia Neri", "fratello": "Luigi Bianchi", "slot": 1},
        {"famiglia": "Famiglia Gialli", "fratello": "Paolo Verdi", "slot": 0},
    ])


def _make_solution():
    """Helper: crea soluzione fittizia per bozza."""
    return {
        "by_month": {
            "2026-05": {
                "by_family": {
                    "Famiglia Neri": ["Mario Rossi", "Luigi Bianchi"],
                },
                "by_brother": {
                    "Mario Rossi": ["Famiglia Neri"],
                    "Luigi Bianchi": ["Famiglia Neri"],
                },
            }
        }
    }


# ===================================================================
# 1. TestCmdSostituzioneCLI
# ===================================================================

class TestCmdSostituzioneCLI:
    """Test per _cmd_sostituzione con mock I/O."""

    def test_no_storico_prints_message(self, repo, capsys):
        _cmd_sostituzione(repo)
        out = capsys.readouterr().out
        assert "Nessun mese" in out

    def test_valid_candidate_selection_works(self, repo, capsys):
        _add_storico(repo)
        with patch("builtins.input", side_effect=[
            "2026-05",       # mese
            "Mario Rossi",   # fratello da sostituire
            "1",             # seleziona primo candidato
        ]):
            _cmd_sostituzione(repo)
        out = capsys.readouterr().out
        assert "Sostituzione effettuata" in out

    def test_selection_zero_cancels(self, repo, capsys):
        _add_storico(repo)
        with patch("builtins.input", side_effect=[
            "2026-05",
            "Mario Rossi",
            "0",  # annulla
        ]):
            _cmd_sostituzione(repo)
        out = capsys.readouterr().out
        # Nessun messaggio di errore o sostituzione
        assert "Errore" not in out

    def test_no_candidates_shows_message(self, repo, capsys):
        # Tutti a capacita' 1, tutti gia' assegnati
        repo.set_brother_capacity("Mario Rossi", 1)
        repo.set_brother_capacity("Luigi Bianchi", 1)
        repo.set_brother_capacity("Paolo Verdi", 1)
        repo.append_storico_turni("2026-05", [
            {"famiglia": "Famiglia Neri", "fratello": "Mario Rossi", "slot": 0},
            {"famiglia": "Famiglia Neri", "fratello": "Luigi Bianchi", "slot": 1},
            {"famiglia": "Famiglia Gialli", "fratello": "Paolo Verdi", "slot": 0},
        ])
        with patch("builtins.input", side_effect=[
            "2026-05",
            "Mario Rossi",
        ]):
            _cmd_sostituzione(repo)
        out = capsys.readouterr().out
        assert "Nessun candidato" in out

    def test_invalid_number_input_handled(self, repo, capsys):
        _add_storico(repo)
        with patch("builtins.input", side_effect=[
            "2026-05",
            "Mario Rossi",
            "abc",  # input non numerico
        ]):
            _cmd_sostituzione(repo)
        out = capsys.readouterr().out
        assert "Errore" in out

    def test_fratello_not_found_handled(self, repo, capsys):
        _add_storico(repo)
        with patch("builtins.input", side_effect=[
            "2026-05",
            "Zzzzzzz",  # nome inesistente
        ]):
            _cmd_sostituzione(repo)
        out = capsys.readouterr().out
        # _ask_fuzzy_name ritorna None, la funzione fa return
        assert "non trovato" in out

    def test_out_of_range_index_handled(self, repo, capsys):
        _add_storico(repo)
        with patch("builtins.input", side_effect=[
            "2026-05",
            "Mario Rossi",
            "99",  # indice fuori range
        ]):
            _cmd_sostituzione(repo)
        out = capsys.readouterr().out
        assert "Errore" in out

    def test_shows_available_months(self, repo, capsys):
        _add_storico(repo)
        with patch("builtins.input", side_effect=[
            "2026-05",
            "Mario Rossi",
            "0",
        ]):
            _cmd_sostituzione(repo)
        out = capsys.readouterr().out
        assert "2026-05" in out
        assert "Mesi disponibili" in out


# ===================================================================
# 2. TestCmdAffinitaCLI
# ===================================================================

class TestCmdAffinitaCLI:
    """Test per _cmd_affinita con mock I/O."""

    def test_empty_affinita_list_message(self, repo, capsys):
        with patch("builtins.input", return_value="I"):
            _cmd_affinita(repo)
        out = capsys.readouterr().out
        assert "Nessuna affinita'" in out

    def test_non_empty_list_shows_entries(self, repo, capsys):
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 5)
        with patch("builtins.input", return_value="I"):
            _cmd_affinita(repo)
        out = capsys.readouterr().out
        assert "Mario Rossi" in out
        assert "Famiglia Neri" in out
        assert "+5" in out

    def test_add_valid_affinita_works(self, repo, capsys):
        with patch("builtins.input", side_effect=[
            "A",
            "Mario Rossi",
            "Famiglia Neri",
            "7",
        ]):
            _cmd_affinita(repo)
        out = capsys.readouterr().out
        assert "impostata" in out
        aff = repo.get_affinita()
        assert len(aff) == 1
        assert aff[0]["peso"] == 7

    def test_add_peso_invalid_shows_error(self, repo, capsys):
        with patch("builtins.input", side_effect=[
            "A",
            "Mario Rossi",
            "Famiglia Neri",
            "abc",  # non numerico
        ]):
            _cmd_affinita(repo)
        out = capsys.readouterr().out
        assert "Errore" in out

    def test_add_peso_out_of_range_shows_error(self, repo, capsys):
        with patch("builtins.input", side_effect=[
            "A",
            "Mario Rossi",
            "Famiglia Neri",
            "15",  # fuori range
        ]):
            _cmd_affinita(repo)
        out = capsys.readouterr().out
        assert "Errore" in out

    def test_remove_valid_index_works(self, repo, capsys):
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 5)
        with patch("builtins.input", side_effect=[
            "R",
            "1",  # primo elemento
        ]):
            _cmd_affinita(repo)
        out = capsys.readouterr().out
        assert "rimossa" in out
        assert repo.get_affinita() == []

    def test_remove_empty_list_returns(self, repo, capsys):
        with patch("builtins.input", return_value="R"):
            _cmd_affinita(repo)
        # nessuna affinita' => return immediato su R, nessun errore
        out = capsys.readouterr().out
        assert "Errore" not in out

    def test_back_selection_returns(self, repo, capsys):
        with patch("builtins.input", return_value="I"):
            _cmd_affinita(repo)
        # nessun errore
        out = capsys.readouterr().out
        assert "Errore" not in out

    def test_remove_invalid_index_handled(self, repo, capsys):
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 5)
        with patch("builtins.input", side_effect=[
            "R",
            "99",  # indice fuori range
        ]):
            _cmd_affinita(repo)
        out = capsys.readouterr().out
        assert "Errore" in out

    def test_fratello_not_found_cancels(self, repo, capsys):
        with patch("builtins.input", side_effect=[
            "A",
            "Zzzzzzz",  # non trovato
        ]):
            _cmd_affinita(repo)
        out = capsys.readouterr().out
        assert "non trovato" in out


# ===================================================================
# 3. TestRepositoryBozzaErrorPaths
# ===================================================================

class TestRepositoryBozzaErrorPaths:
    """Test per error paths delle operazioni bozza nel repository."""

    def test_update_bozza_stato_no_draft_raises(self, repo):
        with pytest.raises(EntitaNonTrovata, match="Nessuna bozza"):
            repo.update_bozza_stato("2026-05", "Famiglia Neri", 0, "accettato")

    def test_update_bozza_stato_invalid_stato_raises(self, repo):
        repo.save_bozza(["2026-05"], _make_solution())
        with pytest.raises(ValidazioneError, match="non valido"):
            repo.update_bozza_stato("2026-05", "Famiglia Neri", 0, "invalido")

    def test_update_bozza_stato_slot_not_found_raises(self, repo):
        repo.save_bozza(["2026-05"], _make_solution())
        with pytest.raises(EntitaNonTrovata, match="non trovata"):
            repo.update_bozza_stato("2026-05", "Famiglia Neri", 99, "accettato")

    def test_conferma_bozza_no_draft_raises(self, repo):
        with pytest.raises(EntitaNonTrovata, match="Nessuna bozza"):
            repo.conferma_bozza()

    def test_conferma_bozza_all_proposto_returns_empty(self, repo):
        repo.save_bozza(["2026-05"], _make_solution())
        # Tutti rimangono "proposto" (default), nessuno "accettato"
        result = repo.conferma_bozza()
        assert result == {"salvati": [], "saltati": []}

    def test_conferma_bozza_skips_mese_already_in_storico(self, repo):
        # Aggiungi il mese allo storico prima
        repo.append_storico_turni("2026-05", [
            {"famiglia": "Famiglia Neri", "fratello": "Mario Rossi", "slot": 0},
        ])
        repo.save_bozza(["2026-05"], _make_solution())
        # Accetta tutto nella bozza
        bozza = repo.get_bozza()
        for a in bozza["assegnazioni"]:
            repo.update_bozza_stato(a["mese"], a["famiglia"], a["slot"], "accettato")
        # Conferma: il mese e' gia' nello storico, viene saltato
        result = repo.conferma_bozza()
        assert "2026-05" not in result["salvati"]

    def test_save_bozza_overwrites_previous_draft(self, repo):
        sol1 = _make_solution()
        repo.save_bozza(["2026-05"], sol1)
        assert repo.get_bozza() is not None
        n_ass_1 = len(repo.get_bozza()["assegnazioni"])

        # Nuova soluzione con dati diversi
        sol2 = {
            "by_month": {
                "2026-06": {
                    "by_family": {
                        "Famiglia Neri": ["Paolo Verdi"],
                    },
                    "by_brother": {
                        "Paolo Verdi": ["Famiglia Neri"],
                    },
                }
            }
        }
        repo.save_bozza(["2026-06"], sol2)
        bozza = repo.get_bozza()
        assert bozza["mesi"] == ["2026-06"]
        assert len(bozza["assegnazioni"]) == 1

    def test_discard_bozza_when_no_draft_no_error(self, repo):
        # Non deve sollevare eccezioni
        repo.discard_bozza()
        assert repo.get_bozza() is None

    def test_bozza_survives_save_load_roundtrip(self, repo):
        repo.save_bozza(["2026-05"], _make_solution())
        repo2 = JsonRepository(repo.filename)
        bozza = repo2.get_bozza()
        assert bozza is not None
        assert bozza["mesi"] == ["2026-05"]
        assert len(bozza["assegnazioni"]) == 2

    def test_bozza_turni_is_none_after_conferma(self, repo):
        repo.save_bozza(["2026-05"], _make_solution())
        bozza = repo.get_bozza()
        for a in bozza["assegnazioni"]:
            repo.update_bozza_stato(a["mese"], a["famiglia"], a["slot"], "accettato")
        repo.conferma_bozza()
        assert repo.bozza_turni is None
        assert repo.get_bozza() is None


# ===================================================================
# 4. TestRepositoryEsecuzioneErrorPaths
# ===================================================================

class TestRepositoryEsecuzioneErrorPaths:
    """Test per error paths di set_stato_esecuzione."""

    def test_mese_not_found_raises(self, repo):
        _add_storico(repo)
        with pytest.raises(EntitaNonTrovata):
            repo.set_stato_esecuzione("2099-01", "Famiglia Neri", 0, "completato")

    def test_famiglia_not_found_raises(self, repo):
        _add_storico(repo)
        with pytest.raises(EntitaNonTrovata):
            repo.set_stato_esecuzione("2026-05", "Famiglia Inesistente", 0, "completato")

    def test_invalid_stato_raises(self, repo):
        _add_storico(repo)
        with pytest.raises(ValidazioneError, match="non valido"):
            repo.set_stato_esecuzione("2026-05", "Famiglia Neri", 0, "stato_sbagliato")

    def test_stato_esecuzione_persists_after_save_load(self, repo):
        _add_storico(repo)
        repo.set_stato_esecuzione("2026-05", "Famiglia Neri", 0, "completato")
        repo2 = JsonRepository(repo.filename)
        storico = repo2.get_storico_turni()
        rec = next(r for r in storico if r["mese"] == "2026-05")
        a = next(a for a in rec["assegnazioni"]
                 if a["famiglia"] == "Famiglia Neri" and a["slot"] == 0)
        assert a["stato_esecuzione"] == "completato"

    def test_backward_compat_old_records_without_stato(self, repo):
        _add_storico(repo)
        storico = repo.get_storico_turni()
        rec = next(r for r in storico if r["mese"] == "2026-05")
        for a in rec["assegnazioni"]:
            # Vecchi record non hanno stato_esecuzione; default = pianificato
            assert a.get("stato_esecuzione", "pianificato") == "pianificato"

    def test_slot_not_found_raises(self, repo):
        _add_storico(repo)
        with pytest.raises(EntitaNonTrovata):
            repo.set_stato_esecuzione("2026-05", "Famiglia Neri", 99, "completato")


# ===================================================================
# 5. TestRepositoryAffinitaErrorPaths
# ===================================================================

class TestRepositoryAffinitaErrorPaths:
    """Test per error paths delle operazioni affinita' nel repository."""

    def test_add_affinita_fratello_not_found_raises(self, repo):
        with pytest.raises(EntitaNonTrovata, match="Fratello"):
            repo.add_affinita("Famiglia Neri", "Inesistente", 5)

    def test_add_affinita_famiglia_not_found_raises(self, repo):
        with pytest.raises(EntitaNonTrovata, match="Famiglia"):
            repo.add_affinita("Famiglia Inesistente", "Mario Rossi", 5)

    def test_add_affinita_peso_out_of_range_raises(self, repo):
        with pytest.raises(ValidazioneError, match="Peso"):
            repo.add_affinita("Famiglia Neri", "Mario Rossi", 15)
        with pytest.raises(ValidazioneError, match="Peso"):
            repo.add_affinita("Famiglia Neri", "Mario Rossi", -15)

    def test_remove_affinita_not_found_raises(self, repo):
        with pytest.raises(EntitaNonTrovata, match="non trovata"):
            repo.remove_affinita("Famiglia Neri", "Mario Rossi")

    def test_sanitize_updates_affinita_names(self, repo):
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 5)
        # Rinomina Mario Rossi -> Marco Rossi tramite alias
        repo.sanitize({"Mario Rossi": "Marco Rossi"})
        aff = repo.get_affinita()
        nomi_fratelli = [a["fratello"] for a in aff]
        assert "Marco Rossi" in nomi_fratelli
        assert "Mario Rossi" not in nomi_fratelli

    def test_sanitize_removes_orphaned_affinita(self, repo):
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 5)
        # Rimuovi fratello poi sanifica: affinita' orfane vengono eliminate
        repo.remove_brother("Mario Rossi")
        # Dopo remove_brother le affinita' sono gia' ripulite
        assert len(repo.get_affinita()) == 0
        # Verifica con sanitize esplicito che non ci siano residui
        repo.sanitize({})
        assert len(repo.get_affinita()) == 0


# ===================================================================
# 6. TestAffinitaFamigliaDataclass
# ===================================================================

class TestAffinitaFamigliaDataclass:
    """Test per la validazione del dataclass AffinitaFamiglia."""

    def test_valid_peso_range(self):
        # Valori validi ai limiti
        af_min = AffinitaFamiglia(famiglia="Neri", fratello="Mario", peso=-10)
        assert af_min.peso == -10
        af_max = AffinitaFamiglia(famiglia="Neri", fratello="Mario", peso=10)
        assert af_max.peso == 10
        af_zero = AffinitaFamiglia(famiglia="Neri", fratello="Mario", peso=0)
        assert af_zero.peso == 0

    def test_peso_11_raises(self):
        with pytest.raises(ValidazioneError, match="Peso"):
            AffinitaFamiglia(famiglia="Neri", fratello="Mario", peso=11)

    def test_peso_minus_11_raises(self):
        with pytest.raises(ValidazioneError, match="Peso"):
            AffinitaFamiglia(famiglia="Neri", fratello="Mario", peso=-11)

    def test_peso_none_raises(self):
        with pytest.raises((ValidazioneError, TypeError)):
            AffinitaFamiglia(famiglia="Neri", fratello="Mario", peso=None)

    def test_peso_string_raises(self):
        with pytest.raises((ValidazioneError, TypeError)):
            AffinitaFamiglia(famiglia="Neri", fratello="Mario", peso="cinque")


# ===================================================================
# 7. TestTrovaSostitutoDetail
# ===================================================================

class TestTrovaSostitutoDetail:
    """Test dettagliati per trova_sostituto."""

    def test_returns_candidates_sorted_by_score(self, repo):
        # Crea storico con carichi diversi
        repo.append_storico_turni("2026-04", [
            {"famiglia": "Famiglia Neri", "fratello": "Paolo Verdi", "slot": 0},
            {"famiglia": "Famiglia Neri", "fratello": "Paolo Verdi", "slot": 1},
        ])
        repo.append_storico_turni("2026-05", [
            {"famiglia": "Famiglia Neri", "fratello": "Mario Rossi", "slot": 0},
            {"famiglia": "Famiglia Neri", "fratello": "Luigi Bianchi", "slot": 1},
        ])
        candidati = trova_sostituto(repo, "2026-05", "Mario Rossi")
        # I candidati sono ordinati per score (carico piu' basso = score piu' alto)
        for i in range(len(candidati) - 1):
            assert candidati[i]["score"] >= candidati[i + 1]["score"]

    def test_respects_capacity_limits(self, repo):
        repo.set_brother_capacity("Mario Rossi", 1)
        repo.set_brother_capacity("Luigi Bianchi", 1)
        repo.set_brother_capacity("Paolo Verdi", 1)
        repo.append_storico_turni("2026-05", [
            {"famiglia": "Famiglia Neri", "fratello": "Mario Rossi", "slot": 0},
            {"famiglia": "Famiglia Neri", "fratello": "Luigi Bianchi", "slot": 1},
            {"famiglia": "Famiglia Gialli", "fratello": "Paolo Verdi", "slot": 0},
        ])
        candidati = trova_sostituto(repo, "2026-05", "Mario Rossi")
        # Tutti a cap 1 e gia' assegnati: nessun candidato
        assert candidati == []

    def test_respects_indisponibilita(self, repo):
        _add_storico(repo)
        repo.set_indisponibilita("Paolo Verdi", ["2026-05"])
        candidati = trova_sostituto(repo, "2026-05", "Mario Rossi")
        nomi = [c["fratello"] for c in candidati]
        assert "Paolo Verdi" not in nomi

    def test_empty_storico_returns_empty(self, repo):
        candidati = trova_sostituto(repo, "2026-05", "Mario Rossi")
        assert candidati == []

    def test_mese_not_in_storico_returns_empty(self, repo):
        _add_storico(repo)
        candidati = trova_sostituto(repo, "2099-01", "Mario Rossi")
        assert candidati == []

    def test_fratello_not_assigned_returns_empty(self, repo):
        _add_storico(repo)
        # Paolo Verdi non e' assegnato in Famiglia Neri (slot 0 e 1 sono Mario e Luigi)
        # ma e' in Famiglia Gialli. Cerchiamo un mese dove non e' assegnato affatto.
        repo.append_storico_turni("2026-06", [
            {"famiglia": "Famiglia Neri", "fratello": "Mario Rossi", "slot": 0},
        ])
        # Paolo Verdi non ha assegnazioni nel 2026-06
        candidati = trova_sostituto(repo, "2026-06", "Paolo Verdi")
        assert candidati == []


# ===================================================================
# 8. TestStatoCompletion
# ===================================================================

class TestStatoCompletion:
    """Test per tasso_completamento e report_carico_fratelli."""

    def test_tasso_completamento_all_pianificato_zero(self):
        storico = [{
            "mese": "2026-05",
            "assegnazioni": [
                {"famiglia": "Fam-A", "fratello": "F1", "slot": 0,
                 "stato_esecuzione": "pianificato"},
                {"famiglia": "Fam-A", "fratello": "F2", "slot": 1,
                 "stato_esecuzione": "pianificato"},
            ],
        }]
        result = tasso_completamento(storico)
        assert result["tasso_pct"] == 0.0
        assert result["completate"] == 0
        assert result["pianificate"] == 2

    def test_tasso_completamento_all_completato_100(self):
        storico = [{
            "mese": "2026-05",
            "assegnazioni": [
                {"famiglia": "Fam-A", "fratello": "F1", "slot": 0,
                 "stato_esecuzione": "completato"},
                {"famiglia": "Fam-A", "fratello": "F2", "slot": 1,
                 "stato_esecuzione": "completato"},
            ],
        }]
        result = tasso_completamento(storico)
        assert result["tasso_pct"] == 100.0
        assert result["completate"] == 2
        assert result["pianificate"] == 0

    def test_report_carico_solo_completati_filters(self):
        storico = [{
            "mese": "2026-05",
            "assegnazioni": [
                {"famiglia": "Fam-A", "fratello": "F1", "slot": 0,
                 "stato_esecuzione": "completato"},
                {"famiglia": "Fam-A", "fratello": "F2", "slot": 1,
                 "stato_esecuzione": "pianificato"},
                {"famiglia": "Fam-B", "fratello": "F1", "slot": 0,
                 "stato_esecuzione": "annullato"},
            ],
        }]
        report = report_carico_fratelli(storico, solo_completati=True)
        # Solo F1 con stato completato
        assert len(report) == 1
        assert report[0]["fratello"] == "F1"
        assert report[0]["visite_totali"] == 1

    def test_backward_compat_no_stato_counted_as_pianificato(self):
        # Record senza stato_esecuzione: default e' "pianificato"
        storico = [{
            "mese": "2026-05",
            "assegnazioni": [
                {"famiglia": "Fam-A", "fratello": "F1", "slot": 0},
                {"famiglia": "Fam-A", "fratello": "F2", "slot": 1},
            ],
        }]
        result = tasso_completamento(storico)
        assert result["totale"] == 2
        assert result["pianificate"] == 2
        assert result["completate"] == 0
        assert result["tasso_pct"] == 0.0

        # solo_completati filtra tutto perche' nessuno ha stato completato
        report = report_carico_fratelli(storico, solo_completati=True)
        assert len(report) == 0
