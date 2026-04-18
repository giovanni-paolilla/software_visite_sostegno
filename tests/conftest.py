"""
Configurazione globale pytest.

Aggiunge la root del progetto al sys.path in modo che i test
possano importare turni_visite senza installazione del pacchetto,
e senza dover impostare PYTHONPATH manualmente.

Uso:
    cd <root-progetto>
    pytest
"""
import sys
from pathlib import Path

# La root del progetto e' due livelli sopra questo file (tests/conftest.py)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
