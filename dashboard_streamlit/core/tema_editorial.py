"""Tema visual 'editorial serio' -- paleta clara, restrita, sem decoracao."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# Paleta de cores com significado
COR_BOM = "#0F6B72"
COR_RUIM = "#B0413E"
COR_ATENCAO = "#B8862B"
COR_NEUTRA = "#9CA3AF"
COR_TEXTO_SECUNDARIO = "#6B7280"

PLOTLY_TEMPLATE_CLARO = "plotly_white"


def aplicar_estilo_sidebar() -> None:
    """Texto claro na sidebar e nos campos de digitacao (chat_input, text_input,
    text_area) -- todos usam o mesmo fundo teal escuro (secondaryBackgroundColor),
    em qualquer lugar da pagina, entao precisam do mesmo ajuste de contraste.

    O date_input e' excecao: seu campo de texto tem fundo claro por dentro
    (herdado do calendario), entao forcar texto claro nele o deixa invisivel
    (branco no branco) -- precisa de texto escuro, ao contrario do resto.
    """
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            background-color: #1E293B !important;
        }
        section[data-testid="stSidebar"] * {
            color: #F1F5F9 !important;
        }
        [data-testid="stChatInput"] textarea,
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea {
            color: #F1F5F9 !important;
        }
        [data-testid="stChatInput"] textarea::placeholder,
        [data-testid="stTextInput"] input::placeholder,
        [data-testid="stTextArea"] textarea::placeholder {
            color: #F1F5F9 !important;
            opacity: 0.75 !important;
        }
        [data-testid="stDateInput"] * {
            color: #111827 !important;
        }
        [data-testid="stDateInput"] > div {
            background-color: #FFFFFF !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def aplicar_tema_claro(fig: go.Figure, altura: int = 350) -> go.Figure:
    """Tema padrao dos graficos: fundo claro, grade fina, eixo marcado."""
    fig.update_layout(
        template=PLOTLY_TEMPLATE_CLARO,
        height=altura,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=40, b=10),
        font=dict(color="#111827", size=13),
        bargap=0.45,
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="#E5E7EB", gridwidth=1, zeroline=False,
        showline=True, linewidth=1.5, linecolor="#111827",
    )
    fig.update_yaxes(
        showgrid=False, zeroline=False,
        showline=True, linewidth=1.5, linecolor="#111827",
    )
    return fig


def kpi_editorial(col, label: str, valor: str, comparacao: str | None = None,
                   comparacao_boa: bool | None = None, extra: str | None = None) -> None:
    """Card de KPI: valor grande + comparacao + contexto extra."""
    with col:
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="font-size:0.7rem; font-weight:600; letter-spacing:0.05em;
                    color:{COR_TEXTO_SECUNDARIO}; text-transform:uppercase; margin-bottom:0.3rem;">
                    {label}
                </div>
                <div style="font-size:1.7rem; font-weight:700; color:#111827; line-height:1.2;">
                    {valor}
                </div>
                """,
                unsafe_allow_html=True,
            )
            if comparacao:
                cor = COR_BOM if comparacao_boa else COR_RUIM
                icone = "&#10003;" if comparacao_boa else "!"
                st.markdown(
                    f"""<div style="font-size:0.8rem; color:{cor}; margin-top:0.2rem;">
                        {icone} {comparacao}</div>""",
                    unsafe_allow_html=True,
                )
            if extra:
                st.markdown(
                    f"""<div style="font-size:0.75rem; color:{COR_TEXTO_SECUNDARIO}; margin-top:0.3rem;">
                        {extra}</div>""",
                    unsafe_allow_html=True,
                )


def pill(texto: str) -> None:
    """Tag azul pequena de contexto (periodo, data de referencia)."""
    st.markdown(
        f"""<span style="display:inline-block; background:#E8F1FB; color:#2563A8;
            font-size:0.75rem; font-weight:600; padding:0.25rem 0.7rem; border-radius:4px;
            margin-right:0.4rem;">{texto}</span>""",
        unsafe_allow_html=True,
    )


def titulo_secao(texto: str) -> None:
    """Titulo de secao."""
    st.markdown(
        f"""<div style="font-size:1.25rem; font-weight:700; color:#111827;
            margin:0.9rem 0 0.3rem 0;">{texto}</div>""",
        unsafe_allow_html=True,
    )


def explicacao_grafico(texto: str) -> None:
    """Card pequeno de explicacao, colocado embaixo do grafico."""
    st.markdown(
        f"""
        <div style="background:#EAF1FA; border-left: 3px solid #2563A8; border-radius:3px;
            padding:0.4rem 0.7rem; font-size:0.75rem; color:#1E3A5F; margin:0.4rem 0 0.8rem 0;">
            {texto}
        </div>
        """,
        unsafe_allow_html=True,
    )


def nota_contexto(texto: str) -> None:
    """Card de ressalva de metodologia/dado, com icone de info."""
    st.markdown(
        f"""
        <div style="background:#EAF1FA; border-left: 3px solid #2563A8; border-radius:3px;
            padding:0.5rem 0.8rem; font-size:0.8rem; color:#1E3A5F; margin-bottom:0.6rem;">
            &#9432; {texto}
        </div>
        """,
        unsafe_allow_html=True,
    )


def alerta_editorial(cor: str, nivel: str, titulo: str, texto: str) -> None:
    """Card de alerta com barra lateral colorida."""
    icone = "&times;" if cor == COR_RUIM else "!"
    st.markdown(
        f"""
        <div style="border-left: 4px solid {cor}; background: #FAFAFA;
            border-radius: 2px; padding: 0.8rem 1rem; margin-bottom: 0.6rem;">
            <div style="font-weight:600; font-size:0.95rem; color:#111827;">
                <span style="color:{cor};">{icone}</span> {titulo}
                <span style="color:{cor}; font-weight:600;"> ({nivel})</span>
            </div>
            <div style="color:{COR_TEXTO_SECUNDARIO}; font-size:0.85rem; margin-top:0.2rem;">
                {texto}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
