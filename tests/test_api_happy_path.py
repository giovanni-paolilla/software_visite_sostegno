"""Test happy-path per tutti gli endpoint API REST."""
import json
import pytest

try:
    from flask import Flask
    _FLASK_OK = True
except ImportError:
    _FLASK_OK = False

try:
    from ortools.sat.python import cp_model as _cp
    _ORTOOLS_OK = True
except Exception:
    _ORTOOLS_OK = False

pytestmark = pytest.mark.skipif(not _FLASK_OK, reason="flask non installato")


@pytest.fixture
def client(tmp_path):
    from turni_visite.api import create_app
    data_file = tmp_path / "test_data.json"
    app = create_app(data_file=str(data_file))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type="application/json")


def _delete_json(client, url, data):
    return client.delete(url, data=json.dumps(data), content_type="application/json")


def _setup_base(client):
    """Crea fratelli, famiglie e associazioni di base."""
    _post_json(client, "/api/fratelli", {"nome": "Mario Rossi", "capacita": 3})
    _post_json(client, "/api/fratelli", {"nome": "Luigi Bianchi", "capacita": 3})
    _post_json(client, "/api/fratelli", {"nome": "Carla Neri", "capacita": 3})
    _post_json(client, "/api/famiglie", {"nome": "Famiglia Verdi", "frequenza": 2})
    _post_json(client, "/api/famiglie", {"nome": "Famiglia Blu", "frequenza": 1})
    _post_json(client, "/api/associazioni", {"fratello": "Mario Rossi", "famiglia": "Famiglia Verdi"})
    _post_json(client, "/api/associazioni", {"fratello": "Luigi Bianchi", "famiglia": "Famiglia Verdi"})
    _post_json(client, "/api/associazioni", {"fratello": "Carla Neri", "famiglia": "Famiglia Blu"})


class TestFratelliHappyPath:
    def test_add_e_list(self, client):
        resp = _post_json(client, "/api/fratelli", {"nome": "Mario Rossi"})
        assert resp.status_code == 201
        assert resp.get_json()["nome"] == "Mario Rossi"

        resp = client.get("/api/fratelli")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["nome"] == "Mario Rossi"
        assert data[0]["capacita"] == 1

    def test_add_con_capacita(self, client):
        resp = _post_json(client, "/api/fratelli", {"nome": "Mario", "capacita": 5})
        assert resp.status_code == 201
        data = client.get("/api/fratelli").get_json()
        assert data[0]["capacita"] == 5

    def test_delete(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        resp = client.delete("/api/fratelli/Mario")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        assert len(client.get("/api/fratelli").get_json()) == 0

    def test_delete_then_reinsert_same_name(self, client):
        assert _post_json(client, "/api/fratelli", {"nome": "Mario"}).status_code == 201
        assert client.delete("/api/fratelli/Mario").status_code == 200
        resp = _post_json(client, "/api/fratelli", {"nome": "Mario"})
        assert resp.status_code == 201
        assert resp.get_json()["nome"] == "Mario"

    def test_delete_inesistente(self, client):
        resp = client.delete("/api/fratelli/Fantasma")
        assert resp.status_code == 404


class TestFamiglieHappyPath:
    def test_add_e_list(self, client):
        resp = _post_json(client, "/api/famiglie", {"nome": "Fam Rossi"})
        assert resp.status_code == 201

        data = client.get("/api/famiglie").get_json()
        assert len(data) == 1
        assert data[0]["frequenza"] == 2

    def test_add_con_frequenza(self, client):
        resp = _post_json(client, "/api/famiglie", {"nome": "Fam Rossi", "frequenza": 4})
        assert resp.status_code == 201
        data = client.get("/api/famiglie").get_json()
        assert data[0]["frequenza"] == 4

    def test_delete(self, client):
        _post_json(client, "/api/famiglie", {"nome": "Fam Rossi"})
        resp = client.delete("/api/famiglie/Fam Rossi")
        assert resp.status_code == 200

    def test_delete_inesistente(self, client):
        resp = client.delete("/api/famiglie/Fantasma")
        assert resp.status_code == 404


class TestAssociazioniHappyPath:
    def test_associa_e_verifica(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        _post_json(client, "/api/famiglie", {"nome": "Fam A"})
        resp = _post_json(client, "/api/associazioni", {"fratello": "Mario", "famiglia": "Fam A"})
        assert resp.status_code == 201

        data = client.get("/api/famiglie").get_json()
        assert "Mario" in data[0]["fratelli_associati"]

    def test_disassocia(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        _post_json(client, "/api/famiglie", {"nome": "Fam A"})
        _post_json(client, "/api/associazioni", {"fratello": "Mario", "famiglia": "Fam A"})

        resp = _delete_json(client, "/api/associazioni", {"fratello": "Mario", "famiglia": "Fam A"})
        assert resp.status_code == 200

    def test_disassocia_non_associato(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        _post_json(client, "/api/famiglie", {"nome": "Fam A"})
        resp = _delete_json(client, "/api/associazioni", {"fratello": "Mario", "famiglia": "Fam A"})
        assert resp.status_code == 404


class TestDashboardHappyPath:
    def test_dashboard_vuoto(self, client):
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["n_fratelli"] == 0
        assert data["n_famiglie"] == 0

    def test_dashboard_con_dati(self, client):
        _setup_base(client)
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["n_fratelli"] == 3
        assert data["n_famiglie"] == 2


class TestStoricoHappyPath:
    def test_storico_vuoto(self, client):
        resp = client.get("/api/storico")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_delete_storico_mese_non_esistente(self, client):
        resp = client.delete("/api/storico/2026-01")
        assert resp.status_code == 404


class TestStatisticheHappyPath:
    def test_carico_vuoto(self, client):
        resp = client.get("/api/stats/carico")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_equita_vuoto(self, client):
        resp = client.get("/api/stats/equita")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["media"] == 0

    def test_trend_vuoto(self, client):
        resp = client.get("/api/stats/trend")
        assert resp.status_code == 200
        assert resp.get_json() == []


class TestIndisponibilitaHappyPath:
    def test_get_indisponibilita(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        resp = client.get("/api/indisponibilita/Mario")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_add_indisponibilita(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        resp = _post_json(client, "/api/indisponibilita", {"fratello": "Mario", "mese": "2026-03"})
        assert resp.status_code == 201

        data = client.get("/api/indisponibilita/Mario").get_json()
        assert "2026-03" in data

    def test_get_indisponibilita_inesistente(self, client):
        resp = client.get("/api/indisponibilita/Fantasma")
        assert resp.status_code == 404


class TestVincoliHappyPath:
    def test_get_vincoli_vuoti(self, client):
        resp = client.get("/api/vincoli")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_add_vincolo(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        _post_json(client, "/api/fratelli", {"nome": "Luigi"})
        resp = _post_json(client, "/api/vincoli", {
            "fratello_a": "Mario", "fratello_b": "Luigi",
            "tipo": "incompatibile",
        })
        assert resp.status_code == 201

        data = client.get("/api/vincoli").get_json()
        assert len(data) == 1
        assert data[0]["tipo"] == "incompatibile"


@pytest.mark.skipif(not _ORTOOLS_OK, reason="ortools non installato")
class TestOttimizzaHappyPath:
    def test_ottimizza_feasible(self, client):
        _setup_base(client)
        resp = _post_json(client, "/api/ottimizza", {"mesi": ["2026-01"]})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["feasible"] is True
        assert "solution" in data
        assert "2026-01" in data["solution"]["by_month"]

    def test_ottimizza_infeasible(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Solo", "capacita": 0})
        _post_json(client, "/api/famiglie", {"nome": "Fam A", "frequenza": 2})
        _post_json(client, "/api/associazioni", {"fratello": "Solo", "famiglia": "Fam A"})
        resp = _post_json(client, "/api/ottimizza", {"mesi": ["2026-01"]})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["feasible"] is False
        assert "diagnosi" in data

    def test_pre_check_fattibile(self, client):
        _setup_base(client)
        resp = _post_json(client, "/api/pre-check", {"mesi": ["2026-01"]})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["fattibile"] is True

    def test_ottimizza_con_cooldown_custom(self, client):
        _setup_base(client)
        resp = _post_json(client, "/api/ottimizza", {"mesi": ["2026-01"], "cooldown": 1})
        assert resp.status_code == 200
        assert resp.get_json()["feasible"] is True

    def test_cooldown_negativo(self, client):
        _setup_base(client)
        resp = _post_json(client, "/api/ottimizza", {"mesi": ["2026-01"], "cooldown": 0})
        assert resp.status_code == 400

    def test_cooldown_non_numerico(self, client):
        _setup_base(client)
        resp = _post_json(client, "/api/ottimizza", {"mesi": ["2026-01"], "cooldown": "abc"})
        assert resp.status_code == 400
