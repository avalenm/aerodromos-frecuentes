import os
import time
import requests
from bs4 import BeautifulSoup
import datetime
from dotenv import load_dotenv
from notifica import send_telegram

load_dotenv()

API_URL       = os.getenv('API_URL', 'http://194.238.26.6:3639')
SCRAPER_KEY   = os.getenv('SCRAPER_API_KEY', '')

header = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36"
}

REQUEST_TIMEOUT = 20
MAX_RETRIES     = 3
RETRY_DELAY     = 5


def get_with_retry(url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=header, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            print(f'Intento {attempt}/{MAX_RETRIES} fallido para {url}: {e}')
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    return None


def getCamaras(link, nombre, lugar, codigo):
    urlCamara = 'https://aipchile.dgac.gob.cl' + link
    htmlCamara = get_with_retry(urlCamara)
    if htmlCamara is None:
        print(f'No se pudo obtener cámara: {urlCamara}')
        return []
    camaras = []
    soupCamara = BeautifulSoup(htmlCamara.text, 'html.parser').find_all("div", {"class": "imagenes_box"})
    for imagen in soupCamara:
        urlImagen = imagen.find('a')
        urllast = urlImagen.get('href')
        texto = urlImagen.get('title')
        operacional = 1 if len(urllast) > 0 else 0
        txt = texto.split(' ')
        sub = 'tomada'
        ind = [i for i, s in enumerate(txt) if sub in s]
        orientacion = txt[ind[0] - 1]
        camaras.append({
            'lugar':       lugar,
            'nombre':      nombre,
            'codigo':      codigo,
            'orientacion': orientacion,
            'link':        urllast,
            'texto':       texto,
            'operacional': operacional,
        })
    return camaras


def extractCamaras():
    now = datetime.datetime.now(datetime.timezone.utc)
    fechaHoy = now.strftime("%Y-%m-%d %H:%M:%S")
    print(fechaHoy)

    url = 'https://aipchile.dgac.gob.cl/camara/'
    html = get_with_retry(url)
    if html is None:
        msg = '🔴 <b>extraeCamara</b>: No se pudo conectar a aipchile.dgac.gob.cl después de 3 intentos.'
        print(msg)
        send_telegram(msg)
        return

    todasCamaras = []
    soup = BeautifulSoup(html.text, 'html.parser').find_all("td", {"headers": "aerodromos"})
    for link in soup:
        url = link.find('a')
        nombre = url.get('title')
        codigo = nombre[-5:-1]
        if 'SC' not in codigo:
            codigo = ''
        a = nombre.find('(')
        if a > -1:
            nombre = nombre[:a]
            lugar = link.select('div')[1].get_text(strip=True)
        else:
            lugar = "Santiago"
        url = url.get('href')
        datos = getCamaras(url, nombre.strip(), lugar, codigo)
        todasCamaras.extend(datos)

    # Enviar al servidor FeathersJS via HTTP
    resp = requests.post(
        f'{API_URL}/scraper/camaras',
        json={'camaras': todasCamaras, 'fechaHoy': fechaHoy},
        headers={'x-scraper-key': SCRAPER_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    print(f'camaras enviadas: {resp.json()}')
    print('Script Terminado')


if __name__ == '__main__':
    extractCamaras()
