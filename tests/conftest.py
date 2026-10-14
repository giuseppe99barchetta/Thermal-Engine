import pytest
from src.utils import settings


@pytest.fixture(autouse=True)
def isolated_settings_storage(monkeypatch, tmp_path):
    """Tests must never write the developer's source or installed preferences."""
    monkeypatch.setattr(settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
