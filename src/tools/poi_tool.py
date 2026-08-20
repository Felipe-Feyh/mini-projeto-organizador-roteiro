"""Tool de pontos de interesse turístico.

Busca locais relevantes para o destino baseado nas preferências
do viajante. Usa dados estruturados com validação.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.agent.state import PointOfInterest


class POIToolInput(BaseModel):
    """Schema de entrada validado para a tool de POIs."""

    cidade: str = Field(..., min_length=2, max_length=100)
    preferencias: list[str] = Field(default_factory=list)
    orcamento: str = Field(default="moderado")

    @field_validator("preferencias")
    @classmethod
    def validate_preferencias(cls, v: list[str]) -> list[str]:
        """Valida que preferências são categorias permitidas."""
        categorias_validas = {
            "cultura", "gastronomia", "aventura", "compras",
            "relaxamento", "natureza", "vida_noturna", "historia",
        }
        return [p for p in v if p.lower() in categorias_validas]


# Base de dados simulada de POIs por categoria e cidade
# Em produção, integraria com Google Places, TripAdvisor ou similar
_POIS_DATABASE: dict[str, list[dict]] = {
    "cultura": [
        {"nome": "Museu de Arte", "descricao": "Acervo cultural da região", "avaliacao": 4.5, "horario": "09h-18h"},
        {"nome": "Teatro Municipal", "descricao": "Espetáculos e shows locais", "avaliacao": 4.3, "horario": "14h-22h"},
        {"nome": "Centro Histórico", "descricao": "Patrimônio arquitetônico preservado", "avaliacao": 4.7, "horario": "Livre"},
    ],
    "gastronomia": [
        {"nome": "Restaurante Regional", "descricao": "Culinária típica local", "avaliacao": 4.6, "horario": "11h-23h"},
        {"nome": "Mercado Municipal", "descricao": "Produtos frescos e iguarias", "avaliacao": 4.4, "horario": "07h-18h"},
        {"nome": "Café Artesanal", "descricao": "Grãos selecionados e doces", "avaliacao": 4.2, "horario": "08h-20h"},
    ],
    "aventura": [
        {"nome": "Trilha Ecológica", "descricao": "Percurso em meio à natureza", "avaliacao": 4.8, "horario": "06h-17h"},
        {"nome": "Parque de Aventura", "descricao": "Tirolesa, rapel e escalada", "avaliacao": 4.1, "horario": "09h-17h"},
        {"nome": "Mirante Panorâmico", "descricao": "Vista 360° da cidade", "avaliacao": 4.9, "horario": "Livre"},
    ],
    "compras": [
        {"nome": "Shopping Center", "descricao": "Lojas variadas e praça de alimentação", "avaliacao": 4.0, "horario": "10h-22h"},
        {"nome": "Feira de Artesanato", "descricao": "Produtos artesanais locais", "avaliacao": 4.5, "horario": "08h-14h (sábados)"},
    ],
    "relaxamento": [
        {"nome": "Spa & Wellness", "descricao": "Massagens e tratamentos", "avaliacao": 4.7, "horario": "09h-21h"},
        {"nome": "Parque Urbano", "descricao": "Área verde para descanso", "avaliacao": 4.3, "horario": "06h-22h"},
        {"nome": "Praia/Orla", "descricao": "Área de banho e lazer", "avaliacao": 4.6, "horario": "Livre"},
    ],
    "natureza": [
        {"nome": "Jardim Botânico", "descricao": "Flora nativa e exótica", "avaliacao": 4.5, "horario": "08h-17h"},
        {"nome": "Cachoeira", "descricao": "Queda d'água natural", "avaliacao": 4.8, "horario": "07h-16h"},
    ],
    "vida_noturna": [
        {"nome": "Bar com Música ao Vivo", "descricao": "Shows e drinks artesanais", "avaliacao": 4.2, "horario": "19h-03h"},
        {"nome": "Pub Temático", "descricao": "Cervejas artesanais", "avaliacao": 4.0, "horario": "18h-02h"},
    ],
    "historia": [
        {"nome": "Museu Histórico", "descricao": "Acervo da história local", "avaliacao": 4.4, "horario": "09h-17h"},
        {"nome": "Forte/Monumento", "descricao": "Patrimônio histórico", "avaliacao": 4.6, "horario": "08h-18h"},
    ],
}


def get_points_of_interest(
    cidade: str,
    preferencias: list[str],
    orcamento: str = "moderado",
) -> list[PointOfInterest]:
    """Tool principal: busca pontos de interesse para o destino.

    Args:
        cidade: Cidade de destino.
        preferencias: Categorias de interesse do viajante.
        orcamento: Faixa de orçamento.

    Returns:
        Lista de PointOfInterest validados.
    """
    # Validar entrada
    try:
        validated = POIToolInput(
            cidade=cidade,
            preferencias=preferencias,
            orcamento=orcamento,
        )
    except Exception:
        # Fallback: retornar POIs genéricos
        validated = POIToolInput(cidade=cidade, preferencias=["cultura"], orcamento="moderado")

    pois: list[PointOfInterest] = []

    for pref in validated.preferencias:
        categoria_pois = _POIS_DATABASE.get(pref.lower(), [])

        # Filtrar por orçamento se relevante
        max_por_categoria = 2 if orcamento == "economico" else 3

        for poi_data in categoria_pois[:max_por_categoria]:
            pois.append(
                PointOfInterest(
                    nome=f"{poi_data['nome']} - {validated.cidade}",
                    categoria=pref,
                    descricao=poi_data["descricao"],
                    avaliacao=poi_data["avaliacao"],
                    endereco=f"{validated.cidade}, Brasil",
                    horario_funcionamento=poi_data.get("horario", "Consultar"),
                )
            )

    return pois
