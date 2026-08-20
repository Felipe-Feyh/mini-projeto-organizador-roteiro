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
    assert data["dias"] == 4


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


def test_create_itinerary_success(sample_travel_request):
    """Testa a criação de roteiro completa via grafo LangGraph."""
    response = client.post("/roteiro", json=sample_travel_request)
    assert response.status_code == 200
    data = response.json()
    assert data["destino"] == "Porto Alegre"
    assert data["periodo"] == "2026-09-01 a 2026-09-05"
    assert len(data["roteiro"]) == 4  # 4 dias
    assert "trace_id" in data
    assert data["trace_id"] != ""


def test_create_itinerary_invalid_dates():
    """Testa que datas inválidas retornam erro."""
    response = client.post(
        "/roteiro",
        json={
            "destino": "São Paulo",
            "data_inicio": "2026-09-10",
            "data_fim": "2026-09-05",
            "preferencias": ["cultura"],
            "orcamento": "moderado",
        },
    )
    assert response.status_code == 422


def test_create_itinerary_adversarial(adversarial_input):
    """Testa que input malicioso é bloqueado pelo grafo."""
    response = client.post("/roteiro", json=adversarial_input)
    assert response.status_code == 422
    data = response.json()
    assert "errors" in data["detail"]
