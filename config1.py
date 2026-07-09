# Configurações centrais do projeto

from pathlib import Path

# Diretórios
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCE_DIR = DATA_DIR / "reference"
REPORTS_DIR = BASE_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# Criar diretórios se não existirem
for dir_path in [RAW_DIR, PROCESSED_DIR, REFERENCE_DIR, FIGURES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Configurações de dados
UF = "PR"
ANO = 2023
MES = 1

# Colunas essenciais do SIH
COLUNAS_SIH = [
    'SP_GESTOR',   # Código do município gestor
    'SP_CNES',     # ID do hospital
    'SP_CIDPRI',   # CID-10 principal
    'SP_DTINTER',  # Data de internação
    'SP_DTSAIDA',  # Data de saída
    'SP_VALATO',   # Valor do procedimento
    'SP_M_PAC',    # Município do paciente
]

# Mapeamento de colunas (para o Select AI)
COLUNAS_SIH_MAP = {
    'SP_GESTOR': 'codigo_municipio',
    'SP_CNES': 'id_hospital',
    'SP_CIDPRI': 'codigo_diagnostico',
    'SP_DTINTER': 'data_internacao',
    'SP_DTSAIDA': 'data_saida',
    'SP_VALATO': 'valor_procedimento',
    'SP_M_PAC': 'codigo_municipio_paciente',
}