"""Casos conhecidos -- perguntas previsiveis, respondidas com calculo real ja
testado (Pandas/statsmodels), em vez de deixar a IA reescrever a consulta do
zero toda vez.

Cada funcao caso_*() detecta (por palavra-chave, sem IA) se a pergunta bate
com aquele caso; se bater, calcula a resposta de verdade e devolve pronta.
Se nenhuma bater, tentar_caso_conhecido() retorna None -- quem chamou (ver
agente.py / agente_rag.py) cai no fluxo livre de sempre (Select AI gerando
SQL), sem quebrar nada do que ja funciona.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.consultas import calcular_risco_ocupacao
from core.data_loader import load_all


def _bate_com(pergunta: str, palavras: list[str]) -> bool:
    pergunta_lower = pergunta.lower()
    return any(p in pergunta_lower for p in palavras)


# --- Capacidade: quem esta mais lotado/em risco agora ---

_PALAVRAS_RISCO = [
    "lotado", "lotados", "risco", "critico", "criticos", "colapso",
    "alerta", "mais ocupado", "ocupacao mais alta",
]


def caso_hospitais_criticos(pergunta: str, top_n: int = 5) -> dict | None:
    """Agente Capacidade: 'quais hospitais estao mais lotados/em risco'."""
    if not _bate_com(pergunta, _PALAVRAS_RISCO):
        return None

    fato = load_all()["fato_internacao"]
    risco = calcular_risco_ocupacao(fato)
    if risco.empty:
        return None

    top = risco.head(top_n)
    linhas = [
        f"{i}. Hospital CNES {r.id_hospital} ({r.nome_municipio_hospital}) -- "
        f"{r.taxa_ocupacao:.0f}% de ocupacao, nivel {r.nivel_alerta}"
        for i, r in enumerate(top.itertuples(), start=1)
    ]
    explicacao = (
        "Os hospitais com maior risco de colapso agora sao:\n\n"
        + "\n".join(linhas)
        + "\n\nRecomendacao: priorize reforco de leitos, equipe ou transferencia de "
        "pacientes nao urgentes para esses hospitais nas proximas horas -- sao os que "
        "mais precisam de atencao agora."
        + "\n\n(Calculado com a mesma logica testada no Monitoramento -- "
        "classificacao por percentil de ocupacao, nao consulta gerada por IA.)"
    )
    return {"explicacao": explicacao, "tabela": top.reset_index(drop=True)}


# --- Capacidade/Otimizacao: hospital sem leito, para onde encaminhar ---

_PALAVRAS_SEM_LEITO = [
    "sem leito", "sem vaga", "leitos disponiveis", "onde encaminhar",
    "para onde encaminhar", "encaminhar o paciente", "transferir", "transferencia",
    "nao tem leito", "hospital lotado",
]


def _ids_hospital_com_leitos_confiaveis() -> set[str]:
    """IDs de hospital com leitos_totais real (corrigido pela V1, ver
    core/consultas.py:calcular_risco_ocupacao) -- exclui os hospitais que ainda
    carregam o valor inflado da V2 (bug de geracao conhecido, sem correspondencia
    na V1), pra nao recomendar 'leitos disponiveis' que na verdade sao ficticios
    (achado ao testar este caso: hospitais assim chegavam a aparecer com mais de
    1800 leitos disponiveis, numero irreal).
    """
    from core.data_loader import load_dim_hospital

    return set(load_dim_hospital()["id_hospital"].astype(str).str.zfill(7))


def caso_hospital_sem_leitos(pergunta: str, top_n: int = 5) -> dict | None:
    """Agentes Capacidade/Otimizacao: 'hospital sem leito, pra onde encaminhar'.

    Sugere hospitais com leitos disponiveis agora (nivel Verde), priorizando o
    municipio citado na pergunta quando houver. Nao calcula distancia (SDO_GEOM
    e' o ponto fragil do fluxo livre) -- so ocupacao real, ja testada.
    """
    if not _bate_com(pergunta, _PALAVRAS_SEM_LEITO):
        return None

    dados = load_all()
    fato = dados["fato_internacao"]
    risco = calcular_risco_ocupacao(fato)
    if risco.empty:
        return None

    ids_confiaveis = _ids_hospital_com_leitos_confiaveis()
    risco = risco[risco["id_hospital"].isin(ids_confiaveis)]
    if risco.empty:
        return None

    pergunta_lower = pergunta.lower()
    nomes_disponiveis = dados["dim_municipio"]["nome_municipio"].dropna().unique()
    citado = next((n for n in nomes_disponiveis if isinstance(n, str) and n.lower() in pergunta_lower), None)

    candidatos = risco[risco["nivel_alerta"] == "Verde"].sort_values("leitos_disponiveis", ascending=False)
    escopo = "na regiao (nenhum municipio especifico identificado na pergunta)"
    if citado:
        filtrados = candidatos[candidatos["nome_municipio_hospital"] == citado]
        if not filtrados.empty:
            candidatos = filtrados
            escopo = f"em {citado}"

    if candidatos.empty:
        return None

    top = candidatos.head(top_n)
    linhas = [
        f"{i}. Hospital CNES {r.id_hospital} ({r.nome_municipio_hospital}) -- "
        f"{r.leitos_disponiveis:.0f} leitos disponiveis, {r.taxa_ocupacao:.0f}% de ocupacao"
        for i, r in enumerate(top.itertuples(), start=1)
    ]
    primeiro = top.iloc[0]
    explicacao = (
        f"Hospitais com leitos disponiveis {escopo}:\n\n"
        + "\n".join(linhas)
        + f"\n\nRecomendacao: encaminhe os pacientes prioritariamente para o Hospital "
        f"CNES {primeiro['id_hospital']} ({primeiro['nome_municipio_hospital']}), que tem "
        f"o maior numero de leitos disponiveis nessa lista -- confirme a viabilidade da "
        f"transferencia com a regulacao local antes de decidir."
        + "\n\n(Calculado com a mesma logica de ocupacao testada no Monitoramento -- "
        "hospitais classificados como baixo risco (Verde), ordenados por leitos "
        "disponiveis. Nao considera distancia geografica entre hospitais.)"
    )
    return {"explicacao": explicacao, "tabela": top.reset_index(drop=True)}


# --- Otimizacao: comparar tempo medio de internacao entre municipios citados ---


def caso_comparar_municipios(pergunta: str) -> dict | None:
    """Agente Otimizacao: comparar 2+ municipios citados por nome na pergunta."""
    if "compar" not in pergunta.lower():
        return None

    dados = load_all()
    dim_municipio = dados["dim_municipio"]
    fato = dados["fato_internacao"]

    pergunta_lower = pergunta.lower()
    nomes_disponiveis = dim_municipio["nome_municipio"].dropna().unique()
    citados = [nome for nome in nomes_disponiveis if isinstance(nome, str) and nome.lower() in pergunta_lower]
    if len(citados) < 2:
        return None

    codigos = dim_municipio[dim_municipio["nome_municipio"].isin(citados)][["codigo_municipio", "nome_municipio"]]
    fato_pacientes = fato.merge(
        codigos, left_on="codigo_municipio_paciente", right_on="codigo_municipio", how="inner"
    )
    if fato_pacientes.empty:
        return None

    comparacao = (
        fato_pacientes.groupby("nome_municipio", observed=True)
        .agg(internacoes=("internacao_id", "count"), dias_medios=("dias_internacao", "mean"))
        .round(1)
        .reset_index()
        .sort_values("dias_medios")
    )
    linhas = [
        f"- {r.nome_municipio}: {r.dias_medios:.1f} dias medios de internacao ({r.internacoes} internacoes)"
        for r in comparacao.itertuples()
    ]
    municipio_maior = comparacao.iloc[-1]["nome_municipio"]  # sorted ascending por dias_medios
    explicacao = (
        "Comparacao de tempo medio de internacao:\n\n"
        + "\n".join(linhas)
        + f"\n\nRecomendacao: {municipio_maior} tem o maior tempo medio de internacao -- "
        "vale investigar se ha gargalos de alta hospitalar ou maior complexidade de "
        "casos que expliquem a diferenca."
        + "\n\n(Agrupamento direto nos dados reais -- nao e SQL gerado por IA.)"
    )
    return {"explicacao": explicacao, "tabela": comparacao.reset_index(drop=True)}


# --- Predicao: previsao de curto prazo (modelo validado no notebook) ---

_PALAVRAS_PREVISAO = [
    "previsao", "prever", "vao evoluir", "proximos dias", "proxima semana",
    "tendencia futura", "vai aumentar", "vai diminuir",
]

_DIAS_BORDA_NAO_CONFIAVEL = 14  # ver notebooks/painel_preditivo.ipynb


@st.cache_data(show_spinner="Calculando previsao (modelo estatistico)...")
def _prever_internacoes(dias_futuros: int = 14) -> pd.DataFrame:
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel

    fato = load_all()["fato_internacao"]

    serie_diaria = fato.groupby(fato["data_internacao"].dt.floor("D")).size()
    indice = pd.date_range(serie_diaria.index.min(), serie_diaria.index.max(), freq="D")
    serie_diaria = serie_diaria.reindex(indice, fill_value=0)

    fim_confiavel = serie_diaria.index.max() - pd.Timedelta(days=_DIAS_BORDA_NAO_CONFIAVEL)
    inicio = fim_confiavel - pd.Timedelta(days=364)
    serie_recente = serie_diaria.loc[inicio:fim_confiavel].asfreq("D")

    modelo = ETSModel(
        serie_recente, error="add", trend="add", damped_trend=True, seasonal="add", seasonal_periods=7
    )
    ajuste = modelo.fit(disp=False)

    datas_futuras = pd.date_range(serie_recente.index.max() + pd.Timedelta(days=1), periods=dias_futuros, freq="D")
    previsao = ajuste.get_prediction(start=datas_futuras[0], end=datas_futuras[-1])
    resumo = previsao.summary_frame(alpha=0.05)
    resumo["pi_lower"] = resumo["pi_lower"].clip(lower=0)
    return resumo[["mean", "pi_lower", "pi_upper"]].round(0)


def caso_previsao_internacoes(pergunta: str) -> dict | None:
    """Agente Predicao: previsao de curto prazo de internacoes (proximos 7 dias)."""
    if not _bate_com(pergunta, _PALAVRAS_PREVISAO):
        return None

    try:
        resumo = _prever_internacoes(dias_futuros=14)
    except Exception:
        return None
    if resumo.empty:
        return None

    proxima_semana = resumo.head(7)
    media = proxima_semana["mean"].mean()
    linhas = [
        f"- {data.strftime('%d/%m')}: {int(row['mean'])} internacoes previstas (entre {int(row['pi_lower'])} e {int(row['pi_upper'])})"
        for data, row in proxima_semana.iterrows()
    ]
    tendencia_alta = proxima_semana["mean"].iloc[-1] > proxima_semana["mean"].iloc[0]
    recomendacao = (
        "a tendencia e de alta -- reforce a escala de plantao e a disponibilidade de "
        "leitos para os proximos dias"
        if tendencia_alta
        else "a tendencia e estavel ou de queda -- volume nao deve exigir reforco extra "
        "nos proximos dias, mas continue monitorando"
    )
    explicacao = (
        f"Previsao para os proximos 7 dias (media diaria estimada: {media:.0f} internacoes):\n\n"
        + "\n".join(linhas)
        + f"\n\nRecomendacao: {recomendacao}."
        + "\n\nProjecao estatistica de tendencia (modelo Holt-Winters, validado com erro medio "
        "de ~22% num teste anterior) -- nao e uma certeza."
    )
    tabela = proxima_semana.reset_index().rename(columns={"index": "data"})
    return {"explicacao": explicacao, "tabela": tabela}


def tentar_caso_conhecido(pergunta: str, agente_key: str) -> dict | None:
    """Tenta responder com um caso conhecido testado, conforme o agente escolhido.

    Retorna None se nao bater com nenhum caso (ou se algo der errado no
    calculo) -- quem chamou deve cair no fluxo livre de Select AI.
    """
    try:
        if agente_key == "capacidade":
            return caso_hospital_sem_leitos(pergunta) or caso_hospitais_criticos(pergunta)
        if agente_key == "otimizacao":
            return caso_hospital_sem_leitos(pergunta) or caso_comparar_municipios(pergunta)
        if agente_key == "predicao":
            return caso_previsao_internacoes(pergunta)
    except Exception:
        return None
    return None
