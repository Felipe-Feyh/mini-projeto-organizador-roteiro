# Organizador Inteligente de Roteiros de Viagem

> Agente IA que organiza roteiros de viagem personalizados usando LangGraph, com integração a APIs externas, memória persistente, segurança e observabilidade.

**Em desenvolvimento** — documentação completa será adicionada ao final do projeto.

## Início Rápido

```bash
# Clone o repositório
git clone https://github.com/Felipe-Feyh/mini-projeto-organizador-roteiro.git
cd mini-projeto-organizador-roteiro

# Crie o ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt

# Configure variáveis de ambiente
copy .env.example .env
# Edite o .env com suas chaves

# Execute
python -m src.main
```

## Estrutura do Projeto

```
src/
├── agent/       # Fluxo LangGraph (state, nodes, edges, graph)
├── tools/       # Tools de integração (clima, POIs)
├── memory/      # Memória persistente (checkpointer)
├── security/    # Guardrails e governança
├── observability/ # Logs, traces, métricas
├── config.py    # Configurações centralizadas
└── main.py      # FastAPI - entrada principal
```
