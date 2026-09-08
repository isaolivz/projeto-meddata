"""
transformacao_v2.py - Transformacao de dados do MedData (versão anual com limite)
- Suporte para múltiplos meses
- Limite de 300k registros por mês
- Integração com CID-10 (categoria de 3 dígitos)
- Criação de nome fictício para hospitais
- Remoção da coluna 'esfera'
"""

import argparse
import sys
import logging
from pathlib import Path
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

ESTADOS = {
    'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapa', 'AM': 'Amazonas',
    'BA': 'Bahia', 'CE': 'Ceara', 'DF': 'Distrito Federal', 'ES': 'Espirito Santo',
    'GO': 'Goias', 'MA': 'Maranhao', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul',
    'MG': 'Minas Gerais', 'PA': 'Para', 'PB': 'Paraiba', 'PR': 'Parana',
    'PE': 'Pernambuco', 'PI': 'Piaui', 'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte',
    'RS': 'Rio Grande do Sul', 'RO': 'Rondonia', 'RR': 'Roraima', 'SC': 'Santa Catarina',
    'SP': 'Sao Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins'
}


# ============================================================================
# 1. Transformar SIH (com CID-10)
# ============================================================================

def transformar_sih(df, uf=None, ano=None, mes=None):
    """Limpa e padroniza os dados brutos do SIH/SUS."""
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES

    logger.info(f"Transformando SIH: {len(df):,} registros para {uf} {ano}/{mes:02d}")

    # Colunas essenciais para o SIH (grupo RD)
    colunas_essenciais = [
        'SP_GESTOR', 'SP_CNES', 'SP_CIDPRI', 'SP_DTINTER',
        'SP_DTSAIDA', 'SP_VALATO', 'SP_M_PAC', 'SP_AA', 'SP_MM'
    ]

    colunas_existentes = [col for col in colunas_essenciais if col in df.columns]
    df_clean = df[colunas_existentes].copy()

    # Conversao de tipos
    if 'SP_DTINTER' in df_clean.columns:
        df_clean['SP_DTINTER'] = pd.to_datetime(df_clean['SP_DTINTER'], format='%Y%m%d', errors='coerce')
    if 'SP_DTSAIDA' in df_clean.columns:
        df_clean['SP_DTSAIDA'] = pd.to_datetime(df_clean['SP_DTSAIDA'], format='%Y%m%d', errors='coerce')
    if 'SP_VALATO' in df_clean.columns:
        df_clean['SP_VALATO'] = pd.to_numeric(df_clean['SP_VALATO'], errors='coerce')
    if 'SP_AA' in df_clean.columns:
        df_clean['SP_AA'] = pd.to_numeric(df_clean['SP_AA'], errors='coerce').fillna(ano).astype(int)
    if 'SP_MM' in df_clean.columns:
        df_clean['SP_MM'] = pd.to_numeric(df_clean['SP_MM'], errors='coerce').fillna(mes).astype(int)

    # Padronizacao de codigos
    if 'SP_CNES' in df_clean.columns:
        df_clean['SP_CNES'] = df_clean['SP_CNES'].astype(str).str.zfill(7)
    if 'SP_GESTOR' in df_clean.columns:
        df_clean['SP_GESTOR'] = df_clean['SP_GESTOR'].astype(str).str.zfill(6)
    if 'SP_M_PAC' in df_clean.columns:
        df_clean['SP_M_PAC'] = df_clean['SP_M_PAC'].astype(str).str.zfill(6)

    # Renomeacao
    mapeamento = {
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
    mapeamento_existente = {k: v for k, v in mapeamento.items() if k in df_clean.columns}
    df_clean.rename(columns=mapeamento_existente, inplace=True)

    # --- NOVO: Processamento do CID-10 ---
    # Extrair categoria (3 primeiros dígitos sem ponto)
    if 'codigo_diagnostico' in df_clean.columns:
    # SIH já vem com 4 dígitos sem ponto: 'A000'
        df_clean['categoria_cid'] = df_clean['codigo_diagnostico'].astype(str).str[:4]
        logger.info(f"CID-10: {df_clean['categoria_cid'].nunique()} categorias únicas extraídas")

    # Features derivadas
    if 'data_internacao' in df_clean.columns and 'data_saida' in df_clean.columns:
        df_clean['dias_internacao'] = (df_clean['data_saida'] - df_clean['data_internacao']).dt.days
        df_clean['dias_internacao'] = df_clean['dias_internacao'].fillna(0).clip(lower=0).astype(int)

    if 'codigo_municipio' in df_clean.columns and 'codigo_municipio_paciente' in df_clean.columns:
        df_clean['paciente_viajou'] = (df_clean['codigo_municipio_paciente'] != df_clean['codigo_municipio'])

    if 'data_internacao' in df_clean.columns:
        df_clean['dia_semana'] = df_clean['data_internacao'].dt.day_name()
        df_clean['tipo_dia'] = df_clean['dia_semana'].apply(
            lambda x: 'Fim de Semana' if x in ['Saturday', 'Sunday'] else 'Dia Util'
        )

    if 'ano_competencia' in df_clean.columns and 'mes_competencia' in df_clean.columns:
        df_clean['ano_mes'] = df_clean['ano_competencia'].astype(str) + '-' + df_clean['mes_competencia'].astype(str).str.zfill(2)

    # Remocao de duplicatas e invalidos
    df_clean = df_clean.drop_duplicates()

    if 'data_internacao' in df_clean.columns:
        df_clean = df_clean[df_clean['data_internacao'].notna()]

    if 'id_hospital' in df_clean.columns:
        df_clean = df_clean[df_clean['id_hospital'].notna()]

    logger.info(f"SIH transformado: {len(df_clean):,} registros")
    return df_clean


# ============================================================================
# 2. Transformar CNES (com nome fictício e sem esfera)
# ============================================================================

def transformar_cnes(df, uf=None, ano=None, mes=None):
    """Limpa e padroniza os dados brutos do CNES."""
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES

    logger.info(f"Transformando CNES: {len(df):,} registros para {uf} {ano}/{mes:02d}")

    df.columns = [col.upper() for col in df.columns]

    # Colunas do CNES (REMOVEMOS 'ESFERA_A')
    colunas_cnes = {
        'CNES': 'id_hospital',
        'CODUFMUN': 'codigo_municipio',
        'TP_LEITO': 'tipo_leito',
        'QT_EXIST': 'leitos_totais',
        'QT_SUS': 'leitos_sus',
        'QT_NSUS': 'leitos_nao_sus',
        # 'ESFERA_A': 'esfera',  # REMOVIDO - coluna nula
        'TP_UNID': 'tipo_unidade',
        'NIV_HIER': 'nivel_hierarquico',
        'NAT_JUR': 'natureza_juridica'
    }

    colunas_existentes = [col for col in colunas_cnes.keys() if col in df.columns]
    df_clean = df[colunas_existentes].copy()
    df_clean.rename(columns={k: v for k, v in colunas_cnes.items() if k in df.columns}, inplace=True)

    colunas_numericas = ['leitos_totais', 'leitos_sus', 'leitos_nao_sus']
    for col in colunas_numericas:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0).astype(int)

    if 'id_hospital' in df_clean.columns:
        df_clean['id_hospital'] = df_clean['id_hospital'].astype(str).str.zfill(7)
    if 'codigo_municipio' in df_clean.columns:
        df_clean['codigo_municipio'] = df_clean['codigo_municipio'].astype(str).str.zfill(6)

    # --- NOVO: Criar nome fictício para o hospital ---
    if 'id_hospital' in df_clean.columns:
        df_clean['nome_hospital'] = 'Hospital CNES ' + df_clean['id_hospital']

    # Agrupar por hospital (SEM 'esfera')
    colunas_agrupar = [
        'id_hospital', 'codigo_municipio',  # 'esfera' removido
        'tipo_unidade', 'nivel_hierarquico', 'natureza_juridica'
    ]
    colunas_agrupar = [col for col in colunas_agrupar if col in df_clean.columns]

    colunas_somar = [col for col in colunas_numericas if col in df_clean.columns]

    df_agrupado = df_clean.groupby(colunas_agrupar)[colunas_somar].sum().reset_index()

    # Manter o nome do hospital após o groupby
    if 'nome_hospital' in df_clean.columns and 'id_hospital' in df_agrupado.columns:
        # Pegar o primeiro nome para cada hospital (todos são iguais)
        nomes_hospitais = df_clean[['id_hospital', 'nome_hospital']].drop_duplicates(subset=['id_hospital'])
        df_agrupado = df_agrupado.merge(nomes_hospitais, on='id_hospital', how='left')

    def classificar_porte(total_leitos):
        if total_leitos >= 150:
            return 'Grande Porte'
        elif total_leitos >= 50:
            return 'Medio Porte'
        elif total_leitos >= 15:
            return 'Pequeno Porte'
        return 'Micro Porte'

    if 'leitos_totais' in df_agrupado.columns:
        df_agrupado['porte_hospitalar'] = df_agrupado['leitos_totais'].apply(classificar_porte)

    if 'nivel_hierarquico' in df_agrupado.columns:
        df_agrupado['alta_complexidade'] = df_agrupado['nivel_hierarquico'].apply(
            lambda x: 'Alta Complexidade' if pd.notna(x) and x != '' else 'Baixa/Media Complexidade'
        )

    if 'leitos_totais' in df_agrupado.columns and 'leitos_sus' in df_agrupado.columns:
        df_agrupado['percentual_sus'] = (
            df_agrupado['leitos_sus'] / df_agrupado['leitos_totais'] * 100
        ).fillna(0).clip(0, 100).round(2)

    df_agrupado = df_agrupado.drop_duplicates(subset=['id_hospital'])

    logger.info(f"CNES transformado: {len(df_agrupado):,} hospitais")
    return df_agrupado


# ============================================================================
# 3. Transformar IBGE
# ============================================================================

def transformar_ibge(df, uf=None):
    """Limpa e padroniza os dados do IBGE, adicionando UF e estado."""
    uf = uf or config.UF

    logger.info(f"Transformando IBGE: {len(df):,} municipios para {uf}")

    colunas_ibge = ['codigo_ibge', 'nome', 'uf', 'latitude', 'longitude']
    colunas_existentes = [col for col in colunas_ibge if col in df.columns]
    logger.info(f"Colunas encontradas: {colunas_existentes}")

    df_clean = df[colunas_existentes].copy()

    df_clean.rename(columns={
        'codigo_ibge': 'codigo_municipio',
        'nome': 'nome_municipio',
        'uf': 'uf',
        'latitude': 'latitude',
        'longitude': 'longitude'
    }, inplace=True)

    df_clean['estado'] = df_clean['uf'].map(ESTADOS).fillna('Nao informado')
    df_clean['nome_municipio'] = df_clean['nome_municipio'].fillna('Nao informado')
    df_clean['latitude'] = df_clean['latitude'].fillna(0)
    df_clean['longitude'] = df_clean['longitude'].fillna(0)
    df_clean['codigo_municipio'] = df_clean['codigo_municipio'].astype(str).str[:6]

    logger.info(f"IBGE transformado: {len(df_clean):,} municipios")
    return df_clean


# ============================================================================
# 4. Transformar CID-10
# ============================================================================

def transformar_cid10(df_cid10):
    """Processa o CID-10 para criar a dimensão de diagnóstico."""
    if df_cid10 is None or len(df_cid10) == 0:
        logger.warning("Nenhum dado CID-10 disponível")
        return None
    
    logger.info(f"Transformando CID-10: {len(df_cid10):,} registros")
    
    df_clean = df_cid10.copy()
    
    # Garantir que temos a categoria (4 dígitos sem ponto)
    if 'categoria' not in df_clean.columns:
        if 'codigo_cid' in df_clean.columns:
            # Remover ponto e pegar 4 dígitos: 'A00.0' -> 'A000'
            df_clean['categoria'] = df_clean['codigo_cid'].astype(str).str.replace('.', '').str[:4]
    
    # Remover duplicatas por categoria
    df_clean = df_clean.drop_duplicates(subset=['categoria'])
    
    logger.info(f"CID-10 transformado: {len(df_clean):,} categorias únicas")
    return df_clean


# ============================================================================
# 5. Salvar resultados (versão anual)
# ============================================================================

def salvar_resultados_transformacao(df_sih, df_cnes, df_ibge, df_cid10=None, 
                                    uf=None, ano=None, mes=None, upload=True):
    """Salva dataFrames transformados localmente."""
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES

    resultados = {}

    # SIH - salvar como anual se mes=0
    if df_sih is not None and len(df_sih) > 0:
        if mes == 0:
            caminho = config.PROCESSED_DIR / f"sih_transformado_{uf}_{ano}_anual.parquet"
        else:
            caminho = config.PROCESSED_DIR / f"sih_transformado_{uf}_{ano}_{mes:02d}.parquet"
        df_sih.to_parquet(caminho, index=False)
        resultados['sih'] = caminho
        logger.info(f"SIH salvo: {caminho} ({len(df_sih):,} registros)")

    # CNES - salvar como anual se mes=0
    if df_cnes is not None and len(df_cnes) > 0:
        if mes == 0:
            caminho = config.PROCESSED_DIR / f"cnes_transformado_{uf}_{ano}_anual.parquet"
        else:
            caminho = config.PROCESSED_DIR / f"cnes_transformado_{uf}_{ano}_{mes:02d}.parquet"
        df_cnes.to_parquet(caminho, index=False)
        resultados['cnes'] = caminho
        logger.info(f"CNES salvo: {caminho} ({len(df_cnes):,} registros)")

    # IBGE
    if df_ibge is not None and len(df_ibge) > 0:
        caminho = config.REFERENCE_DIR / f"ibge_transformado_{uf}.parquet"
        df_ibge.to_parquet(caminho, index=False)
        resultados['ibge'] = caminho
        logger.info(f"IBGE salvo: {caminho} ({len(df_ibge):,} registros)")

    # CID-10
    if df_cid10 is not None and len(df_cid10) > 0:
        caminho = config.REFERENCE_DIR / f"dim_cid10.parquet"
        df_cid10.to_parquet(caminho, index=False)
        resultados['cid10'] = caminho
        logger.info(f"CID-10 salvo: {caminho} ({len(df_cid10):,} registros)")

    return resultados


# ============================================================================
# 6. Executar transformação para múltiplos meses
# ============================================================================

def transformar_multiplos_meses(uf=None, ano=None, meses=None, limite_por_mes=300000, upload=True):
    """Transforma dados de múltiplos meses com limite de registros."""
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if meses is None:
        meses = list(range(1, 13))

    print("=" * 60)
    print("TRANSFORMANDO MÚLTIPLOS MESES")
    print(f"UF: {uf} | Ano: {ano} | Meses: {meses}")
    print(f"Limite por mês: {limite_por_mes:,} registros")
    print("=" * 60)

    # Importar da ingestão v2
    from ingestao_v2 import baixar_multiplos_meses
    
    # Baixar dados de múltiplos meses
    dados_brutos = baixar_multiplos_meses(uf, ano, meses, limite_por_mes, upload)
    
    if dados_brutos['sih'] is None:
        print("Erro: Não foi possível baixar os dados SIH")
        return None

    # Transformar SIH
    print("\nTransformando SIH...")
    df_sih = transformar_sih(dados_brutos['sih'], uf, ano, mes=0)  # mes=0 = anual

    # Transformar CNES
    print("\nTransformando CNES...")
    df_cnes = transformar_cnes(dados_brutos['cnes'], uf, ano, mes=0)

    # Transformar IBGE (só precisa uma vez)
    from ingestao_v2 import baixar_ibge
    df_ibge_raw = baixar_ibge(uf, upload=False)
    df_ibge = transformar_ibge(df_ibge_raw, uf)

    # Transformar CID-10
    print("\nTransformando CID-10...")
    df_cid10 = transformar_cid10(dados_brutos['cid10'])

    # Salvar resultados
    print("\nSalvando dados transformados...")
    salvar_resultados_transformacao(
        df_sih, df_cnes, df_ibge, df_cid10,
        uf, ano, mes=0, upload=upload
    )

    print("=" * 60)
    print("RESUMO DA TRANSFORMAÇÃO")
    print("-" * 60)
    print(f"SIH:  {len(df_sih):>8,} registros")
    print(f"CNES: {len(df_cnes):>8,} registros")
    print(f"IBGE: {len(df_ibge):>8,} registros")
    if df_cid10 is not None:
        print(f"CID-10: {len(df_cid10):>8,} categorias")
    print("=" * 60)

    return {
        'sih': df_sih,
        'cnes': df_cnes,
        'ibge': df_ibge,
        'cid10': df_cid10
    }


# ============================================================================
# 7. Executar transformação (compatibilidade com original)
# ============================================================================

def executar_transformacao(df_sih_raw, df_cnes_raw, df_ibge_raw, df_cid10_raw=None,
                           uf=None, ano=None, mes=None, upload=True):
    """Executa o pipeline de transformacao das tres fontes de dados."""
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES

    logger.info("Iniciando transformacao para %s %d/%02d", uf, ano, mes)

    df_sih = transformar_sih(df_sih_raw, uf, ano, mes)
    df_cnes = transformar_cnes(df_cnes_raw, uf, ano, mes)
    df_ibge = transformar_ibge(df_ibge_raw, uf)
    df_cid10 = transformar_cid10(df_cid10_raw) if df_cid10_raw is not None else None

    salvar_resultados_transformacao(df_sih, df_cnes, df_ibge, df_cid10, uf, ano, mes, upload)

    return {'sih': df_sih, 'cnes': df_cnes, 'ibge': df_ibge, 'cid10': df_cid10}


# ============================================================================
# 8. Main
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transformacao de dados do MedData v2")
    parser.add_argument('--uf', type=str, default=config.UF, help='UF do estado')
    parser.add_argument('--ano', type=int, default=config.ANO, help='Ano dos dados')
    parser.add_argument('--mes', type=int, help='Mês dos dados (opcional)')
    parser.add_argument('--meses', nargs='+', type=int, help='Lista de meses (ex: 1 2 3)')
    parser.add_argument('--limite', type=int, default=300000, help='Limite de registros por mês')
    parser.add_argument('--upload', action='store_true', default=True, help='Fazer upload para OCI')
    parser.add_argument('--no-upload', action='store_false', dest='upload', help='Nao fazer upload para OCI')
    args = parser.parse_args()

    print("=" * 60)
    print("INICIANDO TRANSFORMACAO DE DADOS v2")
    print(f"UF: {args.uf} | Ano: {args.ano}")
    print("=" * 60)

    config.UF = args.uf
    config.ANO = args.ano

    # Se especificou meses ou limite, transforma múltiplos meses
    if args.meses or args.limite != 300000:
        meses = args.meses if args.meses else list(range(1, 13))
        transformar_multiplos_meses(args.uf, args.ano, meses, args.limite, args.upload)
    elif args.mes:
        # Modo único mês (compatibilidade)
        config.MES = args.mes
        
        from ingestao_v2 import baixar_sih, baixar_cnes_leitos, baixar_ibge, baixar_cid10
        
        df_sih_raw = baixar_sih(args.uf, args.ano, args.mes, upload=False)
        df_cnes_raw = baixar_cnes_leitos(args.uf, args.ano, args.mes, upload=False)
        df_ibge_raw = baixar_ibge(args.uf, upload=False)
        df_cid10_raw = baixar_cid10()
        
        if df_sih_raw is None or df_cnes_raw is None or df_ibge_raw is None:
            print("Falha ao carregar dados brutos.")
            sys.exit(1)
        
        executar_transformacao(
            df_sih_raw=df_sih_raw,
            df_cnes_raw=df_cnes_raw,
            df_ibge_raw=df_ibge_raw,
            df_cid10_raw=df_cid10_raw,
            uf=args.uf,
            ano=args.ano,
            mes=args.mes,
            upload=args.upload
        )
    else:
        # Modo automático: transforma todos os meses
        print("Modo automático: transformando todos os meses de 2024")
        transformar_multiplos_meses(args.uf, args.ano, list(range(1, 13)), args.limite, args.upload)

    print("\nTransformacao concluida com sucesso.")
    sys.exit(0)