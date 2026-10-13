import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from src.utils import credentials, settings


@pytest.fixture
def vault(monkeypatch):
    data = {}
    backend = SimpleNamespace(set_password=lambda service, key, value: data.__setitem__(key, value),
                              get_password=lambda service, key: data.get(key),
                              delete_password=lambda service, key: data.pop(key, None))
    monkeypatch.setattr(credentials, "get_backend", lambda: backend)
    return data, backend


def test_protection_roundtrip_reuse_and_deletion(vault, monkeypatch, tmp_path):
    data, _ = vault
    path = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "SETTINGS_FILE", str(path))
    monkeypatch.setattr(settings, "_settings", {"network_sensors": [], "target_fps": 30})
    sources = [{"id": "room", "protocol": "mqtt", "password": "dummy-password", "token": "dummy-token"}]
    settings.set_setting("network_sensors", sources)
    persisted = json.loads(path.read_text())
    assert "dummy-password" not in path.read_text() and "dummy-token" not in path.read_text()
    assert persisted["target_fps"] == 30
    assert len(data) == 2
    restored = settings.get_setting("network_sensors")
    assert restored[0]["password"] == "dummy-password" and restored[0]["token"] == "dummy-token"
    settings.set_setting("network_sensors", restored)
    assert len(data) == 2
    settings.set_setting("network_sensors", [])
    assert not data


def test_failed_file_save_preserves_old_settings_and_credentials(vault, monkeypatch, tmp_path):
    data, _ = vault
    monkeypatch.setattr(settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    old = {"network_sensors": [{"id": "room", "password": "old-password"}]}
    monkeypatch.setattr(settings, "_settings", old)
    monkeypatch.setattr(settings, "write_json_atomic", Mock(side_effect=OSError("cannot write")))
    with pytest.raises(RuntimeError, match="Previous sensor configuration was preserved"):
        settings.set_setting("network_sensors", [{"id": "room", "password": "new-password"}])
    assert settings._settings is old
    assert not data


def test_partial_vault_failure_rolls_back_new_entries(vault):
    data, backend = vault
    def save(service, key, value):
        if value == "new-token":
            raise OSError("store denied")
        data[key] = value
    backend.set_password = save
    with pytest.raises(RuntimeError):
        credentials.protect_sources([{"password": "new", "token": "new-token"}])
    assert not data


def test_missing_credential_is_not_silently_cleared(vault):
    with pytest.raises(RuntimeError, match="missing"):
        credentials.resolve_sources([{"id": "room", "password_ref": "absent"}])


def test_plaintext_backend_is_rejected(monkeypatch):
    import keyring
    backend = type("Plaintext", (), {"priority": 100})()
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    with pytest.raises(RuntimeError, match="No unlocked OS credential store"):
        credentials.get_backend()
