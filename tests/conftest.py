import pytest
from backend.config import settings
from backend.db import init_db
from backend.seed import seed


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "app_access_token", "")
    monkeypatch.setattr(settings, "demo_mode", True)
    init_db()
    seed()
    from backend.main import requests_by_ip

    requests_by_ip.clear()
