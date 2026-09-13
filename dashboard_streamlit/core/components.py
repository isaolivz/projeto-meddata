"""Componentes de UI reutilizaveis entre as paginas do MedData."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.consultas import Filtros


def sidebar_filtros(dim_hospital: pd.DataFrame, dim_municipio: pd.DataFrame, fato: pd.DataFrame) -> Filtros:
    st.sidebar.header("Filtros")

    data_min = fato["data_internacao"].min()
    data_max = fato["data_internacao"].max()

    periodo = st.sidebar.date_input(
        "Periodo (data de internacao)",
        value=(data_min.date(), data_max.date()),
        min_value=data_min.date(),
        max_value=data_max.date(),
    )
    if isinstance(periodo, tuple) and len(periodo) == 2:
        data_inicio, data_fim = pd.Timestamp(periodo[0]), pd.Timestamp(periodo[1])
    else:
        data_inicio, data_fim = pd.Timestamp(data_min), pd.Timestamp(data_max)

    municipios_disponiveis = (
        dim_municipio[dim_municipio["codigo_municipio"].isin(fato["codigo_municipio_paciente"].unique())]
        .sort_values("nome_municipio")
    )
    municipios_selecionados = st.sidebar.multiselect(
        "Municipio (do paciente)",
        options=municipios_disponiveis["codigo_municipio"].tolist(),
        format_func=lambda c: municipios_disponiveis.loc[
            municipios_disponiveis["codigo_municipio"] == c, "nome_municipio"
        ].iloc[0],
    )

    hospitais_disponiveis = sorted(dim_hospital["id_hospital"].unique().tolist())
    hospitais_selecionados = st.sidebar.multiselect(
        "Hospital (codigo CNES)",
        options=hospitais_disponiveis,
    )

    return Filtros(
        data_inicio=data_inicio,
        data_fim=data_fim,
        municipios=municipios_selecionados or None,
        hospitais=hospitais_selecionados or None,
    )
