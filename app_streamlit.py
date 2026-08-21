"""Interface Streamlit para o Organizador de Roteiros de Viagem.

Execute com: streamlit run app_streamlit.py
"""

import json
from datetime import date, timedelta

import streamlit as st
import httpx

# Configuração da página
st.set_page_config(
    page_title="Organizador de Roteiros de Viagem",
    page_icon="🗺️",
    layout="wide",
)

API_URL = "http://localhost:8000"


def main():
    st.title("🗺️ Organizador Inteligente de Roteiros de Viagem")
    st.markdown("*Agente IA com LangGraph para gerar roteiros personalizados*")

    # Sidebar com informações
    with st.sidebar:
        st.header("ℹ️ Sobre")
        st.markdown("""
        Este agente utiliza:
        - **LangGraph** para orquestração
        - **Groq** (LLM gratuito)
        - **OpenWeatherMap** para clima
        - **Memória SQLite** para contexto
        - **Guardrails** de segurança
        """)

        st.divider()
        st.header("🔗 Links")
        st.markdown("[📊 API Docs](http://localhost:8000/docs)")
        st.markdown("[📋 Board Kanban](https://github.com/users/Felipe-Feyh/projects/2)")

        st.divider()
        st.header("🛡️ Status")
        try:
            health = httpx.get(f"{API_URL}/health", timeout=5).json()
            st.success(f"API: {health['status']}")
        except Exception:
            st.error("API offline. Execute: python -m src.main")

    # Tabs principais
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📝 Novo Roteiro", "🛡️ Segurança", "📊 Observabilidade", "💾 Memória"]
    )

    # === Tab 1: Criar Roteiro ===
    with tab1:
        st.header("Criar Roteiro de Viagem")

        col1, col2 = st.columns(2)

        with col1:
            destino = st.text_input("🏙️ Destino", value="Porto Alegre")
            data_inicio = st.date_input(
                "📅 Data de Início",
                value=date.today() + timedelta(days=30),
            )
            data_fim = st.date_input(
                "📅 Data de Fim",
                value=date.today() + timedelta(days=34),
            )

        with col2:
            preferencias = st.multiselect(
                "❤️ Preferências",
                ["cultura", "gastronomia", "aventura", "compras", "relaxamento", "natureza", "vida_noturna", "historia"],
                default=["cultura", "gastronomia"],
            )
            orcamento = st.selectbox(
                "💰 Orçamento",
                ["economico", "moderado", "premium"],
                index=1,
            )

        if st.button("🚀 Gerar Roteiro", type="primary", use_container_width=True):
            with st.spinner("Gerando roteiro..."):
                try:
                    response = httpx.post(
                        f"{API_URL}/roteiro",
                        json={
                            "destino": destino,
                            "data_inicio": str(data_inicio),
                            "data_fim": str(data_fim),
                            "preferencias": preferencias,
                            "orcamento": orcamento,
                            "restricoes": [],
                        },
                        timeout=30,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        st.success(f"✅ Roteiro gerado! Trace: `{data['trace_id']}`")

                        # Mostrar alertas
                        if data.get("alertas"):
                            for alerta in data["alertas"]:
                                st.warning(alerta)

                        # Mostrar clima
                        st.subheader("🌤️ Clima Previsto")
                        clima = data.get("clima_previsto", {})
                        if clima:
                            col_c1, col_c2, col_c3 = st.columns(3)
                            col_c1.metric("Temperatura Média", f"{clima.get('temperatura_media', 'N/A')}°C")
                            col_c2.metric("Condição", clima.get("condicao", "N/A"))
                            col_c3.metric("Umidade", f"{clima.get('umidade', 'N/A')}%")

                        # Mostrar roteiro dia a dia
                        st.subheader("📋 Roteiro Dia a Dia")
                        for dia in data.get("roteiro", []):
                            with st.expander(f"Dia {dia['dia']} - {dia.get('data', '')} | {dia.get('clima_esperado', '')}"):
                                st.markdown("**🌅 Manhã:**")
                                for ativ in dia.get("periodo_manha", []):
                                    st.markdown(f"  - {ativ}")
                                st.markdown("**☀️ Tarde:**")
                                for ativ in dia.get("periodo_tarde", []):
                                    st.markdown(f"  - {ativ}")
                                st.markdown("**🌙 Noite:**")
                                for ativ in dia.get("periodo_noite", []):
                                    st.markdown(f"  - {ativ}")

                        # Pontos de interesse
                        st.subheader("📍 Pontos de Interesse")
                        for poi in data.get("pontos_interesse", []):
                            st.markdown(f"- **{poi['nome']}** ({poi['categoria']}) ⭐ {poi.get('avaliacao', 'N/A')}")

                    elif response.status_code == 422:
                        error_data = response.json()
                        st.error("❌ Validação falhou:")
                        detail = error_data.get("detail", {})
                        if isinstance(detail, dict):
                            for err in detail.get("errors", []):
                                st.error(f"  • {err}")
                        else:
                            st.error(str(detail))
                    else:
                        st.error(f"Erro: {response.status_code} - {response.text}")

                except httpx.ConnectError:
                    st.error("❌ API offline. Execute: `python -m src.main`")
                except Exception as e:
                    st.error(f"Erro: {str(e)}")

    # === Tab 2: Segurança ===
    with tab2:
        st.header("🛡️ Testes de Segurança")

        if st.button("🔍 Executar Cenários Adversariais"):
            try:
                response = httpx.get(f"{API_URL}/seguranca/adversarial", timeout=10)
                data = response.json()

                col1, col2, col3 = st.columns(3)
                col1.metric("Total", data["total_scenarios"])
                col2.metric("Passaram", data["passed"], delta_color="normal")
                col3.metric("Falharam", data["failed"], delta_color="inverse")

                for result in data["results"]:
                    icon = "✅" if result["passed"] else "❌"
                    with st.expander(f"{icon} {result['scenario']}"):
                        st.write(f"**Descrição:** {result['description']}")
                        st.write(f"**Bloqueado:** {'Sim' if result['actual_blocked'] else 'Não'}")
                        st.write(f"**Nível:** {result['security_level']}")
                        if result.get("reason"):
                            st.write(f"**Motivo:** {result['reason']}")
            except Exception as e:
                st.error(f"Erro: {e}")

        st.divider()
        st.subheader("Testar entrada manualmente")
        test_input = st.text_input("Digite uma entrada para verificar:", "Porto Alegre")
        if st.button("Verificar Segurança"):
            try:
                response = httpx.post(
                    f"{API_URL}/seguranca/verificar",
                    json={
                        "destino": test_input,
                        "data_inicio": "2026-09-01",
                        "data_fim": "2026-09-05",
                        "preferencias": [],
                        "orcamento": "moderado",
                    },
                    timeout=10,
                )
                data = response.json()
                if data["is_safe"]:
                    st.success(f"✅ Entrada segura (nível: {data['level']})")
                else:
                    st.error(f"🚫 Entrada bloqueada: {data['reason']}")
            except Exception as e:
                st.error(f"Erro: {e}")

    # === Tab 3: Observabilidade ===
    with tab3:
        st.header("📊 Observabilidade")

        try:
            metrics = httpx.get(f"{API_URL}/observabilidade/metricas", timeout=10).json()

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Execuções", metrics.get("total_executions", 0))
            col2.metric("Latência Média", f"{metrics.get('avg_latency_ms', 0):.0f}ms")
            col3.metric("Taxa de Erro", f"{metrics.get('error_rate', 0):.1f}%")
            col4.metric("Máx Latência", f"{metrics.get('max_latency_ms', 0):.0f}ms")

            if metrics.get("node_avg_latencies"):
                st.subheader("Latência por Node")
                st.bar_chart(metrics["node_avg_latencies"])

        except Exception:
            st.info("Sem dados de métricas ainda. Execute alguns roteiros primeiro.")

        st.divider()
        st.subheader("Traces Recentes")
        try:
            traces = httpx.get(f"{API_URL}/observabilidade/traces", timeout=10).json()
            if traces.get("traces"):
                for trace in traces["traces"][:5]:
                    st.markdown(
                        f"- `{trace['trace_id']}` | {trace['total_steps']} steps | "
                        f"{trace['total_latency_ms']:.0f}ms | Erros: {trace['errors_count']}"
                    )
            else:
                st.info("Nenhum trace registrado ainda.")
        except Exception:
            st.info("Execute roteiros para gerar traces.")

    # === Tab 4: Memória ===
    with tab4:
        st.header("💾 Memória e Contexto")

        try:
            ctx = httpx.get(f"{API_URL}/memoria/contexto", timeout=10).json()
            context = ctx.get("context", {})

            if context.get("has_context"):
                st.subheader("Destinos Recentes")
                for dest in context.get("recent_destinations", []):
                    st.markdown(f"- 📍 {dest}")

                st.subheader("Preferências Frequentes")
                for pref, count in context.get("frequent_preferences", {}).items():
                    st.markdown(f"- {pref}: {count}x")

                st.metric("Total de Viagens", context.get("total_trips", 0))
            else:
                st.info("Sem histórico ainda. Gere roteiros para construir memória.")

        except Exception:
            st.info("API indisponível.")

        st.divider()
        st.subheader("Histórico de Execuções")
        try:
            history = httpx.get(f"{API_URL}/memoria/historico", timeout=10).json()
            for exec_item in history.get("executions", [])[:5]:
                st.markdown(
                    f"- **{exec_item['destino']}** | {exec_item['data_inicio']} a {exec_item['data_fim']} | "
                    f"Status: {exec_item['status']}"
                )
        except Exception:
            pass


if __name__ == "__main__":
    main()
