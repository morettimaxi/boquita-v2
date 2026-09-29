#!/usr/bin/env python3
"""Sube cookies de una sesión al Cloudflare Worker.

Uso:
    python upload_cookies.py 34
    python upload_cookies.py 34 --force
"""
import sys
import json
import os
import argparse
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

def main():
    parser = argparse.ArgumentParser(description='Sube cookies de sesión al Worker')
    parser.add_argument('session', type=int, help='Número de sesión (ej: 34)')
    parser.add_argument('--force', action='store_true', help='Subir aunque no tenga cookies críticas')
    parser.add_argument('--evento', type=int, default=868, help='Evento NID (default: 868)')
    args = parser.parse_args()

    cookie_file = f'session_{args.session}_cookies.json'
    if not os.path.exists(cookie_file):
        print(f'ERROR: No existe {cookie_file}')
        sys.exit(1)

    with open(cookie_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cookies = data.get('cookies', [])
    local_storage = data.get('local_storage', {})

    if not cookies:
        print(f'ERROR: {cookie_file} no tiene cookies')
        sys.exit(1)

    critical = [c for c in cookies if any(
        k in c.get('name', '').lower() for k in ['queueitaccepted', 'hwwaf', 'clid']
    )]
    has_clid = any(c.get('name') == 'CLID' for c in cookies)

    print(f'Sesión {args.session}:')
    print(f'  Cookies totales: {len(cookies)}')
    print(f'  Cookies críticas: {len(critical)}')
    print(f'  CLID (HttpOnly): {"SI" if has_clid else "NO"}')
    print(f'  localStorage items: {len(local_storage)}')

    if not critical and not args.force:
        print('ERROR: No hay cookies críticas. Usá --force para subir igual.')
        sys.exit(1)

    print(f'\nSubiendo al Worker...')

    payload = {
        'cookies': cookies,
        'cookie_string': data.get('cookie_string', ''),
        'local_storage': local_storage,
        'evento': args.evento,
        'source': f'upload-manual-session-{args.session}',
        'active': True,
    }

    resp = requests.post(
        f'{WORKER_URL}/api/cookies',
        json=payload,
        headers={'X-API-Key': WORKER_API_KEY, 'Content-Type': 'application/json'},
        timeout=10,
    )

    if resp.ok:
        result = resp.json()
        print(f'OK: {result.get("critical_count", 0)} críticas, {result.get("total_count", 0)} total')
        print(f'Timestamp: {result.get("updated_at", "")}')
    else:
        print(f'FALLO: HTTP {resp.status_code} - {resp.text}')
        sys.exit(1)

if __name__ == '__main__':
    main()
