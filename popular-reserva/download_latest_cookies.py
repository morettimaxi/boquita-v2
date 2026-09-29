#!/usr/bin/env python3
"""Descarga las ultimas cookies guardadas en el Cloudflare Worker a un archivo JSON
compatible con los scripts de popular (order-popu-familia-rapido.py, etc.).

Uso:
    python download_latest_cookies.py
    python download_latest_cookies.py --token Cangele2015
    python download_latest_cookies.py --output boca_cookies_worker.json
    python download_latest_cookies.py --status
"""
import argparse
from datetime import datetime, timezone
import json
import os
import sys

import requests

DEFAULT_WORKER_URL = 'https://boca-cookies.rosaleseze86.workers.dev'
DEFAULT_ACCESS_CODE = 'Cangele2015'


def _read_env_or_reg(var_name: str, fallback: str = '') -> str:
    val = os.environ.get(var_name, '').strip()
    if val or os.name != 'nt':
        return val or fallback
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k:
            return str(winreg.QueryValueEx(k, var_name)[0]).strip() or fallback
    except OSError:
        return fallback


def get_credentials(cli_code: str = None):
    code = cli_code or _read_env_or_reg('WORKER_ACCESS_CODE') or _read_env_or_reg('WORKER_TOKEN') or DEFAULT_ACCESS_CODE
    api_key = _read_env_or_reg('WORKER_API_KEY', '')
    return code, api_key


def check_status(worker_url: str):
    try:
        r = requests.get(f'{worker_url}/api/cookies/status', timeout=10)
        if r.ok:
            return r.json()
    except Exception as e:
        print(f"WARN: No se pudo consultar /api/cookies/status: {e}")
    return None


def download_cookies(worker_url: str, code: str, api_key: str, output_path: str, force: bool = False):
    headers = {}
    if code:
        headers['X-Access-Code'] = code
    if api_key:
        headers['X-API-Key'] = api_key

    params = {}
    if code:
        params['code'] = code

    print(f"Consultando worker: {worker_url}/api/cookies/latest ...")
    try:
        resp = requests.get(f'{worker_url}/api/cookies/latest', headers=headers, params=params, timeout=15)
    except Exception as e:
        print(f"ERROR conectando al worker: {e}")
        return False

    if resp.status_code == 403:
        print(f"ERROR: Codigo de acceso invalido (HTTP 403).")
        print(f"Pasa el token con --token TU_CODIGO o configura setx WORKER_ACCESS_CODE \"...\"")
        return False
    elif resp.status_code == 404:
        print(f"ERROR: No hay cookies guardadas en el worker todavia (HTTP 404).")
        print(f"Ejecuta primero el queue_bot o un upload.")
        return False
    elif not resp.ok:
        print(f"ERROR HTTP {resp.status_code}: {resp.text}")
        return False

    try:
        data = resp.json()
    except Exception as e:
        print(f"ERROR parseando respuesta JSON: {e}")
        return False

    cookies = data.get('cookies', [])
    cookie_string = data.get('cookie_string', '')
    updated_at_str = data.get('updated_at', '')
    critical_cookies = data.get('critical_cookies', [])

    # Si por alguna razon cookie_string viene vacio pero hay cookies, lo reconstruimos
    if not cookie_string and cookies:
        cookie_string = '; '.join(
            f"{c.get('name')}={c.get('value')}"
            for c in cookies
            if c.get('name') and c.get('value') is not None
        )
        data['cookie_string'] = cookie_string

    if not cookie_string:
        print("ERROR: La respuesta del worker no contiene cookies validas.")
        return False

    # Calcular antiguedad
    age_minutes = None
    if updated_at_str:
        try:
            # Soportar ISO formats
            ts = updated_at_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(ts)
            now = datetime.now(timezone.utc)
            delta = now - dt
            age_minutes = int(delta.total_seconds() // 60)
        except Exception:
            pass

    has_queueit = any(
        c.get('name', '').startswith('QueueITAccepted')
        for c in (critical_cookies or cookies)
    ) or ('QueueITAccepted' in cookie_string)

    print("\n--- Informacion de Cookies del Worker ---")
    print(f"  Fuente:            {data.get('source', 'desconocida')}")
    print(f"  Evento NID:        {data.get('evento', 'N/A')}")
    print(f"  Total cookies:     {len(cookies)}")
    print(f"  Criticas:          {len(critical_cookies)}")
    print(f"  Tiene Queue-it:    {'SI (QueueITAccepted)' if has_queueit else 'NO'}")
    if age_minutes is not None:
        print(f"  Subidas hace:      {age_minutes} minutos ({updated_at_str})")
        if age_minutes > 80:
            print(f"  AVISO: Tienen mas de 80 minutos. Queue-it suele expirar a los ~80-90 min.")
            if not force:
                print("  (Podes usar --force si queres guardarlas de todos modos)")
    else:
        print(f"  Actualizadas:      {updated_at_str}")

    # Guardar archivo en formato 100% compatible en Downloads y en carpeta local
    saved_paths = []
    downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
    target_paths = [output_path]

    # Si output_path es relativo, tambien guardamos en Downloads
    if not os.path.isabs(output_path):
        target_paths.append(os.path.join(downloads_dir, os.path.basename(output_path)))

    # Quitar duplicados preservando orden
    seen = set()
    unique_targets = []
    for p in target_paths:
        abs_p = os.path.abspath(p)
        if abs_p not in seen:
            seen.add(abs_p)
            unique_targets.append(p)

    for p in unique_targets:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            saved_paths.append(os.path.abspath(p))
        except Exception as e:
            print(f"WARN guardando en {p}: {e}")

    if not saved_paths:
        print(f"ERROR guardando archivo de cookies.")
        return False

    print("\nGuardado exitoso en:")
    for sp in saved_paths:
        print(f"  -> {sp}")

    print("\nPara correr popular usando este archivo:")
    print(f"  python order-popu-familia-rapido.py --evento {data.get('evento') or 870} --cookies {output_path}")
    print("  (O directo sin --cookies, ya que toma boca_cookies*.json mas nuevo automaticamente)")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Descarga las ultimas cookies del Cloudflare Worker a un archivo compatible con scripts de popular'
    )
    parser.add_argument(
        '--token', '--code', dest='code', default=None,
        help='Codigo de acceso / token al worker (default: WORKER_ACCESS_CODE o Cangele2015)'
    )
    parser.add_argument(
        '--output', '-o', default='boca_cookies_worker.json',
        help='Ruta del archivo de salida (default: boca_cookies_worker.json)'
    )
    parser.add_argument(
        '--status', action='store_true',
        help='Solo consultar el estado en el worker sin descargar archivo'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Guardar aunque las cookies parezcan antiguas'
    )
    parser.add_argument(
        '--url', default=DEFAULT_WORKER_URL,
        help=f'URL base del worker (default: {DEFAULT_WORKER_URL})'
    )
    args = parser.parse_args()

    code, api_key = get_credentials(args.code)

    if args.status:
        st = check_status(args.url)
        if st:
            print("Estado del Worker:")
            print(json.dumps(st, indent=2))
        sys.exit(0)

    ok = download_cookies(
        worker_url=args.url,
        code=code,
        api_key=api_key,
        output_path=args.output,
        force=args.force
    )
    if not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
