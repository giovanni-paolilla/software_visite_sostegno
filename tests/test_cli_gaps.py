"""Test per CLI — comandi e error paths non coperti."""
import pytest
from unittest.mock import patch, MagicMock

from turni_visite.cli import (
    _ask_fuzzy_name,
    _cmd_frequenza,
    _cmd_capacita,
    _cmd_indisponibilita,
    _cmd_vincoli,
    _cmd_backup,
    _cmd_sostituzione,
    _cmd_affinita,
    _cmd_storico,
    _cmd_ottimizza,
    _cmd_import_csv,
    main,
)
from turni_visite.repository import JsonRepository


@pytest.fixture
def repo(tmp_path):
    r = JsonRepository(str(tmp_path / "cli_gaps.json"))
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_brother("Carla Neri")
    r.add_family("Famiglia Verdi")
    r.add_family("Famiglia Blu")
    r.set_frequency("Famiglia Verdi", 2)
    r.set_frequency("Famiglia Blu", 2)
    r.associate("Mario Rossi", "Famiglia Verdi")
    r.associate("Luigi Bianchi", "Famiglia Verdi")
    r.associate("Carla Neri", "Famiglia Blu")
    r.associate("Mario Rossi", "Famiglia Blu")
    return r


# ---------------------------------------------------------------------------
# _ask_fuzzy_name edge cases
# ---------------------------------------------------------------------------

class TestAskFuzzyNameEdge:
    def test_scelta_fuori_range(self):
        with patch("builtins.input", side_effect=["99", "0"]):
            result = _ask_fuzzy_name("Mario Ross", ["Mario Rossi", "Luigi Bianchi"], "fratelli")
        assert result is None

    def test_scelta_non_numerica(self):
        with patch("builtins.input", side_effect=["xyz", "0"]):
            result = _ask_fuzzy_name("Mario Ross", ["Mario Rossi"], "fratelli")
        assert result is None

    def test_riscrittura_con_nome_valido(self):
        with patch("builtins.input", side_effect=["", "Mario Rossi"]):
            result = _ask_fuzzy_name("Mario Ross", ["Mario Rossi"], "fratelli")
        assert result == "Mario Rossi"

    def test_riscrittura_con_invio_vuoto(self):
        with patch("builtins.input", side_effect=["", ""]):
            result = _ask_fuzzy_name("Mario Ross", ["Mario Rossi"], "fratelli")
        assert result is None

    def test_riscrittura_ricorsiva(self):
        with patch("builtins.input", side_effect=["", "Luigi Bianch", "1"]):
            result = _ask_fuzzy_name("Mario Ross", ["Mario Rossi", "Luigi Bianchi"], "fratelli")
        assert result == "Luigi Bianchi"


# ---------------------------------------------------------------------------
# _cmd_frequenza error paths
# ---------------------------------------------------------------------------

class TestCmdFrequenzaErrors:
    def test_valore_non_numerico(self, repo, capsys):
        with patch("builtins.input", side_effect=["Famiglia Verdi", "I", "abc"]):
            _cmd_frequenza(repo)
        assert "non numerico" in capsys.readouterr().out

    def test_annullata_se_non_trovata(self, repo, capsys):
        with patch("builtins.input", side_effect=["Zzzzz"]):
            _cmd_frequenza(repo)
        assert "annullata" in capsys.readouterr().out

    def test_frequenza_non_valida(self, repo, capsys):
        with patch("builtins.input", side_effect=["Famiglia Verdi", "I", "3"]):
            _cmd_frequenza(repo)
        assert "Errore" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _cmd_capacita error paths
# ---------------------------------------------------------------------------

class TestCmdCapacitaErrors:
    def test_valore_non_numerico(self, repo, capsys):
        with patch("builtins.input", side_effect=["Mario Rossi", "I", "abc"]):
            _cmd_capacita(repo)
        assert "non numerico" in capsys.readouterr().out

    def test_annullata_se_non_trovato(self, repo, capsys):
        with patch("builtins.input", side_effect=["Zzzzz"]):
            _cmd_capacita(repo)
        assert "annullata" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _cmd_indisponibilita error paths
# ---------------------------------------------------------------------------

class TestCmdIndisponibilitaErrors:
    def test_mese_non_valido(self, repo, capsys):
        with patch("builtins.input", side_effect=["Mario Rossi", "A", "bad-month"]):
            _cmd_indisponibilita(repo)
        assert "Errore" in capsys.readouterr().out

    def test_azione_indietro(self, repo, capsys):
        with patch("builtins.input", side_effect=["Mario Rossi", "I"]):
            _cmd_indisponibilita(repo)

    def test_visualizza_indisponibilita_esistenti(self, repo, capsys):
        repo.add_indisponibilita("Mario Rossi", "2026-05")
        with patch("builtins.input", side_effect=["Mario Rossi", "I"]):
            _cmd_indisponibilita(repo)
        assert "2026-05" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _cmd_vincoli error paths
# ---------------------------------------------------------------------------

class TestCmdVincoliErrors:
    def test_rimuovi_indice_non_valido(self, repo, capsys):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        with patch("builtins.input", side_effect=["R", "abc"]):
            _cmd_vincoli(repo)
        assert "Errore" in capsys.readouterr().out

    def test_rimuovi_indice_fuori_range(self, repo, capsys):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        with patch("builtins.input", side_effect=["R", "99"]):
            _cmd_vincoli(repo)
        assert "Errore" in capsys.readouterr().out

    def test_rimuovi_vincolo_ok(self, repo, capsys):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        with patch("builtins.input", side_effect=["R", "1"]):
            _cmd_vincoli(repo)
        assert len(repo.get_vincoli()) == 0

    def test_rimuovi_su_lista_vuota(self, repo, capsys):
        with patch("builtins.input", return_value="R"):
            _cmd_vincoli(repo)

    def test_azione_indietro(self, repo, capsys):
        with patch("builtins.input", return_value="I"):
            _cmd_vincoli(repo)

    def test_aggiungi_fratello_b_annullato(self, repo, capsys):
        with patch("builtins.input", side_effect=["A", "Mario Rossi", "Zzzzz"]):
            _cmd_vincoli(repo)

    def test_aggiungi_tipo_non_valido(self, repo, capsys):
        with patch("builtins.input", side_effect=[
            "A", "Mario Rossi", "Luigi Bianchi", "invalido", "test"]):
            _cmd_vincoli(repo)
        assert "Errore" in capsys.readouterr().out

    def test_visualizza_vincoli_esistenti(self, repo, capsys):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile", "desc test")
        with patch("builtins.input", return_value="I"):
            _cmd_vincoli(repo)
        out = capsys.readouterr().out
        assert "Mario Rossi" in out
        assert "incompatibile" in out


# ---------------------------------------------------------------------------
# _cmd_backup error paths
# ---------------------------------------------------------------------------

class TestCmdBackupErrors:
    def test_ripristina_lista_vuota(self, repo, capsys):
        with patch("builtins.input", return_value="3"):
            with patch("turni_visite.cli.list_backups", return_value=[]):
                _cmd_backup(repo)
        assert "Nessun backup" in capsys.readouterr().out

    def test_ripristina_indice_non_valido(self, repo, capsys):
        bk = [{"filename": "f.json", "modified": "2026-01-01", "path": "/tmp/f.json", "size_kb": 1}]
        with patch("builtins.input", side_effect=["3", "abc"]):
            with patch("turni_visite.cli.list_backups", return_value=bk):
                _cmd_backup(repo)
        assert "Errore" in capsys.readouterr().out

    def test_ripristina_ok(self, repo, capsys, tmp_path):
        bk_file = tmp_path / "backup.json"
        bk_file.write_text('{"schema_version":3,"fratelli":["Test"],"famiglie":[],"associazioni":{},"frequenze":{},"capacita":{"Test":1},"settings":{"cooldown_mesi":3},"storico_turni":[],"indisponibilita":{},"vincoli_personalizzati":[],"week_templates":{},"audit_log":[],"affinita":[],"bozza_turni":null}')
        bk = [{"filename": "backup.json", "modified": "2026-01-01", "path": str(bk_file), "size_kb": 1}]
        with patch("builtins.input", side_effect=["3", "1", "s"]):
            with patch("turni_visite.cli.list_backups", return_value=bk):
                with patch("turni_visite.cli.restore_backup") as mock_restore:
                    _cmd_backup(repo)

    def test_indietro(self, repo, capsys):
        with patch("builtins.input", return_value="0"):
            _cmd_backup(repo)

    def test_lista_con_backup(self, repo, capsys):
        bk = [{"filename": "f.json", "modified": "2026-01-01", "size_kb": 2}]
        with patch("builtins.input", return_value="2"):
            with patch("turni_visite.cli.list_backups", return_value=bk):
                _cmd_backup(repo)
        out = capsys.readouterr().out
        assert "f.json" in out


# ---------------------------------------------------------------------------
# _cmd_sostituzione
# ---------------------------------------------------------------------------

class TestCmdSostituzione:
    def test_storico_vuoto(self, repo, capsys):
        _cmd_sostituzione(repo)
        assert "Nessun mese" in capsys.readouterr().out

    def test_sostituzione_nessun_candidato(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with patch("builtins.input", side_effect=["2026-01", "Mario Rossi"]):
            with patch("turni_visite.cli.trova_sostituto", return_value=[]):
                _cmd_sostituzione(repo)
        assert "Nessun candidato" in capsys.readouterr().out

    def test_sostituzione_annulla(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        candidati = [{"fratello": "Luigi Bianchi", "famiglia": "Famiglia Verdi", "slot": 0, "carico_attuale": 1}]
        with patch("builtins.input", side_effect=["2026-01", "Mario Rossi", "0"]):
            with patch("turni_visite.cli.trova_sostituto", return_value=candidati):
                _cmd_sostituzione(repo)

    def test_sostituzione_ok(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        candidati = [{"fratello": "Luigi Bianchi", "famiglia": "Famiglia Verdi", "slot": 0, "carico_attuale": 1}]
        with patch("builtins.input", side_effect=["2026-01", "Mario Rossi", "1"]):
            with patch("turni_visite.cli.trova_sostituto", return_value=candidati):
                _cmd_sostituzione(repo)
        assert "Sostituzione effettuata" in capsys.readouterr().out

    def test_sostituzione_fratello_annullato(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with patch("builtins.input", side_effect=["2026-01", "Zzzzz"]):
            _cmd_sostituzione(repo)

    def test_sostituzione_errore_indice(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        candidati = [{"fratello": "Luigi Bianchi", "famiglia": "Famiglia Verdi", "slot": 0, "carico_attuale": 1}]
        with patch("builtins.input", side_effect=["2026-01", "Mario Rossi", "99"]):
            with patch("turni_visite.cli.trova_sostituto", return_value=candidati):
                _cmd_sostituzione(repo)
        assert "Errore" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _cmd_affinita
# ---------------------------------------------------------------------------

class TestCmdAffinita:
    def test_lista_vuota(self, repo, capsys):
        with patch("builtins.input", return_value="I"):
            _cmd_affinita(repo)
        assert "Nessuna affinita'" in capsys.readouterr().out

    def test_aggiungi_ok(self, repo, capsys):
        with patch("builtins.input", side_effect=[
            "A", "Mario Rossi", "Famiglia Verdi", "5"]):
            _cmd_affinita(repo)
        assert "Affinita' impostata" in capsys.readouterr().out
        assert len(repo.get_affinita()) == 1

    def test_aggiungi_peso_non_valido(self, repo, capsys):
        with patch("builtins.input", side_effect=[
            "A", "Mario Rossi", "Famiglia Verdi", "abc"]):
            _cmd_affinita(repo)
        assert "Errore" in capsys.readouterr().out

    def test_aggiungi_fratello_annullato(self, repo, capsys):
        with patch("builtins.input", side_effect=["A", "Zzzzz"]):
            _cmd_affinita(repo)

    def test_aggiungi_famiglia_annullata(self, repo, capsys):
        with patch("builtins.input", side_effect=["A", "Mario Rossi", "Zzzzz"]):
            _cmd_affinita(repo)

    def test_rimuovi_ok(self, repo, capsys):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 5)
        with patch("builtins.input", side_effect=["R", "1"]):
            _cmd_affinita(repo)
        assert "Affinita' rimossa" in capsys.readouterr().out

    def test_rimuovi_indice_non_valido(self, repo, capsys):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 5)
        with patch("builtins.input", side_effect=["R", "abc"]):
            _cmd_affinita(repo)
        assert "Errore" in capsys.readouterr().out

    def test_rimuovi_su_lista_vuota(self, repo, capsys):
        with patch("builtins.input", return_value="R"):
            _cmd_affinita(repo)

    def test_visualizza_affinita_esistenti(self, repo, capsys):
        repo.add_affinita("Famiglia Verdi", "Mario Rossi", 5)
        with patch("builtins.input", return_value="I"):
            _cmd_affinita(repo)
        out = capsys.readouterr().out
        assert "Mario Rossi" in out
        assert "+5" in out


# ---------------------------------------------------------------------------
# _cmd_storico edge cases
# ---------------------------------------------------------------------------

class TestCmdStoricoEdge:
    def test_dettaglio_mese_non_trovato(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with patch("builtins.input", side_effect=["D", "2099-01"]):
            _cmd_storico(repo)
        assert "non trovato" in capsys.readouterr().out

    def test_elimina_mese_non_trovato(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with patch("builtins.input", side_effect=["E", "2099-01", "s"]):
            _cmd_storico(repo)
        assert "Errore" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _cmd_ottimizza edge cases
# ---------------------------------------------------------------------------

try:
    from ortools.sat.python import cp_model as _cp
    _ORTOOLS_OK = True
except Exception:
    _ORTOOLS_OK = False


@pytest.mark.skipif(not _ORTOOLS_OK, reason="ortools non installato")
class TestCmdOttimizzaEdge:
    def test_precheck_fail_utente_rifiuta(self, repo, capsys, monkeypatch):
        import turni_visite.cli as cli_mod
        monkeypatch.setattr(cli_mod, "quick_check", lambda *a, **kw: {
            "fattibile": False, "problemi": ["Problema test"], "avvisi": []})
        ww = {}
        with patch("builtins.input", side_effect=["2026-01", "", "", "N"]):
            _cmd_ottimizza(repo, ww)
        out = capsys.readouterr().out
        assert "PROBLEMI" in out

    def test_runtime_error(self, repo, capsys, monkeypatch):
        import turni_visite.cli as cli_mod
        monkeypatch.setattr(cli_mod, "quick_check", lambda *a, **kw: {
            "fattibile": True, "problemi": [], "avvisi": []})
        monkeypatch.setattr(cli_mod, "esegui_ottimizzazione",
                            lambda **kw: (_ for _ in ()).throw(RuntimeError("Solver fallito")))
        ww = {}
        with patch("builtins.input", side_effect=["2026-01", "", ""]):
            _cmd_ottimizza(repo, ww)
        assert "Solver fallito" in capsys.readouterr().out

    def test_infeasible(self, repo, capsys, monkeypatch):
        import turni_visite.cli as cli_mod
        from types import SimpleNamespace
        monkeypatch.setattr(cli_mod, "quick_check", lambda *a, **kw: {
            "fattibile": True, "problemi": [], "avvisi": []})
        monkeypatch.setattr(cli_mod, "esegui_ottimizzazione",
                            lambda **kw: SimpleNamespace(feasible=False, solution=None))
        monkeypatch.setattr(cli_mod, "diagnosi_infeasible",
                            lambda **kw: "Non risolvibile: risorse insufficienti")
        ww = {}
        with patch("builtins.input", side_effect=["2026-01", "", ""]):
            _cmd_ottimizza(repo, ww)
        assert "infeasible" in capsys.readouterr().out

    def test_salvataggio_conflitto_storico(self, repo, capsys, monkeypatch, tmp_path):
        import turni_visite.cli as cli_mod
        from turni_visite.domain import StoricoConflittoError
        from types import SimpleNamespace
        sol = {"by_month": {"2026-01": {"by_family": {"Famiglia Verdi": ["Mario Rossi", "Luigi Bianchi"]}}}}
        monkeypatch.setattr(cli_mod, "quick_check", lambda *a, **kw: {
            "fattibile": True, "problemi": [], "avvisi": []})
        monkeypatch.setattr(cli_mod, "esegui_ottimizzazione",
                            lambda **kw: SimpleNamespace(feasible=True, solution=sol))
        monkeypatch.setattr(cli_mod, "print_reports_mesi", lambda *a: None)
        monkeypatch.setattr(cli_mod, "export_pdf_mesi", lambda *a, **kw: None)
        monkeypatch.setattr(cli_mod, "open_file", lambda *a: None)
        monkeypatch.setattr(cli_mod, "conferma_e_salva_turni",
                            lambda *a: (_ for _ in ()).throw(StoricoConflittoError("Conflitto")))
        monkeypatch.setattr(cli_mod, "DATA_FILE", tmp_path / "dati.json")
        ww = {}
        with patch("builtins.input", side_effect=["2026-01", "", "", "N", "N", "s"]):
            _cmd_ottimizza(repo, ww)
        assert "Non posso salvare" in capsys.readouterr().out

    def test_pdf_errore_fallback(self, repo, capsys, monkeypatch, tmp_path):
        import turni_visite.cli as cli_mod
        from types import SimpleNamespace
        sol = {"by_month": {"2026-01": {"by_family": {"Famiglia Verdi": ["Mario Rossi", "Luigi Bianchi"]}}}}
        monkeypatch.setattr(cli_mod, "quick_check", lambda *a, **kw: {
            "fattibile": True, "problemi": [], "avvisi": []})
        monkeypatch.setattr(cli_mod, "esegui_ottimizzazione",
                            lambda **kw: SimpleNamespace(feasible=True, solution=sol))
        monkeypatch.setattr(cli_mod, "print_reports_mesi", lambda *a: None)
        monkeypatch.setattr(cli_mod, "export_pdf_mesi",
                            lambda *a, **kw: (_ for _ in ()).throw(OSError("PDF fail")))
        monkeypatch.setattr(cli_mod, "DATA_FILE", tmp_path / "dati.json")
        ww = {}
        with patch("builtins.input", side_effect=["2026-01", "", "", "N", "N", "n"]):
            _cmd_ottimizza(repo, ww)
        out = capsys.readouterr().out
        assert "Errore nel salvataggio del PDF" in out
        assert "Bozza non salvata" in out

    def test_whatsapp_export(self, repo, capsys, monkeypatch, tmp_path):
        import turni_visite.cli as cli_mod
        from types import SimpleNamespace
        sol = {"by_month": {"2026-01": {"by_family": {"Famiglia Verdi": ["Mario Rossi", "Luigi Bianchi"]}}}}
        monkeypatch.setattr(cli_mod, "quick_check", lambda *a, **kw: {
            "fattibile": True, "problemi": [], "avvisi": []})
        monkeypatch.setattr(cli_mod, "esegui_ottimizzazione",
                            lambda **kw: SimpleNamespace(feasible=True, solution=sol))
        monkeypatch.setattr(cli_mod, "print_reports_mesi", lambda *a: None)
        monkeypatch.setattr(cli_mod, "export_pdf_mesi", lambda *a, **kw: None)
        monkeypatch.setattr(cli_mod, "open_file", lambda *a: None)
        monkeypatch.setattr(cli_mod, "DATA_FILE", tmp_path / "dati.json")
        monkeypatch.setattr(cli_mod, "conferma_e_salva_turni", lambda *a: ["2026-01"])
        ww = {}
        with patch("builtins.input", side_effect=["2026-01", "", "", "s", "N", "s"]):
            _cmd_ottimizza(repo, ww)
        out = capsys.readouterr().out
        assert "Turni salvati" in out


# ---------------------------------------------------------------------------
# _cmd_import_csv error path
# ---------------------------------------------------------------------------

class TestCmdImportCsvError:
    def test_file_non_trovato(self, repo, capsys):
        with patch("builtins.input", return_value="/tmp/nonexistent_xyz.csv"):
            _cmd_import_csv(repo)
        out = capsys.readouterr().out
        assert "non trovato" in out.lower() or "errore" in out.lower()


# ---------------------------------------------------------------------------
# main() edge cases
# ---------------------------------------------------------------------------

class TestMainEdge:
    def test_scelta_non_numerica(self, capsys, monkeypatch):
        import turni_visite.cli as cli_mod
        monkeypatch.setattr(cli_mod, "DATA_FILE", "/tmp/test_main_cli.json")
        with patch("builtins.input", side_effect=["abc", "19"]):
            with patch.object(JsonRepository, "__init__", lambda self, f: self._reset_state()):
                with patch.object(JsonRepository, "_reset_state", lambda self: setattr(self, 'fratelli', set()) or
                                  setattr(self, 'famiglie', set()) or setattr(self, 'associazioni', {}) or
                                  setattr(self, 'frequenze', {}) or setattr(self, 'capacita', {}) or
                                  setattr(self, 'storico_turni', []) or setattr(self, 'settings', {"cooldown_mesi": 3}) or
                                  setattr(self, 'indisponibilita', {}) or setattr(self, 'vincoli_personalizzati', []) or
                                  setattr(self, 'week_templates', {}) or setattr(self, 'audit_log', []) or
                                  setattr(self, 'affinita', []) or setattr(self, 'bozza_turni', None) or
                                  setattr(self, 'filename', "/tmp/test_main_cli.json")):
                    with patch.object(JsonRepository, "load", lambda self: None):
                        with patch("turni_visite.cli.trova_alias_simili", return_value=[]):
                            main()
        out = capsys.readouterr().out
        assert "non valida" in out

    def test_scelta_fuori_range(self, capsys, monkeypatch):
        import turni_visite.cli as cli_mod
        monkeypatch.setattr(cli_mod, "DATA_FILE", "/tmp/test_main_cli2.json")
        with patch("builtins.input", side_effect=["99", "19"]):
            with patch.object(JsonRepository, "__init__", lambda self, f: self._reset_state()):
                with patch.object(JsonRepository, "_reset_state", lambda self: setattr(self, 'fratelli', set()) or
                                  setattr(self, 'famiglie', set()) or setattr(self, 'associazioni', {}) or
                                  setattr(self, 'frequenze', {}) or setattr(self, 'capacita', {}) or
                                  setattr(self, 'storico_turni', []) or setattr(self, 'settings', {"cooldown_mesi": 3}) or
                                  setattr(self, 'indisponibilita', {}) or setattr(self, 'vincoli_personalizzati', []) or
                                  setattr(self, 'week_templates', {}) or setattr(self, 'audit_log', []) or
                                  setattr(self, 'affinita', []) or setattr(self, 'bozza_turni', None) or
                                  setattr(self, 'filename', "/tmp/test_main_cli2.json")):
                    with patch.object(JsonRepository, "load", lambda self: None):
                        with patch("turni_visite.cli.trova_alias_simili", return_value=[]):
                            main()
        out = capsys.readouterr().out
        assert "non valida" in out
