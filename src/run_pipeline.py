"""
Script principal para execução do pipeline de dados MedData.

Orquestra ingestão, transformação e exportação dos dados.

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

from config import config
from ingestao import baixar_sih, baixar_cnes_leitos, baixar_ibge
from transformacao import TransformadorDados


class PipelineMedData:
    """
    Classe principal do pipeline de dados do MedData.
    
    Orquestra todas as etapas do pipeline:
    1. Ingestão dos dados brutos
    2. Transformação e limpeza
    3. Exportação dos resultados
    """
    
    def __init__(self, uf=None, ano=None, mes=None):
        """
        Inicializa o pipeline com as configurações.
        """
        self.uf = uf or config.UF
        self.ano = ano or config.ANO
        self.mes = mes or config.MES
        
        # Atualiza config com valores atuais
        config.UF = self.uf
        config.ANO = self.ano
        config.MES = self.mes
        
        self.logger = self._setup_logging()
        self.transformador = TransformadorDados(config)
        self.dados = {}
    
    def _setup_logging(self) -> logging.Logger:
        """Configura o sistema de logging."""
        logger = logging.getLogger('pipeline')
        logger.setLevel(logging.INFO)
        
        fh = logging.FileHandler('pipeline.log')
        fh.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
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
        """
        if steps is None:
            steps = ['ingest', 'transform', 'export']
        
        self.logger.info("=" * 70)
        self.logger.info("INICIANDO PIPELINE MEDDATA")
        self.logger.info(f"UF: {self.uf} | Ano: {self.ano} | Mês: {self.mes:02d}")
        self.logger.info("=" * 70)
        
        try:
            if 'ingest' in steps:
                self.logger.info("\n[STEP 1] INGESTÃO DE DADOS")
                self._executar_ingestao()
            
            if 'transform' in steps:
                self.logger.info("\n[STEP 2] TRANSFORMAÇÃO DE DADOS")
                self._executar_transformacao()
            
            if 'export' in steps:
                self.logger.info("\n[STEP 3] EXPORTAÇÃO DOS DADOS")
                self._executar_exportacao()
            
            self.logger.info("\n" + "=" * 70)
            self.logger.info("PIPELINE CONCLUÍDO COM SUCESSO!")
            self.logger.info("=" * 70)
            
            return self.dados
            
        except Exception as e:
            self.logger.error(f"Erro na execução do pipeline: {str(e)}")
            raise
    
    def _executar_ingestao(self):
        """Executa a etapa de ingestão."""
        self.logger.info("Baixando dados...")
        
        self.dados['sih_raw'] = baixar_sih(uf=self.uf, ano=self.ano, mes=self.mes)
        self.dados['cnes_raw'] = baixar_cnes_leitos(uf=self.uf, ano=self.ano, mes=self.mes)
        self.dados['ibge_raw'] = baixar_ibge(uf=self.uf)
        
        self.logger.info("Ingestão concluída")
        self._resumo_dados('raw')
    
    def _executar_transformacao(self):
        """Executa a etapa de transformação."""
        self.logger.info("Transformando dados...")
        
        self.dados['sih'] = self.transformador.transformar_sih(self.dados['sih_raw'])
        self.dados['cnes'] = self.transformador.transformar_cnes(self.dados['cnes_raw'])
        self.dados['ibge'] = self.transformador.transformar_ibge(self.dados['ibge_raw'])
        
        self.dados['integrado'], self.dados['ocupacao'] = self.transformador.integrar_dados(
            self.dados['sih'],
            self.dados['cnes'],
            self.dados['ibge']
        )
        
        self.logger.info("Transformação concluída")
        self._resumo_dados('transformado')
    
def _executar_exportacao(self):
    """Executa a etapa de exportação."""
    self.logger.info("Exportando dados...")
    
    # Usa o mesmo padrão do transformacao.py
    datasets_para_salvar = {
        'sih': f"sih_transformado_{self.uf}_{self.ano}_{self.mes:02d}.parquet",
        'cnes': f"cnes_transformado_{self.uf}_{self.ano}_{self.mes:02d}.parquet",
        'ibge': f"ibge_transformado_{self.uf}.parquet",
        'integrado': f"meddata_integrado_{self.uf}_{self.ano}_{self.mes:02d}.parquet",
        'ocupacao': f"ocupacao_hospitalar_{self.uf}_{self.ano}_{self.mes:02d}.parquet",
    }
    
    for nome, nome_arquivo in datasets_para_salvar.items():
        df = self.dados.get(nome)
        if df is not None and isinstance(df, pd.DataFrame) and len(df) > 0:
            caminho = self.config.PROCESSED_DIR / nome_arquivo
            df.to_parquet(caminho, index=False)
            self.logger.info(f"   {nome}: {caminho} ({len(df):,} registros)")
    
    self.logger.info(" Exportação concluída")

def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description='Pipeline MedData')
    parser.add_argument('--step', choices=['ingest', 'transform', 'export', 'all'],
                       default='all', help='Etapa a executar')
    parser.add_argument('--uf', default=None, help='UF para processar')
    parser.add_argument('--ano', type=int, default=None, help='Ano para processar')
    parser.add_argument('--mes', type=int, default=None, help='Mês para processar')
    
    args = parser.parse_args()
    
    uf = args.uf or config.UF
    ano = args.ano or config.ANO
    mes = args.mes or config.MES
    
    steps = None if args.step == 'all' else [args.step]
    
    pipeline = PipelineMedData(uf=uf, ano=ano, mes=mes)
    pipeline.executar(steps=steps)


if __name__ == "__main__":
    main()