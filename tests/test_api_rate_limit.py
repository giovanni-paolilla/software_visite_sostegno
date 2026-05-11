"""Test per la classe _RateLimiter e la risposta 429 dell'API REST."""
import time
import pytest

try:
    from flask import Flask
    _FLASK_OK = True
except ImportError:
    _FLASK_OK = False

pytestmark = pytest.mark.skipif(not _FLASK_OK, reason="flask non installato")


# ---------------------------------------------------------------------------
# Test unitari della classe _RateLimiter (senza Flask)
# ---------------------------------------------------------------------------

class TestRateLimiterUnit:
    def test_permette_richieste_entro_limite(self):
        from turni_visite.api import _RateLimiter
        limiter = _RateLimiter(max_calls=3, period=60.0)
        assert limiter.allow("client1") is True
        assert limiter.allow("client1") is True
        assert limiter.allow("client1") is True

    def test_blocca_dopo_max_calls(self):
        from turni_visite.api import _RateLimiter
        limiter = _RateLimiter(max_calls=3, period=60.0)
        for _ in range(3):
            limiter.allow("client1")
        # La quarta deve essere bloccata
        assert limiter.allow("client1") is False

    def test_client_diversi_indipendenti(self):
        from turni_visite.api import _RateLimiter
        limiter = _RateLimiter(max_calls=2, period=60.0)
        limiter.allow("clientA")
        limiter.allow("clientA")
        # clientA e' esaurito, ma clientB e' indipendente
        assert limiter.allow("clientA") is False
        assert limiter.allow("clientB") is True

    def test_reset_dopo_finestra_temporale(self):
        """Dopo la finestra temporale le chiamate scadono e il limiter si resetta."""
        from turni_visite.api import _RateLimiter
        limiter = _RateLimiter(max_calls=2, period=0.05)  # finestra di 50ms
        limiter.allow("client1")
        limiter.allow("client1")
        assert limiter.allow("client1") is False
        # Attesa sufficiente a far scadere la finestra
        time.sleep(0.1)
        # Ora il limiter deve permettere nuovamente le chiamate
        assert limiter.allow("client1") is True

    def test_calls_clear_resetta_limiter(self):
        """Svuotare _calls (come fa conftest) resetta effettivamente il limiter."""
        from turni_visite.api import _RateLimiter
        limiter = _RateLimiter(max_calls=2, period=60.0)
        limiter.allow("client1")
        limiter.allow("client1")
        assert limiter.allow("client1") is False
        # Simula il reset del conftest
        limiter._calls.clear()
        assert limiter.allow("client1") is True


# ---------------------------------------------------------------------------
# Test di integrazione: 429 sul client Flask
# (disabilita autouse conftest per questo fixture — usa il limiter dedicato)
# ---------------------------------------------------------------------------

@pytest.fixture
def client_rate_limit(tmp_path, monkeypatch):
    """Client API con rate limiter generale impostato a 3 richieste."""
    import turni_visite.api as api_mod
    from turni_visite.api import _RateLimiter

    monkeypatch.setattr(api_mod, "_API_KEY", "")
    monkeypatch.setattr(api_mod, "_NO_AUTH", True)

    # Sostituisce il limiter generale con uno a 3 richieste per facilitare il test
    limiter_stretto = _RateLimiter(max_calls=3, period=60.0)
    monkeypatch.setattr(api_mod, "_limiter_general", limiter_stretto)

    data_file = tmp_path / "test_rate.json"
    app = api_mod.create_app(data_file=str(data_file))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestRateLimiter429:
    def test_dopo_n_richieste_rapide_ritorna_429(self, client_rate_limit):
        """Superato il limite, l'API risponde 429."""
        import turni_visite.api as api_mod
        # Forza il limiter a essere gia' pieno per l'IP di test
        limiter = api_mod._limiter_general
        for _ in range(3):
            limiter.allow("127.0.0.1")

        resp = client_rate_limit.get("/api/dashboard")
        assert resp.status_code == 429
        data = resp.get_json()
        assert "errore" in data

    def test_prima_del_limite_risponde_200(self, client_rate_limit):
        """Prima di esaurire il budget, le richieste vengono servite normalmente."""
        resp = client_rate_limit.get("/api/dashboard")
        assert resp.status_code == 200
