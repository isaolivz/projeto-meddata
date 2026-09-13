"""Orquestracao dos 3 agentes da pagina Pergunte aos Dados (roteamento por palavra-chave)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from core.casos_conhecidos import tentar_caso_conhecido
from core.db import RespostaSelectAI, perguntar

AGENTES = {
    "capacidade": {
        "label": "Agente de Capacidade",
        "descricao": "Volume de internacoes, ocupacao de leitos e ranking de hospitais/municipios.",
        "palavras_chave": [
            "leito", "leitos", "capacidade", "ocupacao", "volume", "ranking",
            "mais internacoes", "atendimento", "quantidade",
        ],
        "contexto": (
            "Voce e um agente de analise de CAPACIDADE hospitalar. Foque em volume de "
            "internacoes, leitos disponiveis e ranking de hospitais ou municipios. "
            "Sempre termine sua resposta com uma recomendacao pratica e objetiva para "
            "o gestor hospitalar, nao so o dado."
        ),
    },
    "predicao": {
        "label": "Agente de Predicao",
        "descricao": "Evolucao das internacoes ao longo do tempo e tendencias.",
        "palavras_chave": [
            "evoluiram", "evolucao", "tendencia", "previsao", "prever",
            "ao longo do", "periodo", "crescimento", "queda",
        ],
        "contexto": (
            "Voce e um agente de analise de PREDICAO/TENDENCIA. Foque em como as "
            "internacoes evoluem ao longo do tempo (por mes/periodo) e possiveis tendencias. "
            "Sempre termine sua resposta com uma recomendacao pratica e objetiva para "
            "o gestor hospitalar, nao so o dado."
        ),
    },
    "otimizacao": {
        "label": "Agente de Otimizacao",
        "descricao": "Comparacoes entre municipios/hospitais e oportunidades de eficiencia.",
        "palavras_chave": [
            "compare", "comparacao", "eficiencia", "otimiza", "distancia",
            "tempo de internacao", "custo", "valor", "melhor", "pior",
        ],
        "contexto": (
            "Voce e um agente de OTIMIZACAO. Foque em comparacoes entre municipios ou "
            "hospitais, tempo de internacao, distancia percorrida e custo dos procedimentos. "
            "Sempre termine sua resposta com uma recomendacao pratica e objetiva para "
            "o gestor hospitalar, nao so o dado."
        ),
    },
}


def rotear_pergunta(pergunta: str) -> str:
    """Escolhe o agente por contagem de palavras-chave na pergunta."""
    pergunta_lower = pergunta.lower()
    pontuacao = {
        chave: sum(1 for palavra in cfg["palavras_chave"] if palavra in pergunta_lower)
        for chave, cfg in AGENTES.items()
    }
    melhor = max(pontuacao, key=pontuacao.get)
    return melhor if pontuacao[melhor] > 0 else "capacidade"


def _profile_do_agente(agente_key: str) -> str:
    especifico = os.getenv(f"SELECT_AI_PROFILE_{agente_key.upper()}")
    return especifico or os.getenv("SELECT_AI_PROFILE", "")


@dataclass
class RespostaAgente:
    agente_key: str
    agente_label: str
    resposta: RespostaSelectAI


def perguntar_ao_agente(pergunta: str, agente_key: str | None = None) -> RespostaAgente:
    agente_key = agente_key or rotear_pergunta(pergunta)
    agente = AGENTES[agente_key]

    # tenta um caso conhecido (calculo testado, sem IA) antes do fluxo livre
    caso = tentar_caso_conhecido(pergunta, agente_key)
    if caso is not None:
        resposta = RespostaSelectAI(
            pergunta=pergunta, sql_gerado="", tabela=caso["tabela"], explicacao=caso["explicacao"]
        )
    else:
        # pergunta pura pro SQL; contexto do agente so na explicacao final
        resposta = perguntar(pergunta, profile=_profile_do_agente(agente_key), contexto=agente["contexto"])

    return RespostaAgente(agente_key=agente_key, agente_label=agente["label"], resposta=resposta)
