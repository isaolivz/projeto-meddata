import pandas as pd
from pysus import sih
from pysus import cnes
from pathlib import Path
import sys
from typing import Optional 

# Adiciona a pasta raiz ao path do Python
sys.path.append(str(Path(__file__).parent.parent))

# 1. IMPORTANDO O CONFIG
# -----------------------------------------
from config import(
    RAW_DIR, 
    REFERENCE_DIR, 
    UF, 
    ANO, 
    MES, 
    get_codigo_uf,
    get_nome_arquivo
)

# 2. FUNÇÃO QUE BAIXA SIH
# -----------------------------------------
def baixar_sih(
    uf: str = UF, 
    ano: int = ANO, 
    mes: int = MES
) -> Optional[pd.DataFrame]:
    """
    Baixa dados do SIH/SUS para uma UF específica.
    
    Args:
        uf: Sigla do estado (ex: 'SP', 'PR')
        ano: Ano dos dados (ex: 2024)
        mes: Mês dos dados (1-12)
    
    Returns:
        DataFrame com os dados do SIH ou None se erro.
    """
    print(f"[SIH] Baixando dados: {uf} {ano}/{mes:02d}")
    
    try:
        arquivos = sih(state=uf, year=ano, month=mes)

        if not arquivos:
            raise ValueError(f"Nenhum arquivo encontrado para {uf} {ano}/{mes}")
        
        df = pd.read_parquet(arquivos[0])
        print(f"[SIH] Carregado: {len(df):,} registros")

        caminho = RAW_DIR / get_nome_arquivo('sih')
        df.to_parquet(caminho, index=False)
        print(f"[SIH] Dados salvos em: {caminho}")

        return df
    
    except Exception as e:
        print(f"[ERRO SIH] {str(e)}") 
        return None
    
# 3. FUNÇÃO QUE BAIXA CNES
# -----------------------------------------
def baixar_cnes_leitos(
    uf: str = UF,
    ano: int = ANO,
    mes: int = MES,
) -> Optional[pd.DataFrame]:
    """
    Baixa dados de leitos do CNES para uma UF específica.
    
    Args:
        uf: Sigla do estado (ex: 'SP', 'PR')
        ano: Ano dos dados
        mes: Mês dos dados (1-12)
    
    Returns:
        DataFrame com dados de leitos ou None se erro.
    """
    
    print(f"[CNES] Baixando dados {uf} {ano}/{mes:02d}")

    try:
        arquivos = cnes(state=uf, year=ano, month=mes, group="LT")

        if not arquivos:
            raise ValueError(f"Nenhum arquivo encontrado para {uf} {ano}/{mes}")

        df = pd.read_parquet(arquivos[0])
        print(f"[CNES] Carregado: {len(df)} registros")  

        caminho = RAW_DIR / get_nome_arquivo('cnes')
        df.to_parquet(caminho, index=False)
        print(f"[CNES] Dados salvos em: {caminho}")

        return df
    
    except Exception as e:
        print(f"[ERRO CNES] {str(e)}")
        return None
    
# 4. FUNCAO QUE BAIXA IBGE
# -----------------------------------------
def baixar_ibge(
    uf: str = UF,
    ano: int = ANO,
    mes: int = MES
) -> Optional[pd.DataFrame]:
    """
    Baixa dados de municípios do IBGE para uma UF específica.
    
    Args:
        uf: Sigla do estado (ex: 'SP', 'PR')
    
    Returns:
        DataFrame com dados do IBGE ou None se erro.
    """
    
    print(f"[IBGE] Carregando dados para {uf}")

    try:
        codigo_uf = get_codigo_uf(uf)

        if codigo_uf is None:
            raise ValueError(f"UF '{uf}' não encontrada. Use uma das: {list(CODIGOS_UF.keys())}")
        
        url = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"

        df = pd.read_csv(url)

        df = df[df['codigo_uf'] == codigo_uf].copy()

        if len(df) == 0:
            raise ValueError(f"Nenhum município encontrado para UF '{uf} (código: {codigo_uf})'")
        
        print(f"[IBGE] Carregado: {len(df):,} municípios")  

        caminho = REFERENCE_DIR / get_nome_arquivo('ibge')
        df.to_parquet(caminho, index=False)
        print(f"[IBGE] Dados salvos em: {caminho}")

        return df
    
    except Exception as e:
        print(f"[ERRO IBGE] {str(e)}")
        return None
    
# 5. FUNCAO PARA BAIXAR TODOS
# -----------------------------------------
def baixar_todos(
    uf: str = UF, 
    ano: int = ANO, 
    mes: int = MES
) -> dict:
    """
    Baixa todas as fontes de dados de uma vez.
    
    Args:
        uf: Sigla do estado
        ano: Ano dos dados
        mes: Mês dos dados
    
    Returns:
        Dicionário com os DataFrames baixados.
    """
    print("=" * 50)
    print("INICIANDO INGESTÃO DE DADOS")
    print(f"UF: {uf} | Ano: {ano} | Mês: {mes:02d}")
    print("=" * 50)
    
    resultados = {}
    
    resultados['sih'] = baixar_sih(uf, ano, mes)
    resultados['cnes'] = baixar_cnes_leitos(uf, ano, mes)
    resultados['ibge'] = baixar_ibge(uf)
    
    print("=" * 50)
    print("RESUMO DA INGESTÃO")
    print("-" * 50)
    for nome, df in resultados.items():
        status = "OK" if df is not None else "FALHA"
        registros = len(df) if df is not None else 0
        print(f"{nome.upper():10} | {status:5} | {registros:>8,} registros")
    print("=" * 50)
    
    return resultados


if __name__ == "__main__":
    dados = baixar_todos()
    
    todos_ok = all(df is not None for df in dados.values())
    
    if todos_ok:
        print("\n[SUCESSO] Ingestão concluída com sucesso!")
    else:
        print("\n[ATENCAO] Algumas fontes falharam. Verifique os erros acima.")