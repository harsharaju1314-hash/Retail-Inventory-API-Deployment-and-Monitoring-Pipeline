from unittest.mock import patch


def test_health_check_healthy(client):
    """Verify that /health returns HTTP 200 and healthy status when DB is reachable."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "timestamp" in data
    assert data["version"] == "1.0.0"


def test_health_check_db_failure(client):
    """Verify that /health returns HTTP 503 and unhealthy status when DB is unreachable."""
    with patch("app.routes.check_db_connection", return_value=(False, "OperationalError: unable to open database file")):
        response = client.get("/health")
        assert response.status_code == 503

        data = response.get_json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert "OperationalError" in data["error"]
