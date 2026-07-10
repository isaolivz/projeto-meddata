"""
Configurações centrais do projeto MedData.

Este arquivo contém todas as configurações do sistema:
- Diretórios do projeto
- Parâmetros dos dados (UF, ano, mês)
- Colunas do SIH e mapeamento
- Códigos auxiliares (IBGE)

Uso:
    from config import config
    print(config.UF)
"""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class Config:
    """
    Configuração central do projeto MedData.
    """
    
    # Parâmetros principais
    UF: str = "SC"
    ANO: int = 2024
    MES: int = 1
    
    # Diretórios (inicializados no __post_init__)
    BASE_DIR: Path = None
    DATA_DIR: Path = None
    RAW_DIR: Path = None
    PROCESSED_DIR: Path = None
    REFERENCE_DIR: Path = None
    REPORTS_DIR: Path = None
    FIGURES_DIR: Path = None
    
    # Colunas do SIH
    COLUNAS_SIH: list = None
    COLUNAS_SIH_MAP: dict = None
    
    # Códigos IBGE
    CODIGOS_UF: dict = None
    
    def __post_init__(self):
        """Inicializa diretórios e valores padrão."""
        # Diretórios
        if self.BASE_DIR is None:
            self.BASE_DIR = Path(__file__).parent
        
        if self.DATA_DIR is None:
            self.DATA_DIR = self.BASE_DIR / "data"
        if self.RAW_DIR is None:
            self.RAW_DIR = self.DATA_DIR / "raw"
        if self.PROCESSED_DIR is None:
            self.PROCESSED_DIR = self.DATA_DIR / "processed"
        if self.REFERENCE_DIR is None:
            self.REFERENCE_DIR = self.DATA_DIR / "reference"
        if self.REPORTS_DIR is None:
            self.REPORTS_DIR = self.BASE_DIR / "reports"
        if self.FIGURES_DIR is None:
            self.FIGURES_DIR = self.REPORTS_DIR / "figures"
        
        # Criar diretórios
        for pasta in [self.RAW_DIR, self.PROCESSED_DIR, self.REFERENCE_DIR, self.FIGURES_DIR]:
            pasta.mkdir(parents=True, exist_ok=True)
        
        # Colunas do SIH
        if self.COLUNAS_SIH is None:
            self.COLUNAS_SIH = [
                'SP_GESTOR',    # Código do município gestor
                'SP_CNES',      # ID do hospital
                'SP_CIDPRI',    # CID-10 principal
                'SP_DTINTER',   # Data de internação
                'SP_DTSAIDA',   # Data de saída
                'SP_VALATO',    # Valor do procedimento
                'SP_M_PAC',     # Município do paciente
                'SP_AA',        # Ano
                'SP_MM'         # Mês
            ]
        
        # Mapeamento de colunas
        if self.COLUNAS_SIH_MAP is None:
            self.COLUNAS_SIH_MAP = {
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
        
        # Códigos IBGE
        if self.CODIGOS_UF is None:
            self.CODIGOS_UF = {
                'PR': 41, 'SP': 35, 'RJ': 33, 'MG': 31,
                'BA': 29, 'RS': 43, 'SC': 42, 'GO': 52,
                'PE': 26, 'CE': 23, 'PA': 15, 'AM': 13,
                'MT': 51, 'MS': 50, 'DF': 53, 'ES': 32,
                'MA': 21, 'RN': 24, 'PB': 25, 'PI': 22,
                'AL': 27, 'SE': 28, 'TO': 17, 'RO': 11,
                'AC': 12, 'AP': 16, 'RR': 14
            }
    
    def get_codigo_uf(self, uf=None):
        """Retorna o código IBGE de uma UF."""
        if uf is None:
            uf = self.UF
        return self.CODIGOS_UF.get(uf)
    
    def get_nome_arquivo(self, prefixo, extensao='parquet'):
        """Gera nome de arquivo padronizado."""
        return f"{prefixo}_{self.UF}_{self.ANO}_{self.MES:02d}.{extensao}"
    
    def to_dict(self):
        """Converte configuração para dicionário."""
        return {
            'UF': self.UF,
            'ANO': self.ANO,
            'MES': self.MES,
            'RAW_DIR': str(self.RAW_DIR),
            'PROCESSED_DIR': str(self.PROCESSED_DIR),
            'REFERENCE_DIR': str(self.REFERENCE_DIR),
            'COLUNAS_SIH': self.COLUNAS_SIH,
            'COLUNAS_SIH_MAP': self.COLUNAS_SIH_MAP,
            'CODIGOS_UF': self.CODIGOS_UF,
        }


# Instância única para uso em todo o projeto
config = Config()