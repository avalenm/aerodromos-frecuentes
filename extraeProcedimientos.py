import os
import re
import requests
import time
from bs4 import BeautifulSoup
from dateutil.parser import parse
import datetime
from io import BytesIO
from dotenv import load_dotenv
from notifica import send_telegram
import pdfplumber

load_dotenv()

API_URL     = os.getenv('API_URL', 'http://194.238.26.6:3639')
SCRAPER_KEY = os.getenv('SCRAPER_API_KEY', '')


header = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36"
}

def get(url, intentos=3, espera=5):
    for intento in range(1, intentos + 1):
        try:
            return requests.get(url, headers=header, timeout=20)
        except requests.exceptions.RequestException as e:
            print(f"  Intento {intento}/{intentos} fallido para {url}: {e}")
            if intento < intentos:
                time.sleep(espera)
    raise requests.exceptions.ConnectionError(f"No se pudo conectar a {url} tras {intentos} intentos")


_NOISE_TOKENS = [
    '121.', '118.', '119.', '125.', '128.',  # frecuencias
    '°S ', '°N ', '°E ', '°W ',              # coordenadas
    'CAMBIO:', 'FT/NM', 'Altitud', 'Transition',
    'DASA', 'AIS-MAP', 'No se ajusta', 'Not to scale',
    'SECCION', 'SECCIÓN',
]


def _is_noise(line):
    """Devuelve True si la línea claramente no es un título de cartilla."""
    if not line or len(line) < 4:
        return True
    if any(p in line for p in _NOISE_TOKENS):
        return True
    # Comienza con minúscula → fragmento de texto arrastrado, no un título
    if line[0].islower():
        return True
    # Solo números, unidades y símbolos — incluye ′ (U+2032, prime de aviación)
    if re.match(r"^[\d\s'′\.\°\-/\(\)]{1,15}$", line):
        return True
    # Nivel de vuelo: FL210, FL100
    if re.match(r'^FL\s*\d+$', line, re.IGNORECASE):
        return True
    # Código de Q-route: Q-815, Q-103
    if re.match(r'^[A-Z]-\d+$', line):
        return True
    # Identificación de aeródromo: "CIUDAD - AD NOMBRE" o "CIUDAD - AP NOMBRE"
    if re.search(r'.{3,}\s*[-–]\s*(?:AD|AP)\b', line, re.IGNORECASE):
        return True
    # Formato altitud+rumbo: "3500' HDG", "10000 FT", "020°"
    if re.search(r"\d+['′°]\s*(HDG|FT|NM|MSA)?$", line, re.IGNORECASE):
        return True
    return False


def _is_type_code(text):
    """Retorna True si el texto es solo un código de tipo (IAC1, SID 4, STAR12, etc.)
    sin información adicional — indica extracción fallida."""
    return bool(re.match(r'^(?:IAC|SID|STAR|MRVA)\s*\d+$', text.strip(), re.IGNORECASE))


def _has_valid_content(text):
    """Retorna True si el título contiene al menos uno de:
    - Un waypoint ICAO (5 letras + dígito): EROLO 2A, PAMES 1, ANDES 1
    - Un tipo de nav aid: ILS, VOR, NDB, RNP, RNAV, LOC
    Los títulos válidos SIEMPRE cumplen una de estas condiciones.
    """
    if re.search(r'\b[A-Z]{5}\s+\d', text):
        return True
    if re.search(r'\b(?:ILS|VOR|NDB|RNP|RNAV|LOC|LLZ|GPS|GLS)\b', text, re.IGNORECASE):
        return True
    return False


def _defragment(line):
    """Para líneas con texto fragmentado (dígitos sueltos), extrae el nombre del
    procedimiento que suele aparecer al final: ej. '4 0 2 -V /U2 0 3 -L/U ANDES 1' → 'ANDES 1'.
    Retorna None si no encuentra nada aprovechable.
    """
    if sum(1 for w in line.split() if re.match(r'^\d$', w)) < 3:
        return None  # No es texto fragmentado
    # Busca 4+ letras mayúsculas seguidas de número al final de la línea
    m = re.search(r'([A-Z]{4,}(?:\s+[A-Z]{4,})*\s+\d[A-Z]?)$', line.rstrip())
    return m.group(1).strip() if m else None


def _navaid_title(line):
    """Si la línea mezcla nombre de ciudad/aeropuerto + tipo de procedimiento,
    extrae solo el tipo (ej: 'CONCEPCION - CHILE ILS Y RWY 02' → 'ILS Y RWY 02').
    Si no hay prefijo reconocible, devuelve la línea completa.
    """
    # Prefijo de ciudad antes de tipo de nav aid (ILS/VOR/etc.)
    m = re.search(r'((?:ILS|VOR|NDB|LOC|LLZ|RNAV|GPS|GLS|RNP)\b.*)', line, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Prefijo de ciudad/fragmento antes de waypoint ICAO de 5 letras
    # Ej: "TEMUCO LIXAN 3G/..." → "LIXAN 3G/...", "U OPURA 5C/..." → "OPURA 5C/..."
    m2 = re.match(r'^[A-Z]{1,10}\s+([A-Z]{5}\s+\d.*)', line)
    if m2:
        return m2.group(1).strip()
    return line


def _clean_title(titulo):
    """Elimina prefijos de ruido conocidos del título extraído."""
    # "CHART KIDEM..." o "HART KIDEM..." provienen del texto del header del chart
    for prefix in ('CHART ', 'HART '):
        if titulo.upper().startswith(prefix):
            titulo = titulo[len(prefix):]
    # Prefijo de 1-6 letras antes de tipo de nav aid
    # ej: "LE VOR" → "VOR", "CHILE ILS" → "ILS", "HILE ILS" → "ILS"
    titulo = re.sub(
        r'^[A-Z]{1,6}\s+(?=(?:ILS|VOR|NDB|RNP|RNAV|LOC|LLZ|GPS|GLS|SID|STAR)\b)',
        '', titulo, flags=re.IGNORECASE
    )
    # Asteriscos y guiones al inicio: "* VUMIT 2N/..." → "VUMIT 2N/..."
    titulo = re.sub(r'^\s*[\*\-]+\s*', '', titulo)
    # Fragmentos numéricos/decimales al inicio: "04 FAMEL" → "FAMEL", ".1 EROLO" → "EROLO"
    titulo = re.sub(r'^[\d\.]+\s+(?=[A-Z])', '', titulo)
    # Fragmento de palabra en minúsculas al inicio: "ción TIMDA" → "TIMDA"
    titulo = re.sub(r'^[a-záéíóúñ]+\s+', '', titulo)
    return titulo.strip()


def extraeTitulo(content, aerodromo_code, fallback):
    """Extrae el título real de la cartilla desde el PDF.

    Busca la línea que contiene el código ICAO y evalúa tanto la línea
    siguiente (SID/STAR/IAC RNAV: título está abajo) como la anterior
    (ILS/cartas complejas: el título aparece antes del código en el stream PDF).
    Combina dos líneas si el título está partido (termina en '/').
    """
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            page = pdf.pages[0]
            w, h = page.width, page.height

            pattern = re.compile(r'\b' + re.escape(aerodromo_code.upper()) + r'\b')

            # Tres pasadas: lado derecho → full-width normal → full-width con crop amplio
            # Landscape 13%, portrait 25% (o 40% en última pasada)
            passes = [
                (0.35, 0.13 if w > h else 0.25),
                (0.0,  0.13 if w > h else 0.25),
                (0.0,  0.13 if w > h else 0.40),
            ]

            for x0_frac, header_pct in passes:
                x0 = min(w * x0_frac, w - 1)
                y1 = max(h * header_pct, 1)
                bbox = (x0, 0, w, y1)
                text = page.crop(bbox).extract_text()
                if not text:
                    continue

                lines = [l.strip() for l in text.split('\n') if l.strip()]

                for i, line in enumerate(lines):
                    if not pattern.search(line.upper()):
                        continue

                    candidate = None

                    # Opción A: título en la línea siguiente (SID/STAR/IAC RNAV)
                    if i + 1 < len(lines) and not _is_noise(lines[i + 1]):
                        candidate = _navaid_title(lines[i + 1])
                        # Texto fragmentado (ej: "4 0 2 -V /U2 0 3 ANDES 1") → rescatar cola útil
                        defrag = _defragment(candidate)
                        if defrag:
                            candidate = defrag
                        # Título partido en 2 líneas (SID con muchos waypoints)
                        elif candidate.endswith('/') and i + 2 < len(lines) and not _is_noise(lines[i + 2]):
                            candidate = candidate + lines[i + 2]

                    # Opción B: título en la línea anterior (ILS/cartas con header-tabla)
                    if (not candidate or _is_noise(candidate) or len(candidate) < 5) and i > 0:
                        prev = lines[i - 1]
                        if not _is_noise(prev):
                            prev_candidate = _navaid_title(prev)
                            if not _is_noise(prev_candidate) and len(prev_candidate) >= 5:
                                candidate = prev_candidate

                    if candidate and len(candidate) >= 5:
                        cleaned = _clean_title(candidate)
                        if not (cleaned and len(cleaned) >= 5 and not _is_noise(cleaned)):
                            break
                        if _is_type_code(cleaned):
                            break
                        # Para IAC/SID/STAR el título debe contener waypoint (5 letras) o nav aid
                        is_procedure = bool(re.match(
                            r'^(?:IAC|SID|STAR|MRVA)', fallback, re.IGNORECASE))
                        if is_procedure and not _has_valid_content(cleaned):
                            break
                        return cleaned

                    break  # Solo procesamos la primera ocurrencia del código ICAO

            return fallback

    except Exception as e:
        print(f"  Error extrayendo título PDF: {e}")

    return fallback


def scrapeProcedimientos(fechaHoy):
    """Devuelve (procedimientos, errores, offline)."""
    print(fechaHoy)
    totalPdfs = 0
    offline = 0
    procedimientos = []
    errores = []

    for i in range(0, 2):
        url = 'https://aipchile.dgac.gob.cl/aip/vol2/seccion/proc/pagina/0' + format(i)
        html = get(url)
        estado = html.status_code
        if estado == 200:
            soup = BeautifulSoup(html.text, 'html.parser').find_all('a')
            for link in soup:
                url = link.get('href')
                url = url.replace(" ", "%20")
                txt = url.split("/")
                if len(txt) > 7:
                    if txt[7].find("MRVAC") == 0:
                        inicio = "MRVA"
                    else:
                        inicio = ""
                    tipo_codigo = inicio + txt[7][4:-4]
                    if txt[7].find("cond.aprox.ifr") == 0:
                        tipo_codigo = "Cond. Aprox. IFR"
                    tipo_codigo = tipo_codigo.replace("%20", " ").strip()

                    if len(txt[6]) == 4:
                        try:
                            myfile = get(url)
                            dt = parse(myfile.headers['Last-Modified'])
                            fechaHora = dt.strftime("%Y-%m-%d %H:%M:%S")

                            titulo = extraeTitulo(myfile.content, txt[6], tipo_codigo)
                            print(f"  {txt[6]} {tipo_codigo} → {titulo}")

                            totalPdfs = totalPdfs + 1
                            p = {
                                'fecha': fechaHoy,
                                'aerodromo': txt[6],
                                'url': url,
                                'tipo': tipo_codigo,
                                'titulo': titulo,
                                'modificacion': fechaHora
                            }
                            procedimientos.append(p)
                        except Exception as e:
                            errores.append(url)
                            print(f"  Error: {e}")
        else:
            offline = 1

    url2 = 'https://aipchile.dgac.gob.cl/aip/vol1/seccion/enr'
    html2 = get(url2)
    estado2 = html2.status_code
    santiago = ['SCTB', 'SCLC']
    vichuquen = ['SCLI', 'SCVQ', 'SCVK']
    if estado2 == 200:
        soup2 = BeautifulSoup(html2.text, 'html.parser').find(id="cat7")
        for pdf in soup2:
            url2 = pdf.find('a')
            if not isinstance(url2, int):
                urlPdf = url2.get('href')
                txt = urlPdf.split("/")
                urlPdf = 'https://aipchile.dgac.gob.cl' + urlPdf.replace(" ", "%20")
                try:
                    myfile1 = get(urlPdf)
                    dt1 = parse(myfile1.headers['Last-Modified'])
                    fechaHora1 = dt1.strftime("%Y-%m-%d %H:%M:%S")
                    if txt[6].find('Vichuquen') != -1:
                        for v in vichuquen:
                            p = {
                                'fecha': fechaHoy,
                                'aerodromo': v,
                                'url': urlPdf,
                                'tipo': 'Ruta Santiago - Vichuquen',
                                'modificacion': fechaHora1
                            }
                            procedimientos.append(p)
                            totalPdfs = totalPdfs + 1
                    else:
                        for s in santiago:
                            textoTipo = txt[6].split(' ')
                            if textoTipo[4] == 'Rutas':
                                tipo = textoTipo[4] + ' ' + textoTipo[5] + ' para AD Eulogio Sanchez y Vitacura'
                            elif textoTipo[4] == 'Procedimiento':
                                tipo = 'Procedimiento encaminamiento del tránsito'
                            else:
                                tipo = 'VRC1 - VRC2'
                            p = {
                                'fecha': fechaHoy,
                                'aerodromo': s,
                                'url': urlPdf,
                                'tipo': tipo,
                                'modificacion': fechaHora1
                            }
                            procedimientos.append(p)
                            totalPdfs = totalPdfs + 1

                except Exception as e:
                    errores.append(urlPdf)
                    print(f"  Error: {e}")

    for p in procedimientos:
        p.setdefault('titulo', p['tipo'])

    print(errores)
    print(f'Total PDFs: {totalPdfs}')
    return procedimientos, errores, offline


def runProcedimientos():
    now = datetime.datetime.now(datetime.timezone.utc)
    fechaHoy = now.strftime("%Y-%m-%d %H:%M:%S")
    print(fechaHoy)

    try:
        procedimientos, errores, offline = scrapeProcedimientos(fechaHoy)
    except Exception as e:
        msg = f'🔴 <b>extraeProcedimientos</b>: Error durante el scraping.\n<code>{e}</code>'
        print(msg)
        send_telegram(msg)
        raise

    if offline:
        msg = '🔴 <b>extraeProcedimientos</b>: la DGAC no respondio 200 en el listado, no se envia nada.'
        print(msg)
        send_telegram(msg)
        return

    # Enviar al servidor FeathersJS via HTTP (la API hace upsert + borra los que no vinieron)
    resp = requests.post(
        f'{API_URL}/scraper/procedimientos',
        json={'procedimientos': procedimientos, 'fechaHoy': fechaHoy},
        headers={'x-scraper-key': SCRAPER_KEY},
        timeout=120,
    )
    if not resp.ok:
        msg = f'🔴 <b>extraeProcedimientos</b>: la API respondio HTTP {resp.status_code}.\n<code>{resp.text[:300]}</code>'
        print(msg)
        send_telegram(msg)
        resp.raise_for_status()
    print(f'procedimientos enviados: {resp.json()}')
    print('Script Terminado')


if __name__ == '__main__':
    runProcedimientos()
