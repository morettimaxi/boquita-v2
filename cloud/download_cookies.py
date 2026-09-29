#!/usr/bin/env python3
"""cloud/download_cookies.py
Descarga las ultimas cookies vigentes del Cloudflare Worker a tu PC local.
Guarda automaticamente tanto en Downloads como en popular-reserva/ para que los scripts
de reserva (order-popu-familia-rapido.py) las usen de inmediato.
"""

import argparse
import json
import os
import sys
import requests

DEFAULT_WORKER_URL = 'https://boca-cookies.rosaleseze86.workers.dev'
DEFAULT_ACCESS_CODE = 'Cangele2015'
DEFAULT_API_KEY = '6HHGGVfCch0U80-3kfBZS5e8EbmeiEKE5kTea8FWn1o'


def get_downloads_dir() -> str:
    home = os.path.expanduser('~')
    win_dl = os.path.join(home, 'Downloads')
    if os.path.isdir(win_dl):
        return win_dl
    return os.getcwd()


def download(worker_url: str = DEFAULT_WORKER_URL, code: str = DEFAULT_ACCESS_CODE, api_key: str = DEFAULT_API_KEY):
    headers = {}
    if code:
        headers['X-Access-Code'] = code
    if api_key:
        headers['X-API-Key'] = api_key

    params = {'code': code} if code else {}

    print(f"[*] Consultando worker: {worker_url}/api/cookies/latest ...")
    try:
        resp = requests.get(f'{worker_url}/api/cookies/latest', headers=headers, params=params, timeout=15)
    except Exception as e:
        print(f"[ERROR] Conectando al worker: {e}")
        return False

    if resp.status_code == 403:
        print("[ERROR] Codigo de acceso invalido (HTTP 403).")
        return False
    elif resp.status_code == 404:
        print("[ERROR] No hay cookies guardadas todavia en el worker (HTTP 404).")
        return False
    elif not resp.ok:
        print(f"[ERROR] HTTP {resp.status_code}: {resp.text}")
        return False

    data = resp.json()
    cookies_list = data.get('cookies') or []
    if not cookies_list:
        print("[ERROR] El worker devolvio una respuesta sin cookies validas.")
        return False

    paths_to_save = []
    # 1. Downloads
    paths_to_save.append(os.path.join(get_downloads_dir(), 'boca_cookies_worker.json'))

    # 2. popular-reserva local
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    popu_dir = os.path.join(root_dir, 'popular-reserva')
    if os.path.isdir(popu_dir):
        paths_to_save.append(os.path.join(popu_dir, 'boca_cookies_worker.json'))

    for p in paths_to_save:
        try:
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(cookies_list, f, indent=2)
            print(f"[OK] Guardado en: {p}")
        except Exception as e:
            print(f"[WARN] Error guardando en {p}: {e}")

    print(f"\n[EXITO] Descargadas {len(cookies_list)} cookies listas para reservar.")
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Descargar cookies del Cloudflare Worker')
    parser.add_argument('--url', default=DEFAULT_WORKER_URL, help='URL del worker')
    parser.add_argument('--code', default=DEFAULT_ACCESS_CODE, help='Codigo de acceso')
    args = parser.parse_args()

    ok = download(worker_url=args.url, code=args.code)
    sys.exit(0 if ok else 1)
