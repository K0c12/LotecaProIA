from flask import Flask, render_template_string, request
import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd
import json
import os
import time
import random
import traceback
from duckduckgo_search import DDGS
import urllib3

# Desabilita avisos de segurança
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
ARQUIVO_ESCUDOS = 'escudos.json'

# --- 1. CONFIGURAÇÕES DE ESTRATÉGIA ---
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

# --- 2. FUNÇÕES AUXILIARES ---
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
    # Retorna logo genérica para não travar na busca (opcional: reativar DDGS se quiser)
    return "https://cdn-icons-png.flaticon.com/512/53/53283.png"

# --- 3. GERADOR DE DADOS DE TESTE (SALVA-VIDAS) ---
def gerar_dados_simulados():
    print("⚠️ ATIVANDO MODO DE SIMULAÇÃO (DADOS FICTÍCIOS) ⚠️")
    times = [
        ("Flamengo", "Vasco"), ("Palmeiras", "Corinthians"), ("São Paulo", "Santos"),
        ("Grêmio", "Internacional"), ("Cruzeiro", "Atlético-MG"), ("Bahia", "Vitória"),
        ("Fluminense", "Botafogo"), ("Fortaleza", "Ceará"), ("Sport", "Náutico"),
        ("Coritiba", "Athletico-PR"), ("Goiás", "Vila Nova"), ("Paysandu", "Remo"),
        ("Avaí", "Figueirense"), ("Brasil", "Argentina")
    ]
    dados = []
    for i, (mandante, visitante) in enumerate(times, 1):
        # Gera probabilidades aleatórias que somam 100
        p1 = random.randint(20, 60)
        px = random.randint(20, 40)
        p2 = 100 - (p1 + px)
        if p2 < 0: p2 = 0
        
        dados.append({
            "Jogo": i,
            "Img1": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
            "Mandante": mandante,
            "Prob_Casa": float(p1),
            "Prob_Empate": float(px),
            "Prob_Fora": float(p2),
            "Visitante": visitante,
            "Img2": "https://cdn-icons-png.flaticon.com/512/53/53283.png"
        })
    return pd.DataFrame(dados)

# --- 4. EXTRAÇÃO DE DADOS (COM FALLBACK) ---
def buscar_dados_vovoteca():
    print("--- 📥 TENTANDO BAIXAR DADOS REAIS ---")
    url = "https://vovoteca.com/loteca-enquetes-secos-duplos/"
    scraper = cloudscraper.create_scraper()
    
    try:
        response = scraper.get(url)
        if response.status_code != 200:
            raise Exception(f"Status Code {response.status_code}")

        soup = BeautifulSoup(response.content, 'html.parser')
        dados = []
        dic_escudos = carregar_escudos()
        
        # Tenta encontrar a tabela (Lógica simplificada)
        # Se o site mudou e não acha 'tr-linha', vai cair no except e usar dados simulados
        linhas_encontradas = 0
        for i in range(1, 15):
            linha = soup.find('tr', id=f'tr-linha-{i}')
            if not linha: continue
            
            cols = linha.find_all('td')
            if len(cols) < 6: continue
            
            mandante = cols[1].text.strip()
            visitante = cols[5].text.strip()
            idx = i - 1
            
            try:
                p1 = float(soup.find('td', id=f'resultado-{idx}-home').text.strip().replace('%','').replace(',','.'))
                px = float(soup.find('td', id=f'resultado-{idx}-middle').text.strip().replace('%','').replace(',','.'))
                p2 = float(soup.find('td', id=f'resultado-{idx}-away').text.strip().replace('%','').replace(',','.'))
            except:
                p1, px, p2 = 33.3, 33.3, 33.3

            dados.append({
                "Jogo": i,
                "Img1": dic_escudos.get(mandante, buscar_logo_web(mandante)),
                "Mandante": mandante,
                "Prob_Casa": p1, "Prob_Empate": px, "Prob_Fora": p2,
                "Visitante": visitante,
                "Img2": dic_escudos.get(visitante, buscar_logo_web(visitante))
            })
            linhas_encontradas += 1

        if linhas_encontradas < 14:
            print(f"❌ Encontrei apenas {linhas_encontradas} jogos. O site deve estar carregando via JS.")
            return gerar_dados_simulados() # <--- PULO DO GATO: Se falhar, usa simulado
            
        return pd.DataFrame(dados)
    
    except Exception as e:
        print(f"❌ FALHA NO DOWNLOAD: {e}")
        return gerar_dados_simulados() # <--- Se der erro de conexão, usa simulado

# --- 5. LÓGICA IA ---
def gerar_palpite(p1, px, p2, tipo):
    probs = {'1': p1, 'X': px, '2': p2}
    ordenado = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    fav = ordenado[0][0]
    vice = ordenado[1][0]

    if tipo == "TRIPLO": return "TRIPLO (1 X 2)", "bg-primary text-white"
    elif tipo == "DUPLO":
        palpite = "".join(sorted([fav, vice]))
        return f"DUPLO {palpite.replace('12', '1 2')}", "bg-warning"
    else: return f"COLUNA {fav}", "bg-success text-white"

def aplicar_estrategia(df, nome_estrategia):
    if df.empty: return df
    config = CONFIG_APOSTAS.get(nome_estrategia, CONFIG_APOSTAS["Econômico"])
    
    df['Risco'] = 100 - df[['Prob_Casa', 'Prob_Empate', 'Prob_Fora']].max(axis=1)
    df_sorted = df.sort_values(by='Risco', ascending=False)
    
    ind_triplos = df_sorted.head(config['triplos']).index
    restante = df_sorted.drop(ind_triplos)
    ind_duplos = restante.head(config['duplos']).index

    palpites, classes = [], []
    for idx in df.index:
        tipo = "TRIPLO" if idx in ind_triplos else "DUPLO" if idx in ind_duplos else "SECO"
        txt, css = gerar_palpite(df.at[idx,'Prob_Casa'], df.at[idx,'Prob_Empate'], df.at[idx,'Prob_Fora'], tipo)
        palpites.append(txt)
        classes.append(css)

    df['Palpite IA'] = palpites
    df['Classe_CSS'] = classes
    return df

# --- 6. ROTA FLASK ---
@app.route('/')
def home():
    modo = request.args.get('modo', 'Econômico')
    df = buscar_dados_vovoteca()
    df_final = aplicar_estrategia(df, modo)
    
    # Verifica se os dados são simulados (Flamengo x Vasco é o jogo 1 do simulado)
    eh_simulado = False
    if not df_final.empty and df_final.iloc[0]['Mandante'] == "Flamengo":
        eh_simulado = True

    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
        <meta charset="utf-8"> <title>Loteca pro IA</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #eef2f3; font-family: 'Segoe UI', sans-serif; }
            .container { max-width: 1000px; margin-top: 20px; }
            .card { border-radius: 12px; border:none; shadow:0 4px 15px rgba(0,0,0,0.1); }
            .img-time { height: 30px; }
            .palpite-box { padding: 6px 10px; border-radius: 6px; font-weight: bold; font-size: 0.9rem; }
            td { vertical-align: middle; }
        </style>
    </head>
    <body>
    <div class="container mb-5">
        <div class="card">
            <div class="card-header bg-dark text-white text-center py-3">
                <h3 class="mb-0">🎱 Loteca pro IA</h3>
                <small>Estratégia: {{ modo }}</small>
            </div>
            <div class="card-body bg-white">
                <form class="row justify-content-center g-2 mb-3" onchange="this.submit()">
                    <div class="col-auto align-self-center fw-bold">Mudar Estratégia:</div>
                    <div class="col-auto">
                        <select name="modo" class="form-select form-select-sm">
                            {% for n in opcoes %}
                            <option value="{{ n }}" {% if n == modo %}selected{% endif %}>
                                {{ n }} ({{ configs[n]['duplos'] }}D + {{ configs[n]['triplos'] }}T)
                            </option>
                            {% endfor %}
                        </select>
                    </div>
                </form>

                {% if simulado %}
                <div class="alert alert-warning text-center">
                    <strong>⚠️ MODO OFFLINE / SIMULAÇÃO</strong><br>
                    Não foi possível ler o site oficial (bloqueio ou manutenção).<br>
                    Exibindo <strong>DADOS FICTÍCIOS</strong> apenas para testar a lógica dos palpites.
                </div>
                {% endif %}

                <div class="table-responsive">
                    <table class="table table-hover text-center align-middle">
                        <thead class="table-secondary small">
                            <tr><th>#</th><th>Mandante</th><th>%</th><th>Visitante</th><th>Sugestão IA</th></tr>
                        </thead>
                        <tbody>
                            {% for i, row in df.iterrows() %}
                            <tr>
                                <td class="fw-bold text-muted">{{ row['Jogo'] }}</td>
                                <td class="text-end fw-semibold">{{ row['Mandante'] }} <img src="{{ row['Img1'] }}" class="img-time"></td>
                                <td>
                                    <div class="progress" style="height: 4px;">
                                        <div class="progress-bar bg-success" style="width:{{ row['Prob_Casa'] }}%"></div>
                                        <div class="progress-bar bg-warning" style="width:{{ row['Prob_Empate'] }}%"></div>
                                        <div class="progress-bar bg-danger" style="width:{{ row['Prob_Fora'] }}%"></div>
                                    </div>
                                    <small class="text-muted" style="font-size:0.7rem">
                                        {{ row['Prob_Casa']|int }}/{{ row['Prob_Empate']|int }}/{{ row['Prob_Fora']|int }}
                                    </small>
                                </td>
                                <td class="text-start fw-semibold"><img src="{{ row['Img2'] }}" class="img-time"> {{ row['Visitante'] }}</td>
                                <td><span class="{{ row['Classe_CSS'] }} palpite-box">{{ row['Palpite IA'] }}</span></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    </body>
    </html>
    """
    return render_template_string(html, df=df_final, modo=modo, opcoes=CONFIG_APOSTAS.keys(), configs=CONFIG_APOSTAS, simulado=eh_simulado)

if __name__ == '__main__':
    app.run(debug=True, port=10000)
