"""Consultas/agregacoes em Pandas usadas pela Visao Geral e pelo Monitoramento."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Filtros:
    data_inicio: pd.Timestamp | None = None
    data_fim: pd.Timestamp | None = None
    municipios: list[int] | None = None  # codigo_municipio (paciente)
    hospitais: list[int] | None = None  # id_hospital (CNES)


def aplicar_filtros(fato: pd.DataFrame, filtros: Filtros) -> pd.DataFrame:
    df = fato
    mask = pd.Series(True, index=df.index)

    if filtros.data_inicio is not None:
        mask &= df["data_internacao"] >= filtros.data_inicio
    if filtros.data_fim is not None:
        mask &= df["data_internacao"] <= filtros.data_fim
    if filtros.municipios:
        mask &= df["codigo_municipio_paciente"].isin(filtros.municipios)
    if filtros.hospitais:
        mask &= df["id_hospital"].isin(filtros.hospitais)

    return df.loc[mask]


def calcular_kpis(fato_filtrado: pd.DataFrame, dim_hospital: pd.DataFrame) -> dict:
    """KPIs de volume/contexto (nao de risco -- ver calcular_kpis_operacionais)."""
    from core.data_loader import load_dim_hospital

    hospitais_no_filtro = fato_filtrado["id_hospital"].unique()

    dim_hospital_v1 = load_dim_hospital()
    leitos_reais = dim_hospital_v1[["id_hospital", "leitos_totais"]].copy()
    leitos_reais["id_hospital"] = leitos_reais["id_hospital"].astype(str).str.zfill(7)

    hospitais_corrigido = dim_hospital[["id_hospital", "leitos_totais"]].merge(
        leitos_reais, on="id_hospital", how="left", suffixes=("_original", "")
    )
    hospitais_corrigido["leitos_totais"] = hospitais_corrigido["leitos_totais"].fillna(
        hospitais_corrigido["leitos_totais_original"]
    )

    leitos_totais = hospitais_corrigido.loc[
        hospitais_corrigido["id_hospital"].isin(hospitais_no_filtro), "leitos_totais"
    ].sum()

    return {
        "total_internacoes": int(len(fato_filtrado)),
        "total_hospitais": int(fato_filtrado["id_hospital"].nunique()),
        "total_municipios": int(fato_filtrado["codigo_municipio_paciente"].nunique()),
        "total_leitos": int(leitos_totais),
        "media_dias_internacao": float(fato_filtrado["dias_internacao"].mean()) if len(fato_filtrado) else 0.0,
        "valor_total_procedimentos": float(fato_filtrado["valor_procedimento"].sum()),
        "percentual_pacientes_viajaram": float(fato_filtrado["paciente_viajou"].mean() * 100) if len(fato_filtrado) else 0.0,
    }


def internacoes_por_periodo(fato_filtrado: pd.DataFrame) -> pd.DataFrame:
    """Serie temporal (por mes) de quantidade de internacoes."""
    if fato_filtrado.empty:
        return pd.DataFrame(columns=["periodo", "internacoes"])

    serie = (
        fato_filtrado.assign(periodo=fato_filtrado["data_internacao"].dt.to_period("M").astype(str))
        .groupby("periodo", observed=True)
        .size()
        .reset_index(name="internacoes")
        .sort_values("periodo")
    )
    return serie


def ranking_hospitais(
    fato_filtrado: pd.DataFrame, dim_hospital: pd.DataFrame, top_n: int = 10
) -> pd.DataFrame:
    """Ranking de hospitais por volume de internacoes (identificados por codigo CNES)."""
    contagem = (
        fato_filtrado.groupby("id_hospital", observed=True)
        .size()
        .reset_index(name="internacoes")
    )
    ranking = contagem.merge(
        dim_hospital[["id_hospital", "nome_municipio_hospital", "porte_hospitalar"]],
        on="id_hospital",
        how="left",
    )
    ranking = ranking.sort_values("internacoes", ascending=False).head(top_n)
    ranking["id_hospital"] = ranking["id_hospital"].astype(str)
    return ranking.reset_index(drop=True)


def ranking_municipios(
    fato_filtrado: pd.DataFrame, dim_municipio: pd.DataFrame, top_n: int = 10
) -> pd.DataFrame:
    """Ranking de municipios (do paciente) por volume de internacoes."""
    contagem = (
        fato_filtrado.groupby("codigo_municipio_paciente", observed=True)
        .size()
        .reset_index(name="internacoes")
    )
    ranking = contagem.merge(
        dim_municipio[["codigo_municipio", "nome_municipio"]],
        left_on="codigo_municipio_paciente",
        right_on="codigo_municipio",
        how="left",
    )
    ranking = ranking.sort_values("internacoes", ascending=False).head(top_n)
    return ranking[["nome_municipio", "internacoes"]].reset_index(drop=True)


def distribuicao_por_porte(fato_filtrado: pd.DataFrame, dim_hospital: pd.DataFrame) -> pd.DataFrame:
    """Quantidade de hospitais (nao internacoes) por porte, no filtro atual."""
    hospitais_no_filtro = fato_filtrado["id_hospital"].unique()
    dim_no_filtro = dim_hospital[dim_hospital["id_hospital"].isin(hospitais_no_filtro)]
    dist = dim_no_filtro["porte_hospitalar"].value_counts().reset_index()
    dist.columns = ["porte_hospitalar", "hospitais"]
    return dist.sort_values("hospitais", ascending=False)


def distribuicao_dias_internacao(fato_filtrado: pd.DataFrame) -> pd.DataFrame:
    return fato_filtrado[["dias_internacao"]].dropna()


def distribuicao_paciente_viajou(fato_filtrado: pd.DataFrame) -> pd.DataFrame:
    dist = fato_filtrado["paciente_viajou"].value_counts().reset_index()
    dist.columns = ["paciente_viajou", "internacoes"]
    dist["paciente_viajou"] = dist["paciente_viajou"].map({True: "Viajou", False: "Nao viajou"})
    return dist


# funcoes exclusivas dos dados V2 (dependem de dim_diagnostico)


def _fato_com_diagnostico_valido(fato_filtrado: pd.DataFrame) -> pd.DataFrame:
    """Remove internacoes com diagnostico_id=0 (sem correspondencia exata no CID, ~2% do total)."""
    return fato_filtrado[fato_filtrado["diagnostico_id"] != 0]


def top_diagnosticos(
    fato_filtrado: pd.DataFrame, dim_diagnostico: pd.DataFrame, top_n: int = 10
) -> pd.DataFrame:
    """Ranking dos diagnosticos (CID) mais frequentes."""
    valido = _fato_com_diagnostico_valido(fato_filtrado)
    contagem = (
        valido.groupby("diagnostico_id", observed=True)
        .size()
        .reset_index(name="internacoes")
    )
    ranking = contagem.merge(
        dim_diagnostico[["diagnostico_id", "categoria_cid", "descricao_cid"]],
        on="diagnostico_id",
        how="left",
    )
    ranking = ranking.sort_values("internacoes", ascending=False).head(top_n)
    return ranking[["categoria_cid", "descricao_cid", "internacoes"]].reset_index(drop=True)


def distribuicao_por_categoria_diagnostico(
    fato_filtrado: pd.DataFrame, dim_diagnostico: pd.DataFrame, top_n_descricoes: int = 40
) -> pd.DataFrame:
    """Agrupa internacoes por categoria/descricao CID, pro treemap de diagnosticos."""
    valido = _fato_com_diagnostico_valido(fato_filtrado)
    merged = valido[["diagnostico_id"]].merge(
        dim_diagnostico[["diagnostico_id", "categoria_cid", "descricao_cid"]],
        on="diagnostico_id",
        how="left",
    )
    dist = (
        merged.groupby(["categoria_cid", "descricao_cid"], observed=True)
        .size()
        .reset_index(name="internacoes")
        .sort_values("internacoes", ascending=False)
        .head(top_n_descricoes)
    )
    return dist


def evolucao_top_hospitais(
    fato_filtrado: pd.DataFrame, dim_hospital: pd.DataFrame, top_n: int = 8, n_meses_recentes: int = 14
) -> pd.DataFrame:
    """Internacoes por mes dos top_n hospitais, restrito aos n_meses_recentes mais recentes."""
    if fato_filtrado.empty:
        return pd.DataFrame(columns=["periodo", "id_hospital", "nome_municipio_hospital", "internacoes"])

    top_hospitais = (
        fato_filtrado.groupby("id_hospital", observed=True).size().nlargest(top_n).index
    )
    base = fato_filtrado[fato_filtrado["id_hospital"].isin(top_hospitais)].copy()
    base["periodo"] = base["data_internacao"].dt.to_period("M").astype(str)

    periodos_recentes = sorted(base["periodo"].unique())[-n_meses_recentes:]
    base = base[base["periodo"].isin(periodos_recentes)]

    serie = (
        base.groupby(["periodo", "id_hospital"], observed=True)
        .size()
        .reset_index(name="internacoes")
        .merge(dim_hospital[["id_hospital", "nome_municipio_hospital"]], on="id_hospital", how="left")
        .sort_values("periodo")
    )
    serie["id_hospital"] = serie["id_hospital"].astype(str)
    return serie


def mapa_municipios(fato_filtrado: pd.DataFrame, dim_municipio: pd.DataFrame) -> pd.DataFrame:
    """Internacoes por municipio do paciente, com coordenadas para plotagem em mapa."""
    contagem = (
        fato_filtrado.groupby("codigo_municipio_paciente", observed=True)
        .size()
        .reset_index(name="internacoes")
    )
    mapa = contagem.merge(
        dim_municipio[["codigo_municipio", "nome_municipio", "latitude", "longitude"]],
        left_on="codigo_municipio_paciente",
        right_on="codigo_municipio",
        how="left",
    )
    return mapa.dropna(subset=["latitude", "longitude"])


def calcular_risco_ocupacao(
    fato_completo: pd.DataFrame,
    hospitais_filtro: list[str] | None = None,
    offset_dias: int = 0,
    data_referencia: "pd.Timestamp | None" = None,
) -> pd.DataFrame:
    """Ocupacao real por hospital numa janela de 30 dias, com nivel de risco por percentil.

    Usa leitos_totais da V1 (real) em vez da V2 (bug de geracao, ~12-16x maior).
    fato_completo deve ser o DataFrame NAO filtrado por periodo -- so
    data_referencia (o "fim" da janela) respeita o filtro da sidebar.
    offset_dias desloca a janela pra tras (usado pra comparar com o periodo anterior).
    """
    from core.data_loader import load_dim_hospital, load_dim_hospital_v2

    dim_hospital_v1 = load_dim_hospital()
    dim_hospital_v2 = load_dim_hospital_v2()

    # leitos_totais real (V1) casado pelo codigo CNES com zero a esquerda (V2)
    leitos_reais = dim_hospital_v1[["id_hospital", "leitos_totais"]].copy()
    leitos_reais["id_hospital"] = leitos_reais["id_hospital"].astype(str).str.zfill(7)

    hospitais = dim_hospital_v2[["id_hospital", "nome_municipio_hospital", "leitos_totais"]].merge(
        leitos_reais, on="id_hospital", how="left", suffixes=("_v2", "")
    )
    hospitais["leitos_totais"] = hospitais["leitos_totais"].fillna(hospitais["leitos_totais_v2"])
    hospitais = hospitais[hospitais["leitos_totais"] > 0][["id_hospital", "nome_municipio_hospital", "leitos_totais"]]

    if hospitais_filtro:
        hospitais = hospitais[hospitais["id_hospital"].isin(hospitais_filtro)]

    if fato_completo.empty or hospitais.empty:
        return pd.DataFrame(columns=["id_hospital", "nome_municipio_hospital", "leitos_totais", "leitos_ocupados", "leitos_disponiveis", "taxa_ocupacao", "nivel_alerta"])

    fim_disponivel = fato_completo["data_internacao"].max()
    fim_base = min(data_referencia, fim_disponivel) if data_referencia is not None else fim_disponivel
    fim = fim_base - pd.Timedelta(days=offset_dias)
    inicio = fim - pd.Timedelta(days=29)
    tolerancia = inicio - pd.Timedelta(days=90)

    base = fato_completo[fato_completo["data_internacao"] <= fim].copy()
    tem_saida_no_periodo = base["data_saida"] >= inicio
    sem_saida_recente = base["data_saida"].isna() & (base["data_internacao"] >= tolerancia)
    base = base[tem_saida_no_periodo | sem_saida_recente]

    fim_efetivo = base["data_saida"].fillna(fim).clip(upper=fim)
    inicio_efetivo = base["data_internacao"].clip(lower=inicio)
    base["dias_ocupados"] = (fim_efetivo - inicio_efetivo).dt.days.clip(lower=0) + 1

    ocupacao = base.groupby("id_hospital", observed=True)["dias_ocupados"].sum().reset_index()

    resultado = hospitais.merge(ocupacao, on="id_hospital", how="left")
    resultado["dias_ocupados"] = resultado["dias_ocupados"].fillna(0)
    resultado["leitos_ocupados"] = (resultado["dias_ocupados"] / 30).round(1)
    resultado["leitos_disponiveis"] = (resultado["leitos_totais"] - resultado["leitos_ocupados"]).round(1)
    resultado["taxa_ocupacao"] = ((resultado["leitos_ocupados"] / resultado["leitos_totais"]) * 100).round(2)

    percentil = resultado["taxa_ocupacao"].rank(pct=True)
    resultado["nivel_alerta"] = pd.cut(
        percentil, bins=[-0.01, 0.50, 0.75, 0.90, 1.0], labels=["Verde", "Amarelo", "Laranja", "Vermelho"]
    )

    return resultado[
        ["id_hospital", "nome_municipio_hospital", "leitos_totais", "leitos_ocupados", "leitos_disponiveis", "taxa_ocupacao", "nivel_alerta"]
    ].sort_values("taxa_ocupacao", ascending=False)


def _variacao_percentual(atual: float, anterior: float) -> float | None:
    """Variacao percentual de anterior para atual. None se nao da pra calcular (anterior=0)."""
    if anterior == 0:
        return None
    return round((atual - anterior) / anterior * 100, 1)


def calcular_kpis_operacionais(
    fato_completo: pd.DataFrame,
    hospitais_filtro: list[str] | None = None,
    data_referencia: "pd.Timestamp | None" = None,
) -> dict:
    """KPIs do Monitoramento, com variacao vs. periodo anterior (30 dias vs 30 dias antes)."""
    risco_atual = calcular_risco_ocupacao(fato_completo, hospitais_filtro, offset_dias=0, data_referencia=data_referencia)
    risco_anterior = calcular_risco_ocupacao(fato_completo, hospitais_filtro, offset_dias=30, data_referencia=data_referencia)

    fim_disponivel = fato_completo["data_internacao"].max()
    fim_atual = min(data_referencia, fim_disponivel) if data_referencia is not None else fim_disponivel
    inicio_atual = fim_atual - pd.Timedelta(days=29)
    fim_anterior = fim_atual - pd.Timedelta(days=30)
    inicio_anterior = fim_anterior - pd.Timedelta(days=29)

    fato_alvo = fato_completo
    if hospitais_filtro:
        fato_alvo = fato_alvo[fato_alvo["id_hospital"].isin(hospitais_filtro)]

    internacoes_atual = int(
        fato_alvo[(fato_alvo["data_internacao"] >= inicio_atual) & (fato_alvo["data_internacao"] <= fim_atual)].shape[0]
    )
    internacoes_anterior = int(
        fato_alvo[(fato_alvo["data_internacao"] >= inicio_anterior) & (fato_alvo["data_internacao"] <= fim_anterior)].shape[0]
    )

    def _ocupacao_media(risco: pd.DataFrame) -> float:
        if risco.empty or risco["leitos_totais"].sum() == 0:
            return 0.0
        return round(risco["leitos_ocupados"].sum() / risco["leitos_totais"].sum() * 100, 1)

    ocupacao_atual = _ocupacao_media(risco_atual)
    ocupacao_anterior = _ocupacao_media(risco_anterior)

    leitos_disp_atual = round(risco_atual["leitos_disponiveis"].sum(), 0) if not risco_atual.empty else 0
    leitos_disp_anterior = round(risco_anterior["leitos_disponiveis"].sum(), 0) if not risco_anterior.empty else 0

    criticos_atual = int((risco_atual["nivel_alerta"] == "Vermelho").sum()) if not risco_atual.empty else 0
    criticos_anterior = int((risco_anterior["nivel_alerta"] == "Vermelho").sum()) if not risco_anterior.empty else 0

    return {
        "internacoes": internacoes_atual,
        "internacoes_variacao": _variacao_percentual(internacoes_atual, internacoes_anterior),
        "ocupacao_media": ocupacao_atual,
        "ocupacao_media_variacao": _variacao_percentual(ocupacao_atual, ocupacao_anterior),
        "leitos_disponiveis": int(leitos_disp_atual),
        "leitos_disponiveis_variacao": _variacao_percentual(leitos_disp_atual, leitos_disp_anterior),
        "hospitais_criticos": criticos_atual,
        "hospitais_criticos_variacao": criticos_atual - criticos_anterior,  # diferenca em contagem, nao %
    }


def gerar_alertas_inteligentes(risco: pd.DataFrame, top_n: int = 3) -> list[dict]:
    """Monta frases curtas sobre os hospitais mais criticos (regra simples, sem IA)."""
    if risco.empty:
        return []

    top = risco.head(top_n)
    alertas = []
    for _, linha in top.iterrows():
        disponiveis = linha["leitos_disponiveis"]
        if disponiveis < 0:
            texto_leitos = f"{abs(disponiveis):.0f} leitos acima da capacidade oficial"
        else:
            texto_leitos = f"{disponiveis:.0f} leitos disponiveis"
        alertas.append({
            "hospital": linha["id_hospital"],
            "municipio": linha["nome_municipio_hospital"],
            "taxa_ocupacao": linha["taxa_ocupacao"],
            "nivel": linha["nivel_alerta"],
            "texto": f"Ocupacao em {linha['taxa_ocupacao']:.0f}%, {texto_leitos}.",
        })
    return alertas
