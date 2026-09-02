# ============================================================
# LLM MANAGER - COHERE
# ============================================================

import cohere
from config.config import Config

class LLMManager:
    def __init__(self):
        self.client = cohere.Client(api_key=Config.COHERE_API_KEY)
        self.model = Config.COHERE_MODEL
    
    def gerar_resposta(self, pergunta: str, dados: str, contexto: str) -> str:
        prompt = f"""
        Você é um assistente de gestão hospitalar.
        
        PERGUNTA: {pergunta}
        
        DADOS: {dados}
        
        CONTEXTO: {contexto if contexto else "Nenhum"}
        
        Responda em português, de forma clara e objetiva.
        """
        
        resposta = self.client.generate(
            model=self.model,
            prompt=prompt,
            max_tokens=500,
            temperature=0.3
        )
        
        return resposta.generations[0].text.strip()