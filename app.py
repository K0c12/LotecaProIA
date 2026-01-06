from flask import Flask, render_template_string, request
import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd
import json
import os
import requests
import traceback
from duckduckgo_search import DDGS
import urllib3

# Desabilita avisos de segurança (Necessário para o site da Caixa)
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

def buscar_logo_web(nome_time):
    return "https://cdn-icons-png.flaticon.com/512/53/53283.png"

# --- 3. SISTEMA DE COLETA (HIERARQUIA DE FONTES) ---

def buscar_dados_vovoteca():
    """ TENTATIVA 1: Site Vovoteca (Melhor pois tem % pronta) """
    print("--- 1️⃣ TENTANDO VOVOTECA ---")
    url = "https://vovoteca.com/loteca-enquetes-secos-duplos/"
    scraper = cloudscraper.create_scraper()
    
    try:
        response = scraper.get(url, timeout=10)
        if response.status_code != 200: return None

        soup = BeautifulSoup(response.content, 'html.parser')
        dados = []
        dic_escudos = carregar_escudos()
        
        contagem = 0
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
                "Mandante": mandante, "Visitante": visitante,
                "Prob_Casa": p1, "Prob_Empate": px, "Prob_Fora": p2
            })
            contagem += 1
        
        if contagem < 14: return None 
        return pd.DataFrame(dados)
    except:
        return None

def buscar_dados_caixa():
    """ TENTATIVA 2: Site Oficial da Caixa (Apenas nomes, sem %) """
    print("--- 2️⃣ TENTANDO SITE DA CAIXA ---")
    url = "https://loterias.caixa.gov.br/Paginas/Programacao-Loteca.aspx"
    
    # Headers para fingir ser um navegador comum
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        # A Caixa exige verify=False por problemas de certificado SSL
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        if response.status_code != 200: return None

        soup = BeautifulSoup(response.content, 'html.parser')
        dados = []
        
        # Encontra a tabela da Loteca
        tabela = soup.find('table', class_='loteca')
        if not tabela: return None
        
        linhas = tabela.find_all('tr')
        contador = 0
        
        for linha in linhas:
            cols = linha.find_all('td')
            # A estrutura da caixa geralmente tem o ID do jogo na primeira coluna
            if len(cols) >= 5:
                try:
                    # Verifica se a primeira coluna é um número (1 a 14)
                    jogo_num = cols[0].text.strip()
                    if not jogo_num.isdigit(): continue
                    
                    # Extrai os nomes (Baseado no HTML que você mandou)
                    # Coluna 2 (índice 2) é Mandante, Coluna 4 (índice 4) é Visitante
                    mandante = cols[2].text.strip()
                    visitante = cols[4].text.strip()
                    
                    if mandante and visitante:
                        dados.append({
                            "Jogo": int(jogo_num),
                            "Mandante": mandante, "Visitante": visitante,
                            "Prob_Casa": 33.3, "Prob_Empate": 33.4, "Prob_Fora": 33.3 # Padrão neutro
                        })
                        contador += 1
                except: continue

        if contador < 14: return None
        print("✅ Dados obtidos da CAIXA com sucesso!")
        return pd.DataFrame(dados)

    except Exception as e:
        print(f"❌ Erro Caixa: {e}")
        return None

def obter_dados_finais():
    # 1. Tenta Vovoteca
    df = buscar_dados_vovoteca()
    if df is not None and not df.empty:
        return df, "automático (Vovoteca)"
    
    # 2. Tenta Caixa
    df = buscar_dados_caixa()
    if df is not None and not df.empty:
        return df, "manual_caixa" # Retorna flag para abrir modo manual
    
    # 3. Backup Estático (Último recurso)
    backup = [
        {"Jogo": i, "Mandante": "Time Casa", "Visitante": "Time Fora", "Prob_Casa": 33, "Prob_Empate": 34, "Prob_Fora": 33}
        for i in range(1, 15)
    ]
    return pd.DataFrame(backup), "manual_backup"

# --- 4. LÓGICA DA IA ---
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
    return df.sort_values(by='Jogo')

# --- 5. ROTAS FLASK ---

@app.route('/', methods=['GET', 'POST'])
def home():
    modo = request.args.get('modo', 'Econômico')

    # --- PROCESSAMENTO DO FORMULÁRIO MANUAL ---
    if request.method == 'POST':
        modo = request.form.get('modo_selecionado')
        dados_manuais = []
        for i in range(1, 15):
            mandante = request.form.get(f'time1_{i}')
            visitante = request.form.get(f'time2_{i}')
            p1 = float(request.form.get(f'range1_{i}', 33))
            p2 = float(request.form.get(f'range2_{i}', 33))
            px = 100 - (p1 + p2)
            if px < 0: px = 0
            
            dados_manuais.append({
                "Jogo": i, "Mandante": mandante, "Visitante": visitante,
                "Prob_Casa": p1, "Prob_Empate": px, "Prob_Fora": p2,
                "Img1": "", "Img2": ""
            })
        
        df_final = aplicar_estrategia(pd.DataFrame(dados_manuais), modo)
        return render_resultado(df_final, modo)

    # --- CARREGAMENTO INICIAL ---
    df, fonte = obter_dados_finais()

    # Se a fonte não for automática (Vovoteca), força o modo manual para ajuste
    if fonte != "automático (Vovoteca)":
        lista_jogos = []
        for _, row in df.iterrows():
            lista_jogos.append((row['Mandante'], row['Visitante']))
        return render_manual(modo, lista_jogos, fonte)
    
    # Se for Vovoteca, mostra resultado direto
    df_final = aplicar_estrategia(df, modo)
    return render_resultado(df_final, modo)

# --- 6. TELAS HTML ---

def render_manual(modo, lista_jogos, fonte_origem):
    msg_alerta = "Ajuste sua intuição abaixo."
    if fonte_origem == "manual_caixa":
        msg_alerta = "Dados obtidos do <strong>Site da Caixa</strong>. Como eles não fornecem probabilidades, ajuste as barras abaixo."
    elif fonte_origem == "manual_backup":
        msg_alerta = "<strong>Modo Offline Total.</strong> Sites indisponíveis."

    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Loteca Pro IA - Ajuste Manual</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #f0f2f5; font-family: 'Segoe UI', sans-serif; }
            .card-game { background: white; margin-bottom: 15px; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        </style>
    </head>
    <body>
    <div class="container py-4">
        <div class="alert alert-warning text-center">
            ⚠️ {{ msg|safe }}
        </div>
        
        <form method="POST" action="/">
            <div class="card mb-3 p-3 text-center bg-dark text-white">
                <label>Estratégia Selecionada:</label>
                <select name="modo_selecionado" class="form-select mt-2">
                    {% for n in opcoes %}
                    <option value="{{ n }}" {% if n == modo %}selected{% endif %}>{{ n }}</option>
                    {% endfor %}
                </select>
            </div>

            {% for time1, time2 in jogos %}
            <div class="card-game">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="badge bg-secondary">{{ loop.index }}</span>
                    <div class="text-center w-100">
                        <input type="hidden" name="time1_{{ loop.index }}" value="{{ time1 }}">
                        <input type="hidden" name="time2_{{ loop.index }}" value="{{ time2 }}">
                        <span class="fw-bold text-primary">{{ time1 }}</span> 
                        <span class="text-muted small">x</span> 
                        <span class="fw-bold text-danger">{{ time2 }}</span>
                    </div>
                </div>

                <div class="row g-2">
                    <div class="col-12">
                        <label class="small text-muted">Força {{ time1 }}: <span id="val1_{{ loop.index }}">33</span>%</label>
                        <input type="range" class="form-range" min="0" max="100" value="33" 
                               name="range1_{{ loop.index }}" id="r1_{{ loop.index }}" 
                               oninput="atualizar({{ loop.index }})">
                    </div>
                    <div class="col-12">
                        <label class="small text-muted">Força {{ time2 }}: <span id="val2_{{ loop.index }}">33</span>%</label>
                        <input type="range" class="form-range" min="0" max="100" value="33" 
                               name="range2_{{ loop.index }}" id="r2_{{ loop.index }}" 
                               oninput="atualizar({{ loop.index }})">
                    </div>
                </div>
                <div class="text-center mt-1">
                    <small>Empate previsto: <strong id="valX_{{ loop.index }}" class="text-warning">34%</strong></small>
                </div>
            </div>
            {% endfor %}

            <button type="submit" class="btn btn-success w-100 py-3 fw-bold fs-5">🎲 CALCULAR PALPITES</button>
        </form>
    </div>

    <script>
    function atualizar(id) {
        let r1 = document.getElementById('r1_' + id);
        let r2 = document.getElementById('r2_' + id);
        let v1 = parseInt(r1.value);
        let v2 = parseInt(r2.value);
        if (v1 + v2 > 100) { v2 = 100 - v1; r2.value = v2; }
        let vx = 100 - (v1 + v2);
        document.getElementById('val1_' + id).innerText = v1;
        document.getElementById('val2_' + id).innerText = v2;
        document.getElementById('valX_' + id).innerText = vx + '%';
    }
    </script>
    </body>
    </html>
    """
    return render_template_string(html, jogos=lista_jogos, modo=modo, opcoes=CONFIG_APOSTAS.keys(), msg=msg_alerta)

def render_resultado(df, modo):
    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
        <meta charset="utf-8"> <title>Resultado Loteca Pro IA</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #eef2f3; }
            .palpite-box { padding: 5px 10px; border-radius: 5px; font-weight: bold; display:inline-block; width:100%; }
        </style>
    </head>
    <body>
    <div class="container py-3">
        <div class="card shadow">
            <div class="card-header bg-success text-white text-center">
                <h3 class="mb-0">🎱 Palpites Gerados</h3>
                <small>{{ modo }}</small>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-striped text-center align-middle mb-0">
                        <thead class="table-dark">
                            <tr><th>#</th><th>Confronto</th><th>Probabilidades</th><th>Palpite IA</th></tr>
                        </thead>
                        <tbody>
                            {% for i, row in df.iterrows() %}
                            <tr>
                                <td class="fw-bold">{{ row['Jogo'] }}</td>
                                <td>
                                    <div class="d-flex justify-content-between small fw-bold">
                                        <span class="text-primary">{{ row['Mandante'] }}</span>
                                        <span class="text-danger">{{ row['Visitante'] }}</span>
                                    </div>
                                </td>
                                <td>
                                    <div class="progress" style="height: 6px;">
                                        <div class="progress-bar bg-success" style="width:{{ row['Prob_Casa'] }}%"></div>
                                        <div class="progress-bar bg-warning" style="width:{{ row['Prob_Empate'] }}%"></div>
                                        <div class="progress-bar bg-danger" style="width:{{ row['Prob_Fora'] }}%"></div>
                                    </div>
                                    <small style="font-size:0.7rem">
                                        {{ row['Prob_Casa']|int }}% / {{ row['Prob_Empate']|int }}% / {{ row['Prob_Fora']|int }}%
                                    </small>
                                </td>
                                <td><span class="{{ row['Classe_CSS'] }} palpite-box">{{ row['Palpite IA'] }}</span></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="card-footer text-center">
                <a href="/" class="btn btn-outline-dark">🔄 Reiniciar</a>
            </div>
        </div>
    </div>
    </body>
    </html>
    """
    return render_template_string(html, df=df, modo=modo)

if __name__ == '__main__':
    app.run(debug=True, port=10000)
