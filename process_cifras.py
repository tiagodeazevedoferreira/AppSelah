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
        return tom if tom in ['C','C#','Db','D','D#','Eb','E','F','F#','Gb','G','G#','Ab','A','A#','Bb','B'] else None
    
    # Primeiro acorde plausível
    acordes_inicio = re.findall(r'\b([A-G]#?b?)(m|°|aug|dim|sus|add|maj|min|7|9|11|13)?\b', texto[:500], re.IGNORECASE)
    if acordes_inicio:
        return acordes_inicio[0][0].upper()
    return None

# Pós-processamento simples para erros comuns do OCR
def corrigir_acorde_ocr(acorde):
    correcoes = {
        'Fim': 'F#m',
        'Fam': 'F#m',
        'Fame': 'F#m',
        'F#m D': 'F#m/D',
        'DIFE': 'D/F#',
        'D IFE': 'D/F#',
        'DI FE': 'D/F#',
        'F#M': 'F#m',
        'F# m': 'F#m',
        'Bb': 'A#',  # ou Bb se preferir manter
        'rn': 'm',   # rn comum para m
    }
    for errado, correto in correcoes.items():
        acorde = acorde.replace(errado, correto)
    # Corrige / virando I ou l
    acorde = acorde.replace('I', '/').replace('l', '/').replace(' | ', '/')
    return acorde.strip()

def extrair_texto_do_arquivo(url):
    try:
        # Ajuste para Postimg (dl=1)
        if 'postimg.cc' in url.lower() or 'i.postimg.cc' in url.lower():
            if '?dl=1' not in url and '&dl=1' not in url:
                url += '&dl=1' if '?' in url else '?dl=1'

        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=30, headers=headers, allow_redirects=True)

        if response.status_code != 200:
            return {"erro": f"Status {response.status_code}"}

        content = response.content

        # Detecta HTML indesejado
        preview = content[:1000].decode('utf-8', errors='ignore').lower()
        if '<html' in preview or 'postimg' in preview or 'download original' in preview:
            return {"erro": "HTML de preview detectado"}

        file_io = io.BytesIO(content)
        try:
            img = Image.open(file_io)
            texto_bruto = pytesseract.image_to_string(img, lang='por+eng', config='--psm 6 --oem 3')
        except:
            # Tenta PDF
            file_io.seek(0)
            if b'%PDF' in content[:10]:
                images = convert_from_bytes(content)
                texto_bruto = ''
                for img in images:
                    texto_bruto += pytesseract.image_to_string(img, lang='por+eng', config='--psm 6 --oem 3') + '\n\n'
            else:
                return {"erro": "Não é imagem/PDF válido"}

        # Corrige acordes comuns no texto bruto
        linhas = texto_bruto.split('\n')
        cifra_parseada = []
        for linha in linhas:
            if not linha.strip():
                continue
            # Tenta separar acordes e letra (simples: acordes em linha superior)
            acordes = re.findall(r'\b([A-G]#?b?m?[\d/]*)', linha)
            letra = re.sub(r'\b[A-G]#?b?m?[\d/]*\b', '', linha).strip()
            acordes_corrigidos = [corrigir_acorde_ocr(a) for a in acordes if a.strip()]
            cifra_parseada.append({
                "acordes": acordes_corrigidos,
                "letra": letra
            })

        return cifra_parseada if cifra_parseada else {"erro": "Nenhum texto detectado"}

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
            texto_extraido = resultado["erro"]
            tom_original = None
            cifra_parseada = []
        else:
            cifra_parseada = resultado
            texto_bruto = '\n'.join([f"{' '.join(l['acordes'])} {l['letra']}" for l in cifra_parseada])
            tom_original = detectar_tom_original(texto_bruto) or '?'
            texto_extraido = texto_bruto  # fallback bruto

        ref = db.reference(f'cifras/{slug}')
        ref.set({
            'titulo': titulo,
            'artista': artista,
            'tom_original': tom_original,
            'cifra_original': texto_extraido,  # fallback
            'cifra_parseada': cifra_parseada,  # estrutura nova
            'url_original': link_imagem,
            'processado_em': str(os.getenv('GITHUB_RUN_NUMBER', 'manual'))
        })

        print(f"OK → {titulo} | {artista} | Tom: {tom_original or '?'} | Slug: {slug}")

    except Exception as e:
        print(f"Erro na linha {idx} ({titulo}): {str(e)}")

print(f"\nProcessamento finalizado. {len(processadas)} músicas processadas/atualizadas.")