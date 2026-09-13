# ============================================================
# CLASSE BASE PARA TODOS OS AGENTES
# ============================================================

class BaseAgente:
    def __init__(self, conexao):
        self.conexao = conexao
        self.profile_name = "MEU_PROFILE"
    
    def responder(self, pergunta: str):
        raise NotImplementedError("Cada agente deve implementar 'responder'")
    
    def _gerar_sql_com_select_ai(self, pergunta: str) -> str:
        sql = f"""
        SELECT DBMS_CLOUD_AI.GENERATE(
            prompt => 'Gere SQL para: {pergunta}',
            profile_name => '{self.profile_name}'
        ) FROM dual
        """
        cursor = self.conexao.cursor()
        cursor.execute(sql)
        return cursor.fetchone()[0]
    
    def _executar_sql(self, sql: str) -> list:
        cursor = self.conexao.cursor()
        cursor.execute(sql)
        colunas = [desc[0].lower() for desc in cursor.description] if cursor.description else []
        resultados = []
        for row in cursor.fetchall():
            if colunas:
                resultados.append(dict(zip(colunas, row)))
            else:
                resultados.append(row)
        return resultados