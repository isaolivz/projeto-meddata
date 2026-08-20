"""
Modulo de transformacao de dados para o projeto MedData.

Este modulo contem funcoes para limpeza, transformacao e integracao
das tres fontes de dados:
- SIH/SUS (internacoes hospitalares)
- CNES (estabelecimentos de saude e leitos)
- IBGE (municipios e coordenadas)

Uso:
    from transformacao import TransformadorDados
    
    transformador = TransformadorDados(config)
    dados = transformador.executar_pipeline(df_sih_raw, df_cnes_raw, df_ibge_raw)
"""

import argparse
import pandas as pd
import numpy as np
import oci
from oci.config import from_file
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

# Configuracao de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# FUNÇÃO DE UPLOAD PARA OBJECT STORAGE
# ============================================================
def upload_para_object_storage(arquivo_local: Path, objeto_name: str, bucket: str = "meddata-gold"):
    """
    Faz upload de um arquivo para o Object Storage da OCI.
    
    Args:
        arquivo_local: Caminho do arquivo local
        objeto_name: Nome do objeto no Object Storage
        bucket: Nome do bucket (padrão: meddata-gold)
    """
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


# ================================================================
# CLASSE TRANSFORMADORDADOS
# ================================================================

class TransformadorDados:
    """
    Classe principal para transformacao e integracao dos dados do MedData.
    
    Attributes:
        config: Objeto de configuracao do projeto
        uf: Unidade Federativa
        ano: Ano de referencia
        mes: Mes de referencia
    """
    
    def __init__(self, config):
        """
        Inicializa o transformador com as configuracoes do projeto.
        
        Args:
            config: Objeto Config do projeto
        """
        self.config = config
        self.uf = config.UF
        self.ano = config.ANO
        self.mes = config.MES
        self.logger = logger
        
        # Dicionario de mapeamento para tipos de leito
        self.MAPEAMENTO_LEITOS = {
            '1': 'Clinico',
            '2': 'Cirurgico',
            '3': 'Obstetrico',
            '4': 'Pediatrico',
            '5': 'UTI',
            '6': 'Isolamento',
            '7': 'Outros'
        }
        
        # Dicionario de mapeamento para esfera
        self.MAPEAMENTO_ESFERA = {
            'E': 'Estadual',
            'M': 'Municipal',
            'F': 'Federal',
            '': 'Não Informado',
        }
        
        self.logger.info(f"Transformador inicializado para {self.uf} {self.ano}/{self.mes:02d}")
    
    # ================================================================
    # 1. TRANSFORMACAO DO SIH/SUS
    # ================================================================
    
    def transformar_sih(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma dados brutos do SIH/SUS.
        
        Etapas:
        1. Selecao de colunas essenciais
        2. Conversao de tipos
        3. Remocao de duplicatas
        4. Padronizacao de IDs
        5. Renomeacao de colunas
        6. Criacao de features
        """
        self.logger.info(f"Transformando SIH: {len(df):,} registros")
        
        # 1. Selecionar colunas essenciais
        colunas_essenciais = [
            'SP_GESTOR',
            'SP_CNES',
            'SP_CIDPRI',
            'SP_DTINTER',
            'SP_DTSAIDA',
            'SP_VALATO',
            'SP_M_PAC',
            'SP_AA',
            'SP_MM'
        ]
        
        df_transformado = df[colunas_essenciais].copy()
        
        # 2. Converter tipos
        df_transformado['SP_DTINTER'] = pd.to_datetime(df_transformado['SP_DTINTER'], format='%Y%m%d', errors='coerce')
        df_transformado['SP_DTSAIDA'] = pd.to_datetime(df_transformado['SP_DTSAIDA'], format='%Y%m%d', errors='coerce')
        df_transformado['SP_VALATO'] = pd.to_numeric(df_transformado['SP_VALATO'], errors='coerce')
        df_transformado['SP_AA'] = pd.to_numeric(df_transformado['SP_AA'], errors='coerce').fillna(0).astype(int)
        df_transformado['SP_MM'] = pd.to_numeric(df_transformado['SP_MM'], errors='coerce').fillna(0).astype(int)
        
        # 3. Remover duplicatas exatas
        df_transformado = df_transformado.drop_duplicates()
        
        # 4. Padronizar IDs
        df_transformado['SP_CNES'] = df_transformado['SP_CNES'].astype(str).str.zfill(7)
        df_transformado['SP_GESTOR'] = df_transformado['SP_GESTOR'].astype(str).str.zfill(6)
        df_transformado['SP_M_PAC'] = df_transformado['SP_M_PAC'].astype(str).str.zfill(6)
        
        # 5. Renomear colunas
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
        df_transformado.rename(columns=mapeamento_colunas, inplace=True)
        
        # 6. Criar features
        df_transformado['dias_internacao'] = (
            df_transformado['data_saida'] - df_transformado['data_internacao']
        ).dt.days.fillna(0).clip(lower=0)
        
        df_transformado['paciente_viajou'] = (
            df_transformado['codigo_municipio_paciente'] != df_transformado['codigo_municipio']
        )
        
        df_transformado['dia_semana'] = df_transformado['data_internacao'].dt.day_name()
        df_transformado['mes_ano'] = pd.PeriodIndex(
            year=df_transformado['ano_competencia'],
            month=df_transformado['mes_competencia'],
            freq='M'
        )
        
        self.logger.info(f"SIH transformado: {len(df_transformado):,} registros")
        return df_transformado
    
    # ================================================================
    # 2. TRANSFORMACAO DO CNES
    # ================================================================
    
    def transformar_cnes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma dados brutos do CNES.
        """
        self.logger.info(f"Transformando CNES: {len(df):,} registros")
        
        # 1. Padronizar nomes das colunas
        df.columns = [col.upper() for col in df.columns]
        
        # 2. Selecionar colunas relevantes
        colunas_selecionadas = [
            'CNES', 'CODUFMUN', 'TP_LEITO', 'QT_EXIST', 'QT_CONTR',
            'QT_SUS', 'QT_NSUS', 'ESFERA_A', 'TP_UNID', 'NIV_HIER', 'NAT_JUR'
        ]
        
        colunas_presentes = [col for col in colunas_selecionadas if col in df.columns]
        df_selecionado = df[colunas_presentes].copy()
        
        # 3. Converter tipos
        colunas_numericas = ['QT_EXIST', 'QT_CONTR', 'QT_SUS', 'QT_NSUS']
        for col in colunas_numericas:
            if col in df_selecionado.columns:
                df_selecionado[col] = pd.to_numeric(df_selecionado[col], errors='coerce').fillna(0).astype(int)
        
        # 4. Agrupar por hospital
        colunas_agrupar = [col for col in df_selecionado.columns if col not in colunas_numericas]
        colunas_somar = [col for col in df_selecionado.columns if col in colunas_numericas]
        df_agrupado = df_selecionado.groupby(colunas_agrupar)[colunas_somar].sum().reset_index()
        
        # 5. Padronizar CNES
        df_agrupado['CNES'] = df_agrupado['CNES'].astype(str).str.zfill(7)
        
        # 6. Renomear colunas
        mapeamento = {
            'CNES': 'id_hospital',
            'CODUFMUN': 'codigo_municipio',
            'TP_LEITO': 'tipo_leito',
            'QT_EXIST': 'total_leitos',
            'QT_CONTR': 'leitos_contratados',
            'QT_SUS': 'leitos_sus',
            'QT_NSUS': 'leitos_nao_sus',
            'ESFERA_A': 'esfera',
            'TP_UNID': 'tipo_unidade',
            'NIV_HIER': 'nivel_hierarquico',
            'NAT_JUR': 'natureza_juridica',
        }
        df_agrupado.rename(columns=mapeamento, inplace=True)
        
        # 7. Mapear tipos de leito
        df_agrupado['tipo_leito_nome'] = df_agrupado['tipo_leito'].map(self.MAPEAMENTO_LEITOS).fillna('Outros')
        
        # 8. Classificar porte
        def classificar_porte(total):
            if total >= 150:
                return 'Grande Porte'
            elif total >= 50:
                return 'Medio Porte'
            elif total >= 15:
                return 'Pequeno Porte'
            return 'Micro Porte'
        
        df_agrupado['porte_hospitalar'] = df_agrupado['total_leitos'].apply(classificar_porte)
        
        # 9. Classificar complexidade
        df_agrupado['alta_complexidade'] = df_agrupado['nivel_hierarquico'].apply(
            lambda x: 'Alta Complexidade' if pd.notna(x) and x != '' else 'Baixa/Media Complexidade'
        )
        
        # 10. Classificar esfera
        df_agrupado['esfera_classificacao'] = df_agrupado['esfera'].map(self.MAPEAMENTO_ESFERA).fillna('Não Informado')
        
        # 11. Percentual de leitos SUS
        df_agrupado['percentual_sus'] = (
            df_agrupado['leitos_sus'] / df_agrupado['total_leitos'] * 100
        ).fillna(0).clip(0, 100).round(2)
        
        self.logger.info(f"CNES transformado: {len(df_agrupado):,} hospitais")
        return df_agrupado
    
    # ================================================================
    # 3. TRANSFORMACAO DO IBGE
    # ================================================================
    
    def transformar_ibge(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma dados do IBGE.
        """
        self.logger.info(f"Transformando IBGE: {len(df):,} municipios")
        
        colunas = ['codigo_ibge', 'nome', 'latitude', 'longitude']
        df_transformado = df[colunas].copy()
        df_transformado['codigo_ibge'] = df_transformado['codigo_ibge'].astype(str).str[:6]
        
        mapeamento = {
            'codigo_ibge': 'codigo_municipio',
            'nome': 'nome_municipio',
            'latitude': 'latitude',
            'longitude': 'longitude'
        }
        df_transformado.rename(columns=mapeamento, inplace=True)
        
        self.logger.info(f"IBGE transformado: {len(df_transformado):,} municipios")
        return df_transformado
    
    # ================================================================
    # 4. INTEGRACAO DOS DADOS
    # ================================================================
    
    def integrar_dados(
        self,
        df_sih: pd.DataFrame,
        df_cnes: pd.DataFrame,
        df_ibge: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Integra as tres fontes de dados.
        """
        self.logger.info("Iniciando integracao dos dados")
        
        # 1. Merge SIH + CNES
        df_integrado = df_sih.merge(
            df_cnes,
            on='id_hospital',
            how='left',
            suffixes=('', '_cnes')
        )
        
        # 2. Renomear colunas do CNES
        rename_cnes = {
            'codigo_municipio_cnes': 'codigo_municipio_hospital',
            'total_leitos': 'leitos_totais',
            'leitos_sus': 'leitos_sus',
            'leitos_nao_sus': 'leitos_nao_sus',
            'tipo_unidade': 'tipo_unidade',
            'esfera': 'esfera',
            'esfera_classificacao': 'esfera_classificacao',
            'porte_hospitalar': 'porte_hospitalar',
            'alta_complexidade': 'alta_complexidade',
            'percentual_sus': 'percentual_sus_hospital',
        }
        df_integrado.rename(columns=rename_cnes, inplace=True)
        
        # 3. Merge com IBGE (hospital)
        df_ibge_hospital = df_ibge[['codigo_municipio', 'nome_municipio', 'latitude', 'longitude']].copy()
        df_ibge_hospital.rename(columns={
            'nome_municipio': 'nome_municipio_hospital',
            'latitude': 'latitude_hospital',
            'longitude': 'longitude_hospital'
        }, inplace=True)
        df_integrado = df_integrado.merge(df_ibge_hospital, on='codigo_municipio', how='left')
        
        # 4. Merge com IBGE (paciente)
        df_ibge_paciente = df_ibge[['codigo_municipio', 'nome_municipio', 'latitude', 'longitude']].copy()
        df_ibge_paciente.rename(columns={
            'codigo_municipio': 'codigo_municipio_paciente_ibge',
            'nome_municipio': 'nome_municipio_paciente',
            'latitude': 'latitude_paciente',
            'longitude': 'longitude_paciente'
        }, inplace=True)
        df_integrado = df_integrado.merge(
            df_ibge_paciente,
            left_on='codigo_municipio_paciente',
            right_on='codigo_municipio_paciente_ibge',
            how='left'
        )
        if 'codigo_municipio_paciente_ibge' in df_integrado.columns:
            df_integrado.drop(columns=['codigo_municipio_paciente_ibge'], inplace=True)
        
        # 5. Calcular distancia
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
        
        df_integrado['distancia_estimada_km'] = df_integrado.apply(
            lambda row: haversine(
                row.get('latitude_hospital', np.nan),
                row.get('longitude_hospital', np.nan),
                row.get('latitude_paciente', np.nan),
                row.get('longitude_paciente', np.nan)
            ),
            axis=1
        )
        
        # 6. Calcular ocupacao
        df_integrado['ano_mes'] = pd.PeriodIndex(
            year=df_integrado['ano_competencia'],
            month=df_integrado['mes_competencia'],
            freq='M'
        )
        
        internacoes_por_hospital = df_integrado.groupby(['id_hospital', 'ano_mes']).agg({
            'dias_internacao': 'sum',
            'id_hospital': 'count'
        }).rename(columns={'id_hospital': 'total_internacoes'}).reset_index()
        
        df_ocupacao = internacoes_por_hospital.merge(
            df_cnes[['id_hospital', 'leitos_sus']],
            on='id_hospital',
            how='left'
        )
        
        df_ocupacao['dias_disponiveis'] = df_ocupacao['leitos_sus'] * 30
        df_ocupacao['taxa_ocupacao'] = (
            df_ocupacao['dias_internacao'] / df_ocupacao['dias_disponiveis'] * 100
        ).clip(0, 100).fillna(0)
        
        self.logger.info(f"Integracao concluida: {len(df_integrado):,} registros")
        return df_integrado, df_ocupacao
    
    # ================================================================
    # 5. PIPELINE COMPLETO
    # ================================================================
    
    def executar_pipeline(
        self,
        df_sih_raw: pd.DataFrame,
        df_cnes_raw: pd.DataFrame,
        df_ibge_raw: pd.DataFrame,
        salvar: bool = True,
        upload: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Executa o pipeline completo de transformacao.
        """
        self.logger.info("=" * 60)
        self.logger.info("INICIANDO PIPELINE DE TRANSFORMACAO")
        self.logger.info("=" * 60)
        
        resultados = {}
        
        self.logger.info("\n1. Transformando SIH...")
        df_sih = self.transformar_sih(df_sih_raw)
        resultados['sih'] = df_sih
        
        self.logger.info("\n2. Transformando CNES...")
        df_cnes = self.transformar_cnes(df_cnes_raw)
        resultados['cnes'] = df_cnes
        
        self.logger.info("\n3. Transformando IBGE...")
        df_ibge = self.transformar_ibge(df_ibge_raw)
        resultados['ibge'] = df_ibge
        
        self.logger.info("\n4. Integrando dados...")
        df_integrado, df_ocupacao = self.integrar_dados(df_sih, df_cnes, df_ibge)
        resultados['integrado'] = df_integrado
        resultados['ocupacao'] = df_ocupacao
        
        if salvar:
            self.logger.info("\n5. Salvando resultados...")
            self._salvar_resultados(resultados, upload)
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info("PIPELINE CONCLUIDO COM SUCESSO!")
        self.logger.info("=" * 60)
        return resultados
    
    def _salvar_resultados(self, resultados: Dict[str, pd.DataFrame], upload: bool = True):
        """
        Salva os DataFrames transformados em arquivos e envia para Object Storage.
        """
        for nome, df in resultados.items():
            if df is None or len(df) == 0:
                continue
            
            # Definir caminho local
            if nome == 'sih':
                caminho = self.config.PROCESSED_DIR / f"sih_transformado_{self.uf}_{self.ano}_{self.mes:02d}.parquet"
                objeto = f"sih_transformado/{self.uf}/{self.ano}/{self.mes:02d}/sih_transformado_{self.uf}_{self.ano}_{self.mes:02d}.parquet"
            elif nome == 'cnes':
                caminho = self.config.PROCESSED_DIR / f"cnes_transformado_{self.uf}_{self.ano}_{self.mes:02d}.parquet"
                objeto = f"cnes_transformado/{self.uf}/{self.ano}/{self.mes:02d}/cnes_transformado_{self.uf}_{self.ano}_{self.mes:02d}.parquet"
            elif nome == 'ibge':
                caminho = self.config.PROCESSED_DIR / f"ibge_transformado_{self.uf}.parquet"
                objeto = f"ibge_transformado/{self.uf}/ibge_transformado_{self.uf}.parquet"
            elif nome == 'integrado':
                caminho = self.config.PROCESSED_DIR / f"meddata_integrado_{self.uf}_{self.ano}_{self.mes:02d}.parquet"
                objeto = f"meddata_integrado/{self.uf}/{self.ano}/{self.mes:02d}/meddata_integrado_{self.uf}_{self.ano}_{self.mes:02d}.parquet"
            elif nome == 'ocupacao':
                caminho = self.config.PROCESSED_DIR / f"ocupacao_hospitalar_{self.uf}_{self.ano}_{self.mes:02d}.parquet"
                objeto = f"ocupacao_hospitalar/{self.uf}/{self.ano}/{self.mes:02d}/ocupacao_hospitalar_{self.uf}_{self.ano}_{self.mes:02d}.parquet"
            else:
                caminho = self.config.PROCESSED_DIR / f"{nome}_{self.uf}_{self.ano}_{self.mes:02d}.parquet"
                objeto = f"{nome}/{self.uf}/{self.ano}/{self.mes:02d}/{nome}_{self.uf}_{self.ano}_{self.mes:02d}.parquet"
            
            # Salvar localmente
            df.to_parquet(caminho, index=False)
            self.logger.info(f"   {nome}: {caminho} ({len(df):,} registros)")
            
            # Upload para Object Storage
            if upload:
                upload_para_object_storage(caminho, objeto, "meddata-gold")


# ================================================================
# 6. FUNCOES AUXILIARES
# ================================================================

def transformar_sih_simples(df: pd.DataFrame, uf: str = 'PR', ano: int = 2024, mes: int = 1) -> pd.DataFrame:
    from config import Config
    config = Config()
    config.UF = uf
    config.ANO = ano
    config.MES = mes
    return TransformadorDados(config).transformar_sih(df)


def transformar_cnes_simples(df: pd.DataFrame, uf: str = 'PR', ano: int = 2024, mes: int = 1) -> pd.DataFrame:
    from config import Config
    config = Config()
    config.UF = uf
    config.ANO = ano
    config.MES = mes
    return TransformadorDados(config).transformar_cnes(df)


def transformar_ibge_simples(df: pd.DataFrame, uf: str = 'PR') -> pd.DataFrame:
    from config import Config
    config = Config()
    config.UF = uf
    return TransformadorDados(config).transformar_ibge(df)


# ================================================================
# 7. EXECUCAO DIRETA COM ARGPARSE
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
    
    # Criar transformador e executar
    transformador = TransformadorDados(config)
    resultados = transformador.executar_pipeline(
        df_sih_raw=df_sih_raw,
        df_cnes_raw=df_cnes_raw,
        df_ibge_raw=df_ibge_raw,
        salvar=True,
        upload=args.upload
    )
    
    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO DOS RESULTADOS")
    print("=" * 60)
    for nome, df in resultados.items():
        if df is not None:
            print(f"{nome.upper():12} | {len(df):>8,} registros | {len(df.columns):>3} colunas")
    
    print("\n✅ Transformação concluída com sucesso!")
    sys.exit(0)