# ============================================================
# RAG MANAGER - CHROMADB
# ============================================================

import os
import chromadb
from chromadb.utils import embedding_functions
from config.config import Config

class RAGManager:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=Config.CHROMA_PERSIST_DIR)
        
        self.embedding_fn = embedding_functions.CohereEmbeddingFunction(
            api_key=Config.COHERE_API_KEY,
            model="embed-english-v3.0"
        )
        
        try:
            self.collection = self.client.get_collection(
                name=Config.CHROMA_COLLECTION_NAME,
                embedding_function=self.embedding_fn
            )
        except:
            self.collection = self.client.create_collection(
                name=Config.CHROMA_COLLECTION_NAME,
                embedding_function=self.embedding_fn
            )
    
    def buscar(self, pergunta: str, k: int = 3) -> list:
        try:
            resultados = self.collection.query(
                query_texts=[pergunta],
                n_results=k
            )
            
            if resultados and 'documents' in resultados:
                return resultados['documents'][0]
            return []
        except:
            return []
    
    def adicionar(self, texto: str, metadados: dict = None):
        if not metadados:
            metadados = {"fonte": "manual"}
        
        self.collection.add(
            documents=[texto],
            metadatas=[metadados],
            ids=[f"doc_{self.collection.count()}"]
        )