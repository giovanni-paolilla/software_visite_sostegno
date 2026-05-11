"""Test per turni_visite.logging_cfg."""
import logging
import logging.handlers
import pytest
from turni_visite.logging_cfg import setup_logging, LOG_MAX_BYTES, LOG_BACKUP_COUNT
import turni_visite.config as config_mod


@pytest.fixture(autouse=True)
def isolate_root_logger():
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    for h in list(root.handlers):
        root.removeHandler(h)
    yield
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)
    for h in saved_handlers:
        root.addHandler(h)
    root.setLevel(saved_level)


class TestSetupLogging:
    def test_configura_rotating_handler(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config_mod, "PROJECT_DIR", tmp_path)
        setup_logging()
        root = logging.getLogger()
        rotating = [
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(rotating) == 1
        handler = rotating[0]
        assert handler.maxBytes == LOG_MAX_BYTES
        assert handler.backupCount == LOG_BACKUP_COUNT

    def test_idempotenza(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config_mod, "PROJECT_DIR", tmp_path)
        setup_logging()
        setup_logging()
        root = logging.getLogger()
        rotating = [
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(rotating) == 1
