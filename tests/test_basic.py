"""Testes básicos para validação inicial do projeto."""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_check():
    """Testa se o endpoint de saúde retorna corretamente."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_validate_request(sample_travel_request):
    """Testa validação de request."""
    response = client.post("/roteiro/validar", json=sample_travel_request)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["destino"] == "Porto Alegre"


def test_invalid_request_empty_destino():
    """Testa que destino vazio é rejeitado."""
    response = client.post(
        "/roteiro/validar",
        json={
            "destino": "",
            "data_inicio": "2026-09-01",
            "data_fim": "2026-09-05",
        },
    )
    assert response.status_code == 422
