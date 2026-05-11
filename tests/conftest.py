"""
Configurazione globale pytest.

Aggiunge la root del progetto al sys.path in modo che i test
possano importare turni_visite senza installazione del pacchetto,
e senza dover impostare PYTHONPATH manualmente.

Uso:
    cd <root-progetto>
    pytest
"""
import os
import sys
from pathlib import Path

# Disabilita l'autenticazione API per tutti i test (centralizzato qui
# per evitare duplicazione nei singoli moduli di test).
os.environ.setdefault("TURNI_API_NO_AUTH", "1")

import pytest

# La root del progetto e' due livelli sopra questo file (tests/conftest.py)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from turni_visite.repository import JsonRepository


@pytest.fixture(autouse=True)
def _reset_api_rate_limiters():
    """Resetta i rate limiter dell'API dopo ogni test per evitare 429.

    Il reset avviene *dopo* il test (post-yield) per non bloccare i test
    che vogliono verificare il comportamento del rate limiter stesso.
    Il try/except evita l'import di Flask nei test che non lo usano.
    """
    yield
    try:
        import turni_visite.api as api_mod
        api_mod._limiter_ottimizza._calls.clear()
        api_mod._limiter_general._calls.clear()
    except (ImportError, AttributeError):
        pass


@pytest.fixture
def data_file(tmp_path):
    """File dati temporaneo vuoto."""
    return tmp_path / "dati_turni.json"


@pytest.fixture
def repo(data_file):
    """Repository vuoto su filesystem temporaneo."""
    return JsonRepository(str(data_file))


@pytest.fixture
def repo_base(data_file):
    """Repository con dati minimi: 2 fratelli, 1 famiglia, 1 associazione."""
    r = JsonRepository(str(data_file))
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_family("Famiglia Verdi")
    r.associate("Mario Rossi", "Famiglia Verdi")
    r.associate("Luigi Bianchi", "Famiglia Verdi")
    return r
