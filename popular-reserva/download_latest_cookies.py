#!/usr/bin/env python3
"""Descarga las ultimas cookies guardadas en el Cloudflare Worker a un archivo JSON
compatible con los scripts de popular (order-popu-familia-rapido.py, etc.).

Uso:
    python download_latest_cookies.py
    python download_latest_cookies.py --token Cangele2015
    python download_latest_cookies.py --output boca_cookies_worker.json
    python download_latest_cookies.py --status
    python download_latest_cookies.py --list
    python download_latest_cookies.py --id ID_DEL_JUEGO
"""
import argparse
from datetime import datetime, timezone
import json
import os
import sys
import time

import requests

DEFAULT_WORKER_URL = 'https://boca-cookies.rosaleseze86.workers.dev'
DEFAULT_ACCESS_CODE = 'Cangele2015'
MAX_AGE_MINUTES = 60


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


def check_queue_status(worker_url: str):
    try:
        r = requests.get(f'{worker_url}/api/queue/status', timeout=10)
        if r.ok:
            return r.json()
    except Exception as e:
        print(f"WARN: No se pudo consultar /api/queue/status: {e}")
    return None


def _auth(code: str, api_key: str):
    headers = {}
    params = {}
    if code:
        headers['X-Access-Code'] = code
        params['code'] = code
    if api_key:
        headers['X-API-Key'] = api_key
    return headers, params


def list_history(worker_url: str, code: str, api_key: str):
    headers, params = _auth(code, api_key)
    print(f"Consultando historial: {worker_url}/api/cookies/history ...")
    try:
        resp = requests.get(f'{worker_url}/api/cookies/history', headers=headers, params=params, timeout=15)
    except Exception as e:
        print(f"WARN: historial no disponible ({e}). La ultima sigue en /api/cookies/latest.")
        return False
    if resp.status_code == 404:
        print("El worker todavia no publica historial. Podes bajar la ultima con el comando de siempre.")
        return False
    if not resp.ok:
        print(f"WARN: historial HTTP {resp.status_code}. La ultima sigue en /api/cookies/latest.")
        return False
    try:
        sets = resp.json().get('sets') or []
    except Exception as e:
        print(f"WARN: historial ilegible ({e}).")
        return False
    if not sets:
        print("Historial vacio. Todavia no entro ningun juego ademas de latest, o el worker es viejo.")
        return True
    print(f"\n{len(sets)} juego(s) guardados (maximo 10, no se bajan si tienen {MAX_AGE_MINUTES} min o mas):")
    for item in sets:
        mark = 'VENCIDA' if item.get('stale') else 'VIGENTE'
        print(
            f"  [{mark}] {item.get('id')} | {item.get('source') or '?'} | "
            f"hace {item.get('age_minutes')} min | criticas={item.get('critical_count')}"
        )
    print("\nBajar una vigente:")
    print("  python download_latest_cookies.py --id ID")
    return True


def download_cookies(worker_url: str, code: str, api_key: str, output_path: str, force: bool = False, item_id: str = None, endpoint: str = None):
    headers, params = _auth(code, api_key)
    if endpoint:
        target = endpoint
    elif item_id:
        target = f'{worker_url}/api/cookies/history/{item_id}'
    else:
        target = f'{worker_url}/api/cookies/latest'

    print(f"Consultando worker: {target} ...")
    try:
        resp = requests.get(target, headers=headers, params=params, timeout=15)
    except Exception as e:
        print(f"ERROR conectando al worker: {e}")
        return False

    if resp.status_code == 403:
        print(f"ERROR: Codigo de acceso invalido (HTTP 403).")
        print(f"Pasa el token con --token TU_CODIGO o configura setx WORKER_ACCESS_CODE \"...\"")
        return False
    elif resp.status_code == 404:
        if item_id:
            print(f"ERROR: no esta el juego {item_id} (HTTP 404).")
            print("Mira los ids con: python download_latest_cookies.py --list")
        else:
            if 'waf418' in target:
                print("ERROR: todavia no hay capturas 418 en el worker (HTTP 404).")
            else:
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
        if age_minutes >= MAX_AGE_MINUTES and not force:
            print(f"  NO SE GUARDAN: tienen {age_minutes} min (maximo {MAX_AGE_MINUTES}).")
            print("  --list muestra las otras. --force las baja igual.")
            list_history(worker_url, code, api_key)
            return False
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
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

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
        '--queue', action='store_true',
        help='Ver estado de la fila reportado por el bot en la otra PC'
    )
    parser.add_argument(
        '--watch', action='store_true',
        help='Monitorear en vivo cada 4 segundos hasta que pasen la fila'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Guardar aunque las cookies tengan 60 minutos o mas'
    )
    parser.add_argument(
        '--list', action='store_true',
        help='Mostrar los juegos guardados en el worker (maximo 10) sin descargar'
    )
    parser.add_argument(
        '--id', dest='item_id', default=None,
        help='Bajar un juego puntual del historial en vez del ultimo'
    )
    parser.add_argument(
        '--waf418', action='store_true',
        help='Bajar la ultima captura del 418 (cola aparte, no pisa la cookie normal)'
    )
    parser.add_argument(
        '--url', default=DEFAULT_WORKER_URL,
        help=f'URL base del worker (default: {DEFAULT_WORKER_URL})'
    )
    args = parser.parse_args()

    code, api_key = get_credentials(args.code)

    if args.list:
        ok = list_history(args.url, code, api_key)
        sys.exit(0 if ok else 1)

    if args.watch:
        print(f"[*] Monitoreando estado de la fila en vivo desde {args.url} (Ctrl+C para salir)...")
        last_reported_passed = 0
        try:
            while True:
                q = check_queue_status(args.url)
                now_str = datetime.now().strftime('%H:%M:%S')
                has_data = q and ('best_time_minutes' in q or 'best_time' in q or q.get('total_sessions') is not None)
                if not has_data:
                    print(f"[{now_str}] Esperando reporte del bot en la otra PC...")
                else:
                    online = q.get('online', False)
                    best_t = q.get('best_time_minutes') if q.get('best_time_minutes') is not None else q.get('best_time')
                    avg_t = q.get('avg_time_minutes') if q.get('avg_time_minutes') is not None else q.get('avg_time')
                    act_s = q.get('active_sessions', 0)
                    tot_s = q.get('total_sessions', 0)
                    pass_s = q.get('passed_sessions', 0)
                    age_s = q.get('age_seconds', 0)

                    status_str = "ONLINE" if online else f"OFFLINE (hace {age_s}s)"
                    best_str = f"{best_t} min" if best_t is not None else "calculando..."
                    avg_str = f"{avg_t} min" if avg_t is not None else "N/A"

                    print(f"[{now_str}] Bot: {status_str} | 🏆 Mejor: {best_str} | Prom: {avg_str} | Sesiones: {act_s}/{tot_s} | Pasadas: {pass_s}")

                    if pass_s > last_reported_passed:
                        print(f"\n🎉 ¡ALERTA! {pass_s} sesion(es) pasaron la fila. Descargando cookies automaticamente...")
                        download_cookies(args.url, code, api_key, args.output, force=True)
                        last_reported_passed = pass_s
                time.sleep(4)
        except KeyboardInterrupt:
            print("\nMonitoreo finalizado.")
            sys.exit(0)

    if args.queue:
        q = check_queue_status(args.url)
        has_data = q and ('best_time_minutes' in q or 'best_time' in q or q.get('total_sessions') is not None)
        if not has_data:
            print("No hay telemetria de cola activa todavia en el Worker.")
            print("Asegurate de haber iniciado queue_bot.py en la otra PC.")
            sys.exit(0)
        print("=== Monitoreo de Fila en Vivo (Bot en otra PC) ===")
        age_s = q.get('age_seconds', 0)
        if q.get('online'):
            best_t = q.get('best_time_minutes') if q.get('best_time_minutes') is not None else q.get('best_time')
            avg_t = q.get('avg_time_minutes') if q.get('avg_time_minutes') is not None else q.get('avg_time')
            best_str = f"{best_t} min" if best_t is not None else "Calculando..."
            avg_str = f"{avg_t} min" if avg_t is not None else "N/A"
            print(f"  Estado del Bot:      ONLINE (Reporte hace {age_s}s)")
            print(f"  🏆 Mejor Tiempo:     {best_str}")
            print(f"  Tiempo Promedio:     {avg_str}")
            print(f"  Sesiones:            {q.get('active_sessions', 0)} activas / {q.get('total_sessions', 0)} total")
            print(f"  Ya Pasaron la Fila:  {q.get('passed_sessions', 0)}")
        else:
            print(f"  Estado del Bot:      OFFLINE (Ultimo reporte hace {age_s}s)")
        sys.exit(0)

    if args.status:
        st = check_status(args.url)
        if not st:
            print("ERROR: No se pudo obtener respuesta del Worker.")
            sys.exit(1)

        print("=== Estado de Cookies en el Worker ===")
        if not st.get('has_cookies'):
            print("  Estado:              VACIO (No hay cookies subidas)")
        else:
            updated_at = st.get('updated_at', '')
            age_mins = st.get('age_minutes', 0)
            crit = st.get('critical_count', 0)
            evento = st.get('evento') or 'No especificado'

            # Formato de tiempo local legible
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
            print(f"  Evento NID:          {evento}")
            print(f"  Cookies Criticas:    {crit}")

            if age_mins < 15:
                print(f"  Vigencia:            EXCELENTE (Frescas)")
            elif age_mins <= 75:
                print(f"  Vigencia:            VIGENTES (Validas para operar)")
            else:
                print(f"  Vigencia:            VENCIDAS / EXPIRADAS (Tienen mas de 75 min)")

        queue_info = st.get('queue')
        print("\n=== Monitoreo de Fila en Vivo (Bot en otra PC) ===")
        if queue_info and (queue_info.get('best_time') is not None or queue_info.get('total_sessions') is not None):
            age_s = queue_info.get('age_seconds', 0)
            if queue_info.get('online'):
                best_t = queue_info.get('best_time')
                avg_t = queue_info.get('avg_time')
                act_s = queue_info.get('active_sessions', 0)
                tot_s = queue_info.get('total_sessions', 0)
                pass_s = queue_info.get('passed_sessions', 0)

                best_str = f"{best_t} min" if best_t is not None else "Calculando..."
                avg_str = f"{avg_t} min" if avg_t is not None else "N/A"

                print(f"  Estado del Bot:      ONLINE (Reporte hace {age_s}s)")
                print(f"  🏆 Mejor Tiempo:     {best_str}")
                print(f"  Tiempo Promedio:     {avg_str}")
                print(f"  Sesiones:            {act_s} activas / {tot_s} total")
                print(f"  Ya Pasaron la Fila:  {pass_s}")
            else:
                print(f"  Estado del Bot:      OFFLINE (Ultimo reporte hace {age_s}s)")
        else:
            print("  Estado del Bot:      SIN REPORTES (El bot aun no inicio o no envio heartbeat)")

        sys.exit(0)

    endpoint = None
    output_path = args.output
    force = args.force
    if args.waf418:
        endpoint = f'{args.url}/api/waf418/latest'
        force = True
        if output_path == 'boca_cookies_worker.json':
            output_path = 'boca_cookies_418.json'

    ok = download_cookies(
        worker_url=args.url,
        code=code,
        api_key=api_key,
        output_path=output_path,
        force=force,
        item_id=args.item_id,
        endpoint=endpoint,
    )
    if not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
