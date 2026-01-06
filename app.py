from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import json
import os
from coleta import executar_coleta 

app = Flask(__name__)
NOME_ARQUIVO_DADOS = 'jogos.json'

# --- CONFIGURAÇÃO COM PREÇOS ---
CONFIG_APOSTAS = {
    "Econômico":          {"duplos": 1, "triplos": 0, "valor": 4.00},
    "Fortalecido":        {"duplos": 3, "triplos": 0, "valor": 16.00},
    "Profissional":       {"duplos": 1, "triplos": 1, "valor": 12.00},
    "Magnata":            {"duplos": 0, "triplos": 6, "valor": 1458.00},
    "Dono da Zorra Toda": {"duplos": 5, "triplos": 3, "valor": 1728.00}
}

# --- DADOS DO GABARITO (Inteligência Offline) ---
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
        return render_resultado(df_final, modo)

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
        
    return render_manual(modo, lista_jogos_sliders, fonte)

def render_manual(modo, jogos, fonte):
    html = """
    <!doctype html>
    <html lang="pt-br" data-bs-theme="dark">
    <head>
        <meta charset="utf-8"> <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Loteca Pro IA</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            /* TEMA DARK CUSTOMIZADO */
            body { background: #121212; font-family: 'Segoe UI', sans-serif; padding-top: 80px; color: #e0e0e0; }
            
            /* Navbar Escura */
            .navbar-custom { position: fixed; top: 0; left: 0; width: 100%; z-index: 1000; background: #1f1f1f; box-shadow: 0 4px 12px rgba(0,0,0,0.5); padding: 12px 0; border-bottom: 1px solid #333; }
            
            /* Cards Escuros */
            .card-game { background: #1e1e1e; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid #333; transition: transform 0.2s; }
            .card-game:hover { transform: translateY(-2px); border-color: #444; }

            /* Textos e Badges */
            .team-box { width: 42%; text-align: center; font-weight: 700; font-size: 0.95rem; color: #ffffff; text-shadow: 0 1px 2px rgba(0,0,0,0.5); }
            .vs-badge { background: #333; color: #aaa; padding: 4px 8px; border-radius: 8px; font-size: 0.75rem; font-weight: bold; border: 1px solid #444; }
            
            /* Dica Alert (Dark) */
            .risk-alert { font-size: 0.8rem; background: #2c1515; color: #ff8b8b; padding: 10px; border-radius: 6px; margin-top: 15px; border-left: 3px solid #e53e3e; display: flex; align-items: center; gap: 8px; }

            /* SLIDERS DARK MODE */
            .slider-row { display: flex; justify-content: space-between; gap: 10px; height: 160px; align-items: flex-end; padding: 0 10px; }
            .slider-col { position: relative; width: 30%; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; }
            
            .custom-range {
                -webkit-appearance: slider-vertical;
                width: 100%; height: 100%;
                opacity: 0; position: absolute; bottom: 0; z-index: 5; cursor: pointer;
            }
            
            /* Fundo da Barra (Cinza Escuro) */
            .bar-bg { width: 10px; height: 100%; background: #333; border-radius: 10px; position: absolute; bottom: 0; z-index: 1; border: 1px solid #444; }
            
            /* Preenchimento Colorido Brilhante */
            .bar-fill { width: 10px; border-radius: 10px; position: absolute; bottom: 0; z-index: 2; transition: height 0.15s ease-out; box-shadow: 0 0 10px rgba(0,0,0,0.5); }
            
            /* Thumb (Bolinha Dark) */
            .thumb-val {
                width: 36px; height: 36px; background: #2d2d2d; border-radius: 50%;
                box-shadow: 0 2px 5px rgba(0,0,0,0.5); border: 2px solid;
                position: absolute; z-index: 3;
                display: flex; align-items: center; justify-content: center;
                font-weight: 800; font-size: 0.75rem; pointer-events: none;
                transition: bottom 0.15s ease-out; margin-bottom: -18px; color: #fff;
            }
            
            .casa .bar-fill { background: linear-gradient(to top, #198754, #2ecc71); } 
            .casa .thumb-val { border-color: #2ecc71; color: #2ecc71
