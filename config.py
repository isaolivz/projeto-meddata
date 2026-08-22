"""
config.py - Configuracoes centrais do projeto MedData.
"""

from pathlib import Path


class Config:
    """Configuracao central do projeto MedData."""
    
    def __init__(self):
        # Parametros principais
        self.UF = "SP"
        self.ANO = 2024
        self.MES = 1
        
        # Diretorios
        self.BASE_DIR = Path(__file__).parent
        self.DATA_DIR = self.BASE_DIR / "data"
        self.RAW_DIR = self.DATA_DIR / "raw"
        self.PROCESSED_DIR = self.DATA_DIR / "processed"
        self.REFERENCE_DIR = self.DATA_DIR / "reference"
        
        # Criar diretorios
        for pasta in [self.RAW_DIR, self.PROCESSED_DIR, self.REFERENCE_DIR]:
            pasta.mkdir(parents=True, exist_ok=True)
        
        # Codigos IBGE para UF
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
        """Retorna o codigo IBGE de uma UF."""
        if uf is None:
            uf = self.UF
        return self.CODIGOS_UF.get(uf)
    
    def get_nome_arquivo(self, prefixo, uf=None, ano=None, mes=None, extensao='parquet'):
        """Retorna o nome padronizado de um arquivo."""
        if uf is None:
            uf = self.UF
        if ano is None:
            ano = self.ANO
        if mes is None:
            mes = self.MES
        return f"{prefixo}_{uf}_{ano}_{mes:02d}.{extensao}"


# Instancia unica para uso em todo o projeto
config = Config()