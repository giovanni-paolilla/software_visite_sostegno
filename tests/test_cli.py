"""Test per turni_visite.cli — funzioni CLI con I/O mockato."""
import pytest
from unittest.mock import patch, MagicMock

from turni_visite.cli import (
    _parse_lista_mesi_interattiva,
    _ensure_week_windows_for_month,
    _stampa_elenco,
    _ask_fuzzy_name,
    _cmd_aggiungi_fratello,
    _cmd_aggiungi_famiglia,
    _cmd_associa,
    _cmd_frequenza,
    _cmd_capacita,
    _cmd_elimina_fratello,
    _cmd_elimina_famiglia,
    _cmd_storico,
    _cmd_indisponibilita,
    _cmd_vincoli,
    _cmd_backup,
    _cmd_statistiche,
    _cmd_import_csv,
    _cmd_dashboard,
    _cmd_sanifica,
    _cmd_ottimizza,
)
from turni_visite.repository import JsonRepository


@pytest.fixture
def repo(tmp_path):
    r = JsonRepository(str(tmp_path / "cli_test.json"))
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_family("Famiglia Verdi")
    r.set_frequency("Famiglia Verdi", 2)
    r.associate("Mario Rossi", "Famiglia Verdi")
    r.associate("Luigi Bianchi", "Famiglia Verdi")
    return r


# ---------------------------------------------------------------------------
# _parse_lista_mesi_interattiva
# ---------------------------------------------------------------------------

class TestParseListaMesiInterattiva:
    def test_mesi_validi(self):
        with patch("builtins.input", side_effect=["2026-01", "2026-03", ""]):
            result = _parse_lista_mesi_interattiva()
        assert result == ["2026-01", "2026-03"]

    def test_mese_duplicato_ignorato(self):
        with patch("builtins.input", side_effect=["2026-01", "2026-01", ""]):
            result = _parse_lista_mesi_interattiva()
        assert result == ["2026-01"]

    def test_mese_non_valido_scartato(self, capsys):
        with patch("builtins.input", side_effect=["bad", "2026-01", ""]):
            result = _parse_lista_mesi_interattiva()
        assert result == ["2026-01"]
        assert "Formato" in capsys.readouterr().out

    def test_invio_vuoto_termina(self):
        with patch("builtins.input", side_effect=[""]):
            result = _parse_lista_mesi_interattiva()
        assert result == []

    def test_mesi_ordinati(self):
        with patch("builtins.input", side_effect=["2026-03", "2026-01", ""]):
            result = _parse_lista_mesi_interattiva()
        assert result == ["2026-01", "2026-03"]


# ---------------------------------------------------------------------------
# _ensure_week_windows_for_month
# ---------------------------------------------------------------------------

class TestEnsureWeekWindows:
    def test_usa_default_con_invio(self):
        ww = {}
        with patch("builtins.input", return_value=""):
            _ensure_week_windows_for_month(
                "2026-01", {"Fam A": 2}, {"Fam A"}, ww, {},
            )
        assert 2 in ww["2026-01"]
        assert len(ww["2026-01"][2]) == 2

    def test_usa_template_salvato(self):
        ww = {}
        with patch("builtins.input", return_value=""):
            _ensure_week_windows_for_month(
                "2026-01", {"Fam A": 2}, {"Fam A"}, ww,
                {"2": ["05-11", "19-25"]},
            )
        assert ww["2026-01"][2] == ["05-11", "19-25"]

    def test_input_custom(self):
        ww = {}
        with patch("builtins.input", return_value="03-09, 17-23"):
            _ensure_week_windows_for_month(
                "2026-01", {"Fam A": 2}, {"Fam A"}, ww, {},
            )
        assert ww["2026-01"][2] == ["03-09", "17-23"]

    def test_input_errato_poi_corretto(self):
        ww = {}
        with patch("builtins.input", side_effect=["bad", "03-09, 17-23"]):
            _ensure_week_windows_for_month(
                "2026-01", {"Fam A": 2}, {"Fam A"}, ww, {},
            )
        assert 2 in ww["2026-01"]

    def test_freq_gia_presente_skip(self):
        ww = {"2026-01": {2: ["01-07", "15-21"]}}
        with patch("builtins.input") as mock_input:
            _ensure_week_windows_for_month(
                "2026-01", {"Fam A": 2}, {"Fam A"}, ww, {},
            )
        mock_input.assert_not_called()


# ---------------------------------------------------------------------------
# _stampa_elenco
# ---------------------------------------------------------------------------

class TestStampaElenco:
    def test_stampa_fratelli_e_famiglie(self, repo, capsys):
        _stampa_elenco(repo)
        out = capsys.readouterr().out
        assert "Mario Rossi" in out
        assert "Luigi Bianchi" in out
        assert "Famiglia Verdi" in out

    def test_repo_vuoto(self, tmp_path, capsys):
        r = JsonRepository(str(tmp_path / "empty.json"))
        _stampa_elenco(r)
        out = capsys.readouterr().out
        assert "Nessun fratello" in out
        assert "Nessuna famiglia" in out

    def test_mostra_indisponibilita(self, repo, capsys):
        repo.add_indisponibilita("Mario Rossi", "2026-05")
        _stampa_elenco(repo)
        out = capsys.readouterr().out
        assert "indisponibile" in out
        assert "2026-05" in out


# ---------------------------------------------------------------------------
# _ask_fuzzy_name
# ---------------------------------------------------------------------------

class TestAskFuzzyName:
    def test_nome_esatto(self):
        result = _ask_fuzzy_name("Mario Rossi", ["Mario Rossi", "Luigi Bianchi"], "fratelli")
        assert result == "Mario Rossi"

    def test_nome_canonicalizzato(self):
        result = _ask_fuzzy_name("mario rossi", ["Mario Rossi"], "fratelli")
        assert result == "Mario Rossi"

    def test_nessun_candidato(self, capsys):
        result = _ask_fuzzy_name("Mario", [], "fratelli")
        assert result is None
        assert "Non ci sono" in capsys.readouterr().out

    def test_suggerimento_scelto(self):
        with patch("builtins.input", return_value="1"):
            result = _ask_fuzzy_name("Mario Ross", ["Mario Rossi", "Luigi Bianchi"], "fratelli")
        assert result == "Mario Rossi"

    def test_annulla_con_zero(self):
        with patch("builtins.input", return_value="0"):
            result = _ask_fuzzy_name("Mario Ross", ["Mario Rossi"], "fratelli")
        assert result is None

    def test_nessun_match(self, capsys):
        result = _ask_fuzzy_name("Zzzzz", ["Mario Rossi", "Luigi Bianchi"], "fratelli")
        assert result is None
        assert "non trovato" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _cmd_aggiungi_fratello / _cmd_aggiungi_famiglia
# ---------------------------------------------------------------------------

class TestCmdAggiungiFratello:
    def test_aggiunta_ok(self, repo, capsys):
        with patch("builtins.input", return_value="Carla Neri"):
            _cmd_aggiungi_fratello(repo)
        assert "Carla Neri" in repo.fratelli
        assert "aggiunto" in capsys.readouterr().out

    def test_duplicato(self, repo, capsys):
        with patch("builtins.input", return_value="Mario Rossi"):
            _cmd_aggiungi_fratello(repo)
        assert "Errore" in capsys.readouterr().out


class TestCmdAggiungiFamiglia:
    def test_aggiunta_ok(self, repo, capsys):
        with patch("builtins.input", return_value="Famiglia Blu"):
            _cmd_aggiungi_famiglia(repo)
        assert "Famiglia Blu" in repo.famiglie


# ---------------------------------------------------------------------------
# _cmd_associa
# ---------------------------------------------------------------------------

class TestCmdAssocia:
    def test_associa_ok(self, repo, capsys):
        repo.add_brother("Carla Neri")
        with patch("builtins.input", side_effect=["Carla Neri", "Famiglia Verdi"]):
            _cmd_associa(repo)
        assert "Carla Neri" in repo.associazioni["Famiglia Verdi"]

    def test_fratello_annullato(self, repo, capsys):
        with patch("builtins.input", side_effect=["Zzzzzzz"]):
            _cmd_associa(repo)
        assert "annullata" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _cmd_frequenza / _cmd_capacita
# ---------------------------------------------------------------------------

class TestCmdFrequenza:
    def test_visualizza(self, repo, capsys):
        with patch("builtins.input", side_effect=["Famiglia Verdi", "V"]):
            _cmd_frequenza(repo)
        assert "2" in capsys.readouterr().out

    def test_imposta(self, repo, capsys):
        with patch("builtins.input", side_effect=["Famiglia Verdi", "I", "4"]):
            _cmd_frequenza(repo)
        assert repo.frequenze["Famiglia Verdi"] == 4


class TestCmdCapacita:
    def test_visualizza(self, repo, capsys):
        with patch("builtins.input", side_effect=["Mario Rossi", "V"]):
            _cmd_capacita(repo)
        assert "1" in capsys.readouterr().out

    def test_imposta(self, repo, capsys):
        with patch("builtins.input", side_effect=["Mario Rossi", "I", "5"]):
            _cmd_capacita(repo)
        assert repo.capacita["Mario Rossi"] == 5


# ---------------------------------------------------------------------------
# _cmd_elimina_fratello / _cmd_elimina_famiglia
# ---------------------------------------------------------------------------

class TestCmdEliminaFratello:
    def test_elimina_confermato(self, repo, capsys):
        with patch("builtins.input", side_effect=["Mario Rossi", "s"]):
            _cmd_elimina_fratello(repo)
        assert "Mario Rossi" not in repo.fratelli

    def test_elimina_non_confermato(self, repo):
        with patch("builtins.input", side_effect=["Mario Rossi", "n"]):
            _cmd_elimina_fratello(repo)
        assert "Mario Rossi" in repo.fratelli


class TestCmdEliminaFamiglia:
    def test_elimina_confermato(self, repo, capsys):
        with patch("builtins.input", side_effect=["Famiglia Verdi", "s"]):
            _cmd_elimina_famiglia(repo)
        assert "Famiglia Verdi" not in repo.famiglie


# ---------------------------------------------------------------------------
# _cmd_storico
# ---------------------------------------------------------------------------

class TestCmdStorico:
    def test_storico_vuoto(self, repo, capsys):
        _cmd_storico(repo)
        assert "Nessun mese" in capsys.readouterr().out

    def test_storico_visualizza(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with patch("builtins.input", return_value="I"):
            _cmd_storico(repo)
        out = capsys.readouterr().out
        assert "2026-01" in out

    def test_storico_elimina(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with patch("builtins.input", side_effect=["E", "2026-01", "s"]):
            _cmd_storico(repo)
        assert not repo.storico_has_mese("2026-01")

    def test_storico_dettaglio(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with patch("builtins.input", side_effect=["D", "2026-01"]):
            _cmd_storico(repo)
        out = capsys.readouterr().out
        assert "Famiglia Verdi" in out
        assert "Mario Rossi" in out


# ---------------------------------------------------------------------------
# _cmd_indisponibilita
# ---------------------------------------------------------------------------

class TestCmdIndisponibilita:
    def test_aggiungi(self, repo, capsys):
        with patch("builtins.input", side_effect=["Mario Rossi", "A", "2026-05"]):
            _cmd_indisponibilita(repo)
        assert "2026-05" in repo.get_indisponibilita("Mario Rossi")

    def test_rimuovi(self, repo, capsys):
        repo.add_indisponibilita("Mario Rossi", "2026-05")
        with patch("builtins.input", side_effect=["Mario Rossi", "R", "2026-05"]):
            _cmd_indisponibilita(repo)
        assert "2026-05" not in repo.get_indisponibilita("Mario Rossi")


# ---------------------------------------------------------------------------
# _cmd_vincoli
# ---------------------------------------------------------------------------

class TestCmdVincoli:
    def test_aggiungi_vincolo(self, repo, capsys):
        with patch("builtins.input", side_effect=[
            "A", "Mario Rossi", "Luigi Bianchi", "incompatibile", "test",
        ]):
            _cmd_vincoli(repo)
        assert len(repo.get_vincoli()) == 1

    def test_visualizza_vincoli_vuoti(self, repo, capsys):
        with patch("builtins.input", return_value="I"):
            _cmd_vincoli(repo)
        assert "Nessun vincolo" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _cmd_backup
# ---------------------------------------------------------------------------

class TestCmdBackup:
    def test_crea_backup(self, repo, capsys):
        with patch("builtins.input", return_value="1"):
            with patch("turni_visite.cli.create_backup", return_value="/tmp/backup.json"):
                _cmd_backup(repo)
        assert "creato" in capsys.readouterr().out

    def test_lista_vuota(self, repo, capsys):
        with patch("builtins.input", return_value="2"):
            with patch("turni_visite.cli.list_backups", return_value=[]):
                _cmd_backup(repo)
        assert "Nessun backup" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _cmd_statistiche
# ---------------------------------------------------------------------------

class TestCmdStatistiche:
    def test_storico_vuoto(self, repo, capsys):
        _cmd_statistiche(repo)
        assert "Nessun dato" in capsys.readouterr().out

    def test_carico(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with patch("builtins.input", return_value="1"):
            _cmd_statistiche(repo)
        out = capsys.readouterr().out
        assert "Mario Rossi" in out

    def test_equita(self, repo, capsys):
        repo.append_storico_turni("2026-01", [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
        ])
        with patch("builtins.input", return_value="2"):
            _cmd_statistiche(repo)
        out = capsys.readouterr().out
        assert "Gini" in out


# ---------------------------------------------------------------------------
# _cmd_import_csv
# ---------------------------------------------------------------------------

class TestCmdImportCsv:
    def test_import_valido(self, repo, tmp_path, capsys):
        csv = tmp_path / "import.csv"
        csv.write_text("tipo;nome;valore\nfratello;Carla Neri;2\n", encoding="utf-8")
        with patch("builtins.input", return_value=str(csv)):
            _cmd_import_csv(repo)
        assert "Carla Neri" in repo.fratelli

    def test_percorso_vuoto(self, repo, capsys):
        with patch("builtins.input", return_value=""):
            _cmd_import_csv(repo)


# ---------------------------------------------------------------------------
# _cmd_dashboard
# ---------------------------------------------------------------------------

class TestCmdDashboard:
    def test_dashboard(self, repo, capsys):
        _cmd_dashboard(repo)
        out = capsys.readouterr().out
        assert "DASHBOARD" in out
        assert "Fratelli attivi" in out


# ---------------------------------------------------------------------------
# _cmd_sanifica
# ---------------------------------------------------------------------------

class TestCmdSanifica:
    def test_sanifica_senza_alias(self, repo, capsys):
        with patch("builtins.input", return_value=""):
            _cmd_sanifica(repo)
        assert "sanificati" in capsys.readouterr().out

    def test_sanifica_con_alias(self, repo, capsys):
        with patch("builtins.input", side_effect=["Mario Rossi -> Marco Rossi", ""]):
            _cmd_sanifica(repo)
        assert "Marco Rossi" in repo.fratelli


# ---------------------------------------------------------------------------
# _cmd_ottimizza (integrazione parziale)
# ---------------------------------------------------------------------------

try:
    from ortools.sat.python import cp_model as _cp
    _ORTOOLS_OK = True
except Exception:
    _ORTOOLS_OK = False


@pytest.mark.skipif(not _ORTOOLS_OK, reason="ortools non installato")
class TestCmdOttimizza:
    def test_nessun_mese(self, repo, capsys):
        ww = {}
        with patch("builtins.input", side_effect=[""]):
            _cmd_ottimizza(repo, ww)
        assert "Nessun mese" in capsys.readouterr().out

    def test_ottimizza_e_salva(self, repo, capsys, tmp_path, monkeypatch):
        repo.set_brother_capacity("Mario Rossi", 3)
        repo.set_brother_capacity("Luigi Bianchi", 3)
        ww = {}
        import turni_visite.cli as cli_mod
        monkeypatch.setattr(cli_mod, "DATA_FILE", tmp_path / "dati.json")
        monkeypatch.setattr(
            "turni_visite.cli.export_pdf_mesi",
            lambda *a, **kw: None,
        )
        monkeypatch.setattr(
            "turni_visite.cli.open_file",
            lambda *a, **kw: True,
        )
        with patch("builtins.input", side_effect=[
            "2026-01", "",  # mesi
            "",             # week windows default
            "N",            # no WhatsApp
            "N",            # no CSV
            "s",            # conferma salvataggio
        ]):
            _cmd_ottimizza(repo, ww)
        out = capsys.readouterr().out
        assert "Turni salvati" in out or "PDF creato" in out
