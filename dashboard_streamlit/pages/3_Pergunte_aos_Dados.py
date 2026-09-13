"""Pagina Pergunte aos Dados -- perguntas diretas via Select AI."""

import os
import sys
from pathlib import Path

PROJETO_RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJETO_RAIZ))

# corrige caminho do wallet Oracle (relativo, so funciona da raiz)
os.environ["ORACLE_WALLET_DIR"] = str(PROJETO_RAIZ / "wallet")

import plotly.express as px
import streamlit as st

from core.agente import AGENTES, perguntar_ao_agente
from core.tema_editorial import aplicar_estilo_sidebar, aplicar_tema_claro, explicacao_grafico, titulo_secao

st.set_page_config(page_title="MedData | Pergunte aos Dados", layout="wide")
aplicar_estilo_sidebar()

st.caption("DASHBOARD MEDDATA · PERGUNTE AOS DADOS")
st.title("O que você quer saber sobre a rede?")
st.caption(
    "As perguntas são respondidas por 3 agentes especializados, que consultam o "
    "Oracle Autonomous Database via Select AI (modelo Cohere)."
)

with st.expander("Sobre os agentes"):
    for chave, cfg in AGENTES.items():
        st.markdown(f"**{cfg['label']}** — {cfg['descricao']}")

if "historico" not in st.session_state:
    st.session_state.historico = []

col_pergunta, col_agente = st.columns([4, 1])
with col_pergunta:
    pergunta = st.text_input(
        "Sua pergunta",
        placeholder="Ex.: Quais foram os 10 hospitais com mais internações?",
        label_visibility="collapsed",
    )
with col_agente:
    opcao_agente = st.selectbox(
        "Agente",
        options=["Automático"] + [cfg["label"] for cfg in AGENTES.values()],
        label_visibility="collapsed",
    )

enviar = st.button("Perguntar", type="primary")

if enviar and pergunta.strip():
    agente_forcado = None
    if opcao_agente != "Automático":
        agente_forcado = next(k for k, v in AGENTES.items() if v["label"] == opcao_agente)

    with st.spinner("Consultando o Select AI..."):
        resultado = perguntar_ao_agente(pergunta.strip(), agente_key=agente_forcado)

    st.session_state.historico.insert(0, resultado)

if not st.session_state.historico:
    st.info("Faça uma pergunta acima para começar. Exemplos na descrição de cada agente.")

for item in st.session_state.historico:
    resposta = item.resposta
    with st.container(border=True):
        st.markdown(f"**Pergunta:** {resposta.pergunta}")
        st.caption(f"Respondido por: {item.agente_label}")

        if resposta.erro:
            st.error(resposta.erro)
            continue

        if resposta.explicacao:
            st.markdown(resposta.explicacao)

        if resposta.sql_gerado:
            with st.expander("Ver SQL gerado pelo Select AI"):
                st.code(resposta.sql_gerado, language="sql")

        if not resposta.tabela.empty:
            st.dataframe(resposta.tabela, width="stretch")

            colunas_numericas = resposta.tabela.select_dtypes("number").columns
            colunas_texto = resposta.tabela.select_dtypes(exclude="number").columns
            if len(colunas_numericas) >= 1 and len(colunas_texto) >= 1 and len(resposta.tabela) <= 50:
                fig = px.bar(resposta.tabela, x=colunas_texto[0], y=colunas_numericas[0])
                st.plotly_chart(aplicar_tema_claro(fig), width="stretch")
