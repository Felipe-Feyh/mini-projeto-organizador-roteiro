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

    Fluxo:
    1. Valida entrada
    2. Tenta gerar POIs reais via LLM (conhecimento da cidade)
    3. Fallback: base de dados estática genérica

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

    # Tentar gerar POIs reais via LLM
    if validated.preferencias:
        llm_pois = _get_pois_with_llm(validated.cidade, validated.preferencias)
        if llm_pois:
            return llm_pois

    # Fallback: base de dados estática
    return _get_pois_from_database(validated.cidade, validated.preferencias, orcamento)


def _get_pois_with_llm(cidade: str, preferencias: list[str]) -> list[PointOfInterest] | None:
    """Gera pontos de interesse reais usando o LLM.

    Args:
        cidade: Cidade de destino.
        preferencias: Categorias de interesse.

    Returns:
        Lista de POIs reais ou None se falhar.
    """
    import json as json_module

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from src.llm import get_llm

        llm = get_llm()
        if not llm:
            return None

        prompt = f"""Liste pontos de interesse turísticos REAIS da cidade {cidade}.
Categorias desejadas: {', '.join(preferencias)}

Para cada categoria, liste 2-3 locais reais e conhecidos da cidade.
Responda APENAS com um JSON array, sem texto adicional:
[
  {{"nome": "Nome real do local", "categoria": "categoria", "descricao": "breve descrição", "avaliacao": 4.5, "horario_funcionamento": "09h-18h"}}
]"""

        response = llm.invoke([
            SystemMessage(content="Você é um guia turístico especialista. Responda APENAS com JSON válido contendo locais reais."),
            HumanMessage(content=prompt),
        ])

        content = response.content.strip()
        # Limpar markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            content = content.rsplit("```", 1)[0] if "```" in content else content

        pois_data = json_module.loads(content)

        pois = []
        for poi_data in pois_data:
            pois.append(PointOfInterest(
                nome=poi_data.get("nome", "Atração"),
                categoria=poi_data.get("categoria", "geral"),
                descricao=poi_data.get("descricao", ""),
                avaliacao=float(poi_data.get("avaliacao", 4.0)),
                endereco=cidade,
                horario_funcionamento=poi_data.get("horario_funcionamento", "Consultar"),
            ))

        return pois if pois else None

    except Exception:
        return None


def _get_pois_from_database(
    cidade: str,
    preferencias: list[str],
    orcamento: str,
) -> list[PointOfInterest]:
    """Fallback: retorna POIs da base de dados estática.

    Args:
        cidade: Cidade de destino.
        preferencias: Categorias de interesse.
        orcamento: Faixa de orçamento.

    Returns:
        Lista de POIs genéricos.
    """
    pois: list[PointOfInterest] = []

    for pref in preferencias:
        categoria_pois = _POIS_DATABASE.get(pref.lower(), [])
        max_por_categoria = 2 if orcamento == "economico" else 3

        for poi_data in categoria_pois[:max_por_categoria]:
            pois.append(
                PointOfInterest(
                    nome=f"{poi_data['nome']} - {cidade}",
                    categoria=pref,
                    descricao=poi_data["descricao"],
                    avaliacao=poi_data["avaliacao"],
                    endereco=cidade,
                    horario_funcionamento=poi_data.get("horario", "Consultar"),
                )
            )

    return pois
