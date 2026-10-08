"""
Adicional Copa - Reserva + pago en efectivo (HAR adiconala_copa)

Uso:
  python adicional_copa.py --evento 869
  python adicional_copa.py --evento 869 --dry-run

Lanza las cuentas espaciadas para que la corrida dure entre 3:30 y 4:00.
Si una falla, sigue con la siguiente y al final imprime el reporte.

Parámetros:
  --evento      ID del evento (eventoNid)
  --mode        Modo de operacion: "adicional" (default) o "confirmacion"
                adicional  -> POST /event/v2/buy/additional/order (adherentes, popus)
                confirmacion -> POST /event/confirmation/order (plenos, requiere seccion)
  --cookies     Archivo JSON con cookies (del queue-manager o exportado del browser)
                Si no se pasa, busca session_*_cookies.json o boca_cookies*.json (tambien en Downloads)
  --csv         Archivo CSV con credenciales (default: socios.csv) - columnas: email,password
  --dry-run     No ejecutar, solo mostrar qué haría
  --workers     Procesos en paralelo (0 = las que hagan falta para el intervalo)
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
from concurrent.futures import ProcessPoolExecutor, wait

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('order-popu.log', encoding='utf-8')
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

STATUS_FILE = 'order_status.json'
TARGET_LAST_START_SECONDS = 210


def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
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
        except:
            continue
    
    for cf in cookie_files:
        try:
            with open(cf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cookie_str = data.get('cookie_string', '')
            if cookie_str:
                logger.warning(f"Usando cookies de {cf} (sin QueueITAccepted - puede fallar)")
                return cookie_str
        except:
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
            except:
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
        except:
            continue
    
    if newest_file:
        try:
            with open(newest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cookie_str = data.get('cookie_string', '')
            if cookie_str:
                logger.info(f"Cookies recargadas desde {newest_file} (actualizado)")
                return cookie_str, newest_mtime
        except:
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
            socio_tipo = usuario.get('socioTipo', '')
            
            logger.info(f"LOGIN OK: {email} -> socioNid={socio_nid} ({nombre}) tipo={socio_tipo}")
            return {
                'success': True,
                'token': token,
                'refresh_token': data.get('refreshToken'),
                'socio_nid': socio_nid,
                'socio_numero': socio_numero,
                'nombre': nombre,
                'socio_tipo': socio_tipo,
                'email': email
            }
        else:
            logger.error(f"LOGIN FAIL: {email} -> HTTP {resp.status_code}: {resp.text[:200]}")
            return {'success': False, 'email': email, 'error': f"HTTP {resp.status_code}"}
    
    except Exception as e:
        logger.error(f"LOGIN ERROR: {email} -> {e}")
        return {'success': False, 'email': email, 'error': str(e)}


def get_seccion(token, evento_nid, cookie_string=None):
    """Para mode=confirmacion: obtiene seccion asignada."""
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
        
        if resp.status_code in (200, 201):
            data = resp.json()
            socios_detalle = data.get('sociosConfirmacionDetalle', [])
            if socios_detalle:
                socio = socios_detalle[0]
                secciones = socio.get('eventoSecciones', [])
                puede_confirmar = socio.get('permitirConfirmarConfirmacion', False)
                
                if secciones:
                    seccion = secciones[0]
                    logger.info(f"SECCION: {seccion['nombre']} (nid={seccion['nid']}) - Puede confirmar: {puede_confirmar}")
                    return {
                        'success': True,
                        'seccion_nid': seccion['nid'],
                        'seccion_nombre': seccion['nombre'],
                        'puede_confirmar': puede_confirmar,
                        'confirmacion_tipo': socio.get('confirmacionWebTipoEnum')
                    }
                else:
                    return {'success': False, 'error': 'Sin secciones asignadas'}
            else:
                return {'success': False, 'error': 'Sin detalle de socios'}
        else:
            logger.error(f"SECCION FAIL: HTTP {resp.status_code}: {resp.text[:200]}")
            return {'success': False, 'error': f"HTTP {resp.status_code}"}
    
    except Exception as e:
        logger.error(f"SECCION ERROR: {e}")
        return {'success': False, 'error': str(e)}


def get_adicional_tipo(token, evento_nid, cookie_string=None):
    """GET /event/buy/products/{evento} -> tipoNid del adicional (copa usa -2, no -1)."""
    headers = {
        **HEADERS_BASE,
        'Authorization': f'Bearer {token}'
    }
    if cookie_string:
        headers['Cookie'] = cookie_string

    try:
        resp = requests.get(
            f'{BASE_URL}/event/buy/products/{evento_nid}',
            headers=headers,
            timeout=15
        )
        if resp.status_code != 200:
            logger.warning(f"PRODUCTS FAIL: HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        adicionales = data.get('adicionales') or []
        if not adicionales:
            logger.warning(f"PRODUCTS: evento {evento_nid} sin adicionales")
            return None
        tipo = adicionales[0].get('tipoNid')
        precio = adicionales[0].get('precio')
        logger.info(f"PRODUCTS: evento={evento_nid} adicionalTipoNid={tipo} precio={precio}")
        return str(tipo) if tipo is not None else None
    except Exception as e:
        logger.warning(f"PRODUCTS ERROR: {e}")
        return None


def pay_adicional_efectivo(token, evento_nid, cookie_string=None):
    """Pago en efectivo como en el HAR: saveGuestTicketInfo + additional/order/pay."""
    headers = {
        **HEADERS_BASE,
        'Authorization': f'Bearer {token}'
    }
    if cookie_string:
        headers['Cookie'] = cookie_string

    try:
        prod = requests.get(
            f'{BASE_URL}/event/buy/products/{evento_nid}',
            headers=headers,
            timeout=15
        )
        if prod.status_code != 200:
            logger.warning(f"PAY products FAIL: HTTP {prod.status_code}")
            return {'success': False, 'error': f'products HTTP {prod.status_code}'}
        adicionales = (prod.json().get('adicionales') or [])
        compra = next((a for a in adicionales if a.get('nid')), None)
        if not compra:
            logger.warning('PAY: no hay adicional con nid (pedido) para pagar')
            return {'success': False, 'error': 'sin nid de compra'}

        requests.post(
            f'{BASE_URL}/event/seat/saveGuestTicketInfo',
            json={'ticketsInvitado': []},
            headers=headers,
            timeout=15
        )

        resp = requests.post(
            f'{BASE_URL}/event/buy/additional/order/pay',
            json={
                'compras': [{'nid': compra['nid'], 'productoNid': -5}],
                'medioPagoNid': '-2',
                'payInCash': True,
            },
            headers=headers,
            timeout=15
        )
        if resp.status_code in (200, 201):
            logger.info(f"PAY EFECTIVO OK: nid={compra['nid']} -> {resp.status_code} {resp.text[:200]}")
            return {'success': True, 'status': resp.status_code, 'data': resp.text[:300]}
        logger.warning(f"PAY FAIL: HTTP {resp.status_code}: {resp.text[:200]}")
        return {'success': False, 'error': f'HTTP {resp.status_code}', 'data': resp.text[:200]}
    except Exception as e:
        logger.warning(f"PAY ERROR: {e}")
        return {'success': False, 'error': str(e)}


def do_order_adicional(token, socio_nid, evento_nid,
                       cookie_string=None, cookie_file=None, max_retries=1, retry_wait=0):
    """POST /event/v2/buy/additional/order. Un intento: si falla, no retiene a las demas."""
    headers = {
        **HEADERS_BASE,
        'Authorization': f'Bearer {token}'
    }
    if cookie_string:
        headers['Cookie'] = cookie_string

    tipo_nid = get_adicional_tipo(token, evento_nid, cookie_string) or '-2'

    body = {
        'eventoNid': evento_nid,
        'adicionalTipoNid': tipo_nid,
        'socioNid': str(socio_nid),
        'tieneAbonoDiscapacitado': False
    }

    try:
        resp = requests.post(
            f'{BASE_URL}/event/v2/buy/additional/order',
            json=body,
            headers=headers,
            timeout=12
        )

        if resp.status_code in (200, 201):
            logger.info(f"ORDER OK: socioNid={socio_nid} -> {resp.status_code}")
            pay = pay_adicional_efectivo(token, evento_nid, cookie_string)
            return {
                'success': True,
                'socio_nid': socio_nid,
                'status': resp.status_code,
                'data': resp.text[:300],
                'attempts': 1,
                'pay': pay,
            }

        resp_text = resp.text[:300]
        if 'Ya compraste' in resp_text or 'en proceso de pago' in resp_text:
            logger.info(f"ORDER: socioNid={socio_nid} -> {resp_text[:100]}. No reintenta.")
            return {'success': True, 'socio_nid': socio_nid, 'status': resp.status_code, 'data': resp_text, 'attempts': 1, 'already': True}

        logger.warning(f"ORDER socioNid={socio_nid} -> HTTP {resp.status_code}: {resp.text[:200]}")
        return {'success': False, 'socio_nid': socio_nid, 'status': resp.status_code, 'error': resp.text[:200], 'attempts': 1}
    except requests.exceptions.Timeout:
        logger.warning(f"ORDER socioNid={socio_nid} -> TIMEOUT")
        return {'success': False, 'socio_nid': socio_nid, 'error': 'TIMEOUT', 'attempts': 1}
    except requests.exceptions.ConnectionError:
        logger.warning(f"ORDER socioNid={socio_nid} -> CONNECTION ERROR")
        return {'success': False, 'socio_nid': socio_nid, 'error': 'CONNECTION ERROR', 'attempts': 1}
    except Exception as e:
        logger.warning(f"ORDER socioNid={socio_nid} -> {e}")
        return {'success': False, 'socio_nid': socio_nid, 'error': str(e), 'attempts': 1}


def do_order_confirmacion(token, socio_nid, evento_nid, seccion_nid, confirmacion_tipo,
                          cookie_string=None, cookie_file=None, max_retries=50, retry_wait=20):
    """POST /event/confirmation/order - para confirmacion (plenos)."""
    headers = {
        **HEADERS_BASE,
        'Authorization': f'Bearer {token}'
    }
    if cookie_string:
        headers['Cookie'] = cookie_string
    
    body = {
        'eventoNid': evento_nid,
        'tipoNid': -1,
        'conRotacion': 0,
        'socioNidEventoSeccionNidsC': [{
            'socioNid': socio_nid,
            'confirmacionWebTipoEnum': confirmacion_tipo if confirmacion_tipo is not None else -1,
            'adicionalNid': None,
            'eventoSeccionNid': seccion_nid
        }]
    }
    
    last_cookie_mtime = 0
    
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                f'{BASE_URL}/event/confirmation/order',
                json=body,
                headers=headers,
                timeout=15
            )
            
            if resp.status_code in (200, 201):
                logger.info(f"ORDER OK: socioNid={socio_nid} -> {resp.status_code} (intento {attempt})")
                return {'success': True, 'socio_nid': socio_nid, 'status': resp.status_code, 'data': resp.text[:300], 'attempts': attempt}
            
            logger.warning(f"ORDER socioNid={socio_nid} -> HTTP {resp.status_code}: {resp.text[:200]}")
            return {'success': False, 'socio_nid': socio_nid, 'status': resp.status_code, 'error': resp.text[:200], 'attempts': attempt}
        
        except requests.exceptions.Timeout:
            logger.warning(f"ORDER socioNid={socio_nid} -> TIMEOUT")
            return {'success': False, 'socio_nid': socio_nid, 'error': 'TIMEOUT', 'attempts': attempt}
        except requests.exceptions.ConnectionError:
            logger.warning(f"ORDER socioNid={socio_nid} -> CONNECTION ERROR")
            return {'success': False, 'socio_nid': socio_nid, 'error': 'CONNECTION ERROR', 'attempts': attempt}
        except Exception as e:
            logger.warning(f"ORDER socioNid={socio_nid} -> {e}")
            return {'success': False, 'socio_nid': socio_nid, 'error': str(e), 'attempts': attempt}
    
    return {'success': False, 'socio_nid': socio_nid, 'error': 'sin respuesta'}


def process_socio(socio, evento_nid, mode, cookie_string, cookie_file, dry_run):
    """Procesa un socio: login + order. Guarda estado a order_status.json."""
    email = socio['email']
    password = socio['password']
    
    def update_status(**kwargs):
        s = load_status()
        entry = s.get(email, {'email': email})
        entry.update(kwargs)
        entry['last_update'] = datetime.now().isoformat()
        s[email] = entry
        save_status(s)
    
    update_status(state='login', started=datetime.now().isoformat(), mode=mode)
    
    login_result = do_login(email, password, cookie_string)
    if not login_result['success']:
        update_status(state='login_failed', error=login_result.get('error'))
        return {'email': email, 'login': False, 'order': False, 'error': login_result.get('error')}
    
    token = login_result['token']
    socio_nid = login_result['socio_nid']
    nombre = login_result['nombre']
    socio_tipo = login_result.get('socio_tipo', '')
    
    update_status(state='logged_in', nombre=nombre, socio_nid=socio_nid, socio_tipo=socio_tipo)
    
    if mode == 'adicional':
        if dry_run:
            logger.info(f"[DRY-RUN] {nombre} (socioNid={socio_nid}, tipo={socio_tipo}) -> adicional evento={evento_nid}")
            update_status(state='dry_run')
            return {
                'email': email, 'nombre': nombre, 'socio_nid': socio_nid, 'socio_tipo': socio_tipo,
                'login': True, 'order': 'dry-run'
            }
        
        update_status(state='ordering')
        order_result = do_order_adicional(token, socio_nid, evento_nid, cookie_string, cookie_file)
    
    else:
        update_status(state='getting_seccion')
        seccion_result = get_seccion(token, evento_nid, cookie_string)
        if not seccion_result['success']:
            update_status(state='seccion_failed', error=seccion_result.get('error'))
            return {
                'email': email, 'nombre': nombre, 'socio_nid': socio_nid,
                'login': True, 'order': False,
                'error': f"No se pudo obtener seccion: {seccion_result.get('error')}"
            }
        
        seccion_nid = seccion_result['seccion_nid']
        seccion_nombre = seccion_result['seccion_nombre']
        confirmacion_tipo = seccion_result.get('confirmacion_tipo', -1)
        puede_confirmar = seccion_result.get('puede_confirmar', False)
        
        update_status(state='seccion_ok', seccion=seccion_nombre, seccion_nid=seccion_nid)
        
        if not puede_confirmar:
            logger.warning(f"{nombre}: No puede confirmar (ya confirmado o no habilitado)")
            update_status(state='ya_confirmado')
            return {
                'email': email, 'nombre': nombre, 'socio_nid': socio_nid,
                'login': True, 'order': False, 'seccion': seccion_nombre,
                'error': 'No puede confirmar (ya confirmado o no habilitado)'
            }
        
        if dry_run:
            logger.info(f"[DRY-RUN] {nombre} -> seccion={seccion_nombre} (nid={seccion_nid}), evento={evento_nid}")
            update_status(state='dry_run', seccion=seccion_nombre)
            return {
                'email': email, 'nombre': nombre, 'socio_nid': socio_nid,
                'login': True, 'order': 'dry-run', 'seccion': seccion_nombre
            }
        
        update_status(state='ordering')
        order_result = do_order_confirmacion(token, socio_nid, evento_nid, seccion_nid, confirmacion_tipo,
                                             cookie_string, cookie_file)
    
    final_state = 'reserved' if order_result['success'] else 'order_failed'
    update_status(
        state=final_state,
        order_status=order_result.get('status'),
        order_attempts=order_result.get('attempts'),
        order_error=order_result.get('error', '')
    )
    
    pay = order_result.get('pay') if isinstance(order_result.get('pay'), dict) else None
    error = order_result.get('error', '')
    if pay and not pay.get('success') and not error:
        error = pay.get('error', '')

    return {
        'email': email,
        'nombre': nombre,
        'socio_nid': socio_nid,
        'socio_tipo': socio_tipo,
        'login': True,
        'order': order_result['success'],
        'order_status': order_result.get('status'),
        'order_data': order_result.get('data', error),
        'attempts': order_result.get('attempts'),
        'pay': pay,
        'error': error,
        'already': order_result.get('already', False),
    }


def main():
    parser = argparse.ArgumentParser(description='Order Popu - Confirmar asistencia / comprar adicional Boca')
    parser.add_argument('--evento', type=int, required=True, help='ID del evento (eventoNid)')
    parser.add_argument('--mode', type=str, default='adicional', choices=['adicional', 'confirmacion'],
                        help='adicional (adherentes/popus) o confirmacion (plenos)')
    parser.add_argument('--cookies', type=str, default=None, help='Archivo JSON con cookies')
    parser.add_argument('--csv', type=str, default='socios.csv', help='CSV con email,password')
    parser.add_argument('--dry-run', action='store_true', help='No ejecutar, solo login')
    parser.add_argument('--workers', type=int, default=0,
                        help='Procesos en paralelo (0 = las que hagan falta para el intervalo)')
    args = parser.parse_args()

    print("=" * 70)
    print("ADICIONAL COPA")
    print("=" * 70)
    print(f"Evento: {args.evento}")
    print(f"Modo: {args.mode}")
    if args.mode == 'adicional':
        print("  -> POST /event/v2/buy/additional/order + pago efectivo")
    else:
        print("  -> POST /event/confirmation/order (con seccion)")
    print(f"CSV: {args.csv}")
    print(f"Dry-run: {args.dry_run}")
    print("Duracion estimada: entre 3:30 y 4:00, un intento por cuenta")
    print("=" * 70)

    cookie_string = load_cookies(args.cookies)

    socios = load_socios(args.csv)
    if not socios:
        logger.error("No hay socios para procesar. Crea socios.csv con columnas: email,password")
        sys.exit(1)

    workers = args.workers if args.workers > 0 else len(socios)
    gaps = max(len(socios) - 1, 1)
    gap = TARGET_LAST_START_SECONDS / gaps
    print(
        f"\nProcesando {len(socios)} socios, una cada {gap:.1f}s. "
        f"La ultima sale cerca de los 3:30. No corta: espera a que terminen todas.\n"
    )

    if os.path.exists(STATUS_FILE):
        os.remove(STATUS_FILE)

    started = time.monotonic()
    by_email = {}
    executor = ProcessPoolExecutor(max_workers=workers)
    futures = {}
    try:
        for i, socio in enumerate(socios):
            if i > 0:
                logger.info(f"Proxima en {gap:.1f}s: {socio['email']}")
                time.sleep(gap)
            future = executor.submit(process_socio, socio, args.evento, args.mode,
                                     cookie_string, args.cookies, args.dry_run)
            futures[future] = socio['email']

        done, _pending = wait(set(futures))
        for future in done:
            email = futures[future]
            try:
                by_email[email] = future.result()
            except Exception as e:
                logger.error(f"Error procesando {email}: {e}")
                by_email[email] = {'email': email, 'login': False, 'order': False, 'error': str(e)}
    finally:
        executor.shutdown(wait=True)

    results = []
    for socio in socios:
        results.append(by_email.get(socio['email'], {
            'email': socio['email'], 'login': False, 'order': False, 'error': 'sin resultado'
        }))

    elapsed = time.monotonic() - started

    def estado(r):
        if r.get('order') == 'dry-run':
            return 'DRY-RUN'
        if not r.get('login') or r.get('order') is not True:
            return 'FAIL'
        pay = r.get('pay')
        if isinstance(pay, dict) and not pay.get('success'):
            return 'PAY FAIL'
        if r.get('already'):
            return 'YA TENIA'
        return 'OK'

    print("\n" + "=" * 70)
    print("REPORTE")
    print("=" * 70)
    print(f"Tiempo: {elapsed:.0f}s")
    print(f"Total: {len(results)}")
    print(f"OK: {sum(1 for r in results if estado(r) == 'OK')}")
    print(f"Ya tenia: {sum(1 for r in results if estado(r) == 'YA TENIA')}")
    print(f"Pago fallido: {sum(1 for r in results if estado(r) == 'PAY FAIL')}")
    print(f"Fallaron: {sum(1 for r in results if estado(r) == 'FAIL')}")
    if args.dry_run:
        print("(Dry-run: no se ejecutaron orders)")

    print("\nDetalle:")
    for r in results:
        st = estado(r)
        nombre = r.get('nombre', '')
        error = r.get('error') or ''
        pay = r.get('pay')
        if st == 'PAY FAIL' and isinstance(pay, dict) and pay.get('error'):
            error = pay.get('error')
        extra = f" - {error}" if error and st != 'OK' else ''
        print(f"  [{st}] {r['email']} {nombre}{extra}")

    result_file = f"order_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados en {result_file}")
    print(f"Estado detallado en {STATUS_FILE}")


if __name__ == '__main__':
    main()
