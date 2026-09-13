"""Pagina Visao Geral -- volume, diagnosticos e mapa."""

import sys
from pathlib import Path

PROJETO_RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJETO_RAIZ))

import plotly.express as px
import streamlit as st

from core.components import sidebar_filtros
from core.consultas import (
    aplicar_filtros,
    calcular_kpis,
    distribuicao_dias_internacao,
    distribuicao_paciente_viajou,
    distribuicao_por_categoria_diagnostico,
    distribuicao_por_porte,
    evolucao_top_hospitais,
    internacoes_por_periodo,
    mapa_municipios,
    ranking_municipios,
    top_diagnosticos,
)
from core.data_loader import load_all
from core.tema_editorial import (
    COR_BOM,
    COR_NEUTRA,
    aplicar_estilo_sidebar,
    aplicar_tema_claro,
    explicacao_grafico,
    kpi_editorial,
    pill,
    titulo_secao,
)

st.set_page_config(page_title="MedData | Visão Geral", layout="wide")
aplicar_estilo_sidebar()

st.caption("DASHBOARD MEDDATA · VISÃO GERAL")
st.title("Como está o volume de internações da rede?")

dados = load_all()
dim_hospital = dados["dim_hospital"]
dim_municipio = dados["dim_municipio"]
dim_diagnostico = dados.get("dim_diagnostico")
fato = dados["fato_internacao"]

filtros = sidebar_filtros(dim_hospital, dim_municipio, fato)
fato_filtrado = aplicar_filtros(fato, filtros)

if fato_filtrado.empty:
    st.warning("Nenhuma internação encontrada para os filtros selecionados.")
    st.stop()

pill(f"Período: {filtros.data_inicio.strftime('%b/%Y')} a {filtros.data_fim.strftime('%b/%Y')}")
pill(f"{len(fato_filtrado):,}".replace(",", ".") + " internações no filtro")
st.write("")

# paleta sequencial de teal, pra graficos com varias fatias
SEQUENCIA_TEAL = ["#0F6B72", "#3E8F94", "#7BB3B8", "#B8D8DB"]

# KPIs de volume
titulo_secao("Indicadores gerais")
kpis = calcular_kpis(fato_filtrado, dim_hospital)

col1, col2, col3, col4 = st.columns(4)
kpi_editorial(col1, "Total de internações", f"{kpis['total_internacoes']:,}".replace(",", "."))
kpi_editorial(col2, "Hospitais atendendo", f"{kpis['total_hospitais']:,}".replace(",", "."))
kpi_editorial(col3, "Municípios atendidos", f"{kpis['total_municipios']:,}".replace(",", "."))
kpi_editorial(col4, "Leitos totais (no filtro)", f"{kpis['total_leitos']:,}".replace(",", "."))

col5, col6, col7 = st.columns(3)
kpi_editorial(col5, "Média de dias de internação", f"{kpis['media_dias_internacao']:.1f}")
kpi_editorial(
    col6, "Valor total dos procedimentos",
    f"R$ {kpis['valor_total_procedimentos']:,.2f}".replace(",", "#").replace(".", ",").replace("#", "."),
)
kpi_editorial(col7, "Pacientes que viajaram", f"{kpis['percentual_pacientes_viajaram']:.1f}%")

st.write("")

# grafico de linha de internacoes por periodo + ranking de municipios
col_esq, col_dir = st.columns(2)

with col_esq:
    titulo_secao("Internações por período")
    serie = internacoes_por_periodo(fato_filtrado)
    fig = px.line(serie, x="periodo", y="internacoes", markers=True, color_discrete_sequence=[COR_BOM])
    fig.update_layout(xaxis_title="Mês", yaxis_title="Internações")
    st.plotly_chart(aplicar_tema_claro(fig), width="stretch")
    explicacao_grafico("Volume total de internações por mês, no período e filtros selecionados.")

with col_dir:
    titulo_secao("Ranking de municípios")
    rk_mun = ranking_municipios(fato_filtrado, dim_municipio)
    fig = px.bar(rk_mun, x="internacoes", y="nome_municipio", orientation="h", color_discrete_sequence=[COR_BOM])
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Internações", yaxis_title="")
    st.plotly_chart(aplicar_tema_claro(fig), width="stretch")
    explicacao_grafico("Os 10 municípios de origem do paciente com mais internações no filtro.")

col_esq3, col_dir3 = st.columns(2)

with col_esq3:
    titulo_secao("Hospitais por porte")
    dist_porte = distribuicao_por_porte(fato_filtrado, dim_hospital)
    fig = px.pie(dist_porte, names="porte_hospitalar", values="hospitais", hole=0.6, color_discrete_sequence=SEQUENCIA_TEAL)
    st.plotly_chart(aplicar_tema_claro(fig), width="stretch")
    explicacao_grafico(
        "Quantidade de hospitais cadastrados por porte -- não volume de internações "
        "(que fica quase todo concentrado em Grande Porte e não é um gráfico útil)."
    )

with col_dir3:
    titulo_secao("Distribuição de dias de internação")
    dist_dias = distribuicao_dias_internacao(fato_filtrado)
    fig = px.histogram(dist_dias, x="dias_internacao", nbins=30, color_discrete_sequence=[COR_BOM])
    fig.update_layout(xaxis_title="Dias de internação", yaxis_title="Internações")
    st.plotly_chart(aplicar_tema_claro(fig), width="stretch")
    explicacao_grafico("Quantas internações duraram cada quantidade de dias.")

# --- Secoes exclusivas dos dados V2 (diagnosticos) ---
if dim_diagnostico is not None:
    st.write("")
    titulo_secao("Diagnósticos")

    col_diag1, col_diag2 = st.columns(2)

    with col_diag1:
        st.markdown("**Top 10 diagnósticos (CID)**")
        td = top_diagnosticos(fato_filtrado, dim_diagnostico)
        fig = px.bar(
            td, x="internacoes", y="descricao_cid", orientation="h",
            hover_data=["categoria_cid"], color_discrete_sequence=[COR_BOM],
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Internações", yaxis_title="")
        st.plotly_chart(aplicar_tema_claro(fig, altura=420), width="stretch")

    with col_diag2:
        st.markdown("**Diagnósticos mais frequentes (proporção)**")
        dist_diag = distribuicao_por_categoria_diagnostico(fato_filtrado, dim_diagnostico)
        fig = px.treemap(dist_diag, path=["descricao_cid"], values="internacoes", color_discrete_sequence=SEQUENCIA_TEAL)
        fig.update_traces(textinfo="label+percent root")
        st.plotly_chart(aplicar_tema_claro(fig, altura=420), width="stretch")

    explicacao_grafico(
        "Internações cujo código de diagnóstico não tem correspondência exata na dimensão "
        "(ex.: informado só até a categoria, sem o dígito de subcategoria) foram excluídas -- "
        "cerca de 2% do total."
    )

# --- Mapa geografico + pacientes que viajaram ---
st.write("")
titulo_secao("Distribuição geográfica")
col_mapa, col_viajou = st.columns([2, 1])

with col_mapa:
    mapa = mapa_municipios(fato_filtrado, dim_municipio)
    if not mapa.empty:
        fig = px.scatter_map(
            mapa, lat="latitude", lon="longitude", size="internacoes", color="internacoes",
            hover_name="nome_municipio", color_continuous_scale=["#B8D8DB", "#0F6B72"],
            map_style="open-street-map", size_max=28, zoom=6, height=360,
        )
        fig.update_traces(marker=dict(opacity=0.85))
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
        explicacao_grafico("Restrito ao estado de São Paulo -- é a única UF presente nos dados atuais.")
    else:
        st.info("Sem coordenadas suficientes para montar o mapa com os filtros atuais.")

with col_viajou:
    st.markdown("**Pacientes que viajaram**")
    dist_viajou = distribuicao_paciente_viajou(fato_filtrado)
    fig = px.pie(
        dist_viajou, names="paciente_viajou", values="internacoes", hole=0.6,
        color_discrete_sequence=[COR_BOM, COR_NEUTRA],
    )
    st.plotly_chart(aplicar_tema_claro(fig, altura=360), width="stretch")

# --- Evolucao animada dos hospitais de maior volume ---
st.write("")
titulo_secao("Evolução mensal dos hospitais de maior volume")
ev = evolucao_top_hospitais(fato_filtrado, dim_hospital)
if not ev.empty:
    fig = px.bar(
        ev, x="internacoes", y="id_hospital", orientation="h", animation_frame="periodo",
        range_x=[0, ev["internacoes"].max() * 1.1], hover_data=["nome_municipio_hospital"],
        color_discrete_sequence=[COR_BOM],
    )
    fig.update_layout(showlegend=False, yaxis_title="Código CNES", xaxis_title="Internações no mês")
    fig.update_yaxes(categoryorder="total ascending")
    st.plotly_chart(aplicar_tema_claro(fig, altura=450), width="stretch")
    explicacao_grafico(
        "Ranking mês a mês dos 8 hospitais de maior volume total -- use o botão Play "
        "(ou o controle deslizante) pra ver a posição de cada hospital mudar entre os meses."
    )
else:
    st.info("Sem dados suficientes para a evolução mensal com os filtros atuais.")

st.write("")
titulo_secao("Dados filtrados (amostra)")
st.dataframe(fato_filtrado.head(200), width="stretch", height=320)
explicacao_grafico(f"Mostrando 200 de {len(fato_filtrado):,}".replace(",", ".") + " internações filtradas.")
