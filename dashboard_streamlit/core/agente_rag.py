"""Orquestracao dos agentes do Chat MedData -- roteamento por IA + RAG."""

from __future__ import annotations

import os
from dataclasses import dataclass

import oracledb
from core import db
from core.agente import AGENTES, _profile_do_agente
from core.agente import rotear_pergunta as _rotear_por_palavra_chave
from core.casos_conhecidos import tentar_caso_conhecido
from core.db import RespostaSelectAI
from core.rag import buscar_conhecimento


@dataclass
class RespostaAgenteRAG:
    agente_key: str
    agente_label: str
    resposta: RespostaSelectAI
    trechos_conhecimento: list[str]


def rotear_com_ia(pergunta: str, profile: str) -> str:
    """Pede pro modelo classificar a pergunta num dos 3 agentes (com fallback por palavra-chave)."""
    prompt = (
        "Classifique a pergunta do gestor em EXATAMENTE uma destas 3 categorias: "
        "capacidade, predicao, otimizacao. Responda apenas com a palavra da "
        "categoria escolhida, sem mais nada.\n\n"
        f"Pergunta: {pergunta}"
    )
    try:
        resposta = db.chat_simples(prompt, profile).strip().lower()
    except oracledb.Error:
        return _rotear_por_palavra_chave(pergunta)

    for chave in AGENTES:
        if chave in resposta:
            return chave
    return _rotear_por_palavra_chave(pergunta)


def perguntar_ao_agente_rag(pergunta: str, agente_key: str | None = None) -> RespostaAgenteRAG:
    """Fluxo completo do Chat MedData: orquestrador de IA + RAG + Select AI."""
    profile_padrao = os.getenv("SELECT_AI_PROFILE", "")
    agente_key = agente_key or rotear_com_ia(pergunta, profile_padrao)
    agente_cfg = AGENTES[agente_key]

    # tenta um caso conhecido (calculo testado, sem IA nem RAG) antes do fluxo livre
    caso = tentar_caso_conhecido(pergunta, agente_key)
    if caso is not None:
        resposta = RespostaSelectAI(
            pergunta=pergunta, sql_gerado="", tabela=caso["tabela"], explicacao=caso["explicacao"]
        )
        return RespostaAgenteRAG(
            agente_key=agente_key, agente_label=agente_cfg["label"], resposta=resposta, trechos_conhecimento=[]
        )

    trechos = buscar_conhecimento(agente_key, pergunta, k=2)
    conhecimento_texto = "\n".join(f"- {t}" for t in trechos) if trechos else "(nenhum trecho relevante encontrado)"

    # persona nunca vai pro showsql; conhecimento tecnico do RAG vai (dicas_sql)
    contexto_completo = (
        f"{agente_cfg['contexto']}\n\n"
        f"Conhecimento de referencia sobre este tema (boas praticas de gestao "
        f"hospitalar, use para orientar sua recomendacao):\n{conhecimento_texto}"
    )
    resposta = db.perguntar(
        pergunta,
        profile=_profile_do_agente(agente_key),
        contexto=contexto_completo,
        dicas_sql=conhecimento_texto if trechos else None,
    )

    return RespostaAgenteRAG(
        agente_key=agente_key,
        agente_label=agente_cfg["label"],
        resposta=resposta,
        trechos_conhecimento=trechos,
    )
