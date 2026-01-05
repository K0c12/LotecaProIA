from flask import Flask, render_template_string, request
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import os
import time
from duckduckgo_search import DDGS

app = Flask(__name__)
ARQUIVO_ESCUDOS = 'escudos.json'

# --- SUAS CONFIGURAÇÕES DE APOSTA ---
CONFIG_APOSTAS = {
    "Econômico": {"duplos": 1, "triplos": 0},
    "Econômico Premium": {"duplos": 2, "triplos": 0},
    "Fortalecido": {"duplos": 3, "triplos": 0},
    "Arrojado": {"duplos": 0, "triplos": 1},
    "Profissional": {"duplos": 1, "triplos": 1},
    "Avançado": {"duplos": 2, "triplos": 1},
    "Expert": {"duplos": 0, "triplos": 2},
    "Master": {"duplos": 1, "triplos": 2},
    "Elite": {"duplos": 2, "triplos": 2},
    "Magnata": {"duplos": 0, "triplos": 3},
    "Dono da Zorra Toda": {"duplos": 3, "triplos": 3}
}

# --- FUNÇÕES DE SUPORTE (ESCUDOS E WEB) ---
def carregar_escudos():
    if os.path.exists(ARQUIVO_ESCUDOS):
        with open(ARQUIVO_ESCUDOS, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def salvar_escudos(dic_escudos):
    with open(ARQUIVO_ESCUDOS, 'w', encoding='utf-8') as f:
        json.dump(dic_escudos, f, indent=4, ensure_ascii=False)

def buscar_logo_web(nome_time):
    # (Mesma lógica anterior para economizar espaço na resposta)
    try:
        results = DDGS().images(keywords=f"escudo {nome_time} futebol png transparent", max_results=1)
        lista = list(results)
        if lista: return lista[0]['image']
    except: pass
    return "https://via.placeholder.com/40"

# --- LÓGICA DE INTELIGÊNCIA DO ROBÔ ---
def gerar_palpite(prob_casa, prob_empate, prob_fora, tipo_protecao):
    """
    Define o palpite baseando-se na proteção disponível (Triplo, Duplo ou Seco)
    """
    probs = {'1': prob_casa, 'X': prob_empate, '2': prob_fora}
    # Ordena as probabilidades para saber quem é favorito
    ordenado = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    fav_sigla = ordenado[0][0] # Ex: '1'
    vice_sigla = ordenado[1][0] # Ex: 'X'

    if tipo_protecao == "TRIPLO":
        return "1 X 2 (Qualquer um)", "bg-info" # Azul
    elif tipo_protecao == "DUPLO":
        # O duplo cobre o Favorito + o Segundo mais provável
        # Ordenamos as siglas para ficar bonito (ex: "1X" ou "X2" ou "1 2")
        palpite = "".join(sorted([fav_sigla, vice_sigla]))
        if palpite == "12": palpite = "1 2" # Aberto
        return f"Duplo {palpite}", "bg-warning" # Amarelo
    else:
        # Aposta Seca no Favorito
        return f"Coluna {fav_sigla}", "bg-success text-white" # Verde

def aplicar_estrategia(df, nome_estrategia):
    config = CONFIG_APOSTAS.get(nome_estrategia, CONFIG_APOSTAS["Econômico"])
    qtd_triplos = config['triplos']
    qtd_duplos = config['duplos']

    # 1. Calcular o "Nível de Risco" de cada jogo
    # Risco = 100 - probabilidade do favorito. Quanto maior, mais difícil o jogo.
    df['Risco'] = 100 - df[['Prob_Casa', 'Prob_Empate', 'Prob_Fora']].max(axis=1)

    # 2. Ordenar jogos pelo risco (do mais difícil para o mais fácil) para priorizar proteções
    # Criamos uma coluna temporária de prioridade
    df_sorted = df.sort_values(by='Risco', ascending=False).copy()
    indices_triplos = df_sorted.head(qtd_triplos).index
    
    # Remove os que ganharam triplo para ver quem ganha duplo
    restante = df_sorted.drop(indices_triplos)
    indices_duplos = restante.head(qtd_duplos).index

    # 3. Aplicar os palpites linha a linha
    sugestoes = []
    classes_css = []
    
    for idx in df.index:
        tipo = "SECO"
        if idx in indices_triplos:
            tipo = "TRIPLO"
        elif idx in indices_duplos:
            tipo = "DUPLO"
        
        palpite, css = gerar_palpite(df.at[idx, 'Prob_Casa'], df.at[idx, 'Prob_Empate'], df.at[idx, 'Prob_Fora'], tipo)
        sugestoes.append(palpite)
        classes_css.append(css)

    df['Palpite IA'] = sugestoes
    df['Classe_CSS'] = classes_css # Usado no HTML para colorir
    return df

# --- EXTRAÇÃO DE DADOS ---
def buscar_dados_vovoteca():
    # ... (Código de extração do Vovoteca igual ao anterior) ...
    # ... (Mas retornando colunas numéricas limpas: Prob_Casa, Prob_Empate, Prob_Fora) ...
    # Vou resumir aqui para focar na lógica da estratégia:
    url = "https://vovoteca.com/loteca-enquetes-secos-duplos/"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.content, 'html.parser')
    except: return pd.DataFrame()

    dados = []
    dic_escudos = carregar_escudos()
    houve_mudanca = False

    for i in range(1, 15):
        try:
            # (Lógica de scraping idêntica à anterior)
            linha = soup.find('tr', id=f'tr-linha-{i}')
            if not linha: continue
            
            cols = linha.find_all('td')
            mandante = cols[1].text.strip()
            visitante = cols[5].text.strip()
            idx = i - 1
            
            try:
                p1 = float(soup.find('td', id=f'resultado-{idx}-home').text.strip())
                px = float(soup.find('td', id=f'resultado-{idx}-middle').text.strip())
                p2 = float(soup.find('td', id=f'resultado-{idx}-away').text.strip())
            except: p1, px, p2 = 0.0, 0.0, 0.0

            # Escudos
            if mandante not in dic_escudos:
                dic_escudos[mandante] = buscar_logo_web(mandante)
                houve_mudanca = True
            if visitante not in dic_escudos:
                dic_escudos[visitante] = buscar_logo_web(visitante)
                houve_mudanca = True

            dados.append({
                "Jogo": i,
                "Img1": dic_escudos[mandante],
                "Mandante": mandante,
                "Prob_Casa": p1,
                "Prob_Empate": px,
                "Prob_Fora": p2,
                "Visitante": visitante,
                "Img2": dic_escudos[visitante]
            })
        except: continue
        
    if houve_mudanca: salvar_escudos(dic_escudos)
    return pd.DataFrame(dados)

# --- ROTA PRINCIPAL ---
@app.route('/')
def home():
    # 1. Pega a estratégia escolhida na URL (padrão: Econômico)
    modo_selecionado = request.args.get('modo', 'Econômico')
    
    # 2. Busca dados
    df = buscar_dados_vovoteca()
    if df.empty: return "Erro ao carregar dados do Vovoteca."

    # 3. Aplica a inteligência
    df_calculado = aplicar_estrategia(df, modo_selecionado)

    # 4. Renderiza HTML
    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #f4f7f6; font-family: 'Segoe UI', sans-serif; }
            .card-header { background-color: #2c3e50; color: white; }
            .img-time { width: 40px; height: 40px; object-fit: contain; }
            td { vertical-align: middle !important; }
            .prob-bar { height: 4px; background-color: #e9ecef; margin-top: 5px; }
            .prob-fill { height: 100%; background-color: #28a745; }
        </style>
    </head>
    <body>
    <div class="container py-4">
        <div class="card shadow">
            <div class="card-header text-center">
                <h3>🎱 Robô da Loteca Inteligente</h3>
                <p class="mb-0">Estratégia Atual: <strong>{{ modo }}</strong></p>
            </div>
            
            <div class="card-body bg-light">
                <form method="get" class="row g-3 justify-content-center align-items-center">
                    <div class="col-auto">
                        <label class="col-form-label fw-bold">Escolha seu Perfil:</label>
                    </div>
                    <div class="col-auto">
                        <select name="modo" class="form-select" onchange="this.form.submit()">
                            {% for nome in opcoes %}
                                <option value="{{ nome }}" {% if nome == modo %}selected{% endif %}>
                                    {{ nome }} ({{ configs[nome]['duplos'] }}D + {{ configs[nome]['triplos'] }}T)
                                </option>
                            {% endfor %}
                        </select>
                    </div>
                </form>
            </div>

            <div class="table-responsive">
                <table class="table table-hover table-striped text-center mb-0">
                    <thead class="table-dark">
                        <tr>
                            <th>JG</th>
                            <th>Mandante</th>
                            <th>Probabilidades (%)</th>
                            <th>Visitante</th>
                            <th>Sugestão do Robô</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for index, row in df.iterrows() %}
                        <tr>
                            <td class="fw-bold">{{ row['Jogo'] }}</td>
                            <td class="text-end">
                                {{ row['Mandante'] }} <img src="{{ row['Img1'] }}" class="img-time">
                            </td>
                            <td style="width: 25%;">
                                <div class="d-flex justify-content-between small text-muted">
                                    <span>{{ row['Prob_Casa'] }}</span>
                                    <span>{{ row['Prob_Empate'] }}</span>
                                    <span>{{ row['Prob_Fora'] }}</span>
                                </div>
                                <div class="progress" style="height: 6px;">
                                    <div class="progress-bar bg-success" role="progressbar" style="width: {{ row['Prob_Casa'] }}%"></div>
                                    <div class="progress-bar bg-warning" role="progressbar" style="width: {{ row['Prob_Empate'] }}%"></div>
                                    <div class="progress-bar bg-danger" role="progressbar" style="width: {{ row['Prob_Fora'] }}%"></div>
                                </div>
                            </td>
                            <td class="text-start">
                                <img src="{{ row['Img2'] }}" class="img-time"> {{ row['Visitante'] }}
                            </td>
                            <td class="{{ row['Classe_CSS'] }} fw-bold border">
                                {{ row['Palpite IA'] }}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            <div class="card-footer text-muted text-center small">
                Dados do Vovoteca | Escudos via DuckDuckGo | IA de Gerenciamento de Risco
            </div>
        </div>
    </div>
    </body>
    </html>
    """
    
    return render_template_string(html, 
                                  df=df_calculado, 
                                  modo=modo_selecionado, 
                                  opcoes=CONFIG_APOSTAS.keys(),
                                  configs=CONFIG_APOSTAS)

if __name__ == '__main__':
    app.run(debug=True)
