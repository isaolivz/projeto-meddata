"""
integracao.py - Geração do Star Schema para o MedData.

Este módulo contém funções para integrar as três fontes de dados transformadas
no modelo dimensional Star Schema:
- DIM_HOSPITAL: Dados dos hospitais (a partir do CNES)
- DIM_MUNICIPIO: Dados dos municípios (a partir do IBGE)
- DIM_TEMPO: Dados de tempo (a partir do SIH)
- FATO_INTERNACAO: Eventos de internação (a partir do SIH)

Uso:
    from integracao import gerar_star_schema
    
    resultados = gerar_star_schema(df_sih, df_cnes, df_ibge, uf='PR', ano=2024, mes=1)
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple
import logging
import sys
import os

# Adiciona src ao path
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent))

# Importa o config
from config import config

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ================================================================
# FUNÇÃO DE UPLOAD PARA OBJECT STORAGE
# ================================================================

def upload_para_object_storage(arquivo_local: Path, objeto_name: str, bucket: str = "meddata-gold"):
    """
    Faz upload de um arquivo para o Object Storage da OCI.
    """
    try:
        import oci
        from oci.config import from_file
        
        config_oci = from_file()
        object_storage = oci.object_storage.ObjectStorageClient(config_oci)
        namespace = object_storage.get_namespace().data
        
        with open(arquivo_local, "rb") as arquivo:
            object_storage.put_object(namespace, bucket, objeto_name, arquivo)
        
        logger.info(f"Upload concluído: {bucket}/{objeto_name}")
        return True
    except Exception as e:
        logger.error(f"Falha no upload: {str(e)}")
        return False


# ================================================================
# 1. GERAR DIM_MUNICIPIO
# ================================================================

def gerar_dim_municipio(df_ibge: pd.DataFrame) -> pd.DataFrame:
    """
    Gera a dimensão de municípios a partir do IBGE.
    
    Args:
        df_ibge: DataFrame do IBGE transformado
    
    Returns:
        DataFrame com a dimensão de municípios
    """
    logger.info("Gerando DIM_MUNICIPIO...")
    
    dim = df_ibge.copy()
    
    # Garantir que não há duplicatas
    dim = dim.drop_duplicates(subset=['codigo_municipio'])
    
    # Tratar nulos
    dim['nome_municipio'] = dim['nome_municipio'].fillna('Não informado')
    dim['latitude'] = dim['latitude'].fillna(0)
    dim['longitude'] = dim['longitude'].fillna(0)
    
    logger.info(f"DIM_MUNICIPIO gerada: {len(dim):,} municípios")
    
    return dim


# ================================================================
# 2. GERAR DIM_HOSPITAL
# ================================================================

def gerar_dim_hospital(df_cnes: pd.DataFrame, df_municipios: pd.DataFrame) -> pd.DataFrame:
    """
    Gera a dimensão de hospitais a partir do CNES.
    
    Args:
        df_cnes: DataFrame do CNES transformado (já agregado)
        df_municipios: DataFrame da DIM_MUNICIPIO (para buscar nome do município)
    
    Returns:
        DataFrame com a dimensão de hospitais
    """
    logger.info("Gerando DIM_HOSPITAL...")
    
    dim = df_cnes.copy()
    
    # Buscar nome do município do hospital a partir da DIM_MUNICIPIO
    dim = dim.merge(
        df_municipios[['codigo_municipio', 'nome_municipio', 'latitude', 'longitude']],
        on='codigo_municipio',
        how='left'
    ).rename(columns={
        'nome_municipio': 'nome_municipio_hospital',
        'latitude': 'latitude_hospital',
        'longitude': 'longitude_hospital'
    })
    
    # Tratar nulos
    dim['nome_municipio_hospital'] = dim['nome_municipio_hospital'].fillna('Não informado')
    dim['latitude_hospital'] = dim['latitude_hospital'].fillna(0)
    dim['longitude_hospital'] = dim['longitude_hospital'].fillna(0)
    
    # Garantir que não há duplicatas
    dim = dim.drop_duplicates(subset=['id_hospital'])
    
    # Reorganizar colunas
    colunas_ordem = [
        'id_hospital',
        'codigo_municipio',
        'nome_municipio_hospital',
        'latitude_hospital',
        'longitude_hospital',
        'leitos_totais',
        'leitos_contratados',
        'leitos_sus',
        'leitos_nao_sus',
        'esfera',
        'tipo_unidade',
        'nivel_hierarquico',
        'natureza_juridica',
        'porte_hospitalar',
        'alta_complexidade',
        'esfera_classificacao',
        'percentual_sus'
    ]
    
    colunas_existentes = [col for col in colunas_ordem if col in dim.columns]
    dim = dim[colunas_existentes]
    
    logger.info(f"DIM_HOSPITAL gerada: {len(dim):,} hospitais")
    
    return dim


# ================================================================
# 3. GERAR DIM_TEMPO
# ================================================================

def gerar_dim_tempo(df_sih: pd.DataFrame) -> pd.DataFrame:
    """
    Gera a dimensão de tempo a partir das datas do SIH.
    
    Args:
        df_sih: DataFrame do SIH transformado
    
    Returns:
        DataFrame com a dimensão de tempo
    """
    logger.info("Gerando DIM_TEMPO...")
    
    # Extrair datas únicas
    datas_unicas = pd.Series(df_sih['data_internacao'].unique()).dropna()
    
    if len(datas_unicas) == 0:
        logger.warning("Nenhuma data encontrada no SIH. Criando DIM_TEMPO vazia.")
        return pd.DataFrame(columns=['data_referencia', 'ano', 'mes', 'trimestre', 'dia_semana', 'ano_mes', 'tempo_id'])
    
    dim = pd.DataFrame({
        'data_referencia': datas_unicas,
        'ano': datas_unicas.dt.year,
        'mes': datas_unicas.dt.month,
        'trimestre': datas_unicas.dt.quarter,
        'dia_semana': datas_unicas.dt.day_name(),
        'ano_mes': datas_unicas.dt.strftime('%Y-%m')
    })
    
    # Adicionar ID sequencial
    dim['tempo_id'] = range(1, len(dim) + 1)
    
    # Ordenar por data
    dim = dim.sort_values('data_referencia').reset_index(drop=True)
    
    logger.info(f"DIM_TEMPO gerada: {len(dim):,} datas únicas")
    
    return dim


# ================================================================
# 4. GERAR FATO_INTERNACAO
# ================================================================

def gerar_fato_internacao(
    df_sih: pd.DataFrame,
    df_hospitais: pd.DataFrame,
    df_municipios: pd.DataFrame,
    df_tempo: pd.DataFrame
) -> pd.DataFrame:
    """
    Gera a tabela fato de internações.
    
    Args:
        df_sih: DataFrame do SIH transformado
        df_hospitais: DataFrame da DIM_HOSPITAL
        df_municipios: DataFrame da DIM_MUNICIPIO
        df_tempo: DataFrame da DIM_TEMPO
    
    Returns:
        DataFrame com a fato de internações
    """
    logger.info("Gerando FATO_INTERNACAO...")
    
    fato = df_sih.copy()
    
    logger.info(f"Base SIH: {len(fato):,} registros")
    
    # ============================================================
    # 1. ADICIONAR CHAVES ESTRANGEIRAS
    # ============================================================
    
    # Buscar dados do hospital (nome, coordenadas)
    fato = fato.merge(
        df_hospitais[['id_hospital', 'codigo_municipio', 'nome_municipio_hospital', 
                      'latitude_hospital', 'longitude_hospital', 'leitos_sus']],
        on='id_hospital',
        how='left'
    )
    logger.info(f"Após merge com hospitais: {len(fato):,} registros")
    
    # Buscar dados do município do paciente
    fato = fato.merge(
        df_municipios[['codigo_municipio', 'nome_municipio', 'latitude', 'longitude']],
        left_on='codigo_municipio_paciente',
        right_on='codigo_municipio',
        how='left',
        suffixes=('', '_paciente_ibge')
    ).rename(columns={
        'nome_municipio': 'nome_municipio_paciente',
        'latitude': 'latitude_paciente',
        'longitude': 'longitude_paciente'
    })
    
    # Remover colunas duplicadas
    if 'codigo_municipio_paciente_ibge' in fato.columns:
        fato.drop(columns=['codigo_municipio_paciente_ibge'], inplace=True)
    
    # Buscar tempo_id da DIM_TEMPO
    fato = fato.merge(
        df_tempo[['data_referencia', 'tempo_id']],
        left_on='data_internacao',
        right_on='data_referencia',
        how='left'
    )
    fato.drop(columns=['data_referencia'], inplace=True, errors='ignore')
    
    logger.info(f"Após merges com dimensões: {len(fato):,} registros")
    
    # ============================================================
    # 2. CALCULAR DISTÂNCIA ESTIMADA (haversine)
    # ============================================================
    
    def haversine(lat1, lon1, lat2, lon2):
        from math import radians, sin, cos, sqrt, atan2
        if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2):
            return np.nan
        R = 6371
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c
    
    fato['distancia_estimada_km'] = fato.apply(
        lambda row: haversine(
            row.get('latitude_hospital', np.nan),
            row.get('longitude_hospital', np.nan),
            row.get('latitude_paciente', np.nan),
            row.get('longitude_paciente', np.nan)
        ),
        axis=1
    )
    
    # ============================================================
    # 3. TRATAMENTO DE NULOS
    # ============================================================
    
    # Tratar nulos de paciente
    fato['nome_municipio_paciente'] = fato['nome_municipio_paciente'].fillna('Não informado')
    fato['latitude_paciente'] = fato['latitude_paciente'].fillna(0)
    fato['longitude_paciente'] = fato['longitude_paciente'].fillna(0)
    fato['distancia_estimada_km'] = fato['distancia_estimada_km'].fillna(0)
    
    # Tratar nulos de hospital (se houver)
    fato['nome_municipio_hospital'] = fato['nome_municipio_hospital'].fillna('Não informado')
    fato['latitude_hospital'] = fato['latitude_hospital'].fillna(0)
    fato['longitude_hospital'] = fato['longitude_hospital'].fillna(0)
    
    # Tratar nulos de diagnóstico
    fato['codigo_diagnostico'] = fato['codigo_diagnostico'].fillna('Não informado')
    
    # ============================================================
    # 4. ADICIONAR ID ÚNICO
    # ============================================================
    
    fato['internacao_id'] = range(1, len(fato) + 1)
    
    # ============================================================
    # 5. REORGANIZAR COLUNAS
    # ============================================================
    
    colunas_ordem = [
        'internacao_id',
        'id_hospital',
        'codigo_municipio_paciente',
        'tempo_id',
        'codigo_diagnostico',
        'data_internacao',
        'data_saida',
        'valor_procedimento',
        'dias_internacao',
        'paciente_viajou',
        'nome_municipio_paciente',
        'latitude_paciente',
        'longitude_paciente',
        'nome_municipio_hospital',
        'latitude_hospital',
        'longitude_hospital',
        'distancia_estimada_km',
        'ano_competencia',
        'mes_competencia',
        'dia_semana',
        'tipo_dia'
    ]
    
    colunas_existentes = [col for col in colunas_ordem if col in fato.columns]
    fato = fato[colunas_existentes]
    
    logger.info(f"FATO_INTERNACAO gerada: {len(fato):,} registros")
    
    return fato


# ================================================================
# 5. SALVAR STAR SCHEMA
# ================================================================

def salvar_star_schema(
    dim_municipio: pd.DataFrame,
    dim_hospital: pd.DataFrame,
    dim_tempo: pd.DataFrame,
    fato_internacao: pd.DataFrame,
    uf: str = None,
    ano: int = None,
    mes: int = None,
    upload: bool = True
) -> Dict[str, Path]:
    """
    Salva as quatro tabelas do Star Schema localmente e no Object Storage.
    """
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if mes is None:
        mes = config.MES
    
    resultados = {}
    
    # Mapeamento de tabelas
    tabelas = {
        'dim_municipio': dim_municipio,
        'dim_hospital': dim_hospital,
        'dim_tempo': dim_tempo,
        'fato_internacao': fato_internacao
    }
    
    for nome, df in tabelas.items():
        if df is not None and len(df) > 0:
            # Caminho local
            caminho = config.PROCESSED_DIR / f"{nome}_{uf}_{ano}_{mes:02d}.parquet"
            df.to_parquet(caminho, index=False)
            resultados[nome] = caminho
            logger.info(f"{nome.upper()} salvo: {caminho} ({len(df):,} registros)")
            
            # Upload para Object Storage
            if upload:
                objeto = f"{nome}/{uf}/{ano}/{mes:02d}/{nome}_{uf}_{ano}_{mes:02d}.parquet"
                upload_para_object_storage(caminho, objeto, "meddata-gold")
    
    return resultados


# ================================================================
# 6. GERAR STAR SCHEMA (PIPELINE COMPLETO)
# ================================================================

def gerar_star_schema(
    df_sih: pd.DataFrame,
    df_cnes: pd.DataFrame,
    df_ibge: pd.DataFrame,
    uf: str = None,
    ano: int = None,
    mes: int = None,
    salvar: bool = True,
    upload: bool = True
) -> Dict[str, pd.DataFrame]:
    """
    Executa o pipeline completo de geração do Star Schema.
    """
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if mes is None:
        mes = config.MES
    
    logger.info("=" * 60)
    logger.info(f"GERANDO STAR SCHEMA PARA {uf} {ano}/{mes:02d}")
    logger.info("=" * 60)
    
    # 1. Gerar dimensões
    logger.info("\n[1/4] Gerando DIM_MUNICIPIO...")
    dim_municipio = gerar_dim_municipio(df_ibge)
    
    logger.info("\n[2/4] Gerando DIM_HOSPITAL...")
    dim_hospital = gerar_dim_hospital(df_cnes, dim_municipio)
    
    logger.info("\n[3/4] Gerando DIM_TEMPO...")
    dim_tempo = gerar_dim_tempo(df_sih)
    
    # 2. Gerar fato
    logger.info("\n[4/4] Gerando FATO_INTERNACAO...")
    fato_internacao = gerar_fato_internacao(df_sih, dim_hospital, dim_municipio, dim_tempo)
    
    # 3. Salvar
    if salvar:
        logger.info("\nSalvando Star Schema...")
        salvar_star_schema(dim_municipio, dim_hospital, dim_tempo, fato_internacao, uf, ano, mes, upload)
    
    # 4. Resumo
    logger.info("\n" + "=" * 60)
    logger.info("RESUMO DO STAR SCHEMA")
    logger.info("-" * 60)
    logger.info(f"DIM_MUNICIPIO    : {len(dim_municipio):>8,} registros | {len(dim_municipio.columns):>3} colunas")
    logger.info(f"DIM_HOSPITAL     : {len(dim_hospital):>8,} registros | {len(dim_hospital.columns):>3} colunas")
    logger.info(f"DIM_TEMPO        : {len(dim_tempo):>8,} registros | {len(dim_tempo.columns):>3} colunas")
    logger.info(f"FATO_INTERNACAO  : {len(fato_internacao):>8,} registros | {len(fato_internacao.columns):>3} colunas")
    logger.info("=" * 60)
    
    return {
        'dim_municipio': dim_municipio,
        'dim_hospital': dim_hospital,
        'dim_tempo': dim_tempo,
        'fato_internacao': fato_internacao
    }


# ================================================================
# 7. EXECUÇÃO DIRETA COM ARGPARSE
# ================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Integração e geração do Star Schema para o MedData")
    parser.add_argument('--uf', type=str, default=config.UF, help='UF do estado')
    parser.add_argument('--ano', type=int, default=config.ANO, help='Ano dos dados')
    parser.add_argument('--mes', type=int, default=config.MES, help='Mês dos dados')
    parser.add_argument('--upload', action='store_true', default=True, help='Fazer upload para OCI')
    parser.add_argument('--no-upload', action='store_false', dest='upload', help='Não fazer upload para OCI')
    args = parser.parse_args()
    
    print("=" * 60)
    print("INICIANDO INTEGRAÇÃO E STAR SCHEMA")
    print(f"UF: {args.uf} | Ano: {args.ano} | Mês: {args.mes:02d}")
    print(f"Upload para OCI: {'SIM' if args.upload else 'NÃO'}")
    print("=" * 60)
    
    # Atualizar config
    config.UF = args.uf
    config.ANO = args.ano
    config.MES = args.mes
    
    # Carregar dados transformados
    from transformacao import transformar_sih, transformar_cnes, transformar_ibge
    from ingestao import baixar_sih, baixar_cnes_leitos, baixar_ibge
    
    print("\nBaixando dados brutos...")
    df_sih_raw = baixar_sih(args.uf, args.ano, args.mes, upload=False)
    df_cnes_raw = baixar_cnes_leitos(args.uf, args.ano, args.mes, upload=False)
    df_ibge_raw = baixar_ibge(args.uf, upload=False)
    
    if df_sih_raw is None or df_cnes_raw is None or df_ibge_raw is None:
        print("❌ Falha ao carregar dados brutos.")
        sys.exit(1)
    
    print("\nTransformando dados...")
    df_sih = transformar_sih(df_sih_raw, args.uf, args.ano, args.mes)
    df_cnes = transformar_cnes(df_cnes_raw, args.uf, args.ano, args.mes)
    df_ibge = transformar_ibge(df_ibge_raw, args.uf)
    
    # Gerar Star Schema
    resultados = gerar_star_schema(
        df_sih=df_sih,
        df_cnes=df_cnes,
        df_ibge=df_ibge,
        uf=args.uf,
        ano=args.ano,
        mes=args.mes,
        salvar=True,
        upload=args.upload
    )
    
    print("\n" + "=" * 60)
    print("RESUMO DOS RESULTADOS")
    print("=" * 60)
    for nome, df in resultados.items():
        print(f"{nome.upper():15} | {len(df):>8,} registros | {len(df.columns):>3} colunas")
    
    print("\n✅ Star Schema gerado com sucesso!")
    sys.exit(0)