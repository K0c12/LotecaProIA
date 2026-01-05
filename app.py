import pandas as pd
# Importa a função do outro arquivo
from coleta_dados_loteca import buscar_dados_vovoteca 

# Chama a função
df = buscar_dados_vovoteca()
import os
import json
import math
import pandas as pd
from flask import Flask, render_template, request, jsonify
from duckduckgo_search import DDGS

app = Flask(__name__)
DB_FILE = 'escudos.json'

# ==============================================================================
# CONFIGURAÇÃO DE ESTRATÉGIAS (O MENU DE PERFIS)
# ==============================================================================
# As chaves devem bater com o que o Frontend envia (ou faremos o ajuste no código)
CONFIG_APOSTAS = {
    "Econômico":          {"duplos": 1, "triplos": 0},
    "Econômico Premium":  {"duplos": 2, "triplos": 0},
    "Fortalecido":        {"duplos": 3, "triplos": 0},
    "Arrojado":           {"duplos": 1, "triplos": 1},
    "Profissional":       {"duplos": 0, "triplos": 2},
    "Avançado":           {"duplos": 2, "triplos": 2},
    "Expert":             {"duplos": 0, "triplos": 3},
    "Master":             {"duplos": 2, "triplos": 3},
    "Elite":              {"duplos": 0, "triplos": 5},
    "Magnata":            {"duplos": 0, "triplos": 6},
    "Dono da Zorra Toda": {"duplos": 5, "triplos": 3}
}

# --- FUNÇÕES DE BANCO DE DADOS E BUSCA (MANTÉM IGUAL) ---
def carregar_banco_escudos():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f: return json.load(f)
    return {}

def salvar_banco_escudos(dados):
    with open(DB_FILE, 'w') as f: json.dump(dados, f, indent=4)

def get_escudo_url(nome_time):
    nome_limpo = nome_time.strip().title()
    banco = carregar_banco_escudos()
    if nome_limpo in banco: return banco[nome_limpo]
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(f"escudo {nome_limpo} futebol png transparente wikipedia", max_results=1))
            if results:
                url = results[0]['image']
                banco[nome_limpo] = url
                salvar_banco_escudos(banco)
                return url
    except: pass
    return "https://cdn-icons-png.flaticon.com/512/53/53283.png"

# --- LÓGICA MATEMÁTICA DINÂMICA ---
def calcular_entropia(o1, ox, o2):
    try:
        p1, px, p2 = 1/float(o1), 1/float(ox), 1/float(o2)
        total = p1 + px + p2
        probs = [(p1/total), (px/total), (p2/total)]
        ent = 0
        for p in probs:
            if p > 0: ent -= p * math.log2(p)
        return ent, (probs[1]*100)
    except: return 0, 0

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/escudo', methods=['POST'])
def api_escudo():
    return jsonify({'url': get_escudo_url(request.json.get('time', ''))})

@app.route('/api/processar', methods=['POST'])
def processar():
    data = request.json
    jogos = data.get('jogos', [])
    
    # Recebe o plano e ajusta formatação (ex: 'dono da zorra toda' -> 'Dono Da Zorra Toda' se necessário)
    # Aqui assumimos que o frontend manda a string próxima da chave.
    # O .strip() remove espaços extras.
    plano_recebido = data.get('plano', 'Arrojado').strip()
    
    # Tenta encontrar direto, ou busca ignorando maiúsculas/minúsculas
    config_selecionada = CONFIG_APOSTAS.get("Arrojado") # Padrão
    
    # Busca insensível a maiúsculas/minúsculas para evitar erros
    for nome_chave, config in CONFIG_APOSTAS.items():
        if nome_chave.lower() == plano_recebido.lower():
            config_selecionada = config
            break

    # 1. DEFINIR LIMITES BASEADO NO PLANO (AGORA DINÂMICO)
    LIMIT_DUPLO = config_selecionada['duplos']
    LIMIT_TRIPLO = config_selecionada['triplos']

    print(f"--> Processando Plano: {plano_recebido} | Triplos: {LIMIT_TRIPLO}, Duplos: {LIMIT_DUPLO}")

    resultados = []
    for jogo in jogos:
        ent, p_empate = calcular_entropia(jogo['o1'], jogo['ox'], jogo['o2'])
        try:
            o1, o2 = float(jogo['o1']), float(jogo['o2'])
            base = "Coluna 1" if o1 < o2 else "Coluna 2"
            if abs(o1 - o2) < 0.2: base = "Meio"
        except: base = "Indefinido"

        resultados.append({
            **jogo, 'entropia': ent, 'prob_empate': p_empate, 'base': base
        })

    # 2. ALOCAÇÃO INTELIGENTE
    df = pd.DataFrame(resultados)
    
    # Achar Triplos (Top Entropia / Jogos Mais Difíceis)
    ids_triplo = []
    if LIMIT_TRIPLO > 0 and not df.empty:
        ids_triplo = df.sort_values(by='entropia', ascending=False).head(LIMIT_TRIPLO)['id'].values.tolist()
    
    # Achar Duplos (Top Empate, removendo os triplos já selecionados)
    ids_duplo = []
    if LIMIT_DUPLO > 0 and not df.empty:
        df_rest = df[~df['id'].isin(ids_triplo)] # Remove quem já é triplo
        ids_duplo = df_rest.sort_values(by='prob_empate', ascending=False).head(LIMIT_DUPLO)['id'].values.tolist()

    # 3. GERAR GABARITO
    gabarito = []
    for r in resultados:
        if r['id'] in ids_triplo:
            tipo = "TRIPLO (1X2)"
            classe = "card-triplo"
        elif r['id'] in ids_duplo:
            # Lógica para definir qual lado do duplo cobrir
            if "1" in r['base'] or r['base'] == "Coluna 1":
                tipo = "DUPLO (1X)"
            elif "2" in r['base'] or r['base'] == "Coluna 2":
                tipo = "DUPLO (X2)"
            else:
                # Se for "Meio", pende para o mandante ou X2 se for muito equilibrado
                tipo = "DUPLO (1X)" 
            classe = "card-duplo"
        else:
            tipo = f"SECO {r['base']}"
            classe = "card-seco"
            
        gabarito.append({
            'id': r['id'],
            'mandante': r['mandante'],
            'visitante': r['visitante'],
            'escudo_m': r['escudo_m'],
            'escudo_v': r['escudo_v'],
            'palpite': tipo,
            'classe': classe
        })

    return jsonify(gabarito)

if __name__ == '__main__':
    if not os.path.exists(DB_FILE): salvar_banco_escudos({})

    app.run(host='0.0.0.0', port=8080)
