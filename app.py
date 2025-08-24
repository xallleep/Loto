from flask import Flask, render_template, request, jsonify, session
import random
import sqlite3
import uuid
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_secreta_alterar_em_producao')

# Configurações
PRECO_PALPITE = 3.99
CHAVE_PIX = '19668d66-72cb-44cb-b7fc-fe3d1b8c559b'

# Função para inicializar o banco de dados
def init_db():
    try:
        db_path = os.path.join(os.getcwd(), 'lotofacil.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Criar tabela de pagamentos
        c.execute('''CREATE TABLE IF NOT EXISTS pagamentos
                     (id TEXT PRIMARY KEY, 
                      cliente TEXT,
                      valor REAL,
                      data_criacao TIMESTAMP,
                      data_confirmacao TIMESTAMP)''')
        
        # Criar tabela de palpites
        c.execute('''CREATE TABLE IF NOT EXISTS palpites
                     (id TEXT PRIMARY KEY,
                      pagamento_id TEXT,
                      numeros TEXT,
                      data_criacao TIMESTAMP,
                      premium BOOLEAN DEFAULT FALSE)''')
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Erro ao inicializar banco de dados: {e}")

# Inicializar o banco ao iniciar
init_db()

def gerar_numeros_premium():
    """Gera números 'premium' com distribuição otimizada"""
    numeros = []
    
    # Estratégia de distribuição "premium"
    numeros.extend(random.sample(range(1, 9), 4))      # Baixos: 1-8
    numeros.extend(random.sample(range(9, 17), 5))     # Médios: 9-16  
    numeros.extend(random.sample(range(17, 26), 6))    # Altos: 17-25
    
    # Garantir 15 números únicos
    while len(numeros) < 15:
        novo_numero = random.randint(1, 25)
        if novo_numero not in numeros:
            numeros.append(novo_numero)
    
    return sorted(numeros)

@app.route('/')
def index():
    return render_template('index.html', preco=PRECO_PALPITE)

@app.route('/solicitar-pagamento', methods=['POST'])
def solicitar_pagamento():
    try:
        # Gerar ID único para esta transação
        transacao_id = str(uuid.uuid4())
        
        # Salvar na sessão
        session['transacao_id'] = transacao_id
        session['aguardando_pagamento'] = True
        
        return jsonify({
            'status': 'success', 
            'transacao_id': transacao_id,
            'valor': PRECO_PALPITE,
            'chave_pix': CHAVE_PIX,
            'mensagem': 'Faça o PIX e clique em "Já Paguei" para gerar seus números premium'
        })
        
    except Exception as e:
        print(f"Erro em solicitar-pagamento: {e}")
        return jsonify({'status': 'error', 'message': 'Erro ao processar solicitação'}), 500

@app.route('/gerar-palpite-premium', methods=['POST'])
def gerar_palpite_premium():
    try:
        # Verificar se há uma transação em andamento
        if not session.get('aguardando_pagamento'):
            return jsonify({'status': 'error', 'message': 'Solicite o pagamento primeiro'})
        
        transacao_id = session.get('transacao_id')
        
        if not transacao_id:
            return jsonify({'status': 'error', 'message': 'Sessão inválida'})
        
        conn = sqlite3.connect(os.path.join(os.getcwd(), 'lotofacil.db'))
        c = conn.cursor()
        
        # Registrar o pagamento
        c.execute("INSERT INTO pagamentos (id, cliente, valor, data_criacao, data_confirmacao) VALUES (?, ?, ?, ?, ?)",
                  (transacao_id, 'Cliente', PRECO_PALPITE, datetime.now(), datetime.now()))
        
        # Gerar números premium
        numeros_premium = gerar_numeros_premium()
        numeros_str = ','.join(str(n) for n in numeros_premium)
        
        # Criar palpite premium
        palpite_id = str(uuid.uuid4())
        c.execute("INSERT INTO palpites (id, pagamento_id, numeros, data_criacao, premium) VALUES (?, ?, ?, ?, ?)",
                 (palpite_id, transacao_id, numeros_str, datetime.now(), True))
        
        conn.commit()
        conn.close()
        
        # Limpar sessão
        session['palpite_gerado'] = True
        session['palpite_id'] = palpite_id
        session['palpite_pago'] = True
        session['aguardando_pagamento'] = False
        
        return jsonify({
            'status': 'success', 
            'numeros': numeros_premium, 
            'pago': True,
            'mensagem': 'Palpite premium gerado com sucesso! Boa sorte!'
        })
        
    except Exception as e:
        print(f"Erro em gerar-palpite-premium: {e}")
        return jsonify({'status': 'error', 'message': 'Erro ao gerar palpite premium'}), 500

@app.route('/limpar-sessao', methods=['POST'])
def limpar_sessao():
    try:
        session.clear()
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Erro em limpar-sessao: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'})

@app.route('/<path:path>')
def catch_all(path):
    return render_template('index.html', preco=PRECO_PALPITE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)