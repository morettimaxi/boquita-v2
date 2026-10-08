#!/usr/bin/env python3
"""Escucha /api/waf418/latest y abre Chrome apenas llega una captura nueva.

Uso:
    python watch_418.py
    python watch_418.py --every 1.5
"""
import argparse
import sys
import time

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

import abrir_418 as a418

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def fetch_latest():
    response = requests.get(
        f'{a418.WORKER_URL}/api/waf418/latest',
        params={'code': a418.WORKER_ACCESS_CODE},
        headers={'User-Agent': 'boca-queue-bot'},
        timeout=10,
    )
    if response.status_code == 404:
        return None
    if not response.ok:
        raise RuntimeError(f'Worker HTTP {response.status_code}: {response.text[:200]}')
    return response.json()


def capture_key(data):
    if not data:
        return None
    return data.get('id') or data.get('updated_at') or data.get('url')


def open_capture(data):
    target = a418.redirect_target(data)
    if not target:
        print('ERROR: la captura no tiene URL de redirect')
        return
    if data.get('source') == 'prueba-418-no-usar':
        print('Ignoro captura de prueba')
        return

    if '/queueit/redirect' not in target or 'queueittoken=' not in target:
        print(f'Ignoro captura sin redirect: {target[:160]}')
        return

    print('=' * 70)
    print(f'NUEVO 418: {data.get("source")} {data.get("updated_at")}')
    print(f'Redirect: {target[:220]}')
    print('Abro Chrome real, sin User-Agent de Ubuntu y sin cookies de alla.')
    print('=' * 70)

    options = Options()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=options)
    try:
        driver.get('about:blank')
        print('Entrando al redirect YA, referer queue-it...')
        driver.execute_cdp_cmd('Page.navigate', {
            'url': target,
            'referrer': 'https://bocajuniors.queue-it.net/',
        })
        for _ in range(12):
            time.sleep(1)
            cookies = a418.read_cookies(driver)
            names = a418.critical_names(cookies)
            print(f'  ahora: {driver.current_url[:140]} | finales={names or "todavia no"}')
            url = driver.current_url or ''
            if 'auth/login' in url or 'bocasocios.bocajuniors.com.ar' in url and 'queueit' not in url:
                print('Llego a bocasocios. Chrome queda abierto.')
                break
            if names and any('queueitaccepted' in n.lower() or n == 'CLID' for n in names):
                record, written = a418.save_final(cookies, url, f'watch-418:{data.get("source")}')
                for path in written:
                    print(f'Guardado: {path}')
                a418.upload_final(record)
                break
        print('Enter cierra este Chrome (el watcher sigue).')
        try:
            input()
        except EOFError:
            time.sleep(3600)
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description='Escuchar capturas 418 nuevas y abrir Chrome')
    parser.add_argument('--every', type=float, default=1.5, help='Segundos entre polls')
    args = parser.parse_args()

    print(f'Escuchando {a418.WORKER_URL}/api/waf418/latest cada {args.every}s')
    print('Cuando Ubuntu suba un 418 nuevo, abre Chrome al toque.')
    print('Ctrl+C para parar.\n')

    seen = set()
    try:
        current = fetch_latest()
        key = capture_key(current)
        if key:
            seen.add(key)
            print(f'Baseline actual: {current.get("source")} {current.get("updated_at")} (no la abro)')
    except Exception as error:
        print(f'Baseline: {error}')

    while True:
        try:
            data = fetch_latest()
            key = capture_key(data)
            if key and key not in seen:
                if data.get('source') == 'prueba-418-no-usar':
                    seen.add(key)
                else:
                    seen.add(key)
                    open_capture(data)
                    print('\nSigo escuchando...\n')
        except KeyboardInterrupt:
            print('\nListo.')
            return
        except Exception as error:
            print(f'poll error: {error}')
        time.sleep(args.every)


if __name__ == '__main__':
    main()
