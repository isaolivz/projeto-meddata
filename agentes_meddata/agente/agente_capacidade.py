# ============================================================
# AGENTE CAPACITY - COMPLETO (Select AI + LLM + RAG)
# ============================================================

from .base_agente import BaseAgente
from rag.rag_manager import RAGManager
from llm.llm_manager import LLMManager
import json

class AgenteCapacity(BaseAgente):
    def __init__(self, conexao):
        super().__init__(conexao)
        self.nome = "Capacity"
        
        # Inicializa RAG e LLM
        self.rag = RAGManager()
        self.llm = LLMManager()
    
    def responder(self, pergunta: str) -> dict:
        try:
            # 1. Gera SQL com Select AI
            sql = self._gerar_sql_com_select_ai(pergunta)
            
            # 2. Executa SQL
            dados = self._executar_sql(sql)
            
            # 3. Busca documentos com RAG
            contexto = self.rag.buscar(pergunta)
            
            # 4. Gera resposta com LLM
            dados_texto = json.dumps(dados[:10], indent=2, ensure_ascii=False) if dados else "Nenhum dado"
            contexto_texto = "\n".join(contexto) if contexto else ""
            
            resposta = self.llm.gerar_resposta(pergunta, dados_texto, contexto_texto)
            
            return {
                "success": True,
                "resposta": resposta,
                "dados": dados[:20],
                "total": len(dados),
                "sql": sql
            }
            
        except Exception as e:
            return {"success": False, "erro": str(e)}