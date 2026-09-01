# ============================================================
# TESTE LOCAL
# ============================================================

from database.conexao import DatabaseConnection
from agentes import AgenteCapacity

def main():
    print("=" * 60)
    print("🏥 TESTE - AGENTE CAPACITY")
    print("=" * 60)
    
    db = DatabaseConnection()
    conn = db.get_connection()
    
    agente = AgenteCapacity(conn)
    
    pergunta = input("\n🔍 Pergunta: ")
    resultado = agente.responder(pergunta)
    
    if resultado['success']:
        print(f"\n✅ {resultado['resposta']}")
        print(f"\n📊 Total: {resultado['total']} registros")
    else:
        print(f"❌ Erro: {resultado['erro']}")
    
    db.close()

if __name__ == "__main__":
    main()