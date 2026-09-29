"""
Order Popu Familia - Confirmar titular + grupo familiar (hijos) en un solo POST.

Uso:
  python order-popu-familia.py --evento 870 [--cookies archivo.json] [--dry-run]

Copia de order-popu.py. Arma socioNidEventoSeccionNidsC con TODOS
los socios de /event/confirmation/relativeGroup (como hace la web).
Si no hay familia, confirma solo al titular.
"""

import requests
import json
import csv
import base64
import os
import sys
import time
import argparse
import logging
import glob
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('order-popu-familia-rapido.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

BASE_URL = 'https://bocasocios-gw.bocajuniors.com.ar'
HEADERS_BASE = {
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json',
    'origin': 'https://bocasocios.bocajuniors.com.ar',
    'referer': 'https://bocasocios.bocajuniors.com.ar/',
    'sec-ch-ua': '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'
}

STATUS_FILE = 'order_popu_familia_rapido_status.json'


def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_status(status):
    try:
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error guardando status: {e}")


def load_cookies(cookie_file=None):
    if cookie_file and os.path.exists(cookie_file):
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cookie_str = data.get('cookie_string', '')
            if cookie_str:
                logger.info(f"Cookies cargadas desde {cookie_file}")
                return cookie_str
        except Exception as e:
            logger.warning(f"Error leyendo {cookie_file}: {e}")

    cookie_files = sorted(glob.glob('session_*_cookies.json'), key=os.path.getmtime, reverse=True)
    for cf in cookie_files:
        try:
            with open(cf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cookie_str = data.get('cookie_string', '')
            if cookie_str and 'QueueITAccepted' in cookie_str:
                logger.info(f"Cookies con QueueITAccepted encontradas en {cf}")
                return cookie_str
        except Exception:
            continue

    for cf in cookie_files:
        try:
            with open(cf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cookie_str = data.get('cookie_string', '')
            if cookie_str:
                logger.warning(f"Usando cookies de {cf} (sin QueueITAccepted - puede fallar)")
                return cookie_str
        except Exception:
            continue

    downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
    all_browser_files = []
    for d in ['.', downloads_dir]:
        all_browser_files.extend(glob.glob(os.path.join(d, 'boca_cookies*.json')))

    if all_browser_files:
        all_browser_files.sort(key=os.path.getmtime, reverse=True)
        for bf in all_browser_files:
            try:
                with open(bf, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                cookie_str = data.get('cookie_string', '')
                if cookie_str:
                    logger.info(f"Cookies del browser cargadas desde {bf} (mas reciente)")
                    return cookie_str
            except Exception:
                continue

    logger.warning("No se encontraron archivos de cookies. Continuando sin cookies (puede fallar).")
    return None


def reload_cookies_if_newer(cookie_file, last_cookie_mtime):
    files_to_check = []
    if cookie_file and os.path.exists(cookie_file):
        files_to_check.append(cookie_file)

    downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
    for pattern in ['boca_cookies.json', 'boca_cookies_*.json', 'session_*_cookies.json']:
        files_to_check.extend(glob.glob(pattern))
        files_to_check.extend(glob.glob(os.path.join(downloads_dir, pattern)))

    newest_file = None
    newest_mtime = last_cookie_mtime or 0

    for f in files_to_check:
        try:
            mt = os.path.getmtime(f)
            if mt > newest_mtime:
                newest_mtime = mt
                newest_file = f
        except Exception:
            continue

    if newest_file:
        try:
            with open(newest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cookie_str = data.get('cookie_string', '')
            if cookie_str:
                logger.info(f"Cookies recargadas desde {newest_file} (actualizado)")
                return cookie_str, newest_mtime
        except Exception:
            pass

    return None, last_cookie_mtime


def load_socios(csv_file):
    socios = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get('email', '').strip()
                password = row.get('password', '').strip()
                if email and password:
                    socios.append({'email': email, 'password': password})
        logger.info(f"Cargados {len(socios)} socios desde {csv_file}")
    except FileNotFoundError:
        logger.error(f"Archivo {csv_file} no encontrado")
    except Exception as e:
        logger.error(f"Error leyendo {csv_file}: {e}")
    return socios


def do_login(email, password, cookie_string=None):
    password_b64 = base64.b64encode(password.encode()).decode()

    headers = {**HEADERS_BASE}
    if cookie_string:
        headers['Cookie'] = cookie_string

    try:
        resp = requests.post(
            f'{BASE_URL}/auth/login/baas',
            json={'email': email, 'password': password_b64},
            headers=headers,
            timeout=15
        )

        if resp.status_code == 201:
            data = resp.json()
            token = data.get('token')
            usuario = data.get('usuario', {})
            socio_nid = usuario.get('socioNid')
            socio_numero = usuario.get('socioNumero')
            nombre = f"{usuario.get('nombre', '')} {usuario.get('apellido', '')}".strip()

            logger.info(f"LOGIN OK: {email} -> socioNid={socio_nid} ({nombre})")
            return {
                'success': True,
                'token': token,
                'refresh_token': data.get('refreshToken'),
                'socio_nid': socio_nid,
                'socio_numero': socio_numero,
                'nombre': nombre,
                'email': email
            }
        else:
            logger.error(f"LOGIN FAIL: {email} -> HTTP {resp.status_code}: {resp.text[:200]}")
            return {'success': False, 'email': email, 'error': f"HTTP {resp.status_code}"}

    except Exception as e:
        logger.error(f"LOGIN ERROR: {email} -> {e}")
        return {'success': False, 'email': email, 'error': str(e)}


def _miembro_nombre(socio):
    return f"{socio.get('nombre', '')} {socio.get('apellido', '')}".strip() or f"nid={socio.get('nid')}"


def get_grupo(token, evento_nid, cookie_string=None):
    """POST /event/confirmation/relativeGroup -> todos los socios del grupo familiar."""
    headers = {
        **HEADERS_BASE,
        'Authorization': f'Bearer {token}'
    }
    if cookie_string:
        headers['Cookie'] = cookie_string

    try:
        resp = requests.post(
            f'{BASE_URL}/event/confirmation/relativeGroup',
            json={'eventoNid': str(evento_nid), 'eligeSector': False},
            headers=headers,
            timeout=15
        )

        if resp.status_code not in (200, 201):
            logger.error(f"GRUPO FAIL: HTTP {resp.status_code}: {resp.text[:200]}")
            return {'success': False, 'error': f"HTTP {resp.status_code}"}

        data = resp.json()
        socios_detalle = data.get('sociosConfirmacionDetalle', [])
        if not socios_detalle:
            logger.warning(f"Sin detalle de socios en relativeGroup para evento {evento_nid}")
            return {'success': False, 'error': 'Sin detalle de socios'}

        miembros = []
        for socio in socios_detalle:
            secciones = socio.get('eventoSecciones') or []
            seccion = secciones[0] if secciones else {}
            nombre = _miembro_nombre(socio)
            puede = bool(socio.get('permitirConfirmarConfirmacion'))
            confirmado = bool(socio.get('confirmacionNid') or socio.get('codigoConfirmacion'))
            motivo = socio.get('error') or ''
            if not motivo and socio.get('cumpleCuota') is False:
                motivo = 'no cumple cuota'
            if not motivo and socio.get('penalizado'):
                motivo = 'penalizado'
            miembros.append({
                'socio_nid': socio.get('nid'),
                'nombre': nombre,
                'numero': socio.get('numero'),
                'puede_confirmar': puede,
                'confirmado': confirmado,
                'motivo': motivo,
                'confirmacion_tipo': socio.get('confirmacionWebTipoEnum', -1),
                'con_rotacion': bool(socio.get('conRotacion')),
                'seccion_nid': seccion.get('nid'),
                'seccion_nombre': seccion.get('nombre', ''),
                'seccion_id': seccion.get('id', ''),
            })
            logger.info(
                f"GRUPO: {nombre} nid={socio.get('nid')} seccion={seccion.get('nombre', '?')} "
                f"(nid={seccion.get('nid')}) puede_confirmar={puede} confirmado={confirmado}"
                + (f" motivo={motivo}" if motivo else '')
            )

        return {
            'success': True,
            'miembros': miembros,
            'elige_sector': data.get('eligeSector', False),
            'con_cargo': data.get('conCargo', False),
        }

    except Exception as e:
        logger.error(f"GRUPO ERROR: {e}")
        return {'success': False, 'error': str(e)}


def do_order_grupo(token, evento_nid, miembros, cookie_string=None, cookie_file=None,
                   max_retries=50, retry_wait=20):
    """POST /event/confirmation/order con todos los socios del grupo en un solo body."""
    headers = {
        **HEADERS_BASE,
        'Authorization': f'Bearer {token}'
    }
    if cookie_string:
        headers['Cookie'] = cookie_string

    nids = [m['socio_nid'] for m in miembros]
    nombres = ', '.join(f"{m['nombre']}({m['socio_nid']})" for m in miembros)
    con_rotacion = 1 if any(m.get('con_rotacion') for m in miembros) else 0

    body = {
        'eventoNid': evento_nid,
        'tipoNid': -1,
        'conRotacion': con_rotacion,
        'socioNidEventoSeccionNidsC': [{
            'socioNid': m['socio_nid'],
            'confirmacionWebTipoEnum': m.get('confirmacion_tipo') if m.get('confirmacion_tipo') is not None else -1,
            'adicionalNid': None,
            'eventoSeccionNid': m['seccion_nid']
        } for m in miembros]
    }

    last_cookie_mtime = 0
    logger.info(f"ORDER GRUPO ({len(miembros)}): {nombres}")

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                f'{BASE_URL}/event/confirmation/order',
                json=body,
                headers=headers,
                timeout=15
            )

            if resp.status_code in (200, 201):
                logger.info(f"ORDER OK: nids={nids} -> {resp.status_code} (intento {attempt})")
                return {'success': True, 'socio_nids': nids, 'status': resp.status_code, 'data': resp.text[:300], 'attempts': attempt}

            ya_confirmado = 'ya se encuentra confirmado' in resp.text.lower() or 'ya esta confirmado' in resp.text.lower()
            if resp.status_code == 400 and ya_confirmado:
                logger.info(f"ORDER OK: nids={nids} -> ya estaba confirmado")
                return {'success': True, 'socio_nids': nids, 'status': 400, 'already_confirmed': True, 'attempts': attempt}

            if resp.status_code in (400, 409, 422):
                try:
                    errores = resp.json().get('errores') or []
                except ValueError:
                    errores = []
                motivo = '; '.join(str(e).strip() for e in errores) or resp.text[:200]
                logger.error(f"ORDER RECHAZADO: nids={nids} -> HTTP {resp.status_code}: {motivo} (no se reintenta)")
                return {'success': False, 'socio_nids': nids, 'status': resp.status_code, 'error': motivo, 'attempts': attempt}

            if resp.status_code == 403:
                logger.warning(f"ORDER 403: nids={nids} -> Cola de vuelta. Esperando 60s y recargando cookies... (intento {attempt})")
                time.sleep(60)
                new_cookies, last_cookie_mtime = reload_cookies_if_newer(cookie_file, last_cookie_mtime)
                if new_cookies:
                    cookie_string = new_cookies
                    headers['Cookie'] = cookie_string
                    logger.info(f"Cookies actualizadas para nids={nids}")
                continue

            if resp.status_code == 401:
                logger.warning(f"ORDER 401: nids={nids} -> Token expirado. Esperando 60s... (intento {attempt})")
                time.sleep(60)
                continue

            logger.warning(f"ORDER intento {attempt}/{max_retries}: nids={nids} -> HTTP {resp.status_code}: {resp.text[:200]}")

        except requests.exceptions.Timeout:
            logger.warning(f"ORDER intento {attempt}/{max_retries}: nids={nids} -> TIMEOUT")
        except requests.exceptions.ConnectionError:
            logger.warning(f"ORDER intento {attempt}/{max_retries}: nids={nids} -> CONNECTION ERROR")
        except Exception as e:
            logger.warning(f"ORDER intento {attempt}/{max_retries}: nids={nids} -> {e}")

        if attempt < max_retries:
            logger.info(f"Reintentando en {retry_wait}s... (nids={nids})")
            time.sleep(retry_wait)

    logger.error(f"ORDER AGOTADO: nids={nids} -> {max_retries} intentos fallidos")
    return {'success': False, 'socio_nids': nids, 'error': f'Agotados {max_retries} intentos'}


def process_socio(socio, evento_nid, cookie_string, cookie_file, dry_run):
    email = socio['email']
    password = socio['password']

    def update_status(**kwargs):
        s = load_status()
        entry = s.get(email, {'email': email})
        entry.update(kwargs)
        entry['last_update'] = datetime.now().isoformat()
        s[email] = entry
        save_status(s)

    update_status(state='login', started=datetime.now().isoformat())

    login_result = do_login(email, password, cookie_string)
    if not login_result['success']:
        update_status(state='login_failed', error=login_result.get('error'))
        return {'email': email, 'login': False, 'order': False, 'error': login_result.get('error')}

    token = login_result['token']
    socio_nid = login_result['socio_nid']
    nombre = login_result['nombre']

    update_status(state='logged_in', nombre=nombre, socio_nid=socio_nid)

    update_status(state='getting_grupo')
    grupo = get_grupo(token, evento_nid, cookie_string)
    if not grupo['success']:
        update_status(state='grupo_failed', error=grupo.get('error'))
        return {
            'email': email, 'nombre': nombre, 'socio_nid': socio_nid,
            'login': True, 'order': False,
            'error': f"No se pudo obtener grupo: {grupo.get('error')}"
        }

    miembros = grupo['miembros']
    pendientes = [m for m in miembros if m.get('puede_confirmar') and m.get('seccion_nid')]
    ya_ok = [m for m in miembros if m.get('confirmado')]
    no_habilitados = [m for m in miembros if not m.get('confirmado') and m not in pendientes]
    no_hab_texto = ', '.join(
        f"{m['nombre']} ({m.get('motivo') or ('sin seccion' if m.get('puede_confirmar') else 'no habilitado / adherente?')})"
        for m in no_habilitados
    )
    grupo_nombres = ', '.join(m['nombre'] for m in miembros)
    seccion_nombre = next((m['seccion_nombre'] for m in miembros if m.get('seccion_nombre')), '?')

    update_status(
        state='grupo_ok',
        seccion=seccion_nombre,
        grupo=[m['nombre'] for m in miembros],
        pendientes=[m['nombre'] for m in pendientes],
    )

    if not pendientes and no_habilitados:
        logger.warning(f"NO HABILITADO: {email} -> {no_hab_texto}")
        update_status(state='no_habilitado', error=no_hab_texto)
        return {
            'email': email, 'nombre': nombre, 'socio_nid': socio_nid,
            'login': True, 'order': False, 'no_habilitado': True,
            'seccion': seccion_nombre, 'grupo': grupo_nombres,
            'error': f"No habilitado: {no_hab_texto}",
        }

    if not pendientes:
        logger.info(f"ORDER OK: {nombre} grupo [{grupo_nombres}] -> ya estaban confirmados")
        update_status(state='ya_confirmado')
        return {
            'email': email, 'nombre': nombre, 'socio_nid': socio_nid,
            'login': True, 'order': True, 'already_confirmed': True,
            'seccion': seccion_nombre, 'grupo': grupo_nombres,
            'grupo_nids': [m['socio_nid'] for m in miembros],
        }

    if dry_run:
        logger.info(f"[DRY-RUN] {nombre} grupo [{grupo_nombres}] pendientes={len(pendientes)} seccion={seccion_nombre}")
        update_status(state='dry_run', seccion=seccion_nombre)
        return {
            'email': email, 'nombre': nombre, 'socio_nid': socio_nid,
            'login': True, 'order': 'dry-run', 'seccion': seccion_nombre,
            'grupo': grupo_nombres, 'pendientes': [m['nombre'] for m in pendientes],
        }

    update_status(state='ordering')
    order_result = do_order_grupo(token, evento_nid, pendientes, cookie_string, cookie_file)

    final_state = 'reserved' if order_result['success'] else 'order_failed'
    update_status(
        state=final_state,
        order_status=order_result.get('status'),
        order_attempts=order_result.get('attempts'),
        order_error=order_result.get('error', '')
    )

    extra = ''
    if ya_ok:
        extra += f" (ya ok: {', '.join(m['nombre'] for m in ya_ok)})"
    if no_habilitados:
        extra += f" (no habilitados: {no_hab_texto})"

    return {
        'email': email,
        'nombre': nombre,
        'socio_nid': socio_nid,
        'seccion': seccion_nombre,
        'login': True,
        'order': order_result['success'],
        'already_confirmed': order_result.get('already_confirmed', False),
        'order_status': order_result.get('status'),
        'order_data': order_result.get('data', order_result.get('error', '')),
        'attempts': order_result.get('attempts'),
        'grupo': grupo_nombres + extra,
        'grupo_nids': [m['socio_nid'] for m in pendientes],
        **({} if order_result['success'] else {'error': order_result.get('error', '')}),
    }


def main():
    parser = argparse.ArgumentParser(description='Order Popu Familia - Confirmar titular + familia')
    parser.add_argument('--evento', type=int, required=True, help='ID del evento (eventoNid)')
    parser.add_argument('--cookies', type=str, default=None, help='Archivo JSON con cookies')
    parser.add_argument('--csv', type=str, default='socios.csv', help='CSV con email,password (default: socios.csv)')
    parser.add_argument('--dry-run', action='store_true', help='No ejecutar orders, solo login + grupo')
    parser.add_argument('--workers', type=int, default=5, help='Procesos paralelos (default: 5)')
    parser.add_argument('--delay', type=float, default=1.5, help='Segundos entre lanzar cada socio (default: 1.5)')
    args = parser.parse_args()

    print("=" * 70)
    print("ORDER POPU FAMILIA RAPIDO - Confirmar titular + grupo familiar")
    print("=" * 70)
    print(f"Evento: {args.evento}")
    print(f"CSV: {args.csv}")
    print(f"Workers: {args.workers}")
    print(f"Delay entre socios: {args.delay}s")
    print(f"Dry-run: {args.dry_run}")
    print(f"Estado: {STATUS_FILE}")
    print("=" * 70)

    cookie_string = load_cookies(args.cookies)

    socios = load_socios(args.csv)
    if not socios:
        logger.error("No hay socios para procesar. Crea socios.csv con columnas: email,password")
        sys.exit(1)

    if os.path.exists(STATUS_FILE):
        os.remove(STATUS_FILE)

    print(f"\nProcesando {len(socios)} cuentas con {args.workers} workers...\n")

    results = []

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for i, socio in enumerate(socios):
            if i > 0 and args.delay > 0:
                time.sleep(args.delay)
            logger.info(f"Lanzando {i + 1}/{len(socios)}: {socio['email']}")
            future = executor.submit(process_socio, socio, args.evento, cookie_string, args.cookies, args.dry_run)
            futures[future] = socio['email']

        for future in as_completed(futures):
            email = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Error procesando {email}: {e}")
                results.append({'email': email, 'login': False, 'order': False, 'error': str(e)})

    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)

    login_ok = sum(1 for r in results if r.get('login'))
    login_fail = sum(1 for r in results if not r.get('login'))
    ya_ok = sum(1 for r in results if r.get('already_confirmed'))
    order_ok = sum(1 for r in results if r.get('order') is True and not r.get('already_confirmed'))
    no_hab = sum(1 for r in results if r.get('no_habilitado'))
    order_fail = sum(1 for r in results if r.get('login') and r.get('order') is False and not r.get('no_habilitado'))

    print(f"Total cuentas: {len(results)}")
    print(f"Login exitoso: {login_ok}")
    print(f"Login fallido (usuario/clave?): {login_fail}")
    print(f"Grupos confirmados ahora: {order_ok}")
    print(f"Ya estaban confirmados: {ya_ok}")
    print(f"No habilitados (adherente?): {no_hab}")
    print(f"Rechazados / error: {order_fail}")

    if args.dry_run:
        print("(Dry-run: no se ejecutaron orders)")

    print("\nDetalle:")
    for r in results:
        if r.get('already_confirmed'):
            status = "YA CONFIRMADO"
        elif r.get('order') is True:
            status = "OK"
        elif r.get('order') == 'dry-run':
            status = "DRY-RUN"
        elif not r.get('login'):
            status = "LOGIN FAIL"
        elif r.get('no_habilitado'):
            status = "NO HABILITADO"
        else:
            status = "FAIL"
        nombre = r.get('nombre', '')
        seccion = r.get('seccion', '?')
        grupo = r.get('grupo', '')
        extra = f" | grupo: {grupo}" if grupo else ''
        error = f" - {r['error']}" if r.get('error') else ''
        print(f"  [{status}] {r['email']} {nombre} -> {seccion}{extra}{error}")

    result_file = f"order_popu_familia_rapido_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados en {result_file}")
    print(f"Estado detallado en {STATUS_FILE}")


if __name__ == '__main__':
    main()
