import os
import re
import time
import datetime
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from notifica import send_telegram

load_dotenv()

API_URL     = os.getenv('API_URL', 'http://194.238.26.6:3639')
SCRAPER_KEY = os.getenv('SCRAPER_API_KEY', '')

header = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36"
}

# Si mas de esta cantidad de aerodromos responde distinto de 200, abortamos sin
# enviar nada: si no, la API los borraria por no venir en esta corrida.
MAX_FALLIDOS = 20


def get(url, intentos=3, espera=5):
    for intento in range(1, intentos + 1):
        try:
            return requests.get(url, headers=header, timeout=20)
        except requests.exceptions.RequestException as e:
            print(f"  Intento {intento}/{intentos} fallido para {url}: {e}")
            if intento < intentos:
                time.sleep(espera)
    raise requests.exceptions.ConnectionError(f"No se pudo conectar a {url} tras {intentos} intentos")


def devuelveGrados(text):
    text = text.replace('º', '')
    text = text.split(' ')
    grados = int(text[0]) + (float(text[1]) / 60) + (float(text[2]) / 3600)
    grados = round(grados, 4) * -1
    return grados


def scrapeAds(fechaHoy):
    """Recorre combinacionesAds.txt y devuelve (ads, pistas, errores_ubicacion)."""
    ads = []
    pistas = []
    error = 0
    fallidos = 0

    with open("combinacionesAds.txt", "r") as text_file:
        content = [x.strip() for x in text_file.readlines() if x.strip()]

    for ad in content:
        url = 'https://aipchile.dgac.gob.cl/aerodromo/show?aerodromo_sel=aerodromo&designador=' + ad + '&popup=&boton=Consultar'
        html = get(url)
        if html.status_code != 200:
            fallidos += 1
            print(f"  {ad}: HTTP {html.status_code}")
            if fallidos > MAX_FALLIDOS:
                raise RuntimeError(f"{fallidos} aerodromos con respuesta distinta de 200, se aborta")
            continue

        soup = BeautifulSoup(html.text, 'html.parser').find_all("div", {"class": "font_global"})
        codigo = soup[1]
        test = codigo(text=re.compile('No existe aeródromo con tal designador'))
        cerrado = codigo(text=re.compile('Ad. cerrado en forma definitiva'))
        if len(cerrado) > 0:
            # No se incluye: la API lo borra al no venir en esta corrida
            print(ad + ' cerrado en forma definitiva, se omite')
            continue
        if len(test) != 0:
            print(ad + ' no existe')
            continue

        encabeazado = codigo.find('h2').text
        pos = encabeazado.find(':')
        pos1 = encabeazado.find('(')
        nombre = encabeazado[pos + 1:pos1].strip()
        arrayText = encabeazado.split('(')
        uso = arrayText[1][0:3]
        if "SC" in uso:
            uso = 'PVT'
        ubicacion = codigo.find('td', {'headers': 'ubicacion'}).text
        ubicacion = ubicacion.replace('</br>', '').replace('\n', ' ').replace('\r', '')
        ubicacion = " ".join(ubicacion.split())
        ubicacion = ubicacion.split(',')
        i = ubicacion[0].find('Chile (')
        try:
            if i == -1:
                if len(ubicacion) < 4:
                    raise IndexError('ubicacion incompleta')
                lugar = ubicacion[0].strip()
                region = ubicacion[1].replace('Región', '').strip()
                lat = ubicacion[2].replace('Chile (', '').replace('S', '').replace("'", "").strip()
                long = ubicacion[3].replace('W) Ver ubicación en el mapa', '').replace("'", "").strip()
                latitud = devuelveGrados(lat)
                longitud = devuelveGrados(long)
            else:
                if ad == 'sczr':
                    lugar = 'Curepto'
                    region = 'VII'
                elif ad == 'sclt':
                    lugar = 'Topocalma'
                    region = 'VI'
                else:
                    lugar = ''
                    region = ''
                error = error + 1
                lat = ubicacion[0].replace('Chile (', '').replace('S', '').replace("'", "").strip()
                long = ubicacion[1].replace('W) Ver ubicación en el mapa', '').replace("'", "").strip()
                latitud = devuelveGrados(lat)
                longitud = devuelveGrados(long)
        except (IndexError, ValueError) as e:
            print(f"  {ad}: ubicacion con formato inesperado, se omite ({e})")
            continue

        try:
            # si no tiene horario el AD esta cerrado
            horario = codigo.find('td', {'headers': 'horas_operacion'}).text.strip()
        except Exception as e:
            horario = ''
            print("ERROR : " + str(e))
        try:
            elevacion = codigo.find('td', {'headers': 'elevacion'}).text.strip()
        except Exception:
            elevacion = ''
        try:
            obs = codigo.find('td', {'headers': 'observaciones'}).text.strip()
        except Exception:
            obs = ''

        metar = codigo(text=re.compile('No hay metares registrados'))
        metar = '0' if len(metar) == 1 else '1'
        print(ad + ' ' + metar)

        ads.append({
            "fecha": fechaHoy,
            "Nombre": nombre,
            "Uso": uso,
            "Codigo": ad.upper(),
            "Lugar": lugar,
            "Region": region,
            "Lat": lat,
            "Long": long,
            "Latitud": latitud,
            "Longitud": longitud,
            "Horario": horario,
            "Altitud": elevacion,
            "Obs": obs,
            "Metar": metar,
        })

        # ********* Pistas ***************
        try:
            tabla = BeautifulSoup(html.text, 'html.parser').find('table', {'class': 'tabla-pistas'})
            rows = tabla.findChildren(['tr'])
            for p in rows:
                celda = p.find('td', {'headers': 'orientacion'})
                if celda is None:
                    continue
                orientacion = celda.text
                print(orientacion)
                pistas.append({
                    "fecha": fechaHoy,
                    "Codigo": ad.upper(),
                    "Orientacion": orientacion,
                    "Dimencion": p.find('td', {'headers': 'dimension'}).text,
                    "Pendiente": p.find('td', {'headers': 'pendiente'}).text,
                    "Superficie": p.find('td', {'headers': 'superficie'}).text,
                    "Resistencia": p.find('td', {'headers': 'resistencia'}).text,
                    "Apch": p.find('td', {'headers': 'apch'}).text,
                    "Thr": p.find('td', {'headers': 'thr'}).text,
                    "Rwy": p.find('td', {'headers': 'rwy'}).text,
                    "Papi": p.find('td', {'headers': 'papi'}).text,
                    "Modificacion": '',
                })
        except Exception as e:
            print("ERROR : " + str(e))

    print('Total errores ubicacion: ' + str(error))
    print(f'Aerodromos: {len(ads)}  Pistas: {len(pistas)}  HTTP fallidos: {fallidos}')
    return ads, pistas


def runAds():
    now = datetime.datetime.now(datetime.timezone.utc)
    fechaHoy = now.strftime("%Y-%m-%d %H:%M:%S")
    print(fechaHoy)

    try:
        ads, pistas = scrapeAds(fechaHoy)
    except Exception as e:
        msg = f'🔴 <b>extraeAerodromos</b>: Error durante el scraping.\n<code>{e}</code>'
        print(msg)
        send_telegram(msg)
        raise

    # Enviar al servidor FeathersJS via HTTP (la API hace upsert + borra los que no vinieron)
    resp = requests.post(
        f'{API_URL}/scraper/aerodromos',
        json={'ads': ads, 'pistas': pistas, 'fechaHoy': fechaHoy},
        headers={'x-scraper-key': SCRAPER_KEY},
        timeout=120,
    )
    if not resp.ok:
        msg = f'🔴 <b>extraeAerodromos</b>: la API respondio HTTP {resp.status_code}.\n<code>{resp.text[:300]}</code>'
        print(msg)
        send_telegram(msg)
        resp.raise_for_status()
    print(f'aerodromos enviados: {resp.json()}')
    print('Proceso terminado')


if __name__ == '__main__':
    runAds()
