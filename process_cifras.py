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
        # Ajuste automático para Postimg: adiciona ?dl=1 para download direto
        if 'postimg.cc' in url.lower() or 'i.postimg.cc' in url.lower():
            if '?dl=1' not in url and '&dl=1' not in url:
                if '?' in url:
                    url += '&dl=1'
                else:
                    url += '?dl=1'
            print(f"Link Postimg ajustado para download direto: {url}")

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, timeout=30, headers=headers, allow_redirects=True, stream=True)

        print(f"Status do download: {response.status_code} | URL final: {response.url}")
        print(f"Content-Type recebido: {response.headers.get('Content-Type', 'desconhecido')}")
        print(f"Tamanho do content: {len(response.content)} bytes")

        if response.status_code != 200:
            return f"[ERRO Download] Status {response.status_code} - {response.text[:200]}"

        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk

        # Detecta se veio HTML de erro/preview
        try:
            content_preview = content[:2000].decode('utf-8', errors='ignore').lower()
            if '<html' in content_preview or 'postimg' in content_preview or 'download original image' in content_preview or 'couldn\'t preview' in content_preview:
                return "[ERRO] Recebido página HTML de preview em vez da imagem direta. Verifique se o link é raw/direct."
        except:
            pass

        # Tenta abrir como imagem
        file_io = io.BytesIO(content)
        try:
            img = Image.open(file_io)
            texto = pytesseract.image_to_string(img, lang='por+eng', config='--psm 6')
            return texto.strip() or "[Imagem baixada, mas nenhum texto detectado]"
        except Exception as img_err:
            print(f"Erro ao abrir como imagem: {str(img_err)}")
            # Tenta como PDF (caso raro)
            file_io.seek(0)
            if b'%PDF' in content[:10]:
                images = convert_from_bytes(content)
                texto = ''
                for img in images:
                    texto += pytesseract.image_to_string(img, lang='por+eng') + '\n\n'
                return texto.strip()
            else:
                return f"[ERRO] Não é imagem/PDF válido: {str(img_err)} - Tamanho: {len(content)} bytes"

    except requests.exceptions.RequestException as req_err:
        return f"[ERRO de rede] {str(req_err)}"
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