"""Test per turni_visite.notifications."""
import pytest
from turni_visite.notifications import _build_message_for_brother


class TestBuildMessage:
    def test_messaggio_contiene_fratello(self):
        solution = {
            "by_month": {
                "2026-05": {
                    "by_brother": {"Mario": ["Fam A", "Fam B"]},
                    "by_family": {"Fam A": ["Mario"], "Fam B": ["Mario"]},
                },
            },
        }
        msg = _build_message_for_brother("Mario", ["2026-05"], solution, {"Fam A": 1, "Fam B": 1})
        assert "Caro Mario" in msg
        assert "Fam A" in msg
        assert "Fam B" in msg
        assert "2026-05" in msg

    def test_messaggio_senza_assegnazioni(self):
        solution = {
            "by_month": {
                "2026-05": {
                    "by_brother": {},
                    "by_family": {},
                },
            },
        }
        msg = _build_message_for_brother("Mario", ["2026-05"], solution, {})
        assert "Caro Mario" in msg

    def test_messaggio_piu_mesi(self):
        solution = {
            "by_month": {
                "2026-05": {
                    "by_brother": {"Mario": ["Fam A"]},
                    "by_family": {"Fam A": ["Mario"]},
                },
                "2026-06": {
                    "by_brother": {"Mario": ["Fam B"]},
                    "by_family": {"Fam B": ["Mario"]},
                },
            },
        }
        msg = _build_message_for_brother("Mario", ["2026-05", "2026-06"], solution, {"Fam A": 1, "Fam B": 1})
        assert "2026-05" in msg
        assert "2026-06" in msg


class TestSendNotificationsNoSmtp:
    def test_smtp_non_configurato(self, tmp_path):
        from turni_visite.repository import JsonRepository
        data_file = tmp_path / "test.json"
        repo = JsonRepository(data_file)
        from turni_visite.notifications import send_notifications
        result = send_notifications(repo, ["2026-05"], {"by_month": {}})
        assert result["errori"]
        assert "SMTP" in result["errori"][0]["errore"]
