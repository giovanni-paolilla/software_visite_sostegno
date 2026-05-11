"""Test completi per turni_visite.notifications — happy path con mock SMTP."""
import pytest
from unittest.mock import patch, MagicMock, ANY
from pathlib import Path

from turni_visite.notifications import send_notifications, _get_smtp_config, _get_email_fratelli


@pytest.fixture
def repo_smtp(tmp_path):
    from turni_visite.repository import JsonRepository
    r = JsonRepository(str(tmp_path / "notif_test.json"))
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_family("Fam A")
    r.associate("Mario Rossi", "Fam A")
    r.associate("Luigi Bianchi", "Fam A")
    r.set_setting("smtp_host", "smtp.test.com")
    r.set_setting("smtp_port", 587)
    r.set_setting("smtp_user", "user@test.com")
    r.set_setting("smtp_password", "secret")
    r.set_setting("smtp_from", "turni@test.com")
    r.set_setting("email_fratelli", {
        "Mario Rossi": "mario@test.com",
        "Luigi Bianchi": "luigi@test.com",
    })
    return r


def _solution():
    return {
        "by_month": {
            "2026-01": {
                "by_family": {"Fam A": ["Mario Rossi", "Luigi Bianchi"]},
                "by_brother": {
                    "Mario Rossi": ["Fam A"],
                    "Luigi Bianchi": ["Fam A"],
                },
            }
        }
    }


class TestGetSmtpConfig:
    def test_config_presente(self, repo_smtp):
        cfg = _get_smtp_config(repo_smtp)
        assert cfg["host"] == "smtp.test.com"
        assert cfg["port"] == 587
        assert cfg["user"] == "user@test.com"
        assert cfg["from"] == "turni@test.com"

    def test_config_assente(self, tmp_path):
        from turni_visite.repository import JsonRepository
        r = JsonRepository(str(tmp_path / "empty.json"))
        cfg = _get_smtp_config(r)
        assert cfg["host"] == ""
        assert cfg["user"] == ""


class TestGetEmailFratelli:
    def test_mappa_email(self, repo_smtp):
        emails = _get_email_fratelli(repo_smtp)
        assert emails["Mario Rossi"] == "mario@test.com"

    def test_mappa_vuota(self, tmp_path):
        from turni_visite.repository import JsonRepository
        r = JsonRepository(str(tmp_path / "empty.json"))
        assert _get_email_fratelli(r) == {}


class TestSendNotificationsHappyPath:
    @patch("turni_visite.notifications.smtplib.SMTP")
    def test_invia_a_tutti(self, mock_smtp_class, repo_smtp):
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        result = send_notifications(repo_smtp, ["2026-01"], _solution())

        assert set(result["inviati"]) == {"Luigi Bianchi", "Mario Rossi"}
        assert result["errori"] == []
        assert result["non_configurati"] == []
        assert mock_server.starttls.called
        assert mock_server.login.called
        assert mock_server.send_message.call_count == 2
        mock_server.quit.assert_called_once()

    @patch("turni_visite.notifications.smtplib.SMTP")
    def test_fratello_senza_email(self, mock_smtp_class, repo_smtp):
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server
        repo_smtp.set_setting("email_fratelli", {"Mario Rossi": "mario@test.com"})

        result = send_notifications(repo_smtp, ["2026-01"], _solution())

        assert "Mario Rossi" in result["inviati"]
        assert "Luigi Bianchi" in result["non_configurati"]
        assert mock_server.send_message.call_count == 1

    @patch("turni_visite.notifications.smtplib.SMTP")
    def test_con_allegato_pdf(self, mock_smtp_class, repo_smtp, tmp_path):
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server
        pdf = tmp_path / "turni.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake content")

        result = send_notifications(repo_smtp, ["2026-01"], _solution(), pdf_path=str(pdf))

        assert len(result["inviati"]) == 2
        call_args = mock_server.send_message.call_args_list[0]
        msg = call_args[0][0]
        payloads = msg.get_payload()
        assert len(payloads) == 2  # testo + pdf

    @patch("turni_visite.notifications.smtplib.SMTP")
    def test_pdf_inesistente_non_allegato(self, mock_smtp_class, repo_smtp):
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        result = send_notifications(
            repo_smtp, ["2026-01"], _solution(),
            pdf_path="/non/esiste/turni.pdf",
        )

        assert len(result["inviati"]) == 2
        call_args = mock_server.send_message.call_args_list[0]
        msg = call_args[0][0]
        payloads = msg.get_payload()
        assert len(payloads) == 1  # solo testo

    @patch("turni_visite.notifications.smtplib.SMTP")
    def test_errore_invio_singolo(self, mock_smtp_class, repo_smtp):
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server
        mock_server.send_message.side_effect = [Exception("SMTP error"), None]

        result = send_notifications(repo_smtp, ["2026-01"], _solution())

        assert len(result["errori"]) == 1
        assert len(result["inviati"]) == 1
        mock_server.quit.assert_called_once()


class TestSendNotificationsErrors:
    @patch("turni_visite.notifications.smtplib.SMTP")
    def test_connessione_fallita(self, mock_smtp_class, repo_smtp):
        mock_smtp_class.side_effect = Exception("Connection refused")

        result = send_notifications(repo_smtp, ["2026-01"], _solution())

        assert len(result["errori"]) == 1
        assert "Connessione SMTP fallita" in result["errori"][0]["errore"]
        assert result["inviati"] == []

    def test_smtp_non_configurato(self, tmp_path):
        from turni_visite.repository import JsonRepository
        r = JsonRepository(str(tmp_path / "no_smtp.json"))
        result = send_notifications(r, ["2026-01"], _solution())
        assert len(result["errori"]) == 1
        assert "SMTP non configurato" in result["errori"][0]["errore"]

    @patch("turni_visite.notifications.smtplib.SMTP")
    def test_solution_senza_assegnazioni(self, mock_smtp_class, repo_smtp):
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        result = send_notifications(repo_smtp, ["2026-01"], {"by_month": {}})

        assert result["inviati"] == []
        assert result["non_configurati"] == []
        mock_server.send_message.assert_not_called()

    @patch("turni_visite.notifications.smtplib.SMTP")
    def test_quit_fallisce_silenziosamente(self, mock_smtp_class, repo_smtp):
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server
        mock_server.quit.side_effect = Exception("already closed")

        result = send_notifications(repo_smtp, ["2026-01"], _solution())
        assert len(result["inviati"]) == 2
