"""Test per la validazione input dell'API REST."""
import json
import pytest

try:
    from flask import Flask
    _FLASK_OK = True
except ImportError:
    _FLASK_OK = False

pytestmark = pytest.mark.skipif(not _FLASK_OK, reason="flask non installato")


@pytest.fixture
def client(tmp_path):
    from turni_visite.api import create_app
    data_file = tmp_path / "test_data.json"
    app = create_app(data_file=str(data_file))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestFratelliValidation:
    def test_body_non_json(self, client):
        resp = client.post("/api/fratelli", data="not json",
                           content_type="text/plain")
        assert resp.status_code == 415

    def test_nome_mancante(self, client):
        resp = client.post("/api/fratelli",
                           data=json.dumps({"capacita": 3}),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_capacita_fuori_range(self, client):
        resp = client.post("/api/fratelli",
                           data=json.dumps({"nome": "Mario", "capacita": 100}),
                           content_type="application/json")
        assert resp.status_code == 400
        assert "capacit" in resp.get_json()["errore"].lower()

    def test_aggiunta_valida(self, client):
        resp = client.post("/api/fratelli",
                           data=json.dumps({"nome": "Mario", "capacita": 3}),
                           content_type="application/json")
        assert resp.status_code == 201


class TestFamiglieValidation:
    def test_frequenza_non_valida(self, client):
        resp = client.post("/api/famiglie",
                           data=json.dumps({"nome": "Rossi", "frequenza": 3}),
                           content_type="application/json")
        assert resp.status_code == 400
        assert "frequenza" in resp.get_json()["errore"].lower()

    def test_aggiunta_valida(self, client):
        resp = client.post("/api/famiglie",
                           data=json.dumps({"nome": "Rossi", "frequenza": 2}),
                           content_type="application/json")
        assert resp.status_code == 201


class TestAssociazioniValidation:
    def test_campi_mancanti(self, client):
        resp = client.post("/api/associazioni",
                           data=json.dumps({"fratello": "Mario"}),
                           content_type="application/json")
        assert resp.status_code == 400
        assert "obbligatori" in resp.get_json()["errore"].lower()


class TestOttimizzaValidation:
    def test_mesi_formato_errato(self, client):
        resp = client.post("/api/ottimizza",
                           data=json.dumps({"mesi": ["2025-13"]}),
                           content_type="application/json")
        assert resp.status_code == 400
        assert "mese" in resp.get_json()["errore"].lower()

    def test_mesi_non_lista(self, client):
        resp = client.post("/api/ottimizza",
                           data=json.dumps({"mesi": "2025-03"}),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_mesi_mancante(self, client):
        resp = client.post("/api/ottimizza",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 400


class TestPreCheckValidation:
    def test_mesi_formato_errato(self, client):
        resp = client.post("/api/pre-check",
                           data=json.dumps({"mesi": ["abc"]}),
                           content_type="application/json")
        assert resp.status_code == 400


class TestVincoliValidation:
    def test_tipo_non_valido(self, client):
        client.post("/api/fratelli",
                     data=json.dumps({"nome": "Mario"}),
                     content_type="application/json")
        client.post("/api/fratelli",
                     data=json.dumps({"nome": "Luigi"}),
                     content_type="application/json")
        resp = client.post("/api/vincoli",
                           data=json.dumps({
                               "fratello_a": "Mario",
                               "fratello_b": "Luigi",
                               "tipo": "tipo_invalido",
                           }),
                           content_type="application/json")
        assert resp.status_code == 400
        assert "tipo" in resp.get_json()["errore"].lower()


class TestIndisponibilitaValidation:
    def test_mese_formato_errato(self, client):
        client.post("/api/fratelli",
                     data=json.dumps({"nome": "Mario"}),
                     content_type="application/json")
        resp = client.post("/api/indisponibilita",
                           data=json.dumps({"fratello": "Mario", "mese": "invalid"}),
                           content_type="application/json")
        assert resp.status_code == 400


class TestStoricoValidation:
    def test_delete_mese_formato_errato(self, client):
        resp = client.delete("/api/storico/not-a-month")
        assert resp.status_code == 400
