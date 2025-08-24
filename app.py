from flask import Flask, render_template, request, jsonify, session
import random
import sqlite3
import uuid
from datetime import datetime
import os
import requests
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_alterar_em_producao')

# Configurações
PRECO_PALPITE = 3.99
CHAVE_PIX = '19668d66-72cb-44cb-b7fc-fe3d1b8c559b'  # Chave PIX

# Inicializar banco de dados
def init_db():
    # No Render, precisamos usar caminho absoluto
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
    
    # Tabela de palpites
    c.execute('''CREATE TABLE IF NOT EXISTS palpites
                 (id TEXT PRIMARY KEY,
                  pagamento_id TEXT,
                  numeros TEXT,
                  data_criacao TIMESTAMP,
                  pago INTEGER DEFAULT 0,
                  FOREIGN KEY (pagamento_id) REFERENCES pagamentos (id))''')
    
    conn.commit()
    conn.close()

# Inicializar o banco ao iniciar a aplicação
init_db()

def gerar_numeros_aleatorios():
    """Gera 15 números aleatórios entre 1 e 25"""
    return sorted(random.sample(range(1, 26), 15))

def gerar_numeros_premium():
    """Gera números 'premium' com uma ligeira alteração na distribuição"""
    # Esta função gera números com uma distribuição um pouco diferente
    # para dar a sensação de que são mais "especiais"
    numeros = []
    
    # Garantir alguns números baixos (1-8)
    numeros.extend(random.sample(range(1, 9), 3))
    
    # Garantir alguns números médios (9-16)
    numeros.extend(random.sample(range(9, 17), 5))
    
    # Garantir alguns números altos (17-25)
    numeros.extend(random.sample(range(17, 26), 4))
    
    # Completar com números aleatórios
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
        # Se já tem um palpite pago na sessão, retorna os números premium
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
        
        # Se não pagou, gera números aleatórios normais
        numeros = gerar_numeros_aleatorios()
        numeros_str = ','.join(str(n) for n in numeros)
        palpite_id = str(uuid.uuid4())
        
        # Salva no banco de dados como não pago
        conn = sqlite3.connect(os.path.join(os.getcwd(), 'lotofacil.db'))
        c = conn.cursor()
        c.execute("INSERT INTO palpites (id, numeros, data_criacao, pago) VALUES (?, ?, ?, ?)",
                 (palpite_id, numeros_str, datetime.now(), 0))
        conn.commit()
        conn.close()
        
        # Salva na sessão
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
            'qrcode_imagem': '',  # Não temos imagem real do QR code
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
        
        # Atualizar status do pagamento para confirmado
        conn = sqlite3.connect(os.path.join(os.getcwd(), 'lotofacil.db'))
        c = conn.cursor()
        c.execute("UPDATE pagamentos SET status = 'confirmado', data_confirmacao = ? WHERE id = ?",
                 (datetime.now(), pagamento_id))
        
        # Gerar novos números "premium" e atualizar o palpite
        numeros_premium = gerar_numeros_premium()
        numeros_str = ','.join(str(n) for n in numeros_premium)
        
        c.execute("UPDATE palpites SET pagamento_id = ?, numeros = ?, pago = 1 WHERE id = ?",
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

# Rota para health check (necessária para o Render)
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'})

# Rota de fallback para evitar erro 404 no Render
@app.route('/<path:path>')
def catch_all(path):
    return render_template('index.html', preco=PRECO_PALPITE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # No Render, precisamos usar host '0.0.0.0'
    app.run(host='0.0.0.0', port=port, debug=False)