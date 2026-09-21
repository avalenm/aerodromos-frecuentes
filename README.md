# Aeródromos Chile — Scrapers DGAC

Scrapers de datos de aeródromos chilenos (sitio oficial de la DGAC, `aipchile.dgac.gob.cl`).

## Por qué este repo es público

GitHub Actions da **minutos ilimitados** a repositorios públicos y solo 3.000 min/mes a la cuenta para repos privados. Además la DGAC bloquea la IP fija del VPS, así que los scrapers no pueden correr allá. Cada run de Actions sale con una IP distinta.

**No hay información sensible en este repo.** Los scrapers no tocan la base de datos: hacen `POST` a la API en el VPS con una clave (`x-scraper-key`) que vive en GitHub Secrets. Los logs son públicos, por eso ningún script imprime secrets ni excepciones que puedan contenerlos.

## Workflows

| Workflow | Job | Frecuencia | Script | Endpoint |
|---|---|---|---|---|
| `scrape-frecuentes.yml` | Cámaras | cada 10 min | `extraeCamara.py` | `POST /scraper/camaras` |
| `scrape-frecuentes.yml` | Cerrados / NOTAMs | cada 30 min | `extraeCerrados.py` | `POST /scraper/cerrados` |
| `scrape-frecuentes.yml` | Keep-alive | cada 30 min | — | re-habilita ambos workflows por API |
| `scrape-dgac.yml` | Aeródromos + pistas | cada 48 h | `extraeAerodromos.py` | `POST /scraper/aerodromos` |
| `scrape-dgac.yml` | Aviso frecuencias | cada 48 h | `avisoCambioFrecuencias.py` | `POST /scraper/frecuencias` |
| `scrape-dgac.yml` | Procedimientos PDF | cada 72 h | `extraeProcedimientos.py` | `POST /scraper/procedimientos` |

GitHub desactiva los crons de un repo público tras 60 días sin commits; el job keep-alive lo evita re-habilitando los workflows vía API.

## Qué hace cada script

- **`extraeCamara.py`** — estado, orientación y link de cada cámara de aeródromo.
- **`extraeCerrados.py`** — NOTAMs QFALC (aeródromos cerrados) y QMRLC (pistas cerradas).
- **`extraeAerodromos.py`** — recorre `combinacionesAds.txt` (todos los designadores `SC??`) y extrae nombre, uso, ubicación, coordenadas, horario, elevación, observaciones y pistas. Si más de 20 páginas responden distinto de 200 aborta sin enviar, para que la API no borre aeródromos por un fallo de la DGAC.
- **`avisoCambioFrecuencias.py`** — compara el `Last-Modified` del PDF ENR 4.1 de frecuencias con el guardado; si cambió, avisa por Telegram.
- **`extraeProcedimientos.py`** — listado de cartillas PDF (IAC, SID, STAR, MRVA, rutas) por aeródromo y extrae el título real desde el PDF con `pdfplumber`.

La API hace upsert de lo recibido y borra lo que no vino en la corrida (misma semántica que tenía el `delete_many` original), con un mínimo de registros para no vaciar una colección.

## Arquitectura

```
GitHub Actions (este repo — público, IP rotatoria)
├── extraeCamara.py            → POST /scraper/camaras         ┐
├── extraeCerrados.py          → POST /scraper/cerrados        │
├── extraeAerodromos.py        → POST /scraper/aerodromos      ├→ API FeathersJS (VPS) → MongoDB
├── avisoCambioFrecuencias.py  → POST /scraper/frecuencias     │
└── extraeProcedimientos.py    → POST /scraper/procedimientos  ┘

Repo privado (aerodromos-chile)
├── api/   → FeathersJS REST API (endpoints /scraper/* en src/middleware/index.js)
└── app/   → Flutter (iOS/Android)
```

## Secrets requeridos

| Secret | Descripción |
|---|---|
| `API_URL` | URL base de la API (ej. `http://194.238.26.6:3639`) |
| `SCRAPER_API_KEY` | Debe coincidir con `SCRAPER_API_KEY` en el `.env` de la API |
| `TELEGRAM_TOKEN` | Bot de Telegram para alertas de error y cambio de frecuencias |
| `TELEGRAM_CHAT_ID` | Chat que recibe las alertas |

## Correr local

```bash
pip install -r requirements.txt
cp .env.example .env   # completar
python extraeAerodromos.py
```
