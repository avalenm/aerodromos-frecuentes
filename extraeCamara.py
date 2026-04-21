import os
import time
import requests
from bs4 import BeautifulSoup
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'))
db = client['aerodromos']
col = db['camaras']

header = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36"
}

REQUEST_TIMEOUT = 20  # segundos
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos entre reintentos


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
        if (len(urllast) > 0):
            operacional = 1
        else:
            operacional = 0
        txt = texto.split(' ')
        sub = 'tomada'
        ind = [i for i, s in enumerate(txt) if sub in s]
        orientacion = txt[ind[0] - 1]

        datos = {
            'lugar': lugar,
            'nombre': nombre,
            'codigo': codigo,
            'orientacion': orientacion,
            'link': urllast,
            'texto': texto,
            'operacional': operacional,
        }
        camaras.append(datos)
    return camaras

def extractCamaras():

    now = datetime.datetime.now()
    fechaHoy = now.strftime("%Y-%m-%d %H:%M:%S")
    print(fechaHoy)
    totalCamaras = 0

    url = 'https://aipchile.dgac.gob.cl/camara/'

    html = get_with_retry(url)
    if html is None:
        print('No se pudo conectar a DGAC después de los reintentos. Abortando.')
        return

    soup = BeautifulSoup(html.text, 'html.parser').find_all("td", {"headers": "aerodromos"})
    for link in soup:
        url = link.find('a')
        nombre = url.get('title')
        codigo = nombre[-5:-1]
        if('SC' not in codigo):
            codigo = ''
        a = nombre.find('(')
        if(a>-1):
            nombre = nombre[:a]
            lugar = link.select('div')[1].get_text(strip=True)
        else:
            lugar = "Santiago"

        url = url.get('href')
        totalCamaras = totalCamaras + 1
        datos = getCamaras(url, nombre.strip(), lugar, codigo)
        for cam in datos:
            col.update_one({
                'nombre': cam['nombre'],
                'codigo': cam['codigo'],
                'orientacion': cam['orientacion'],
            },{
                "$set":{
                    'fecha': fechaHoy,
                    'lugar': cam['lugar'],
                    'nombre': cam['nombre'],
                    'codigo': cam['codigo'],
                    'orientacion': cam['orientacion'],
                    'link': cam['link'],
                    'texto': cam['texto'],
                    'operacional': cam['operacional']
                    }
            }, upsert=True)
            col.delete_many({'fecha': {'$ne': fechaHoy}})

    print(totalCamaras)
    print('Scrip Terminado')

if __name__ == '__main__':
    extractCamaras()
