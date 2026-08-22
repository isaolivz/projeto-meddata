"""
Módulo de cálculo de indicadores para o projeto MedData.

Este módulo contém funções para calcular os KPIs e métricas
utilizadas no dashboard.

Uso:
    from indicadores import CalculadorIndicadores
    
    calculador = CalculadorIndicadores()
    indicadores = calculador.calcular_todos(df_integrado, df_ocupacao)
"""

import pandas as pd
import numpy as np
from typing import Dict, Any


class CalculadorIndicadores:
    """
    Classe para cálculo de indicadores do MedData.
    """
    
    def calcular_todos(self, df_integrado: pd.DataFrame, df_ocupacao: pd.DataFrame) -> Dict[str, Any]:
        """
        Calcula todos os indicadores.
        
        Args:
            df_integrado: DataFrame integrado
            df_ocupacao: DataFrame com dados de ocupação
            
        Returns:
            Dicionário com todos os indicadores
        """
        indicadores = {}
        
        # 1. Indicadores gerais
        indicadores.update(self._indicadores_gerais(df_integrado))
        
        # 2. Indicadores de internação
        indicadores.update(self._indicadores_internacao(df_integrado))
        
        # 3. Indicadores de custo
        indicadores.update(self._indicadores_custo(df_integrado))
        
        # 4. Indicadores de ocupação
        indicadores.update(self._indicadores_ocupacao(df_ocupacao))
        
        # 5. Indicadores de deslocamento
        indicadores.update(self._indicadores_deslocamento(df_integrado))
        
        # 6. Indicadores de diagnóstico
        indicadores.update(self._indicadores_diagnostico(df_integrado))
        
        return indicadores
    
    def _indicadores_gerais(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calcula indicadores gerais."""
        return {
            'total_internacoes': len(df),
            'total_hospitais': df['id_hospital'].nunique(),
            'total_municipios': df['codigo_municipio'].nunique(),
            'periodo_inicio': df['data_internacao'].min(),
            'periodo_fim': df['data_internacao'].max(),
        }
    
    def _indicadores_internacao(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calcula indicadores de internação."""
        return {
            'media_permanencia': df['dias_internacao'].mean(),
            'mediana_permanencia': df['dias_internacao'].median(),
            'max_permanencia': df['dias_internacao'].max(),
            'total_dias_internacao': df['dias_internacao'].sum(),
        }
    
    def _indicadores_custo(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calcula indicadores de custo."""
        return {
            'custo_total': df['valor_procedimento'].sum(),
            'custo_medio': df['valor_procedimento'].mean(),
            'custo_mediana': df['valor_procedimento'].median(),
            'custo_maximo': df['valor_procedimento'].max(),
        }
    
    def _indicadores_ocupacao(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calcula indicadores de ocupação."""
        if len(df) == 0:
            return {
                'taxa_ocupacao_media': 0,
                'taxa_ocupacao_max': 0,
                'hospitais_com_ocupacao': 0,
            }
        
        return {
            'taxa_ocupacao_media': df['taxa_ocupacao'].mean(),
            'taxa_ocupacao_max': df['taxa_ocupacao'].max(),
            'hospitais_com_ocupacao': len(df),
            'leitos_sus_totais': df['leitos_sus'].sum() if 'leitos_sus' in df.columns else 0,
        }
    
    def _indicadores_deslocamento(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calcula indicadores de deslocamento."""
        if 'paciente_viajou' not in df.columns:
            return {'taxa_deslocamento': 0}
        
        viajaram = df['paciente_viajou'].sum()
        total = len(df)
        
        return {
            'taxa_deslocamento': viajaram / total * 100,
            'total_viajaram': viajaram,
            'distancia_media': df['distancia_estimada_km'].mean() if 'distancia_estimada_km' in df.columns else 0,
        }
    
    def _indicadores_diagnostico(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calcula indicadores de diagnóstico."""
        if 'codigo_diagnostico' not in df.columns:
            return {'top_diagnosticos': {}}
        
        top = df['codigo_diagnostico'].value_counts().head(10)
        return {
            'top_diagnosticos': top.to_dict(),
            'total_diagnosticos': df['codigo_diagnostico'].nunique(),
        }