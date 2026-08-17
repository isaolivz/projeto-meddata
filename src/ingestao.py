"""
ingestao.py - Ingestao de dados do SUS para o MedData.

Este modulo baixa dados do SIH/SUS, CNES e IBGE e os envia para o Object Storage.
Suporta execucao com argumentos para UF, ano e mes.

Uso:
    python src/ingestao.py --uf PR --ano 2024 --mes 1
    python src/ingestao.py --uf SP --ano 2024 --mes 1 2 3  (multiplos meses)
"""

import argparse
import pandas as pd
import oci
from oci.config import from_file
from pysus import SIH, CNES
from pathlib import Path
import sys
import os
import tempfile
from typing import Optional, List

sys.path.append(str(Path(__file__).parent.parent))
from config import config


# ================================================================
# FUNCAO DE UPLOAD PARA OBJECT STORAGE
# ================================================================

def upload_para_object_storage(arquivo_local: Path, objeto_name: str, bucket: str = "meddata-bronze") -> bool:
    """
    Envia um arquivo para o Object Storage da OCI.
    """
    try:
        config_oci = from_file()
        object_storage = oci.object_storage.ObjectStorageClient(config_oci)
        namespace = object_storage.get_namespace().data

        with open(arquivo_local, "rb") as arquivo:
            object_storage.put_object(namespace, bucket, objeto_name, arquivo)

        print(f"[OCI] Upload concluido: {bucket}/{objeto_name}")
        return True
    except Exception as e:
        print(f"[ERRO OCI] Falha no upload: {str(e)}")
        return False


# ================================================================
# 1. FUNCAO QUE BAIXA SIH
# ================================================================

def baixar_sih(
    uf: str = None,
    ano: int = None,
    mes: int = None,
    upload: bool = True
) -> Optional[pd.DataFrame]:
    """
    Baixa dados do SIH/SUS e envia para o Object Storage.

    Args:
        uf: Sigla da UF (ex: PR, SP)
        ano: Ano dos dados
        mes: Mes dos dados (1-12)
        upload: Se True, faz upload para o Object Storage

    Returns:
        DataFrame com os dados baixados ou None em caso de erro
    """
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES

    print(f"[SIH] Baixando dados: {uf} {ano}/{mes:02d}")

    try:
        # Usar SIH (classe) em vez de sih (funcao)
        sih = SIH()
        arquivos = sih.download(uf, ano, months=[mes])

        if not arquivos:
            raise ValueError(f"Nenhum arquivo encontrado para {uf} {ano}/{mes}")

        df = pd.read_parquet(arquivos[0])
        print(f"[SIH] Carregado: {len(df):,} registros")

        # Salvar localmente
        caminho_raw = config.RAW_DIR / config.get_nome_arquivo('sih', uf=uf, ano=ano, mes=mes)
        df.to_parquet(caminho_raw, index=False)
        print(f"[SIH] Salvo localmente: {caminho_raw}")

        # Upload para Object Storage
        if upload:
            objeto_name = f"sih/{uf}/{ano}/sih_{uf}_{ano}_{mes:02d}.parquet"
            upload_para_object_storage(caminho_raw, objeto_name, "meddata-bronze")

        return df

    except Exception as e:
        print(f"[ERRO SIH] {str(e)}")
        return None


# ================================================================
# 2. FUNCAO QUE BAIXA CNES
# ================================================================

def baixar_cnes_leitos(
    uf: str = None,
    ano: int = None,
    mes: int = None,
    upload: bool = True
) -> Optional[pd.DataFrame]:
    """
    Baixa dados de leitos do CNES (grupo LT) e envia para o Object Storage.
    """
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES

    print(f"[CNES] Baixando dados: {uf} {ano}/{mes:02d}")

    try:
        cnes = CNES()
        arquivos = cnes.download(uf, ano, months=[mes], group="LT")

        if not arquivos:
            raise ValueError(f"Nenhum arquivo encontrado para {uf} {ano}/{mes}")

        df = pd.read_parquet(arquivos[0])
        print(f"[CNES] Carregado: {len(df):,} registros")

        caminho_raw = config.RAW_DIR / config.get_nome_arquivo('cnes', uf=uf, ano=ano, mes=mes)
        df.to_parquet(caminho_raw, index=False)
        print(f"[CNES] Salvo localmente: {caminho_raw}")

        if upload:
            objeto_name = f"cnes/{uf}/{ano}/cnes_{uf}_{ano}_{mes:02d}.parquet"
            upload_para_object_storage(caminho_raw, objeto_name, "meddata-bronze")

        return df

    except Exception as e:
        print(f"[ERRO CNES] {str(e)}")
        return None


# ================================================================
# 3. FUNCAO QUE BAIXA CNES COMPLETO (ESTABELECIMENTOS)
# ================================================================

def baixar_cnes_estabelecimentos(
    uf: str = None,
    ano: int = None,
    mes: int = None,
    upload: bool = True
) -> Optional[pd.DataFrame]:
    """
    Baixa dados completos do CNES (estabelecimentos) com nome e localizacao.
    """
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES

    print(f"[CNES] Baixando estabelecimentos: {uf} {ano}/{mes:02d}")

    try:
        cnes = CNES()
        arquivos = cnes.download(uf, ano, months=[mes], group="estabelecimentos")

        if not arquivos:
            raise ValueError(f"Nenhum arquivo de estabelecimentos para {uf} {ano}/{mes}")

        df = pd.read_parquet(arquivos[0])
        print(f"[CNES] Estabelecimentos carregados: {len(df):,} registros")

        caminho_raw = config.RAW_DIR / f"cnes_estabelecimentos_{uf}_{ano}_{mes:02d}.parquet"
        df.to_parquet(caminho_raw, index=False)
        print(f"[CNES] Salvo localmente: {caminho_raw}")

        if upload:
            objeto_name = f"cnes/{uf}/{ano}/cnes_estabelecimentos_{uf}_{ano}_{mes:02d}.parquet"
            upload_para_object_storage(caminho_raw, objeto_name, "meddata-bronze")

        return df

    except Exception as e:
        print(f"[ERRO CNES] Falha ao baixar estabelecimentos: {str(e)}")
        return None


# ================================================================
# 4. FUNCAO QUE BAIXA IBGE
# ================================================================

def baixar_ibge(
    uf: str = None,
    upload: bool = True
) -> Optional[pd.DataFrame]:
    """
    Baixa dados de municipios do IBGE e envia para o Object Storage.
    """
    uf = uf or config.UF

    print(f"[IBGE] Carregando dados para {uf}")

    try:
        codigo_uf = config.get_codigo_uf(uf)
        if codigo_uf is None:
            raise ValueError(f"UF '{uf}' nao encontrada.")

        url = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
        df = pd.read_csv(url)
        df = df[df['codigo_uf'] == codigo_uf].copy()

        if len(df) == 0:
            raise ValueError(f"Nenhum municipio encontrado para UF '{uf}'")

        print(f"[IBGE] Carregado: {len(df):,} municipios")

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


# ================================================================
# 5. FUNCAO PARA BAIXAR MULTIPLOS MESES
# ================================================================

def baixar_meses(
    uf: str = None,
    ano: int = None,
    meses: List[int] = None,
    upload: bool = True
) -> dict:
    """
    Baixa dados para multiplos meses de uma vez.

    Args:
        uf: Sigla da UF
        ano: Ano dos dados
        meses: Lista de meses (ex: [1, 2, 3])
        upload: Se True, faz upload para o Object Storage

    Returns:
        Dicionario com os resultados por mes
    """
    uf = uf or config.UF
    ano = ano or config.ANO
    meses = meses or [config.MES]

    resultados = {}

    for mes in meses:
        print(f"\n--- Processando {uf} {ano}/{mes:02d} ---")
        resultados[mes] = {
            'sih': baixar_sih(uf, ano, mes, upload),
            'cnes_leitos': baixar_cnes_leitos(uf, ano, mes, upload),
            'cnes_estabelecimentos': baixar_cnes_estabelecimentos(uf, ano, mes, upload),
            'ibge': baixar_ibge(uf, upload) if mes == meses[0] else None
        }

    return resultados


# ================================================================
# 6. FUNCAO PARA BAIXAR TUDO (UM MES)
# ================================================================

def baixar_todos(
    uf: str = None,
    ano: int = None,
    mes: int = None,
    upload: bool = True
) -> dict:
    """
    Baixa todas as fontes de dados para um mes especifico.
    """
    uf = uf or config.UF
    ano = ano or config.ANO
    mes = mes or config.MES

    print("=" * 50)
    print("INICIANDO INGESTAO DE DADOS")
    print(f"UF: {uf} | Ano: {ano} | Mes: {mes:02d}")
    print(f"Upload para OCI: {'SIM' if upload else 'NAO'}")
    print("=" * 50)

    resultados = {
        'sih': baixar_sih(uf, ano, mes, upload),
        'cnes_leitos': baixar_cnes_leitos(uf, ano, mes, upload),
        'cnes_estabelecimentos': baixar_cnes_estabelecimentos(uf, ano, mes, upload),
        'ibge': baixar_ibge(uf, upload)
    }

    print("\n" + "=" * 50)
    print("RESUMO DA INGESTAO")
    print("-" * 50)
    for nome, df in resultados.items():
        status = "OK" if df is not None else "FALHA"
        registros = len(df) if df is not None else 0
        print(f"{nome.upper():25} | {status:5} | {registros:>8,} registros")
    print("=" * 50)

    return resultados


# ================================================================
# 7. MAIN COM ARGPARSE
# ================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestao de dados do MedData")
    parser.add_argument('--uf', type=str, default=config.UF, help='UF do estado')
    parser.add_argument('--ano', type=int, default=config.ANO, help='Ano dos dados')
    parser.add_argument('--mes', type=int, default=config.MES, help='Mes dos dados (1-12)')
    parser.add_argument('--meses', type=int, nargs='+', help='Multiplos meses (ex: 1 2 3)')
    parser.add_argument('--upload', action='store_true', default=True, help='Fazer upload para OCI')
    parser.add_argument('--no-upload', action='store_false', dest='upload', help='Nao fazer upload para OCI')
    args = parser.parse_args()

    # Se --meses for passado, baixar multiplos meses
    if args.meses:
        resultados = baixar_meses(args.uf, args.ano, args.meses, args.upload)
        todos_ok = all(
            all(df is not None for df in mes_result.values() if df is not None)
            for mes_result in resultados.values()
        )
    else:
        resultados = baixar_todos(args.uf, args.ano, args.mes, args.upload)
        todos_ok = all(df is not None for df in resultados.values())

    if todos_ok:
        print("\nSUCESSO: Ingestao concluida!")
        sys.exit(0)
    else:
        print("\nATENCAO: Algumas fontes falharam.")
        sys.exit(1)