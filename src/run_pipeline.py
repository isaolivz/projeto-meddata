"""
Script principal para execução do pipeline de dados MedData.

Orquestra ingestão, transformação, validação e exportação dos dados.

Uso:
    python run_pipeline.py                    # Executa pipeline completo
    python run_pipeline.py --step ingest     # Apenas ingestão
    python run_pipeline.py --step transform  # Apenas transformação
    python run_pipeline.py --uf SP --ano 2024  # Com parâmetros customizados
"""
import pandas as pd
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# Adiciona src ao path
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent))

from config import Config
from ingestao import baixar_sih, baixar_cnes_leitos, baixar_ibge
from transformacao import TransformadorDados
from validacao import ValidadorDados
from indicadores import CalculadorIndicadores
from visualizacao import GeradorVisualizacoes


class PipelineMedData:
    """
    Classe principal do pipeline de dados do MedData.
    
    Orquestra todas as etapas do pipeline:
    1. Ingestão dos dados brutos
    2. Transformação e limpeza
    3. Validação da qualidade
    4. Cálculo de indicadores
    5. Geração de visualizações
    6. Exportação dos resultados
    """
    
    def __init__(self, config: Config):
        """
        Inicializa o pipeline com as configurações.
        
        Args:
            config: Objeto de configuração do projeto
        """
        self.config = config
        self.logger = self._setup_logging()
        self.transformador = TransformadorDados(config)
        self.validador = ValidadorDados()
        self.indicadores = CalculadorIndicadores()
        self.visualizador = GeradorVisualizacoes()
        
        self.dados = {}
        
    def _setup_logging(self) -> logging.Logger:
        """Configura o sistema de logging."""
        logger = logging.getLogger('pipeline')
        logger.setLevel(logging.INFO)
        
        # Handler para arquivo
        fh = logging.FileHandler('pipeline.log')
        fh.setLevel(logging.INFO)
        
        # Handler para console
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    def executar(self, steps: list = None) -> dict:
        """
        Executa o pipeline completo ou steps específicos.
        
        Args:
            steps: Lista de steps a executar. Se None, executa todos.
            
        Returns:
            Dicionário com os dados processados
        """
        if steps is None:
            steps = ['ingest', 'transform', 'validate', 'indicators', 'visualize', 'export']
        
        self.logger.info("=" * 70)
        self.logger.info("INICIANDO PIPELINE MEDDATA")
        self.logger.info(f"UF: {self.config.UF} | Ano: {self.config.ANO} | Mês: {self.config.MES:02d}")
        self.logger.info("=" * 70)
        
        try:
            # Step 1: Ingestão
            if 'ingest' in steps:
                self.logger.info("\n[STEP 1] INGESTÃO DE DADOS")
                self._executar_ingestao()
            
            # Step 2: Transformação
            if 'transform' in steps:
                self.logger.info("\n[STEP 2] TRANSFORMAÇÃO DE DADOS")
                self._executar_transformacao()
            
            # Step 3: Validação
            if 'validate' in steps:
                self.logger.info("\n[STEP 3] VALIDAÇÃO DOS DADOS")
                self._executar_validacao()
            
            # Step 4: Indicadores
            if 'indicators' in steps:
                self.logger.info("\n[STEP 4] CÁLCULO DE INDICADORES")
                self._executar_indicadores()
            
            # Step 5: Visualizações
            if 'visualize' in steps:
                self.logger.info("\n[STEP 5] GERAÇÃO DE VISUALIZAÇÕES")
                self._executar_visualizacoes()
            
            # Step 6: Exportação
            if 'export' in steps:
                self.logger.info("\n[STEP 6] EXPORTAÇÃO DOS DADOS")
                self._executar_exportacao()
            
            self.logger.info("\n" + "=" * 70)
            self.logger.info("✅ PIPELINE CONCLUÍDO COM SUCESSO!")
            self.logger.info("=" * 70)
            
            return self.dados
            
        except Exception as e:
            self.logger.error(f"❌ Erro na execução do pipeline: {str(e)}")
            raise
    
    def _executar_ingestao(self):
        """Executa a etapa de ingestão."""
        self.logger.info("Baixando dados...")
        
        self.dados['sih_raw'] = baixar_sih(
            uf=self.config.UF,
            ano=self.config.ANO,
            mes=self.config.MES
        )
        
        self.dados['cnes_raw'] = baixar_cnes_leitos(
            uf=self.config.UF,
            ano=self.config.ANO,
            mes=self.config.MES
        )
        
        self.dados['ibge_raw'] = baixar_ibge(
            uf=self.config.UF
        )
        
        self.logger.info("✅ Ingestão concluída")
        self._resumo_dados('raw')
    
    def _executar_transformacao(self):
        """Executa a etapa de transformação."""
        self.logger.info("Transformando dados...")
        
        # Usar dados já baixados ou carregar do arquivo
        if 'sih_raw' not in self.dados:
            self.dados['sih_raw'] = self._carregar_raw('sih')
        
        if 'cnes_raw' not in self.dados:
            self.dados['cnes_raw'] = self._carregar_raw('cnes')
        
        if 'ibge_raw' not in self.dados:
            self.dados['ibge_raw'] = self._carregar_raw('ibge')
        
        # Transformar
        self.dados['sih'] = self.transformador.transformar_sih(self.dados['sih_raw'])
        self.dados['cnes'] = self.transformador.transformar_cnes(self.dados['cnes_raw'])
        self.dados['ibge'] = self.transformador.transformar_ibge(self.dados['ibge_raw'])
        
        # Integrar
        self.dados['integrado'], self.dados['ocupacao'] = self.transformador.integrar_dados(
            self.dados['sih'],
            self.dados['cnes'],
            self.dados['ibge']
        )
        
        self.logger.info("✅ Transformação concluída")
        self._resumo_dados('transformado')
    
    def _executar_validacao(self):
        """Executa a etapa de validação."""
        self.logger.info("Validando dados...")
        
        # Validar cada dataset
        for nome in ['sih', 'cnes', 'ibge', 'integrado']:
            if nome in self.dados:
                relatorio = self.validador.validar_dataset(
                    self.dados[nome],
                    nome
                )
                self.dados[f'{nome}_validacao'] = relatorio
                self.logger.info(f"   {nome}: {relatorio['status']}")
        
        self.logger.info("✅ Validação concluída")
    
    def _executar_indicadores(self):
        """Executa a etapa de cálculo de indicadores."""
        self.logger.info("Calculando indicadores...")
        
        if 'integrado' in self.dados:
            self.dados['indicadores'] = self.indicadores.calcular_todos(
                self.dados['integrado'],
                self.dados['ocupacao']
            )
            
            self.logger.info("   Indicadores calculados:")
            for nome, valor in self.dados['indicadores'].items():
                if isinstance(valor, (int, float)):
                    self.logger.info(f"      {nome}: {valor:.2f}")
                else:
                    self.logger.info(f"      {nome}: {valor}")
        
        self.logger.info("✅ Indicadores calculados")
    
    def _executar_visualizacoes(self):
        """Executa a etapa de geração de visualizações."""
        self.logger.info("Gerando visualizações...")
        
        if 'integrado' in self.dados:
            self.visualizador.gerar_todas(
                self.dados['integrado'],
                self.dados['ocupacao']
            )
        
        self.logger.info("✅ Visualizações geradas")
    
    def _executar_exportacao(self):
        """Executa a etapa de exportação."""
        self.logger.info("Exportando dados...")
    
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        datasets_para_salvar = ['sih', 'cnes', 'ibge', 'integrado', 'ocupacao']
    
        for nome in datasets_para_salvar:
            df = self.dados.get(nome)
            if df is not None and isinstance(df, pd.DataFrame) and len(df) > 0:
                caminho = self.config.PROCESSED_DIR / f"{nome}_{timestamp}.parquet"
                df.to_parquet(caminho, index=False)
                self.logger.info(f"   {nome}: {caminho} ({len(df):,} registros)")
    
        self.logger.info("✅ Exportação concluída")
    
    def _carregar_raw(self, nome: str) -> pd.DataFrame:
        """Carrega dados brutos do arquivo."""
        import pandas as pd
        
        caminho = self.config.RAW_DIR / f"{nome}_{self.config.UF}_{self.config.ANO}_{self.config.MES:02d}.parquet"
        if caminho.exists():
            return pd.read_parquet(caminho)
        else:
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    
    def _resumo_dados(self, etapa: str):
        """Mostra resumo dos dados."""
        self.logger.info(f"\nResumo da {etapa}:")
        for nome, df in self.dados.items():
            if isinstance(df, pd.DataFrame):
                self.logger.info(f"   {nome}: {len(df):,} registros, {len(df.columns)} colunas")


def main():
    """Função principal."""
    # Parse argumentos
    parser = argparse.ArgumentParser(description='Pipeline MedData')
    parser.add_argument('--step', choices=['ingest', 'transform', 'validate', 
                                           'indicators', 'visualize', 'export', 'all'],
                       default='all', help='Etapa a executar')
    parser.add_argument('--uf', default=None, help='UF para processar')
    parser.add_argument('--ano', type=int, default=None, help='Ano para processar')
    parser.add_argument('--mes', type=int, default=None, help='Mês para processar')
    
    args = parser.parse_args()
    
    # Carregar configuração
    config = Config()
    
    # Sobrescrever parâmetros se fornecidos
    if args.uf:
        config.UF = args.uf
    if args.ano:
        config.ANO = args.ano
    if args.mes:
        config.MES = args.mes
    
    # Definir steps
    if args.step == 'all':
        steps = None
    else:
        steps = [args.step]
    
    # Executar pipeline
    pipeline = PipelineMedData(config)
    pipeline.executar(steps=steps)


if __name__ == "__main__":
    main()