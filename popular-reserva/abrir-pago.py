"""
Abre Chrome con cookies de Queue-it + login automático para que el socio pague.

Uso:
  python abrir-pago.py --email user@mail.com --password pass123 [--cookies archivo.json] [--evento 868]
  python abrir-pago.py --csv socios.csv [--evento 868]   (abre un Chrome por socio)
"""

import json
import os
import sys
import glob
import csv
import time
import base64
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def find_latest_cookies(cookie_file=None):
    if cookie_file and os.path.exists(cookie_file):
        with open(cookie_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
    all_files = []
    for d in ['.', downloads_dir]:
        all_files.extend(glob.glob(os.path.join(d, 'boca_cookies*.json')))
        all_files.extend(glob.glob(os.path.join(d, 'session_*_cookies.json')))
    
    if not all_files:
        print("No se encontraron archivos de cookies")
        sys.exit(1)
    
    all_files.sort(key=os.path.getmtime, reverse=True)
    newest = all_files[0]
    print(f"Usando cookies de: {newest}")
    
    with open(newest, 'r', encoding='utf-8') as f:
        return json.load(f)


def inject_cookies(driver, cookies):
    """Inyecta via CDP. QueueIT va a .bocajuniors.com.ar (como en el browser real)."""
    driver.execute_cdp_cmd('Network.enable', {})

    for c in cookies:
        name = c.get('name', '')
        value = c.get('value', '')
        if not name or not value:
            continue

        domains = []
        if c.get('domain'):
            domains.append(c['domain'])
        elif name.startswith('QueueITAccepted') or name.startswith('_ga') or name.startswith('_cl'):
            domains.append('.bocajuniors.com.ar')
        elif 'HWWAF' in name or name == 'CLID':
            domains.extend([
                'bocasocios.bocajuniors.com.ar',
                'bocasocios-gw.bocajuniors.com.ar',
            ])
        else:
            domains.append('.bocajuniors.com.ar')

        if name.startswith('QueueITAccepted') and '.bocajuniors.com.ar' not in domains:
            domains.append('.bocajuniors.com.ar')

        for domain in domains:
            params = {
                'name': name,
                'value': value,
                'domain': domain,
                'path': c.get('path', '/'),
                'secure': c.get('secure', False),
                'httpOnly': c.get('httpOnly', False),
            }
            try:
                driver.execute_cdp_cmd('Network.setCookie', params)
            except Exception:
                pass


def open_and_login(email, password, cookies, evento, index=0):
    """Abre Chrome, inyecta cookies, hace login y navega al evento."""
    print(f"\n[{index}] Abriendo Chrome para {email}...")
    
    options = Options()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    
    driver.get('https://bocasocios.bocajuniors.com.ar/auth/login')
    inject_cookies(driver, cookies)
    
    driver.get('https://bocasocios.bocajuniors.com.ar/auth/login')
    
    try:
        wait = WebDriverWait(driver, 10)
        
        email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="email"], input[placeholder*="correo"], input[name="email"]')))
        email_input.clear()
        email_input.send_keys(email)
        
        time.sleep(0.5)
        
        pass_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
        pass_input.clear()
        pass_input.send_keys(password)
        
        time.sleep(0.5)
        
        login_btn = driver.find_element(By.XPATH, '//button[contains(translate(text(),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"iniciar") or contains(translate(text(),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"sesión") or contains(translate(text(),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"login")]')
        login_btn.click()
        
        print(f"[{index}] Login enviado para {email}")
        
        time.sleep(3)
        
        if '/auth/login' not in driver.current_url:
            print(f"[{index}] Login OK - redirigido a {driver.current_url}")
            driver.get(f'https://bocasocios.bocajuniors.com.ar/matches/{evento}/assist')
            print(f"[{index}] Navegando a /matches/{evento}/assist")
        else:
            print(f"[{index}] Login puede haber fallado - sigue en login")
    
    except Exception as e:
        print(f"[{index}] Error en login automatico: {e}")
        print(f"[{index}] Hacé login manual en el Chrome que se abrió")
    
    return driver


def main():
    parser = argparse.ArgumentParser(description='Abrir Chrome con cookies + login para pagar')
    parser.add_argument('--email', type=str, help='Email del socio')
    parser.add_argument('--password', type=str, help='Password del socio')
    parser.add_argument('--csv', type=str, default=None, help='CSV con email,password (abre un Chrome por socio)')
    parser.add_argument('--cookies', type=str, default=None, help='Archivo JSON con cookies')
    parser.add_argument('--evento', type=int, default=868, help='ID del evento')
    args = parser.parse_args()
    
    data = find_latest_cookies(args.cookies)
    cookies = data.get('cookies', [])
    
    has_queueit = any('QueueITAccepted' in c.get('name', '') for c in cookies)
    if has_queueit:
        print("QueueITAccepted encontrada")
    else:
        print("ADVERTENCIA: Sin QueueITAccepted - puede mandar a la cola")
    
    socios = []
    
    if args.csv:
        try:
            with open(args.csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get('email', '').strip()
                    password = row.get('password', '').strip()
                    if email and password:
                        socios.append({'email': email, 'password': password})
            print(f"Cargados {len(socios)} socios desde {args.csv}")
        except Exception as e:
            print(f"Error leyendo CSV: {e}")
            sys.exit(1)
    elif args.email and args.password:
        socios.append({'email': args.email, 'password': args.password})
    else:
        print("Necesitas --email/--password o --csv")
        sys.exit(1)
    
    drivers = []
    for i, socio in enumerate(socios):
        if i > 0:
            time.sleep(3)
        driver = open_and_login(socio['email'], socio['password'], cookies, args.evento, i)
        drivers.append(driver)
    
    print()
    print("=" * 50)
    print(f"{len(drivers)} Chrome(s) abiertos con login")
    print("Pagá desde ahí. No cierres esta terminal.")
    print("Presiona Enter cuando termines para cerrar todo.")
    print("=" * 50)
    
    try:
        input()
    except EOFError:
        import signal
        signal.pause()
    
    for d in drivers:
        try:
            d.quit()
        except:
            pass


if __name__ == '__main__':
    main()
