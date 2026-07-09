# Funções para ingestão de dados

import pandas as pd
from pysus import sih
from pysus import cnes
from pathlib import Path
import sys
import os

#caminho raiz
sys.path.append('/content/meddata-project')

#importando o config
from config import RAW_DIR, UF, ANO, MES, REFERENCE_DIR

#funcao para baixar os dados do sih
def baixar_sih(uf=UF, ano=ANO, mes=MES):
    
    print(f"Baixando SIH/SUS: {uf} {ano}/{mes}")
    arquivos = sih(state=uf, year=ano, month=mes)

    if not arquivos:
        raise ValueError(f"Nenhum arquivo encontrado para {uf} {ano}/{mes}")
    
    df = pd.read_parquet(arquivos[0])
    print(f" SIH carregado: {len(df):,} registros")
    
    # Salvar cópia bruta
    caminho = RAW_DIR / f"sih_{uf}_{ano}_{mes:02d}.parquet"
    df.to_parquet(caminho)
    print(f"Dados brutos salvos em: {caminho}")
    
    return df

#funcao para baixar os dados do cnes
def baixar_cnes_leitos(uf= UF, ano=ANO, mes=MES):
    print(f"Baixando CNES {uf} {ano}/{mes}")

    arquivos = cnes(state=uf, year=ano,month=mes, group="LT")
    if not arquivos:
        raise ValueError(f"Nnenhum arquivo de leitos encontradopara {uf} {ano}/{mes}")
 
    df = pd.read_parquet(arquivos[0])
    
    print(f" CNES Leitos carregado: {len(df)} hospitais")
    
    # Salvar cópia
    caminho = RAW_DIR / f"cnes_leitos_{uf}_{ano}_{mes:02d}.parquet"
    df.to_parquet(caminho)
    print(f"Dados salvos em: {caminho}")
    
    return df

#funcao para baixar dados do ibge
def baixar_ibge(uf=UF):

    codigos_uf = {
        'PR': 41, 'SP': 35, 'RJ': 33, 'MG': 31,
        'BA': 29, 'RS': 43, 'SC': 42, 'GO': 52,
        'PE': 26, 'CE': 23, 'PA': 15, 'AM': 13,
        'MT': 51, 'MS': 50, 'DF': 53, 'ES': 32,
        'MA': 21, 'RN': 24, 'PB': 25, 'PI': 22,
        'AL': 27, 'SE': 28, 'TO': 17, 'RO': 11,
        'AC': 12, 'AP': 16, 'RR': 14
    }
    if uf not in codigos_uf:
        raise ValueError(f"UF '{uf}' não encontrada. Use uma das: {list(codigos_uf.keys())}")
    
    codigo_uf = codigos_uf[uf]
    
    # Baixa os dados
    url = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
    df = pd.read_csv(url)
    
    # Filtra pela UF
    df = df[df['codigo_uf'] == codigo_uf].copy()
    
    if len(df) == 0:
        raise ValueError(f"Nenhum município encontrado para UF '{uf}' (código {codigo_uf})")
    
    print(f"IBGE carregado: {len(df)} municípios")
    
    # Salvar
    caminho = REFERENCE_DIR / f"ibge_{uf}.parquet"
    df.to_parquet(caminho)
    print(f"Dados salvos em: {caminho}")
    
    return df

if __name__ == "__main__":
    baixar_sih()
    baixar_cnes_leitos()
    baixar_ibge()