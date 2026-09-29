#!/usr/bin/env python3
"""cloud/upload_cookies.py
Sube manualmente un archivo de cookies JSON al Cloudflare Worker.
"""

import argparse
import json
import os
import sys
import requests

DEFAULT_WORKER_URL = 'https://boca-cookies.rosaleseze86.workers.dev'
DEFAULT_API_KEY = '6HHGGVfCch0U80-3kfBZS5e8EbmeiEKE5kTea8FWn1o'


def upload(file_path: str, worker_url: str = DEFAULT_WORKER_URL, api_key: str = DEFAULT_API_KEY, evento: str = None):
    if not os.path.exists(file_path):
        print(f"[ERROR] Archivo no encontrado: {file_path}")
        return False

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cookies = data if isinstance(data, list) else data.get('cookies', [])
    if not cookies:
        print("[ERROR] No se encontraron cookies en el archivo.")
        return False

    payload = {
        'cookies': cookies,
        'evento': evento
    }

    headers = {
        'Content-Type': 'application/json',
        'X-API-Key': api_key
    }

    print(f"[*] Subiendo {len(cookies)} cookies al Worker...")
    try:
        resp = requests.post(f'{worker_url}/api/cookies', json=payload, headers=headers, timeout=15)
        if resp.ok:
            print(f"[EXITO] Cookies subidas correctamente: {resp.json()}")
            return True
        else:
            print(f"[ERROR] HTTP {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Fallo la conexion: {e}")
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Subir cookies al Worker')
    parser.add_argument('file', help='Ruta al archivo JSON de cookies')
    parser.add_argument('--evento', default=None, help='ID de evento opcional')
    parser.add_argument('--url', default=DEFAULT_WORKER_URL, help='URL del Worker')
    args = parser.parse_args()

    ok = upload(args.file, worker_url=args.url, evento=args.evento)
    sys.exit(0 if ok else 1)
