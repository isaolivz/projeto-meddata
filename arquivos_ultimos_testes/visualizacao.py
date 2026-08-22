"""
Módulo de visualização para o projeto MedData.

Este módulo contém funções para gerar gráficos padrão
para relatórios e dashboards.

Uso:
    from visualizacao import GeradorVisualizacoes
    
    visualizador = GeradorVisualizacoes()
    visualizador.gerar_todas(df_integrado, df_ocupacao)
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from pathlib import Path


class GeradorVisualizacoes:
    """
    Classe para geração de visualizações do MedData.
    """
    
    def __init__(self, output_dir: str = '../reports/figures/'):
        """
        Inicializa o gerador de visualizações.
        
        Args:
            output_dir: Diretório para salvar as imagens
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurar estilo
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (12, 6)
        plt.rcParams['font.size'] = 11
        plt.rcParams['axes.titlesize'] = 14
    
    def gerar_todas(self, df_integrado: pd.DataFrame, df_ocupacao: pd.DataFrame):
        """
        Gera todas as visualizações padrão.
        
        Args:
            df_integrado: DataFrame integrado
            df_ocupacao: DataFrame com dados de ocupação
        """
        self.gerar_distribuicao_permanencia(df_integrado)
        self.gerar_top_diagnosticos(df_integrado)
        self.gerar_distribuicao_custos(df_integrado)
        self.gerar_deslocamento(df_integrado)
        self.gerar_internacoes_por_dia(df_integrado)
        self.gerar_taxa_ocupacao(df_ocupacao)
        self.gerar_top_hospitais(df_integrado)
    
    def gerar_distribuicao_permanencia(self, df: pd.DataFrame):
        """Gera gráfico de distribuição de permanência."""
        plt.figure(figsize=(12, 5))
        
        dados = df[df['dias_internacao'] <= 30]['dias_internacao']
        plt.hist(dados, bins=30, color='skyblue', edgecolor='black')
        plt.axvline(dados.mean(), color='red', linestyle='--', 
                   label=f'Média: {dados.mean():.1f} dias')
        plt.axvline(dados.median(), color='green', linestyle='--', 
                   label=f'Mediana: {dados.median():.0f} dias')
        plt.xlabel('Dias de Internação')
        plt.ylabel('Frequência')
        plt.title('Distribuição de Permanência Hospitalar')
        plt.legend()
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'distribuicao_permanencia.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def gerar_top_diagnosticos(self, df: pd.DataFrame):
        """Gera gráfico de top diagnósticos."""
        if 'codigo_diagnostico' not in df.columns:
            return
        
        top = df['codigo_diagnostico'].value_counts().head(10)
        
        plt.figure(figsize=(12, 6))
        bars = plt.barh(top.index, top.values, color='skyblue')
        plt.bar_label(bars, padding=3)
        plt.xlabel('Número de Internações')
        plt.title('Top 10 Diagnósticos')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        plt.savefig(self.output_dir / 'top_diagnosticos.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def gerar_distribuicao_custos(self, df: pd.DataFrame):
        """Gera gráfico de distribuição de custos."""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Histograma
        ax1 = axes[0]
        dados = df[df['valor_procedimento'] <= 500]['valor_procedimento']
        ax1.hist(dados, bins=50, color='skyblue', edgecolor='black')
        ax1.axvline(dados.mean(), color='red', linestyle='--', 
                   label=f'Média: R$ {dados.mean():.2f}')
        ax1.axvline(dados.median(), color='green', linestyle='--', 
                   label=f'Mediana: R$ {dados.median():.2f}')
        ax1.set_xlabel('Valor do Procedimento (R$)')
        ax1.set_ylabel('Frequência')
        ax1.set_title('Distribuição de Custos')
        ax1.legend()
        
        # Boxplot
        ax2 = axes[1]
        sns.boxplot(y=df['valor_procedimento'], ax=ax2, color='lightcoral')
        ax2.set_ylabel('Valor do Procedimento (R$)')
        ax2.set_title('Boxplot dos Custos')
        ax2.set_ylim(0, 500)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'distribuicao_custos.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def gerar_deslocamento(self, df: pd.DataFrame):
        """Gera gráfico de deslocamento de pacientes."""
        if 'paciente_viajou' not in df.columns:
            return
        
        viajaram = df['paciente_viajou'].sum()
        total = len(df)
        
        plt.figure(figsize=(8, 8))
        labels = ['Viajaram', 'Não Viajaram']
        sizes = [viajaram, total - viajaram]
        colors = ['#ff6b6b', '#4ecdc4']
        explode = (0.05, 0)
        
        plt.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, 
                explode=explode, startangle=90, shadow=True)
        plt.title('Taxa de Deslocamento de Pacientes')
        plt.axis('equal')
        plt.tight_layout()
        plt.savefig(self.output_dir / 'deslocamento_pacientes.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def gerar_internacoes_por_dia(self, df: pd.DataFrame):
        """Gera gráfico de internações por dia da semana."""
        if 'dia_semana' not in df.columns:
            return
        
        ordem = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        dias = df['dia_semana'].value_counts().reindex(ordem)
        
        plt.figure(figsize=(12, 5))
        dias.plot(kind='bar', color='skyblue', edgecolor='black')
        plt.xlabel('Dia da Semana')
        plt.ylabel('Número de Internações')
        plt.title('Internações por Dia da Semana')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'internacoes_por_dia.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def gerar_taxa_ocupacao(self, df: pd.DataFrame):
        """Gera gráfico de taxa de ocupação."""
        if len(df) == 0:
            return
        
        plt.figure(figsize=(12, 5))
        plt.hist(df['taxa_ocupacao'], bins=20, color='skyblue', edgecolor='black')
        plt.axvline(df['taxa_ocupacao'].mean(), color='red', linestyle='--',
                   label=f'Média: {df["taxa_ocupacao"].mean():.1f}%')
        plt.xlabel('Taxa de Ocupação (%)')
        plt.ylabel('Número de Hospitais')
        plt.title('Distribuição da Taxa de Ocupação Hospitalar')
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.output_dir / 'taxa_ocupacao.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def gerar_top_hospitais(self, df: pd.DataFrame):
        """Gera gráfico de top hospitais por internações."""
        if 'id_hospital' not in df.columns:
            return
        
        top = df['id_hospital'].value_counts().head(10)
        
        plt.figure(figsize=(12, 6))
        bars = plt.barh(top.index, top.values, color='skyblue')
        plt.bar_label(bars, padding=3)
        plt.xlabel('Número de Internações')
        plt.title('Top 10 Hospitais por Internações')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        plt.savefig(self.output_dir / 'top_hospitais.png', dpi=150, bbox_inches='tight')
        plt.close()