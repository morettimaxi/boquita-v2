#!/usr/bin/env python3
"""Sube el boca_cookies*.json mas nuevo (Downloads o cwd) al Cloudflare Worker.

Uso:
    python upload_latest_cookies.py
    python upload_latest_cookies.py --file C:\\Users\\moret\\Downloads\\boca_cookies_....json
    python upload_latest_cookies.py --evento 870
"""
import argparse
import glob
import json
import os
import sys

import requests

WORKER_URL = 'https://boca-cookies.rosaleseze86.workers.dev'


def _read_worker_key():
    key = os.environ.get('WORKER_API_KEY', '').strip()
    if key or os.name != 'nt':
        return key
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k:
            return str(winreg.QueryValueEx(k, 'WORKER_API_KEY')[0]).strip()
    except OSError:
        return ''


WORKER_API_KEY = _read_worker_key()


def find_latest_cookie_file(explicit=None):
    if explicit:
        if not os.path.exists(explicit):
            print(f'ERROR: No existe {explicit}')
            sys.exit(1)
        return explicit

    downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
    files = []
    for d in ['.', downloads_dir]:
        files.extend(glob.glob(os.path.join(d, 'boca_cookies*.json')))

    if not files:
        print('ERROR: No hay boca_cookies*.json en cwd ni en Downloads')
        sys.exit(1)

    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def main():
    parser = argparse.ArgumentParser(description='Sube el export de cookies mas nuevo al Worker')
    parser.add_argument('--file', type=str, default=None, help='JSON puntual (si no, el mas nuevo)')
    parser.add_argument('--evento', type=int, default=None, help='Evento NID opcional')
    parser.add_argument('--force', action='store_true', help='Subir aunque no haya cookies criticas')
    args = parser.parse_args()

    cookie_file = find_latest_cookie_file(args.file)
    with open(cookie_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cookies = data.get('cookies', [])
    if not cookies:
        print(f'ERROR: {cookie_file} no tiene cookies')
        sys.exit(1)

    critical = [c for c in cookies if any(
        k in c.get('name', '').lower() for k in ['queueitaccepted', 'hwwaf', 'clid']
    )]

    print(f'Archivo: {cookie_file}')
    print(f'  URL: {data.get("url", "")}')
    print(f'  Timestamp: {data.get("timestamp", "")}')
    print(f'  Cookies totales: {len(cookies)}')
    print(f'  Cookies criticas: {len(critical)}')
    for c in critical:
        print(f'    - {c.get("name")}')

    if not critical and not args.force:
        print('ERROR: No hay cookies criticas (QueueIT / HWWAF). Usá --force para subir igual.')
        sys.exit(1)

    print('\nSubiendo al Worker...')
    payload = {
        'cookies': cookies,
        'cookie_string': data.get('cookie_string', ''),
        'local_storage': data.get('local_storage', {}),
        'evento': args.evento,
        'source': f'browser-export-{os.path.basename(cookie_file)}',
        'active': True,
    }

    resp = requests.post(
        f'{WORKER_URL}/api/cookies',
        json=payload,
        headers={'X-API-Key': WORKER_API_KEY, 'Content-Type': 'application/json'},
        timeout=15,
    )

    if resp.ok:
        result = resp.json()
        print(f'OK: {result.get("critical_count", 0)} criticas, {result.get("total_count", 0)} total')
        print(f'Timestamp worker: {result.get("updated_at", "")}')
    else:
        print(f'FALLO: HTTP {resp.status_code} - {resp.text}')
        sys.exit(1)


if __name__ == '__main__':
    main()
