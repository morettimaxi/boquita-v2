#!/usr/bin/env python3
"""Misma cola que queue_bot.py.

Cuando una sesion recibe HTTP 418 al ir a bocasocios, sube en el momento
cookies (incluye HttpOnly), localStorage y sessionStorage a una cola aparte
del Worker: POST /api/waf418.

No pisa /api/cookies/latest. queue_bot.py queda igual.

Uso:
    python queue_bot_418.py
"""
import json
import logging
import os
import re
import socket
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

import requests as http_requests

import queue_bot

class _SinLogsNet(logging.Filter):
    def filter(self, record):
        return '[NET]' not in record.getMessage()

queue_bot.logger.addFilter(_SinLogsNet())

STORAGE_ORIGINS = (
    'https://bocasocios.bocajuniors.com.ar',
    'https://bocasocios-gw.bocajuniors.com.ar',
    'https://www.bocajuniors.com.ar',
)


class Waf418SessionManager(queue_bot.SessionManager):
    def capture_network_tokens(self):
        wrapped = []
        for session in self.sessions:
            driver = session.get('driver')
            if not driver or not hasattr(driver, 'get_log'):
                continue
            original = driver.get_log

            def spy(kind, _original=original, _session=session):
                logs = _original(kind)
                if kind == 'performance':
                    self._catch_418(_session, logs)
                return logs

            driver.get_log = spy
            wrapped.append((driver, original))
        try:
            super().capture_network_tokens()
        finally:
            for driver, original in wrapped:
                driver.get_log = original

    def _catch_418(self, session, logs):
        if session.get('waf418_uploaded'):
            return
        hit_url = None
        hit_headers = {}
        for log_entry in logs or []:
            try:
                message = json.loads(log_entry.get('message') or '{}')
                payload = message.get('message', {})
                if payload.get('method') != 'Network.responseReceived':
                    continue
                response = payload.get('params', {}).get('response', {})
                url = response.get('url') or ''
                if response.get('status') == 418 and 'bocajuniors' in url:
                    hit_url = url
                    hit_headers = response.get('headers') or {}
                    break
            except Exception:
                continue
        if not hit_url:
            return
        queue_bot.logger.info(f"418 en sesion {session['id']}: {hit_url[:180]}")
        self._upload_418(session, hit_url, hit_headers)

    def _origin_of(self, url):
        try:
            parsed = urlparse(url or '')
        except Exception:
            return ''
        if parsed.scheme in ('http', 'https') and parsed.netloc:
            return f'{parsed.scheme}://{parsed.netloc}'
        return ''

    def _read_page_storage(self, driver):
        local_storage = {}
        session_storage = {}
        try:
            local_storage = driver.execute_script(
                "let ls={}; for (let i=0;i<localStorage.length;i++){let k=localStorage.key(i); ls[k]=localStorage.getItem(k);} return ls;"
            ) or {}
        except Exception:
            pass
        try:
            session_storage = driver.execute_script(
                "let ss={}; for (let i=0;i<sessionStorage.length;i++){let k=sessionStorage.key(i); ss[k]=sessionStorage.getItem(k);} return ss;"
            ) or {}
        except Exception:
            pass
        return local_storage, session_storage

    def _read_origin_storage(self, driver, origin):
        found = {'local_storage': {}, 'session_storage': {}}
        for is_local, key in ((True, 'local_storage'), (False, 'session_storage')):
            try:
                result = driver.execute_cdp_cmd('DOMStorage.getDOMStorageItems', {
                    'storageId': {
                        'securityOrigin': origin,
                        'isLocalStorage': is_local,
                    },
                })
            except Exception:
                continue
            items = {}
            for pair in result.get('entries') or []:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    items[str(pair[0])] = pair[1]
            found[key] = items
        return found

    def _upload_418(self, session, url, response_headers=None):
        driver = session.get('driver')
        if not driver:
            return
        try:
            try:
                cdp = driver.execute_cdp_cmd('Network.getAllCookies', {})
                cookies = cdp.get('cookies', [])
            except Exception:
                cookies = driver.get_cookies()
        except Exception as error:
            queue_bot.logger.warning(f"418 sesion {session['id']}: no pude leer cookies: {error}")
            return

        page_url = ''
        try:
            page_url = driver.current_url or ''
        except Exception:
            pass

        user_agent = session.get('user_agent') or ''
        if not user_agent:
            try:
                user_agent = driver.execute_script('return navigator.userAgent') or ''
            except Exception:
                pass

        local_storage, session_storage = self._read_page_storage(driver)
        try:
            driver.execute_cdp_cmd('DOMStorage.enable', {})
        except Exception:
            pass

        origins = {}
        page_origin = self._origin_of(page_url)
        if page_origin:
            origins[page_origin] = {
                'local_storage': local_storage,
                'session_storage': session_storage,
            }
        extra_origins = set(STORAGE_ORIGINS)
        extra_origins.add(self._origin_of(url))
        for cookie in cookies:
            domain = (cookie.get('domain') or '').lstrip('.')
            if 'bocajuniors' in domain or 'queue-it' in domain:
                extra_origins.add(f'https://{domain}')
        for origin in extra_origins:
            if not origin or origin in origins:
                continue
            snapshot = self._read_origin_storage(driver, origin)
            if snapshot['local_storage'] or snapshot['session_storage']:
                origins[origin] = snapshot

        relevant = []
        for cookie in cookies:
            domain = (cookie.get('domain') or '').lower()
            if 'bocajuniors' in domain or 'queue-it' in domain or 'cloudflare' in domain:
                relevant.append(cookie)
        if relevant:
            cookies = relevant

        cookie_string = '; '.join(
            f"{c.get('name')}={c.get('value')}" for c in cookies if c.get('name')
        )
        record = {
            'session_id': session['id'],
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'page_url': page_url,
            'user_agent': user_agent,
            'status': 418,
            'response_headers': response_headers or {},
            'cookies': cookies,
            'cookie_string': cookie_string,
            'local_storage': local_storage,
            'session_storage': session_storage,
            'origins': origins,
        }
        try:
            with open(f"session_{session['id']}_418.json", 'w', encoding='utf-8') as handle:
                json.dump(record, handle, indent=2)
        except Exception as error:
            queue_bot.logger.warning(f"418 sesion {session['id']}: no pude guardar el JSON local: {error}")

        queue_bot.logger.info(
            f"418 sesion {session['id']}: intentando subir a /api/waf418 "
            f"({len(cookies)} cookies, origenes={len(origins)}, "
            f"localStorage={len(local_storage)}, sessionStorage={len(session_storage)})"
        )
        try:
            response = http_requests.post(
                f"{queue_bot.WORKER_URL}/api/waf418",
                json={
                    'cookies': cookies,
                    'cookie_string': cookie_string,
                    'local_storage': local_storage,
                    'session_storage': session_storage,
                    'origins': origins,
                    'url': url,
                    'page_url': page_url,
                    'user_agent': user_agent,
                    'response_headers': response_headers or {},
                    'source': f"queue-bot-418-session-{session['id']}",
                    'evento': 868,
                },
                headers={
                    'X-API-Key': queue_bot.WORKER_API_KEY,
                    'Content-Type': 'application/json',
                },
                timeout=10,
            )
        except Exception as error:
            queue_bot.logger.warning(f"418 sesion {session['id']}: Worker no respondio: {error}")
            return

        if not response.ok:
            queue_bot.logger.warning(
                f"418 sesion {session['id']}: Worker FALLO HTTP {response.status_code}"
            )
            return

        session['waf418_uploaded'] = True
        queue_bot.logger.info(
            f"418 sesion {session['id']} -> cola waf418 OK "
            f"({len(cookies)} cookies, origenes={len(origins)}, "
            f"localStorage={len(local_storage)}, sessionStorage={len(session_storage)})"
        )

    def _upload_to_worker(self, session_id, cookies, cookie_string, local_storage):
        queue_bot.logger.info(
            f"Sesion {session_id}: intentando subir cookies a /api/cookies "
            f"({len(cookies)} cookies, localStorage={len(local_storage or {})})"
        )
        return super()._upload_to_worker(session_id, cookies, cookie_string, local_storage)

    def _refresh_live_times(self):
        for session in list(self.sessions):
            driver = session.get('driver')
            previous = session.get('wait_time')
            if not driver or previous is None:
                continue
            try:
                if not driver.service.is_connectable():
                    queue_bot.logger.warning(
                        f"Sesion {session['id']}: Chrome cerrado, no pude validar el tiempo"
                    )
                    continue
                url = driver.current_url or ''
                if 'queueittoken=' in url or '/queueit/redirect' in url or 'bocasocios.bocajuniors.com.ar' in url:
                    queue_bot.logger.info(
                        f"Sesion {session['id']}: ya salio de la fila, no refresco ({url[:140]})"
                    )
                    continue
                driver.refresh()
                time.sleep(1.5)
                text = driver.execute_script(
                    "var el=document.getElementById('MainPart_lbWhichIsIn');"
                    "return el ? (el.innerText || el.textContent || '') : '';"
                ) or ''
                text = str(text).strip()
            except Exception as error:
                queue_bot.logger.warning(
                    f"Sesion {session['id']}: no pude validar el tiempo: {error}"
                )
                continue

            low = text.lower()
            new_time = None
            if any(phrase in low for phrase in ('más de una hora', 'mas de una hora', 'more than an hour', 'over an hour')):
                new_time = 65
            else:
                match = re.search(r'(\d+)', text)
                if match:
                    value = int(match.group(1))
                    if 0 <= value <= 180:
                        new_time = value
            if new_time is None:
                queue_bot.logger.info(
                    f"Sesion {session['id']}: la pagina no dice minutos ('{text[:80]}'), dejo {previous}"
                )
                continue
            session['wait_time'] = new_time
            session['raw_time_text'] = text
            session['last_update'] = datetime.now()
            queue_bot.logger.info(
                f"Sesion {session['id']}: tiempo real {new_time} min (antes {previous})"
            )


queue_bot.SessionManager = Waf418SessionManager

SERVER_NAME = os.environ.get('QUEUE_SERVER_NAME') or socket.gethostname()
REPORT_EVERY_SECONDS = 120


def _report_queue_once():
    manager = queue_bot.session_manager
    if not manager or not manager.sessions:
        return
    timed = [session for session in manager.sessions if session.get('wait_time') is not None]
    if not timed:
        return
    manager._refresh_live_times()
    stats = manager.get_stats()
    passed = sum(
        1 for session in manager.sessions
        if session.get('captured_redirect_url') or session.get('cookies_uploaded') or session.get('waf418_uploaded')
    )
    uploaded = sum(
        1 for session in manager.sessions
        if session.get('cookies_uploaded') or session.get('waf418_uploaded')
    )
    total = len(manager.sessions)
    response = http_requests.post(
        f'{queue_bot.WORKER_URL}/api/queue/heartbeat',
        json={
            'server_name': SERVER_NAME,
            'best_time': stats.get('best_time'),
            'avg_time': round(stats['avg_time'], 1) if stats.get('avg_time') is not None else None,
            'active_sessions': stats.get('active_sessions', 0),
            'total_sessions': total,
            'passed_sessions': passed,
            'cookies_uploaded': uploaded,
            'opening_time': manager.opening_time,
        },
        headers={'X-API-Key': queue_bot.WORKER_API_KEY, 'Content-Type': 'application/json'},
        timeout=10,
    )
    if not response.ok:
        queue_bot.logger.warning(f'Fila {SERVER_NAME}: Worker HTTP {response.status_code}')
        return
    queue_bot.logger.info(
        f'Fila {SERVER_NAME} -> Worker: mejor {stats.get("best_time")} min, '
        f'{total} sesiones, cookies subidas {uploaded}'
    )


def _report_loop():
    while True:
        time.sleep(20)
        try:
            _report_queue_once()
        except Exception as error:
            queue_bot.logger.warning(f'Fila {SERVER_NAME}: no pude reportar: {error}')
        time.sleep(REPORT_EVERY_SECONDS)


threading.Thread(target=_report_loop, daemon=True).start()


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print("=" * 80)
    print("queue_bot_418")
    print("Misma cola que queue_bot.py.")
    print("Si una sesion recibe 418 en bocasocios, sube cookies + localStorage + sessionStorage")
    print("a la cola aparte POST /api/waf418. /api/cookies/latest no se pisa.")
    print(f"Nombre de este servidor: {SERVER_NAME}")
    print("Cada 2 minutos refresca la pagina, lee el tiempo real y lo sube al Worker.")
    print("Avisa en el log cuando intenta subir un 418 o las cookies finales.")
    print("Dashboard: http://localhost:5000")
    print("=" * 80)
    queue_bot.app.run(debug=False, host='0.0.0.0', port=5000)
