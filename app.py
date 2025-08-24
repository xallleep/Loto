from flask import Flask, render_template, request, jsonify, session
import random
import sqlite3
import uuid
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_alterar_em_producao')

# Configurações
PRECO_PALPITE = 3.99
CHAVE_PIX = '19668d66-72cb-44cb-b7fc-fe3d1b8c559b'

# Inicializar banco de dados
def init_db():
    db_path = os.path.join(os.getcwd(), 'lotofacil.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Tabela de pagamentos
    c.execute('''CREATE TABLE IF NOT EXISTS pagamentos
                 (id TEXT PRIMARY KEY, 
                  cliente TEXT,
                  valor REAL,
                  status TEXT,
                  data_criacao TIMESTAMP,
                  data_confirmacao TIMESTAMP,
                  qrcode_texto TEXT,
                  qrcode_imagem TEXT)''')
    
    # Tabela de palpites - CORRIGIDA: removida coluna 'pago'
    c.execute('''CREATE TABLE IF NOT EXISTS palpites
                 (id TEXT PRIMARY KEY,
                  pagamento_id TEXT,
                  numeros TEXT,
                  data_criacao TIMESTAMP,
                  FOREIGN KEY (pagamento_id) REFERENCES pagamentos (id))''')
    
    conn.commit()
    conn.close()

# Verificar e inicializar banco
init_db()

def gerar_numeros_aleatorios():
    """Gera 15 números aleatórios entre 1 e 25"""
    return sorted(random.sample(range(1, 26), 15))

def gerar_numeros_premium():
    """Gera números 'premium' com distribuição otimizada"""
    numeros = []
    
    # Garantir boa distribuição
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

@app.route('/gerar-palpite', methods=['POST'])
def gerar_palpite():
    try:
        # Se já tem palpite pago na sessão
        if 'palpite_pago' in session and session['palpite_pago']:
            palpite_id = session.get('palpite_id')
            conn = sqlite3.connect(os.path.join(os.getcwd(), 'lotofacil.db'))
            c = conn.cursor()
            c.execute("SELECT numeros FROM palpites WHERE id = ?", (palpite_id,))
            resultado = c.fetchone()
            conn.close()
            
            if resultado:
                numeros = list(map(int, resultado[0].split(',')))
                return jsonify({'status': 'success', 'numeros': numeros, 'pago': True})
        
        # Gerar números aleatórios (gratuitos)
        numeros = gerar_numeros_aleatorios()
        numeros_str = ','.join(str(n) for n in numeros)
        palpite_id = str(uuid.uuid4())
        
        # Salvar no banco (sem pagamento_id indica que é gratuito)
        conn = sqlite3.connect(os.path.join(os.getcwd(), 'lotofacil.db'))
        c = conn.cursor()
        c.execute("INSERT INTO palpites (id, numeros, data_criacao) VALUES (?, ?, ?)",
                 (palpite_id, numeros_str, datetime.now()))
        conn.commit()
        conn.close()
        
        # Salvar na sessão
        session['palpite_gerado'] = True
        session['palpite_id'] = palpite_id
        session['palpite_pago'] = False
        
        return jsonify({'status': 'success', 'numeros': numeros, 'pago': False})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/iniciar-pagamento', methods=['POST'])
def iniciar_pagamento():
    try:
        # Criar registro de pagamento
        pagamento_id = str(uuid.uuid4())
        
        # Simular dados do PIX
        qrcode_data = f"00020126580014br.gov.bcb.pix0134{CHAVE_PIX}5204000053039865404{PRECO_PALPITE:.2f}5802BR5925PALPITEIRO PREMIUM LTDA6008BRASILIA62290525{random.randint(10000, 99999)}6304"
        
        # Salvar no banco de dados
        conn = sqlite3.connect(os.path.join(os.getcwd(), 'lotofacil.db'))
        c = conn.cursor()
        
        c.execute("INSERT INTO pagamentos (id, cliente, valor, status, data_criacao, qrcode_texto) VALUES (?, ?, ?, ?, ?, ?)",
                  (pagamento_id, 'Cliente', PRECO_PALPITE, 'pendente', datetime.now(), qrcode_data))
        
        conn.commit()
        conn.close()
        
        # Salvar na sessão
        session['pagamento_id'] = pagamento_id
        
        return jsonify({
            'status': 'success', 
            'pagamento_id': pagamento_id,
            'valor': PRECO_PALPITE,
            'qrcode_texto': qrcode_data,
            'qrcode_imagem': '',
            'chave_pix': CHAVE_PIX
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/confirmar-pagamento', methods=['POST'])
def confirmar_pagamento():
    try:
        pagamento_id = request.json.get('pagamento_id')
        palpite_id = session.get('palpite_id')
        
        if not pagamento_id or not palpite_id:
            return jsonify({'status': 'error', 'message': 'IDs necessários não fornecidos'})
        
        # Atualizar status do pagamento
        conn = sqlite3.connect(os.path.join(os.getcwd(), 'lotofacil.db'))
        c = conn.cursor()
        c.execute("UPDATE pagamentos SET status = 'confirmado', data_confirmacao = ? WHERE id = ?",
                 (datetime.now(), pagamento_id))
        
        # Gerar números premium
        numeros_premium = gerar_numeros_premium()
        numeros_str = ','.join(str(n) for n in numeros_premium)
        
        # Atualizar palpite com pagamento_id (indica que é pago)
        c.execute("UPDATE palpites SET pagamento_id = ?, numeros = ? WHERE id = ?",
                 (pagamento_id, numeros_str, palpite_id))
        
        conn.commit()
        conn.close()
        
        # Atualizar sessão
        session['pagamento_confirmado'] = True
        session['palpite_pago'] = True
        
        return jsonify({'status': 'success', 'numeros': numeros_premium, 'pago': True})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/limpar-sessao', methods=['POST'])
def limpar_sessao():
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'})

@app.route('/<path:path>')
def catch_all(path):
    return render_template('index.html', preco=PRECO_PALPITE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)