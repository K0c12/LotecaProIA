from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import json
import os
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

@app.route('/atualizar_agora')
def forcar_atualizacao():
    try:
        executar_coleta()
        return redirect(url_for('home'))
    except Exception as e: return f"Erro: {e}"

@app.route('/', methods=['GET', 'POST'])
def home():
    modo = request.args.get('modo', 'Econômico')

    if request.method == 'POST':
        modo = request.form.get('modo_selecionado')
        dados_form = []
        for i in range(1, 15):
            mandante = request.form.get(f'time1_{i}')
            visitante = request.form.get(f'time2_{i}')
            # Agora pegamos os 3 valores diretos dos sliders
            p1 = float(request.form.get(f'range1_{i}'))
            px = float(request.form.get(f'rangex_{i}'))
            p2 = float(request.form.get(f'range2_{i}'))
            
            # Garante soma 100 no backend também por segurança
            total = p1 + px + p2
            if total == 0: total = 1 # evita div zero
            p1 = (p1 / total) * 100
            px = (px / total) * 100
            p2 = (p2 / total) * 100

            dados_form.append({"Jogo": i, "Mandante": mandante, "Visitante": visitante, "Prob_Casa": p1, "Prob_Empate": px, "Prob_Fora": p2})
        df_final = aplicar_estrategia(pd.DataFrame(dados_form), modo)
        return render_resultado(df_final, modo)

    dados_lista, fonte = carregar_dados_do_arquivo()
    
    lista_jogos_sliders = []
    if dados_lista:
        for row in dados_lista:
            lista_jogos_sliders.append({
                "Mandante": row['Mandante'], "Visitante": row['Visitante'],
                "p1": int(row['Prob_Casa']), "p2": int(row['Prob_Fora']), "px": int(row['Prob_Empate'])
            })
    else:
        # Dados padrão caso arquivo esteja vazio (34-33-33)
        lista_jogos_sliders = [{"Mandante": "Time A", "Visitante": "Time B", "p1": 34, "px": 33, "p2": 33} for _ in range(14)]
        
    return render_manual(modo, lista_jogos_sliders, fonte)

def render_manual(modo, jogos, fonte):
    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
        <meta charset="utf-8"> <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Loteca IA - Ajuste Fino</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #eef2f3; font-family: 'Segoe UI', sans-serif; }
            .card-game { background: white; border-radius: 15px; padding: 20px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
            .btn-refresh { position: fixed; bottom: 20px; right: 20px; z-index: 1000; border-radius: 50px; padding: 15px 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
            
            /* --- CSS DOS SLIDERS VERTICAIS (Adaptado do seu modelo) --- */
            .slider-container {
                display: flex;
                justify-content: space-around;
                align-items: flex-end;
                height: 250px;
                padding-top: 40px;
            }
            .range-wrapper {
                position: relative;
                width: 60px;
                height: 100%;
                text-align: center;
            }
            .range-label {
                position: absolute;
                top: -35px;
                left: 50%;
                transform: translateX(-50%);
                font-weight: bold;
                font-size: 1.1rem;
                color: #555;
            }
            .range-slider {
                display: inline-block;
                width: 60px;
                height: 100%;
                position: relative;
            }
            /* Input Range Escondido mas Funcional */
            .range-slider input[type=range] {
                position: absolute;
                left: 0; bottom: 0;
                width: 100%; height: 100%;
                margin: 0;
                opacity: 0;
                cursor: pointer;
                z-index: 3;
                -webkit-appearance: slider-vertical; /* Importante para mobile */
            }
            
            /* Barra de Fundo */
            .range-slider:after {
                content: "";
                position: absolute;
                bottom: 0; left: 15px; /* Centralizar (60-30)/2 */
                width: 30px;
                height: 100%;
                background-color: #e9ecef;
                border-radius: 30px;
                z-index: 0;
            }
            
            /* Barra Colorida Dinâmica */
            .range-slider__bar {
                position: absolute;
                bottom: 0; left: 15px;
                width: 30px;
                border-radius: 0 0 30px 30px;
                z-index: 1;
                pointer-events: none;
                transition: height 0.1s ease-out;
            }
            
            /* Botão (Thumb) Circular */
            .range-slider__thumb {
                position: absolute;
                left: 5px; /* (60-50)/2 */
                width: 50px; height: 50px;
                background: white;
                border-radius: 50%;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                z-index: 2;
                pointer-events: none;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                font-weight: bold;
                color: #555;
                transition: bottom 0.1s ease-out;
            }

            /* Cores Específicas */
            .casa .range-slider__bar { background: linear-gradient(to top, #198754, #20c997); }
            .empate .range-slider__bar { background: linear-gradient(to top, #ffc107, #ffca2c); }
            .fora .range-slider__bar { background: linear-gradient(to top, #dc3545, #ff6b6b); }
            
            .team-name { font-size: 1rem; font-weight: bold; margin-top: 10px; display: block; height: 40px; line-height: 1.2; }
        </style>
    </head>
    <body>
    
    <a href="/atualizar_agora" class="btn btn-primary btn-refresh fw-bold">🔄 Atualizar</a>

    <div class="container py-3">
        <div class="alert alert-info text-center shadow-sm">
            📊 <strong>Distribuição de Probabilidades (Soma 100%)</strong><br>
            Arraste qualquer barra e as outras se ajustam proporcionalmente!
        </div>
        
        <form method="POST" action="/">
            <div class="card mb-4 bg-dark text-white text-center p-3">
                <label class="fw-bold">Estratégia:</label>
                <select name="modo_selecionado" class="form-select text-center fw-bold mt-1">
                    {% for n in opcoes %}
                    <option value="{{ n }}" {% if n == modo %}selected{% endif %}>{{ n }}</option>
                    {% endfor %}
                </select>
            </div>

            {% for jogo in jogos %}
            <div class="card-game" id="jogo_{{ loop.index }}">
                <div class="text-center mb-3">
                    <span class="badge bg-secondary mb-2">JOGO {{ loop.index }}</span>
                    <input type="hidden" name="time1_{{ loop.index }}" value="{{ jogo.Mandante }}">
                    <input type="hidden" name="time2_{{ loop.index }}" value="{{ jogo.Visitante }}">
                </div>

                <div class="slider-container">
                    <div class="range-wrapper casa">
                        <span class="range-label" id="lbl1_{{ loop.index }}">{{ jogo.p1 }}%</span>
                        <div class="range-slider">
                            <input type="range" orient="vertical" min="0" max="100" value="{{ jogo.p1 }}" 
                                   name="range1_{{ loop.index }}" id="r1_{{ loop.index }}" 
                                   oninput="updateProporcional({{ loop.index }}, 'p1')">
                            <div class="range-slider__bar" id="bar1_{{ loop.index }}"></div>
                            <div class="range-slider__thumb" id="thumb1_{{ loop.index }}">{{ jogo.p1 }}</div>
                        </div>
                        <span class="team-name text-success">{{ jogo.Mandante }}</span>
                    </div>

                    <div class="range-wrapper empate">
                        <span class="range-label" id="lblx_{{ loop.index }}">{{ jogo.px }}%</span>
                        <div class="range-slider">
                            <input type="range" orient="vertical" min="0" max="100" value="{{ jogo.px }}" 
                                   name="rangex_{{ loop.index }}" id="rx_{{ loop.index }}" 
                                   oninput="updateProporcional({{ loop.index }}, 'px')">
                            <div class="range-slider__bar" id="barx_{{ loop.index }}"></div>
                            <div class="range-slider__thumb" id="thumbx_{{ loop.index }}">X</div>
                        </div>
                        <span class="team-name text-warning">Empate</span>
                    </div>

                    <div class="range-wrapper fora">
                        <span class="range-label" id="lbl2_{{ loop.index }}">{{ jogo.p2 }}%</span>
                        <div class="range-slider">
                            <input type="range" orient="vertical" min="0" max="100" value="{{ jogo.p2 }}" 
                                   name="range2_{{ loop.index }}" id="r2_{{ loop.index }}" 
                                   oninput="updateProporcional({{ loop.index }}, 'p2')">
                            <div class="range-slider__bar" id="bar2_{{ loop.index }}"></div>
                            <div class="range-slider__thumb" id="thumb2_{{ loop.index }}">{{ jogo.p2 }}</div>
                        </div>
                        <span class="team-name text-danger">{{ jogo.Visitante }}</span>
                    </div>
                </div>
            </div>
            {% endfor %}

            <div class="d-grid pb-5">
                <button type="submit" class="btn btn-success btn-lg fw-bold shadow p-3">🎲 CALCULAR PALPITES</button>
            </div>
        </form>
    </div>

    <script>
    // Inicializa a posição visual das barras ao carregar
    document.addEventListener("DOMContentLoaded", function() {
        for(let i=1; i<=14; i++) {
            visualUpdate(i, 'p1'); visualUpdate(i, 'px'); visualUpdate(i, 'p2');
        }
    });

    function visualUpdate(id, type) {
        let suffix = type === 'p1' ? '1' : type === 'px' ? 'x' : '2';
        let input = document.getElementById('r' + suffix + '_' + id);
        let bar = document.getElementById('bar' + suffix + '_' + id);
        let thumb = document.getElementById('thumb' + suffix + '_' + id);
        let label = document.getElementById('lbl' + suffix + '_' + id);
        
        let val = parseInt(input.value);
        
        // Atualiza altura da barra e posição do botão
        bar.style.height = val + '%';
        thumb.style.bottom = val + '%';
        thumb.style.marginBottom = '-25px'; // Metade da altura do thumb para centralizar
        
        // Atualiza texto
        label.innerText = val + '%';
        if (suffix !== 'x') thumb.innerText = val; // Mostra número no thumb (exceto Empate que fica X)
    }

    function updateProporcional(id, changedType) {
        // Elementos
        let el1 = document.getElementById('r1_' + id);
        let elx = document.getElementById('rx_' + id);
        let el2 = document.getElementById('r2_' + id);

        let v1 = parseInt(el1.value);
        let vx = parseInt(elx.value);
        let v2 = parseInt(el2.value);

        let changedVal = parseInt(document.getElementById(changedType.replace('p1','r1').replace('px','rx').replace('p2','r2') + '_' + id).value);
        let resto = 100 - changedVal;

        // Se o valor mudado for 100, zera os outros
        if (resto <= 0) {
            if(changedType === 'p1') { elx.value = 0; el2.value = 0; }
            if(changedType === 'px') { el1.value = 0; el2.value = 0; }
            if(changedType === 'p2') { el1.value = 0; elx.value = 0; }
        } else {
            // Distribuição Proporcional
            let totalOutros = 0;
            if(changedType === 'p1') totalOutros = vx + v2;
            if(changedType === 'px') totalOutros = v1 + v2;
            if(changedType === 'p2') totalOutros = v1 + vx;

            if (totalOutros === 0) {
                // Se os outros eram 0, divide o resto igualmente
                let metade = Math.floor(resto / 2);
                if(changedType === 'p1') { elx.value = metade; el2.value = resto - metade; }
                if(changedType === 'px') { el1.value = metade; el2.value = resto - metade; }
                if(changedType === 'p2') { el1.value = metade; elx.value = resto - metade; }
            } else {
                // Regra de 3 para manter a proporção
                if(changedType === 'p1') {
                    elx.value = Math.round((vx / totalOutros) * resto);
                    el2.value = resto - parseInt(elx.value); // O último pega a sobra pra fechar 100
                }
                if(changedType === 'px') {
                    el1.value = Math.round((v1 / totalOutros) * resto);
                    el2.value = resto - parseInt(el1.value);
                }
                if(changedType === 'p2') {
                    el1.value = Math.round((v1 / totalOutros) * resto);
                    elx.value = resto - parseInt(el1.value);
                }
            }
        }

        // Atualiza visual de todos
        visualUpdate(id, 'p1');
        visualUpdate(id, 'px');
        visualUpdate(id, 'p2');
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
                                        <div class="progress-bar bg-success" style="width:{{ row['Prob_Casa'] }}%"></div>
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
