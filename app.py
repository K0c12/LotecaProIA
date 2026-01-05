from flask import Flask, render_template_string, request
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import os
import time
import traceback # Importante para ver o erro real
from duckduckgo_search import DDGS
import urllib3

# Desabilita avisos de segurança SSL para evitar poluição no terminal
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
ARQUIVO_ESCUDOS = 'escudos.json'

# --- 1. CONFIGURAÇÕES DE ESTRATÉGIA (ATUALIZADAS) ---
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

# --- 2. FUNÇÕES DE ESCUDOS (JSON + BUSCA) ---
def carregar_escudos():
    if os.path.exists(ARQUIVO_ESCUDOS):
        try:
            with open(ARQUIVO_ESCUDOS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

def salvar_escudos(dic_escudos):
    try:
        with open(ARQUIVO_ESCUDOS, 'w', encoding='utf-8') as f:
            json.dump(dic_escudos, f, indent=4, ensure_ascii=False)
    except: pass

def buscar_logo_web(nome_time):
    print(f"   > 🔍 Buscando escudo online para: {nome_time}...")
    try:
        # Busca imagem PNG transparente
        results = DDGS().images(
            keywords=f"escudo {nome_time} futebol png transparent", 
            max_results=1
        )
        lista = list(results)
        if lista:
            return lista[0]['image']
    except Exception as e:
        print(f"     [!] Erro busca img: {e}")
    
    # Imagem genérica se falhar
    return "https://cdn-icons-png.flaticon.com/512/53/53283.png"

# --- 3. EXTRAÇÃO DE DADOS (COM DEBUG DO ERRO) ---
def buscar_dados_vovoteca():
    print("--- 📥 INICIANDO DOWNLOAD DOS DADOS ---")
    url = "https://vovoteca.com/loteca-enquetes-secos-duplos/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }
    
    try:
        # verify=False ignora erros de SSL do site
        response = requests.get(url, headers=headers, verify=False, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ ERRO CRÍTICO NA CONEXÃO COM O SITE:")
        print(e)
        return pd.DataFrame()

    try:
        soup = BeautifulSoup(response.content, 'html.parser')
        dados = []
        dic_escudos = carregar_escudos()
        houve_mudanca = False

        # Tenta encontrar tabelas de várias formas caso o site mude
        for i in range(1, 15):
            try:
                # Tenta encontrar a linha do jogo pelo ID
                linha = soup.find('tr', id=f'tr-linha-{i}')
                if not linha:
                    # Se falhar, tenta achar qualquer tr que contenha os dados (lógica de fallback)
                    continue 
                
                cols = linha.find_all('td')
                if len(cols) < 6: continue

                # Extrai nomes
                mandante = cols[1].text.strip()
                visitante = cols[5].text.strip()
                idx = i - 1
                
                # Extrai porcentagens com tratamento de erro
                try:
                    p1_elem = soup.find('td', id=f'resultado-{idx}-home')
                    px_elem = soup.find('td', id=f'resultado-{idx}-middle')
                    p2_elem = soup.find('td', id=f'resultado-{idx}-away')

                    # Se não achou pelo ID, tenta pegar da linha
                    if not p1_elem: p1 = 0.0
                    else: p1 = float(p1_elem.text.strip().replace('%','').replace(',','.'))

                    if not px_elem: px = 0.0
                    else: px = float(px_elem.text.strip().replace('%','').replace(',','.'))

                    if not p2_elem: p2 = 0.0
                    else: p2 = float(p2_elem.text.strip().replace('%','').replace(',','.'))

                except Exception as e:
                    print(f"Erro ao ler porcentagens jogo {i}: {e}")
                    p1, px, p2 = 33.3, 33.3, 33.3 # Valores padrão para não quebrar

                # Gerencia Escudos
                if mandante not in dic_escudos:
                    dic_escudos[mandante] = buscar_logo_web(mandante)
                    houve_mudanca = True
                    time.sleep(0.5) 
                
                if visitante not in dic_escudos:
                    dic_escudos[visitante] = buscar_logo_web(visitante)
                    houve_mudanca = True
                    time.sleep(0.5)

                dados.append({
                    "Jogo": i,
                    "Img1": dic_escudos.get(mandante, ""),
                    "Mandante": mandante,
                    "Prob_Casa": p1,
                    "Prob_Empate": px,
                    "Prob_Fora": p2,
                    "Visitante": visitante,
                    "Img2": dic_escudos.get(visitante, "")
                })
                print(f"✅ Jogo {i} OK: {mandante} x {visitante}")

            except Exception as e:
                print(f"⚠️ Erro ao processar linha do jogo {i}: {e}")
                traceback.print_exc() # MOSTRA O ERRO DETALHADO
                continue

        if houve_mudanca:
            salvar_escudos(dic_escudos)
            
        return pd.DataFrame(dados)
    
    except Exception as e:
        print("❌ ERRO NO PROCESSAMENTO DO HTML:")
        traceback.print_exc() # ISSO É O QUE VAI TE MOSTRAR O ERRO
        return pd.DataFrame()

# --- 4. LÓGICA DE INTELIGÊNCIA (IA) ---
def gerar_palpite(prob_casa, prob_empate, prob_fora, tipo_protecao):
    probs = {'1': prob_casa, 'X': prob_empate, '2': prob_fora}
    # Ordena do maior para o menor
    ordenado = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    fav_sigla = ordenado[0][0] # O mais provável
    vice_sigla = ordenado[1][0] # O segundo mais provável

    if tipo_protecao == "TRIPLO":
        return "TRIPLO (1 X 2)", "bg-primary text-white" # Azul
    elif tipo_protecao == "DUPLO":
        palpite = "".join(sorted([fav_sigla, vice_sigla])) # Ex: "1X"
        if palpite == "12": palpite = "1 2 (Aberto)"
        return f"DUPLO {palpite}", "bg-warning" # Amarelo
    else:
        return f"COLUNA {fav_sigla}", "bg-success text-white" # Verde

def aplicar_estrategia(df, nome_estrategia):
    if df.empty: return df
    
    config = CONFIG_APOSTAS.get(nome_estrategia, CONFIG_APOSTAS["Econômico"])
    qtd_triplos = config['triplos']
    qtd_duplos = config['duplos']

    # Calcula RISCO: Quanto menor a % do favorito, maior o risco
    # Risco = 100 - (maior probabilidade do jogo)
    df['Risco'] = 100 - df[['Prob_Casa', 'Prob_Empate', 'Prob_Fora']].max(axis=1)

    # Ordena por risco para distribuir Triplos/Duplos nos jogos difíceis
    df_sorted = df.sort_values(by='Risco', ascending=False)
    
    indices_triplos = df_sorted.head(qtd_triplos).index
    restante = df_sorted.drop(indices_triplos)
    indices_duplos = restante.head(qtd_duplos).index

    palpites = []
    classes = []

    for idx in df.index:
        tipo = "SECO"
        if idx in indices_triplos: tipo = "TRIPLO"
        elif idx in indices_duplos: tipo = "DUPLO"
        
        txt, css = gerar_palpite(df.at[idx, 'Prob_Casa'], df.at[idx, 'Prob_Empate'], df.at[idx, 'Prob_Fora'], tipo)
        palpites.append(txt)
        classes.append(css)

    df['Palpite IA'] = palpites
    df['Classe_CSS'] = classes
    return df

# --- 5. ROTA E TEMPLATE HTML ---
@app.route('/')
def home():
    modo_selecionado = request.args.get('modo', 'Econômico')
    
    # Busca e processa
    df = buscar_dados_vovoteca()
    df_calculado = aplicar_estrategia(df, modo_selecionado)

    # Template HTML embutido
    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
        <meta charset="utf-8">
        <title>Loteca pro IA</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #eef2f3; font-family: 'Segoe UI', sans-serif; }
            .container { max-width: 1000px; margin-top: 20px; }
            .card { border: none; shadow: 0 4px 8px rgba(0,0,0,0.1); border-radius: 12px; }
            .img-time { height: 35px; width: 35px; object-fit: contain; }
            .prob-col { font-size: 0.85rem; color: #666; }
            td { vertical-align: middle !important; }
            .palpite-box { padding: 8px; border-radius: 6px; font-weight: bold; font-size: 0.9rem; }
        </style>
    </head>
    <body>
    <div class="container mb-5">
        <div class="card shadow-sm">
            <div class="card-header bg-dark text-white text-center py-3">
                <h3 class="mb-0">🎱 Loteca pro IA</h3>
                <small>Estratégia Atual: {{ modo }}</small>
            </div>
            
            <div class="card-body bg-light border-bottom">
                <form method="get" class="row justify-content-center align-items-center g-2">
                    <div class="col-auto"><label class="fw-bold">Alterar Estratégia:</label></div>
                    <div class="col-auto">
                        <select name="modo" class="form-select form-select-sm" onchange="this.form.submit()">
                            {% for nome in opcoes %}
                                <option value="{{ nome }}" {% if nome == modo %}selected{% endif %}>
                                    {{ nome }} ({{ configs[nome]['duplos'] }}D + {{ configs[nome]['triplos'] }}T)
                                </option>
                            {% endfor %}
                        </select>
                    </div>
                </form>
            </div>

            {% if df.empty %}
                <div class="alert alert-danger m-3 text-center">
                    <h4>❌ Erro na Coleta de Dados</h4>
                    <p>Não foi possível carregar os jogos. Verifique o terminal para ver o motivo exato.</p>
                </div>
            {% else %}
            <div class="table-responsive">
                <table class="table table-hover table-striped text-center mb-0 align-middle">
                    <thead class="table-secondary small">
                        <tr>
                            <th>#</th>
                            <th>Mandante</th>
                            <th style="width: 30%">Probabilidades (%)</th>
                            <th>Visitante</th>
                            <th>Sugestão IA</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for index, row in df.iterrows() %}
                        <tr>
                            <td class="fw-bold text-muted">{{ row['Jogo'] }}</td>
                            <td class="text-end fw-semibold">
                                {{ row['Mandante'] }} <img src="{{ row['Img1'] }}" class="img-time ms-1">
                            </td>
                            <td>
                                <div class="progress" style="height: 6px; margin-bottom: 4px;">
                                    <div class="progress-bar bg-success" style="width: {{ row['Prob_Casa'] }}%"></div>
                                    <div class="progress-bar bg-warning" style="width: {{ row['Prob_Empate'] }}%"></div>
                                    <div class="progress-bar bg-danger" style="width: {{ row['Prob_Fora'] }}%"></div>
                                </div>
                                <div class="d-flex justify-content-between prob-col">
                                    <span>{{ row['Prob_Casa'] }}</span>
                                    <span>{{ row['Prob_Empate'] }}</span>
                                    <span>{{ row['Prob_Fora'] }}</span>
                                </div>
                            </td>
                            <td class="text-start fw-semibold">
                                <img src="{{ row['Img2'] }}" class="img-time me-1"> {{ row['Visitante'] }}
                            </td>
                            <td>
                                <div class="palpite-box {{ row['Classe_CSS'] }}">
                                    {{ row['Palpite IA'] }}
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
        </div>
    </div>
    </body>
    </html>
    """
    
    return render_template_string(html, df=df_calculado, modo=modo_selecionado, opcoes=CONFIG_APOSTAS.keys(), configs=CONFIG_APOSTAS)

if __name__ == '__main__':
    app.run(debug=True, port=10000)
