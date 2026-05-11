"""Test per autenticazione API key e header CORS."""
import os
import pytest

try:
    from flask import Flask
    _FLASK_OK = True
except ImportError:
    _FLASK_OK = False

pytestmark = pytest.mark.skipif(not _FLASK_OK, reason="flask non installato")


@pytest.fixture
def client_no_key(tmp_path, monkeypatch):
    import turni_visite.api as api_mod
    monkeypatch.setattr(api_mod, "_API_KEY", "")
    monkeypatch.setattr(api_mod, "_NO_AUTH", True)
    data_file = tmp_path / "test_data.json"
    app = api_mod.create_app(data_file=str(data_file))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def client_with_key(tmp_path, monkeypatch):
    import turni_visite.api as api_mod
    monkeypatch.setattr(api_mod, "_API_KEY", "secret123")
    monkeypatch.setattr(api_mod, "_NO_AUTH", False)
    data_file = tmp_path / "test_data.json"
    app = api_mod.create_app(data_file=str(data_file))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestAuthDisabled:
    def test_senza_key_configurata_accetta_tutto(self, client_no_key):
        resp = client_no_key.get("/api/dashboard")
        assert resp.status_code == 200

    def test_header_superfluo_ignorato(self, client_no_key):
        resp = client_no_key.get("/api/dashboard", headers={"X-API-Key": "qualsiasi"})
        assert resp.status_code == 200


class TestAuthEnabled:
    def test_senza_header_ritorna_401(self, client_with_key):
        resp = client_with_key.get("/api/dashboard")
        assert resp.status_code == 401
        data = resp.get_json()
        assert "errore" in data

    def test_chiave_errata_ritorna_401(self, client_with_key):
        resp = client_with_key.get("/api/dashboard", headers={"X-API-Key": "sbagliata"})
        assert resp.status_code == 401

    def test_chiave_corretta_ritorna_200(self, client_with_key):
        resp = client_with_key.get("/api/dashboard", headers={"X-API-Key": "secret123"})
        assert resp.status_code == 200

    def test_post_senza_chiave_ritorna_401(self, client_with_key):
        import json
        resp = client_with_key.post(
            "/api/fratelli",
            data=json.dumps({"nome": "Mario"}),
            content_type="application/json",
        )
        assert resp.status_code == 401


class TestCORSHeaders:
    def test_cors_origin_presente(self, client_no_key):
        # L'API aggiunge CORS headers solo se la richiesta include un header Origin valido (con porta)
        resp = client_no_key.get("/api/dashboard", headers={"Origin": "http://localhost:5000"})
        assert "Access-Control-Allow-Origin" in resp.headers

    def test_cors_methods_presente(self, client_no_key):
        resp = client_no_key.get("/api/dashboard")
        assert "Access-Control-Allow-Methods" in resp.headers
