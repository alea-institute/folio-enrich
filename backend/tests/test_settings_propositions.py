from __future__ import annotations

import pytest

from app.config import settings


@pytest.mark.asyncio
async def test_settings_get_and_put_proposition_extraction_flag(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "proposition_extraction_enabled", False)

    response = await client.get("/settings")
    assert response.status_code == 200
    assert response.json()["proposition_extraction_enabled"] is False

    response = await client.put(
        "/settings", json={"proposition_extraction_enabled": True}
    )
    assert response.status_code == 200
    assert settings.proposition_extraction_enabled is True

    response = await client.get("/settings")
    assert response.json()["proposition_extraction_enabled"] is True
