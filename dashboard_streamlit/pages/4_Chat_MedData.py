"""Pagina Chat MedData -- conversa com os 3 agentes (IA + RAG)."""

import os
import sys
from pathlib import Path

PROJETO_RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJETO_RAIZ))

# corrige caminho do wallet Oracle (relativo, so funciona da raiz)
os.environ["ORACLE_WALLET_DIR"] = str(PROJETO_RAIZ / "wallet")

import plotly.express as px
import streamlit as st

from core.agente import AGENTES
from core.agente_rag import perguntar_ao_agente_rag
from core.tema_editorial import aplicar_estilo_sidebar, aplicar_tema_claro

st.set_page_config(page_title="MedData | Chat", layout="wide")
aplicar_estilo_sidebar()

st.caption("DASHBOARD MEDDATA · CHAT")
st.title("Converse com o MedData")
st.caption(
    "Os 3 agentes (Capacidade, Predição e Otimização) são escolhidos por um orquestrador de "
    "IA (não por palavra-chave) e usam uma base de conhecimento própria (RAG) para dar "
    "recomendações, além dos dados reais consultados via Select AI."
)

if "chat_mensagens" not in st.session_state:
    st.session_state.chat_mensagens = []


def _renderizar_resposta_assistente(item: dict) -> None:
    st.caption(item["agente_label"])

    if item.get("erro"):
        st.error(item["erro"])
        return

    if item.get("explicacao"):
        st.markdown(item["explicacao"])

    trechos = item.get("trechos_conhecimento") or []
    if trechos:
        with st.expander("Conhecimento de domínio usado (RAG)"):
            for t in trechos:
                st.markdown(f"- {t}")

    if item.get("sql_gerado"):
        with st.expander("Ver SQL gerado pelo Select AI"):
            st.code(item["sql_gerado"], language="sql")

    tabela = item.get("tabela")
    if tabela is not None and not tabela.empty:
        st.dataframe(tabela, width="stretch")

        colunas_numericas = tabela.select_dtypes("number").columns
        colunas_texto = tabela.select_dtypes(exclude="number").columns
        if len(colunas_numericas) >= 1 and len(colunas_texto) >= 1 and len(tabela) <= 50:
            fig = px.bar(tabela, x=colunas_texto[0], y=colunas_numericas[0])
            st.plotly_chart(aplicar_tema_claro(fig), width="stretch")


for msg in st.session_state.chat_mensagens:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["conteudo"])
        else:
            _renderizar_resposta_assistente(msg)

if not st.session_state.chat_mensagens:
    st.markdown("**Experimente perguntar:**")
    sugestoes = [
        "Quais hospitais estão mais lotados?",
        "Como reduzir custos hospitalares?",
        "Como as internações vão evoluir nos próximos meses?",
    ]
    cols = st.columns(len(sugestoes))
    for col, sugestao in zip(cols, sugestoes):
        if col.button(sugestao, width="stretch"):
            st.session_state["_pergunta_sugerida"] = sugestao
            st.rerun()

pergunta = st.chat_input("Pergunte algo sobre as internações...")

if not pergunta and "_pergunta_sugerida" in st.session_state:
    pergunta = st.session_state.pop("_pergunta_sugerida")

if pergunta:
    st.session_state.chat_mensagens.append({"role": "user", "conteudo": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Consultando os agentes MedData..."):
            resultado = perguntar_ao_agente_rag(pergunta)

        item_assistente = {
            "role": "assistant",
            "agente_label": resultado.agente_label,
            "erro": resultado.resposta.erro,
            "explicacao": resultado.resposta.explicacao,
            "sql_gerado": resultado.resposta.sql_gerado,
            "tabela": resultado.resposta.tabela,
            "trechos_conhecimento": resultado.trechos_conhecimento,
        }
        _renderizar_resposta_assistente(item_assistente)

    st.session_state.chat_mensagens.append(item_assistente)

if st.session_state.chat_mensagens:
    if st.button("Limpar conversa"):
        st.session_state.chat_mensagens = []
        st.rerun()

with st.expander("Sobre os agentes"):
    st.markdown(
        "Diferente da página **Pergunte aos Dados** (que roteia por palavra-chave e não tem "
        "base de conhecimento própria), aqui um orquestrador de IA decide qual agente "
        "responde, e cada um consulta uma base de conhecimento (RAG) com boas práticas de "
        "gestão hospitalar antes de responder."
    )
    for cfg in AGENTES.values():
        st.markdown(f"**{cfg['label']}** — {cfg['descricao']}")
