from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import json
import os
from coleta import executar_coleta 

app = Flask(__name__)
NOME_ARQUIVO_DADOS = 'jogos.json'

# --- 1. CONFIGURAÇÕES ---
CONFIG_APOSTAS = {
    "Econômico":          {"duplos": 1, "triplos": 0, "valor": 4.00},
    "Fortalecido":        {"duplos": 3, "triplos": 0, "valor": 16.00},
    "Profissional":       {"duplos": 1, "triplos": 1, "valor": 12.00},
    "Magnata":            {"duplos": 0, "triplos": 6, "valor": 1458.00},
    "Dono da Zorra Toda": {"duplos": 5, "triplos": 3, "valor": 1728.00}
}

# Gabarito de Segurança (Offline)
DEFAULTS_GABARITO = {
    1:  {"p1": 70, "px": 20, "p2": 10, "dica": ""},
    2:  {"p1": 45, "px": 10, "p2": 45, "dica": "Caça-Zebra: Tendência aberta"},
    3:  {"p1": 50, "px": 25, "p2": 25, "dica": "⚠️ Risco #1: Favorito costuma tropeçar!"},
    4:  {"p1": 50, "px": 35, "p2": 15, "dica": "Cuidado com empate (31%)"},
    5:  {"p1": 65, "px": 20, "p2": 15, "dica": ""},
    6:  {"p1": 60, "px": 25, "p2": 15, "dica": ""},
    7:  {"p1": 60, "px": 20, "p2": 20, "dica": ""},
    8:  {"p1": 55, "px": 25, "p2": 20, "dica": "⚠️ Risco #4: Visitante surpreende"},
    9:  {"p1": 50, "px": 30, "p2": 20, "dica": "⚠️ Risco #2: Crítico para Zebras"},
    10: {"p1": 70, "px": 20, "p2": 10, "dica": ""},
    11: {"p1": 55, "px": 25, "p2": 20, "dica": "⚠️ Risco #3: Jogo muito equilibrado"},
    12: {"p1": 65, "px": 20, "p2": 15, "dica": ""},
    13: {"p1": 80, "px": 15, "p2": 5,  "dica": "Super Favorito"},
    14: {"p1": 33, "px": 34, "p2": 33, "dica": "Jogo de Triplo (Equilíbrio Total)"}
}

# --- 2. FUNÇÕES LÓGICAS ---
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
    
    if tipo == "TRIPLO": 
        return "TRIPLO (1 X 2)", "bg-primary text-white border-primary"
    elif tipo == "DUPLO":
        palpite = "".join(sorted([fav, vice])).replace('12', '1 2')
        return f"DUPLO {palpite}", "bg-warning text-dark border-warning"
    else: 
        return f"COLUNA {fav}", "bg-success text-white border-success"

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

# --- 3. ROTAS DO SITE ---
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
            p1 = float(request.form.get(f'range1_{i}'))
            px = float(request.form.get(f'rangex_{i}'))
            p2 = float(request.form.get(f'range2_{i}'))
            
            total = p1 + px + p2
            if total == 0: total = 1
            p1 = (p1 / total) * 100
            px = (px / total) * 100
            p2 = (p2 / total) * 100

            dados_form.append({"Jogo": i, "Mandante": mandante, "Visitante": visitante, "Prob_Casa": p1, "Prob_Empate": px, "Prob_Fora": p2})
        df_final = aplicar_estrategia(pd.DataFrame(dados_form), modo)
        
        # Renderiza RESULTADO
        val_total = CONFIG_APOSTAS.get(modo, CONFIG_APOSTAS['Econômico'])['valor']
        return render_template_string(HTML_RESULTADO, df=df_final, modo=modo, valor=val_total)

    # Renderiza MANUAL
    dados_lista, fonte = carregar_dados_do_arquivo()
    
    if "Vovoteca" not in fonte: 
        times_backup = [
            ("CORINTHIANS/SP", "PONTE PRETA/SP"), ("JUVENTUDE/RS", "YPIRANGA/RS"),
            ("SANTOS/SP", "NOVORIZONTINO/SP"), ("CRUZEIRO/MG", "POUSO ALEGRE/MG"),
            ("PORT DESPORT/SP", "PALMEIRAS/SP"), ("AVENIDA/RS", "GREMIO/RS"),
            ("SAO LUIZ/RS", "CAXIAS/RS"), ("BAHIA/BA", "JEQUIE BA/BA"),
            ("INTERNACIONAL/RS", "NOVO HAMBURGO/RS"), ("ATLETICO/MG", "BETIM/MG"),
            ("FERROVIARIO/CE", "FORTALEZA/CE"), ("NOROESTE/SP", "BRAGANTINO/SP"),
            ("FLAMENGO/RJ", "PORTUGUESA/RJ"), ("MIRASSOL/SP", "SAO PAULO/SP")
        ]
        dados_lista = []
        for i, (mand, vis) in enumerate(times_backup, 1):
            padrao = DEFAULTS_GABARITO.get(i, {"p1":33, "px":34, "p2":33, "dica":""})
            dados_lista.append({
                "Jogo": i, "Mandante": mand, "Visitante": vis,
                "Prob_Casa": padrao["p1"], "Prob_Empate": padrao["px"], "Prob_Fora": padrao["p2"]
            })
        fonte = "Gabarito Offline (Editável)"

    lista_jogos_sliders = []
    for row in dados_lista:
        idx = int(row['Jogo'])
        dica = DEFAULTS_GABARITO.get(idx, {}).get("dica", "")
        lista_jogos_sliders.append({
            "Jogo": idx,
            "Mandante": row['Mandante'], "Visitante": row['Visitante'],
            "p1": int(row['Prob_Casa']), "p2": int(row['Prob_Fora']), "px": int(row['Prob_Empate']),
            "dica": dica
        })
        
    return render_template_string(HTML_MANUAL, jogos=lista_jogos_sliders, modo=modo, configs=CONFIG_APOSTAS, fonte=fonte)

# --- 4. TEMPLATES HTML (FICAM NO FINAL PARA NÃO ATRAPALHAR) ---

HTML_MANUAL = """
<!doctype html>
<html lang="pt-br" data-bs-theme="dark">
<head>
    <meta charset="utf-8"> <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Loteca Pro IA</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background: #121212; font-family: 'Segoe UI', sans-serif; padding-top: 80px; color: #e0e0e0; }
        .navbar-custom { position: fixed; top: 0; left: 0; width: 100%; z-index: 1000; background: #1f1f1f; box-shadow: 0 4px 12px rgba(0,0,0,0.5); padding: 12px 0; border-bottom: 1px solid #333; }
        .card-game { background: #1e1e1e; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid #333; }
        .team-box { width: 42%; text-align: center; font-weight: 700; font-size: 0.95rem; color: #ffffff; text-shadow: 0 1px 2px rgba(0,0,0,0.5); }
        .vs-badge { background: #333; color: #aaa; padding: 4px 8px; border-radius: 8px; font-size: 0.75rem; font-weight: bold; border: 1px solid #444; }
        .risk-alert { font-size: 0.8rem; background: #2c1515; color: #ff8b8b; padding: 10px; border-radius: 6px; margin-top: 15px; border-left: 3px solid #e53e3e; display: flex; align-items: center; gap: 8px; }
        .slider-row { display: flex; justify-content: space-between; gap: 10px; height: 160px; align-items: flex-end; padding: 0 10px; }
        .slider-col { position: relative; width: 30%; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; }
        .custom-range { -webkit-appearance: slider-vertical; width: 100%; height: 100%; opacity: 0; position: absolute; bottom: 0; z-index: 5; cursor: pointer; }
        .bar-bg { width: 10px; height: 100%; background: #333; border-radius: 10px; position: absolute; bottom: 0; z-index: 1; border: 1px solid #444; }
        .bar-fill { width: 10px; border-radius: 10px; position: absolute; bottom: 0; z-index: 2; transition: height 0.15s ease-out; box-shadow: 0 0 10px rgba(0,0,0,0.5); }
        .thumb-val { width: 36px; height: 36px; background: #2d2d2d; border-radius: 50%; box-shadow: 0 2px 5px rgba(0,0,0,0.5); border: 2px solid; position: absolute; z-index: 3; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.75rem; pointer-events: none; transition: bottom 0.15s ease-out; margin-bottom: -18px; color: #fff; }
        .casa .bar-fill { background: linear-gradient(to top, #198754, #2ecc71); } .casa .thumb-val { border-color: #2ecc71; color: #2ecc71; }
        .empate .bar-fill { background: linear-gradient(to top, #d39e00, #f1c40f); } .empate .thumb-val { border-color: #f1c40f; color: #f1c40f; }
        .fora .bar-fill { background: linear-gradient(to top, #c0392b, #e74c3c); } .fora .thumb-val { border-color: #e74c3c; color: #e74c3c; }
        .lbl-top { margin-bottom: auto; font-size: 0.75rem; font-weight: bold; color: #888; text-transform: uppercase; letter-spacing: 1px; }
    </style>
</head>
<body>
<div class="navbar-custom">
    <div class="container d-flex justify-content-between">
        <div class="d-flex align-items-center gap-2">
            <i class="fa-solid fa-robot text-success fs-4"></i>
            <h5 class="m-0 fw-bold text-white">Loteca Pro IA <small class="text-secondary ms-2">v8.0</small></h5>
        </div>
        <a href="/atualizar_agora" class="btn btn-sm btn-outline-light fw-bold rounded-pill px-3"><i class="fa-solid fa-sync-alt me-1"></i> Atualizar</a>
    </div>
</div>
<div class="container">
    <form method="POST" action="/">
        <div class="card border-0 shadow-sm mb-4" style="background: #252525; border-radius: 16px; border: 1px solid #333;">
            <div class="card-body text-center p-4">
                <label class="text-uppercase text-secondary fw-bold" style="font-size: 0.75rem; letter-spacing: 1px;">Estratégia & Orçamento</label>
                <div class="d-flex justify-content-center mt-2">
                    <select name="modo_selecionado" class="form-select form-select-lg text-center fw-bold border-0 shadow-sm" style="max-width: 400px; border-radius: 12px; background: #333; color: #fff;">
                        {% for n, c in configs.items() %}
                        <option value="{{ n }}" {% if n == modo %}selected{% endif %}>{{ n }} • R$ {{ "%.2f"|format(c['valor'])|replace('.', ',') }}</option>
                        {% endfor %}
                    </select>
                </div>
            </div>
        </div>
        <div class="row">
        {% for jogo in jogos %}
            <div class="col-md-6 col-lg-4">
                <div class="card-game">
                    <div class="d-flex justify-content-between mb-3">
                        <span class="badge bg-dark border border-secondary text-secondary">{{ jogo.Jogo }}</span>
                        {% if jogo.dica %}<i class="fa-solid fa-circle-exclamation text-warning" title="Risco"></i>{% endif %}
                    </div>
                    <div class="game-header">
                        <div class="team-box text-start">{{ jogo.Mandante }}</div>
                        <div class="vs-badge">VS</div>
                        <div class="team-box text-end">{{ jogo.Visitante }}</div>
                        <input type="hidden" name="time1_{{ jogo.Jogo }}" value="{{ jogo.Mandante }}">
                        <input type="hidden" name="time2_{{ jogo.Jogo }}" value="{{ jogo.Visitante }}">
                    </div>
                    <div class="slider-row">
                        <div class="slider-col casa">
                            <div class="lbl-top">Casa</div>
                            <input type="range" class="custom-range" min="0" max="100" value="{{ jogo.p1 }}" name="range1_{{ jogo.Jogo }}" id="r1_{{ jogo.Jogo }}" oninput="upd({{ jogo.Jogo }}, 'p1')">
                            <div class="bar-bg"></div><div class="bar-fill" id="bar1_{{ jogo.Jogo }}"></div><div class="thumb-val" id="thumb1_{{ jogo.Jogo }}">{{ jogo.p1 }}</div>
                        </div>
                        <div class="slider-col empate">
                            <div class="lbl-top">X</div>
                            <input type="range" class="custom-range" min="0" max="100" value="{{ jogo.px }}" name="rangex_{{ jogo.Jogo }}" id="rx_{{ jogo.Jogo }}" oninput="upd({{ jogo.Jogo }}, 'px')">
                            <div class="bar-bg"></div><div class="bar-fill" id="barx_{{ jogo.Jogo }}"></div><div class="thumb-val" id="thumbx_{{ jogo.Jogo }}">{{ jogo.px }}</div>
                        </div>
                        <div class="slider-col fora">
                            <div class="lbl-top">Fora</div>
                            <input type="range" class="custom-range" min="0" max="100" value="{{ jogo.p2 }}" name="range2_{{ jogo.Jogo }}" id="r2_{{ jogo.Jogo }}" oninput="upd({{ jogo.Jogo }}, 'p2')">
                            <div class="bar-bg"></div><div class="bar-fill" id="bar2_{{ jogo.Jogo }}"></div><div class="thumb-val" id="thumb2_{{ jogo.Jogo }}">{{ jogo.p2 }}</div>
                        </div>
                    </div>
                    {% if jogo.dica %}
                    <div class="risk-alert"><i class="fa-solid fa-triangle-exclamation"></i> {{ jogo.dica }}</div>
                    {% endif %}
                </div>
            </div>
        {% endfor %}
        </div>
        <div class="d-grid pb-5 mt-3">
            <button type="submit" class="btn btn-success btn-lg fw-bold shadow py-3 rounded-pill text-uppercase"><i class="fa-solid fa-wand-magic-sparkles me-2"></i> Calcular Palpites</button>
        </div>
    </form>
</div>
<script>
document.addEventListener("DOMContentLoaded", () => { for(let i=1; i<=14; i++) { visUpd(i, 'p1'); visUpd(i, 'px'); visUpd(i, 'p2'); } });
function visUpd(id, type) {
    let s = type==='p1'?'1':type==='px'?'x':'2';
    let val = document.getElementById('r'+s+'_'+id).value;
    document.getElementById('bar'+s+'_'+id).style.height = val+'%';
    document.getElementById('thumb'+s+'_'+id).style.bottom = val+'%';
    document.getElementById('thumb'+s+'_'+id).innerText = val;
}
function upd(id, type) {
    let el1=document.getElementById('r1_'+id), elx=document.getElementById('rx_'+id), el2=document.getElementById('r2_'+id);
    let v1=parseInt(el1.value), vx=parseInt(elx.value), v2=parseInt(el2.value);
    let changed = parseInt(document.getElementById(type.replace('p1','r1').replace('px','rx').replace('p2','r2')+'_'+id).value);
    let resto = 100 - changed;
    if(resto<=0) {
        if(type==='p1'){elx.value=0;el2.value=0} if(type==='px'){el1.value=0;el2.value=0} if(type==='p2'){el1.value=0;elx.value=0}
    } else {
        let tot = (type==='p1'?vx+v2 : type==='px'?v1+v2 : v1+vx);
        if(tot===0) {
            let m = Math.floor(resto/2);
            if(type==='p1'){elx.value=m;el2.value=resto-m} if(type==='px'){el1.value=m;el2.value=resto-m} if(type==='p2'){el1.value=m;elx.value=resto-m}
        } else {
            if(type==='p1'){elx.value=Math.round((vx/tot)*resto);el2.value=resto-parseInt(elx.value)}
            if(type==='px'){el1.value=Math.round((v1/tot)*resto);el2.value=resto-parseInt(el1.value)}
            if(type==='p2'){el1.value=Math.round((v1/tot)*resto);elx.value=resto-parseInt(el1.value)}
        }
    }
    visUpd(id,'p1');visUpd(id,'px');visUpd(id,'p2');
}
</script>
</body>
</html>
"""

HTML_RESULTADO = """
<!doctype html>
<html lang="pt-br" data-bs-theme="dark">
<head>
    <meta charset="utf-8"> <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background: #121212; color: #eee; font-family: 'Segoe UI'; }
        .tag { padding: 8px; border-radius: 8px; font-weight: 800; display: block; width: 100%; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; color: #000; }
        .card { background: #1e1e1e; border: 1px solid #333; }
        .table-dark-custom { --bs-table-bg: #1e1e1e; --bs-table-color: #eee; --bs-table-border-color: #333; }
    </style>
</head>
<body>
<div class="container py-4">
    <div class="card shadow border-0" style="border-radius:16px; overflow:hidden;">
        <div class="card-header bg-success text-white text-center py-4">
            <h3 class="mb-0 fw-bold"><i class="fa-solid fa-check-circle me-2"></i>Palpites Gerados</h3>
            <div class="badge bg-dark mt-2 px-3 py-2 fs-6 border border-secondary">
                {{ modo }} • Custo Estimado: R$ {{ "%.2f"|format(valor)|replace('.', ',') }}
            </div>
        </div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-dark-custom table-hover text-center align-middle mb-0">
                    <thead class="table-secondary small text-dark"><tr><th>#</th><th>Jogo</th><th>Probabilidades</th><th>Palpite Final</th></tr></thead>
                    <tbody>
                        {% for i, row in df.iterrows() %}
                        <tr>
                            <td class="fw-bold text-secondary">{{ row['Jogo'] }}</td>
                            <td><div class="small fw-bold">{{ row['Mandante'] }}<br><span class="text-secondary" style="font-size:0.7rem;">x</span><br>{{ row['Visitante'] }}</div></td>
                            <td style="width: 30%;">
                                <div class="progress" style="height:8px; border-radius:4px; background: #333;">
                                    <div class="progress-bar bg-success" style="width:{{ row['Prob_Casa'] }}%"></div>
                                    <div class="progress-bar bg-warning" style="width:{{ row['Prob_Empate'] }}%"></div>
                                    <div class="progress-bar bg-danger" style="width:{{ row['Prob_Fora'] }}%"></div>
                                </div>
                                <div class="d-flex justify-content-between mt-1" style="font-size: 0.65rem; color:#aaa;">
                                    <span>{{ row['Prob_Casa']|int }}%</span><span>{{ row['Prob_Empate']|int }}%</span><span>{{ row['Prob_Fora']|int }}%</span>
                                </div>
                            </td>
                            <td><span class="{{ row['Classe_CSS'] }} tag shadow-sm">{{ row['Palpite IA'] }}</span></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        <div class="card-footer p-3 bg-dark border-top border-secondary">
            <a href="/" class="btn btn-outline-light w-100 fw-bold rounded-pill"><i class="fa-solid fa-rotate-left me-2"></i> Refazer Palpites</a>
        </div>
    </div>
</div>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=True, port=10000)
