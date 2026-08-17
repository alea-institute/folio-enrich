from __future__ import annotations

import pytest

from app.config import settings


@pytest.mark.asyncio
async def test_settings_get_and_put_proposition_extraction_flag(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "proposition_extraction_enabled", False)

    response = await client.get("/settings")
    assert response.status_code == 200
    assert response.json()["proposition_extraction_enabled"] is False
    assert response.json()["proposition_taxonomy"] == {
        "Legal Proposition": (
            "https://folio.openlegalstandard.org/RNICD9MDcFQJJX6nxX11Vt"
        ),
        "Factual Statement": (
            "https://folio.openlegalstandard.org/RnKWv1E6U2Ssc5SRsG14NO"
        ),
        "Judicial Legal Conclusion": (
            "https://folio.openlegalstandard.org/RKTUVhpkOGaH53JFNJ4X4s"
        ),
        "Judicial Finding of Fact": (
            "https://folio.openlegalstandard.org/R7ZrWzdAOf6mXVtcQ49gWat"
        ),
        "stipulation": None,
        "arguendo assumption": None,
        "judicial notice": None,
        "cited-authority proposition": None,
        "hypothetical illustration": None,
        "policy proposition": None,
    }

    response = await client.put(
        "/settings", json={"proposition_extraction_enabled": True}
    )
    assert response.status_code == 200
    assert settings.proposition_extraction_enabled is True

    response = await client.get("/settings")
    assert response.json()["proposition_extraction_enabled"] is True
