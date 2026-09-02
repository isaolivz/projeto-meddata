# ============================================================
# API FLASK
# ============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
from database.conexao import DatabaseConnection
from agentes import AgenteCapacity

app = Flask(__name__)
CORS(app)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "OK"})

@app.route('/api/perguntar', methods=['POST'])
def perguntar():
    data = request.get_json()
    pergunta = data.get('pergunta', '')
    
    if not pergunta:
        return jsonify({"success": False, "erro": "Pergunta não fornecida"})
    
    try:
        db = DatabaseConnection()
        conn = db.get_connection()
        agente = AgenteCapacity(conn)
        resultado = agente.responder(pergunta)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"success": False, "erro": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)