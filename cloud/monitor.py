#!/usr/bin/env python3
"""cloud/monitor.py
Monitorea la fila de Queue-it en vivo desde el Worker de Cloudflare
y descarga automaticamente las cookies en cuanto una sesion pasa la cola.

Uso:
    python cloud/monitor.py --watch    # En vivo cada 4s (descarga sola cuando pasa)
    python cloud/monitor.py --queue    # Ver solo la cola ahora
    python cloud/monitor.py --status   # Ver cola + estado de cookies
    python cloud/monitor.py --download # Descargar cookies ahora
"""

import argparse
from datetime import datetime
import json
import os
import sys
import time
import requests

DEFAULT_WORKER_URL = 'https://boca-cookies.rosaleseze86.workers.dev'
DEFAULT_ACCESS_CODE = 'Cangele2015'
DEFAULT_API_KEY = '6HHGGVfCch0U80-3kfBZS5e8EbmeiEKE5kTea8FWn1o'


def get_downloads_dir() -> str:
    """Retorna la ruta de la carpeta Downloads del usuario actual en Windows/Mac/Linux"""
    home = os.path.expanduser('~')
    win_dl = os.path.join(home, 'Downloads')
    if os.path.isdir(win_dl):
        return win_dl
    return os.getcwd()


def check_queue(worker_url: str):
    try:
        r = requests.get(f'{worker_url}/api/queue/status', timeout=8)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return None


def check_status(worker_url: str):
    try:
        r = requests.get(f'{worker_url}/api/cookies/status', timeout=8)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return None


def download_cookies(worker_url: str, code: str = DEFAULT_ACCESS_CODE, api_key: str = DEFAULT_API_KEY):
    headers = {}
    if code:
        headers['X-Access-Code'] = code
    if api_key:
        headers['X-API-Key'] = api_key

    params = {'code': code} if code else {}

    print(f"[*] Descargando cookies desde {worker_url}/api/cookies/latest ...")
    try:
        resp = requests.get(f'{worker_url}/api/cookies/latest', headers=headers, params=params, timeout=15)
    except Exception as e:
        print(f"[ERROR] Conectando al Worker: {e}")
        return False

    if resp.status_code == 403:
        print("[ERROR] Codigo de acceso invalido (HTTP 403).")
        return False
    elif resp.status_code == 404:
        print("[AVISO] No hay cookies guardadas todavia en el Worker.")
        return False
    elif not resp.ok:
        print(f"[ERROR] HTTP {resp.status_code}: {resp.text}")
        return False

    data = resp.json()
    cookies_list = data.get('cookies') or []
    if not cookies_list:
        print("[AVISO] El Worker no devolvio cookies validas.")
        return False

    # Guardar en dos destinos clave para que order-popu lo detecte de inmediato:
    # 1. En Downloads con nombre boca_cookies_worker.json
    # 2. En popular-reserva/boca_cookies_worker.json
    paths_to_save = []
    dl_file = os.path.join(get_downloads_dir(), 'boca_cookies_worker.json')
    paths_to_save.append(dl_file)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    popu_dir = os.path.join(root_dir, 'popular-reserva')
    if os.path.isdir(popu_dir):
        paths_to_save.append(os.path.join(popu_dir, 'boca_cookies_worker.json'))

    for p in paths_to_save:
        try:
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(cookies_list, f, indent=2)
            print(f"[OK] Cookies guardadas en: {p}")
        except Exception as e:
            print(f"[WARN] No se pudo guardar en {p}: {e}")

    print(f"[LISTO] Total cookies guardadas: {len(cookies_list)}.")
    return True


def watch_loop(worker_url: str):
    print(f"[*] Monitoreando estado de la fila en vivo desde {worker_url}")
    print("[*] Presiona Ctrl+C para salir.\n")
    last_passed = 0

    try:
        while True:
            q = check_queue(worker_url)
            now_str = datetime.now().strftime('%H:%M:%S')

            if not q or ('best_time_minutes' not in q and 'best_time' not in q and q.get('total_sessions') is None):
                print(f"[{now_str}] Esperando primer reporte del bot en la otra PC...")
            else:
                online = q.get('online', False)
                best_t = q.get('best_time_minutes') if q.get('best_time_minutes') is not None else q.get('best_time')
                avg_t = q.get('avg_time_minutes') if q.get('avg_time_minutes') is not None else q.get('avg_time')
                act_s = q.get('active_sessions', 0)
                tot_s = q.get('total_sessions', 0)
                pass_s = q.get('passed_sessions', 0)
                age_s = q.get('age_seconds', 0)

                bot_status = "ONLINE" if online else f"OFFLINE (hace {age_s}s)"
                best_str = f"{best_t} min" if best_t is not None else "calculando..."
                avg_str = f"{avg_t} min" if avg_t is not None else "N/A"

                print(f"[{now_str}] Bot: {bot_status:<16} | MEJOR: {best_str:<10} | Promedio: {avg_str:<8} | Sesiones: {act_s}/{tot_s} | Pasadas: {pass_s}")

                if pass_s > last_passed:
                    print(f"\n[ALERTA] !!! {pass_s} sesion(es) pasaron la fila !!!")
                    print("[*] Descargando cookies automaticamente a tu PC...")
                    download_cookies(worker_url)
                    last_passed = pass_s
                    print("[LISTO] Ya podes ejecutar tu script de reserva en popular-reserva!\n")

            time.sleep(4)
    except KeyboardInterrupt:
        print("\nMonitoreo finalizado.")


def print_queue_info(worker_url: str):
    q = check_queue(worker_url)
    if not q or ('best_time_minutes' not in q and 'best_time' not in q and q.get('total_sessions') is None):
        print("No hay telemetria de cola activa todavia en el Worker.")
        print("Asegurate de haber iniciado el bot en la otra PC.")
        return

    online = q.get('online', False)
    best_t = q.get('best_time_minutes') if q.get('best_time_minutes') is not None else q.get('best_time')
    avg_t = q.get('avg_time_minutes') if q.get('avg_time_minutes') is not None else q.get('avg_time')
    age_s = q.get('age_seconds', 0)

    best_str = f"{best_t} min" if best_t is not None else "Calculando..."
    avg_str = f"{avg_t} min" if avg_t is not None else "N/A"

    print("\n=== Monitoreo de Fila en Vivo (Bot en otra PC) ===")
    status_label = f"ONLINE (Reporte hace {age_s}s)" if online else f"OFFLINE (Ultimo reporte hace {age_s}s)"
    print(f"  Estado del Bot:      {status_label}")
    print(f"  Mejor Tiempo:        {best_str}")
    print(f"  Tiempo Promedio:     {avg_str}")
    print(f"  Sesiones Activas:    {q.get('active_sessions', 0)} / {q.get('total_sessions', 0)}")
    print(f"  Ya Pasaron la Fila:  {q.get('passed_sessions', 0)}\n")


def print_status_info(worker_url: str):
    st = check_status(worker_url)
    if not st:
        print("[ERROR] No se pudo conectar al Worker.")
        return

    print("\n=== Estado de Cookies en el Worker ===")
    if not st.get('has_cookies'):
        print("  Estado:              VACIO (No hay cookies subidas)")
    else:
        updated_at = st.get('updated_at', '')
        age_mins = st.get('age_minutes', 0)
        crit = st.get('critical_count', 0)

        tiempo_local = updated_at
        try:
            ts = updated_at.replace('Z', '+00:00')
            dt_utc = datetime.fromisoformat(ts)
            dt_local = dt_utc.astimezone()
            tiempo_local = dt_local.strftime('%Y-%m-%d %H:%M:%S (%Z)')
        except Exception:
            pass

        print(f"  Generadas / Subidas: {tiempo_local}")
        print(f"  Antiguedad:          Hace {age_mins} minutos")
        print(f"  Cookies Criticas:    {crit}")

        if age_mins < 15:
            vig = "EXCELENTE (Frescas)"
        elif age_mins <= 75:
            vig = "VIGENTES (Validas para operar)"
        else:
            vig = "EXPIRADAS (Tienen mas de 75 min)"
        print(f"  Vigencia:            {vig}")

    print_queue_info(worker_url)


def main():
    parser = argparse.ArgumentParser(description='Monitoreo y descarga de cookies en la nube')
    parser.add_argument('--watch', action='store_true', help='Monitorear en vivo cada 4 segundos')
    parser.add_argument('--queue', action='store_true', help='Ver solo el estado de la fila actual')
    parser.add_argument('--status', action='store_true', help='Ver estado completo (cookies + fila)')
    parser.add_argument('--download', action='store_true', help='Descargar cookies ahora')
    parser.add_argument('--url', default=DEFAULT_WORKER_URL, help=f'URL del Worker (default: {DEFAULT_WORKER_URL})')

    args = parser.parse_args()

    if args.watch:
        watch_loop(args.url)
    elif args.queue:
        print_queue_info(args.url)
    elif args.download:
        download_cookies(args.url)
    else:
        print_status_info(args.url)


if __name__ == '__main__':
    main()
