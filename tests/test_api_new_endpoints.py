"""Test completi per i nuovi endpoint API: affinita, bozza, sostituzione,
stato esecuzione e export WhatsApp."""
import json
import pytest

try:
    from flask import Flask
    _FLASK_OK = True
except ImportError:
    _FLASK_OK = False

pytestmark = pytest.mark.skipif(not _FLASK_OK, reason="flask non installato")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type="application/json")


def _patch_json(client, url, data):
    return client.patch(url, data=json.dumps(data), content_type="application/json")


def _delete_json(client, url, data):
    return client.delete(url, data=json.dumps(data), content_type="application/json")


def _setup_base(client):
    """Crea fratelli, famiglie e associazioni di base tramite API."""
    _post_json(client, "/api/fratelli", {"nome": "Mario Rossi", "capacita": 3})
    _post_json(client, "/api/fratelli", {"nome": "Luigi Bianchi", "capacita": 3})
    _post_json(client, "/api/fratelli", {"nome": "Carla Neri", "capacita": 3})
    _post_json(client, "/api/famiglie", {"nome": "Famiglia Verdi", "frequenza": 2})
    _post_json(client, "/api/famiglie", {"nome": "Famiglia Blu", "frequenza": 1})
    _post_json(client, "/api/associazioni", {"fratello": "Mario Rossi", "famiglia": "Famiglia Verdi"})
    _post_json(client, "/api/associazioni", {"fratello": "Luigi Bianchi", "famiglia": "Famiglia Verdi"})
    _post_json(client, "/api/associazioni", {"fratello": "Carla Neri", "famiglia": "Famiglia Blu"})
    _post_json(client, "/api/associazioni", {"fratello": "Mario Rossi", "famiglia": "Famiglia Blu"})


def _make_data_file(tmp_path, extra=None):
    """Build a JSON data file with base entities and optional extra data merged in."""
    base = {
        "schema_version": 3,
        "fratelli": ["Carla Neri", "Luigi Bianchi", "Mario Rossi"],
        "famiglie": ["Famiglia Blu", "Famiglia Verdi"],
        "associazioni": {
            "Famiglia Verdi": ["Luigi Bianchi", "Mario Rossi"],
            "Famiglia Blu": ["Carla Neri", "Mario Rossi"],
        },
        "frequenze": {"Famiglia Verdi": 2, "Famiglia Blu": 1},
        "capacita": {"Mario Rossi": 3, "Luigi Bianchi": 3, "Carla Neri": 3},
        "settings": {"cooldown_mesi": 3},
        "storico_turni": [],
        "indisponibilita": {},
        "vincoli_personalizzati": [],
        "week_templates": {},
        "audit_log": [],
        "affinita": [],
        "bozza_turni": None,
    }
    if extra:
        base.update(extra)
    data_file = tmp_path / "test_data.json"
    data_file.write_text(json.dumps(base, indent=4, ensure_ascii=False), encoding="utf-8")
    return str(data_file)


def _make_client(data_file):
    """Create a Flask test client bound to the given data file."""
    from turni_visite.api import create_app
    app = create_app(data_file=data_file)
    app.config["TESTING"] = True
    return app.test_client()


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    from turni_visite.api import create_app
    data_file = tmp_path / "test_data.json"
    app = create_app(data_file=str(data_file))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def base_client(tmp_path):
    """Client with base entities already loaded from pre-built file."""
    data_file = _make_data_file(tmp_path)
    from turni_visite.api import create_app
    app = create_app(data_file=data_file)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ======================================================================
# 1. Affinita (10 tests)
# ======================================================================

class TestAffinita:
    def test_get_affinita_empty(self, client):
        resp = client.get("/api/affinita")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_post_affinita_creates_entry(self, base_client):
        resp = _post_json(base_client, "/api/affinita", {
            "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "peso": 5,
        })
        assert resp.status_code == 201
        assert resp.get_json()["ok"] is True

        data = base_client.get("/api/affinita").get_json()
        assert len(data) == 1
        assert data[0]["famiglia"] == "Famiglia Verdi"
        assert data[0]["fratello"] == "Mario Rossi"
        assert data[0]["peso"] == 5

    def test_post_affinita_updates_existing(self, base_client):
        _post_json(base_client, "/api/affinita", {
            "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "peso": 3,
        })
        resp = _post_json(base_client, "/api/affinita", {
            "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "peso": -2,
        })
        assert resp.status_code == 201
        data = base_client.get("/api/affinita").get_json()
        assert len(data) == 1
        assert data[0]["peso"] == -2

    def test_post_affinita_invalid_peso_too_high(self, base_client):
        resp = _post_json(base_client, "/api/affinita", {
            "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "peso": 99,
        })
        assert resp.status_code == 400
        assert "errore" in resp.get_json()

    def test_post_affinita_invalid_peso_too_low(self, base_client):
        resp = _post_json(base_client, "/api/affinita", {
            "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "peso": -99,
        })
        assert resp.status_code == 400

    def test_post_affinita_missing_fields(self, client):
        resp = _post_json(client, "/api/affinita", {"famiglia": "X"})
        assert resp.status_code == 400
        assert "Campi obbligatori mancanti" in resp.get_json()["errore"]

    def test_post_affinita_empty_body(self, client):
        resp = client.post("/api/affinita", data="not json",
                           content_type="application/json")
        assert resp.status_code == 400

    def test_delete_affinita_removes_entry(self, base_client):
        _post_json(base_client, "/api/affinita", {
            "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "peso": 5,
        })
        resp = _delete_json(base_client, "/api/affinita", {
            "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi",
        })
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        assert base_client.get("/api/affinita").get_json() == []

    def test_delete_affinita_not_found(self, base_client):
        resp = _delete_json(base_client, "/api/affinita", {
            "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi",
        })
        assert resp.status_code == 404
        assert "errore" in resp.get_json()

    def test_post_affinita_nonexistent_fratello(self, base_client):
        resp = _post_json(base_client, "/api/affinita", {
            "famiglia": "Famiglia Verdi", "fratello": "Fantasma", "peso": 1,
        })
        assert resp.status_code == 400


# ======================================================================
# 2. Bozza turni (12 tests)
# ======================================================================

def _bozza_solution(mese, family, brothers):
    """Build a minimal solution dict suitable for save_bozza."""
    return {
        "by_month": {
            mese: {
                "by_family": {family: brothers},
                "by_brother": {b: [family] for b in brothers},
            }
        }
    }


def _bozza_data(mesi, assegnazioni):
    """Build a bozza_turni dict as stored in JSON."""
    return {
        "mesi": mesi,
        "created_at": "2026-01-01T00:00:00",
        "assegnazioni": assegnazioni,
    }


class TestBozza:
    def test_get_bozza_returns_null_when_empty(self, client):
        # L'API ritorna 404 quando non c'e' bozza attiva
        resp = client.get("/api/bozza")
        assert resp.status_code == 404
        assert "errore" in resp.get_json()

    def test_get_bozza_returns_draft_after_save(self, tmp_path):
        bozza = _bozza_data(["2026-03"], [
            {"mese": "2026-03", "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi",
             "slot": 1, "stato": "proposto"},
            {"mese": "2026-03", "famiglia": "Famiglia Verdi", "fratello": "Luigi Bianchi",
             "slot": 2, "stato": "proposto"},
        ])
        data_file = _make_data_file(tmp_path, {"bozza_turni": bozza})
        client = _make_client(data_file)

        with client:
            resp = client.get("/api/bozza")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data is not None
            assert "2026-03" in data["mesi"]
            assert len(data["assegnazioni"]) == 2

    def test_delete_bozza_clears_draft(self, tmp_path):
        bozza = _bozza_data(["2026-03"], [
            {"mese": "2026-03", "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi",
             "slot": 1, "stato": "proposto"},
        ])
        data_file = _make_data_file(tmp_path, {"bozza_turni": bozza})
        client = _make_client(data_file)

        with client:
            resp = client.delete("/api/bozza")
            assert resp.status_code == 200
            assert resp.get_json()["ok"] is True
            # Dopo DELETE, GET ritorna 404 (nessuna bozza attiva)
            resp = client.get("/api/bozza")
            assert resp.status_code == 404

    def test_patch_bozza_stato_updates_assignment(self, tmp_path):
        bozza = _bozza_data(["2026-03"], [
            {"mese": "2026-03", "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi",
             "slot": 1, "stato": "proposto"},
        ])
        data_file = _make_data_file(tmp_path, {"bozza_turni": bozza})
        client = _make_client(data_file)

        with client:
            resp = _patch_json(client, "/api/bozza/stato", {
                "mese": "2026-03", "famiglia": "Famiglia Verdi", "slot": 1,
                "stato": "accettato",
            })
            assert resp.status_code == 200
            assert resp.get_json()["ok"] is True

            bozza_data = client.get("/api/bozza").get_json()
            assert bozza_data["assegnazioni"][0]["stato"] == "accettato"

    def test_patch_bozza_stato_invalid_state(self, tmp_path):
        bozza = _bozza_data(["2026-03"], [
            {"mese": "2026-03", "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi",
             "slot": 1, "stato": "proposto"},
        ])
        data_file = _make_data_file(tmp_path, {"bozza_turni": bozza})
        client = _make_client(data_file)

        with client:
            resp = _patch_json(client, "/api/bozza/stato", {
                "mese": "2026-03", "famiglia": "Famiglia Verdi", "slot": 1,
                "stato": "invalido",
            })
            assert resp.status_code == 400
            assert "errore" in resp.get_json()

    def test_patch_bozza_stato_missing_fields(self, client):
        resp = _patch_json(client, "/api/bozza/stato", {"mese": "2026-03"})
        assert resp.status_code == 400
        assert "Campi obbligatori mancanti" in resp.get_json()["errore"]

    def test_patch_bozza_stato_no_bozza(self, client):
        resp = _patch_json(client, "/api/bozza/stato", {
            "mese": "2026-03", "famiglia": "X", "slot": 1, "stato": "accettato",
        })
        assert resp.status_code == 400

    def test_conferma_bozza_moves_accepted_to_storico(self, tmp_path):
        bozza = _bozza_data(["2026-04"], [
            {"mese": "2026-04", "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi",
             "slot": 1, "stato": "accettato"},
            {"mese": "2026-04", "famiglia": "Famiglia Verdi", "fratello": "Luigi Bianchi",
             "slot": 2, "stato": "accettato"},
        ])
        data_file = _make_data_file(tmp_path, {"bozza_turni": bozza})
        client = _make_client(data_file)

        with client:
            resp = _post_json(client, "/api/bozza/conferma", {})
            assert resp.status_code == 200
            data = resp.get_json()
            # L'API ritorna direttamente il risultato del repo: {"salvati": [...], "saltati": [...]}
            assert "2026-04" in data["salvati"]

            storico = client.get("/api/storico").get_json()
            mesi_storico = [r["mese"] for r in storico]
            assert "2026-04" in mesi_storico

    def test_conferma_bozza_clears_draft(self, tmp_path):
        bozza = _bozza_data(["2026-05"], [
            {"mese": "2026-05", "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi",
             "slot": 1, "stato": "accettato"},
        ])
        data_file = _make_data_file(tmp_path, {"bozza_turni": bozza})
        client = _make_client(data_file)

        with client:
            _post_json(client, "/api/bozza/conferma", {})
            # Dopo conferma, GET /api/bozza ritorna 404 (nessuna bozza attiva)
            resp = client.get("/api/bozza")
            assert resp.status_code == 404

    def test_conferma_bozza_discards_rejected(self, tmp_path):
        bozza = _bozza_data(["2026-06"], [
            {"mese": "2026-06", "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi",
             "slot": 1, "stato": "accettato"},
            {"mese": "2026-06", "famiglia": "Famiglia Verdi", "fratello": "Luigi Bianchi",
             "slot": 2, "stato": "rifiutato"},
        ])
        data_file = _make_data_file(tmp_path, {"bozza_turni": bozza})
        client = _make_client(data_file)

        with client:
            resp = _post_json(client, "/api/bozza/conferma", {})
            assert resp.status_code == 200

            storico = client.get("/api/storico").get_json()
            mese_rec = next(r for r in storico if r["mese"] == "2026-06")
            assert len(mese_rec["assegnazioni"]) == 1
            assert mese_rec["assegnazioni"][0]["fratello"] == "Mario Rossi"

    def test_conferma_bozza_no_draft_returns_400(self, client):
        resp = _post_json(client, "/api/bozza/conferma", {})
        assert resp.status_code == 400
        assert "errore" in resp.get_json()

    def test_patch_bozza_stato_assignment_not_found(self, tmp_path):
        bozza = _bozza_data(["2026-03"], [
            {"mese": "2026-03", "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi",
             "slot": 1, "stato": "proposto"},
        ])
        data_file = _make_data_file(tmp_path, {"bozza_turni": bozza})
        client = _make_client(data_file)

        with client:
            resp = _patch_json(client, "/api/bozza/stato", {
                "mese": "2026-03", "famiglia": "Famiglia Verdi", "slot": 99,
                "stato": "accettato",
            })
            assert resp.status_code == 400

    def test_conferma_bozza_all_rejected_saves_nothing(self, tmp_path):
        bozza = _bozza_data(["2026-07"], [
            {"mese": "2026-07", "famiglia": "Famiglia Verdi", "fratello": "Mario Rossi",
             "slot": 1, "stato": "rifiutato"},
        ])
        data_file = _make_data_file(tmp_path, {"bozza_turni": bozza})
        client = _make_client(data_file)

        with client:
            resp = _post_json(client, "/api/bozza/conferma", {})
            assert resp.status_code == 200
            data = resp.get_json()
            # L'API ritorna direttamente il risultato del repo: {"salvati": [...], "saltati": [...]}
            assert data["salvati"] == []

            storico = client.get("/api/storico").get_json()
            assert len(storico) == 0


# ======================================================================
# 3. Sostituzione (9 tests)
# ======================================================================

def _storico_rec(mese, assegnazioni):
    """Build a storico record as stored in JSON."""
    return {
        "mese": mese,
        "created_at": "2026-01-01T00:00:00",
        "confirmed_at": "2026-01-01T00:00:00",
        "assegnazioni": assegnazioni,
    }


class TestSostituzione:
    def _make_storico_client(self, tmp_path, mese="2026-03"):
        storico = [_storico_rec(mese, [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 1},
            {"famiglia": "Famiglia Blu", "fratello": "Luigi Bianchi", "slot": 1},
            {"famiglia": "Famiglia Blu", "fratello": "Carla Neri", "slot": 2},
        ])]
        data_file = _make_data_file(tmp_path, {"storico_turni": storico})
        return _make_client(data_file)

    def test_sostituzione_finds_candidates(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            resp = _post_json(client, "/api/sostituzione", {
                "mese": "2026-03", "fratello_malato": "Mario Rossi",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert isinstance(data, list)
            fratelli_candidati = [c["fratello"] for c in data]
            assert "Luigi Bianchi" in fratelli_candidati

    def test_sostituzione_no_candidates_unknown_brother(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            # L'API ritorna 404 se il fratello malato non esiste nel repository
            resp = _post_json(client, "/api/sostituzione", {
                "mese": "2026-03", "fratello_malato": "Fantasma Non Esistente",
            })
            assert resp.status_code == 404
            assert "errore" in resp.get_json()

    def test_sostituzione_no_storico_for_month(self, base_client):
        resp = _post_json(base_client, "/api/sostituzione", {
            "mese": "2099-12", "fratello_malato": "Mario Rossi",
        })
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_sostituzione_with_famiglia_filter(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            resp = _post_json(client, "/api/sostituzione", {
                "mese": "2026-03", "fratello_malato": "Mario Rossi",
                "famiglia": "Famiglia Verdi",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert isinstance(data, list)
            for c in data:
                assert c["famiglia"] == "Famiglia Verdi"

    def test_sostituzione_missing_fields(self, client):
        resp = _post_json(client, "/api/sostituzione", {"mese": "2026-03"})
        assert resp.status_code == 400
        assert "Campi obbligatori mancanti" in resp.get_json()["errore"]

    def test_sostituzione_empty_body(self, client):
        resp = _post_json(client, "/api/sostituzione", {})
        assert resp.status_code == 400

    def test_applica_sostituzione_updates_storico(self, tmp_path):
        # Mario Rossi è a slot=1 nei dati di _make_storico_client
        client = self._make_storico_client(tmp_path)
        with client:
            resp = _post_json(client, "/api/sostituzione/applica", {
                "mese": "2026-03",
                "famiglia": "Famiglia Verdi",
                "slot": 1,
                "vecchio_fratello": "Mario Rossi",
                "nuovo_fratello": "Luigi Bianchi",
            })
            assert resp.status_code == 200
            assert resp.get_json()["ok"] is True

            storico = client.get("/api/storico").get_json()
            mese_rec = next(r for r in storico if r["mese"] == "2026-03")
            slot1 = next(a for a in mese_rec["assegnazioni"]
                         if a["famiglia"] == "Famiglia Verdi" and a["slot"] == 1)
            assert slot1["fratello"] == "Luigi Bianchi"

    def test_applica_sostituzione_not_found(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            resp = _post_json(client, "/api/sostituzione/applica", {
                "mese": "2026-03",
                "famiglia": "Famiglia Verdi",
                "slot": 99,
                "vecchio_fratello": "Mario Rossi",
                "nuovo_fratello": "Luigi Bianchi",
            })
            assert resp.status_code == 400

    def test_applica_sostituzione_missing_fields(self, client):
        resp = _post_json(client, "/api/sostituzione/applica", {
            "mese": "2026-03", "famiglia": "X",
        })
        assert resp.status_code == 400
        assert "Campi obbligatori mancanti" in resp.get_json()["errore"]

    def test_applica_sostituzione_nuovo_fratello_inesistente(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            resp = _post_json(client, "/api/sostituzione/applica", {
                "mese": "2026-03",
                "famiglia": "Famiglia Verdi",
                "slot": 0,
                "vecchio_fratello": "Mario Rossi",
                "nuovo_fratello": "Fantasma Ignoto",
            })
            assert resp.status_code == 400


# ======================================================================
# 4. Stato esecuzione (11 tests)
# ======================================================================

class TestStatoEsecuzione:
    def _make_storico_client(self, tmp_path, mese="2026-03"):
        storico = [_storico_rec(mese, [
            {"famiglia": "Famiglia Verdi", "fratello": "Mario Rossi", "slot": 0},
            {"famiglia": "Famiglia Verdi", "fratello": "Luigi Bianchi", "slot": 1},
            {"famiglia": "Famiglia Blu", "fratello": "Carla Neri", "slot": 0},
        ])]
        data_file = _make_data_file(tmp_path, {"storico_turni": storico})
        return _make_client(data_file)

    def test_set_completato(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            resp = _patch_json(client, "/api/storico/2026-03/esecuzione", {
                "famiglia": "Famiglia Verdi", "slot": 0, "stato": "completato",
            })
            assert resp.status_code == 200
            assert resp.get_json()["ok"] is True

    def test_set_annullato(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            resp = _patch_json(client, "/api/storico/2026-03/esecuzione", {
                "famiglia": "Famiglia Blu", "slot": 0, "stato": "annullato",
            })
            assert resp.status_code == 200
            assert resp.get_json()["ok"] is True

    def test_set_pianificato_after_completato(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            _patch_json(client, "/api/storico/2026-03/esecuzione", {
                "famiglia": "Famiglia Verdi", "slot": 0, "stato": "completato",
            })
            resp = _patch_json(client, "/api/storico/2026-03/esecuzione", {
                "famiglia": "Famiglia Verdi", "slot": 0, "stato": "pianificato",
            })
            assert resp.status_code == 200

    def test_invalid_stato_returns_400(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            resp = _patch_json(client, "/api/storico/2026-03/esecuzione", {
                "famiglia": "Famiglia Verdi", "slot": 0, "stato": "sconosciuto",
            })
            assert resp.status_code == 400
            assert "errore" in resp.get_json()

    def test_not_found_slot_returns_400(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            resp = _patch_json(client, "/api/storico/2026-03/esecuzione", {
                "famiglia": "Famiglia Verdi", "slot": 99, "stato": "completato",
            })
            assert resp.status_code == 400

    def test_missing_fields_returns_400(self, client):
        resp = _patch_json(client, "/api/storico/2026-03/esecuzione", {
            "famiglia": "X",
        })
        assert resp.status_code == 400
        assert "Campi obbligatori mancanti" in resp.get_json()["errore"]

    def test_nonexistent_mese_returns_400(self, base_client):
        resp = _patch_json(base_client, "/api/storico/2099-12/esecuzione", {
            "famiglia": "Famiglia Verdi", "slot": 0, "stato": "completato",
        })
        assert resp.status_code == 400

    def test_stats_completamento_returns_tasso(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            resp = client.get("/api/stats/completamento")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "totale" in data
            assert "completate" in data
            assert "annullate" in data
            assert "pianificate" in data
            assert "tasso_pct" in data
            assert data["totale"] == 3
            assert data["completate"] == 0
            assert data["tasso_pct"] == 0.0

    def test_stats_completamento_after_updates(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            _patch_json(client, "/api/storico/2026-03/esecuzione", {
                "famiglia": "Famiglia Verdi", "slot": 0, "stato": "completato",
            })
            _patch_json(client, "/api/storico/2026-03/esecuzione", {
                "famiglia": "Famiglia Verdi", "slot": 1, "stato": "completato",
            })

            resp = client.get("/api/stats/completamento")
            data = resp.get_json()
            assert data["totale"] == 3
            assert data["completate"] == 2
            assert data["tasso_pct"] == pytest.approx(66.7, abs=0.1)

    def test_stats_completamento_empty_storico(self, client):
        resp = client.get("/api/stats/completamento")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["totale"] == 0
        assert data["tasso_pct"] == 0.0

    def test_stats_completamento_with_annullato(self, tmp_path):
        client = self._make_storico_client(tmp_path)
        with client:
            _patch_json(client, "/api/storico/2026-03/esecuzione", {
                "famiglia": "Famiglia Verdi", "slot": 0, "stato": "completato",
            })
            _patch_json(client, "/api/storico/2026-03/esecuzione", {
                "famiglia": "Famiglia Blu", "slot": 0, "stato": "annullato",
            })

            resp = client.get("/api/stats/completamento")
            data = resp.get_json()
            assert data["totale"] == 3
            assert data["completate"] == 1
            assert data["annullate"] == 1
            assert data["pianificate"] == 1


# ======================================================================
# 5. WhatsApp export (8 tests)
# ======================================================================

class TestWhatsAppExport:
    def test_export_returns_text(self, client):
        solution = {
            "by_month": {
                "2026-03": {
                    "by_family": {
                        "Famiglia Verdi": ["Mario Rossi", "Luigi Bianchi"],
                    },
                    "by_brother": {
                        "Mario Rossi": ["Famiglia Verdi"],
                        "Luigi Bianchi": ["Famiglia Verdi"],
                    },
                }
            }
        }
        resp = _post_json(client, "/api/export/whatsapp", {
            "mesi": ["2026-03"],
            "solution": solution,
            "frequenze": {"Famiglia Verdi": 2},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "text" in data
        text = data["text"]
        assert "VISITE DI SOSTEGNO" in text
        assert "Marzo 2026" in text
        assert "Famiglia Verdi" in text
        assert "Mario Rossi" in text

    def test_export_missing_solution(self, client):
        resp = _post_json(client, "/api/export/whatsapp", {"mesi": ["2026-03"]})
        assert resp.status_code == 400
        assert "Campi obbligatori mancanti" in resp.get_json()["errore"]

    def test_export_missing_mesi(self, client):
        resp = _post_json(client, "/api/export/whatsapp", {
            "solution": {"by_month": {}},
        })
        assert resp.status_code == 400

    def test_export_invalid_mesi_format(self, client):
        solution = {"by_month": {"x": {}}}
        resp = _post_json(client, "/api/export/whatsapp", {
            "mesi": ["not-a-date"],
            "solution": solution,
        })
        assert resp.status_code == 400
        assert "Formato mese non valido" in resp.get_json()["errore"]

    def test_export_mesi_not_list(self, client):
        solution = {"by_month": {}}
        resp = _post_json(client, "/api/export/whatsapp", {
            "mesi": "2026-03",
            "solution": solution,
        })
        assert resp.status_code == 400

    def test_export_empty_mesi_list(self, client):
        resp = _post_json(client, "/api/export/whatsapp", {
            "mesi": [],
            "solution": {"by_month": {}},
        })
        assert resp.status_code == 400

    def test_export_solution_with_no_matching_months(self, client):
        """Solution exists but has no data for the requested months."""
        solution = {"by_month": {}}
        resp = _post_json(client, "/api/export/whatsapp", {
            "mesi": ["2026-03"],
            "solution": solution,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "text" in data
        assert isinstance(data["text"], str)

    def test_export_no_json_body(self, client):
        resp = client.post("/api/export/whatsapp",
                           data="not json", content_type="application/json")
        assert resp.status_code == 400

    def test_export_multiple_months(self, client):
        solution = {
            "by_month": {
                "2026-03": {
                    "by_family": {"Fam A": ["Fr A"]},
                    "by_brother": {"Fr A": ["Fam A"]},
                },
                "2026-04": {
                    "by_family": {"Fam B": ["Fr B"]},
                    "by_brother": {"Fr B": ["Fam B"]},
                },
            }
        }
        resp = _post_json(client, "/api/export/whatsapp", {
            "mesi": ["2026-03", "2026-04"],
            "solution": solution,
            "frequenze": {"Fam A": 1, "Fam B": 1},
        })
        assert resp.status_code == 200
        text = resp.get_json()["text"]
        assert "Marzo 2026" in text
        assert "Aprile 2026" in text
