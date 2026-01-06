import cloudscraper
from bs4 import BeautifulSoup
import json
import requests
import urllib3

# Desabilita avisos de segurança
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NOME_ARQUIVO_DADOS = 'jogos.json'

# --- LISTA DE SEGURANÇA (CASO TUDO FALHE) ---
JOGOS_BACKUP = [
    {"Jogo": 1, "Mandante": "CORINTHIANS/SP", "Visitante": "PONTE PRETA/SP"},
    {"Jogo": 2, "Mandante": "JUVENTUDE/RS", "Visitante": "YPIRANGA/RS"},
    {"Jogo": 3, "Mandante": "SANTOS/SP", "Visitante": "NOVORIZONTINO/SP"},
    {"Jogo": 4, "Mandante": "CRUZEIRO/MG", "Visitante": "POUSO ALEGRE/MG"},
    {"Jogo": 5, "Mandante": "PORT DESPORT/SP", "Visitante": "PALMEIRAS/SP"},
    {"Jogo": 6, "Mandante": "AVENIDA/RS", "Visitante": "GREMIO/RS"},
    {"Jogo": 7, "Mandante": "SAO LUIZ/RS", "Visitante": "CAXIAS/RS"},
    {"Jogo": 8, "Mandante": "BAHIA/BA", "Visitante": "JEQUIE BA/BA"},
    {"Jogo": 9, "Mandante": "INTERNACIONAL/RS", "Visitante": "NOVO HAMBURGO/RS"},
    {"Jogo": 10, "Mandante": "ATLETICO/MG", "Visitante": "BETIM/MG"},
    {"Jogo": 11, "Mandante": "FERROVIARIO/CE", "Visitante": "FORTALEZA/CE"},
    {"Jogo": 12, "Mandante": "NOROESTE/SP", "Visitante": "BRAGANTINO/SP"},
    {"Jogo": 13, "Mandante": "FLAMENGO/RJ", "Visitante": "PORTUGUESA/RJ"},
    {"Jogo": 14, "Mandante": "MIRASSOL/SP", "Visitante": "SAO PAULO/SP"}
]

def buscar_vovoteca():
    print("⏳ Tentando Vovoteca...")
    url = "https://vovoteca.com/loteca-enquetes-secos-duplos/"
    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(url, timeout=15)
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
                p2 = float(soup.find('td', id=f'resultado-{idx}-away').text.strip().replace('%','').replace(',','.'))
                px = 100 - (p1 + p2)
            except: p1, px, p2 = 33, 34, 33

            dados.append({"Jogo": i, "Mandante": mandante, "Visitante": visitante, "Prob_Casa": p1, "Prob_Empate": px, "Prob_Fora": p2})
            contagem += 1
        
        if contagem < 14: return None
        return dados, "Vovoteca (Automático)"
    except Exception as e:
        print(f"Erro Vovoteca: {e}")
        return None

def buscar_caixa():
    print("⏳ Tentando Caixa...")
    url = "https://loterias.caixa.gov.br/Paginas/Programacao-Loteca.aspx"
    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(url, timeout=15)
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
                        dados.append({"Jogo": int(jogo_num), "Mandante": mandante, "Visitante": visitante, "Prob_Casa": 33, "Prob_Empate": 34, "Prob_Fora": 33})
                except: continue
        if len(dados) < 14: return None
        return dados, "Caixa (Nomes Oficiais)"
    except Exception as e:
        print(f"Erro Caixa: {e}")
        return None

def executar_coleta():
    # 1. Tenta Vovoteca
    resultado = buscar_vovoteca()
    
    # 2. Se falhar, tenta Caixa
    if not resultado:
        resultado = buscar_caixa()
    
    # 3. Se falhar tudo, usa Backup
    if not resultado:
        print("⚠️ Falha total na internet. Usando Backup Local.")
        dados_finais = []
        for jogo in JOGOS_BACKUP:
            d = jogo.copy()
            d["Prob_Casa"], d["Prob_Empate"], d["Prob_Fora"] = 33, 34, 33
            dados_finais.append(d)
        fonte = "Backup Offline"
    else:
        dados_finais, fonte = resultado

    # SALVA NO ARQUIVO JSON
    pacote = {
        "fonte": fonte,
        "jogos": dados_finais
    }
    
    with open(NOME_ARQUIVO_DADOS, 'w', encoding='utf-8') as f:
        json.dump(pacote, f, indent=4, ensure_ascii=False)
    
    print(f"✅ SUCESSO! Dados salvos em '{NOME_ARQUIVO_DADOS}' usando fonte: {fonte}")

if __name__ == "__main__":
    executar_coleta()