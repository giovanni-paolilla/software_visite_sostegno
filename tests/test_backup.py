"""Test per turni_visite.backup."""
import json
import pytest
from turni_visite.backup import create_backup, list_backups, restore_backup


@pytest.fixture
def data_file(tmp_path):
    f = tmp_path / "dati_turni.json"
    f.write_text(json.dumps({"test": True}), encoding="utf-8")
    return f


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    bd = tmp_path / "backups"
    monkeypatch.setattr("turni_visite.backup.BACKUP_DIR", bd)
    return bd


class TestCreateBackup:
    def test_crea_backup(self, data_file, backup_dir):
        path = create_backup(data_file)
        assert path is not None
        assert backup_dir.exists()
        assert len(list(backup_dir.glob("dati_turni_*.json"))) == 1

    def test_file_non_esiste_ritorna_none(self, tmp_path, backup_dir):
        path = create_backup(tmp_path / "non_esiste.json")
        assert path is None

    def test_rotazione(self, data_file, backup_dir, monkeypatch):
        monkeypatch.setattr("turni_visite.backup.MAX_BACKUPS", 3)
        for _ in range(5):
            create_backup(data_file)
        assert len(list(backup_dir.glob("dati_turni_*.json"))) <= 3


class TestListBackups:
    def test_lista_vuota(self, backup_dir):
        assert list_backups() == []

    def test_lista_con_backup(self, data_file, backup_dir):
        create_backup(data_file)
        result = list_backups()
        assert len(result) == 1
        assert "filename" in result[0]
        assert "size_kb" in result[0]


class TestRestoreBackup:
    def test_ripristina(self, data_file, backup_dir):
        # Modifica il file originale
        data_file.write_text(json.dumps({"modified": True}), encoding="utf-8")
        backup_path = create_backup(data_file)
        # Modifica di nuovo
        data_file.write_text(json.dumps({"modified_again": True}), encoding="utf-8")
        # Ripristina
        restore_backup(backup_path, data_file)
        data = json.loads(data_file.read_text(encoding="utf-8"))
        assert data.get("modified") is True

    def test_backup_non_trovato(self, tmp_path, backup_dir):
        with pytest.raises(FileNotFoundError):
            restore_backup(tmp_path / "non_esiste.json", tmp_path / "dest.json")
