import argparse
import pandas as pd
import oci
from oci.config import from_file
from pysus import sih
from pysus import cnes
from pathlib import Path
import sys
import os
import tempfile
from typing import Optional

# Adiciona a pasta raiz ao path do Python
sys.path.append(str(Path(__file__).parent.parent))

# Importa o config
from config import config


# FUNÇÃO DE UPLOAD PARA OBJECT STORAGE
#----------------------------------------
def upload_para_object_storage(arquivo_local: Path, objeto_name: str, bucket: str = "meddata-bronze"):
    """
    Aqui nós queriamos que os arquivos salvos já fossem encaminhados
    para o Object Storage pois usamos a VM da oracle que, através dos
    scripts precisava de um fluxo.
    """

    #pesquisamos e configuramos, adicionamos tratamento de erros pra saber onde estava falhando
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



# 2. FUNÇÃO QUE BAIXA SIH
#-----------------------------------------------
def baixar_sih(
    uf: str = None, 
    ano: int = None, 
    mes: int = None,
    upload: bool = True
) -> Optional[pd.DataFrame]: #irá retornar um DF ou None
    """
    Baixa dados do SIH/SUS e envia para o Object Storage.
    """
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if mes is None:
        mes = config.MES
    
    print(f"[SIH] Baixando dados: {uf} {ano}/{mes:02d}")
    
    try:
        arquivos = sih(state=uf, year=ano, month=mes)
        if not arquivos:
            raise ValueError(f"Nenhum arquivo encontrado para {uf} {ano}/{mes}")
        
        df = pd.read_parquet(arquivos[0])
        print(f"[SIH] Carregado: {len(df):,} registros")
        
        # Salvar localmente (temporário)
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            caminho_local = Path(tmp.name)
            df.to_parquet(caminho_local, index=False)
        
        # Salvar na pasta RAW_DIR (backup local)
        caminho_raw = config.RAW_DIR / config.get_nome_arquivo('sih', uf=uf, ano=ano, mes=mes)
        df.to_parquet(caminho_raw, index=False)
        print(f"[SIH] Salvo localmente em: {caminho_raw}")
        
        # Upload para Object Storage (Camada Bronze)
        if upload:
            objeto_name = f"sih/{uf}/{ano}/sih_{uf}_{ano}_{mes:02d}.parquet"
            upload_para_object_storage(caminho_local, objeto_name, "meddata-bronze")
        
        # Limpar arquivo temporário
        os.remove(caminho_local)

        ##ver se precisa do arquivo temp
        
        return df
    
    except Exception as e:
        print(f"[ERRO SIH] {str(e)}")
        return None


# ============================================================
# 3. FUNÇÃO QUE BAIXA CNES
# ============================================================
def baixar_cnes_leitos(
    uf: str = None,
    ano: int = None,
    mes: int = None,
    upload: bool = True
) -> Optional[pd.DataFrame]:
    """
    Baixa dados de leitos do CNES e envia para o Object Storage.
    """
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
            raise ValueError(f"Nenhum arquivo encontrado para {uf} {ano}/{mes}")
        
        df = pd.read_parquet(arquivos[0])
        print(f"[CNES] Carregado: {len(df):,} registros")
        
        # Salvar localmente (temporário)
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            caminho_local = Path(tmp.name)
            df.to_parquet(caminho_local, index=False)
        
        # Salvar na pasta RAW_DIR
        caminho_raw = config.RAW_DIR / config.get_nome_arquivo('cnes', uf=uf, ano=ano, mes=mes)
        df.to_parquet(caminho_raw, index=False)
        print(f"[CNES] Salvo localmente em: {caminho_raw}")
        
        # Upload para Object Storage
        if upload:
            objeto_name = f"cnes/{uf}/{ano}/cnes_{uf}_{ano}_{mes:02d}.parquet"
            upload_para_object_storage(caminho_local, objeto_name, "meddata-bronze")
        
        os.remove(caminho_local)
        
        return df
    
    except Exception as e:
        print(f"[ERRO CNES] {str(e)}")
        return None


# ============================================================
# 4. FUNÇÃO QUE BAIXA IBGE
# ============================================================
##aqui 
def baixar_ibge(
    uf: str = None,
    upload: bool = True
) -> Optional[pd.DataFrame]:
    """
    Baixa dados de municípios do IBGE e envia para o Object Storage.
    """
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

        # Criar a coluna 'uf' a partir do 'codigo_uf'
        df['uf'] = df['codigo_uf'].map(codigo_para_uf).fillna('NA')

        print(f"[IBGE] Carregado: {len(df):,} municípios")

        # Salvar localmente
        caminho_ref = config.REFERENCE_DIR / config.get_nome_arquivo('ibge', uf=uf, ano=None, mes=None)
        df.to_parquet(caminho_ref, index=False)
        print(f"[IBGE] Salvo localmente: {caminho_ref}")

        if upload:
            objeto_name = f"ibge/{uf}/ibge_{uf}.parquet"
            upload_para_object_storage(caminho_ref, objeto_name, "meddata-bronze")

        return df

    except Exception as e:
        print(f"[ERRO IBGE] {str(e)}")
        return None

# ============================================================
# 5. FUNÇÃO PARA BAIXAR TODOS
# ============================================================
def baixar_todos(
    uf: str = None,
    ano: int = None,
    mes: int = None,
    upload: bool = True
) -> dict:
    """
    Baixa todas as fontes de dados de uma vez.
    """
    if uf is None:
        uf = config.UF
    if ano is None:
        ano = config.ANO
    if mes is None:
        mes = config.MES
    
    print("=" * 50)
    print("INICIANDO INGESTÃO DE DADOS")
    print(f"UF: {uf} | Ano: {ano} | Mês: {mes:02d}")
    print(f"Upload para OCI: {'SIM' if upload else 'NÃO'}")
    print("=" * 50)
    
    resultados = {}
    resultados['sih'] = baixar_sih(uf, ano, mes, upload)
    resultados['cnes'] = baixar_cnes_leitos(uf, ano, mes, upload)
    resultados['ibge'] = baixar_ibge(uf, upload)
    
    print("=" * 50)
    print("RESUMO DA INGESTÃO")
    print("-" * 50)
    for nome, df in resultados.items():
        status = "OK" if df is not None else "FALHA"
        registros = len(df) if df is not None else 0
        print(f"{nome.upper():10} | {status:5} | {registros:>8,} registros")
    print("=" * 50)
    
    return resultados


# ============================================================
# 6. MAIN COM ARGPARSE
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestão de dados do MedData")
    parser.add_argument('--uf', type=str, default=config.UF, help='UF do estado')
    parser.add_argument('--ano', type=int, default=config.ANO, help='Ano dos dados')
    parser.add_argument('--mes', type=int, default=config.MES, help='Mês dos dados')
    parser.add_argument('--upload', action='store_true', default=True, help='Fazer upload para OCI')
    parser.add_argument('--no-upload', action='store_false', dest='upload', help='Não fazer upload para OCI')
    args = parser.parse_args()
    
    dados = baixar_todos(uf=args.uf, ano=args.ano, mes=args.mes, upload=args.upload)
    
    todos_ok = all(df is not None for df in dados.values())
    
    if todos_ok:
        print("\nSUCESSO: Ingestão concluída!")
        sys.exit(0)
    else:
        print("\nATENÇÃO: Algumas fontes falharam.")
        sys.exit(1)