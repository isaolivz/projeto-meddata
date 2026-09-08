"""
integracao_v2.py - Integracao e geracao do Star Schema (versão anual)
- Suporte para múltiplos meses
- Limite de 300k registros por mês
- DIM_CID10 (categoria de 3 dígitos)
- Remoção da coluna 'esfera'
- Nome fictício para hospitais
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import logging
import sys

sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent))

from config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def upload_para_object_storage(arquivo_local, objeto_name, bucket="meddata-gold"):
    """Faz upload de um arquivo para o Object Storage da OCI."""
    try:
        import oci
        from oci.config import from_file

        config_oci = from_file()
        object_storage = oci.object_storage.ObjectStorageClient(config_oci)
        namespace = object_storage.get_namespace().data

        with open(arquivo_local, "rb") as arquivo:
            object_storage.put_object(namespace, bucket, objeto_name, arquivo)

        logger.info(f"Upload concluido: {bucket}/{objeto_name}")
        return True
    except Exception as e:
        logger.error(f"Falha no upload: {str(e)}")
        return False


# ============================================================================
# 1. DIM_MUNICIPIO
# ============================================================================

def gerar_dim_municipio(df_ibge):
    """Gera a dimensao de municipios a partir do IBGE."""
    logger.info("Gerando DIM_MUNICIPIO...")

    dim = df_ibge.copy()
    dim = dim.drop_duplicates(subset=['codigo_municipio'])

    dim['nome_municipio'] = dim['nome_municipio'].fillna('Nao informado')
    dim['uf'] = dim['uf'].fillna('NA')
    dim['estado'] = dim['estado'].fillna('Nao informado')
    dim['latitude'] = dim['latitude'].fillna(0)
    dim['longitude'] = dim['longitude'].fillna(0)

    colunas_ordem = [
        'codigo_municipio',
        'nome_municipio',
        'uf',
        'estado',
        'latitude',
        'longitude'
    ]

    dim = dim[colunas_ordem]

    logger.info(f"DIM_MUNICIPIO gerada: {len(dim):,} municipios")
    return dim


# ============================================================================
# 2. DIM_HOSPITAL (com nome fictício e SEM esfera)
# ============================================================================

def gerar_dim_hospital(df_cnes, df_municipios):
    """Gera a dimensao de hospitais a partir do CNES (SEM esfera)."""
    logger.info("Gerando DIM_HOSPITAL...")

    dim = df_cnes.copy()

    # Garantir que temos o nome do hospital (criado na transformação)
    if 'nome_hospital' not in dim.columns:
        dim['nome_hospital'] = 'Hospital CNES ' + dim['id_hospital'].astype(str)

    dim = dim.merge(
        df_municipios[['codigo_municipio', 'nome_municipio', 'uf', 'estado', 'latitude', 'longitude']],
        on='codigo_municipio',
        how='left'
    ).rename(columns={
        'nome_municipio': 'nome_municipio_hospital',
        'uf': 'uf_hospital',
        'estado': 'estado_hospital',
        'latitude': 'latitude_hospital',
        'longitude': 'longitude_hospital'
    })

    dim['nome_municipio_hospital'] = dim['nome_municipio_hospital'].fillna('Nao informado')
    dim['uf_hospital'] = dim['uf_hospital'].fillna('NA')
    dim['estado_hospital'] = dim['estado_hospital'].fillna('Nao informado')
    dim['latitude_hospital'] = dim['latitude_hospital'].fillna(0)
    dim['longitude_hospital'] = dim['longitude_hospital'].fillna(0)

    dim = dim.drop_duplicates(subset=['id_hospital'])

    # Colunas da dimensão hospital (SEM esfera)
    colunas_ordem = [
        'id_hospital',
        'nome_hospital',          # NOVO: nome fictício
        'codigo_municipio',
        'nome_municipio_hospital',
        'uf_hospital',
        'estado_hospital',
        'latitude_hospital',
        'longitude_hospital',
        'leitos_totais',
        'leitos_sus',
        'leitos_nao_sus',
        # 'esfera',               # REMOVIDO
        'tipo_unidade',
        'nivel_hierarquico',
        'natureza_juridica',
        'porte_hospitalar',
        'alta_complexidade',
        'percentual_sus'
    ]

    colunas_existentes = [col for col in colunas_ordem if col in dim.columns]
    dim = dim[colunas_existentes]

    logger.info(f"DIM_HOSPITAL gerada: {len(dim):,} hospitais")
    return dim


# ============================================================================
# 3. DIM_TEMPO
# ============================================================================

def gerar_dim_tempo(df_sih):
    """
    Gera a dimensao de tempo a partir das datas do SIH.
    Mantem TODAS as datas disponiveis.
    """
    logger.info("Gerando DIM_TEMPO...")

    if 'data_internacao' not in df_sih.columns:
        logger.warning("Coluna 'data_internacao' nao encontrada.")
        return pd.DataFrame(columns=['data_referencia', 'ano', 'mes', 'trimestre', 'dia_semana', 'ano_mes', 'tempo_id'])

    datas_unicas = pd.Series(df_sih['data_internacao'].unique()).dropna()

    if len(datas_unicas) == 0:
        logger.warning("Nenhuma data encontrada.")
        return pd.DataFrame(columns=['data_referencia', 'ano', 'mes', 'trimestre', 'dia_semana', 'ano_mes', 'tempo_id'])

    dim = pd.DataFrame({
        'data_referencia': datas_unicas,
        'ano': datas_unicas.dt.year,
        'mes': datas_unicas.dt.month,
        'trimestre': datas_unicas.dt.quarter,
        'dia_semana': datas_unicas.dt.day_name(),
        'ano_mes': datas_unicas.dt.strftime('%Y-%m')
    })

    dim['tempo_id'] = range(1, len(dim) + 1)
    dim = dim.sort_values('data_referencia').reset_index(drop=True)

    logger.info(f"DIM_TEMPO gerada: {len(dim):,} datas unicas")
    logger.info(f"  Anos disponiveis: {sorted(dim['ano'].unique())}")

    return dim


# ============================================================================
# 4. DIM_CID10 (NOVO)
# ============================================================================

def gerar_dim_cid10(df_cid10):
    """Gera a dimensao de CID-10 a partir do arquivo processado."""
    logger.info("Gerando DIM_CID10...")

    if df_cid10 is None or len(df_cid10) == 0:
        logger.warning("Nenhum dado CID-10 disponível")
        return pd.DataFrame()

    dim = df_cid10.copy()
    
    # Garantir colunas necessárias
    if 'categoria' not in dim.columns:
        if 'codigo_cid' in dim.columns:
            dim['categoria'] = dim['codigo_cid'].astype(str).str.replace('.', '').str[:3]
    
    # Remover duplicatas
    dim = dim.drop_duplicates(subset=['categoria'])
    
    # Adicionar ID
    dim['cid10_id'] = range(1, len(dim) + 1)
    
    # Selecionar colunas
    colunas_ordem = ['cid10_id', 'categoria', 'codigo_cid', 'descricao_cid']
    colunas_existentes = [col for col in colunas_ordem if col in dim.columns]
    dim = dim[colunas_existentes]
    
    # Renomear para padrão
    if 'categoria' in dim.columns:
        dim.rename(columns={'categoria': 'categoria_cid'}, inplace=True)
    
    logger.info(f"DIM_CID10 gerada: {len(dim):,} categorias")
    return dim


# ============================================================================
# 5. FATO_INTERNACAO (com FK para CID10)
# ============================================================================

def gerar_fato_internacao(df_sih, df_hospitais, df_municipios, df_tempo, df_cid10=None):
    """
    Gera a tabela fato de internacoes com FK para CID10.
    """
    logger.info("Gerando FATO_INTERNACAO...")

    fato = df_sih.copy()
    logger.info(f"Base SIH: {len(fato):,} registros")

    # Adicionar informacoes do hospital
    fato = fato.merge(
        df_hospitais[['id_hospital', 'codigo_municipio', 'nome_hospital',
                      'nome_municipio_hospital', 'latitude_hospital', 
                      'longitude_hospital', 'leitos_sus']],
        on='id_hospital',
        how='left'
    )
    logger.info(f"Apos merge com hospitais: {len(fato):,} registros")

    # Adicionar informacoes do municipio do paciente
    fato = fato.merge(
        df_municipios[['codigo_municipio', 'nome_municipio', 'uf', 'estado', 'latitude', 'longitude']],
        left_on='codigo_municipio_paciente',
        right_on='codigo_municipio',
        how='left',
        suffixes=('', '_paciente_ibge')
    ).rename(columns={
        'nome_municipio': 'nome_municipio_paciente',
        'uf': 'uf_paciente',
        'estado': 'estado_paciente',
        'latitude': 'latitude_paciente',
        'longitude': 'longitude_paciente'
    })

    if 'codigo_municipio_paciente_ibge' in fato.columns:
        fato.drop(columns=['codigo_municipio_paciente_ibge'], inplace=True)

    # Adicionar tempo_id
    fato = fato.merge(
        df_tempo[['data_referencia', 'tempo_id']],
        left_on='data_internacao',
        right_on='data_referencia',
        how='inner'
    )
    fato.drop(columns=['data_referencia'], inplace=True, errors='ignore')

    # --- NOVO: Adicionar CID10 ---
    if df_cid10 is not None and len(df_cid10) > 0:
        # Usar a categoria (3 dígitos) para fazer o join
        fato = fato.merge(
            df_cid10[['categoria_cid', 'cid10_id', 'codigo_cid', 'descricao_cid']],
            left_on='categoria_cid',
            right_on='categoria_cid',
            how='left'
        )
        logger.info(f"Apos merge com CID10: {len(fato):,} registros")

    logger.info(f"Apos merges: {len(fato):,} registros")

    # Calcular distancia (haversine)
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

    # Tratar nulos
    fato['nome_municipio_paciente'] = fato['nome_municipio_paciente'].fillna('Nao informado')
    fato['uf_paciente'] = fato['uf_paciente'].fillna('NA')
    fato['estado_paciente'] = fato['estado_paciente'].fillna('Nao informado')
    fato['latitude_paciente'] = fato['latitude_paciente'].fillna(0)
    fato['longitude_paciente'] = fato['longitude_paciente'].fillna(0)
    fato['distancia_estimada_km'] = fato['distancia_estimada_km'].fillna(0)

    fato['nome_municipio_hospital'] = fato['nome_municipio_hospital'].fillna('Nao informado')
    fato['latitude_hospital'] = fato['latitude_hospital'].fillna(0)
    fato['longitude_hospital'] = fato['longitude_hospital'].fillna(0)

    fato['codigo_diagnostico'] = fato['codigo_diagnostico'].fillna('Nao informado')
    
    # Se tiver CID10, preencher nulos
    if 'cid10_id' in fato.columns:
        fato['cid10_id'] = fato['cid10_id'].fillna(0).astype(int)

    fato['internacao_id'] = range(1, len(fato) + 1)

    colunas_ordem = [
        'internacao_id',
        'id_hospital',
        'codigo_municipio_paciente',
        'tempo_id',
        'cid10_id',                    # NOVO: FK para CID10
        'codigo_diagnostico',
        'categoria_cid',               # NOVO: categoria de 3 dígitos
        'codigo_cid',                  # NOVO: código completo do CID
        'descricao_cid',               # NOVO: descrição do diagnóstico
        'data_internacao',
        'data_saida',
        'valor_procedimento',
        'dias_internacao',
        'paciente_viajou',
        'nome_municipio_paciente',
        'uf_paciente',
        'estado_paciente',
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


# ============================================================================
# 6. Salvar Star Schema (versão anual)
# ============================================================================

def salvar_star_schema(dim_municipio, dim_hospital, dim_tempo, dim_cid10, fato_internacao, 
                       uf=None, ano=None, mes=None, upload=True):
    """Salva as tabelas do Star Schema (versão anual)."""
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES

    resultados = {}

    tabelas = {
        'dim_municipio': dim_municipio,
        'dim_hospital': dim_hospital,
        'dim_tempo': dim_tempo,
        'dim_cid10': dim_cid10,           # NOVO
        'fato_internacao': fato_internacao
    }

    for nome, df in tabelas.items():
        if df is not None and len(df) > 0:
            # Nome do arquivo: se mes=0 é anual
            if mes == 0:
                caminho = config.PROCESSED_DIR / f"{nome}_{uf}_{ano}_anual.parquet"
            else:
                caminho = config.PROCESSED_DIR / f"{nome}_{uf}_{ano}_{mes:02d}.parquet"
            
            df.to_parquet(caminho, index=False)
            resultados[nome] = caminho
            logger.info(f"{nome.upper()} salvo: {caminho} ({len(df):,} registros)")

            if upload:
                if mes == 0:
                    objeto = f"{nome}/{uf}/{ano}/anual/{nome}_{uf}_{ano}_anual.parquet"
                else:
                    objeto = f"{nome}/{uf}/{ano}/{mes:02d}/{nome}_{uf}_{ano}_{mes:02d}.parquet"
                upload_para_object_storage(caminho, objeto, "meddata-gold")

    return resultados


# ============================================================================
# 7. Gerar Star Schema (completo)
# ============================================================================

def gerar_star_schema(df_sih, df_cnes, df_ibge, df_cid10=None, 
                      uf=None, ano=None, mes=None, salvar=True, upload=True):
    """Executa o pipeline completo de geracao do Star Schema."""
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES

    logger.info("=" * 60)
    logger.info(f"GERANDO STAR SCHEMA PARA {uf} {ano}/{mes:02d}")
    logger.info("=" * 60)

    logger.info("\n[1/5] Gerando DIM_MUNICIPIO...")
    dim_municipio = gerar_dim_municipio(df_ibge)

    logger.info("\n[2/5] Gerando DIM_HOSPITAL...")
    dim_hospital = gerar_dim_hospital(df_cnes, dim_municipio)

    logger.info("\n[3/5] Gerando DIM_TEMPO...")
    dim_tempo = gerar_dim_tempo(df_sih)

    logger.info("\n[4/5] Gerando DIM_CID10...")
    dim_cid10 = gerar_dim_cid10(df_cid10)

    logger.info("\n[5/5] Gerando FATO_INTERNACAO...")
    fato_internacao = gerar_fato_internacao(df_sih, dim_hospital, dim_municipio, dim_tempo, dim_cid10)

    if salvar:
        logger.info("\nSalvando Star Schema...")
        salvar_star_schema(dim_municipio, dim_hospital, dim_tempo, dim_cid10, 
                          fato_internacao, uf, ano, mes, upload)

    logger.info("\n" + "=" * 60)
    logger.info("RESUMO DO STAR SCHEMA")
    logger.info("-" * 60)
    logger.info(f"DIM_MUNICIPIO    : {len(dim_municipio):>8,} registros | {len(dim_municipio.columns):>3} colunas")
    logger.info(f"DIM_HOSPITAL     : {len(dim_hospital):>8,} registros | {len(dim_hospital.columns):>3} colunas")
    logger.info(f"DIM_TEMPO        : {len(dim_tempo):>8,} registros | {len(dim_tempo.columns):>3} colunas")
    if dim_cid10 is not None and len(dim_cid10) > 0:
        logger.info(f"DIM_CID10       : {len(dim_cid10):>8,} registros | {len(dim_cid10.columns):>3} colunas")
    logger.info(f"FATO_INTERNACAO  : {len(fato_internacao):>8,} registros | {len(fato_internacao.columns):>3} colunas")
    logger.info("=" * 60)

    return {
        'dim_municipio': dim_municipio,
        'dim_hospital': dim_hospital,
        'dim_tempo': dim_tempo,
        'dim_cid10': dim_cid10,
        'fato_internacao': fato_internacao
    }


# ============================================================================
# 8. Gerar Star Schema Anual
# ============================================================================

def gerar_star_schema_anual(uf=None, ano=None, meses=None, limite_por_mes=300000, upload=True):
    """Gera o Star Schema para um ano inteiro."""
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if meses is None:
        meses = list(range(1, 13))

    logger.info("=" * 60)
    logger.info(f"GERANDO STAR SCHEMA ANUAL PARA {uf} {ano}")
    logger.info(f"Limite por mês: {limite_por_mes:,} registros")
    logger.info("=" * 60)

    # Usar transformação v2
    from transformacao_v2 import transformar_multiplos_meses
    
    dados_transformados = transformar_multiplos_meses(uf, ano, meses, limite_por_mes, upload)
    
    if dados_transformados is None or dados_transformados['sih'] is None:
        logger.error("Falha na transformação dos dados")
        return None

    # Gerar Star Schema (mes=0 = anual)
    resultado = gerar_star_schema(
        df_sih=dados_transformados['sih'],
        df_cnes=dados_transformados['cnes'],
        df_ibge=dados_transformados['ibge'],
        df_cid10=dados_transformados['cid10'],
        uf=uf,
        ano=ano,
        mes=0,  # 0 = ano todo
        salvar=True,
        upload=upload
    )

    return resultado


# ============================================================================
# 9. Main
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Integracao e geracao do Star Schema v2")
    parser.add_argument('--uf', type=str, default=config.UF, help='UF do estado')
    parser.add_argument('--ano', type=int, default=config.ANO, help='Ano dos dados')
    parser.add_argument('--mes', type=int, help='Mes dos dados (opcional)')
    parser.add_argument('--meses', nargs='+', type=int, help='Lista de meses (ex: 1 2 3)')
    parser.add_argument('--limite', type=int, default=300000, help='Limite de registros por mês')
    parser.add_argument('--upload', action='store_true', default=False, help='Fazer upload para OCI')
    parser.add_argument('--no-upload', action='store_false', dest='upload', help='Nao fazer upload para OCI')
    args = parser.parse_args()

    print("=" * 60)
    print("INICIANDO INTEGRACAO E STAR SCHEMA v2")
    print(f"UF: {args.uf} | Ano: {args.ano}")
    print(f"Upload para OCI: {'SIM' if args.upload else 'NAO'}")
    print("=" * 60)

    config.UF = args.uf
    config.ANO = args.ano

    # Se especificou meses ou limite, gera Star Schema anual
    if args.meses or args.limite != 300000:
        meses = args.meses if args.meses else list(range(1, 13))
        resultado = gerar_star_schema_anual(args.uf, args.ano, meses, args.limite, args.upload)
    elif args.mes:
        # Modo único mês (compatibilidade)
        config.MES = args.mes
        
        from transformacao_v2 import transformar_sih, transformar_cnes, transformar_ibge, transformar_cid10
        from ingestao_v2 import baixar_sih, baixar_cnes_leitos, baixar_ibge, baixar_cid10
        
        print("\nBaixando dados brutos...")
        df_sih_raw = baixar_sih(args.uf, args.ano, args.mes, upload=False)
        df_cnes_raw = baixar_cnes_leitos(args.uf, args.ano, args.mes, upload=False)
        df_ibge_raw = baixar_ibge(args.uf, upload=False)
        df_cid10_raw = baixar_cid10()
        
        if df_sih_raw is None or df_cnes_raw is None or df_ibge_raw is None:
            print("Falha ao carregar dados brutos.")
            sys.exit(1)
        
        print("\nTransformando dados...")
        df_sih = transformar_sih(df_sih_raw, args.uf, args.ano, args.mes)
        df_cnes = transformar_cnes(df_cnes_raw, args.uf, args.ano, args.mes)
        df_ibge = transformar_ibge(df_ibge_raw, args.uf)
        df_cid10 = transformar_cid10(df_cid10_raw)
        
        resultado = gerar_star_schema(
            df_sih=df_sih,
            df_cnes=df_cnes,
            df_ibge=df_ibge,
            df_cid10=df_cid10,
            uf=args.uf,
            ano=args.ano,
            mes=args.mes,
            salvar=True,
            upload=args.upload
        )
    else:
        # Modo automático: gera Star Schema para todos os meses
        print("Modo automático: gerando Star Schema para todos os meses de 2024")
        resultado = gerar_star_schema_anual(args.uf, args.ano, list(range(1, 13)), args.limite, args.upload)

    if resultado:
        print("\n" + "=" * 60)
        print("RESUMO DOS RESULTADOS")
        print("=" * 60)
        for nome, df in resultado.items():
            if df is not None and len(df) > 0:
                print(f"{nome.upper():15} | {len(df):>8,} registros | {len(df.columns):>3} colunas")

        print("\nStar Schema gerado com sucesso!")
        sys.exit(0)
    else:
        print("\nFalha ao gerar Star Schema.")
        sys.exit(1)