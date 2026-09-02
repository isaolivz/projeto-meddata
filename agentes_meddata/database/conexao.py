# ============================================================
# CONEXÃO COM O ORACLE
# ============================================================

import oracledb
from config.config import Config

class DatabaseConnection:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._conectar()
        return cls._instance
    
    def _conectar(self):
        try:
            self.conn = oracledb.connect(
                user=Config.ORACLE_USER,
                password=Config.ORACLE_PASSWORD,
                dsn=Config.ORACLE_DSN
            )
            print("Conectado ao Oracle!")
        except Exception as e:
            print(f"Erro: {e}")
            raise
    
    def get_connection(self):
        return self.conn
    
    def close(self):
        if hasattr(self, 'conn'):
            self.conn.close()