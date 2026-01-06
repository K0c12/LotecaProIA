from flask import Flask, render_template_string, request
import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd
import json
import os
import requests
import traceback
import urllib3

# Desabilita avisos de segurança para o site da Caixa
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

# --- 2. FUNÇÕES DE SUPORTE ---
def carregar_escudos():
    if os.path.exists(ARQUIVO_ESCUDOS):
        try:
            with open(ARQUIVO_ESCUDOS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

# --- 3. COLETA DE DADOS (Vovoteca -> Caixa -> Backup) ---
def buscar_dados_vovoteca():
    """ TENTATIVA 1: Site Vovoteca (Já vem com porcentagens) """
    print("--- 1️⃣ TENTANDO VOVOTECA ---")
    url = "https://vovoteca.com/loteca-enquetes-secos-duplos/"
    scraper = cloudscraper.create_scraper()
    
    try:
        response = scraper.get(url, timeout=10)
        if response.status_code != 200: return None

        soup = BeautifulSoup(response.content, 'html.parser')
        dados = []
        
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
                "Jogo": i, "Mandante": mandante, "Visitante": visitante,
                "Prob_Casa": p1, "Prob_Empate": px, "Prob_Fora": p2
            })
            contagem += 1
        
        if contagem < 14: return None 
        return pd.DataFrame(dados)
    except: return None

def buscar_dados_caixa():
    """ TENTATIVA 2: Site da Caixa (Apenas nomes dos times) """
    print("--- 2️⃣ TENTANDO SITE DA CAIXA ---")
    url = "https://loterias.caixa.gov.br/Paginas/Programacao-Loteca.aspx"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}

    try:
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        if response.status_code != 200: return None

        soup = BeautifulSoup(response.content, 'html.parser')
        dados = []
        tabela = soup.find('table', class_='loteca')
        if not tabela: return None
        
        for linha in tabela.find_all('tr'):
            cols = linha.find_all('td')
            if len(cols) >= 5:
                try:
                    jogo_num = cols[0].text.strip()
                    if not jogo_num.isdigit(): continue
                    mandante = cols[2].text.strip()
                    visitante = cols[4].text.strip()
                    if mandante and visitante:
                        # Define padrão 33/33/33 para ajuste manual
                        dados.append({"Jogo": int(jogo_num), "Mandante": mandante, "Visitante": visitante, "Prob_Casa": 33, "Prob_Empate": 34, "Prob_Fora": 33})
                except: continue

        if len(dados) < 14: return None
        return pd.DataFrame(dados)
    except: return None

def obter_dados_finais():
    # 1. Tenta Vovoteca (Automático)
    df = buscar_dados_vovoteca()
    if df is not None and not df.empty: return df, "automático"
    
    # 2. Tenta Caixa (Manual assistido)
    df = buscar_dados_caixa()
    if df is not None and not df.empty: return df, "manual_caixa"
    
    # 3. Backup Total (Manual puro)
    backup = [{"Jogo": i, "Mandante": f"Time {i}A", "Visitante": f"Time {i}B", "Prob_Casa": 33, "Prob_Empate": 34, "Prob_Fora": 33} for i in range(1, 15)]
    return pd.DataFrame(backup), "manual_backup"

# --- 4. LÓGICA IA ---
def gerar_palpite(p1, px, p2, tipo):
    probs = {'1': p1, 'X': px, '2': p2}
    ordenado = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    fav, vice = ordenado[0][0], ordenado[1][0]

    if tipo == "TRIPLO": return "TRIPLO (1 X 2)", "bg-primary text-white"
    elif tipo == "DUPLO":
        palpite = "".join(sorted([fav, vice])).replace('12', '1 2')
        return f"DUPLO {palpite}", "bg-warning"
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

# --- 5. ROTA PRINCIPAL ---
@app.route('/', methods=['GET', 'POST'])
def home():
    modo = request.args.get('modo', 'Econômico')

    # SE O USUÁRIO ENVIOU OS DADOS MANUAIS (Clicou em Calcular)
    if request.method == 'POST':
        modo = request.form.get('modo_selecionado')
        dados = []
        for i in range(1, 15):
            mandante = request.form.get(f'time1_{i}')
            visitante = request.form.get(f'time2_{i}')
            # Pega valores dos sliders
            p1 = float(request.form.get(f'range1_{i}', 33))
            p2 = float(request.form.get(f'range2_{i}', 33))
            px = 100 - (p1 + p2)
            if px < 0: px = 0
            
            dados.append({"Jogo": i, "Mandante": mandante, "Visitante": visitante, "Prob_Casa": p1, "Prob_Empate": px, "Prob_Fora": p2})
        
        df_final = aplicar_estrategia(pd.DataFrame(dados), modo)
        return render_resultado(df_final, modo)

    # SE ESTÁ ABRINDO O SITE (GET)
    df, fonte = obter_dados_finais()
    
    # Se não veio do Vovoteca (que já tem porcentagem), abre o MODO MANUAL com Sliders
    if fonte != "automático":
        lista_jogos = [(row['Mandante'], row['Visitante']) for _, row in df.iterrows()]
        return render_manual(modo, lista_jogos, fonte)

    # Se veio do Vovoteca, mostra direto
    df_final = aplicar_estrategia(df, modo)
    return render_resultado(df_final, modo)

# --- 6. TELAS HTML ---
def render_manual(modo, lista_jogos, fonte_origem):
    msg = "Ajuste as barras abaixo para definir as probabilidades."
    if fonte_origem == "manual_caixa":
        msg = "Times carregados da <strong>Caixa</strong>. Defina o favoritismo arrastando as barras!"

    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Ajuste Manual - Loteca IA</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #f0f2f5; font-family: 'Segoe UI', sans-serif; }
            .card-game { background: white; margin-bottom: 20px; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
            /* Estilo dos Sliders */
            input[type=range] { width: 100%; cursor: pointer; }
            .team-label { font-weight: bold; font-size: 1.1rem; }
            .percent-val { font-weight: bold; font-size: 1.2rem; min-width: 50px; display: inline-block; text-align: right;}
            .vs-badge { background: #e9ecef; padding: 5px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; color: #6c757d; }
        </style>
    </head>
    <body>
    <div class="container py-4">
        <div class="alert alert-info text-center shadow-sm">
            🎯 <strong>Modo de Edição Manual</strong><br>{{ msg|safe }}
        </div>
        
        <form method="POST" action="/">
            <div class="card mb-4 border-0 shadow-sm bg-dark text-white">
                <div class="card-body text-center">
                    <label class="form-label fw-bold">Estratégia do Robô:</label>
                    <select name="modo_selecionado" class="form-select form-select-lg text-center fw-bold">
                        {% for n in opcoes %}
                        <option value="{{ n }}" {% if n == modo %}selected{% endif %}>{{ n }}</option>
                        {% endfor %}
                    </select>
                </div>
            </div>

            {% for time1, time2 in jogos %}
            <div class="card-game">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <span class="badge bg-secondary rounded-circle p-2">{{ loop.index }}</span>
                    <div class="text-center w-100 px-2">
                        <input type="hidden" name="time1_{{ loop.index }}" value="{{ time1 }}">
                        <input type="hidden" name="time2_{{ loop.index }}" value="{{ time2 }}">
                        <div class="d-flex justify-content-center align-items-center gap-2">
                            <span class="team-label text-primary">{{ time1 }}</span>
                            <span class="vs-badge">X</span>
                            <span class="team-label text-danger">{{ time2 }}</span>
                        </div>
                    </div>
                </div>

                <div class="row g-3 align-items-center mb-2">
                    <div class="col-12">
                        <label class="d-flex justify-content-between small text-muted">
                            <span>Vitória {{ time1 }}</span>
                            <span class="text-primary"><span id="txt1_{{ loop.index }}">33</span>%</span>
                        </label>
                        <input type="range" class="form-range" min="0" max="100" value="33" 
                               name="range1_{{ loop.index }}" id="r1_{{ loop.index }}" 
                               oninput="atualizar({{ loop.index }}, 'mandante')">
                    </div>
                    
                    <div class="col-12">
                        <label class="d-flex justify-content-between small text-muted">
                            <span>Vitória {{ time2 }}</span>
                            <span class="text-danger"><span id="txt2_{{ loop.index }}">33</span>%</span>
                        </label>
                        <input type="range" class="form-range" min="0" max="100" value="33" 
                               name="range2_{{ loop.index }}" id="r2_{{ loop.index }}" 
                               oninput="atualizar({{ loop.index }}, 'visitante')">
                    </div>
                </div>

                <div class="text-center bg-light p-2 rounded">
                    <small class="text-muted fw-bold">Probabilidade de Empate (Automático)</small>
                    <div class="d-flex justify-content-center align-items-center gap-2 mb-2">
                        <span class="percent-val text-warning" id="txtX_{{ loop.index }}">34%</span>
                    </div>
                    
                    <div class="progress" style="height: 12px; border-radius: 6px;">
                        <div class="progress-bar bg-primary" id="bar1_{{ loop.index }}" style="width: 33%" title="{{ time1 }}"></div>
                        <div class="progress-bar bg-warning text-dark" id="barX_{{ loop.index }}" style="width: 34%" title="Empate"></div>
                        <div class="progress-bar bg-danger" id="bar2_{{ loop.index }}" style="width: 33%" title="{{ time2 }}"></div>
                    </div>
                </div>
            </div>
            {% endfor %}

            <div class="d-grid gap-2 mb-5">
                <button type="submit" class="btn btn-success btn-lg fw-bold shadow">
                    🎲 GERAR PALPITES AGORA
                </button>
            </div>
        </form>
    </div>

    <script>
    function atualizar(id, origem) {
        let r1 = document.getElementById('r1_' + id); // Slider Mandante
        let r2 = document.getElementById('r2_' + id); // Slider Visitante
        
        let v1 = parseInt(r1.value);
        let v2 = parseInt(r2.value);

        // LÓGICA INTELIGENTE:
        // Se a soma passar de 100, diminui o outro time para caber.
        if (v1 + v2 > 100) {
            if (origem === 'mandante') {
                v2 = 100 - v1;
                r2.value = v2;
            } else {
                v1 = 100 - v2;
                r1.value = v1;
            }
        }

        // Calcula Empate (Resto)
        let vx = 100 - (v1 + v2);

        // Atualiza Textos
        document.getElementById('txt1_' + id).innerText = v1;
        document.getElementById('txt2_' + id).innerText = v2;
        document.getElementById('txtX_' + id).innerText = vx + '%';

        // Atualiza a Barra Colorida
        document.getElementById('bar1_' + id).style.width = v1 + '%';
        document.getElementById('barX_' + id).style.width = vx + '%';
        document.getElementById('bar2_' + id).style.width = v2 + '%';
    }
    </script>
    </body>
    </html>
    """
    return render_template_string(html, jogos=lista_jogos, modo=modo, opcoes=CONFIG_APOSTAS.keys(), msg=msg)

def render_resultado(df, modo):
    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
        <meta charset="utf-8"> <title>Resultado Loteca</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>body { background-color: #eef2f3; } .palpite-box { padding: 5px; border-radius: 5px; font-weight: bold; width:100%; display:block; }</style>
    </head>
    <body>
    <div class="container py-3">
        <div class="card shadow border-0">
            <div class="card-header bg-success text-white text-center py-3">
                <h3 class="mb-0">🎱 Palpites Gerados</h3>
                <small>{{ modo }}</small>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-striped text-center align-middle mb-0">
                        <thead class="table-dark small"><tr><th>#</th><th>Jogo</th><th>%</th><th>Palpite IA</th></tr></thead>
                        <tbody>
                            {% for i, row in df.iterrows() %}
                            <tr>
                                <td class="fw-bold">{{ row['Jogo'] }}</td>
                                <td><div class="small fw-bold">{{ row['Mandante'] }}<br><span class="text-danger">vs</span><br>{{ row['Visitante'] }}</div></td>
                                <td style="width:30%">
                                    <div class="progress" style="height: 6px;">
                                        <div class="progress-bar bg-primary" style="width:{{ row['Prob_Casa'] }}%"></div>
                                        <div class="progress-bar bg-warning" style="width:{{ row['Prob_Empate'] }}%"></div>
                                        <div class="progress-bar bg-danger" style="width:{{ row['Prob_Fora'] }}%"></div>
                                    </div>
                                    <small style="font-size:0.7rem">{{ row['Prob_Casa']|int }}/{{ row['Prob_Empate']|int }}/{{ row['Prob_Fora']|int }}</small>
                                </td>
                                <td><span class="{{ row['Classe_CSS'] }} palpite-box">{{ row['Palpite IA'] }}</span></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="card-footer text-center"><a href="/" class="btn btn-outline-dark w-100">🔄 Novo Cálculo</a></div>
        </div>
    </div>
    </body>
    </html>
    """
    return render_template_string(html, df=df, modo=modo)

if __name__ == '__main__':
    app.run(debug=True, port=10000)
