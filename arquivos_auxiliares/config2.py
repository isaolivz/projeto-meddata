"""
Configurações centrais do projeto MedData.

Este arquivo contém todas as configurações do sistema:
- Diretórios do projeto
- Parâmetros dos dados (UF, ano, mês)
- Colunas do SIH e mapeamento
- Códigos auxiliares (IBGE)

Uso:
    from config import UF, ANO, RAW_DIR, CODIGOS_UF
"""

# 1. DIRETÓRIOS DO PROJETO
# ------------------------------------
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCE_DIR = DATA_DIR / "reference"
REPORTS_DIR = BASE_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# Criar diretórios se não existirem
for pasta in [RAW_DIR, PROCESSED_DIR, REFERENCE_DIR, FIGURES_DIR]:
    pasta.mkdir(parents=True, exist_ok=True)

# 2. CONFIGURAÇÕES DOS DADOS
# ------------------------------------
UF = "SP"           # Estado: PR (testes)
ANO = 2024          # Ano dos dados
MES = 1             # Mês (1-12)

# 3. COLUNAS DO SIH
# -------------------------------------
COLUNAS_SIH = [
    'SP_GESTOR',    # Código do município gestor
    'SP_CNES',      # ID do hospital
    'SP_CIDPRI',    # CID-10 principal
    'SP_DTINTER',   # Data de internação
    'SP_DTSAIDA',   # Data de saída
    'SP_VALATO',    # Valor do procedimento
    'SP_M_PAC',     # Município do paciente
    'SP_AA',       # Ano
    'SP_MM'        # Mês
]

COLUNAS_SIH_MAP = {
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

# 4. CÓDIGOS IBGE POR UF
# -----------------------------------------
CODIGOS_UF = {
    'PR': 41, 'SP': 35, 'RJ': 33, 'MG': 31,
    'BA': 29, 'RS': 43, 'SC': 42, 'GO': 52,
    'PE': 26, 'CE': 23, 'PA': 15, 'AM': 13,
    'MT': 51, 'MS': 50, 'DF': 53, 'ES': 32,
    'MA': 21, 'RN': 24, 'PB': 25, 'PI': 22,
    'AL': 27, 'SE': 28, 'TO': 17, 'RO': 11,
    'AC': 12, 'AP': 16, 'RR': 14
}

# 5. FUNÇÕES AUXILIARES
# -----------------------------------------
def get_codigo_uf(uf=None):
    """
    Retorna o código IBGE de uma UF.
    
    Args:
        uf: Sigla do estado (ex: 'SP'). Se None, usa UF padrão.
    
    Returns:
        Código IBGE do estado (ex: 35 para SP)
    
    Exemplos:
        >>> get_codigo_uf('SP')
        35
        >>> get_codigo_uf()  # Se UF = 'PR'
        41
    """
    if uf is None:
        uf = UF
    return CODIGOS_UF.get(uf)

def get_nome_arquivo(prefixo, extensao='parquet'):
    """
    Gera nome de arquivo padronizado.
    
    Args:
        prefixo: Prefixo do arquivo (ex: 'sih', 'cnes')
        extensao: Extensão do arquivo (ex: 'parquet', 'csv')
    
    Returns:
        Nome formatado: prefixo_UF_ANO_MES.extensao
    
    Exemplos:
        >>> get_nome_arquivo('sih')
        'sih_PR_2024_01.parquet'
        >>> get_nome_arquivo('cnes', 'csv')
        'cnes_PR_2024_01.csv'
    """
    return f"{prefixo}_{UF}_{ANO}_{MES:02d}.{extensao}"