"""
transformacao.py - Limpeza e padronização das fontes de dados do MedData.

Este módulo contém funções para transformar cada fonte de dados individualmente:
- SIH/SUS: Limpeza, padronização de datas, códigos, criação de features
- CNES: Padronização de colunas, agregação por hospital
- IBGE: Padronização de códigos, seleção de colunas

Cada função retorna um DataFrame limpo e padronizado, pronto para ser integrado.
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Tuple
import logging
from datetime import datetime
import sys
import os
import tempfile

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
# 1. TRANSFORMAÇÃO DO SIH/SUS (com mapeamento SP_ que sempre funcionou)
# ================================================================

def transformar_sih(
    df: pd.DataFrame, 
    uf: str = None, 
    ano: int = None, 
    mes: int = None
) -> pd.DataFrame:
    """
    Limpa e padroniza os dados brutos do SIH/SUS.
    
    Etapas:
    1. Seleção das colunas essenciais (SP_GESTOR, SP_CNES, etc.)
    2. Conversão de tipos (datas, números)
    3. Padronização de códigos (CNES, municípios)
    4. Criação de features derivadas (dias de internação, etc.)
    5. Remoção de duplicatas
    """
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if mes is None:
        mes = config.MES
    
    logger.info(f"Transformando SIH: {len(df):,} registros para {uf} {ano}/{mes:02d}")
    
    # ============================================================
    # 1. MAPEAMENTO DE COLUNAS (usando os nomes que SEMPRE funcionaram)
    # ============================================================
    colunas_essenciais = [
        'SP_GESTOR',    # Código do município gestor
        'SP_CNES',      # Código CNES do hospital
        'SP_CIDPRI',    # CID-10 principal
        'SP_DTINTER',   # Data de internação
        'SP_DTSAIDA',   # Data de alta
        'SP_VALATO',    # Valor do procedimento
        'SP_M_PAC',     # Município do paciente
        'SP_AA',        # Ano de competência
        'SP_MM'         # Mês de competência
    ]
    
    # Verificar quais colunas existem
    colunas_existentes = [col for col in colunas_essenciais if col in df.columns]
    colunas_faltantes = [col for col in colunas_essenciais if col not in df.columns]
    
    if colunas_faltantes:
        logger.warning(f"Colunas não encontradas: {colunas_faltantes}")
        logger.info(f"Colunas disponíveis: {df.columns.tolist()[:10]}...")
    
    # Selecionar colunas existentes
    df_clean = df[colunas_existentes].copy()
    
    # ============================================================
    # 2. CONVERSÃO DE TIPOS
    # ============================================================
    
    # Converter datas
    if 'SP_DTINTER' in df_clean.columns:
        df_clean['SP_DTINTER'] = pd.to_datetime(df_clean['SP_DTINTER'], format='%Y%m%d', errors='coerce')
    if 'SP_DTSAIDA' in df_clean.columns:
        df_clean['SP_DTSAIDA'] = pd.to_datetime(df_clean['SP_DTSAIDA'], format='%Y%m%d', errors='coerce')
    
    # Converter valores numéricos
    if 'SP_VALATO' in df_clean.columns:
        df_clean['SP_VALATO'] = pd.to_numeric(df_clean['SP_VALATO'], errors='coerce')
    if 'SP_AA' in df_clean.columns:
        df_clean['SP_AA'] = pd.to_numeric(df_clean['SP_AA'], errors='coerce').fillna(ano).astype(int)
    if 'SP_MM' in df_clean.columns:
        df_clean['SP_MM'] = pd.to_numeric(df_clean['SP_MM'], errors='coerce').fillna(mes).astype(int)
    
    # ============================================================
    # 3. PADRONIZAÇÃO DE CÓDIGOS
    # ============================================================
    
    if 'SP_CNES' in df_clean.columns:
        df_clean['SP_CNES'] = df_clean['SP_CNES'].astype(str).str.zfill(7)
    if 'SP_GESTOR' in df_clean.columns:
        df_clean['SP_GESTOR'] = df_clean['SP_GESTOR'].astype(str).str.zfill(6)
    if 'SP_M_PAC' in df_clean.columns:
        df_clean['SP_M_PAC'] = df_clean['SP_M_PAC'].astype(str).str.zfill(6)
    
    # ============================================================
    # 4. RENOMEAR COLUNAS
    # ============================================================
    
    mapeamento_colunas = {
        'SP_GESTOR': 'codigo_municipio',
        'SP_CNES': 'id_hospital',
        'SP_CIDPRI': 'codigo_diagnostico',
        'SP_DTINTER': 'data_internacao',
        'SP_DTSAIDA': 'data_saida',
        'SP_VALATO': 'valor_procedimento',
        'SP_M_PAC': 'codigo_municipio_paciente',
        'SP_AA': 'ano_competencia',
        'SP_MM': 'mes_competencia'
    }
    
    # Renomear apenas colunas que existem
    mapeamento_existente = {k: v for k, v in mapeamento_colunas.items() if k in df_clean.columns}
    df_clean.rename(columns=mapeamento_existente, inplace=True)
    
    logger.info(f"Colunas selecionadas: {len(df_clean.columns)}")
    
    # ============================================================
    # 5. CRIAÇÃO DE FEATURES DERIVADAS
    # ============================================================
    
    # Dias de internação
    if 'data_internacao' in df_clean.columns and 'data_saida' in df_clean.columns:
        df_clean['dias_internacao'] = (df_clean['data_saida'] - df_clean['data_internacao']).dt.days
        df_clean['dias_internacao'] = df_clean['dias_internacao'].fillna(0).clip(lower=0).astype(int)
    
    # Paciente viajou
    if 'codigo_municipio' in df_clean.columns and 'codigo_municipio_paciente' in df_clean.columns:
        df_clean['paciente_viajou'] = (
            df_clean['codigo_municipio_paciente'] != df_clean['codigo_municipio']
        )
    
    # Dia da semana
    if 'data_internacao' in df_clean.columns:
        df_clean['dia_semana'] = df_clean['data_internacao'].dt.day_name()
        df_clean['tipo_dia'] = df_clean['dia_semana'].apply(
            lambda x: 'Fim de Semana' if x in ['Saturday', 'Sunday'] else 'Dia Util'
        )
    
    # Mes/ano (como string)
    if 'ano_competencia' in df_clean.columns and 'mes_competencia' in df_clean.columns:
        df_clean['ano_mes'] = df_clean['ano_competencia'].astype(str) + '-' + df_clean['mes_competencia'].astype(str).str.zfill(2)
    
    # ============================================================
    # 6. REMOÇÃO DE DUPLICATAS E REGISTROS INVÁLIDOS
    # ============================================================
    
    antes = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    removidos = antes - len(df_clean)
    if removidos > 0:
        logger.info(f"Duplicatas removidas: {removidos:,} ({removidos/antes*100:.2f}%)")
    
    # Remover registros sem data de internação
    if 'data_internacao' in df_clean.columns:
        antes = len(df_clean)
        df_clean = df_clean[df_clean['data_internacao'].notna()]
        removidos = antes - len(df_clean)
        if removidos > 0:
            logger.info(f"Registros sem data removidos: {removidos:,}")
    
    # Remover registros sem CNES
    if 'id_hospital' in df_clean.columns:
        antes = len(df_clean)
        df_clean = df_clean[df_clean['id_hospital'].notna()]
        removidos = antes - len(df_clean)
        if removidos > 0:
            logger.info(f"Registros sem CNES removidos: {removidos:,}")
    
    logger.info(f"SIH transformado: {len(df_clean):,} registros")
    
    return df_clean


# ================================================================
# 2. TRANSFORMAÇÃO DO CNES
# ================================================================

def transformar_cnes(
    df: pd.DataFrame, 
    uf: str = None, 
    ano: int = None, 
    mes: int = None
) -> pd.DataFrame:
    """
    Limpa e padroniza os dados brutos do CNES, agregando por hospital.
    """
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if mes is None:
        mes = config.MES
    
    logger.info(f"Transformando CNES: {len(df):,} registros para {uf} {ano}/{mes:02d}")
    
    # ============================================================
    # 1. PADRONIZAR NOMES DAS COLUNAS
    # ============================================================
    df.columns = [col.upper() for col in df.columns]
    
    # ============================================================
    # 2. MAPEAMENTO DE COLUNAS
    # ============================================================
    colunas_cnes = {
        'CNES': 'id_hospital',
        'CODUFMUN': 'codigo_municipio',
        'TP_LEITO': 'tipo_leito',
        'QT_EXIST': 'leitos_totais',
        'QT_CONTR': 'leitos_contratados',
        'QT_SUS': 'leitos_sus',
        'QT_NSUS': 'leitos_nao_sus',
        'ESFERA_A': 'esfera',
        'TP_UNID': 'tipo_unidade',
        'NIV_HIER': 'nivel_hierarquico',
        'NAT_JUR': 'natureza_juridica'
    }
    
    # Selecionar colunas existentes
    colunas_existentes = [col for col in colunas_cnes.keys() if col in df.columns]
    df_clean = df[colunas_existentes].copy()
    df_clean.rename(columns={k: v for k, v in colunas_cnes.items() if k in df.columns}, inplace=True)
    
    logger.info(f"Colunas selecionadas: {len(df_clean.columns)}")
    
    # ============================================================
    # 3. CONVERSÃO DE TIPOS
    # ============================================================
    
    colunas_numericas = ['leitos_totais', 'leitos_contratados', 'leitos_sus', 'leitos_nao_sus']
    for col in colunas_numericas:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0).astype(int)
    
    # ============================================================
    # 4. PADRONIZAÇÃO DE CÓDIGOS
    # ============================================================
    
    if 'id_hospital' in df_clean.columns:
        df_clean['id_hospital'] = df_clean['id_hospital'].astype(str).str.zfill(7)
    
    if 'codigo_municipio' in df_clean.columns:
        df_clean['codigo_municipio'] = df_clean['codigo_municipio'].astype(str).str.zfill(6)
    
    # ============================================================
    # 5. AGRUPAMENTO POR HOSPITAL
    # ============================================================
    
    colunas_agrupar = ['id_hospital', 'codigo_municipio', 'esfera', 'tipo_unidade', 
                       'nivel_hierarquico', 'natureza_juridica']
    colunas_agrupar = [col for col in colunas_agrupar if col in df_clean.columns]
    
    colunas_somar = [col for col in colunas_numericas if col in df_clean.columns]
    
    df_agrupado = df_clean.groupby(colunas_agrupar)[colunas_somar].sum().reset_index()
    
    logger.info(f"Hospitais únicos: {len(df_agrupado):,}")
    
    # ============================================================
    # 6. CRIAÇÃO DE FEATURES
    # ============================================================
    
    MAPEAMENTO_LEITOS = {
        '1': 'Clinico', '2': 'Cirurgico', '3': 'Obstetrico', 
        '4': 'Pediatrico', '5': 'UTI', '6': 'Isolamento', '7': 'Outros'
    }
    
    MAPEAMENTO_ESFERA = {
        'E': 'Estadual', 'M': 'Municipal', 'F': 'Federal', '': 'Não Informado'
    }
    
    def classificar_porte(total_leitos):
        if total_leitos >= 150:
            return 'Grande Porte'
        elif total_leitos >= 50:
            return 'Medio Porte'
        elif total_leitos >= 15:
            return 'Pequeno Porte'
        else:
            return 'Micro Porte'
    
    if 'leitos_totais' in df_agrupado.columns:
        df_agrupado['porte_hospitalar'] = df_agrupado['leitos_totais'].apply(classificar_porte)
    
    if 'nivel_hierarquico' in df_agrupado.columns:
        df_agrupado['alta_complexidade'] = df_agrupado['nivel_hierarquico'].apply(
            lambda x: 'Alta Complexidade' if pd.notna(x) and x != '' else 'Baixa/Media Complexidade'
        )
    
    if 'esfera' in df_agrupado.columns:
        df_agrupado['esfera_classificacao'] = df_agrupado['esfera'].map(MAPEAMENTO_ESFERA).fillna('Não Informado')
    
    if 'leitos_totais' in df_agrupado.columns and 'leitos_sus' in df_agrupado.columns:
        df_agrupado['percentual_sus'] = (
            df_agrupado['leitos_sus'] / df_agrupado['leitos_totais'] * 100
        ).fillna(0).clip(0, 100).round(2)
    
    # ============================================================
    # 7. REMOÇÃO DE DUPLICATAS
    # ============================================================
    
    df_agrupado = df_agrupado.drop_duplicates(subset=['id_hospital'])
    
    logger.info(f"CNES transformado: {len(df_agrupado):,} hospitais")
    
    return df_agrupado


# ================================================================
# 3. TRANSFORMAÇÃO DO IBGE
# ================================================================

def transformar_ibge(
    df: pd.DataFrame, 
    uf: str = None
) -> pd.DataFrame:
    """
    Limpa e padroniza os dados do IBGE.
    """
    if uf is None:
        uf = config.UF
    
    logger.info(f"Transformando IBGE: {len(df):,} municípios para {uf}")
    
    colunas_ibge = ['codigo_ibge', 'nome', 'latitude', 'longitude']
    df_clean = df[colunas_ibge].copy()
    
    df_clean['codigo_ibge'] = df_clean['codigo_ibge'].astype(str).str[:6]
    
    df_clean.rename(columns={
        'codigo_ibge': 'codigo_municipio',
        'nome': 'nome_municipio',
        'latitude': 'latitude',
        'longitude': 'longitude'
    }, inplace=True)
    
    df_clean = df_clean.drop_duplicates(subset=['codigo_municipio'])
    
    # Tratar nulos
    df_clean['nome_municipio'] = df_clean['nome_municipio'].fillna('Não informado')
    df_clean['latitude'] = df_clean['latitude'].fillna(0)
    df_clean['longitude'] = df_clean['longitude'].fillna(0)
    
    logger.info(f"IBGE transformado: {len(df_clean):,} municípios")
    
    return df_clean


# ================================================================
# 4. FUNÇÃO DE UPLOAD PARA OBJECT STORAGE
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
# 5. SALVAR RESULTADOS DA TRANSFORMAÇÃO
# ================================================================

def salvar_resultados_transformacao(
    df_sih: pd.DataFrame,
    df_cnes: pd.DataFrame,
    df_ibge: pd.DataFrame,
    uf: str = None,
    ano: int = None,
    mes: int = None,
    upload: bool = True
) -> Dict[str, Path]:
    """
    Salva os DataFrames transformados localmente e no Object Storage.
    """
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if mes is None:
        mes = config.MES
    
    resultados = {}
    
    # SIH
    if df_sih is not None and len(df_sih) > 0:
        caminho = config.PROCESSED_DIR / f"sih_transformado_{uf}_{ano}_{mes:02d}.parquet"
        df_sih.to_parquet(caminho, index=False)
        resultados['sih'] = caminho
        logger.info(f"SIH salvo: {caminho} ({len(df_sih):,} registros)")
        
        if upload:
            objeto = f"sih_transformado/{uf}/{ano}/{mes:02d}/sih_transformado_{uf}_{ano}_{mes:02d}.parquet"
            upload_para_object_storage(caminho, objeto, "meddata-gold")
    
    # CNES
    if df_cnes is not None and len(df_cnes) > 0:
        caminho = config.PROCESSED_DIR / f"cnes_transformado_{uf}_{ano}_{mes:02d}.parquet"
        df_cnes.to_parquet(caminho, index=False)
        resultados['cnes'] = caminho
        logger.info(f"CNES salvo: {caminho} ({len(df_cnes):,} registros)")
        
        if upload:
            objeto = f"cnes_transformado/{uf}/{ano}/{mes:02d}/cnes_transformado_{uf}_{ano}_{mes:02d}.parquet"
            upload_para_object_storage(caminho, objeto, "meddata-gold")
    
    # IBGE
    if df_ibge is not None and len(df_ibge) > 0:
        caminho = config.PROCESSED_DIR / f"ibge_transformado_{uf}.parquet"
        df_ibge.to_parquet(caminho, index=False)
        resultados['ibge'] = caminho
        logger.info(f"IBGE salvo: {caminho} ({len(df_ibge):,} registros)")
        
        if upload:
            objeto = f"ibge_transformado/{uf}/ibge_transformado_{uf}.parquet"
            upload_para_object_storage(caminho, objeto, "meddata-gold")
    
    return resultados


# ================================================================
# 6. PIPELINE DE TRANSFORMAÇÃO
# ================================================================

def executar_transformacao(
    df_sih_raw: pd.DataFrame,
    df_cnes_raw: pd.DataFrame,
    df_ibge_raw: pd.DataFrame,
    uf: str = None,
    ano: int = None,
    mes: int = None,
    upload: bool = True
) -> Dict[str, pd.DataFrame]:
    """
    Executa o pipeline de transformação das três fontes de dados.
    """
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if mes is None:
        mes = config.MES
    
    logger.info("=" * 60)
    logger.info(f"INICIANDO TRANSFORMAÇÃO PARA {uf} {ano}/{mes:02d}")
    logger.info("=" * 60)
    
    # 1. Transformar SIH
    logger.info("\n[1/3] Transformando SIH...")
    df_sih = transformar_sih(df_sih_raw, uf, ano, mes)
    
    # 2. Transformar CNES
    logger.info("\n[2/3] Transformando CNES...")
    df_cnes = transformar_cnes(df_cnes_raw, uf, ano, mes)
    
    # 3. Transformar IBGE
    logger.info("\n[3/3] Transformando IBGE...")
    df_ibge = transformar_ibge(df_ibge_raw, uf)
    
    # 4. Salvar resultados
    logger.info("\nSalvando resultados...")
    salvar_resultados_transformacao(df_sih, df_cnes, df_ibge, uf, ano, mes, upload)
    
    # 5. Resumo
    logger.info("\n" + "=" * 60)
    logger.info("RESUMO DA TRANSFORMAÇÃO")
    logger.info("-" * 60)
    logger.info(f"SIH  : {len(df_sih):>8,} registros | {len(df_sih.columns):>3} colunas")
    logger.info(f"CNES : {len(df_cnes):>8,} registros | {len(df_cnes.columns):>3} colunas")
    logger.info(f"IBGE : {len(df_ibge):>8,} registros | {len(df_ibge.columns):>3} colunas")
    logger.info("=" * 60)
    
    return {
        'sih': df_sih,
        'cnes': df_cnes,
        'ibge': df_ibge
    }


# ================================================================
# 7. EXECUÇÃO DIRETA COM ARGPARSE
# ================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transformação de dados do MedData")
    parser.add_argument('--uf', type=str, default=config.UF, help='UF do estado')
    parser.add_argument('--ano', type=int, default=config.ANO, help='Ano dos dados')
    parser.add_argument('--mes', type=int, default=config.MES, help='Mês dos dados')
    parser.add_argument('--upload', action='store_true', default=True, help='Fazer upload para OCI')
    parser.add_argument('--no-upload', action='store_false', dest='upload', help='Não fazer upload para OCI')
    args = parser.parse_args()
    
    print("=" * 60)
    print("INICIANDO TRANSFORMAÇÃO DE DADOS")
    print(f"UF: {args.uf} | Ano: {args.ano} | Mês: {args.mes:02d}")
    print(f"Upload para OCI: {'SIM' if args.upload else 'NÃO'}")
    print("=" * 60)
    
    # Atualizar config
    config.UF = args.uf
    config.ANO = args.ano
    config.MES = args.mes
    
    # Importar funções de ingestão
    from ingestao import baixar_sih, baixar_cnes_leitos, baixar_ibge
    
    # Baixar dados brutos
    df_sih_raw = baixar_sih(args.uf, args.ano, args.mes, upload=False)
    df_cnes_raw = baixar_cnes_leitos(args.uf, args.ano, args.mes, upload=False)
    df_ibge_raw = baixar_ibge(args.uf, upload=False)
    
    if df_sih_raw is None or df_cnes_raw is None or df_ibge_raw is None:
        print("❌ Falha ao carregar dados brutos.")
        sys.exit(1)
    
    # Executar transformação
    resultados = executar_transformacao(
        df_sih_raw=df_sih_raw,
        df_cnes_raw=df_cnes_raw,
        df_ibge_raw=df_ibge_raw,
        uf=args.uf,
        ano=args.ano,
        mes=args.mes,
        upload=args.upload
    )
    
    # Resumo final
    print("\n" + "=" * 60)
    print("RESUMO DOS RESULTADOS")
    print("=" * 60)
    for nome, df in resultados.items():
        print(f"{nome.upper():10} | {len(df):>8,} registros | {len(df.columns):>3} colunas")
    
    print("\n✅ Transformação concluída com sucesso!")
    sys.exit(0)