"""
Módulo de validação de dados para o projeto MedData.

Este módulo contém funções para validar a qualidade e integridade
dos dados transformados.

Uso:
    from validacao import ValidadorDados
    
    validador = ValidadorDados()
    relatorio = validador.validar_dataset(df, 'sih')
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any


class ValidadorDados:
    """
    Classe para validação de dados do MedData.
    """
    
    def __init__(self):
        """Inicializa o validador."""
        self.regras = {
            'sih': self._regras_sih,
            'cnes': self._regras_cnes,
            'ibge': self._regras_ibge,
            'integrado': self._regras_integrado,
        }
    
    def validar_dataset(self, df: pd.DataFrame, nome: str) -> Dict[str, Any]:
        """
        Valida um dataset baseado em seu nome.
        
        Args:
            df: DataFrame a validar
            nome: Nome do dataset ('sih', 'cnes', 'ibge', 'integrado')
            
        Returns:
            Dicionário com resultados da validação
        """
        if nome in self.regras:
            return self.regras[nome](df)
        else:
            return self._validar_generico(df, nome)
    
    def _validar_generico(self, df: pd.DataFrame, nome: str) -> Dict[str, Any]:
        """Validação genérica para qualquer dataset."""
        return {
            'nome': nome,
            'registros': len(df),
            'colunas': len(df.columns),
            'nulos': df.isnull().sum().sum(),
            'duplicatas': df.duplicated().sum(),
            'status': 'OK' if len(df) > 0 else 'FALHA'
        }
    
    def _regras_sih(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validação específica para SIH."""
        relatorio = self._validar_generico(df, 'sih')
        
        # Colunas obrigatórias
        colunas_obrigatorias = [
            'codigo_municipio', 'id_hospital', 'codigo_diagnostico',
            'data_internacao', 'data_saida', 'valor_procedimento',
            'codigo_municipio_paciente'
        ]
        
        colunas_faltando = [col for col in colunas_obrigatorias if col not in df.columns]
        relatorio['colunas_faltando'] = colunas_faltando
        
        # Verificar datas
        if 'data_internacao' in df.columns:
            datas_invalidas = df['data_internacao'].isnull().sum()
            relatorio['datas_invalidas'] = datas_invalidas
        
        # Verificar valores negativos
        if 'valor_procedimento' in df.columns:
            negativos = (df['valor_procedimento'] < 0).sum()
            relatorio['valores_negativos'] = negativos
        
        # Status final
        relatorio['status'] = 'OK' if (
            len(df) > 0 and
            len(colunas_faltando) == 0 and
            relatorio.get('datas_invalidas', 0) == 0
        ) else 'ATENCAO'
        
        return relatorio
    
    def _regras_cnes(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validação específica para CNES."""
        relatorio = self._validar_generico(df, 'cnes')
        
        # Colunas obrigatórias
        colunas_obrigatorias = [
            'id_hospital', 'codigo_municipio', 'total_leitos'
        ]
        
        colunas_faltando = [col for col in colunas_obrigatorias if col not in df.columns]
        relatorio['colunas_faltando'] = colunas_faltando
        
        # Verificar leitos
        if 'total_leitos' in df.columns:
            sem_leitos = (df['total_leitos'] == 0).sum()
            relatorio['hospitais_sem_leitos'] = sem_leitos
        
        # Status final
        relatorio['status'] = 'OK' if (
            len(df) > 0 and
            len(colunas_faltando) == 0
        ) else 'ATENCAO'
        
        return relatorio
    
    def _regras_ibge(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validação específica para IBGE."""
        relatorio = self._validar_generico(df, 'ibge')
        
        # Colunas obrigatórias
        colunas_obrigatorias = [
            'codigo_municipio', 'nome_municipio', 'latitude', 'longitude'
        ]
        
        colunas_faltando = [col for col in colunas_obrigatorias if col not in df.columns]
        relatorio['colunas_faltando'] = colunas_faltando
        
        # Status final
        relatorio['status'] = 'OK' if (
            len(df) > 0 and
            len(colunas_faltando) == 0
        ) else 'ATENCAO'
        
        return relatorio
    
    def _regras_integrado(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validação específica para dataset integrado."""
        relatorio = self._validar_generico(df, 'integrado')
        
        # Verificar colunas chave
        colunas_chave = ['id_hospital', 'codigo_municipio', 'data_internacao']
        for col in colunas_chave:
            if col in df.columns:
                nulos = df[col].isnull().sum()
                relatorio[f'{col}_nulos'] = nulos
        
        # Verificar integridade dos joins
        if 'leitos_sus' in df.columns:
            sem_leitos = df['leitos_sus'].isnull().sum()
            relatorio['sem_dados_cnes'] = sem_leitos
        
        if 'latitude_hospital' in df.columns:
            sem_coordenadas = df['latitude_hospital'].isnull().sum()
            relatorio['sem_coordenadas'] = sem_coordenadas
        
        # Status final
        relatorio['status'] = 'OK' if (
            len(df) > 0 and
            relatorio.get('sem_dados_cnes', len(df)) < len(df) * 0.3
        ) else 'ATENCAO'
        
        return relatorio