#!/usr/bin/env python3
"""Abre Chrome, va a bocasocios, captura cookies (con HttpOnly) + localStorage via CDP.
Guarda en formato compatible con upload_cookies.py.

Uso:
    python capture_browser.py
    python capture_browser.py --upload
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BOCA_URL = 'https://bocasocios.bocajuniors.com.ar'
WORKER_URL = 'https://boca-cookies.rosaleseze86.workers.dev'
WORKER_API_KEY = '6HHGGVfCch0U80-3kfBZS5e8EbmeiEKE5kTea8FWn1o'


def main():
    parser = argparse.ArgumentParser(description='Captura cookies + localStorage de bocasocios')
    parser.add_argument('--upload', action='store_true', help='Subir al Worker después de capturar')
    parser.add_argument('--output', default='browser_cookies.json', help='Archivo de salida')
    parser.add_argument('--headless', action='store_true', help='Modo headless')
    args = parser.parse_args()

    print('Abriendo Chrome...')
    options = Options()
    if args.headless:
        options.add_argument('--headless=new')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])

    driver = webdriver.Chrome(options=options)

    try:
        print(f'Navegando a {BOCA_URL}...')
        driver.get(BOCA_URL)
        time.sleep(3)

        print(f'URL actual: {driver.current_url}')

        if 'queue.it' in driver.current_url or 'queueit' in driver.current_url.lower():
            print('\nEstas en la cola de Queue-it.')
            print('Esperando a que pases la cola... (o cerrá con Ctrl+C)')
            while 'queue.it' in driver.current_url or 'queueit' in driver.current_url.lower():
                time.sleep(2)
            print(f'Pasaste la cola. URL: {driver.current_url}')
            time.sleep(2)

        # CDP: cookies completas incluyendo HttpOnly
        print('\nCapturando cookies via CDP...')
        cdp_result = driver.execute_cdp_cmd('Network.getCookies', {
            'urls': [
                'https://bocasocios.bocajuniors.com.ar',
                'https://bocasocios-gw.bocajuniors.com.ar',
                'https://.bocajuniors.com.ar',
            ]
        })
        all_cookies = cdp_result.get('cookies', [])

        # localStorage
        print('Capturando localStorage...')
        local_storage = driver.execute_script("""
            let ls = {};
            for (let i = 0; i < localStorage.length; i++) {
                let key = localStorage.key(i);
                ls[key] = localStorage.getItem(key);
            }
            return ls;
        """)

        # Formato compatible con upload_cookies.py
        chrome_cookies = []
        for c in all_cookies:
            cc = {
                'name': c.get('name', ''),
                'value': c.get('value', ''),
                'domain': c.get('domain', ''),
                'path': c.get('path', '/'),
                'secure': c.get('secure', False),
                'httpOnly': c.get('httpOnly', False),
                'sameSite': c.get('sameSite', 'Lax'),
            }
            if c.get('expires', 0) > 0:
                cc['expirationDate'] = c['expires']
            chrome_cookies.append(cc)

        critical = [c for c in chrome_cookies if any(
            k in c['name'].lower() for k in ['queueitaccepted', 'hwwaf', 'clid']
        )]
        has_clid = any(c['name'] == 'CLID' for c in chrome_cookies)
        cookie_string = '; '.join(f"{c['name']}={c['value']}" for c in chrome_cookies)

        data = {
            'session_id': 'browser',
            'timestamp': datetime.now().isoformat(),
            'redirect_url': '',
            'current_url': driver.current_url,
            'cookies': chrome_cookies,
            'local_storage': local_storage,
            'cookie_string': cookie_string,
        }

        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        print(f'\nResultado:')
        print(f'  Cookies totales: {len(chrome_cookies)}')
        print(f'  Cookies criticas: {len(critical)}')
        for c in critical:
            print(f'    - {c["name"]} (httpOnly={c["httpOnly"]})')
        print(f'  CLID (HttpOnly): {"SI" if has_clid else "NO"}')
        print(f'  localStorage: {len(local_storage)} items')
        if local_storage:
            for k in list(local_storage.keys())[:10]:
                print(f'    - {k}: {str(local_storage[k])[:60]}')
        print(f'  Guardado en: {args.output}')

        if args.upload:
            import requests
            print(f'\nSubiendo al Worker...')
            payload = {
                'cookies': chrome_cookies,
                'cookie_string': cookie_string,
                'local_storage': local_storage,
                'evento': 868,
                'source': 'capture-browser-manual',
                'active': True,
            }
            api_key = WORKER_API_KEY
            resp = requests.post(
                'https://boca-cookies.rosaleseze86.workers.dev/api/cookies',
                json=payload,
                headers={
                    'X-API-Key': api_key,
                    'Content-Type': 'application/json',
                },
                timeout=10,
            )
            if resp.ok:
                r = resp.json()
                print(f'OK: {r.get("critical_count", 0)} criticas, {r.get("total_count", 0)} total')
            else:
                print(f'FALLO: HTTP {resp.status_code} - {resp.text}')

    finally:
        input('\nEnter para cerrar Chrome...')
        driver.quit()

if __name__ == '__main__':
    main()
