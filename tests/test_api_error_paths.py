"""Test per error paths e edge cases dell'API REST."""
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


def _post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type="application/json")


def _patch_json(client, url, data):
    return client.patch(url, data=json.dumps(data), content_type="application/json")


def _delete_json(client, url, data):
    return client.delete(url, data=json.dumps(data), content_type="application/json")


def _setup_data(client):
    _post_json(client, "/api/fratelli", {"nome": "Mario"})
    _post_json(client, "/api/fratelli", {"nome": "Luigi"})
    _post_json(client, "/api/fratelli", {"nome": "Carla"})
    _post_json(client, "/api/famiglie", {"nome": "Rossi"})
    _post_json(client, "/api/famiglie", {"nome": "Bianchi"})
    _post_json(client, "/api/associazioni", {"fratello": "Mario", "famiglia": "Rossi"})
    _post_json(client, "/api/associazioni", {"fratello": "Luigi", "famiglia": "Rossi"})
    _post_json(client, "/api/associazioni", {"fratello": "Carla", "famiglia": "Bianchi"})
    _post_json(client, "/api/associazioni", {"fratello": "Mario", "famiglia": "Bianchi"})


class TestFratelliErrorPaths:
    def test_capacita_non_numerica(self, client):
        resp = _post_json(client, "/api/fratelli", {"nome": "Test", "capacita": "abc"})
        assert resp.status_code == 400

    def test_capacita_negativa(self, client):
        resp = _post_json(client, "/api/fratelli", {"nome": "Test", "capacita": -1})
        assert resp.status_code == 400

    def test_nome_duplicato(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        resp = _post_json(client, "/api/fratelli", {"nome": "Mario"})
        assert resp.status_code == 409
        assert "errore" in resp.get_json()

    def test_nome_vuoto(self, client):
        resp = _post_json(client, "/api/fratelli", {"nome": ""})
        assert resp.status_code == 400

    def test_nome_null(self, client):
        resp = _post_json(client, "/api/fratelli", {"nome": None})
        assert resp.status_code == 400

    def test_delete_non_esistente(self, client):
        resp = client.delete("/api/fratelli/Fantasma")
        assert resp.status_code == 404

    def test_body_non_dict(self, client):
        resp = client.post("/api/fratelli", data=json.dumps([1, 2, 3]),
                           content_type="application/json")
        assert resp.status_code == 400
        assert "JSON" in resp.get_json()["errore"]

    def test_capacita_zero_valido(self, client):
        resp = _post_json(client, "/api/fratelli", {"nome": "Inattivo", "capacita": 0})
        assert resp.status_code == 201

    def test_capacita_50_valido(self, client):
        resp = _post_json(client, "/api/fratelli", {"nome": "Super", "capacita": 50})
        assert resp.status_code == 201


class TestFamiglieErrorPaths:
    def test_frequenza_non_numerica(self, client):
        resp = _post_json(client, "/api/famiglie", {"nome": "Fam", "frequenza": "abc"})
        assert resp.status_code == 400

    def test_nome_vuoto(self, client):
        resp = _post_json(client, "/api/famiglie", {"nome": ""})
        assert resp.status_code == 400

    def test_nome_duplicato(self, client):
        _post_json(client, "/api/famiglie", {"nome": "Rossi"})
        resp = _post_json(client, "/api/famiglie", {"nome": "Rossi"})
        assert resp.status_code == 409

    def test_delete_non_esistente(self, client):
        resp = client.delete("/api/famiglie/Fantasma")
        assert resp.status_code == 404

    def test_frequenza_5_non_valida(self, client):
        resp = _post_json(client, "/api/famiglie", {"nome": "Test", "frequenza": 5})
        assert resp.status_code == 400


class TestAssociazioniErrorPaths:
    def test_fratello_non_esistente(self, client):
        _post_json(client, "/api/famiglie", {"nome": "Rossi"})
        resp = _post_json(client, "/api/associazioni", {"fratello": "Fantasma", "famiglia": "Rossi"})
        assert resp.status_code == 400

    def test_famiglia_non_esistente(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        resp = _post_json(client, "/api/associazioni", {"fratello": "Mario", "famiglia": "Fantasma"})
        assert resp.status_code == 400

    def test_associazione_duplicata(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        _post_json(client, "/api/famiglie", {"nome": "Rossi"})
        _post_json(client, "/api/associazioni", {"fratello": "Mario", "famiglia": "Rossi"})
        resp = _post_json(client, "/api/associazioni", {"fratello": "Mario", "famiglia": "Rossi"})
        assert resp.status_code == 409

    def test_disassociate_body_non_json(self, client):
        resp = client.delete("/api/associazioni", data="nope", content_type="text/plain")
        assert resp.status_code == 400

    def test_disassociate_non_esistente(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        _post_json(client, "/api/famiglie", {"nome": "Rossi"})
        resp = _delete_json(client, "/api/associazioni", {"fratello": "Mario", "famiglia": "Rossi"})
        assert resp.status_code == 404


class TestOttimizzaErrorPaths:
    def test_mesi_lista_vuota(self, client):
        resp = _post_json(client, "/api/ottimizza", {"mesi": []})
        assert resp.status_code == 400

    def test_mesi_con_none(self, client):
        resp = _post_json(client, "/api/ottimizza", {"mesi": [None]})
        assert resp.status_code == 400

    def test_cooldown_zero(self, client):
        _setup_data(client)
        resp = _post_json(client, "/api/ottimizza", {"mesi": ["2026-01"], "cooldown": 0})
        assert resp.status_code == 400

    def test_cooldown_float_string(self, client):
        _setup_data(client)
        resp = _post_json(client, "/api/ottimizza", {"mesi": ["2026-01"], "cooldown": "abc"})
        assert resp.status_code == 400

    def test_body_non_json(self, client):
        resp = client.post("/api/ottimizza", data="nope", content_type="text/plain")
        assert resp.status_code == 415


class TestPreCheckErrorPaths:
    def test_mesi_lista_vuota(self, client):
        resp = _post_json(client, "/api/pre-check", {"mesi": []})
        assert resp.status_code == 400

    def test_cooldown_negativo(self, client):
        _setup_data(client)
        resp = _post_json(client, "/api/pre-check", {"mesi": ["2026-01"], "cooldown": -5})
        assert resp.status_code == 400

    def test_cooldown_non_numerico(self, client):
        _setup_data(client)
        resp = _post_json(client, "/api/pre-check", {"mesi": ["2026-01"], "cooldown": "x"})
        assert resp.status_code == 400

    def test_body_mancante(self, client):
        resp = client.post("/api/pre-check")
        assert resp.status_code == 400


class TestVincoliErrorPaths:
    def test_fratello_a_non_esistente(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Luigi"})
        resp = _post_json(client, "/api/vincoli", {
            "fratello_a": "Fantasma", "fratello_b": "Luigi", "tipo": "incompatibile"})
        assert resp.status_code == 400

    def test_campi_mancanti_fratello_a(self, client):
        resp = _post_json(client, "/api/vincoli", {"fratello_b": "X", "tipo": "incompatibile"})
        assert resp.status_code == 400

    def test_campi_mancanti_tipo(self, client):
        resp = _post_json(client, "/api/vincoli", {"fratello_a": "X", "fratello_b": "Y"})
        assert resp.status_code == 400

    def test_get_vincoli_vuoti(self, client):
        resp = client.get("/api/vincoli")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_get_vincoli_con_dati(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        _post_json(client, "/api/fratelli", {"nome": "Luigi"})
        _post_json(client, "/api/vincoli", {
            "fratello_a": "Mario", "fratello_b": "Luigi",
            "tipo": "incompatibile", "descrizione": "test"})
        resp = client.get("/api/vincoli")
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["tipo"] == "incompatibile"

    def test_vincolo_con_se_stesso(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        resp = _post_json(client, "/api/vincoli", {
            "fratello_a": "Mario", "fratello_b": "Mario", "tipo": "incompatibile"})
        assert resp.status_code == 400


class TestIndisponibilitaErrorPaths:
    def test_fratello_non_esistente_post(self, client):
        resp = _post_json(client, "/api/indisponibilita", {"fratello": "Fantasma", "mese": "2026-05"})
        assert resp.status_code == 400

    def test_fratello_non_esistente_get(self, client):
        resp = client.get("/api/indisponibilita/Fantasma")
        assert resp.status_code == 404

    def test_campi_mancanti(self, client):
        resp = _post_json(client, "/api/indisponibilita", {"fratello": "Mario"})
        assert resp.status_code == 400

    def test_mese_invalido(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        resp = _post_json(client, "/api/indisponibilita", {"fratello": "Mario", "mese": "abc"})
        assert resp.status_code == 400


class TestStoricoErrorPaths:
    def test_delete_mese_non_trovato(self, client):
        resp = client.delete("/api/storico/2026-01")
        assert resp.status_code == 404

    def test_get_storico_vuoto(self, client):
        resp = client.get("/api/storico")
        assert resp.status_code == 200
        assert resp.get_json() == []


class TestStatsEndpoints:
    def test_carico_storico_vuoto(self, client):
        resp = client.get("/api/stats/carico")
        assert resp.status_code == 200

    def test_equita_storico_vuoto(self, client):
        resp = client.get("/api/stats/equita")
        assert resp.status_code == 200

    def test_trend_storico_vuoto(self, client):
        resp = client.get("/api/stats/trend")
        assert resp.status_code == 200

    def test_completamento_storico_vuoto(self, client):
        resp = client.get("/api/stats/completamento")
        assert resp.status_code == 200


class TestDashboardEndpoint:
    def test_dashboard_vuoto(self, client):
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["n_fratelli"] == 0
        assert data["n_famiglie"] == 0

    def test_dashboard_con_dati(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario", "capacita": 3})
        _post_json(client, "/api/famiglie", {"nome": "Rossi", "frequenza": 2})
        resp = client.get("/api/dashboard")
        data = resp.get_json()
        assert data["n_fratelli"] == 1
        assert data["capacita_totale"] == 3
        assert data["domanda_totale"] == 2
        assert data["bilancio"] == 1


class TestAffinitaErrorPaths:
    def test_famiglia_non_esistente(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        resp = _post_json(client, "/api/affinita", {"famiglia": "X", "fratello": "Mario", "peso": 5})
        assert resp.status_code == 400

    def test_peso_stringa(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        _post_json(client, "/api/famiglie", {"nome": "Rossi"})
        resp = _post_json(client, "/api/affinita", {"famiglia": "Rossi", "fratello": "Mario", "peso": "abc"})
        assert resp.status_code == 400

    def test_peso_fuori_range(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        _post_json(client, "/api/famiglie", {"nome": "Rossi"})
        resp = _post_json(client, "/api/affinita", {"famiglia": "Rossi", "fratello": "Mario", "peso": 15})
        assert resp.status_code == 400

    def test_peso_zero_valido(self, client):
        _post_json(client, "/api/fratelli", {"nome": "Mario"})
        _post_json(client, "/api/famiglie", {"nome": "Rossi"})
        resp = _post_json(client, "/api/affinita", {"famiglia": "Rossi", "fratello": "Mario", "peso": 0})
        assert resp.status_code == 201

    def test_delete_campi_mancanti(self, client):
        resp = _delete_json(client, "/api/affinita", {"famiglia": "Rossi"})
        assert resp.status_code == 400


class TestBozzaSlotEdgeCases:
    def test_patch_slot_non_numerico(self, client):
        resp = _patch_json(client, "/api/bozza/stato", {
            "mese": "2026-01", "famiglia": "Rossi", "slot": "abc", "stato": "accettato"})
        assert resp.status_code == 400

    def test_conferma_senza_bozza(self, client):
        resp = client.post("/api/bozza/conferma")
        assert resp.status_code == 400


class TestSostituzioneErrorPaths:
    def test_applica_slot_non_numerico(self, client):
        resp = _post_json(client, "/api/sostituzione/applica", {
            "mese": "2026-01", "famiglia": "R", "slot": "abc",
            "vecchio_fratello": "A", "nuovo_fratello": "B"})
        assert resp.status_code == 400

    def test_applica_nuovo_fratello_non_esistente(self, client):
        _setup_data(client)
        resp = _post_json(client, "/api/sostituzione/applica", {
            "mese": "2026-01", "famiglia": "Rossi", "slot": 0,
            "vecchio_fratello": "Mario", "nuovo_fratello": "Fantasma"})
        assert resp.status_code == 400


class TestEsecuzioneErrorPaths:
    def test_slot_non_numerico(self, client):
        resp = _patch_json(client, "/api/storico/2026-01/esecuzione", {
            "famiglia": "Rossi", "slot": "abc", "stato": "completato"})
        assert resp.status_code == 400

    def test_body_mancante(self, client):
        resp = client.patch("/api/storico/2026-01/esecuzione")
        assert resp.status_code == 400

    def test_campi_mancanti(self, client):
        resp = _patch_json(client, "/api/storico/2026-01/esecuzione", {"famiglia": "R"})
        assert resp.status_code == 400


class TestWhatsAppExportEdge:
    def test_solution_senza_by_month(self, client):
        # L'API richiede che 'solution' contenga 'by_month': restituisce 400 se mancante
        resp = _post_json(client, "/api/export/whatsapp", {
            "mesi": ["2026-01"], "solution": {}})
        assert resp.status_code == 400

    def test_frequenze_opzionali(self, client):
        resp = _post_json(client, "/api/export/whatsapp", {
            "mesi": ["2026-01"], "solution": {"by_month": {}},
            "frequenze": {"Rossi": 2}})
        assert resp.status_code == 200
