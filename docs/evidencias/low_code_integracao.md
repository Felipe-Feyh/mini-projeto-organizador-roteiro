# Integração Low-Code/No-Code - n8n

## Visão Geral

Fluxo automatizado no **n8n** que integra com a aplicação principal para:
1. Receber solicitação de roteiro via webhook
2. Chamar a API da aplicação
3. Enviar notificação no Discord com o resultado

## Fluxo

```
[Webhook Trigger] → [Chamar API /webhook/roteiro-pronto] → [IF sucesso?]
                                                              ├── SIM → [Notificar Discord ✅]
                                                              └── NÃO → [Notificar Discord ❌]
```

## Componentes

| Node | Tipo | Descrição |
|------|------|-----------|
| Webhook Trigger | Gatilho | Recebe POST com dados do roteiro |
| Chamar API Roteiro | HTTP Request | POST para `/webhook/roteiro-pronto` |
| Roteiro Gerado? | Condicional | Verifica campo `success` da resposta |
| Notificar Discord | Discord Webhook | Envia mensagem formatada |
| Notificar Erro | Discord Webhook | Envia alerta de falha |

## Instruções de Reprodução

### 1. Instalar n8n
```bash
npx n8n
# Ou via Docker:
docker run -it --rm -p 5678:5678 n8nio/n8n
```

### 2. Importar o fluxo
1. Abra http://localhost:5678
2. Vá em **Workflows** → **Import from File**
3. Selecione `docs/evidencias/n8n_flow.json`

### 3. Configurar variáveis
- `DISCORD_WEBHOOK_URL`: URL do webhook do Discord (Settings → Environment Variables)

### 4. Ativar e testar
1. Ative o workflow
2. Envie um POST para o webhook do n8n:
```bash
curl -X POST http://localhost:5678/webhook/gerar-roteiro \
  -H "Content-Type: application/json" \
  -d '{
    "destino": "Porto Alegre",
    "data_inicio": "2026-09-01",
    "data_fim": "2026-09-05",
    "preferencias": ["cultura", "gastronomia"],
    "orcamento": "moderado"
  }'
```

### 5. Resultado esperado
- Roteiro gerado pela aplicação
- Mensagem no Discord:
  ```
  🗺️ Roteiro para Porto Alegre pronto!
  📅 2026-09-01 a 2026-09-05 (4 dias)
  ✅ Trace: abc12345
  ```

## Segundo Webhook: Health Report

Também disponível um endpoint para monitoramento periódico:
- **URL**: `GET /webhook/health-report`
- **Uso no n8n**: Cron Trigger (a cada 5 minutos) → HTTP Request → IF degraded → Alerta Discord

## Relação com a Solução Principal

- A **lógica principal** permanece na aplicação (LangGraph, tools, memória)
- O **n8n atua como orquestrador externo** para automação de notificações
- O gatilho pode ser:
  - Manual (webhook externo)
  - Periódico (health check)
  - Evento (ex: nova solicitação de usuário via chatbot)
