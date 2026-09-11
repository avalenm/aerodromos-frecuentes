import os
import requests

TELEGRAM_TOKEN   = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')


def send_telegram(mensaje: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f'[notifica] Telegram no configurado. Mensaje: {mensaje}')
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            json={'chat_id': TELEGRAM_CHAT_ID, 'text': mensaje, 'parse_mode': 'HTML'},
            timeout=10,
        )
    except Exception as e:
        # No imprimir str(e): la URL contiene el token y los logs son publicos
        print(f'[notifica] Error enviando Telegram: {type(e).__name__}')
