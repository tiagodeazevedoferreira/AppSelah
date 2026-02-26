import gspread
from google.oauth2.service_account import Credentials
import firebase_admin
from firebase_admin import credentials, db
import re
import os
import json
from unidecode import unidecode
import pytesseract
from pdf2image import convert_from_bytes
from docx import Document
from PIL import Image
import io
import requests

# Configurações fixas
SHEET_ID = '1OuMaJ-nyFujxE-QNoZCE8iyaPEmRfJLHWr5DfevX6cc'
ABA_NOME = 'Musicas'
FIREBASE_URL = 'https://appmusicasimosp-default-rtdb.firebaseio.com/'

# Inicializa Firebase
cred_dict = json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT_JSON'])
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})

# Acesso à planilha
scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
creds = Credentials.from_service_account_info(cred_dict, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).worksheet(ABA_NOME)

def gerar_slug(titulo, artista):
    text = f"{titulo} {artista}".lower().strip()
    text = unidecode(text)
    text = re.sub(r'[^a-z0-9 ]', '', text)
    text = re.sub(r'\s+', '-', text)
    return text or 'sem-titulo'

def detectar_tom_original(texto):
    match = re.search(r'(?:tom|tonalidade|key)\s*[:=]\s*([A-G]#?b?)', texto, re.IGNORECASE)
    if match:
        tom = match.group(1).upper().replace('BB', 'B').replace('B', 'Bb')
        return tom if tom in ['C','C#','Db','D','D#','Eb','E','F','F#','Gb','G','G#','Ab','A','A#','Bb','B'] else None
    
    acordes_inicio = re.findall(r'\b([A-G]#?b?)(m|°|aug|dim|sus|add|maj|min|7|9|11|13)?\b', texto[:500], re.IGNORECASE)
    if acordes_inicio:
        return acordes_inicio[0][0].upper()
    return None

# Biblioteca de correções (vamos adicionar mais conforme erros aparecerem)
def corrigir_acorde(acorde):
    correcoes = {
        'DIFE': 'D/F#',
        'DI FE': 'D/F#',
        'D IFE': 'D/F#',
        'Fim': 'F#m',
        'Fam': 'F#m',
        'Fame': 'F#m',
        'F#m D': 'F#m/D',
        'Fame D': 'F#m/D',
        'F#M': 'F#m',
        'rn': 'm',
        'I': '/',
        'l': '/',
        ' | ': '/',
        'E#': '#',  # contexto F#m, Bb
    }
    for errado, correto in correcoes.items():
        acorde = acorde.replace(errado, correto)
    return acorde.strip()

def extrair_texto_do_arquivo(url):
    try:
        # Ajuste Postimg
        if 'postimg.cc' in url.lower():
            if '?dl=1' not in url:
                url += '&dl=1' if '?' in url else '?dl=1'

        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=30, headers=headers, allow_redirects=True)

        if response.status_code != 200:
            return {"erro": f"Status {response.status_code}"}

        content = response.content

        # Detecta HTML
        preview = content[:1000].decode('utf-8', errors='ignore').lower()
        if '<html' in preview or 'postimg' in preview or 'download original' in preview:
            return {"erro": "HTML de preview detectado"}

        file_io = io.BytesIO(content)
        img = Image.open(file_io)

        # Tentativas múltiplas de OCR
        configs = [
            '--psm 6 --oem 3',  # bloco de texto uniforme
            '--psm 4 --oem 3',  # linha única
            '--psm 3 --oem 3'   # totalmente automático
        ]

        texto_bruto = ''
        for config in configs:
            texto = pytesseract.image_to_string(img, lang='por+eng', config=config)
            if len(texto.strip()) > 50:  # mínimo para considerar válido
                texto_bruto = texto
                break

        if not texto_bruto.strip():
            return {"erro": "Nenhum texto detectado após tentativas"}

        # Corrige acordes no texto bruto
        texto_bruto = '\n'.join([re.sub(r'\b([A-G]#?b?m?[\d/]*)\b', lambda x: corrigir_acorde(x.group(0)), linha) for linha in texto_bruto.split('\n')])

        # Parsing estruturado
        linhas = texto_bruto.split('\n')
        cifra_parseada = []
        for i, linha in enumerate(linhas, 1):
            if not linha.strip():
                continue

            # Tenta separar acordes (linhas superiores) e letra
            acordes_raw = re.findall(r'\b([A-G]#?b?m?[\d/]*)\b', linha)
            letra = re.sub(r'\b[A-G]#?b?m?[\d/]*\b', '', linha).strip()

            acordes = []
            posicao_atual = 0
            for acorde in acordes_raw:
                posicao = linha.find(acorde, posicao_atual)
                acordes.append({
                    "acorde": corrigir_acorde(acorde),
                    "posicao": posicao
                })
                posicao_atual = posicao + len(acorde)

            cifra_parseada.append({
                "linha": i,
                "acordes": acordes,
                "letra": letra
            })

        return cifra_parseada

    except Exception as e:
        return {"erro": str(e)[:200]}

# Processamento principal
rows = sheet.get_all_values()
processadas = set()

for idx, row in enumerate(rows[1:], start=2):
    if len(row) < 8:
        continue
    
    link_imagem = (row[7] or '').strip()
    if not link_imagem:
        continue

    titulo = (row[0] or '').strip()
    artista = (row[1] or '').strip()
    if not titulo:
        continue

    slug = gerar_slug(titulo, artista)
    if slug in processadas:
        print(f"Duplicata ignorada: {titulo} - {artista}")
        continue
    processadas.add(slug)

    try:
        resultado = extrair_texto_do_arquivo(link_imagem)
        if "erro" in resultado:
            cifra_parseada = []
            tom_original = None
            texto_fallback = resultado["erro"]
        else:
            cifra_parseada = resultado
            texto_fallback = '\n'.join([f"{' '.join([a['acorde'] for a in l['acordes']])} {l['letra']}" for l in cifra_parseada])
            tom_original = detectar_tom_original(texto_fallback) or '?'

        ref = db.reference(f'cifras/{slug}')
        ref.set({
            'titulo': titulo,
            'artista': artista,
            'tom_original': tom_original,
            'cifra_parseada': cifra_parseada,
            'url_original': link_imagem,
            'processado_em': str(os.getenv('GITHUB_RUN_NUMBER', 'manual'))
        })

        print(f"OK → {titulo} | {artista} | Tom: {tom_original} | Slug: {slug}")

    except Exception as e:
        print(f"Erro na linha {idx} ({titulo}): {str(e)}")

print(f"\nProcessamento finalizado. {len(processadas)} músicas processadas/atualizadas.")