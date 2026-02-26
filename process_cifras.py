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
import requests
from PIL import Image
import io

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
    # Procura por "Tom: C" ou similar
    match = re.search(r'(?:tom|tonalidade|key)\s*[:=]\s*([A-G]#?b?)', texto, re.IGNORECASE)
    if match:
        tom = match.group(1).upper().replace('BB', 'B').replace('B', 'Bb')
        return tom if tom in ['C','C#','Db','D','D#','Eb','E','F','F#','Gb','G','G#','Ab','A','A#','Bb','B'] else 'C'
    
    # Senão pega o primeiro acorde plausível
    acordes_inicio = re.findall(r'\b([A-G]#?b?)(m|°|aug|dim|sus|add|maj|min|7|9|11|13)?\b', texto[:500], re.IGNORECASE)
    if acordes_inicio:
        return acordes_inicio[0][0].upper()
    return 'C'

def extrair_texto_do_arquivo(url):
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        content_type = response.headers.get('content-type', '').lower()
        content = response.content

        if 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' in content_type or url.endswith('.docx'):
            doc = Document(io.BytesIO(content))
            return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())

        elif 'pdf' in content_type or url.endswith('.pdf'):
            images = convert_from_bytes(content)
        else:  # imagem (jpg, png, etc)
            img = Image.open(io.BytesIO(content))
            images = [img]

        texto_completo = ''
        for img in images:
            texto_completo += pytesseract.image_to_string(img, lang='por+eng', config='--psm 6') + '\n\n'
        return texto_completo.strip()

    except Exception as e:
        return f"[ERRO AO EXTRAIR] {str(e)[:200]}"

# Processamento principal
rows = sheet.get_all_values()
processadas = set()

for idx, row in enumerate(rows[1:], start=2):  # pula cabeçalho
    if len(row) < 8:
        continue
    
    link_imagem = (row[7] or '').strip()  # Coluna H = índice 7
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
        texto_extraido = extrair_texto_do_arquivo(link_imagem)
        tom_original = detectar_tom_original(texto_extraido)

        ref = db.reference(f'cifras/{slug}')
        ref.set({
            'titulo': titulo,
            'artista': artista,
            'tom_original': tom_original,
            'cifra_original': texto_extraido,
            'url_original': link_imagem,
            'processado_em': str(os.getenv('GITHUB_RUN_NUMBER', 'manual'))
        })

        print(f"OK → {titulo} | {artista} | Tom: {tom_original} | Slug: {slug}")

    except Exception as e:
        print(f"Erro na linha {idx} ({titulo}): {str(e)}")

print(f"\nProcessamento finalizado. {len(processadas)} músicas processadas/atualizadas.")