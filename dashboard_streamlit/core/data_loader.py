"""Carrega os dados locais (CSV) do MedData em DataFrames Pandas."""
from __future__ import annotations

import os
import urllib.request

import pandas as pd
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# arquivos grandes demais pro GitHub normal (>100MB) -- ficam num GitHub
# Release em vez do repositorio, e sao baixados aqui na primeira vez que o
# app roda (ex.: no Streamlit Cloud, onde a pasta data/ nao tem esses 2
# arquivos). Localmente, se o arquivo ja existe em data/, nunca baixa nada.
_RELEASE_BASE_URL = "https://github.com/isaolivz/meddata-project/releases/download/dados-v1"
_ARQUIVOS_GRANDES = {
    "fato_internacao_SP_2024_01_certo.csv": f"{_RELEASE_BASE_URL}/fato_internacao_SP_2024_01_certo.csv",
    "fato_internacao_SP_2024_01_v2.csv": f"{_RELEASE_BASE_URL}/fato_internacao_SP_2024_01_v2.csv",
}


def _garantir_arquivo(caminho: str) -> str:
    """Baixa o arquivo do GitHub Release se ele nao existir localmente."""
    nome = os.path.basename(caminho)
    if os.path.exists(caminho) or nome not in _ARQUIVOS_GRANDES:
        return caminho

    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with st.spinner(f"Baixando {nome} (primeira vez, pode levar um minuto)..."):
        urllib.request.urlretrieve(_ARQUIVOS_GRANDES[nome], caminho)
    return caminho

DIM_HOSPITAL_FILE = os.path.join(DATA_DIR, "dim_hospital_SP_2024_01_certo.csv")
DIM_MUNICIPIO_FILE = os.path.join(DATA_DIR, "dim_municipio_SP_2024_01_certo.csv")
DIM_TEMPO_FILE = os.path.join(DATA_DIR, "dim_tempo_SP_2024_01.csv")
FATO_INTERNACAO_FILE = os.path.join(DATA_DIR, "fato_internacao_SP_2024_01_certo.csv")

# arquivos V2 (dados atualizados, com diagnosticos)
DIM_HOSPITAL_V2_FILE = os.path.join(DATA_DIR, "dim_hospital_SP_2024_01_v2.csv")
DIM_MUNICIPIO_V2_FILE = os.path.join(DATA_DIR, "dim_municipio_SP_2024_01_v2.csv")
DIM_TEMPO_V2_FILE = os.path.join(DATA_DIR, "dim_tempo_SP_2024_01_v2.csv")
DIM_DIAGNOSTICO_V2_FILE = os.path.join(DATA_DIR, "dim_diagnostico_SP_2024_01_v2.csv")
FATO_INTERNACAO_V2_FILE = os.path.join(DATA_DIR, "fato_internacao_SP_2024_01_v2.csv")

# troca pra "v1" e reinicia o app pra reverter (as funcoes V1 abaixo continuam intactas)
VERSAO_ATIVA = "v2"


def _br_decimal_to_float(series: pd.Series) -> pd.Series:
    """Converte coluna numerica no formato BR ("-23,5324") para float."""
    return pd.to_numeric(
        series.astype(str).str.replace(",", ".", regex=False), errors="coerce"
    )


@st.cache_data(show_spinner="Carregando hospitais...")
def load_dim_hospital() -> pd.DataFrame:
    df = pd.read_csv(DIM_HOSPITAL_FILE, sep=";", encoding="utf-8-sig")

    df["latitude_hospital"] = _br_decimal_to_float(df["latitude_hospital"])
    df["longitude_hospital"] = _br_decimal_to_float(df["longitude_hospital"])
    df["percentual_sus"] = _br_decimal_to_float(df["percentual_sus"])

    df["id_hospital"] = df["id_hospital"].astype("int64")
    df["codigo_municipio"] = df["codigo_municipio"].astype("int64")
    for col in ("uf_hospital", "tipo_unidade", "natureza_juridica", "porte_hospitalar", "alta_complexidade"):
        df[col] = df[col].astype("category")

    return df


@st.cache_data(show_spinner="Carregando municipios...")
def load_dim_municipio() -> pd.DataFrame:
    df = pd.read_csv(DIM_MUNICIPIO_FILE, sep=";", encoding="utf-8-sig")

    df["latitude"] = _br_decimal_to_float(df["latitude"])
    df["longitude"] = _br_decimal_to_float(df["longitude"])
    df["codigo_municipio"] = df["codigo_municipio"].astype("int64")
    df["uf"] = df["uf"].astype("category")

    return df


@st.cache_data(show_spinner="Carregando calendario...")
def load_dim_tempo() -> pd.DataFrame:
    df = pd.read_csv(DIM_TEMPO_FILE, sep=",", encoding="utf-8-sig")

    df["data_referencia"] = pd.to_datetime(df["data_referencia"], errors="coerce")
    df["tempo_id"] = df["tempo_id"].astype("int64")
    df["dia_semana"] = df["dia_semana"].astype("category")
    df["ano_mes"] = df["ano_mes"].astype("category")

    return df


# colunas mantidas da FATO_INTERNACAO (o resto e redundante, ja vem via join)
_FATO_USECOLS = [
    "internacao_id",
    "id_hospital",
    "codigo_municipio_paciente",
    "tempo_id",
    "codigo_diagnostico",
    "data_internacao",
    "data_saida",
    "valor_procedimento",
    "dias_internacao",
    "paciente_viajou",
    "distancia_estimada_km",
    "ano_competencia",
    "mes_competencia",
]


@st.cache_data(show_spinner="Carregando internacoes (pode levar alguns segundos)...")
def load_fato_internacao() -> pd.DataFrame:
    df = pd.read_csv(
        _garantir_arquivo(FATO_INTERNACAO_FILE),
        sep=";",
        encoding="utf-8-sig",
        usecols=_FATO_USECOLS,
        dtype={
            "internacao_id": "int64",
            "id_hospital": "int64",
            "codigo_municipio_paciente": "int64",
            "tempo_id": "int64",
            "codigo_diagnostico": "category",
            "dias_internacao": "int32",
            "ano_competencia": "int16",
            "mes_competencia": "int8",
        },
    )

    df["data_internacao"] = pd.to_datetime(df["data_internacao"], errors="coerce")
    df["data_saida"] = pd.to_datetime(df["data_saida"], errors="coerce")
    df["valor_procedimento"] = _br_decimal_to_float(df["valor_procedimento"]).astype("float32")
    df["distancia_estimada_km"] = _br_decimal_to_float(df["distancia_estimada_km"]).astype("float32")
    df["paciente_viajou"] = df["paciente_viajou"].astype("bool")

    return df


def load_all() -> dict[str, pd.DataFrame]:
    """Carrega os datasets ativos (V1 ou V2, conforme VERSAO_ATIVA)."""
    if VERSAO_ATIVA == "v2":
        return {
            "dim_hospital": load_dim_hospital_v2(),
            "dim_municipio": load_dim_municipio_v2(),
            "dim_tempo": load_dim_tempo_v2(),
            "dim_diagnostico": load_dim_diagnostico_v2(),
            "fato_internacao": load_fato_internacao_v2(),
        }
    return {
        "dim_hospital": load_dim_hospital(),
        "dim_municipio": load_dim_municipio(),
        "dim_tempo": load_dim_tempo(),
        "fato_internacao": load_fato_internacao(),
    }


# loaders V2 -- ids de hospital/municipio como texto, com diagnosticos


@st.cache_data(show_spinner="Carregando hospitais (v2)...")
def load_dim_hospital_v2() -> pd.DataFrame:
    df = pd.read_csv(DIM_HOSPITAL_V2_FILE, sep=";", encoding="utf-8-sig", dtype={"id_hospital": "str", "codigo_municipio": "str"})
    df = df.copy()

    df["latitude_hospital"] = _br_decimal_to_float(df["latitude_hospital"])
    df["longitude_hospital"] = _br_decimal_to_float(df["longitude_hospital"])
    df["percentual_sus"] = _br_decimal_to_float(df["percentual_sus"])

    for col in ("uf_hospital", "tipo_unidade", "natureza_juridica", "porte_hospitalar", "alta_complexidade"):
        df[col] = df[col].astype("category")

    return df


@st.cache_data(show_spinner="Carregando municipios (v2)...")
def load_dim_municipio_v2() -> pd.DataFrame:
    df = pd.read_csv(DIM_MUNICIPIO_V2_FILE, sep=";", encoding="utf-8-sig", dtype={"codigo_municipio": "str"})
    df = df.copy()

    df["latitude"] = _br_decimal_to_float(df["latitude"])
    df["longitude"] = _br_decimal_to_float(df["longitude"])
    df["uf"] = df["uf"].astype("category")

    return df


@st.cache_data(show_spinner="Carregando calendario (v2)...")
def load_dim_tempo_v2() -> pd.DataFrame:
    df = pd.read_csv(DIM_TEMPO_V2_FILE, sep=";", encoding="utf-8-sig")

    df["data_referencia"] = pd.to_datetime(df["data_referencia"], errors="coerce")
    df["tempo_id"] = df["tempo_id"].astype("int64")
    df["dia_semana"] = df["dia_semana"].astype("category")
    df["ano_mes"] = df["ano_mes"].astype("category")

    return df


@st.cache_data(show_spinner="Carregando diagnosticos (v2)...")
def load_dim_diagnostico_v2() -> pd.DataFrame:
    df = pd.read_csv(DIM_DIAGNOSTICO_V2_FILE, sep=";", encoding="utf-8-sig")

    df["diagnostico_id"] = df["diagnostico_id"].astype("int32")
    df["categoria_cid"] = df["categoria_cid"].astype("category")

    return df


# colunas mantidas da FATO_INTERNACAO_V2 (o resto e redundante, ja vem via join)
_FATO_V2_USECOLS = [
    "internacao_id",
    "id_hospital",
    "codigo_municipio_paciente",
    "tempo_id",
    "diagnostico_id",
    "codigo_diagnostico",
    "data_internacao",
    "data_saida",
    "valor_procedimento",
    "dias_internacao",
    "paciente_viajou",
    "distancia_estimada_km",
    "ano_competencia",
    "mes_competencia",
]


@st.cache_data(show_spinner="Carregando internacoes v2 (pode levar alguns segundos)...")
def load_fato_internacao_v2() -> pd.DataFrame:
    df = pd.read_csv(
        _garantir_arquivo(FATO_INTERNACAO_V2_FILE),
        sep=";",
        encoding="utf-8-sig",
        usecols=_FATO_V2_USECOLS,
        dtype={
            "internacao_id": "int64",
            "id_hospital": "str",
            "codigo_municipio_paciente": "str",
            "tempo_id": "int64",
            "diagnostico_id": "int32",
            "codigo_diagnostico": "category",
            "dias_internacao": "int32",
            "ano_competencia": "int16",
            "mes_competencia": "int8",
        },
    )

    df["data_internacao"] = pd.to_datetime(df["data_internacao"], errors="coerce")
    df["data_saida"] = pd.to_datetime(df["data_saida"], errors="coerce")
    df["valor_procedimento"] = _br_decimal_to_float(df["valor_procedimento"]).astype("float32")
    df["distancia_estimada_km"] = _br_decimal_to_float(df["distancia_estimada_km"]).astype("float32")

    if df["paciente_viajou"].dtype != bool:
        df["paciente_viajou"] = df["paciente_viajou"].astype(str).str.strip().str.lower().eq("true")

    return df
