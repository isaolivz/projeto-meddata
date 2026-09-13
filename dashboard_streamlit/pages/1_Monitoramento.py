"""Pagina Monitoramento -- alertas, risco e ocupacao."""

import sys
from pathlib import Path

PROJETO_RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJETO_RAIZ))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.components import sidebar_filtros
from core.consultas import (
    aplicar_filtros,
    calcular_kpis_operacionais,
    calcular_risco_ocupacao,
    gerar_alertas_inteligentes,
    internacoes_por_periodo,
)
from core.data_loader import load_all
from core.tema_editorial import (
    COR_ATENCAO,
    COR_BOM,
    COR_RUIM,
    alerta_editorial,
    aplicar_estilo_sidebar,
    aplicar_tema_claro,
    explicacao_grafico,
    kpi_editorial,
    nota_contexto,
    pill,
    titulo_secao,
)

st.set_page_config(page_title="MedData | Monitoramento", layout="wide")
aplicar_estilo_sidebar()

st.caption("DASHBOARD MEDDATA · MONITORAMENTO")
st.title("A rede hospitalar está em risco de colapso?")

dados = load_all()
dim_hospital = dados["dim_hospital"]
dim_municipio = dados["dim_municipio"]
fato = dados["fato_internacao"]

filtros = sidebar_filtros(dim_hospital, dim_municipio, fato)
fato_filtrado = aplicar_filtros(fato, filtros)

if fato_filtrado.empty:
    st.warning("Nenhuma internacao encontrada para os filtros selecionados.")
    st.stop()

kpis = calcular_kpis_operacionais(fato, hospitais_filtro=filtros.hospitais, data_referencia=filtros.data_fim)
risco = calcular_risco_ocupacao(fato, hospitais_filtro=filtros.hospitais, data_referencia=filtros.data_fim)

pill(f"Período: {filtros.data_inicio.strftime('%b/%Y')} a {filtros.data_fim.strftime('%b/%Y')}")
pill(f"Janela de risco: 30 dias até {filtros.data_fim.strftime('%d/%m/%Y')}")
st.write("")

CORES_RISCO = {"Verde": COR_BOM, "Amarelo": COR_ATENCAO, "Laranja": COR_ATENCAO, "Vermelho": COR_RUIM}

# --- KPIs em 3 camadas ---
col1, col2, col3, col4 = st.columns(4)
kpi_editorial(
    col1, "Internações (30 dias)", f"{kpis['internacoes']:,}".replace(",", "."),
    comparacao=f"{kpis['internacoes_variacao']:.1f}% vs período anterior" if kpis["internacoes_variacao"] is not None else None,
    comparacao_boa=(kpis["internacoes_variacao"] or 0) <= 0,
)
kpi_editorial(
    col2, "Ocupação média", f"{kpis['ocupacao_media']:.1f}%",
    comparacao=f"{kpis['ocupacao_media_variacao']:.1f} p.p. vs período anterior" if kpis["ocupacao_media_variacao"] is not None else None,
    comparacao_boa=(kpis["ocupacao_media_variacao"] or 0) <= 0,
)
kpi_editorial(
    col3, "Leitos disponíveis", f"{kpis['leitos_disponiveis']:,}".replace(",", "."),
    comparacao=f"{kpis['leitos_disponiveis_variacao']:.1f}% vs período anterior" if kpis["leitos_disponiveis_variacao"] is not None else None,
    comparacao_boa=(kpis["leitos_disponiveis_variacao"] or 0) >= 0,
)
kpi_editorial(
    col4, "Hospitais em alerta crítico", str(kpis["hospitais_criticos"]),
    comparacao=f"{int(kpis['hospitais_criticos_variacao']):+d} vs período anterior",
    comparacao_boa=kpis["hospitais_criticos_variacao"] <= 0,
    extra="Classificação por percentil (top 10%) -- referência relativa, não limite fixo.",
)

st.write("")

# --- Alertas ---
alertas = gerar_alertas_inteligentes(risco, top_n=3)
if alertas:
    for alerta in alertas:
        cor = CORES_RISCO.get(alerta["nivel"], COR_RUIM if alerta["nivel"] == "Vermelho" else COR_ATENCAO)
        alerta_editorial(cor, alerta["nivel"], f"Hospital {alerta['hospital']} — {alerta['municipio']}", alerta["texto"])

st.write("")
nota_contexto(
    "Alertas usam classificação por percentil (top 10% crítico, 15% laranja, 25% amarelo) -- "
    "referência relativa, não limite fixo. Os últimos 14 dias da base têm registro incompleto "
    "(borda de extração de dados) -- gráficos de tendência excluem esse período."
)

titulo_secao("O que estes números estão dizendo?")

if "leitura_monitoramento" not in st.session_state:
    st.session_state["leitura_monitoramento"] = None

if st.button("✨ Gerar a leitura do período", key="btn_leitura"):
    resumo_alertas = (
        "; ".join(f"Hospital {a['hospital']} ({a['municipio']}): {a['texto']}" for a in alertas)
        if alertas else "nenhum alerta gerado"
    )
    prompt_leitura = (
        "Voce e um analista de gestao hospitalar. Com base SOMENTE nos numeros reais abaixo "
        "(ja calculados, nao invente nenhum outro numero), escreva uma leitura curta em "
        "portugues, em ate 3 paragrafos curtos: (1) o que esta indo bem, (2) o que preocupa, "
        "(3) a acao mais urgente. Seja direto, sem enrolacao.\n\n"
        f"Internacoes (30 dias): {kpis['internacoes']} (variacao {kpis['internacoes_variacao']}% vs periodo anterior)\n"
        f"Ocupacao media da rede: {kpis['ocupacao_media']:.1f}% (variacao {kpis['ocupacao_media_variacao']} p.p.)\n"
        f"Leitos disponiveis: {kpis['leitos_disponiveis']} (variacao {kpis['leitos_disponiveis_variacao']}%)\n"
        f"Hospitais em alerta critico: {kpis['hospitais_criticos']} (variacao {kpis['hospitais_criticos_variacao']})\n"
        f"Alertas gerados: {resumo_alertas}"
    )
    try:
        import os

        from core import db

        # corrige caminho do wallet Oracle (relativo, so funciona da raiz)
        os.environ["ORACLE_WALLET_DIR"] = str(PROJETO_RAIZ / "wallet")

        profile = os.getenv("SELECT_AI_PROFILE", "")
        with st.spinner("Gerando leitura..."):
            st.session_state["leitura_monitoramento"] = db.chat_simples(prompt_leitura, profile)
    except Exception as e:
        st.session_state["leitura_monitoramento"] = None
        st.error(f"Não foi possível gerar a leitura agora: {e}")

if st.session_state["leitura_monitoramento"]:
    st.markdown(
        f"""<div style="background:#FFFFFF; border:1px solid #E5E7EB; border-radius:6px;
            padding:1rem 1.2rem; font-size:0.9rem; color:#111827; line-height:1.6;">
            {st.session_state['leitura_monitoramento']}</div>""",
        unsafe_allow_html=True,
    )
explicacao_grafico(
    "Resumo em 3 parágrafos (o que vai bem, o que preocupa, ação mais urgente), escrito só a "
    "partir dos números já calculados nesta página -- a IA não consulta o banco diretamente aqui."
)

st.write("")
titulo_secao("Onde está o risco?")

if not risco.empty:
    top10 = risco.head(10).copy()
    top10 = top10.iloc[::-1]  # maior no topo do grafico horizontal
    cores_barras = [COR_RUIM if n in ("Vermelho", "Laranja") else (COR_ATENCAO if n == "Amarelo" else COR_BOM) for n in top10["nivel_alerta"]]

    fig = go.Figure(
        go.Bar(
            x=top10["taxa_ocupacao"],
            y=[f"CNES {h}" for h in top10["id_hospital"]],
            orientation="h",
            marker_color=cores_barras,
            text=[f"{v:.0f}%" for v in top10["taxa_ocupacao"]],
            textposition="outside",
            cliponaxis=False,
        )
    )
    fig.update_layout(showlegend=False, xaxis_title="Taxa de ocupação (%)", yaxis_title="")
    fig = aplicar_tema_claro(fig, altura=320)
    st.plotly_chart(fig, width="stretch")
    explicacao_grafico(
        "Os 10 hospitais com maior taxa de ocupação no período filtrado. Terracota = crítico/laranja "
        "(top 25%) · âmbar = atenção (top 25-50%) · teal = dentro do esperado."
    )
else:
    st.info("Sem dados suficientes com os filtros atuais.")

st.write("")
col_esq, col_dir = st.columns(2)

with col_esq:
    titulo_secao("Leitos totais x leitos ocupados")
    if not risco.empty:
        fig = go.Figure()
        for nivel, cor in CORES_RISCO.items():
            grupo = risco[risco["nivel_alerta"] == nivel]
            if grupo.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=grupo["leitos_totais"], y=grupo["leitos_ocupados"], mode="markers",
                    name=nivel, marker=dict(color=cor, size=8, line=dict(width=0)),
                )
            )
        limite = max(risco["leitos_totais"].max(), risco["leitos_ocupados"].max())
        fig.add_shape(type="line", x0=0, y0=0, x1=limite, y1=limite, line=dict(color="#C5CBD3", dash="dash", width=1))
        fig.update_layout(xaxis_title="Leitos totais", yaxis_title="Leitos ocupados (média 30 dias)", legend_title_text="")
        fig = aplicar_tema_claro(fig, altura=300)
        st.plotly_chart(fig, width="stretch")
        explicacao_grafico(
            "Cada ponto é um hospital. Pontos acima da linha tracejada = operando acima da capacidade oficial."
        )
    else:
        st.info("Sem dados suficientes com os filtros atuais.")

with col_dir:
    titulo_secao("Ocupação da rede")
    valor_ocupacao = kpis["ocupacao_media"]
    eixo_max = max(100.0, valor_ocupacao * 1.2)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=valor_ocupacao,
            number={"suffix": "%", "font": {"color": "#111827"}},
            gauge={
                "axis": {"range": [0, eixo_max], "tickcolor": "#9CA3AF"},
                "bar": {"color": "#111827", "thickness": 0.25},
                "bgcolor": "#FFFFFF",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 70], "color": "#E4F0EF"},
                    {"range": [70, 85], "color": "#F3E8D2"},
                    {"range": [85, 95], "color": "#F0D5C9"},
                    {"range": [95, eixo_max], "color": "#F1D4D1"},
                ],
            },
        )
    )
    fig = aplicar_tema_claro(fig, altura=220)
    st.plotly_chart(fig, width="stretch")
    explicacao_grafico(
        "Média ponderada pelo tamanho de cada hospital -- mesmo número do KPI 'Ocupação média' acima."
    )

st.write("")
titulo_secao("Hospitais mais críticos")

if not risco.empty:
    top15 = risco.head(10).copy()
    tabela = top15[
        ["id_hospital", "nome_municipio_hospital", "taxa_ocupacao", "leitos_totais", "leitos_disponiveis", "nivel_alerta"]
    ].rename(
        columns={
            "id_hospital": "Hospital (CNES)",
            "nome_municipio_hospital": "Município",
            "taxa_ocupacao": "Ocupação",
            "leitos_totais": "Leitos totais",
            "leitos_disponiveis": "Leitos livres",
            "nivel_alerta": "Status",
        }
    )

    def _cor_status_editorial(valor):
        cor = CORES_RISCO.get(valor, COR_ATENCAO)
        return f"background-color: {cor}1A; color: {cor}; font-weight: 600;"

    tabela_estilizada = tabela.style.map(_cor_status_editorial, subset=["Status"])

    st.dataframe(
        tabela_estilizada,
        column_config={
            "Ocupação": st.column_config.ProgressColumn(
                "Ocupação", format="%.1f%%", min_value=0, max_value=max(100.0, float(tabela["Ocupação"].max()))
            ),
            "Leitos totais": st.column_config.NumberColumn("Leitos totais", format="%d"),
            "Leitos livres": st.column_config.NumberColumn("Leitos livres", format="%d"),
        },
        hide_index=True,
        width="stretch",
        height=320,
    )
    explicacao_grafico(
        "Os 10 hospitais com maior ocupação. \"Hospital\" mostra o código CNES -- os dados não "
        "trazem o nome real do estabelecimento."
    )
else:
    st.info("Sem dados suficientes com os filtros atuais.")

st.write("")
st.markdown("---")

# grafico de barras + linha de tendencia de internacoes
titulo_secao("Internações por período (com tendência)")
serie = internacoes_por_periodo(fato_filtrado)
if not serie.empty:
    media_movel = serie["internacoes"].rolling(window=3, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=serie["periodo"], y=serie["internacoes"], marker_color="#A9C2C7", name="Internações"))
    fig.add_trace(
        go.Scatter(
            x=serie["periodo"], y=media_movel, mode="lines+markers",
            line=dict(color="#111827", dash="dash", width=1.5), marker=dict(size=5, color="#111827"),
            name="Tendência (média móvel 3 meses)",
        )
    )
    fig.add_annotation(
        x=serie["periodo"].iloc[-1], y=media_movel.iloc[-1],
        text=f"{media_movel.iloc[-1]:,.0f}".replace(",", "."),
        showarrow=False, yshift=18, bgcolor="#FFFFFF", bordercolor="#111827", borderwidth=1,
        font=dict(size=11, color="#111827"),
    )
    fig.update_layout(
        xaxis_title="Mês", yaxis_title="Internações",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig = aplicar_tema_claro(fig, altura=300)
    st.plotly_chart(fig, width="stretch")
    explicacao_grafico(
        "Volume mensal de internações. A linha pontilhada é a tendência (média móvel de 3 meses)."
    )
else:
    st.info("Sem dados suficientes com os filtros atuais.")

# barra de hospitais criticos por porte + barra pareada de periodo atual x anterior
col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    titulo_secao("Hospitais críticos por porte")
    if not risco.empty:
        risco_porte = risco.merge(dim_hospital[["id_hospital", "porte_hospitalar"]], on="id_hospital", how="left")
        criticos_porte = risco_porte[risco_porte["nivel_alerta"].isin(["Vermelho", "Laranja"])]
        contagem = criticos_porte["porte_hospitalar"].value_counts().reset_index()
        contagem.columns = ["porte_hospitalar", "hospitais"]
        contagem = contagem.sort_values("hospitais", ascending=True)
        total_criticos = int(contagem["hospitais"].sum())

        if total_criticos > 0:
            contagem["pct"] = contagem["hospitais"] / total_criticos * 100
            fig = go.Figure(
                go.Bar(
                    x=contagem["hospitais"], y=contagem["porte_hospitalar"], orientation="h",
                    marker_color="#3E6E79",
                    text=[f"{p:.0f}% · {n} hospitais" for p, n in zip(contagem["pct"], contagem["hospitais"])],
                    textposition="outside", cliponaxis=False,
                )
            )
            fig.update_layout(xaxis_title="Hospitais em alerta crítico/laranja", yaxis_title="")
            fig = aplicar_tema_claro(fig, altura=280)
            st.plotly_chart(fig, width="stretch")
            explicacao_grafico("Distribuição dos hospitais em alerta crítico ou laranja, por porte hospitalar.")
        else:
            st.info("Nenhum hospital em alerta crítico/laranja com os filtros atuais.")
    else:
        st.info("Sem dados suficientes com os filtros atuais.")

with col_exp2:
    titulo_secao("Período atual x anterior (semanal)")

    fato_para_semanas = fato[fato["id_hospital"].isin(filtros.hospitais)] if filtros.hospitais else fato

    # exclui os ultimos 14 dias (registro incompleto -- ver notebooks/painel_preditivo.ipynb)
    fim_confiavel = fato_para_semanas["data_internacao"].max() - pd.Timedelta(days=14)
    SEMANAS_JANELA = 6
    fim_atual = fim_confiavel
    inicio_atual = fim_atual - pd.Timedelta(weeks=SEMANAS_JANELA) + pd.Timedelta(days=1)
    fim_anterior = inicio_atual - pd.Timedelta(days=1)
    inicio_anterior = fim_anterior - pd.Timedelta(weeks=SEMANAS_JANELA) + pd.Timedelta(days=1)

    def _contagem_semanal(df: pd.DataFrame, inicio: pd.Timestamp, fim: pd.Timestamp) -> pd.Series:
        sub = df[(df["data_internacao"] >= inicio) & (df["data_internacao"] <= fim)].copy()
        sub["semana"] = ((sub["data_internacao"] - inicio).dt.days // 7) + 1
        return sub.groupby("semana").size().reindex(range(1, SEMANAS_JANELA + 1), fill_value=0)

    semanal_atual = _contagem_semanal(fato_para_semanas, inicio_atual, fim_atual)
    semanal_anterior = _contagem_semanal(fato_para_semanas, inicio_anterior, fim_anterior)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[f"Semana {i}" for i in semanal_atual.index], y=semanal_anterior.values,
        name="Anterior", marker_color="#C7D2D8",
    ))
    fig.add_trace(go.Bar(
        x=[f"Semana {i}" for i in semanal_atual.index], y=semanal_atual.values,
        name="Atual", marker_color="#3E6E79",
    ))
    fig.update_layout(
        barmode="group", xaxis_title="", yaxis_title="Internações/semana",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig = aplicar_tema_claro(fig, altura=280)
    st.plotly_chart(fig, width="stretch")
    explicacao_grafico(
        f"Compara as últimas 6 semanas com as 6 anteriores. Atual: {inicio_atual.date()} a "
        f"{fim_atual.date()} · anterior: {inicio_anterior.date()} a {fim_anterior.date()}."
    )
