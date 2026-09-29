#!/usr/bin/env python3
"""
Queue Bot - Gestión de Sesiones para Colas con captura completa
- Todo lo de v4 + captura de cookies HttpOnly via CDP
- Captura localStorage de bocasocios
- Auto-sube cookies + localStorage al Cloudflare Worker
- La extensión de Chrome inyecta todo (como EBJ)
"""

# ⚙️ CONFIGURACIÓN: Cambiar entre 'local' o 'prod'
ENVIRONMENT = 'prod'  # Cambiar a 'local' para testear

# URLs según entorno
URLS = {
    'local': 'http://localhost:8000/boca-redirect.html',
    'prod': 'https://bocasocios.bocajuniors.com.ar/home'
}

import time
import json
import threading
import random
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from flask import Flask, render_template, jsonify, request
from urllib.parse import urlparse
import os
import logging
from typing import List, Dict, Optional
import requests as http_requests

# --- Config Worker Cloudflare ---
WORKER_URL = 'https://boca-cookies.rosaleseze86.workers.dev'
WORKER_API_KEY = os.environ.get('WORKER_API_KEY', '')

# Configurar logging a terminal + archivo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('queue_manager.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# User agents aleatorios actualizados para 2024
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
]

# Resoluciones de pantalla comunes
SCREEN_RESOLUTIONS = [
    (1920, 1080), (1366, 768), (1536, 864), (1440, 900), 
    (1280, 720), (1600, 900), (1024, 768), (1680, 1050),
    (1280, 1024), (1920, 1200), (2560, 1440), (1280, 800)
]

# Configuraciones de viewport
VIEWPORT_SIZES = [
    (1200, 800), (1024, 768), (1366, 768), (1440, 900),
    (1280, 720), (1536, 864), (1600, 900), (1920, 1080)
]

def get_random_user_agent():
    """Obtiene un user agent aleatorio"""
    return random.choice(USER_AGENTS)

def get_random_screen_resolution():
    """Obtiene una resolución de pantalla aleatoria"""
    return random.choice(SCREEN_RESOLUTIONS)

def get_random_viewport_size():
    """Obtiene un tamaño de viewport aleatorio"""
    return random.choice(VIEWPORT_SIZES)

def simulate_human_behavior(driver, duration=3):
    """Simula comportamiento humano con movimientos de mouse aleatorios"""
    try:
        actions = ActionChains(driver)
        
        # Simular movimientos de mouse aleatorios
        for _ in range(random.randint(2, 5)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            actions.move_by_offset(x, y)
            actions.pause(random.uniform(0.1, 0.3))
        
        # Simular scroll aleatorio
        scroll_amount = random.randint(-300, 300)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        
        # Pausa aleatoria para simular lectura
        time.sleep(random.uniform(0.5, duration))
        
        # Ejecutar movimientos
        actions.perform()
        
    except Exception as e:
        logger.debug(f"Error simulando comportamiento humano: {e}")

def add_random_delays():
    """Agrega delays aleatorios para simular comportamiento humano"""
    time.sleep(random.uniform(0.5, 2.0))

def randomize_browser_properties(driver):
    """Randomiza propiedades del navegador para evitar detección"""
    try:
        # Randomizar timezone
        timezones = [
            "America/New_York", "America/Los_Angeles", "America/Chicago",
            "Europe/London", "Europe/Paris", "Europe/Berlin",
            "America/Argentina/Buenos_Aires", "America/Mexico_City"
        ]
        timezone = random.choice(timezones)
        
        # ⚡ Scripts AVANZADOS para randomizar propiedades y ocultar headless
        driver.execute_script(f"""
            // ⚡⚡⚡ CRÍTICO: Ocultar que es headless
            Object.defineProperty(navigator, 'headless', {{
                get: function() {{ return false; }}
            }});
            
            // ⚡ CRÍTICO: Ocultar webdriver (Queue-it lo detecta)
            Object.defineProperty(navigator, 'webdriver', {{
                get: function() {{ return undefined; }}
            }});
            
            // Randomizar timezone
            Object.defineProperty(Intl.DateTimeFormat.prototype, 'resolvedOptions', {{
                value: function() {{
                    return {{
                        timeZone: '{timezone}',
                        locale: 'en-US'
                    }};
                }}
            }});
            
            // Randomizar language
            Object.defineProperty(navigator, 'language', {{
                get: function() {{ return 'en-US'; }}
            }});
            
            // Randomizar platform
            Object.defineProperty(navigator, 'platform', {{
                get: function() {{ return 'Win32'; }}
            }});
            
            // Simular plugins realistas (importante para headless)
            Object.defineProperty(navigator, 'plugins', {{
                get: function() {{ 
                    return [
                        {{
                            0: {{type: "application/x-google-chrome-pdf", suffixes: "pdf"}},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        }}
                    ]; 
                }}
            }});
            
            // Randomizar canvas fingerprint
            const originalGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type) {{
                if (type === '2d') {{
                    const context = originalGetContext.call(this, type);
                    const originalFillText = context.fillText;
                    context.fillText = function(text, x, y) {{
                        const noise = Math.random() * 0.01;
                        return originalFillText.call(this, text, x + noise, y + noise);
                    }};
                    return context;
                }}
                return originalGetContext.call(this, type);
            }};
            
            // Randomizar WebGL fingerprint
            const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) {{
                    return 'Intel Inc.';
                }}
                if (parameter === 37446) {{
                    return 'Intel(R) HD Graphics 620';
                }}
                return originalGetParameter.call(this, parameter);
            }};
            
            // ⚡ QUEUE-IT: Prevenir detección de automatización
            window.navigator.chrome = {{
                runtime: {{}},
                loadTimes: function() {{}},
                csi: function() {{}},
                app: {{}}
            }};
            
            // Ocultar variables de automatización de Selenium
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """)
        
    except Exception as e:
        logger.debug(f"Error randomizando propiedades del navegador: {e}")

def simulate_human_typing(driver, element, text, typing_speed=0.05):
    """Simula tipeo humano con velocidad variable"""
    try:
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(typing_speed, typing_speed * 3))
    except Exception as e:
        logger.debug(f"Error simulando tipeo humano: {e}")
        element.send_keys(text)  # Fallback normal

class SessionManager:
    def __init__(self, target_url: str, opening_time: str, session_count: int = 5):
        self.target_url = target_url
        self.opening_time = opening_time  # "13:00"
        self.session_count = session_count
        self.sessions = []
        self.drivers = []
        self.running = False
        self.monitor_thread = None
        self.burst_executed = False
        self.burst_lock = threading.Lock()
        
        # Limpiar archivos de sesiones anteriores
        self._cleanup_old_files()
        
        # Crear directorio para perfiles con timestamp único
        timestamp = int(time.time())
        self.profiles_dir = os.path.join(os.getcwd(), "chrome_profiles", f"session_{timestamp}")
        os.makedirs(self.profiles_dir, exist_ok=True)
        logger.info(f"Directorio de perfiles: {self.profiles_dir}")
    
    def _cleanup_old_files(self):
        """Borra archivos de tokens y redirects de sesiones anteriores"""
        import glob
        patterns = [
            'session_*_token.json',
            'session_*_redirects.txt',
            'tokens.txt'
        ]
        removed = 0
        for pattern in patterns:
            for filepath in glob.glob(pattern):
                try:
                    os.remove(filepath)
                    removed += 1
                except Exception as e:
                    logger.debug(f"No se pudo borrar {filepath}: {e}")
        if removed > 0:
            logger.info(f"Limpieza: {removed} archivos de sesiones anteriores eliminados")
    
    def create_independent_session(self, session_id: int) -> webdriver.Chrome:
        """Crea una sesión independiente de Chrome HEADLESS con perfil separado y medidas anti-bot"""
        try:
            options = Options()
            
            # Configurar perfil único para cada sesión (dentro del directorio con timestamp)
            profile_path = os.path.join(self.profiles_dir, f"profile_{session_id}")
            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument(f"--profile-directory=Default")
            
            # ⚡ MODO HEADLESS (sin ventanas)
            options.add_argument("--headless=new")  # Nuevo headless mode
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            # ⚡ CRÍTICO: User agent aleatorio (GUARDARLO para restauración)
            user_agent = get_random_user_agent()
            options.add_argument(f"--user-agent={user_agent}")
            
            # Configuraciones anti-detección avanzadas
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins-discovery")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-sync")
            options.add_argument("--disable-translate")
            options.add_argument("--disable-features=VizDisplayCompositor,TranslateUI")
            options.add_argument("--disable-ipc-flooding-protection")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--disable-component-extensions-with-background-pages")
            options.add_argument("--disable-logging")
            options.add_argument("--log-level=3")
            
            # ⚡ OPTIMIZACIÓN: No cargar imágenes en headless
            options.add_argument("--blink-settings=imagesEnabled=false")
            
            # Configuraciones experimentales
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.media_stream_mic": 2,
                "profile.default_content_setting_values.media_stream_camera": 2,
                "profile.default_content_setting_values.geolocation": 2,
                "profile.password_manager_enabled": False,
                "credentials_enable_service": False,
                "profile.default_content_settings.popups": 0
            })
            
            # ⚡⚡⚡ HABILITAR LOGS DE PERFORMANCE para capturar network requests
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
            # Headers aleatorios
            screen_resolution = get_random_screen_resolution()
            options.add_argument(f"--window-size={screen_resolution[0]},{screen_resolution[1]}")
            
            # Crear driver
            driver = webdriver.Chrome(options=options)
            
            # Habilitar Network logging via CDP
            driver.execute_cdp_cmd('Network.enable', {})
            
            # Configurar ventana con tamaño aleatorio
            viewport_size = get_random_viewport_size()
            driver.set_window_size(viewport_size[0], viewport_size[1])
            
            # Posición aleatoria de ventana
            x_pos = random.randint(0, 200) + (session_id * 50)
            y_pos = random.randint(0, 200) + (session_id * 30)
            driver.set_window_position(x_pos, y_pos)
            
            # ⚡ En modo headless no hay ventanas para minimizar
            # Las sesiones corren en background automáticamente
            
            # Aplicar randomización de propiedades del navegador
            randomize_browser_properties(driver)
            
            # Delay aleatorio antes de navegar
            add_random_delays()
            
            logger.info(f"Sesión {session_id} creada con User-Agent: {user_agent[:50]}...")
            
            return driver
            
        except Exception as e:
            logger.error(f"Error creando sesión {session_id}: {e}")
            return None
    
    def start_sessions(self):
        """Inicia todas las sesiones"""
        if self.running:
            logger.warning("Las sesiones ya están ejecutándose")
            return
        
        self.running = True
        logger.info(f"Iniciando {self.session_count} sesiones independientes...")
        
        # Crear sesiones
        for i in range(self.session_count):
            try:
                driver = self.create_independent_session(i)
                if driver:
                    # Navegar a la URL con parámetros únicos
                    unique_url = f"{self.target_url}?session_id={i}&timestamp={int(time.time())}"
                    driver.get(unique_url)
                    
                    # ⚡ GUARDAR USER AGENT USADO (para restauración idéntica)
                    user_agent_used = driver.execute_script("return navigator.userAgent;")
                    
                    # Crear objeto de sesión
                    session_data = {
                        'id': i,
                        'driver': driver,
                        'queue_id': None,
                        'wait_time': None,
                        'status': 'waiting',
                        'last_update': datetime.now(),
                        'url': unique_url,
                        'user_agent': user_agent_used  # ← Guardamos el UA para restaurar igual
                    }
                    
                    self.sessions.append(session_data)
                    self.drivers.append(driver)
                    
                    logger.info(f"Sesión {i} iniciada correctamente")
                    
                    # Pequeño delay entre sesiones
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"Error iniciando sesión {i}: {e}")
        
        # Iniciar monitoreo
        self.start_monitoring()
        logger.info(f"Sistema iniciado con {len(self.sessions)} sesiones activas")
    
    def extract_queue_data(self, session: Dict, quick_mode: bool = False) -> Dict:
        """Extrae datos de la cola de una sesión específica con comportamiento humano
        
        Args:
            session: Sesión a extraer datos
            quick_mode: Si es True, reduce timeouts para refresh manual (más rápido)
        """
        try:
            # ✅ VALIDAR QUE LA SESIÓN TENGA DRIVER Y ESTÉ ACTIVO
            driver = session.get('driver')
            if not driver:
                raise Exception("Sesión sin driver")
            
            # ✅ VERIFICAR QUE EL DRIVER ESTÉ CONECTADO
            try:
                # Verificar que la sesión del driver sea válida
                current_url = driver.current_url
            except Exception as driver_error:
                raise Exception(f"Driver inválido o desconectado: {driver_error}")
            
            # ⚡⚡⚡ SI YA REDIRIGIÓ A /queueit/redirect, NO BUSCAR MÁS (mantener datos actuales)
            if '/queueit/redirect' in current_url and 'queueittoken=' in current_url:
                logger.info(f"Sesión {session['id']}: Ya tiene el redirect con token - Manteniendo datos actuales")
                
                # Marcar como completado con éxito
                return {
                    'queue_id': session.get('queue_id'),
                    'wait_time': session.get('wait_time'),
                    'status': 'ready',  # Listo para usar
                    'last_update': datetime.now(),
                    'url': current_url,
                    'raw_time_text': 'Token capturado - Listo para usar'
                }
            
            current_time = datetime.now()
            opening_time = datetime.strptime(self.opening_time, "%H:%M").time()
            opening_datetime = datetime.combine(current_time.date(), opening_time)
            
            # Verificar si estamos en hora de apertura (con margen de 1 minuto)
            time_until_opening = (opening_datetime - current_time).total_seconds()
            is_opening_time = -60 <= time_until_opening <= 300  # 1 min antes a 5 min después
            
            # Si estamos en hora de apertura, hacer refresh automático
            if is_opening_time and time_until_opening <= 0:
                logger.info(f"Sesión {session['id']}: Hora de apertura detectada, refrescando...")
                driver.refresh()
                add_random_delays()
            
            # ⚡ MODO RÁPIDO: Reducir delays y timeouts
            if quick_mode:
                # Simular comportamiento humano más corto (OPTIMIZADO: 2x más rápido)
                time.sleep(random.uniform(0.2, 0.5))
                max_queue_attempts = 2
                queue_timeout = 3  # ⚡ Reducido de 4s a 3s
            else:
                # Comportamiento normal
                simulate_human_behavior(driver, duration=random.uniform(1, 2))
                max_queue_attempts = 3
                queue_timeout = 8
            
            # Intentar obtener Queue ID con reintentos
            queue_id = None
            for attempt in range(max_queue_attempts):
                try:
                    queue_id_element = WebDriverWait(driver, queue_timeout).until(
                        EC.presence_of_element_located((By.ID, "hlLinkToQueueTicket2"))
                    )
                    
                    # Simular hover sobre el elemento (más rápido en quick_mode)
                    if not quick_mode:
                        actions = ActionChains(driver)
                        actions.move_to_element(queue_id_element).perform()
                        add_random_delays()
                    
                    queue_id = queue_id_element.text.strip()
                    
                    # Validar que el Queue ID sea válido
                    if queue_id and len(queue_id) > 5 and not any(word in queue_id.lower() for word in ['cargando', 'calculando', 'obteniendo', 'loading']):
                        break
                    else:
                        queue_id = None
                        
                except TimeoutException:
                    if attempt < (max_queue_attempts - 1) and not quick_mode:
                        logger.debug(f"Sesión {session['id']}: Reintento {attempt + 1} para Queue ID")
                        driver.refresh()
                        add_random_delays()
                    else:
                        queue_id = None
            
            # Manejo del tiempo de espera según la fase
            wait_time = None
            time_text = ""
            
            if current_time >= opening_datetime:
                # Solo intentar obtener tiempo de espera si ya es hora de apertura
                logger.info(f"Sesión {session['id']}: Es hora de apertura, verificando si cambió la página...")
                
                # ⚡ MODO RÁPIDO: Menos intentos y timeouts más cortos (OPTIMIZADO)
                if quick_mode:
                    max_time_attempts = 3
                    time_timeout = 2  # ⚡ Reducido de 3s a 2s
                    retry_wait = (1, 2)  # ⚡ Reducido de (2,3) a (1,2)
                else:
                    max_time_attempts = 8
                    time_timeout = 5
                    retry_wait = (4, 8)
                
                for attempt in range(max_time_attempts):
                    try:
                        # Primero verificar si existe el elemento de tiempo (la página cambió)
                        time_element = WebDriverWait(driver, time_timeout).until(
                            EC.presence_of_element_located((By.ID, "MainPart_lbWhichIsIn"))
                        )
                        
                        logger.info(f"Sesión {session['id']}: ¡Página cambió! Elemento de tiempo encontrado")
                        
                        # Simular hover sobre el elemento de tiempo (solo en modo normal)
                        if not quick_mode:
                            actions = ActionChains(driver)
                            actions.move_to_element(time_element).perform()
                            add_random_delays()
                        
                        time_text = time_element.text.strip()
                        
                        # Textos que indican que aún está cargando
                        loading_texts = ['cargando', 'calculando', 'obteniendo', 'loading', 'espere', 'wait', 'procesando']
                        
                        # ⚡ Si encontramos texto de carga, RETRY RÁPIDO (no esperar mucho)
                        if any(word in time_text.lower() for word in loading_texts):
                            logger.info(f"Sesión {session['id']}: '{time_text}' → RETRY RÁPIDO")
                            if attempt < (max_time_attempts - 1):
                                time.sleep(0.5)  # ⚡ Espera mínima antes de retry
                                driver.refresh()
                                time.sleep(0.3)
                                continue
                        
                        # Extraer número de minutos
                        import re
                        time_match = re.search(r'(\d+)', time_text)
                        if time_match:
                            potential_time = int(time_match.group(1))
                            # Validar que el tiempo sea razonable (0-60 minutos)
                            if 0 <= potential_time <= 60:
                                wait_time = potential_time
                                logger.info(f"Sesión {session['id']}: ¡Tiempo de espera obtenido! {wait_time} minutos")
                                break
                            else:
                                logger.debug(f"Sesión {session['id']}: Tiempo fuera de rango: {potential_time}")
                        
                        # Si no hay número pero hay texto válido, puede ser "LISTO" o similar
                        elif time_text and not any(word in time_text.lower() for word in loading_texts):
                            logger.info(f"Sesión {session['id']}: Estado especial detectado: '{time_text}'")
                            
                            # ✅ MANEJO ESPECÍFICO DE "MÁS DE UNA HORA"
                            if any(phrase in time_text.lower() for phrase in ['más de una hora', 'more than an hour', 'over an hour']):
                                wait_time = 65  # Directamente asignar 65 minutos
                                logger.info(f"Sesión {session['id']}: 'MÁS DE UNA HORA' convertido a {wait_time} min")
                                break  # ← TERMINAR AQUÍ
                            
                            # ✅ MANEJO DE ACCESO INMEDIATO  
                            elif any(phrase in time_text.lower() for phrase in ['listo', 'ready', 'accede ahora', 'access now', 'ingresa', 'enter']):
                                wait_time = 0  # Acceso inmediato
                                logger.info(f"Sesión {session['id']}: Acceso inmediato detectado: '{time_text}'")
                                break  # ← TERMINAR AQUÍ
                            
                            # ✅ OTROS ESTADOS ESPECIALES
                            else:
                                # Podría ser "LISTO", "READY", "ACCEDE AHORA", etc.
                                logger.info(f"Sesión {session['id']}: Estado especial sin tiempo: '{time_text}'")
                                break
                        
                    except TimeoutException:
                        # El elemento de tiempo aún no existe (página no cambió)
                        logger.debug(f"Sesión {session['id']}: Página aún no cambió, intento {attempt + 1}")
                        
                        if attempt < (max_time_attempts - 1):
                            # Hacer refresh para ver si la página cambió
                            if not quick_mode:
                                driver.refresh()
                                add_random_delays()
                                time.sleep(random.uniform(2, 4))
                            else:
                                driver.refresh()
                                time.sleep(random.uniform(1, 2))
                        else:
                            logger.warning(f"Sesión {session['id']}: Página no cambió después de {attempt + 1} intentos")
                            time_text = "Página no actualizada"
            
            else:
                # Antes de la hora de apertura - NO buscar elemento de tiempo
                logger.debug(f"Sesión {session['id']}: Pre-apertura, página de 'en cola' esperada")
                time_text = "Pre-apertura (sin tiempo)"
                wait_time = None
            
            # Log para debugging
            if current_time >= opening_datetime and wait_time is None:
                logger.info(f"Sesión {session['id']}: Esperando cambio de página o tiempo válido, estado: '{time_text}'")
            
            # Simular scroll aleatorio
            scroll_amount = random.randint(-100, 100)
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            add_random_delays()
            
            # Determinar estado con lógica mejorada
            if current_time >= opening_datetime:
                if wait_time is not None:
                    status = 'active'
                elif queue_id and any(word in time_text.lower() for word in ['abrimos', 'apertura', 'ready', 'listo']):
                    status = 'ready'
                else:
                    status = 'active'  # Asumimos activo si pasó la hora
            else:
                status = 'waiting'
            
            # Log del resultado
            logger.debug(f"Sesión {session['id']}: Queue ID: {queue_id}, Tiempo: {wait_time}, Estado: {status}, Texto: '{time_text}'")
            
            return {
                'queue_id': queue_id,
                'wait_time': wait_time,
                'status': status,
                'last_update': datetime.now(),
                'url': driver.current_url,
                'raw_time_text': time_text  # ← Texto literal de la página
            }
            
        except Exception as e:
            logger.error(f"Error extrayendo datos de sesión {session['id']}: {e}")
            return {
                'queue_id': None,
                'wait_time': None,
                'status': 'error',
                'last_update': datetime.now(),
                'url': None,
                'raw_time_text': ""
            }
    
    def capture_network_tokens(self):
        """Revisa network logs de TODAS las sesiones buscando queueittoken en redirects.
        Corre constantemente desde el monitoreo para no perder ningún 302."""
        for session in self.sessions:
            try:
                driver = session.get('driver')
                if not driver:
                    continue
                try:
                    if not driver.service.is_connectable():
                        continue
                except:
                    continue
                
                try:
                    logs = driver.get_log('performance')
                except Exception as log_err:
                    logger.warning(f"Sesion {session['id']}: No se pudo leer performance logs: {log_err}")
                    continue
                
                network_count = 0
                for log_entry in logs:
                    try:
                        message = json.loads(log_entry['message'])
                        method = message.get('message', {}).get('method', '')
                        
                        if method in ('Network.requestWillBeSent', 'Network.responseReceived'):
                            params = message.get('message', {}).get('params', {})
                            
                            if method == 'Network.requestWillBeSent':
                                url = params.get('request', {}).get('url', '')
                            else:
                                url = params.get('response', {}).get('url', '')
                            
                            if not url or url.startswith('data:'):
                                continue
                            
                            network_count += 1
                            
                            # Solo loguear URLs relevantes (API calls, redirects, enqueue/status)
                            is_relevant = (
                                'queueittoken' in url or
                                '/queueit/redirect' in url or
                                '/queueit/validate' in url or
                                'spa-api/queue' in url or
                                '/api/ipv4' in url
                            )
                            if is_relevant:
                                short_url = url[:150] if len(url) > 150 else url
                                logger.info(f"[NET] S{session['id']} {method.split('.')[-1]}: {short_url}")
                            
                            if 'queueittoken=' in url:
                                logger.info(f"!!!! TOKEN ENCONTRADO en sesion {session['id']} !!!!")
                                logger.info(f"!!!! URL: {url}")
                                
                                try:
                                    with open('tokens.txt', 'a', encoding='utf-8') as f:
                                        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        f.write(f"[{ts}] Sesion {session['id']}: {url}\n")
                                except Exception as e:
                                    logger.error(f"Error escribiendo tokens.txt: {e}")
                                
                                try:
                                    sf = f"session_{session['id']}_redirects.txt"
                                    with open(sf, 'a', encoding='utf-8') as f:
                                        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        f.write(f"[{ts}] {url}\n")
                                except Exception as e:
                                    logger.error(f"Error escribiendo {sf}: {e}")
                                
                                try:
                                    jf = f"session_{session['id']}_token.json"
                                    with open(jf, 'w', encoding='utf-8') as f:
                                        json.dump({
                                            'session_id': session['id'],
                                            'url': url,
                                            'timestamp': datetime.now().isoformat(),
                                            'queue_id': session.get('queue_id'),
                                            'wait_time': session.get('wait_time')
                                        }, f, indent=2)
                                except Exception as e:
                                    logger.error(f"Error escribiendo JSON: {e}")
                                
                                session['captured_redirect_url'] = url
                                
                                # Extraer cookies del browser (QueueITAccepted, HWWAFSESID, etc.)
                                try:
                                    all_cookies = driver.get_cookies()
                                    cookie_file = f"session_{session['id']}_cookies.json"
                                    with open(cookie_file, 'w', encoding='utf-8') as f:
                                        json.dump({
                                            'session_id': session['id'],
                                            'timestamp': datetime.now().isoformat(),
                                            'redirect_url': url,
                                            'cookies': all_cookies,
                                            'cookie_string': '; '.join(f"{c['name']}={c['value']}" for c in all_cookies)
                                        }, f, indent=2)
                                    
                                    important_cookies = [c for c in all_cookies if any(k in c['name'].lower() for k in ['queueitaccepted', 'hwwaf', 'clid'])]
                                    if important_cookies:
                                        logger.info(f"COOKIES CAPTURADAS sesion {session['id']}:")
                                        for c in important_cookies:
                                            logger.info(f"  {c['name']} = {c['value'][:80]}...")
                                    else:
                                        logger.info(f"Sesion {session['id']}: {len(all_cookies)} cookies guardadas en {cookie_file} (ninguna QueueIT/HWWAF encontrada)")
                                except Exception as cookie_err:
                                    logger.warning(f"No se pudieron extraer cookies de sesion {session['id']}: {cookie_err}")
                                
                    except Exception as parse_err:
                        logger.debug(f"Error parseando log entry: {parse_err}")
                
                if network_count > 0:
                    logger.info(f"[NET] Sesion {session['id']}: {network_count} requests de red capturados")
                else:
                    logger.info(f"[NET] Sesion {session['id']}: 0 requests (logs vacios)")
                    
            except Exception as e:
                logger.error(f"Error en capture_network_tokens sesion {session['id']}: {e}")

    def capture_session_cookies(self):
        """Extrae cookies COMPLETAS (incluyendo HttpOnly via CDP) + localStorage.
        Sube automáticamente al Cloudflare Worker para la extensión."""
        for session in self.sessions:
            if not session.get('captured_redirect_url'):
                continue
            if session.get('cookies_uploaded'):
                continue
            try:
                driver = session.get('driver')
                if not driver:
                    continue
                try:
                    if not driver.service.is_connectable():
                        continue
                except:
                    continue
                
                # CDP: captura TODAS las cookies incluyendo HttpOnly (CLID)
                try:
                    cdp_result = driver.execute_cdp_cmd('Network.getCookies', {
                        'urls': [
                            'https://bocasocios.bocajuniors.com.ar',
                            'https://bocasocios-gw.bocajuniors.com.ar',
                            'https://.bocajuniors.com.ar'
                        ]
                    })
                    all_cookies = cdp_result.get('cookies', [])
                except Exception:
                    all_cookies = driver.get_cookies()
                
                if not all_cookies:
                    continue
                
                # Capturar localStorage de bocasocios
                local_storage = {}
                try:
                    local_storage = driver.execute_script("""
                        let ls = {};
                        for (let i = 0; i < localStorage.length; i++) {
                            let key = localStorage.key(i);
                            ls[key] = localStorage.getItem(key);
                        }
                        return ls;
                    """)
                except Exception:
                    pass
                
                # Convertir cookies CDP al formato que chrome.cookies.set() necesita
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
                
                important = [c for c in chrome_cookies if any(
                    k in c['name'].lower() for k in ['queueitaccepted', 'hwwaf', 'clid']
                )]
                
                cookie_string = '; '.join(f"{c['name']}={c['value']}" for c in chrome_cookies)
                
                # Guardar localmente
                cookie_file = f"session_{session['id']}_cookies.json"
                with open(cookie_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'session_id': session['id'],
                        'timestamp': datetime.now().isoformat(),
                        'redirect_url': session.get('captured_redirect_url', ''),
                        'current_url': driver.current_url,
                        'cookies': chrome_cookies,
                        'local_storage': local_storage,
                        'cookie_string': cookie_string
                    }, f, indent=2)
                
                has_clid = any(c['name'] == 'CLID' for c in chrome_cookies)
                logger.info(
                    f"COOKIES sesion {session['id']}: "
                    f"{len(important)} criticas, {len(all_cookies)} total, "
                    f"CLID={'SI' if has_clid else 'NO'}, "
                    f"localStorage={len(local_storage)} items"
                )
                session['cookies_saved'] = True
                
                # Auto-upload al Worker (solo la primera sesión con cookies críticas)
                if important and not getattr(self, '_worker_uploaded', False):
                    self._upload_to_worker(session['id'], chrome_cookies, cookie_string, local_storage)
                
            except Exception as e:
                logger.debug(f"Error capturando cookies sesion {session['id']}: {e}")

    def _upload_to_worker(self, session_id, cookies, cookie_string, local_storage):
        """Sube cookies + localStorage al Cloudflare Worker."""
        try:
            payload = {
                'cookies': cookies,
                'cookie_string': cookie_string,
                'local_storage': local_storage,
                'evento': 868,
                'source': f'queue-bot-session-{session_id}',
                'active': True,
            }
            resp = http_requests.post(
                f'{WORKER_URL}/api/cookies',
                json=payload,
                headers={'X-API-Key': WORKER_API_KEY, 'Content-Type': 'application/json'},
                timeout=10
            )
            if resp.ok:
                data = resp.json()
                logger.info(
                    f"UPLOAD sesion {session_id} -> Worker OK: "
                    f"{data.get('critical_count', 0)} criticas, "
                    f"localStorage={len(local_storage)} items"
                )
                self._worker_uploaded = True
            else:
                logger.warning(f"UPLOAD sesion {session_id} -> Worker FALLO: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"UPLOAD sesion {session_id} -> Worker ERROR: {e}")

    def burst_refresh_all(self, max_retries: int = 3) -> Dict:
        """⚡⚡⚡ BURST: Refresca TODAS las sesiones SIMULTÁNEAMENTE sin delays
        
        Diseñado para el momento exacto de apertura - máxima velocidad
        Args:
            max_retries: Número de reintentos rápidos si dice "calculando"
        Returns:
            Dict con resultados del burst
        """
        logger.info("=" * 60)
        logger.info("🚀🚀🚀 BURST MODE ACTIVADO - TODAS LAS SESIONES SIMULTÁNEAS")
        logger.info("=" * 60)
        
        results = {
            'success': 0,
            'error': 0,
            'best_time': None,
            'best_session_id': None,
            'times': []
        }
        results_lock = threading.Lock()
        
        def burst_single_session(session):
            """Burst de una sesión individual - SIN DELAYS, máxima velocidad"""
            try:
                driver = session.get('driver')
                if not driver:
                    return
                
                # Verificar conexión
                try:
                    if not driver.service.is_connectable():
                        return
                except:
                    return
                
                # ⚡ REFRESH INMEDIATO
                driver.refresh()
                
                # ⚡ ESPERA MÍNIMA para que cargue la página
                time.sleep(0.5)
                
                # ⚡ RETRY LOOP RÁPIDO - Si dice "calculando", reintentar inmediato
                for retry in range(max_retries):
                    try:
                        # Buscar elemento de tiempo con timeout corto
                        time_element = WebDriverWait(driver, 2).until(
                            EC.presence_of_element_located((By.ID, "MainPart_lbWhichIsIn"))
                        )
                        
                        time_text = time_element.text.strip()
                        
                        # ⚡ TEXTOS DE CARGA - RETRY INMEDIATO
                        loading_texts = ['calculando', 'cargando', 'obteniendo', 'loading', 
                                        'espere', 'wait', 'procesando', 'please wait']
                        
                        if any(word in time_text.lower() for word in loading_texts):
                            logger.info(f"⏳ Sesión {session['id']}: '{time_text}' - RETRY #{retry+1}")
                            time.sleep(0.3)  # ⚡ Espera mínima antes de retry
                            driver.refresh()
                            time.sleep(0.3)
                            continue  # ⚡ RETRY INMEDIATO
                        
                        # Extraer tiempo
                        import re
                        time_match = re.search(r'(\d+)', time_text)
                        
                        if time_match:
                            wait_time = int(time_match.group(1))
                            
                            # Actualizar sesión
                            session['wait_time'] = wait_time
                            session['status'] = 'active'
                            session['last_update'] = datetime.now()
                            session['raw_time_text'] = time_text
                            
                            with results_lock:
                                results['success'] += 1
                                results['times'].append({
                                    'session_id': session['id'],
                                    'time': wait_time
                                })
                                
                                # Trackear mejor tiempo
                                if results['best_time'] is None or wait_time < results['best_time']:
                                    results['best_time'] = wait_time
                                    results['best_session_id'] = session['id']
                            
                            logger.info(f"✅ Sesión {session['id']}: {wait_time} min")
                            return
                        
                        # "Más de una hora"
                        elif any(phrase in time_text.lower() for phrase in ['más de una hora', 'more than an hour']):
                            session['wait_time'] = 65
                            session['status'] = 'active'
                            session['last_update'] = datetime.now()
                            session['raw_time_text'] = time_text
                            
                            with results_lock:
                                results['success'] += 1
                                results['times'].append({
                                    'session_id': session['id'],
                                    'time': 65
                                })
                            
                            logger.info(f"⏰ Sesión {session['id']}: >1 hora")
                            return
                        
                        # Acceso inmediato
                        elif any(phrase in time_text.lower() for phrase in ['listo', 'ready', 'accede', 'ingresa']):
                            session['wait_time'] = 0
                            session['status'] = 'ready'
                            session['last_update'] = datetime.now()
                            session['raw_time_text'] = time_text
                            
                            with results_lock:
                                results['success'] += 1
                                results['best_time'] = 0
                                results['best_session_id'] = session['id']
                                results['times'].append({
                                    'session_id': session['id'],
                                    'time': 0
                                })
                            
                            logger.info(f"🎯 Sesión {session['id']}: ¡ACCESO INMEDIATO!")
                            return
                            
                    except TimeoutException:
                        logger.debug(f"Sesión {session['id']}: Elemento no encontrado, retry #{retry+1}")
                        if retry < max_retries - 1:
                            driver.refresh()
                            time.sleep(0.3)
                
                # Si llegamos aquí, no se pudo obtener tiempo
                with results_lock:
                    results['error'] += 1
                    
            except Exception as e:
                logger.error(f"Error en burst sesión {session['id']}: {e}")
                with results_lock:
                    results['error'] += 1
        
        # ⚡⚡⚡ LANZAR TODOS LOS THREADS SIMULTÁNEAMENTE (SIN DELAY)
        threads = []
        start_time = time.time()
        
        for session in self.sessions:
            thread = threading.Thread(target=burst_single_session, args=(session,))
            thread.start()
            threads.append(thread)
        
        # Esperar a que todos terminen
        for thread in threads:
            thread.join(timeout=15)  # Timeout de 15 seg máximo
        
        # Capturar tokens de network logs después del burst
        self.capture_network_tokens()
        
        elapsed = time.time() - start_time
        
        # Ordenar resultados por tiempo
        results['times'] = sorted(results['times'], key=lambda x: x['time'])
        
        logger.info("=" * 60)
        logger.info(f"🏁 BURST COMPLETADO en {elapsed:.2f}s")
        logger.info(f"   ✅ Éxitos: {results['success']} | ❌ Errores: {results['error']}")
        if results['best_time'] is not None:
            logger.info(f"   🏆 MEJOR TIEMPO: {results['best_time']} min (Sesión {results['best_session_id']})")
        logger.info("=" * 60)
        
        return results

    def update_session_data(self):
        """Actualiza los datos SOLO de sesiones incompletas (EN PARALELO para máxima velocidad)"""
        # Crear una copia de la lista para evitar modificaciones durante iteración
        sessions_copy = self.sessions.copy()
        
        # Filtrar sesiones incompletas
        incomplete_sessions = []
        for session in sessions_copy:
            try:
                driver = session.get('driver')
                if not driver:
                    continue
                
                try:
                    if not driver.service.is_connectable():
                        continue
                except:
                    continue
                
                has_queue_id = session.get('queue_id') is not None
                has_wait_time = session.get('wait_time') is not None
                is_complete = has_queue_id and has_wait_time
                
                if not is_complete:
                    incomplete_sessions.append(session)
            except:
                continue
        
        if not incomplete_sessions:
            return
        
        logger.debug(f"⚡ Actualizando {len(incomplete_sessions)} sesiones EN PARALELO...")
        
        # Lock para thread-safety
        sessions_lock = threading.Lock()
        
        def update_single_session(session, delay):
            """Actualiza una sesión individual en un thread"""
            try:
                # Delay escalonado de 1 segundo entre cada una (anti-detección)
                time.sleep(delay)
                
                # Extraer datos actuales
                current_data = self.extract_queue_data(session, quick_mode=True)
                
                # Actualizar sesión de forma thread-safe
                with sessions_lock:
                    session.update(current_data)
                    
                    # Verificar si ahora está completa
                    new_has_queue_id = session.get('queue_id') is not None
                    new_has_wait_time = session.get('wait_time') is not None
                    if new_has_queue_id and new_has_wait_time:
                        logger.info(f"🎯 Sesión {session['id']}: ¡COMPLETA! Queue: {session['queue_id'][:8]}... Tiempo: {session['wait_time']} min")
                        logger.info(f"✅ Sesión {session['id']}: Ya no se actualizará automáticamente (solo manual)")
                
            except Exception as e:
                logger.error(f"Error actualizando sesión {session.get('id', 'unknown')}: {e}")
                if "invalid session id" in str(e).lower() or "no such window" in str(e).lower():
                    with sessions_lock:
                        if session in self.sessions:
                            self.sessions.remove(session)
        
        # Crear threads para actualizar sesiones en paralelo con delay anti-detección
        threads = []
        for idx, session in enumerate(incomplete_sessions):
            # 0.5 segundo base + random 0-0.25 seg (parecer más humano, evitar patrón)
            # ⚡ OPTIMIZADO: 2x más rápido que antes (era 1.0s)
            delay = idx * 0.5 + random.uniform(0, 0.25)
            thread = threading.Thread(target=update_single_session, args=(session, delay))
            thread.daemon = True
            thread.start()
            threads.append(thread)
        
        # Esperar a que todos terminen
        for thread in threads:
            thread.join(timeout=30)  # Timeout de 30 seg por si algo se traba
    
    def start_monitoring(self):
        """Inicia el monitoreo continuo de las sesiones con frecuencia adaptativa + BURST automático"""
        def monitor():
            while self.running:
                try:
                    # Calcular tiempo hasta apertura
                    current_time = datetime.now()
                    opening_time = datetime.strptime(self.opening_time, "%H:%M").time()
                    opening_datetime = datetime.combine(current_time.date(), opening_time)
                    time_until_opening = (opening_datetime - current_time).total_seconds()
                    
                    # ⚡⚡⚡ BURST AUTOMÁTICO: Cuando llega la hora exacta de apertura
                    if not self.burst_executed and -5 <= time_until_opening <= 5:
                        # Estamos en el momento de apertura (±5 segundos)
                        with self.burst_lock:
                            if not self.burst_executed:
                                logger.info("🚀🚀🚀 ¡HORA DE APERTURA DETECTADA! INICIANDO BURST AUTOMÁTICO...")
                                self.burst_executed = True
                                self.burst_refresh_all(max_retries=10)  # 10 reintentos en burst automático
                                continue  # Saltar al siguiente ciclo
                    
                    # ✅ VERIFICAR SI TODAS LAS SESIONES ESTÁN COMPLETAS
                    complete_sessions = 0
                    for s in self.sessions:
                        if s.get('queue_id') and s.get('wait_time') is not None:
                            complete_sessions += 1
                    
                    # ✅ SI TODAS ESTÁN COMPLETAS, REDUCIR FRECUENCIA DRÁSTICAMENTE
                    if complete_sessions == len(self.sessions) and len(self.sessions) > 0:
                        monitor_interval = 120  # Solo cada 2 minutos
                        logger.info(f"🎯 TODAS las {len(self.sessions)} sesiones están completas - Monitoreo reducido: cada 2 minutos")
                    else:
                        # Determinar frecuencia de monitoreo basada en proximidad a apertura
                        if time_until_opening <= 0:
                            # Ya pasó la hora de apertura - monitoreo muy frecuente
                            monitor_interval = 3
                            logger.debug("Monitoreo post-apertura: cada 3 segundos")
                        elif time_until_opening <= 60:
                            # Último minuto antes de apertura - monitoreo muy frecuente  
                            monitor_interval = 5
                            logger.debug("Monitoreo pre-apertura (último minuto): cada 5 segundos")
                        elif time_until_opening <= 300:
                            # Últimos 5 minutos - monitoreo frecuente
                            monitor_interval = 8
                            logger.debug("Monitoreo pre-apertura (últimos 5 min): cada 8 segundos")
                        elif time_until_opening <= 600:
                            # Últimos 10 minutos - monitoreo medio
                            monitor_interval = 15
                            logger.debug("Monitoreo pre-apertura (últimos 10 min): cada 15 segundos")
                        else:
                            # Más de 10 minutos - monitoreo normal
                            monitor_interval = 30
                            logger.debug("Monitoreo normal: cada 30 segundos")
                        
                        # Mostrar progreso de sesiones incompletas
                        incomplete_sessions = len(self.sessions) - complete_sessions
                        if incomplete_sessions > 0:
                            logger.debug(f"📊 {incomplete_sessions}/{len(self.sessions)} sesiones aún necesitan datos")
                    
                    # ⚡ CAPTURAR TOKENS de network logs SIEMPRE (no perder ningún 302)
                    self.capture_network_tokens()
                    
                    # Extraer cookies de sesiones que pasaron Queue-it
                    try:
                        self.capture_session_cookies()
                    except:
                        pass
                    
                    self.update_session_data()
                    time.sleep(monitor_interval)
                    
                except Exception as e:
                    logger.error(f"Error en monitoreo: {e}")
                    time.sleep(5)
        
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
    
    def get_sessions_data(self) -> List[Dict]:
        """Obtiene datos de todas las sesiones para el dashboard"""
        sessions_data = []
        
        for session in self.sessions:
            # ⚡ OBTENER LINK COMPLETO con token de Queue-it para copiar
            full_url = session.get('url', '')
            redirect_url = session.get('captured_redirect_url', None)  # ← Usar URL capturada de network
            
            # ⚡ Si no está en memoria, intentar cargar desde archivo JSON
            if not redirect_url:
                try:
                    json_file = f"session_{session['id']}_token.json"
                    if os.path.exists(json_file):
                        with open(json_file, 'r', encoding='utf-8') as f:
                            saved_data = json.load(f)
                            redirect_url = saved_data.get('url')
                            session['captured_redirect_url'] = redirect_url  # Restaurar en memoria
                            logger.debug(f"📂 Token de sesión {session['id']} restaurado desde {json_file}")
                except Exception as load_error:
                    logger.debug(f"No se pudo cargar token guardado: {load_error}")
            
            try:
                driver = session.get('driver')
                if driver:
                    # URL actual
                    full_url = driver.current_url
                    
                    # Los network logs se capturan en capture_network_tokens() (centralizado)
                    # Solo leer el redirect ya capturado
                    if not redirect_url and session.get('captured_redirect_url'):
                        redirect_url = session['captured_redirect_url']
                    
                    # ⚡⚡⚡ BUSCAR TOKEN EN COOKIES (Queue-it lo guarda ahí)
                    try:
                        cookies = driver.get_cookies()
                        queueit_token = None
                        
                        # Buscar cookie de Queue-it
                        for cookie in cookies:
                            cookie_name = cookie.get('name', '').lower()
                            if 'queueit' in cookie_name or 'queue-it' in cookie_name:
                                cookie_value = cookie.get('value', '')
                                if cookie_value and len(cookie_value) > 20:
                                    queueit_token = cookie_value
                                    logger.debug(f"Sesión {session['id']}: Token encontrado en cookie '{cookie['name']}'")
                                    break
                        
                        # Si no está en cookies, buscar en localStorage
                        if not queueit_token:
                            queueit_token = driver.execute_script("""
                                // Buscar token en localStorage
                                for (let i = 0; i < localStorage.length; i++) {
                                    let key = localStorage.key(i);
                                    if (key && (key.toLowerCase().includes('queueit') || key.toLowerCase().includes('queue-it'))) {
                                        let value = localStorage.getItem(key);
                                        if (value && value.length > 20) {
                                            return value;
                                        }
                                    }
                                }
                                return null;
                            """)
                        
                        # ⚡ Si encontramos token, reconstruir URL de redirect
                        if queueit_token and session.get('queue_id'):
                            # Formato típico de Queue-it redirect:
                            # https://bocasocios-gw.bocajuniors.com.ar/queueit/redirect?queueittoken=TOKEN
                            
                            # Extraer dominio base de la URL actual
                            from urllib.parse import urlparse
                            parsed = urlparse(full_url)
                            base_domain = f"{parsed.scheme}://{parsed.netloc}"
                            
                            # Reconstruir URL de redirect
                            redirect_url = f"{base_domain}/queueit/redirect?queueittoken={queueit_token}"
                            logger.debug(f"Sesión {session['id']}: URL de redirect reconstruida desde cookies/storage")
                            
                    except Exception as token_error:
                        logger.debug(f"Sesión {session['id']}: No se pudo extraer token: {token_error}")
                        
            except Exception as e:
                logger.debug(f"Error obteniendo URL sesión {session['id']}: {e}")
            
            session_info = {
                'id': session['id'],
                'queue_id': session['queue_id'],
                'wait_time': session['wait_time'],
                'status': session['status'],
                'last_update': session['last_update'].strftime("%H:%M:%S"),
                'url': session['url'],
                'full_url': redirect_url if redirect_url else full_url,  # ← Usar redirect reconstruido si existe
                'raw_time_text': session.get('raw_time_text', 'Sin texto')
            }
            sessions_data.append(session_info)
        
        return sessions_data
    
    def get_best_session(self) -> Optional[Dict]:
        """Obtiene la sesión con menor tiempo de espera"""
        active_sessions = [s for s in self.sessions if s['wait_time'] is not None]
        
        if not active_sessions:
            return None
        
        return min(active_sessions, key=lambda x: x['wait_time'])
    
    def get_top_sessions(self, count: int = 3) -> List[Dict]:
        """Obtiene las mejores N sesiones ordenadas por tiempo de espera"""
        active_sessions = [s for s in self.sessions if s['wait_time'] is not None]
        
        if not active_sessions:
            return []
        
        # Ordenar por tiempo de espera (menor a mayor)
        sorted_sessions = sorted(active_sessions, key=lambda x: x['wait_time'])
        
        # Retornar las mejores N sesiones
        return sorted_sessions[:count]
    
    def focus_multiple_sessions(self, session_ids: List[int]) -> List[bool]:
        """Enfoca múltiples sesiones específicas"""
        results = []
        
        for session_id in session_ids:
            try:
                session = next((s for s in self.sessions if s['id'] == session_id), None)
                if session and session['driver']:
                    driver = session['driver']
                    
                    # Configurar ventana para múltiples sesiones
                    window_width = 800
                    window_height = 600
                    
                    # Calcular posición para que no se superpongan
                    x_offset = (session_id % 3) * (window_width + 10)
                    y_offset = (session_id // 3) * (window_height + 40)
                    
                    driver.set_window_position(50 + x_offset, 50 + y_offset)
                    driver.set_window_size(window_width, window_height)
                    
                    # Simular comportamiento humano
                    simulate_human_behavior(driver, duration=1)
                    
                    results.append(True)
                    logger.info(f"Sesión {session_id} enfocada en posición ({50 + x_offset}, {50 + y_offset})")
                else:
                    results.append(False)
                    
            except Exception as e:
                logger.error(f"Error enfocando sesión {session_id}: {e}")
                results.append(False)
        
        return results
    
    def focus_session(self, session_id: int) -> bool:
        """Restaura una sesión headless como ventana normal (mantiene TODO: cookies, localStorage, sessionStorage)
        
        NOTA: Puede dar error 418 del WAF si se intenta navegar con el token.
        Solución: Usa el link que se copia desde el dashboard en otro navegador/IP.
        """
        try:
            session = next((s for s in self.sessions if s['id'] == session_id), None)
            if not session or not session['driver']:
                logger.error(f"Sesión {session_id} no encontrada o sin driver")
                return False
            
            old_driver = session['driver']
            profile_path = os.path.join(self.profiles_dir, f"profile_{session_id}")
            
            # ⚡ CRÍTICO: Obtener el MISMO user agent que headless usó
            original_user_agent = session.get('user_agent', get_random_user_agent())
            logger.info(f"🔄 Usando MISMO User-Agent: {original_user_agent[:50]}...")
            
            logger.info(f"🔄 Capturando estado completo de sesión {session_id}...")
            
            # ⚡ CAPTURAR TODO EL ESTADO ANTES DE CERRAR
            try:
                current_url = old_driver.current_url
                cookies = old_driver.get_cookies()
                
                local_storage = old_driver.execute_script("""
                    let ls = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        let key = localStorage.key(i);
                        ls[key] = localStorage.getItem(key);
                    }
                    return ls;
                """)
                
                session_storage = old_driver.execute_script("""
                    let ss = {};
                    for (let i = 0; i < sessionStorage.length; i++) {
                        let key = sessionStorage.key(i);
                        ss[key] = sessionStorage.getItem(key);
                    }
                    return ss;
                """)
                
                logger.info(f"✅ Estado capturado: {len(cookies)} cookies, localStorage: {len(local_storage)} items, sessionStorage: {len(session_storage)} items")
                
            except Exception as capture_error:
                logger.error(f"Error capturando estado: {capture_error}")
                current_url = old_driver.current_url
                cookies = []
                local_storage = {}
                session_storage = {}
            
            # Cerrar driver headless
            try:
                old_driver.quit()
            except:
                pass
            
            logger.info(f"🔄 Creando nueva sesión CON VENTANA (MISMA configuración que headless)...")
            
            # ⚡⚡⚡ CRÍTICO: Usar EXACTAMENTE las mismas opciones que headless (excepto --headless)
            options = Options()
            
            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument(f"--profile-directory=Default")
            options.add_argument(f"--user-agent={original_user_agent}")
            
            # ⚡ MISMAS configuraciones anti-detección que headless
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins-discovery")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-sync")
            options.add_argument("--disable-translate")
            options.add_argument("--disable-features=VizDisplayCompositor,TranslateUI")
            options.add_argument("--disable-ipc-flooding-protection")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--disable-component-extensions-with-background-pages")
            options.add_argument("--disable-logging")
            options.add_argument("--log-level=3")
            options.add_argument("--blink-settings=imagesEnabled=false")
            
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.media_stream_mic": 2,
                "profile.default_content_setting_values.media_stream_camera": 2,
                "profile.default_content_setting_values.geolocation": 2,
                "profile.password_manager_enabled": False,
                "credentials_enable_service": False,
                "profile.default_content_settings.popups": 0
            })
            
            # Crear nuevo driver
            new_driver = webdriver.Chrome(options=options)
            
            # Habilitar Network logging via CDP
            new_driver.execute_cdp_cmd('Network.enable', {})
            
            # ⚡ APLICAR protecciones anti-bot ANTES de navegar
            randomize_browser_properties(new_driver)
            
            # Configurar ventana
            new_driver.set_window_position(100, 100)
            new_driver.set_window_size(1200, 800)
            
            # Ir al dominio base primero
            parsed_url = urlparse(current_url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            logger.info(f"🔄 Navegando a dominio base: {base_url}")
            new_driver.get(base_url)
            time.sleep(2)
            
            # ⚡ RESTAURAR TODO EL ESTADO
            try:
                logger.info(f"🔄 Restaurando {len(cookies)} cookies...")
                for cookie in cookies:
                    try:
                        cookie_copy = cookie.copy()
                        cookie_copy.pop('expiry', None)
                        cookie_copy.pop('httpOnly', None) 
                        cookie_copy.pop('sameSite', None)
                        new_driver.add_cookie(cookie_copy)
                    except Exception as cookie_error:
                        logger.debug(f"Cookie ya existe o error: {cookie_error}")
                
                if local_storage:
                    new_driver.execute_script("""
                        let ls = arguments[0];
                        for (let key in ls) {
                            localStorage.setItem(key, ls[key]);
                        }
                    """, local_storage)
                    logger.info(f"✅ localStorage restaurado: {len(local_storage)} items")
                
                if session_storage:
                    new_driver.execute_script("""
                        let ss = arguments[0];
                        for (let key in ss) {
                            sessionStorage.setItem(key, ss[key]);
                        }
                    """, session_storage)
                    logger.info(f"✅ sessionStorage restaurado: {len(session_storage)} items")
                
                logger.info(f"🔄 Navegando a URL original: {current_url}")
                new_driver.get(current_url)
                
                logger.info(f"✅ Sesión restaurada (puede dar 418 si intenta usar el token)")
                
            except Exception as restore_error:
                logger.error(f"Error restaurando estado: {restore_error}")
            
            # Actualizar la sesión con el nuevo driver
            session['driver'] = new_driver
            
            if old_driver in self.drivers:
                self.drivers.remove(old_driver)
            self.drivers.append(new_driver)
            
            logger.info(f"✅ Sesión {session_id} COMPLETAMENTE restaurada con ventana")
            logger.info(f"   → User-Agent: ✓ | Cookies: ✓ | localStorage: ✓ | sessionStorage: ✓ | Perfil: ✓")
            logger.info(f"   💡 Si da error 418: Usa el link del dashboard desde otro navegador/IP")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error restaurando sesión {session_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def refresh_session(self, session_id: int) -> bool:
        """Actualiza una sesión específica FORZADO (incluso si ya está completa)"""
        try:
            session = next((s for s in self.sessions if s['id'] == session_id), None)
            if session and session['driver']:
                logger.info(f"🔄 Sesión {session_id}: Refresh MANUAL forzado")
                session['driver'].refresh()
                time.sleep(3)
                
                # ✅ ACTUALIZAR SOLO ESTA SESIÓN (FORZADO)
                try:
                    # Extraer datos actuales (SIEMPRE, sin verificar si está completa)
                    current_data = self.extract_queue_data(session)
                    
                    # Actualizar sesión
                    session.update(current_data)
                    
                    logger.info(f"✅ Sesión {session_id}: Actualizada manualmente - Queue: {session.get('queue_id', 'N/A')[:8]}... Tiempo: {session.get('wait_time', 'N/A')}")
                    
                except Exception as e:
                    logger.error(f"Error extrayendo datos sesión {session_id}: {e}")
                    session['status'] = 'error'
                
                return True
        except Exception as e:
            logger.error(f"Error refrescando sesión {session_id}: {e}")
        
        return False
    
    def close_session(self, session_id: int) -> bool:
        """Cierra una sesión específica"""
        try:
            session = next((s for s in self.sessions if s['id'] == session_id), None)
            if not session:
                logger.warning(f"⚠️  Sesión {session_id} no encontrada")
                return False
                
            # Verificar si la sesión tiene driver
            driver = session.get('driver')
            if driver:
                try:
                    # Cerrar el driver
                    driver.quit()
                    logger.info(f"❌ Sesión {session_id} cerrada: Queue: {session.get('queue_id', 'N/A')[:8] if session.get('queue_id') else 'N/A'}... Tiempo: {session.get('wait_time', 'N/A')} min")
                except Exception as driver_error:
                    logger.warning(f"⚠️  Error cerrando driver de sesión {session_id}: {driver_error}")
                
                # Remover de la lista de drivers si existe
                if driver in self.drivers:
                    self.drivers.remove(driver)
            else:
                logger.warning(f"⚠️  Sesión {session_id} no tiene driver activo")
            
            # Remover de la lista de sesiones
            self.sessions = [s for s in self.sessions if s['id'] != session_id]
            
            logger.info(f"✅ Sesión {session_id} eliminada del sistema - Quedan {len(self.sessions)} sesiones activas")
            return True
                
        except Exception as e:
            logger.error(f"Error cerrando sesión {session_id}: {e}")
            # Intentar limpiar la sesión de la lista aunque haya error
            try:
                self.sessions = [s for s in self.sessions if s.get('id') != session_id]
                logger.info(f"🧹 Limpieza forzada de sesión {session_id}")
            except Exception as cleanup_error:
                logger.error(f"Error en limpieza forzada de sesión {session_id}: {cleanup_error}")
            return False

    def stop_sessions(self):
        """Detiene todas las sesiones"""
        self.running = False
        
        for driver in self.drivers:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error cerrando driver: {e}")
        
        self.sessions.clear()
        self.drivers.clear()
        
        logger.info("Todas las sesiones han sido detenidas")
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas generales"""
        total_sessions = len(self.sessions)
        active_sessions = len([s for s in self.sessions if s['status'] == 'active'])
        waiting_sessions = len([s for s in self.sessions if s['status'] == 'waiting'])
        ready_sessions = len([s for s in self.sessions if s['status'] == 'ready'])
        
        # Calcular tiempos
        sessions_with_time = [s for s in self.sessions if s['wait_time'] is not None]
        if sessions_with_time:
            best_time = min(s['wait_time'] for s in sessions_with_time)
            avg_time = sum(s['wait_time'] for s in sessions_with_time) / len(sessions_with_time)
        else:
            best_time = None
            avg_time = None
        
        # Countdown hasta apertura
        current_time = datetime.now()
        opening_time = datetime.strptime(self.opening_time, "%H:%M").time()
        opening_datetime = datetime.combine(current_time.date(), opening_time)
        
        if current_time < opening_datetime:
            time_until_opening = opening_datetime - current_time
            countdown = str(time_until_opening).split('.')[0]  # Remover microsegundos
        else:
            countdown = "¡ABIERTO!"
        
        return {
            'total_sessions': total_sessions,
            'active_sessions': active_sessions,
            'waiting_sessions': waiting_sessions,
            'ready_sessions': ready_sessions,
            'best_time': best_time,
            'avg_time': round(avg_time, 1) if avg_time else None,
            'countdown': countdown
        }

# Instancia global del gestor
session_manager = None

# Aplicación Flask para el dashboard
app = Flask(__name__)

@app.route('/')
def dashboard():
    """Página principal del dashboard"""
    return render_template('dashboard.html')

@app.route('/api/start', methods=['POST'])
def start_sessions():
    """Inicia las sesiones"""
    global session_manager
    
    data = request.json
    # Usar URL según entorno configurado (local o prod)
    default_url = URLS.get(ENVIRONMENT, URLS['prod'])
    target_url = data.get('target_url', default_url)
    opening_time = data.get('opening_time', '13:01')
    session_count = data.get('session_count', 25)
    
    if session_manager:
        session_manager.stop_sessions()
    
    session_manager = SessionManager(target_url, opening_time, session_count)
    session_manager.start_sessions()
    
    return jsonify({'status': 'success', 'message': f'Iniciadas {session_count} sesiones'})

@app.route('/api/stop', methods=['POST'])
def stop_sessions():
    """Detiene todas las sesiones"""
    global session_manager
    
    if session_manager:
        session_manager.stop_sessions()
        session_manager = None
    
    return jsonify({'status': 'success', 'message': 'Sesiones detenidas'})

@app.route('/api/sessions')
def get_sessions():
    """Obtiene datos de todas las sesiones"""
    if session_manager:
        sessions = session_manager.get_sessions_data()
        stats = session_manager.get_stats()
        return jsonify({
            'sessions': sessions,
            'stats': stats
        })
    
    return jsonify({'sessions': [], 'stats': {}})

@app.route('/api/focus/<int:session_id>', methods=['POST'])
def focus_session(session_id):
    """Enfoca una sesión específica"""
    if session_manager:
        success = session_manager.focus_session(session_id)
        return jsonify({'status': 'success' if success else 'error'})
    
    return jsonify({'status': 'error', 'message': 'No hay sesiones activas'})

@app.route('/api/refresh/<int:session_id>', methods=['POST'])
def refresh_session(session_id):
    """Actualiza una sesión específica"""
    if session_manager:
        success = session_manager.refresh_session(session_id)
        return jsonify({'status': 'success' if success else 'error'})
    
    return jsonify({'status': 'error', 'message': 'No hay sesiones activas'})

@app.route('/api/close/<int:session_id>', methods=['POST'])
def close_session(session_id):
    """Cierra una sesión específica"""
    if session_manager:
        success = session_manager.close_session(session_id)
        if success:
            return jsonify({
                'status': 'success', 
                'message': f'Sesión {session_id} cerrada correctamente'
            })
        else:
            return jsonify({
                'status': 'error', 
                'message': f'No se pudo cerrar la sesión {session_id}'
            })
    
    return jsonify({'status': 'error', 'message': 'No hay sesiones activas'})

@app.route('/api/best')
def get_best_session():
    """Obtiene la mejor sesión"""
    if session_manager:
        best_session = session_manager.get_best_session()
        if best_session:
            return jsonify({
                'status': 'success',
                'session': {
                    'id': best_session['id'],
                    'queue_id': best_session['queue_id'],
                    'wait_time': best_session['wait_time']
                }
            })
    
    return jsonify({'status': 'error', 'message': 'No hay sesiones con tiempos disponibles'})

@app.route('/api/top/<int:count>')
def get_top_sessions(count):
    """Obtiene las mejores N sesiones"""
    if session_manager:
        top_sessions = session_manager.get_top_sessions(count)
        if top_sessions:
            sessions_data = []
            for session in top_sessions:
                sessions_data.append({
                    'id': session['id'],
                    'queue_id': session['queue_id'],
                    'wait_time': session['wait_time'],
                    'status': session['status']
                })
            
            return jsonify({
                'status': 'success',
                'sessions': sessions_data,
                'count': len(sessions_data)
            })
    
    return jsonify({'status': 'error', 'message': 'No hay sesiones disponibles'})

@app.route('/api/focus_multiple', methods=['POST'])
def focus_multiple_sessions():
    """Enfoca múltiples sesiones"""
    if not session_manager:
        return jsonify({'status': 'error', 'message': 'No hay sesiones activas'})
    
    data = request.json
    count = data.get('count', 3)
    session_ids = data.get('session_ids', [])
    
    if session_ids:
        # Usar IDs específicos
        results = session_manager.focus_multiple_sessions(session_ids)
        success_count = sum(results)
        
        return jsonify({
            'status': 'success',
            'message': f'Se enfocaron {success_count}/{len(session_ids)} sesiones',
            'results': results
        })
    else:
        # Usar las mejores sesiones
        top_sessions = session_manager.get_top_sessions(count)
        if top_sessions:
            session_ids = [s['id'] for s in top_sessions]
            results = session_manager.focus_multiple_sessions(session_ids)
            success_count = sum(results)
            
            return jsonify({
                'status': 'success',
                'message': f'Se enfocaron las {success_count} mejores sesiones',
                'session_ids': session_ids,
                'results': results
            })
        else:
            return jsonify({'status': 'error', 'message': 'No hay sesiones con tiempos disponibles'})

@app.route('/api/open_top_sessions/<int:count>', methods=['POST'])
def open_top_sessions(count):
    """Abre las mejores N sesiones"""
    if not session_manager:
        return jsonify({'status': 'error', 'message': 'No hay sesiones activas'})
    
    top_sessions = session_manager.get_top_sessions(count)
    if top_sessions:
        session_ids = [s['id'] for s in top_sessions]
        results = session_manager.focus_multiple_sessions(session_ids)
        success_count = sum(results)
        
        # Información de las sesiones abiertas
        sessions_info = []
        for session in top_sessions:
            sessions_info.append({
                'id': session['id'],
                'queue_id': session['queue_id'],
                'wait_time': session['wait_time']
            })
        
        return jsonify({
            'status': 'success',
            'message': f'Se abrieron las {success_count} mejores sesiones',
            'sessions': sessions_info
        })
    else:
        return jsonify({'status': 'error', 'message': 'No hay sesiones con tiempos disponibles'})

@app.route('/api/burst', methods=['POST'])
def burst_refresh():
    """⚡ BURST: Refresca TODAS las sesiones SIMULTÁNEAMENTE - Máxima velocidad"""
    if not session_manager:
        return jsonify({'status': 'error', 'message': 'No hay sesiones activas'})
    
    try:
        data = request.json or {}
        max_retries = data.get('max_retries', 3)
        
        logger.info("🚀 BURST MANUAL INICIADO desde dashboard")
        results = session_manager.burst_refresh_all(max_retries=max_retries)
        
        return jsonify({
            'status': 'success',
            'message': f'BURST completado: {results["success"]} éxitos, {results["error"]} errores',
            'best_time': results['best_time'],
            'best_session_id': results['best_session_id'],
            'times': results['times'][:10]  # Top 10
        })
        
    except Exception as e:
        logger.error(f"Error en burst: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/reset_burst', methods=['POST'])
def reset_burst():
    """Resetea el flag de burst para permitir otro burst automático"""
    if not session_manager:
        return jsonify({'status': 'error', 'message': 'No hay sesiones activas'})
    
    session_manager.burst_executed = False
    logger.info("🔄 Flag de burst reseteado - Burst automático habilitado nuevamente")
    
    return jsonify({
        'status': 'success',
        'message': 'Burst automático habilitado nuevamente'
    })

@app.route('/api/force_update_all', methods=['POST'])
def force_update_all():
    """Fuerza actualización de TODAS las sesiones ESCALONADO (1 seg entre cada una) - SOLO MANUAL"""
    if not session_manager:
        return jsonify({'status': 'error', 'message': 'No hay sesiones activas'})
    
    try:
        logger.info("🔄 FORZANDO actualización ESCALONADA de TODAS las sesiones (quick mode)")
        
        results = {'success': 0, 'error': 0}
        results_lock = threading.Lock()
        
        def update_single_session(session, delay):
            """Función para actualizar una sesión individual con delay escalonado"""
            try:
                # Esperar el delay escalonado (1 segundo entre cada sesión)
                time.sleep(delay)
                
                if session['driver'] and session['driver'].service.is_connectable():
                    logger.info(f"🔄 Forzando actualización sesión {session['id']} (delay: {delay}s)")
                    session['driver'].refresh()
                    time.sleep(1)  # Pausa corta después del refresh
                    
                    # Extraer datos actuales con QUICK MODE (timeouts reducidos)
                    current_data = session_manager.extract_queue_data(session, quick_mode=True)
                    session.update(current_data)
                    
                    with results_lock:
                        results['success'] += 1
                    
                    logger.info(f"✅ Sesión {session['id']} actualizada: Queue {session.get('queue_id', 'N/A')[:8]}... Tiempo: {session.get('wait_time', 'N/A')} min")
                    
            except Exception as e:
                logger.error(f"Error actualizando sesión {session['id']}: {e}")
                with results_lock:
                    results['error'] += 1
        
        # Crear threads con delays escalonados (0.5 seg + random para parecer más humano)
        threads = []
        for idx, session in enumerate(session_manager.sessions):
            # 0.5 segundo base + random de 0-0.25 seg (evita patrón exacto de bot)
            # ⚡ OPTIMIZADO: 2x más rápido que antes (era 1.0s)
            delay = idx * 0.5 + random.uniform(0, 0.25)
            thread = threading.Thread(target=update_single_session, args=(session, delay))
            thread.start()
            threads.append(thread)
        
        # Esperar a que todos terminen
        for thread in threads:
            thread.join()
        
        total_sessions = len(session_manager.sessions)
        estimated_time = (total_sessions * 0.5) + 8  # Delay escalonado (0.5s) + tiempo de procesamiento
        
        return jsonify({
            'status': 'success',
            'message': f'Se actualizaron {results["success"]} sesiones escalonadas ({results["error"]} errores) - Tiempo: ~{estimated_time}s'
        })
        
    except Exception as e:
        logger.error(f"Error en actualización forzada: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    
    print("=" * 80)
    print("Sistema de Gestion de Sesiones HEADLESS + UI v4 - BURST MODE")
    print("=" * 80)
    print("Modo HEADLESS: Sin ventanas, 50% menos memoria, 2-3x mas rapido")
    print("Dashboard web para control facil")
    print("Dashboard disponible en: http://localhost:5000")
    print(f"\nEntorno: {ENVIRONMENT.upper()}")
    print("   Configuracion por defecto:")
    print(f"   - URL: {URLS[ENVIRONMENT]}")
    print("   - Hora apertura: 13:01")
    print("   - Sesiones: 25")
    print("\nBURST MODE (NUEVO v4):")
    print("   - BURST AUTOMATICO: Se dispara al llegar la hora de apertura")
    print("   - BURST MANUAL: POST /api/burst desde dashboard")
    print("   - Todas las sesiones se refrescan SIMULTANEAMENTE (sin delays)")
    print("   - Retry rapido cuando dice 'calculando' o 'cargando'")
    print("   - Obtiene el mejor tiempo posible en segundos")
    print("\nComo funciona:")
    print("   1. Los navegadores inician en modo HEADLESS (sin ventanas)")
    print("   2. Al llegar la hora -> BURST automatico (todas en paralelo)")
    print("   3. Si dice 'calculando' -> Retry inmediato")
    print("   4. Mantiene TODO: cookies, sesion de cola, posicion, etc.")
    print("\nRequisitos: pip install -r requirements.txt")
    print(f"\nPara cambiar a PROD: Editar linea 13 -> ENVIRONMENT = 'prod'")
    print("=" * 80 + "\n")
    
    # Modo debug desactivado para evitar reinicios automáticos que pierden las sesiones
    # Si necesitas debug, cambia a: debug=True (pero las sesiones se perderán con cada cambio de código)
    app.run(debug=False, host='0.0.0.0', port=5000) 