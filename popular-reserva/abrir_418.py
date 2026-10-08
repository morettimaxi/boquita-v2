#!/usr/bin/env python3
"""Abre Chrome con una captura 418 y entra al ultimo redirect.

Inyecta cookies, localStorage, sessionStorage y el User-Agent de esa captura.
Despues abre la URL que dio 418 (la del queueittoken). Si bocasocios deja pasar,
ahi se generan QueueITAccepted, HWWAF y CLID. Esas finales se guardan y se suben
a la cola normal del Worker.

Uso:
    python abrir_418.py
    python abrir_418.py --file boca_cookies_418.json
    python abrir_418.py --worker
"""
import glob
import json
import os
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

WORKER_URL = 'https://boca-cookies.rosaleseze86.workers.dev'
WORKER_API_KEY = '6HHGGVfCch0U80-3kfBZS5e8EbmeiEKE5kTea8FWn1o'
WORKER_ACCESS_CODE = 'Cangele2015'
CRITICAL = ('queueitaccepted', 'hwwaf', 'clid')

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def find_capture(explicit=None):
    if explicit:
        if not os.path.exists(explicit):
            print(f'ERROR: no existe {explicit}')
            sys.exit(1)
        return explicit
    downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
    here = os.path.dirname(os.path.abspath(__file__))
    roots = ['.', here, downloads, os.path.join(here, '..', 'queue-manager')]
    files = []
    for root in roots:
        files.extend(glob.glob(os.path.join(root, 'boca_cookies_418.json')))
        files.extend(glob.glob(os.path.join(root, 'session_*_418.json')))
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        print('ERROR: no hay captura 418. Bjala con:')
        print('  python download_latest_cookies.py --waf418')
        sys.exit(1)
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def load_capture(path=None, from_worker=False):
    if from_worker:
        print(f'Bajando captura de {WORKER_URL}/api/waf418/latest ...')
        response = requests.get(
            f'{WORKER_URL}/api/waf418/latest',
            params={'code': WORKER_ACCESS_CODE},
            headers={'User-Agent': 'boca-queue-bot'},
            timeout=20,
        )
        if not response.ok:
            print(f'ERROR: Worker HTTP {response.status_code}: {response.text[:200]}')
            sys.exit(1)
        data = response.json()
        print(f"Fuente: {data.get('source', '')}")
        return data, 'worker'
    path = find_capture(path)
    print(f'Usando {os.path.abspath(path)}')
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle), path


def origin_of(url):
    parsed = urlparse(url or '')
    if parsed.scheme in ('http', 'https') and parsed.netloc:
        return f'{parsed.scheme}://{parsed.netloc}'
    return ''


def redirect_target(data):
    url = data.get('url') or ''
    page = data.get('page_url') or ''
    if 'queueittoken=' in url or '/queueit/redirect' in url:
        return url
    if 'queueittoken=' in page or '/queueit/redirect' in page:
        return page
    return url or page


def storage_by_origin(data):
    origins = {}
    raw = data.get('origins') or {}
    if isinstance(raw, dict):
        for origin, snapshot in raw.items():
            if not origin or not isinstance(snapshot, dict):
                continue
            origins[origin] = {
                'local_storage': snapshot.get('local_storage') or {},
                'session_storage': snapshot.get('session_storage') or {},
            }
    page_origin = origin_of(data.get('page_url') or data.get('url') or '')
    if page_origin and page_origin not in origins:
        local_storage = data.get('local_storage') or {}
        session_storage = data.get('session_storage') or {}
        if local_storage or session_storage:
            origins[page_origin] = {
                'local_storage': local_storage,
                'session_storage': session_storage,
            }
    return origins


def inject_cookies(driver, cookies):
    driver.execute_cdp_cmd('Network.enable', {})
    placed = 0
    for cookie in cookies or []:
        name = cookie.get('name') or ''
        value = cookie.get('value')
        if not name or value is None:
            continue
        domain = cookie.get('domain') or '.bocajuniors.com.ar'
        params = {
            'name': name,
            'value': value,
            'domain': domain,
            'path': cookie.get('path') or '/',
            'secure': bool(cookie.get('secure', False)),
            'httpOnly': bool(cookie.get('httpOnly', False)),
        }
        same_site = cookie.get('sameSite')
        if same_site in ('Strict', 'Lax', 'None'):
            params['sameSite'] = same_site
        expires = cookie.get('expires') or cookie.get('expirationDate') or 0
        try:
            expires = float(expires)
        except (TypeError, ValueError):
            expires = 0
        if expires > 0:
            params['expires'] = expires
        try:
            driver.execute_cdp_cmd('Network.setCookie', params)
            placed += 1
        except Exception:
            pass
    return placed


def apply_storage(driver, origin, snapshot):
    driver.get(origin)
    time.sleep(0.4)
    local_storage = snapshot.get('local_storage') or {}
    session_storage = snapshot.get('session_storage') or {}
    if local_storage:
        driver.execute_script(
            """
            const data = arguments[0];
            for (const key of Object.keys(data)) {
                const value = data[key];
                localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value));
            }
            """,
            local_storage,
        )
    if session_storage:
        driver.execute_script(
            """
            const data = arguments[0];
            for (const key of Object.keys(data)) {
                const value = data[key];
                sessionStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value));
            }
            """,
            session_storage,
        )
    return len(local_storage), len(session_storage)


def read_cookies(driver):
    try:
        payload = driver.execute_cdp_cmd('Network.getAllCookies', {})
        cookies = payload.get('cookies') or []
    except Exception:
        cookies = driver.get_cookies()
    kept = []
    for cookie in cookies:
        domain = (cookie.get('domain') or '').lower()
        if 'bocajuniors' in domain or 'queue-it' in domain:
            kept.append(cookie)
    return kept or cookies


def critical_names(cookies):
    return [
        cookie.get('name')
        for cookie in cookies
        if any(key in (cookie.get('name') or '').lower() for key in CRITICAL)
    ]


def save_final(cookies, final_url, source_label):
    cookie_string = '; '.join(
        f"{cookie.get('name')}={cookie.get('value')}"
        for cookie in cookies
        if cookie.get('name')
    )
    record = {
        'timestamp': datetime.now().isoformat(),
        'url': final_url,
        'source': source_label,
        'cookies': cookies,
        'cookie_string': cookie_string,
    }
    downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
    paths = [
        os.path.abspath('boca_cookies_final.json'),
        os.path.join(downloads, 'boca_cookies_final.json'),
    ]
    seen = set()
    written = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(record, handle, indent=2, ensure_ascii=False)
        written.append(path)
    return record, written


def upload_final(record):
    response = requests.post(
        f'{WORKER_URL}/api/cookies',
        json={
            'cookies': record['cookies'],
            'cookie_string': record['cookie_string'],
            'local_storage': {},
            'evento': 868,
            'source': 'abrir-418-final',
            'active': True,
        },
        headers={'X-API-Key': WORKER_API_KEY, 'Content-Type': 'application/json'},
        timeout=15,
    )
    if not response.ok:
        print(f'Worker no guardo las finales: HTTP {response.status_code}')
        return False
    print('Finales subidas a /api/cookies/latest')
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Abrir Chrome con una captura 418 y completar el redirect')
    parser.add_argument('--file', default=None, help='JSON de la captura 418')
    parser.add_argument('--worker', action='store_true', help='Bajar la ultima captura de /api/waf418/latest')
    args = parser.parse_args()

    data, label = load_capture(args.file, args.worker)
    target = redirect_target(data)
    if not target:
        print('ERROR: la captura no tiene la URL del redirect')
        sys.exit(1)
    if data.get('source') == 'prueba-418-no-usar':
        print('ERROR: esa captura es la prueba. No abre el redirect.')
        sys.exit(1)

    user_agent = data.get('user_agent') or ''
    origins = storage_by_origin(data)
    print(f'Redirect: {target[:180]}')
    print(f'Cookies en la captura: {len(data.get("cookies") or [])}')
    print(f'Origenes con storage: {len(origins)}')
    if user_agent:
        print(f'User-Agent: {user_agent[:80]}')

    options = Options()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    if user_agent:
        options.add_argument(f'--user-agent={user_agent}')

    driver = webdriver.Chrome(options=options)
    try:
        placed = inject_cookies(driver, data.get('cookies') or [])
        print(f'Cookies inyectadas: {placed}')
        for origin, snapshot in origins.items():
            local_count, session_count = apply_storage(driver, origin, snapshot)
            print(f'  {origin} localStorage={local_count} sessionStorage={session_count}')

        print('Entrando al redirect...')
        driver.get(target)

        names = []
        cookies = []
        for _ in range(12):
            time.sleep(2)
            cookies = read_cookies(driver)
            names = critical_names(cookies)
            print(f'  ahora: {driver.current_url[:120]} | finales={names or "todavia no"}')
            if names:
                break

        if names:
            record, written = save_final(cookies, driver.current_url, f'abrir-418:{label}')
            for path in written:
                print(f'Guardado: {path}')
            upload_final(record)
        else:
            print('Bocasocios no mando QueueITAccepted / HWWAF / CLID.')
            print('El Chrome queda abierto para ver en que pagina cayo.')

        print('Enter cierra el Chrome.')
        try:
            input()
        except EOFError:
            time.sleep(3600)
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()
