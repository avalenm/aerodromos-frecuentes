import os
import time
import datetime
import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse
from dotenv import load_dotenv
from notifica import send_telegram

load_dotenv()

API_URL     = os.getenv('API_URL', 'http://194.238.26.6:3639')
SCRAPER_KEY = os.getenv('SCRAPER_API_KEY', '')

header = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36"
}


def get(url, intentos=3, espera=5):
    for intento in range(1, intentos + 1):
        try:
            resp = requests.get(url, headers=header, timeout=30)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            print(f"  Intento {intento}/{intentos} fallido para {url}: {e}")
            if intento < intentos:
                time.sleep(espera)
    raise requests.exceptions.ConnectionError(f"No se pudo conectar a {url} tras {intentos} intentos")


def runFrecuencias():
    """Detecta si la DGAC cambio el PDF de frecuencias (ENR, cat4).

    La API guarda el Last-Modified anterior y responde si cambio; el aviso
    se manda por Telegram (antes era un mail por SMTP desde el repo privado).
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    fechaHoy = now.strftime("%Y-%m-%d %H:%M:%S")
    print(fechaHoy)

    try:
        html = get('https://aipchile.dgac.gob.cl/aip/vol1/seccion/enr')
        soup = BeautifulSoup(html.text, 'html.parser').find(id="cat4")
        urlPdf = soup.find('a').get('href')
        urlFinal = 'https://aipchile.dgac.gob.cl' + urlPdf
        pdf = get(urlFinal)
        modificacion = parse(pdf.headers['Last-Modified']).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        msg = f'🔴 <b>avisoCambioFrecuencias</b>: Error durante el scraping.\n<code>{e}</code>'
        print(msg)
        send_telegram(msg)
        raise

    resp = requests.post(
        f'{API_URL}/scraper/frecuencias',
        json={'url': urlFinal, 'modificacion': modificacion, 'fechaHoy': fechaHoy},
        headers={'x-scraper-key': SCRAPER_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    r = resp.json()
    print(f'frecuencias: {r}')

    if r.get('cambio'):
        msg = (f'📻 <b>La DGAC cambió el PDF de frecuencias</b>\n'
               f'Antes: {r.get("anterior")}\nAhora: {modificacion}\n{urlFinal}')
        print(msg)
        send_telegram(msg)
    print('Proceso Terminado')


if __name__ == '__main__':
    runFrecuencias()
