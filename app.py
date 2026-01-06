from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import json
import os
# IMPORTA A FUNÇÃO DO OUTRO ARQUIVO
from coleta import executar_coleta 

app = Flask(__name__)
NOME_ARQUIVO_DADOS = 'jogos.json'

CONFIG_APOSTAS = {
    "Econômico":          {"duplos": 1, "triplos": 0},
    "Fortalecido":        {"duplos": 3, "triplos": 0},
    "Profissional":       {"duplos": 1, "triplos": 1},
    "Magnata":            {"duplos": 0, "triplos": 6},
    "Dono da Zorra Toda": {"duplos": 5, "triplos": 3}
}

def carregar_dados_do_arquivo():
    if not os.path.exists(NOME_ARQUIVO_DADOS):
        return [], "Sem dados. Clique em Atualizar!"
    try:
        with open(NOME_ARQUIVO_DADOS, 'r', encoding='utf-8') as f:
            pacote = json.load(f)
            return pacote['jogos'], pacote['fonte']
    except: return [], "Erro no arquivo."

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

# --- NOVA ROTA PARA O BOTÃO ---
@app.route('/atualizar_agora')
def forcar_atualizacao():
    try:
        print("🔄 Iniciando atualização solicitada pelo usuário...")
        executar_coleta() # Chama o script coleta.py
        return redirect(url_for('home')) # Volta para a home recarregada
    except Exception as e:
        return f"Erro ao atualizar: {e}"

@app.route('/', methods=['GET', 'POST'])
def home():
    modo = request.args.get('modo', 'Econômico')

    if request.method == 'POST':
        modo = request.form.get('modo_selecionado')
        dados_form = []
        for i in range(1, 15):
            mandante = request.form.get(f'time1_{i}')
            visitante = request.form.get(f'time2_{i}')
            p1 = float(request.form.get(f'range1_{i}'))
            p2 = float(request.form.get(f'range2_{i}'))
            px = 100 - (p1 + p2)
            if px < 0: px = 0
            dados_form.append({"Jogo": i, "Mandante": mandante, "Visitante": visitante, "Prob_Casa": p1, "Prob_Empate": px, "Prob_Fora": p2})
        df_final = aplicar_estrategia(pd.DataFrame(dados_form), modo)
        return render_resultado(df_final, modo)

    dados_lista, fonte = carregar_dados_do_arquivo()
    if not dados_lista: fonte = "Nenhum dado encontrado"

    lista_jogos_sliders = []
    for row in dados_lista:
        lista_jogos_sliders.append({
            "Mandante": row['Mandante'], "Visitante": row['Visitante'],
            "p1": int(row['Prob_Casa']), "p2": int(row['Prob_Fora']), "px": int(row['Prob_Empate'])
        })
        
    return render_manual(modo, lista_jogos_sliders, fonte)

def render_manual(modo, jogos, fonte):
    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
        <meta charset="utf-8"> <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Loteca IA</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #eef2f3; font-family: sans-serif; }
            .card-game { background: white; border-radius: 12px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
            input[type=range] { width: 100%; cursor: pointer; }
            .btn-refresh { position: fixed; bottom: 20px; right: 20px; z-index: 1000; border-radius: 50px; padding: 15px 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
        </style>
    </head>
    <body>
    
    <a href="/atualizar_agora" class="btn btn-primary btn-refresh fw-bold">
        🔄 Atualizar Dados
    </a>

    <div class="container py-3">
        <div class="alert alert-success text-center shadow-sm">
            📁 <strong>Fonte: {{ fonte }}</strong><br>
            Ajuste as barras ou clique em Calcular!
        </div>
        
        <form method="POST" action="/">
            <div class="card mb-3 bg-dark text-white text-center p-3">
                <label class="fw-bold">Estratégia:</label>
                <select name="modo_selecionado" class="form-select text-center fw-bold mt-1">
                    {% for n in opcoes %}
                    <option value="{{ n }}" {% if n == modo %}selected{% endif %}>{{ n }}</option>
                    {% endfor %}
                </select>
            </div>

            {% for jogo in jogos %}
            <div class="card-game">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="badge bg-secondary">{{ loop.index }}</span>
                    <div class="w-100 text-center">
                        <input type="hidden" name="time1_{{ loop.index }}" value="{{ jogo.Mandante }}">
                        <input type="hidden" name="time2_{{ loop.index }}" value="{{ jogo.Visitante }}">
                        <span class="fw-bold text-primary">{{ jogo.Mandante }}</span> 
                        <span class="small text-muted fw-bold">vs</span> 
                        <span class="fw-bold text-danger">{{ jogo.Visitante }}</span>
                    </div>
                </div>
                <div class="row g-2 align-items-center">
                    <div class="col-12">
                        <div class="d-flex justify-content-between small">
                            <span>Vitória Casa</span> <span class="text-primary fw-bold"><span id="t1_{{ loop.index }}">{{ jogo.p1 }}</span>%</span>
                        </div>
                        <input type="range" class="form-range" min="0" max="100" value="{{ jogo.p1 }}" 
                               name="range1_{{ loop.index }}" id="r1_{{ loop.index }}" oninput="att({{ loop.index }}, 'casa')">
                    </div>
                    <div class="col-12">
                        <div class="d-flex justify-content-between small">
                            <span>Vitória Fora</span> <span class="text-danger fw-bold"><span id="t2_{{ loop.index }}">{{ jogo.p2 }}</span>%</span>
                        </div>
                        <input type="range" class="form-range" min="0" max="100" value="{{ jogo.p2 }}" 
                               name="range2_{{ loop.index }}" id="r2_{{ loop.index }}" oninput="att({{ loop.index }}, 'fora')">
                    </div>
                </div>
                <div class="mt-2 text-center bg-light rounded p-1">
                    <small class="text-muted fw-bold">Empate: <span id="tx_{{ loop.index }}" class="text-warning">{{ jogo.px }}%</span></small>
                    <div class="progress" style="height: 10px;">
                        <div class="progress-bar bg-primary" id="b1_{{ loop.index }}" style="width: {{ jogo.p1 }}%"></div>
                        <div class="progress-bar bg-warning" id="bx_{{ loop.index }}" style="width: {{ jogo.px }}%"></div>
                        <div class="progress-bar bg-danger" id="b2_{{ loop.index }}" style="width: {{ jogo.p2 }}%"></div>
                    </div>
                </div>
            </div>
            {% endfor %}

            <div class="d-grid pb-5">
                <button type="submit" class="btn btn-success btn-lg fw-bold shadow">🎲 CALCULAR AGORA</button>
            </div>
        </form>
    </div>

    <script>
    function att(id, origem) {
        let r1 = document.getElementById('r1_' + id);
        let r2 = document.getElementById('r2_' + id);
        let v1 = parseInt(r1.value);
        let v2 = parseInt(r2.value);
        if (v1 + v2 > 100) { if (origem === 'casa') { v2 = 100 - v1; r2.value = v2; } else { v1 = 100 - v2; r1.value = v1; } }
        let vx = 100 - (v1 + v2);
        document.getElementById('t1_' + id).innerText = v1;
        document.getElementById('t2_' + id).innerText = v2;
        document.getElementById('tx_' + id).innerText = vx + '%';
        document.getElementById('b1_' + id).style.width = v1 + '%';
        document.getElementById('bx_' + id).style.width = vx + '%';
        document.getElementById('b2_' + id).style.width = v2 + '%';
    }
    </script>
    </body>
    </html>
    """
    return render_template_string(html, jogos=jogos, modo=modo, opcoes=CONFIG_APOSTAS.keys(), fonte=fonte)

def render_resultado(df, modo):
    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
        <meta charset="utf-8"> <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>body{background:#eef2f3}.tag{padding:5px;border-radius:5px;font-weight:bold;display:block;width:100%}</style>
    </head>
    <body>
    <div class="container py-3">
        <div class="card shadow border-0">
            <div class="card-header bg-success text-white text-center">
                <h3 class="mb-0">🎱 Palpites Prontos</h3>
                <small>{{ modo }}</small>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-striped text-center align-middle mb-0">
                        <thead class="table-dark small"><tr><th>#</th><th>Jogo</th><th>%</th><th>Palpite</th></tr></thead>
                        <tbody>
                            {% for i, row in df.iterrows() %}
                            <tr>
                                <td class="fw-bold">{{ row['Jogo'] }}</td>
                                <td><div class="small fw-bold">{{ row['Mandante'] }}<br><span class="text-danger">vs</span><br>{{ row['Visitante'] }}</div></td>
                                <td>
                                    <div class="progress" style="height:6px">
                                        <div class="progress-bar bg-primary" style="width:{{ row['Prob_Casa'] }}%"></div>
                                        <div class="progress-bar bg-warning" style="width:{{ row['Prob_Empate'] }}%"></div>
                                        <div class="progress-bar bg-danger" style="width:{{ row['Prob_Fora'] }}%"></div>
                                    </div>
                                    <small style="font-size:0.7rem">{{ row['Prob_Casa']|int }}/{{ row['Prob_Empate']|int }}/{{ row['Prob_Fora']|int }}</small>
                                </td>
                                <td><span class="{{ row['Classe_CSS'] }} tag">{{ row['Palpite IA'] }}</span></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="card-footer"><a href="/" class="btn btn-outline-dark w-100">🔄 Voltar</a></div>
        </div>
    </div>
    </body>
    </html>
    """
    return render_template_string(html, df=df, modo=modo)

if __name__ == '__main__':
    app.run(debug=True, port=10000)
