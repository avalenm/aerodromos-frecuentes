import os
import requests
import re
import math
from bs4 import BeautifulSoup
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'))
db = client['aerodromos']
col = db['cerrados']

header = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36"
}

now = datetime.datetime.now()
fechaHoy = now.strftime("%Y-%m-%d %H:%M:%S")

aerodromosCerrados = []

def adsCerrados():
    url = "https://aipchile.dgac.gob.cl/notam?notam_filters%5Bfir%5D=&notam_filters%5Bserie%5D%5Btext%5D=&notam_filters%5Btipo%5D=&notam_filters%5Bcodigo%5D%5Btext%5D=QFALC&notam_filters%5Btransito%5D%5Btext%5D=&notam_filters%5Bobjetivo%5D%5Btext%5D=&notam_filters%5Balcance%5D%5Btext%5D=&notam_filters%5Btexto%5D%5Btext%5D=&filter=1&boton=Filtrar"
    #extraigo el numero de resultados
    html = requests.get(url)
    estado = html.status_code
    if estado == 200:
        soup = BeautifulSoup(html.text, 'html.parser')
        test = soup.findAll(text = re.compile('Se encontraron'))
        txt = test[0].replace('\n', '').split(' ')
        cantidad = int(txt[2])
        numeroPaginas = math.ceil(cantidad/20)
        #print(numeroPaginas)

        for i in range(1, numeroPaginas+1):
            #print(i)
            urlAds = "https://aipchile.dgac.gob.cl/notam?page=" + format(i) + "notam_filters%5Bfir%5D=&notam_filters%5Bserie%5D%5Btext%5D=&notam_filters%5Btipo%5D=&notam_filters%5Bcodigo%5D%5Btext%5D=QFALC&notam_filters%5Btransito%5D%5Btext%5D=&notam_filters%5Bobjetivo%5D%5Btext%5D=&notam_filters%5Balcance%5D%5Btext%5D=&notam_filters%5Btexto%5D%5Btext%5D=&filter=1&boton=Filtrar"
            htmlAds = requests.get(urlAds)
            soupAds = BeautifulSoup(htmlAds.text, 'html.parser').find_all('td', class_='codificacion')
            for notam in soupAds:
                txt = notam.getText()
                txt = txt.replace('</br>', '').replace('\n', ' ').replace('\r', '')
                txt = re.sub(' +', ' ', txt)
                a = txt.find('A)')
                b = txt.find('B)')
                c = txt.find('C)')
                d = txt.find('D)')
                e = txt.find('E)')
                notamTxt = txt
                print(txt)
                leng = len(txt)
                enc = print(txt[0:a])
                codigo = txt[a+2:a+6]
                print(codigo)
                inicio = ''
                if(b > -1):
                    #print(txt[b:-bb])
                    inicio = '20' + txt[b+2:b+4] + "-" + txt[b+4:b+6] + "-" + txt[b+6:b+8]
                    print(inicio)
                fin = ''
                if(c > -1):
                    if(txt[c+2:].find('PERM') > -1):
                        fin = '2100-12-31'
                    else:
                        fin = '20' + txt[c+2:c+4] + "-" + txt[c+4:c+6] + "-" + txt[c+6:c+8]
                    print(fin)
                horario = ''
                if(d > -1):
                    dd = leng - e
                    horario = txt[d+2:-dd]
                    #print(txt[d+2:-dd])
                print(txt[e:])
                p = {
                    'Codigo': codigo,
                    'FechaFin': fin,
                    'FechaInicio': inicio,
                    'Horario':horario,
                    'Notam': txt,
                    'Pista': '1',
                    'Tipo': '1'
                    }
                aerodromosCerrados.append(p)

def pistasCerradas():
    url = "https://aipchile.dgac.gob.cl/notam?notam_filters%5Bfir%5D=&notam_filters%5Bserie%5D%5Btext%5D=&notam_filters%5Btipo%5D=&notam_filters%5Bcodigo%5D%5Btext%5D=QMRLC&notam_filters%5Btransito%5D%5Btext%5D=&notam_filters%5Bobjetivo%5D%5Btext%5D=&notam_filters%5Balcance%5D%5Btext%5D=&notam_filters%5Btexto%5D%5Btext%5D=&filter=1&boton=Filtrar"

    #extraigo el numero de resultados
    html = requests.get(url)
    estado = html.status_code
    if estado == 200:
        soup = BeautifulSoup(html.text, 'html.parser')
        test = soup.findAll(text = re.compile('Se encontraron'))
        txt = test[0].replace('\n', '').split(' ')
        cantidad = int(txt[2])
        numeroPaginas = math.ceil(cantidad/20)
        print(numeroPaginas)

        for i in range(1, numeroPaginas+1):
            print(i)
            urlAds = "https://aipchile.dgac.gob.cl/notam?page=" + format(i) + "notam_filters%5Bfir%5D=&notam_filters%5Bserie%5D%5Btext%5D=&notam_filters%5Btipo%5D=&notam_filters%5Bcodigo%5D%5Btext%5D=QMRLC&notam_filters%5Btransito%5D%5Btext%5D=&notam_filters%5Bobjetivo%5D%5Btext%5D=&notam_filters%5Balcance%5D%5Btext%5D=&notam_filters%5Btexto%5D%5Btext%5D=&filter=1&boton=Filtrar"
            htmlAds = requests.get(urlAds)
            soupAds = BeautifulSoup(htmlAds.text, 'html.parser').find_all('td', class_='codificacion')
            for notam in soupAds:
                txt = notam.getText()
                txt = txt.replace('</br>', '').replace('\n', ' ').replace('\r', '')
                txt = re.sub(' +', ' ', txt)
                a = txt.find('A)')
                b = txt.find('B)')
                c = txt.find('C)')
                d = txt.find('D)')
                e = txt.find('E)')
                notamTxt = txt
                print(txt)
                leng = len(txt)
                enc = print(txt[0:a])
                codigo = txt[a + 2:a + 6]
                print(codigo)
                inicio = ''
                if (b > -1):
                    # print(txt[b:-bb])
                    inicio = '20' + txt[b + 2:b + 4] + "-" + txt[b + 4:b + 6] + "-" + txt[b + 6:b + 8]
                    print(inicio)
                fin = ''
                if (c > -1):
                    if (txt[c + 2:].find('PERM') > -1):
                        fin = '2100-12-31'
                    else:
                        fin = '20' + txt[c + 2:c + 4] + "-" + txt[c + 4:c + 6] + "-" + txt[c + 6:c + 8]
                    print(fin)
                horario = ''
                if (d > -1):
                    dd = leng - e
                    horario = txt[d + 2:-dd]
                    # print(txt[d+2:-dd])
                print(txt[e:])
                pistaLoc = txt.find('RWY')
                pista = txt[pistaLoc+4:pistaLoc+6]
                pistaLado = txt[pistaLoc+6:pistaLoc+7]
                if pistaLado != '/':
                    pista = pista + pistaLado
                p = {
                    'Codigo': codigo,
                    'FechaFin': fin,
                    'FechaInicio': inicio,
                    'Horario': horario,
                    'Notam': txt,
                    'Pista': pista,
                    'Tipo': '2'
                }
                aerodromosCerrados.append(p)

def runCerrados():
    adsCerrados()
    pistasCerradas()

    for p in aerodromosCerrados:
        col.update_one({
            'Codigo': p['Codigo'],
            'Notam': p['Notam'],
        }, {
            "$set": {
                'Codigo': p['Codigo'],
                'FechaFin': p['FechaFin'],
                'FechaInicio': p['FechaInicio'],
                'Horario': p['Horario'],
                'Notam': p['Notam'],
                'Pista': p['Pista'],
                'Tipo': p['Tipo'],
                'fecha': fechaHoy,
            }
        }, upsert=True)
        # borro los que no se actualizaron o insertaron
        col.delete_many({'fecha': {'$ne': fechaHoy}})

    print('Scrip Terminado')

if __name__ == '__main__':
    runCerrados()

