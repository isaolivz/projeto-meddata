"""
validacao.py - Validacao formal do Star Schema (requisito do projeto).

Este modulo verifica:
- Integridade referencial (FKs)
- Dados nulos em colunas obrigatorias
- Duplicatas em chaves primarias
- Consistencia dos dados
- Gera relatorio de validacao
"""

import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent))

from config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def carregar_tabelas(uf=None, ano=None, mes=None):
    """Carrega as tabelas do Star Schema da pasta processed."""
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES

    caminhos = {
        'dim_municipio': config.PROCESSED_DIR / f"dim_municipio_{uf}_{ano}_{mes:02d}.parquet",
        'dim_hospital': config.PROCESSED_DIR / f"dim_hospital_{uf}_{ano}_{mes:02d}.parquet",
        'dim_tempo': config.PROCESSED_DIR / f"dim_tempo_{uf}_{ano}_{mes:02d}.parquet",
        'fato_internacao': config.PROCESSED_DIR / f"fato_internacao_{uf}_{ano}_{mes:02d}.parquet"
    }

    dados = {}
    for nome, caminho in caminhos.items():
        if caminho.exists():
            dados[nome] = pd.read_parquet(caminho)
            logger.info(f"Carregado: {nome} ({len(dados[nome]):,} registros)")
        else:
            logger.error(f"Arquivo nao encontrado: {caminho}")
            dados[nome] = None

    return dados


def validar_integridade_referencial(fato, dim_hospital, dim_municipio, dim_tempo):
    """Valida as chaves estrangeiras."""
    erros = []
    
    # FK para DIM_HOSPITAL
    if fato is not None and dim_hospital is not None:
        ids_hospitais = set(dim_hospital['id_hospital'])
        ids_fato = set(fato['id_hospital'])
        ids_invalidos = ids_fato - ids_hospitais
        if ids_invalidos:
            erros.append(f"FK_HOSPITAL: {len(ids_invalidos)} ids de hospital sem correspondencia")
    
    # FK para DIM_TEMPO
    if fato is not None and dim_tempo is not None:
        ids_tempo = set(dim_tempo['tempo_id'])
        ids_fato = set(fato['tempo_id'])
        ids_invalidos = ids_fato - ids_tempo
        if ids_invalidos:
            erros.append(f"FK_TEMPO: {len(ids_invalidos)} ids de tempo sem correspondencia")
    
    return erros


def validar_chaves_primarias(dim_municipio, dim_hospital, dim_tempo, fato):
    """Valida duplicatas nas chaves primarias."""
    erros = []
    
    if dim_municipio is not None:
        dup = dim_municipio['codigo_municipio'].duplicated().sum()
        if dup > 0:
            erros.append(f"DIM_MUNICIPIO: {dup} codigos duplicados")
    
    if dim_hospital is not None:
        dup = dim_hospital['id_hospital'].duplicated().sum()
        if dup > 0:
            erros.append(f"DIM_HOSPITAL: {dup} ids duplicados")
    
    if dim_tempo is not None:
        dup = dim_tempo['tempo_id'].duplicated().sum()
        if dup > 0:
            erros.append(f"DIM_TEMPO: {dup} ids duplicados")
    
    if fato is not None:
        dup = fato['internacao_id'].duplicated().sum()
        if dup > 0:
            erros.append(f"FATO_INTERNACAO: {dup} ids duplicados")
    
    return erros


def validar_nulos(dim_municipio, dim_hospital, dim_tempo, fato):
    """Valida colunas obrigatorias sem nulos."""
    erros = []
    avisos = []
    
    # DIM_MUNICIPIO
    if dim_municipio is not None:
        for col in ['codigo_municipio', 'nome_municipio', 'uf']:
            nulos = dim_municipio[col].isna().sum()
            if nulos > 0:
                erros.append(f"DIM_MUNICIPIO: {nulos} nulos em {col}")
    
    # DIM_HOSPITAL
    if dim_hospital is not None:
        for col in ['id_hospital', 'leitos_totais']:
            nulos = dim_hospital[col].isna().sum()
            if nulos > 0:
                erros.append(f"DIM_HOSPITAL: {nulos} nulos em {col}")
    
    # DIM_TEMPO
    if dim_tempo is not None:
        for col in ['tempo_id', 'data_referencia', 'ano', 'mes']:
            nulos = dim_tempo[col].isna().sum()
            if nulos > 0:
                erros.append(f"DIM_TEMPO: {nulos} nulos em {col}")
    
    # FATO_INTERNACAO
    if fato is not None:
        for col in ['id_hospital', 'data_internacao', 'tempo_id']:
            nulos = fato[col].isna().sum()
            if nulos > 0:
                erros.append(f"FATO_INTERNACAO: {nulos} nulos em {col}")
    
    # Avisos: colunas com muitos nulos (>= 50%)
    if fato is not None:
        for col in ['data_saida', 'codigo_diagnostico']:
            if col in fato.columns:
                nulos = fato[col].isna().sum()
                if nulos > 0 and (nulos / len(fato)) > 0.5:
                    avisos.append(f"FATO_INTERNACAO: {nulos} nulos em {col} ({nulos/len(fato)*100:.1f}%)")
    
    return erros, avisos


def validar_consistencia(dim_municipio, dim_hospital, dim_tempo, fato):
    """Valida consistencia dos dados."""
    erros = []
    avisos = []
    
    # DIM_MUNICIPIO: latitude/longitude validas
    if dim_municipio is not None:
        invalidas = dim_municipio[
            (dim_municipio['latitude'] < -90) | 
            (dim_municipio['latitude'] > 90)
        ]
        if len(invalidas) > 0:
            erros.append(f"DIM_MUNICIPIO: {len(invalidas)} latitudes invalidas")
    
    # DIM_HOSPITAL: leitos nao negativos
    if dim_hospital is not None:
        negativos = dim_hospital[dim_hospital['leitos_totais'] < 0]
        if len(negativos) > 0:
            erros.append(f"DIM_HOSPITAL: {len(negativos)} registros com leitos negativos")
    
    # DIM_HOSPITAL: percentual SUS entre 0 e 100
    if dim_hospital is not None and 'percentual_sus' in dim_hospital.columns:
        invalidos = dim_hospital[
            (dim_hospital['percentual_sus'] < 0) | 
            (dim_hospital['percentual_sus'] > 100)
        ]
        if len(invalidos) > 0:
            erros.append(f"DIM_HOSPITAL: {len(invalidos)} registros com percentual SUS invalido")
    
    # DIM_TEMPO: apenas 2024
    if dim_tempo is not None:
        anos_invalidos = dim_tempo[dim_tempo['ano'] != 2024]
        if len(anos_invalidos) > 0:
            erros.append(f"DIM_TEMPO: {len(anos_invalidos)} registros com ano diferente de 2024")
    
    # FATO_INTERNACAO: dias de internacao nao negativos
    if fato is not None and 'dias_internacao' in fato.columns:
        negativos = fato[fato['dias_internacao'] < 0]
        if len(negativos) > 0:
            erros.append(f"FATO_INTERNACAO: {len(negativos)} registros com dias negativos")
    
    return erros, avisos


def gerar_relatorio(dados, erros, avisos):
    """Gera relatorio de validacao."""
    logger.info("=" * 60)
    logger.info("RELATORIO DE VALIDACAO")
    logger.info("=" * 60)
    
    # Estatisticas das tabelas
    for nome, df in dados.items():
        if df is not None:
            logger.info(f"{nome.upper():20} | {len(df):>8,} registros | {len(df.columns):>3} colunas")
    
    logger.info("-" * 60)
    
    if erros:
        logger.error(f"❌ {len(erros)} ERROS encontrados:")
        for erro in erros:
            logger.error(f"  - {erro}")
    else:
        logger.info("✅ Nenhum erro encontrado")
    
    if avisos:
        logger.warning(f"⚠️ {len(avisos)} AVISOS:")
        for aviso in avisos:
            logger.warning(f"  - {aviso}")
    
    logger.info("=" * 60)
    
    if erros:
        logger.error("❌ VALIDACAO REPROVADA - Corrija os erros antes de carregar.")
    else:
        logger.info("✅ VALIDACAO APROVADA - Dados prontos para carga!")


def executar_validacao(uf=None, ano=None, mes=None):
    """Executa o pipeline completo de validacao."""
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES
    
    logger.info("=" * 60)
    logger.info("INICIANDO VALIDACAO DO STAR SCHEMA")
    logger.info(f"UF: {uf} | Ano: {ano} | Mes: {mes:02d}")
    logger.info("=" * 60)
    
    # Carregar dados
    dados = carregar_tabelas(uf, ano, mes)
    
    # Verificar se todos os dados foram carregados
    if any(df is None for df in dados.values()):
        logger.error("❌ Falha ao carregar uma ou mais tabelas")
        return False, ["Falha no carregamento dos dados"]
    
    # Executar validacoes
    erros = []
    avisos = []
    
    # 1. Integridade referencial
    erros.extend(validar_integridade_referencial(
        dados['fato_internacao'],
        dados['dim_hospital'],
        dados['dim_municipio'],
        dados['dim_tempo']
    ))
    
    # 2. Chaves primarias
    erros.extend(validar_chaves_primarias(
        dados['dim_municipio'],
        dados['dim_hospital'],
        dados['dim_tempo'],
        dados['fato_internacao']
    ))
    
    # 3. Nulos
    e, a = validar_nulos(
        dados['dim_municipio'],
        dados['dim_hospital'],
        dados['dim_tempo'],
        dados['fato_internacao']
    )
    erros.extend(e)
    avisos.extend(a)
    
    # 4. Consistencia
    e, a = validar_consistencia(
        dados['dim_municipio'],
        dados['dim_hospital'],
        dados['dim_tempo'],
        dados['fato_internacao']
    )
    erros.extend(e)
    avisos.extend(a)
    
    # Gerar relatorio
    gerar_relatorio(dados, erros, avisos)
    
    return len(erros) == 0, erros


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validacao do Star Schema")
    parser.add_argument('--uf', type=str, default=config.UF, help='UF do estado')
    parser.add_argument('--ano', type=int, default=config.ANO, help='Ano dos dados')
    parser.add_argument('--mes', type=int, default=config.MES, help='Mes dos dados')
    args = parser.parse_args()
    
    config.UF = args.uf
    config.ANO = args.ano
    config.MES = args.mes
    
    valido, erros = executar_validacao(args.uf, args.ano, args.mes)
    
    if valido:
        sys.exit(0)
    else:
        sys.exit(1)