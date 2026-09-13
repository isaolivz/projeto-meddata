"""Guia introdutorio -- como ler o MedData."""

import sys
from pathlib import Path

PROJETO_RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJETO_RAIZ))

import streamlit as st

from core.tema_editorial import (
    COR_ATENCAO,
    COR_BOM,
    COR_RUIM,
    alerta_editorial,
    aplicar_estilo_sidebar,
    nota_contexto,
    pill,
    titulo_secao,
)

st.set_page_config(page_title="MedData | Guia", layout="wide")
aplicar_estilo_sidebar()

st.caption("DASHBOARD MEDDATA · GUIA")
st.title("Como ler o MedData")
st.markdown(
    "O MedData monitora a ocupação de leitos hospitalares do SUS em São Paulo, com foco em "
    "**risco de colapso** -- não só volume de atendimento. Este guia explica como navegar e "
    "como interpretar os números antes de usar o dashboard de verdade."
)

pill("4 páginas")
pill("dados até nov/2024")
pill("estado de São Paulo")
st.write("")

# --- Como navegar ---
titulo_secao("Como navegar")

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.markdown("**Visão Geral**")
        st.caption(
            "Volume de internações, diagnósticos (CID), mapa e evolução mensal. "
            "Contexto e escala -- não é aqui que se vê quem está em risco agora."
        )
    with st.container(border=True):
        st.markdown("**Pergunte aos Dados**")
        st.caption(
            "Perguntas diretas em português, respondidas por 3 agentes via Select AI. "
            "Bom para fatos objetivos (contagem, ranking, tendência)."
        )
with col2:
    with st.container(border=True):
        st.markdown("**Monitoramento**")
        st.caption(
            "Alertas críticos, ranking de risco por hospital e ocupação da rede. "
            "É aqui que mora o propósito central do projeto."
        )
    with st.container(border=True):
        st.markdown("**Chat MedData**")
        st.caption(
            "Mesmos agentes, em conversa, com uma base de conhecimento (RAG) que orienta "
            "recomendações -- não só o dado cru."
        )

st.write("")

# --- Como ler os indicadores ---
titulo_secao("Como ler os indicadores de risco")
st.caption(
    "Os níveis de alerta são por **percentil** (posição relativa entre os hospitais no "
    "filtro), não um limite fixo de ocupação. Isso significa que sempre vai existir um "
    "\"top 10% pior\" -- mesmo que a rede inteira esteja bem."
)

col_a, col_b, col_c, col_d = st.columns(4)
with col_a:
    alerta_editorial(COR_RUIM, "Vermelho", "Crítico", "Top 10% de ocupação entre os hospitais no filtro.")
with col_b:
    alerta_editorial("#FB923C", "Laranja", "Alto", "Próximos 15% -- ocupação elevada, mas não a pior.")
with col_c:
    alerta_editorial(COR_ATENCAO, "Amarelo", "Atenção", "Próximos 25% -- acima da mediana da rede.")
with col_d:
    alerta_editorial(COR_BOM, "Verde", "Normal", "Os 50% restantes -- dentro do esperado.")

st.write("")
nota_contexto(
    "\"Hospital\" no dashboard sempre mostra o código CNES, nunca um nome real -- os dados "
    "não trazem nome de estabelecimento. \"Ocupação média da rede\" é uma média ponderada "
    "pelo tamanho de cada hospital, não uma média simples entre as taxas individuais."
)

# --- Limitações ---
titulo_secao("Antes de confiar cegamente")
st.markdown(
    "- O Select AI (Pergunte aos Dados / Chat) **não é determinístico** -- a mesma pergunta "
    "pode gerar uma consulta diferente em outra tentativa.\n"
    "- Perguntas de **distância/geolocalização** (\"hospital mais próximo\") ainda são o "
    "ponto mais frágil do sistema.\n"
    "- As respostas da IA não sinalizam nível de confiança -- confira o SQL gerado "
    "(disponível em cada resposta) antes de usar um número em decisão real."
)
st.caption("Lista completa de bugs corrigidos e limitações conhecidas: ver o relatório \"Raio-X do MedData\".")
