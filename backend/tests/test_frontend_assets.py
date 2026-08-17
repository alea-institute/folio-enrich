from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_vendored_elk_bundle_is_served_from_frontend_static_mount():
    response = client.get("/static/vendor/elkjs-0.11.1/elk.bundled.js")

    assert response.status_code == 200
    assert "ELK" in response.text
