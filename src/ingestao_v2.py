"""
ingestao_v2.py - Ingestão de dados do MedData (versão anual com limite)
- Baixa 12 meses de 2024 com limite de 300k registros por mês
- Baixa dados SIH do grupo RD
- Lê CSV de diagnóstico CID-10
- Mantém compatibilidade com o original
"""

import argparse
import pandas as pd
import oci
from oci.config import from_file
from pysus import sih
from pysus import cnes
from pathlib import Path
import sys
import os

sys.path.append(str(Path(__file__).parent.parent))
from config import config


# ============================================================================
# 1. Upload para Object Storage
# ============================================================================

def upload_para_object_storage(arquivo_local: Path, objeto_name: str, bucket: str = "meddata-bronze"):
    """Faz upload de arquivo para Object Storage da OCI."""
    try:
        config_oci = from_file()
        object_storage = oci.object_storage.ObjectStorageClient(config_oci)
        namespace = object_storage.get_namespace().data
        
        with open(arquivo_local, "rb") as arquivo:
            object_storage.put_object(namespace, bucket, objeto_name, arquivo)
        
        print(f"[OCI] Upload concluído: {bucket}/{objeto_name}")
        return True
    except Exception as e:
        print(f"[ERRO OCI] Falha no upload: {str(e)}")
        return False


# ============================================================================
# 2. Baixar CID-10 do CSV
# ============================================================================

def baixar_cid10(caminho_csv=None):
    """
    Lê o arquivo CSV de diagnóstico CID-10.
    Mantém apenas categoria (3 dígitos) e descrição.
    """
    if caminho_csv is None:
        caminho_csv = config.DATA_DIR / "reference" / "CID-10-SUBCATEGORIAS.CSV"
    
    print(f"[CID-10] Carregando arquivo: {caminho_csv}")
    
    try:
        # Ler CSV (ajuste o separador conforme seu arquivo)
        df = pd.read_csv(caminho_csv, sep=';', encoding='latin1')
        print(f"[CID-10] Arquivo carregado: {len(df):,} registros")
        
        # Identificar colunas
        colunas = df.columns.tolist()
        print(f"[CID-10] Colunas disponíveis: {colunas}")
        
        # Mapear colunas (ajuste conforme seu CSV)
        # Exemplo: se tiver 'CODIGO' e 'DESCRICAO'
        col_codigo = None
        col_descricao = None
        
        for col in colunas:
            if 'COD' in col.upper() or 'CID' in col.upper():
                col_codigo = col
            if 'DESC' in col.upper() or 'NOME' in col.upper() or 'DESCRI' in col.upper():
                col_descricao = col
        
        if col_codigo is None or col_descricao is None:
            print("[CID-10] ERRO: Não foi possível identificar colunas de código e descrição")
            return None
        
        # Manter apenas as colunas necessárias
        df_clean = df[[col_codigo, col_descricao]].copy()
        df_clean.rename(columns={
            col_codigo: 'codigo_cid',
            col_descricao: 'descricao_cid'
        }, inplace=True)
        
        # Extrair categoria (3 primeiros dígitos, sem ponto)
        df_clean['categoria'] = df_clean['codigo_cid'].astype(str).str.replace('.', '').str[:3]
        
        # Remover duplicatas por categoria
        df_clean = df_clean.drop_duplicates(subset=['categoria'])
        
        print(f"[CID-10] Processado: {len(df_clean):,} categorias únicas")
        
        # Salvar na pasta reference
        caminho_salvo = config.REFERENCE_DIR / "dim_cid10.parquet"
        df_clean.to_parquet(caminho_salvo, index=False)
        print(f"[CID-10] Salvo em: {caminho_salvo}")
        
        return df_clean
        
    except Exception as e:
        print(f"[ERRO CID-10] {str(e)}")
        return None


# ============================================================================
# 3. Baixar dados do SIH - Internações (grupo RD)
# ============================================================================

def baixar_sih(uf=None, ano=None, mes=None, upload=True):
    """Baixa dados do SIH do grupo RD."""
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if mes is None:
        mes = config.MES
    
    print(f"[SIH] Baixando dados RD: {uf} {ano}/{mes:02d}")
    
    try:
        # Forçar grupo RD
        arquivos = sih(state=uf, year=ano, month=mes, groups=['RD'])
        if not arquivos:
            print(f"[SIH] Nenhum arquivo RD encontrado para {uf} {ano}/{mes}")
            return None
        
        df = pd.read_parquet(arquivos[0])
        print(f"[SIH] Carregado: {len(df):,} registros")
        
        # Salvar na pasta RAW_DIR
        caminho_raw = config.RAW_DIR / config.get_nome_arquivo('sih', uf=uf, ano=ano, mes=mes)
        df.to_parquet(caminho_raw, index=False)
        print(f"[SIH] Salvo localmente em: {caminho_raw}")
        
        return df
    
    except Exception as e:
        print(f"[ERRO SIH] {str(e)}")
        return None


# ============================================================================
# 4. Baixar o CNES - leitos
# ============================================================================

def baixar_cnes_leitos(uf=None, ano=None, mes=None, upload=True):
    """Baixa dados do CNES (leitos)."""
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if mes is None:
        mes = config.MES
    
    print(f"[CNES] Baixando dados {uf} {ano}/{mes:02d}")
    
    try:
        arquivos = cnes(state=uf, year=ano, month=mes, group="LT")
        if not arquivos:
            print(f"[CNES] Nenhum arquivo encontrado para {uf} {ano}/{mes}")
            return None
        
        df = pd.read_parquet(arquivos[0])
        print(f"[CNES] Carregado: {len(df):,} registros")
        
        # Salvar na pasta RAW_DIR
        caminho_raw = config.RAW_DIR / config.get_nome_arquivo('cnes', uf=uf, ano=ano, mes=mes)
        df.to_parquet(caminho_raw, index=False)
        print(f"[CNES] Salvo localmente em: {caminho_raw}")
        
        return df
    
    except Exception as e:
        print(f"[ERRO CNES] {str(e)}")
        return None


# ============================================================================
# 5. Baixar o IBGE - municípios
# ============================================================================

def baixar_ibge(uf=None, upload=True):
    """Baixa dados do IBGE para municípios."""
    uf = uf or config.UF
    
    print(f"[IBGE] Carregando dados para {uf}")
    
    try:
        codigo_uf = config.get_codigo_uf(uf)
        if codigo_uf is None:
            raise ValueError(f"UF '{uf}' não encontrada.")
        
        url = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
        df = pd.read_csv(url)
        df = df[df['codigo_uf'] == codigo_uf].copy()
        
        if len(df) == 0:
            raise ValueError(f"Nenhum município encontrado para UF '{uf}'")
        
        # Mapeamento de codigo_uf para sigla da UF
        codigo_para_uf = {
            11: 'RO', 12: 'AC', 13: 'AM', 14: 'RR', 15: 'PA', 16: 'AP', 17: 'TO',
            21: 'MA', 22: 'PI', 23: 'CE', 24: 'RN', 25: 'PB', 26: 'PE', 27: 'AL',
            28: 'SE', 29: 'BA',
            31: 'MG', 32: 'ES', 33: 'RJ', 35: 'SP',
            41: 'PR', 42: 'SC', 43: 'RS',
            50: 'MS', 51: 'MT', 52: 'GO', 53: 'DF'
        }
        
        df['uf'] = df['codigo_uf'].map(codigo_para_uf).fillna('NA')
        
        print(f"[IBGE] Carregado: {len(df):,} municípios")
        
        # Salvar localmente
        caminho_ref = config.REFERENCE_DIR / config.get_nome_arquivo('ibge', uf=uf, ano=None, mes=None)
        df.to_parquet(caminho_ref, index=False)
        print(f"[IBGE] Salvo localmente: {caminho_ref}")
        
        return df
    
    except Exception as e:
        print(f"[ERRO IBGE] {str(e)}")
        return None


# ============================================================================
# 6. Baixar múltiplos meses com limite
# ============================================================================

def baixar_multiplos_meses(uf=None, ano=None, meses=None, limite_por_mes=300000, upload=True):
    """
    Baixa dados de múltiplos meses com limite de registros por mês.
    
    Args:
        uf: UF do estado
        ano: Ano dos dados
        meses: Lista de meses (ex: [1,2,3]) ou None para todos (1-12)
        limite_por_mes: Limite de registros por mês (default: 300000)
        upload: Fazer upload para OCI
    """
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if meses is None:
        meses = list(range(1, 13))
    
    print("=" * 60)
    print("BAIXANDO MÚLTIPLOS MESES - SIH (grupo RD)")
    print(f"UF: {uf} | Ano: {ano} | Meses: {meses}")
    print(f"Limite por mês: {limite_por_mes:,} registros")
    print("=" * 60)
    
    resultados = {
        'sih': [],
        'cnes': []
    }
    
    # Primeiro, baixar CID-10
    df_cid10 = baixar_cid10()
    
    for mes in meses:
        print(f"\n--- Processando mês {mes:02d}/{ano} ---")
        
        # Baixar SIH (grupo RD)
        df_sih = baixar_sih(uf, ano, mes, upload=upload)
        
        # Aplicar limite se definido
        if df_sih is not None and limite_por_mes and len(df_sih) > limite_por_mes:
            df_sih = df_sih.sample(n=limite_por_mes, random_state=42)
            print(f"  [LIMITE] SIH reduzido para {limite_por_mes:,} registros")
            
            # Salvar novamente com limite
            caminho_raw = config.RAW_DIR / config.get_nome_arquivo('sih', uf=uf, ano=ano, mes=mes)
            df_sih.to_parquet(caminho_raw, index=False)
            print(f"  [LIMITE] SIH salvo com limite em: {caminho_raw}")
        
        # Baixar CNES
        df_cnes = baixar_cnes_leitos(uf, ano, mes, upload=upload)
        
        if df_sih is not None:
            resultados['sih'].append(df_sih)
        if df_cnes is not None:
            resultados['cnes'].append(df_cnes)
    
    # Combinar todos os meses
    print("\n" + "=" * 60)
    print("COMBINANDO DADOS DE TODOS OS MESES")
    
    df_sih_combinado = pd.concat(resultados['sih'], ignore_index=True) if resultados['sih'] else None
    df_cnes_combinado = pd.concat(resultados['cnes'], ignore_index=True) if resultados['cnes'] else None
    
    if df_sih_combinado is not None:
        print(f"Total SIH: {len(df_sih_combinado):,} registros")
        # Salvar arquivo combinado
        caminho_combinado = config.RAW_DIR / f"sih_{uf}_{ano}_todos_meses.parquet"
        df_sih_combinado.to_parquet(caminho_combinado, index=False)
        print(f"SIH combinado salvo em: {caminho_combinado}")
    
    if df_cnes_combinado is not None:
        print(f"Total CNES: {len(df_cnes_combinado):,} registros")
        caminho_combinado = config.RAW_DIR / f"cnes_{uf}_{ano}_todos_meses.parquet"
        df_cnes_combinado.to_parquet(caminho_combinado, index=False)
        print(f"CNES combinado salvo em: {caminho_combinado}")
    
    print("=" * 60)
    
    # Retornar também o CID-10
    return {
        'sih': df_sih_combinado,
        'cnes': df_cnes_combinado,
        'cid10': df_cid10
    }


# ============================================================================
# 7. Função para baixar todos (mantendo compatibilidade)
# ============================================================================

def baixar_todos(uf=None, ano=None, mes=None, upload=True):
    """Versão original para um único mês (mantida para compatibilidade)."""
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if mes is None:
        mes = config.MES
    
    print("=" * 50)
    print("INICIANDO INGESTÃO DE DADOS (MÊS ÚNICO)")
    print(f"UF: {uf} | Ano: {ano} | Mês: {mes:02d}")
    print("=" * 50)
    
    resultados = {}
    resultados['sih'] = baixar_sih(uf, ano, mes, upload)
    resultados['cnes'] = baixar_cnes_leitos(uf, ano, mes, upload)
    resultados['ibge'] = baixar_ibge(uf, upload)
    resultados['cid10'] = baixar_cid10()  # Novo
    
    print("=" * 50)
    print("RESUMO DA INGESTÃO")
    print("-" * 50)
    for nome, df in resultados.items():
        status = "OK" if df is not None else "FALHA"
        registros = len(df) if df is not None else 0
        print(f"{nome.upper():10} | {status:5} | {registros:>8,} registros")
    print("=" * 50)
    
    return resultados


# ============================================================================
# 8. Main
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestão de dados do MedData v2")
    parser.add_argument('--uf', type=str, default=config.UF, help='UF do estado')
    parser.add_argument('--ano', type=int, default=config.ANO, help='Ano dos dados')
    parser.add_argument('--mes', type=int, help='Mês dos dados (opcional, para modo único)')
    parser.add_argument('--meses', nargs='+', type=int, help='Lista de meses (ex: 1 2 3)')
    parser.add_argument('--limite', type=int, default=300000, help='Limite de registros por mês')
    parser.add_argument('--upload', action='store_true', default=True, help='Fazer upload para OCI')
    parser.add_argument('--no-upload', action='store_false', dest='upload', help='Não fazer upload para OCI')
    args = parser.parse_args()
    
    # Se especificou meses ou limite, baixa múltiplos meses
    if args.meses or args.limite != 300000:
        meses = args.meses if args.meses else list(range(1, 13))
        dados = baixar_multiplos_meses(
            uf=args.uf,
            ano=args.ano,
            meses=meses,
            limite_por_mes=args.limite,
            upload=args.upload
        )
        todos_ok = dados['sih'] is not None
    elif args.mes:
        # Modo único mês (compatibilidade)
        dados = baixar_todos(uf=args.uf, ano=args.ano, mes=args.mes, upload=args.upload)
        todos_ok = all(df is not None for df in dados.values())
    else:
        # Modo automático: baixa todos os meses
        print("Modo automático: baixando todos os meses de 2024")
        dados = baixar_multiplos_meses(
            uf=args.uf,
            ano=args.ano,
            meses=list(range(1, 13)),
            limite_por_mes=args.limite,
            upload=args.upload
        )
        todos_ok = dados['sih'] is not None
    
    if todos_ok:
        print("\nSUCESSO: Ingestão concluída!")
        sys.exit(0)
    else:
        print("\nATENÇÃO: Algumas fontes falharam.")
        sys.exit(1) 