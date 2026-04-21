# Aeródromos Chile — Scrapers Frecuentes

Scrapers de alta frecuencia para datos de aeródromos chilenos (DGAC).

## Por qué este repo es público

GitHub Actions otorga **minutos ilimitados** a repositorios públicos, pero solo 2.000 min/mes a repos privados. Los scrapers de este repo corren con mucha frecuencia:

- **Cámaras**: cada 5 minutos → 8.640 ejecuciones/mes
- **NOTAMs/Cerrados**: cada 20 minutos → 2.160 ejecuciones/mes

Esto haría imposible mantenerlos en el repo privado sin incurrir en costos. Al ser público, corren gratis sin límite.

**No hay información sensible en este repo** — las credenciales están en GitHub Secrets y nunca en el código.

## Qué hace cada script

### `extraeCamara.py`
Raspa la sección de cámaras del sitio oficial de la DGAC (`aipchile.dgac.gob.cl/camara/`) y guarda en MongoDB el estado operacional, orientación y link de cada cámara de aeródromo.

### `extraeCerrados.py`
Raspa los NOTAMs de tipo QFALC (aeródromos cerrados) y QMRLC (pistas cerradas) desde el sitio de la DGAC y guarda fechas de inicio/fin, código ICAO y texto completo del NOTAM.

## Arquitectura general

```
GitHub Actions (este repo — público, IP rotatoria)
├── extraeCamara.py    → cada 5 min  → MongoDB en VPS
└── extraeCerrados.py  → cada 20 min → MongoDB en VPS

Repo privado (aerodromos-chile)
├── scraper/  → aeródromos, procedimientos, frecuencias, instagram
├── api/      → FeathersJS REST API
└── app/      → Flutter (iOS/Android)
```

## Rotación de IP

Cada ejecución de GitHub Actions corre en una VM nueva con IP diferente (red de Microsoft Azure), lo que evita el bloqueo de IP por parte de la DGAC al hacer scraping frecuente.

## Secrets requeridos

| Secret | Descripción |
|---|---|
| `CONTABO_SSH_KEY` | Clave SSH privada para el túnel a MongoDB |

El túnel SSH conecta GitHub Actions directamente a MongoDB en el VPS sin exponer el puerto a internet.
