const fs = require('fs');
const axios = require('axios');
const { HttpsProxyAgent } = require('https-proxy-agent');
const { exec } = require('child_process');
const https = require('https');

const eventIdsToTry = [Number(process.env.EVENT_ID || 868)]; // Evento actualizado
const currentEventId = eventIdsToTry[0];

// 🎯 ASIGNAR SECTORES POR VARIABLES DE ENTORNO (múltiples sectores separados por coma)
const INSTANCE_ID = process.env.INSTANCE_ID || 'inst1';
const assignedSectorsStr = process.env.ASSIGNED_SECTORS || 'I,H'; // Ej: "J,I,G,H,F,K,M"
const assignedSectors = assignedSectorsStr.split(',').map(s => s.trim());
let sectorIdMap = {}; // Mapeo de sector -> seatId

const YOUTUBE_VIDEO_URL = 'https://www.youtube.com/watch?v=hcD8cISZrKM&autoplay=1';
const RETRY_INTERVAL_MS = 5000; // 🔧 500ms = ~120 req/min
const REQUEST_TIMEOUT_MS = 5000; // ⚡ Timeout de 5 segundos

// 🚨 DETECCIÓN DE THROTTLING (anti-detección)
const THROTTLE_THRESHOLD_MS = 99999; // DESACTIVADO temporalmente
const THROTTLE_COUNT_LIMIT = 999; // DESACTIVADO temporalmente
const THROTTLE_PAUSE_MS = 0; // DESACTIVADO temporalmente
let throttleCount = 0; // Contador de requests lentas consecutivas

// 🔥 ANTI-WAF: Randomizar mayúsculas/minúsculas en el host Y path
const BASE_HOST = 'bocasocios-gw.bocajuniors.com.ar';

function randomizeCase(str) {
  return str.split('').map(char => {
    // Solo randomizar letras, no números ni símbolos
    if (/[a-zA-Z]/.test(char)) {
      return Math.random() > 0.5 ? char.toUpperCase() : char.toLowerCase();
    }
    return char;
  }).join('');
}

// Alias para compatibilidad
function randomizeHostCase(host) {
  return randomizeCase(host);
}

// 🔀 Randomizar path (excepto números y IDs)
function randomizePath(path) {
  // Separar por / y randomizar cada parte (excepto números puros)
  return path.split('/').map(part => {
    // Si es un número puro (como IDs), no tocar
    if (/^\d+$/.test(part)) {
      return part;
    }
    return randomizeCase(part);
  }).join('/');
}

// randomizePath: true para GET, false para POST reserva
function getRandomizedUrl(path, shouldRandomizePath = false) {
  const randomHost = randomizeCase(BASE_HOST);
  const finalPath = shouldRandomizePath ? randomizePath(path) : path;
  return `https://${randomHost}${finalPath}`;
}

// === 📊 FEATURE FLAG: CALCULAR CONSUMO DE DATOS ===
const CALCULATE_DATA_CONSUMPTION = process.env.CALC_MB === 'true';
let totalBytesConsumed = 0;
let totalRequestsForDataCalc = 0;
const DATA_CONSUMPTION_LOG = './data-consumption.txt';

function calculateRequestSize(url, headers, data = null) {
  let size = 0;
  size += url.length + 20;
  for (const [key, value] of Object.entries(headers)) {
    size += key.length + value.toString().length + 4;
  }
  size += 2;
  if (data) {
    size += JSON.stringify(data).length;
  }
  return size;
}

function calculateResponseSize(response) {
  let size = 0;
  size += 20;
  const headers = response.headers || {};
  for (const [key, value] of Object.entries(headers)) {
    size += key.length + value.toString().length + 4;
  }
  size += 2;
  if (headers['content-length']) {
    size += parseInt(headers['content-length']);
  } else if (response.data) {
    size += JSON.stringify(response.data).length;
  }
  return size;
}

function logDataConsumption(requestSize, responseSize, type) {
  const totalSize = requestSize + responseSize;
  totalBytesConsumed += totalSize;
  totalRequestsForDataCalc++;
  
  const mb = (totalBytesConsumed / (1024 * 1024)).toFixed(2);
  const avgPerRequest = (totalBytesConsumed / totalRequestsForDataCalc / 1024).toFixed(2);
  
  const logLine = `[${new Date().toISOString()}] [${INSTANCE_ID}] ${type}: ↑${(requestSize/1024).toFixed(2)}KB ↓${(responseSize/1024).toFixed(2)}KB | Total: ${mb}MB (${totalRequestsForDataCalc} req, avg ${avgPerRequest}KB/req)`;
  
  console.log(`📊 ${logLine}`);
  
  try {
    fs.appendFileSync(DATA_CONSUMPTION_LOG, logLine + '\n', { encoding: 'utf8' });
    
    if (totalRequestsForDataCalc % 50 === 0) {
      const summary = `\n═══════════════════════════════════════════════════════════════\n` +
                     `📊 RESUMEN [${INSTANCE_ID}] - ${totalRequestsForDataCalc} requests\n` +
                     `   Total consumido: ${mb} MB\n` +
                     `   Promedio por request: ${avgPerRequest} KB\n` +
                     `   Estimado por minuto (30 req/min): ${(avgPerRequest * 30 / 1024).toFixed(2)} MB/min\n` +
                     `   Estimado por hora: ${(avgPerRequest * 30 * 60 / 1024).toFixed(2)} MB/hora\n` +
                     `═══════════════════════════════════════════════════════════════\n`;
      
      fs.appendFileSync(DATA_CONSUMPTION_LOG, summary, { encoding: 'utf8' });
      console.log(`\n${summary}`);
    }
  } catch (err) {
    console.error(`❌ Error guardando consumo de datos: ${err.message}`);
  }
}

// === ABRIR YOUTUBE EN CASO DE RESERVA EXITOSA ===
function openYoutube() {
  try {
    // 🔥 FIX: En Windows el & corta el comando, necesita comillas
    const command = process.platform === 'win32' 
      ? `start "" "${YOUTUBE_VIDEO_URL}"` 
      : `open "${YOUTUBE_VIDEO_URL}"`;
    
    exec(command, (error) => {
      if (error) {
        console.error(`❌ Error abriendo YouTube: ${error.message}`);
      } else {
        console.log(`🎥 YouTube abierto: ${YOUTUBE_VIDEO_URL}`);
      }
    });
  } catch (error) {
    console.error(`❌ Error al ejecutar comando YouTube: ${error.message}`);
  }
}

// === 🚀 V17: KEEP-ALIVE AGENT AGRESIVO (reutilización de conexión) ===
const keepAliveAgent = new https.Agent({
  keepAlive: true,
  keepAliveMsecs: 1000,
  maxSockets: 10,
  maxFreeSockets: 5,
  timeout: REQUEST_TIMEOUT_MS,
  freeSocketTimeout: 30000
});

// === CONFIGURACIÓN DE PROXY ===
const PROXY_USER = process.env.PROXY_USER || '';
const PROXY_PASS = process.env.PROXY_PASS || '';
const PROXY_HOST = process.env.PROXY_HOST || 'geo.iproyal.com';
const PROXY_PORT = process.env.PROXY_PORT || '12321';
let proxySessionId = 1;
let PROXY_URL = `http://${PROXY_USER}:${PROXY_PASS}_country-ar_streaming-1_session-${INSTANCE_ID}-${Date.now()}-${proxySessionId}@${PROXY_HOST}:${PROXY_PORT}`;

// === REUTILIZACIÓN DE CONEXIÓN ===
let requestsWithCurrentIP = 0;
let maxRequestsBeforeRotate = Math.floor(Math.random() * 3) + 3; // Random 3-5

// === TRACKING DE IPs LENTAS ===
const slowIPs = new Set();

// === CACHE DE UBICACIONES FALLIDAS ===
const ubicacionesFallidas = new Map();
const UBICACION_FALLIDA_TTL_MS = 10000; // 10 segundos
const MAX_FALLOS_ANTES_BLOQUEAR = 5; // 5 fallos → blacklist
const BLOQUEO_PERMANENTE_MS = 600000; // 10 minutos

let lastCleanupTime = 0;
const CLEANUP_INTERVAL_MS = 5000;

function limpiarUbicacionesExpiradas() {
  const now = Date.now();
  if (now - lastCleanupTime < CLEANUP_INTERVAL_MS) {
    return;
  }
  lastCleanupTime = now;
  
  for (const [nid, info] of ubicacionesFallidas.entries()) {
    const ttl = info.bloqueada ? BLOQUEO_PERMANENTE_MS : UBICACION_FALLIDA_TTL_MS;
    if (now - info.lastFailed > ttl) {
      ubicacionesFallidas.delete(nid);
    }
  }
}

function isUbicacionBloqueada(nid) {
  limpiarUbicacionesExpiradas();
  
  const info = ubicacionesFallidas.get(nid);
  if (!info) return false;
  
  if (info.bloqueada) return true;
  
  const now = Date.now();
  if (now - info.lastFailed < UBICACION_FALLIDA_TTL_MS) {
    return true;
  }
  
  ubicacionesFallidas.delete(nid);
  return false;
}

function getFallosUbicacion(nid) {
  const info = ubicacionesFallidas.get(nid);
  return info ? info.count : 0;
}

function marcarUbicacionFallida(nid) {
  const info = ubicacionesFallidas.get(nid);
  const now = Date.now();
  
  if (info) {
    info.count++;
    info.lastFailed = now;
    
    if (info.count >= MAX_FALLOS_ANTES_BLOQUEAR) {
      info.bloqueada = true;
      console.log(`🚫🚫🚫 [${INSTANCE_ID}] Ubicación ${nid} → BLACKLIST PERMANENTE (${info.count}/${MAX_FALLOS_ANTES_BLOQUEAR} fallos)`);
      writeReservaLog(`[${INSTANCE_ID}] 🚫 BLACKLIST: Ubicación ${nid} (${info.count} fallos)`);
    } else {
      console.log(`🚫 [${INSTANCE_ID}] Ubicación ${nid} falló ${info.count}/${MAX_FALLOS_ANTES_BLOQUEAR} veces`);
    }
  } else {
    ubicacionesFallidas.set(nid, {
      count: 1,
      lastFailed: now,
      bloqueada: false
    });
    console.log(`🚫 [${INSTANCE_ID}] Ubicación ${nid} falló 1/${MAX_FALLOS_ANTES_BLOQUEAR} veces`);
  }
}

// === CACHE DE PROXY AGENT (reutilización) ===
let cachedProxyAgent = null;
let cachedProxyURL = null;

// === CACHE DE COOKIES EN MEMORIA (USA ARCHIVOS DEL PROXY) ===
const COOKIES_FILE = './queue-cookies-proxy.txt';  // Generado por cookie-refresher.js
const TOKEN_FILE = './shared-token-proxy.json';    // Generado por cookie-refresher.js
let QUEUE_COOKIES = '';
let lastCookiesModTime = 0;
let lastTokenModTime = 0;

function loadCookies() {
  try {
    if (!fs.existsSync(COOKIES_FILE)) {
      console.error(`❌ [${INSTANCE_ID}] Archivo de cookies no encontrado: ${COOKIES_FILE}`);
      console.error(`   Ejecutá primero: node cookie-refresher-proxy.js`);
      return false;
    }
    
    const stats = fs.statSync(COOKIES_FILE);
    const mtime = stats.mtimeMs;
    
    if (mtime > lastCookiesModTime) {
      QUEUE_COOKIES = fs.readFileSync(COOKIES_FILE, 'utf8').trim();
      lastCookiesModTime = mtime;
      console.log(`🔄 [${INSTANCE_ID}] Cookies actualizadas desde archivo (proxy)`);
    }
    
    return true;
  } catch (err) {
    console.error(`❌ [${INSTANCE_ID}] Error al leer cookies: ${err.message}`);
    return false;
  }
}

// === CARGAR TOKEN DESDE ARCHIVO (GENERADO POR COOKIE-REFRESHER-PROXY) ===
function loadToken() {
  try {
    if (!fs.existsSync(TOKEN_FILE)) {
      console.error(`❌ [${INSTANCE_ID}] Archivo de token no encontrado: ${TOKEN_FILE}`);
      console.error(`   Ejecutá primero: node cookie-refresher-proxy.js`);
      return false;
    }
    
    const stats = fs.statSync(TOKEN_FILE);
    const mtime = stats.mtimeMs;
    
    if (mtime > lastTokenModTime || !token) {
      const data = JSON.parse(fs.readFileSync(TOKEN_FILE, 'utf8'));
      if (data.token) {
        token = data.token;
        lastTokenModTime = mtime;
        console.log(`🔄 [${INSTANCE_ID}] Token actualizado desde archivo (proxy)`);
        return true;
      }
    }
    
    return !!token;
  } catch (err) {
    console.error(`❌ [${INSTANCE_ID}] Error al leer token: ${err.message}`);
    return false;
  }
}

// === OBTENER Y GUARDAR SECTORES AUTOMÁTICAMENTE ===
const SECTORS_FILE = `./sectors-event-${currentEventId}.json`;

async function fetchAndSaveSectors() {
  try {
    console.log(`🔍 [${INSTANCE_ID}] Obteniendo sectores del evento ${currentEventId}...`);
    
    const url = getRandomizedUrl(`/event/${currentEventId}/seat/section/availability`, true);
    const headers = getAuthHeaders(token);
    
    const response = await axios.get(url, getAxiosConfig(url, headers));
    const secciones = response.data?.secciones || [];
    
    const laterales = ['F', 'G', 'H', 'I', 'J', 'K', 'M'];
    const sectorsMap = {};
    
    for (const seccion of secciones) {
      for (const letra of laterales) {
        if (seccion.nombre === `Seccion ${letra}` || seccion.nombre === `Sección ${letra}` || seccion.nombre === `Sector ${letra}`) {
          sectorsMap[letra] = seccion.nid;
          console.log(`   ✅ Sector ${letra}: ${seccion.nid}`);
          break;
        }
      }
    }
    
    fs.writeFileSync(SECTORS_FILE, JSON.stringify(sectorsMap, null, 2));
    console.log(`💾 [${INSTANCE_ID}] Sectores guardados en ${SECTORS_FILE}`);
    
    return sectorsMap;
  } catch (error) {
    console.error(`❌ [${INSTANCE_ID}] Error obteniendo sectores: ${error.message}`);
    return null;
  }
}

function loadSectors() {
  try {
    if (fs.existsSync(SECTORS_FILE)) {
      const data = fs.readFileSync(SECTORS_FILE, 'utf8');
      const sectorsMap = JSON.parse(data);
      console.log(`📂 [${INSTANCE_ID}] Sectores cargados desde ${SECTORS_FILE}`);
      return sectorsMap;
    }
    return null;
  } catch (err) {
    console.error(`❌ [${INSTANCE_ID}] Error cargando sectores: ${err.message}`);
    return null;
  }
}

async function getSectorId(sector) {
  let sectorsMap = loadSectors();
  
  if (!sectorsMap) {
    console.log(`📥 [${INSTANCE_ID}] Archivo de sectores no existe, obteniendo desde API...`);
    sectorsMap = await fetchAndSaveSectors();
    
    if (!sectorsMap) {
      console.error(`❌ [${INSTANCE_ID}] No se pudieron obtener los sectores`);
      return null;
    }
  }
  
  const sectorId = sectorsMap[sector];
  if (!sectorId) {
    console.error(`❌ [${INSTANCE_ID}] Sector '${sector}' no encontrado en el mapa`);
    return null;
  }
  
  return sectorId;
}

// === CARGAR MÚLTIPLES SECTORES ===
async function loadMultipleSectors(sectors) {
  let sectorsMap = loadSectors();
  
  if (!sectorsMap) {
    console.log(`📥 [${INSTANCE_ID}] Archivo de sectores no existe, obteniendo desde API...`);
    sectorsMap = await fetchAndSaveSectors();
    
    if (!sectorsMap) {
      console.error(`❌ [${INSTANCE_ID}] No se pudieron obtener los sectores`);
      return false;
    }
  }
  
  const result = {};
  for (const sector of sectors) {
    const sectorId = sectorsMap[sector];
    if (!sectorId) {
      console.error(`❌ [${INSTANCE_ID}] Sector '${sector}' no encontrado en el mapa`);
      return false;
    }
    result[sector] = sectorId;
  }
  
  return result;
}

// === CREDENCIALES ===
const EMAIL = process.env.BOCA_EMAIL || '';
const PASSWORD = Buffer.from(process.env.BOCA_PASSWORD || '').toString('base64');

let token = null;
let reservationMade = false;
let intervalId = null;
let isValidating = false;
let totalRequests = 0;

// === LOG ===
const getLogFileName = () => {
  const dateStr = new Date().toISOString().split('T')[0];
  return `log-${dateStr}-${INSTANCE_ID}.txt`;
};

const logFileName = getLogFileName();
const RESERVA_LOG = './reserva.txt';

function writeLog(message) {
  fs.appendFileSync(logFileName, message + '\n', { encoding: 'utf8' });
}

function getLocalTimestamp() {
  const now = new Date();
  const pad = (n) => n.toString().padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

function writeReservaLog(message) {
  const timestamp = `[${getLocalTimestamp()}] `;
  fs.appendFileSync(RESERVA_LOG, timestamp + message + '\n', { encoding: 'utf8' });
}

const originalLog = console.log;
const originalError = console.error;

console.log = function (...args) {
  const message = args.join(' ');
  const timestamp = `[${new Date().toLocaleTimeString()}] `;
  originalLog(timestamp + message);
  writeLog(timestamp + message);
};

console.error = function (...args) {
  const message = args.join(' ');
  const timestamp = `[${new Date().toLocaleTimeString()}] `;
  originalError(timestamp + message);
  writeLog(timestamp + message);
};

// === VARIACIONES RANDOM ===
const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.6367.118 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.6325.95 Safari/537.36',
];

const ACCEPT_LANGUAGES = [
  'es-AR,es;q=0.9,en;q=0.8',
  'es-AR,es-419;q=0.9,es;q=0.8,en;q=0.7',
  'es,en-US;q=0.9,en;q=0.8',
  'es-AR,es;q=0.9',
  'en,es-AR;q=0.9,es;q=0.8',
];

function getRandomUserAgent() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

function getRandomAcceptLanguage() {
  return ACCEPT_LANGUAGES[Math.floor(Math.random() * ACCEPT_LANGUAGES.length)];
}

// === HEADERS PRE-CALCULADOS ===
let cachedBaseHeaders = null;

function getAuthHeaders(token, includeCookies = true) {
  if (!cachedBaseHeaders) {
    cachedBaseHeaders = {
      'accept': 'application/json, text/plain, */*',
      'dnt': '1',
      'origin': 'https://bocasocios.bocajuniors.com.ar',
      'priority': 'u=1, i',
      'referer': 'https://bocasocios.bocajuniors.com.ar/',
      'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
      'sec-ch-ua-mobile': '?0',
      'sec-ch-ua-platform': '"Windows"',
      'sec-fetch-dest': 'empty',
      'sec-fetch-mode': 'cors',
      'sec-fetch-site': 'same-site',
    };
  }
  
  const headers = {
    ...cachedBaseHeaders,
    'accept-language': getRandomAcceptLanguage(),
    'authorization': `Bearer ${token}`,
    'user-agent': getRandomUserAgent(),
  };
  
  if (includeCookies) {
    headers['cookie'] = QUEUE_COOKIES;
  }
  
  return headers;
}

function getLoginHeaders() {
  return {
    'accept': 'application/json, text/plain, */*',
    'accept-language': getRandomAcceptLanguage(),
    'content-type': 'application/json',
    'dnt': '1',
    'origin': 'https://bocasocios.bocajuniors.com.ar',
    'priority': 'u=1, i',
    'referer': 'https://bocasocios.bocajuniors.com.ar/',
    'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': getRandomUserAgent(),
  };
}

// === DELAY MÍNIMO ===
async function randomDelay(min, max) {
  const delay = Math.floor(Math.random() * (max - min + 1)) + min;
  await new Promise(resolve => setTimeout(resolve, delay));
}

function getNextInterval() {
  const jitter = RETRY_INTERVAL_MS * 0.1;
  const variation = Math.random() * jitter * 2 - jitter;
  return Math.floor(RETRY_INTERVAL_MS + variation);
}

// === 🚀 V17-SIN-PROXY: CONFIGURAR TIMEOUT + KEEP-ALIVE (REUTILIZACIÓN) ===
function getAxiosConfig(url, headers, data = null) {
  const config = { 
    headers,
    timeout: REQUEST_TIMEOUT_MS,
    httpsAgent: keepAliveAgent, // ⚡ SIEMPRE reutiliza conexión local (sin proxy)
  };
  
  if (data) {
    config.data = data;
  }
  
  return config;
}

// === SIN LOGIN - USA TOKEN DEL COOKIE-REFRESHER-PROXY ===
// El token y cookies vienen de: cookie-refresher-proxy.js
// Archivos: queue-cookies-proxy.txt + shared-token-proxy.json

// === 🔥 V17-SIN-PROXY: VALIDAR Y RESERVAR CON PROCESO DE 2 PASOS (IP LOCAL) ===
async function checkAvailabilityAndReserve() {
  if (reservationMade || isValidating) {
    return;
  }

  isValidating = true;
  totalRequests++;

  try {
    await randomDelay(10, 20);
    loadCookies();
    
    // ============================================
    // 🔥 PASO 1: GET GENERAL (todas las secciones)
    // ============================================
    const generalUrl = getRandomizedUrl(`/event/${currentEventId}/seat/section/availability`, true);
    const generalHeaders = getAuthHeaders(token);
    
    const generalStartTime = Date.now();
    let generalResponse;
    
    try {
      // ⚡ IP local con keep-alive (reutilización de conexión)
      generalResponse = await axios.get(generalUrl, getAxiosConfig(generalUrl, generalHeaders));
      const generalElapsed = Date.now() - generalStartTime;
      
      if (CALCULATE_DATA_CONSUMPTION) {
        const reqSize = calculateRequestSize(generalUrl, generalHeaders);
        const resSize = calculateResponseSize(generalResponse);
        logDataConsumption(reqSize, resSize, 'GET general (disponibilidad)');
      }
      
      console.log(`📊 [${INSTANCE_ID}] Req #${totalRequests} - GET general: ${generalElapsed}ms (IP LOCAL)`);
      
      // 🚨 DETECCIÓN DE THROTTLING
      if (generalElapsed > THROTTLE_THRESHOLD_MS) {
        throttleCount++;
        console.log(`⚠️ [${INSTANCE_ID}] Latencia alta (${generalElapsed}ms) - Contador: ${throttleCount}/${THROTTLE_COUNT_LIMIT}`);
        
        if (throttleCount >= THROTTLE_COUNT_LIMIT) {
          console.log(`\n🚨🚨🚨 [${INSTANCE_ID}] THROTTLING DETECTADO 🚨🚨🚨`);
          console.log(`⏸️  Pausando bot por ${THROTTLE_PAUSE_MS/1000/60} minutos para evitar detección...`);
          console.log(`⏰ Reanudará automáticamente a las ${new Date(Date.now() + THROTTLE_PAUSE_MS).toLocaleTimeString()}\n`);
          
          throttleCount = 0; // Reset contador
          isValidating = false;
          
          // Pausa de 10 minutos
          await new Promise(resolve => setTimeout(resolve, THROTTLE_PAUSE_MS));
          
          console.log(`\n✅ [${INSTANCE_ID}] Reanudando operación normal...\n`);
          return;
        }
      } else {
        // Si la request fue rápida, resetear contador
        if (throttleCount > 0) {
          console.log(`✅ [${INSTANCE_ID}] Latencia normal (${generalElapsed}ms) - Reset contador throttling`);
          throttleCount = 0;
        }
      }
      
      // 🎯 Buscar TODOS los sectores asignados y elegir el primero con disponibilidad
      const secciones = generalResponse.data?.secciones || [];
      let sectorEncontrado = null;
      let sectorIdEncontrado = null;
      let seccionEncontrada = null;
      
      for (const sector of assignedSectors) {
        const seatId = sectorIdMap[sector];
        const seccion = secciones.find(sec => sec.nid === seatId);
        
        if (seccion && seccion.hayDisponibilidad) {
          sectorEncontrado = sector;
          sectorIdEncontrado = seatId;
          seccionEncontrada = seccion;
          console.log(`✅ [${INSTANCE_ID}] ${sector}: DISPONIBILIDAD DETECTADA (hayDisponibilidad: true)`);
          break; // Elegir el primero con disponibilidad
        }
      }
      
      if (!sectorEncontrado) {
        const sectoresStr = assignedSectors.join(', ');
        console.log(`⏳ [${INSTANCE_ID}] [${sectoresStr}]: Sin disponibilidad en ninguno`);
        isValidating = false;
        return;
      }
      
      // Usar el sector encontrado para el resto del flujo
      const assignedSector = sectorEncontrado;
      const assignedSeatId = sectorIdEncontrado;
      
      // ============================================
      // 🔥 PASO 2: GET INDIVIDUAL (ubicaciones específicas)
      // ============================================
      let detailResponse;
      let detailElapsed;
      
      try {
        const detailUrl = getRandomizedUrl(`/event/seat/section/${assignedSeatId}/availability`, true);
        const detailHeaders = getAuthHeaders(token);
        
        const detailStartTime = Date.now();
        
        // ⚡ IP local con keep-alive (reutilización de conexión)
        detailResponse = await axios.get(detailUrl, getAxiosConfig(detailUrl, detailHeaders));
        detailElapsed = Date.now() - detailStartTime;
      
      if (CALCULATE_DATA_CONSUMPTION) {
        const reqSize = calculateRequestSize(detailUrl, detailHeaders);
        const resSize = calculateResponseSize(detailResponse);
        logDataConsumption(reqSize, resSize, 'GET individual (ubicaciones)');
      }
      
      console.log(`📊 [${INSTANCE_ID}] GET individual: ${detailElapsed}ms (reutilizando conexión)`);
      
      const data = detailResponse.data;
      
      // Verificar si hay ubicaciones disponibles
      if (data.ubicaciones && data.ubicaciones.length > 0) {
        // Filtrar ubicaciones bloqueadas
        const ubicacionesDisponibles = data.ubicaciones.filter(ubic => {
          if (ubic.nid === 6254404) {
            return false;
          }
          if (isUbicacionBloqueada(ubic.nid)) {
            const fallos = getFallosUbicacion(ubic.nid);
            console.log(`⏭️  [${INSTANCE_ID}] Saltando ubicación ${ubic.nid} (bloqueada, ${fallos} fallos previos)`);
            return false;
          }
          return true;
        });

        if (ubicacionesDisponibles.length === 0) {
          console.log(`⏭️  [${INSTANCE_ID}] Todas las ubicaciones están bloqueadas`);
          isValidating = false;
          return;
        }

        const randomIndex = Math.floor(Math.random() * ubicacionesDisponibles.length);
        const ubicacion = ubicacionesDisponibles[randomIndex];
        
        if (ubicacionesDisponibles.length > 1) {
          console.log(`🔄 [${INSTANCE_ID}] ${ubicacionesDisponibles.length} ubicaciones disponibles, eligiendo #${randomIndex + 1}`);
        }

        console.log(`\n==== [${INSTANCE_ID}] UBICACIÓN ENCONTRADA ====`);
        console.log(`Sector: ${assignedSector} (${data.nombreSeccion})`);
        console.log(`Ubicación: ${ubicacion.nid}`);
        console.log(`Tiempo: GET general ${generalElapsed}ms + GET individual ${detailElapsed}ms = ${generalElapsed + detailElapsed}ms`);
        console.log(`===============================\n`);

        writeReservaLog(`[${INSTANCE_ID}] 🎯 UBICACIÓN ENCONTRADA: Sector ${assignedSector}, Ubicación ${ubicacion.nid}, Tiempo ${generalElapsed + detailElapsed}ms`);

        // ============================================
        // 🔥 PASO 3: POST RESERVA DUAL (con/sin proxy)
        // ============================================
        try {
          console.log(`🔍 [${INSTANCE_ID}] Intentando reserva...`);
          writeReservaLog(`[${INSTANCE_ID}] 🔍 INICIANDO RESERVA para ubicación ${ubicacion.nid}`);
          
          loadCookies();
          
          const reserveStartTime = Date.now();
          const freshHeaders = getAuthHeaders(token);
          const reserveHeaders = {
            ...freshHeaders,
            'content-type': 'application/json'
          };

          const reserveData = { eventoUbicacionNid: ubicacion.nid };
          
          const isReservaExitosa = (responseData) => {
            if (!responseData) return false;
            const desc = responseData.descripcion?.toLowerCase() || '';
            return !desc.includes('no disponible') && !desc.includes('error');
          };
          
          // 🔥 V17-SIN-PROXY: POST simple (IP local, reutilizando conexión)
          console.log(`🚀 [${INSTANCE_ID}] V17-SIN-PROXY: POST con IP local (reutilizando conexión)`);
          
          let reserveRes = null;
          let reserveElapsed = 0;
          let reserveUrl = null; // 🔀 Se genera en cada intento
          const maxRetries = 3;
          
          for (let retry = 0; retry < maxRetries; retry++) {
            try {
              // 🔀 Host randomizado en CADA intento
              reserveUrl = getRandomizedUrl(`/event/seat/reserve/${ubicacion.nid}`);
              console.log(`🔀 [${INSTANCE_ID}] Host: ${new URL(reserveUrl).hostname}`);
              
              const start = Date.now();
              // ⚡ IP local con keep-alive (reutilización de conexión)
              const res = await axios.post(reserveUrl, reserveData, getAxiosConfig(reserveUrl, reserveHeaders));
              reserveElapsed = Date.now() - start;
              
              const exitosa = isReservaExitosa(res.data);
              console.log(`${exitosa ? '✅' : '⚠️'} [${INSTANCE_ID}] POST respondió: ${res.status} en ${reserveElapsed}ms ${exitosa ? '(EXITOSA)' : '(ubicación tomada)'}`);
              
              reserveRes = res;
              
              if (CALCULATE_DATA_CONSUMPTION) {
                const reqSize = calculateRequestSize(reserveUrl, reserveHeaders, reserveData);
                const resSize = calculateResponseSize(res);
                logDataConsumption(reqSize, resSize, 'POST reserve (IP LOCAL)');
              }
              
              break; // Salir del loop si tuvo éxito
              
            } catch (err) {
              const elapsed = Date.now() - reserveStartTime;
              const status = err.response?.status || 0;
              const responseData = err.response?.data ? JSON.stringify(err.response.data) : 'N/A';
              
              // ⚠️ RETRY SOLO EN 500 (y no en último intento) - SIN DELAY (al toque)
              if (status === 500 && retry < maxRetries - 1) {
                console.log(`🔄 [${INSTANCE_ID}] POST error 500 (intento ${retry + 1}/${maxRetries}) - reintentando INMEDIATAMENTE...`);
                console.log(`   Response: ${responseData}`);
                continue; // Reintentar AL TOQUE (sin delay)
              }
              
              // Si llegamos aquí, ya no hay más retries o no es 500
              console.log(`❌ [${INSTANCE_ID}] POST falló después de ${retry + 1} intento(s): ${err.message} (status ${status}) en ${elapsed}ms`);
              
              // Loguear en archivo
              writeReservaLog(`[${INSTANCE_ID}] ❌ RESERVA FALLÓ (después de ${retry + 1} intentos)`);
              writeReservaLog(`[${INSTANCE_ID}]   Error: ${err.message} (status ${status})`);
              if (responseData !== 'N/A') {
                writeReservaLog(`[${INSTANCE_ID}]   Response: ${responseData}`);
              }
              writeReservaLog(`[${INSTANCE_ID}] ⏱️  Timing: GET general ${generalElapsed}ms + GET individual ${detailElapsed}ms + POST ${elapsed}ms`);
              writeReservaLog('─'.repeat(80));
              
              // Marcar ubicación como fallida si el error indica "no disponible"
              const errorData = err.response?.data;
              const desc = errorData?.descripcion?.toLowerCase() || '';
              
              if (desc.includes('no disponible') || errorData?.codigo === 'ERROR_VENTAS__RESERVAR') {
                marcarUbicacionFallida(ubicacion.nid);
              }
              
              isValidating = false;
              return;
            }
          }
          
          if (!reserveRes) {
            console.log(`⚠️ [${INSTANCE_ID}] POST no obtuvo respuesta`);
            isValidating = false;
            return;
          }
          
          const metodoGanador = 'IP LOCAL';

          console.log(`📋 [${INSTANCE_ID}] Respuesta reserva (${reserveRes.status}): ${JSON.stringify(reserveRes.data)}`);
          
          writeReservaLog(`[${INSTANCE_ID}] 📋 RESPUESTA HTTP ${reserveRes.status} (${metodoGanador}) en ${reserveElapsed}ms`);
          writeReservaLog(`[${INSTANCE_ID}] 📄 Data: ${JSON.stringify(reserveRes.data, null, 2)}`);

          if (reserveRes.data?.descripcion?.toLowerCase().includes("no disponible")) {
            console.log(`🔄 [${INSTANCE_ID}] Ubicación ya tomada`);
            writeReservaLog(`[${INSTANCE_ID}] ❌ RESERVA FALLIDA: Ubicación ya tomada`);
            writeReservaLog(`[${INSTANCE_ID}] ⏱️  Timing: GET general ${generalElapsed}ms + GET individual ${detailElapsed}ms + POST ${reserveElapsed}ms`);
            writeReservaLog('─'.repeat(80));
            marcarUbicacionFallida(ubicacion.nid);
          } else if (reserveRes.data?.descripcion?.toLowerCase().includes("error")) {
            console.log(`⚠️ [${INSTANCE_ID}] Error: ${reserveRes.data.descripcion}`);
            writeReservaLog(`[${INSTANCE_ID}] ⚠️  ERROR: ${reserveRes.data.descripcion}`);
            writeReservaLog('─'.repeat(80));
            if (reserveRes.data?.descripcion?.toLowerCase().includes("no disponible") || 
                reserveRes.data?.codigo === "ERROR_VENTAS__RESERVAR") {
              marcarUbicacionFallida(ubicacion.nid);
            }
          } else {
            reservationMade = true;
            clearInterval(intervalId);

            console.log(`\n🎉 ==== [${INSTANCE_ID}] [SUCCESS] RESERVA EXITOSA ====`);
            console.log(`Método: ${metodoGanador} (sin proxy, keep-alive)`);
            console.log(`Sector: ${assignedSector}`);
            console.log(`Ubicación: ${ubicacion.nid}`);
            console.log(`Tiempo TOTAL: ${generalElapsed + detailElapsed + reserveElapsed}ms`);
            console.log(`   - GET general: ${generalElapsed}ms`);
            console.log(`   - GET individual: ${detailElapsed}ms`);
            console.log(`   - POST reserva: ${reserveElapsed}ms`);
            console.log(`=====================================\n`);

            writeReservaLog('═'.repeat(80));
            writeReservaLog(`[${INSTANCE_ID}] 🎉🎉🎉 RESERVA EXITOSA 🎉🎉🎉`);
            writeReservaLog(`[${INSTANCE_ID}] 🏆 Método: ${metodoGanador} (IP LOCAL, sin proxy, keep-alive)`);
            writeReservaLog(`[${INSTANCE_ID}] 🎯 Sector: ${assignedSector}`);
            writeReservaLog(`[${INSTANCE_ID}] 📍 Ubicación: ${ubicacion.nid}`);
            writeReservaLog(`[${INSTANCE_ID}] ⏱️  Timing: GET general ${generalElapsed}ms + GET individual ${detailElapsed}ms + POST ${reserveElapsed}ms = ${generalElapsed + detailElapsed + reserveElapsed}ms total`);
            writeReservaLog('═'.repeat(80));

            try {
              const ticket = reserveRes.data?.ticket;
              if (ticket?.nid != null && ticket?.productoNid != null) {
                fs.writeFileSync(
                  './ultima-reserva.json',
                  JSON.stringify(
                    {
                      ticketNid: ticket.nid,
                      productoNid: ticket.productoNid,
                      ubicacionNid: ubicacion.nid,
                      sector: assignedSector,
                      savedAt: new Date().toISOString(),
                    },
                    null,
                    2
                  ),
                  'utf8'
                );
                console.log(`📝 ultima-reserva.json actualizado (node v-completo.js para iniciar pago)`);
              }
            } catch (e) {
              console.error(`⚠️ No se pudo guardar ultima-reserva.json: ${e.message}`);
            }

            console.log(`\n🚨🚨🚨 ABRIENDO YOUTUBE CON ALARMA 🚨🚨🚨\n`);
            openYoutube();
            
            isValidating = false;
            return;
          }
        } catch (err) {
          console.error(`❌ [${INSTANCE_ID}] Error al reservar: ${err.message}`);
          writeReservaLog(`[${INSTANCE_ID}] ❌ EXCEPCIÓN: ${err.message}`);
          
          if (err.response) {
            writeReservaLog(`[${INSTANCE_ID}] 🚫 HTTP ${err.response.status}: ${JSON.stringify(err.response.data)}`);
            
            if (err.response.status === 401) {
              console.log(`🔑 [${INSTANCE_ID}] [ERROR:401] Token expirado!`);
              loadToken();
              isValidating = false;
              return;
            }
            
            if (err.response.status === 418) {
              console.log(`🚨 [${INSTANCE_ID}] [ERROR:418] IP bloqueada por WAF!`);
              isValidating = false;
              return;
            }
            
            if (err.response.status === 429) {
              console.log(`🚨 [${INSTANCE_ID}] [ERROR:429] Rate limited!`);
              isValidating = false;
              return;
            }
          }
          
          writeReservaLog('─'.repeat(80));
        }
      } else {
        console.log(`⏳ [${INSTANCE_ID}] ${assignedSector}: Sin ubicaciones disponibles`);
      }
      
      } catch (error) {
        const status = error.response?.status;
        
        if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
          console.log(`⏱️ [${INSTANCE_ID}] Timeout en GET individual (${REQUEST_TIMEOUT_MS}ms) - continuando...`);
          isValidating = false;
          return;
        }
        
        console.error(`❌ [${INSTANCE_ID}] Error en GET individual: ${error.message}`);
        
        if (status === 502) {
          console.log(`🔄 [${INSTANCE_ID}] Error 502 - reintentando...`);
          isValidating = false;
          return checkAvailabilityAndReserve();
        }
        
        if (status === 401) {
          console.log(`🔑 [${INSTANCE_ID}] [ERROR:401] Token expirado!`);
          loadToken();
          isValidating = false;
          return;
        }
        
        if (status === 418) {
          console.log(`🚨 [${INSTANCE_ID}] [ERROR:418] IP bloqueada por WAF!`);
          isValidating = false;
          // El orquestador detectará esto y rotará IP
          return;
        }
        
        if (status === 429) {
          console.log(`🚨 [${INSTANCE_ID}] [ERROR:429] Rate limited!`);
          isValidating = false;
          // El orquestador detectará esto y rotará IP
          return;
        }
        
        isValidating = false;
        return;
      }
    
    } catch (error) {
      const status = error.response?.status;
      
      if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        console.log(`⏱️ [${INSTANCE_ID}] Timeout en GET general (${REQUEST_TIMEOUT_MS}ms) - continuando...`);
        isValidating = false;
        return;
      }
      
      console.error(`❌ [${INSTANCE_ID}] Error en GET general: ${error.message}`);
      
      if (status === 502) {
        console.log(`🔄 [${INSTANCE_ID}] Error 502 - reintentando...`);
        isValidating = false;
        return checkAvailabilityAndReserve();
      }
      
      if (status === 401) {
        console.log(`🔑 [${INSTANCE_ID}] [ERROR:401] Token expirado!`);
        loadToken();
        isValidating = false;
        return;
      }
      
      if (status === 418) {
        console.log(`🚨 [${INSTANCE_ID}] [ERROR:418] IP bloqueada por WAF!`);
        isValidating = false;
        return;
      }
      
      if (status === 429) {
        console.log(`🚨 [${INSTANCE_ID}] [ERROR:429] Rate limited!`);
        isValidating = false;
        return;
      }
    }
  } finally {
    isValidating = false;
  }
}

// === MAIN ===
(async () => {
  console.log("======================================");
  console.log(`🚀 [${INSTANCE_ID}] V22 - USA TOKEN/COOKIES DEL PROXY`);
  console.log(`📡 IP: LOCAL (sin proxy) - Token/Cookies de proxy`);
  console.log(`⚡ Intervalo: ${RETRY_INTERVAL_MS}ms (~${Math.round(60000/RETRY_INTERVAL_MS)} req/min)`);
  console.log(`⏱️  Timeout: ${REQUEST_TIMEOUT_MS}ms`);
  console.log(`🔄 PROCESO DE 2 PASOS:`);
  console.log(`   1. GET general → Verificar disponibilidad`);
  console.log(`   2. GET individual → Obtener ubicaciones (si hay disponibilidad)`);
  console.log(`   3. POST simple → Reservar (IP local)`);
  console.log(`🔗 Keep-Alive: REUTILIZACIÓN DE CONEXIÓN entre pasos`);
  console.log(`🔥 POST: SIMPLE (IP LOCAL) con retry en 500`);
  console.log(`🍪 Cookies: ${COOKIES_FILE} (proxy)`);
  console.log(`🎫 Token: ${TOKEN_FILE} (proxy)`);
  console.log(`🚨 Throttling: Pausa ${THROTTLE_PAUSE_MS/1000/60}min si >${THROTTLE_THRESHOLD_MS}ms (${THROTTLE_COUNT_LIMIT}x)`);
  if (CALCULATE_DATA_CONSUMPTION) {
    console.log(`📊 Cálculo de MB: ACTIVADO (CALC_MB=true)`);
  }
  console.log(`🎯 Sectores: ${assignedSectors.join(', ')}`);
  console.log(`🎫 Evento: ${currentEventId}`);
  console.log(`🚫 Cache ubicaciones fallidas: ACTIVADO (ULTRA-RÁPIDO)`);
  console.log(`   - Bloqueo temporal: ${UBICACION_FALLIDA_TTL_MS/1000}s`);
  console.log(`   - BLACKLIST permanente: ${MAX_FALLOS_ANTES_BLOQUEAR} fallos → ${BLOQUEO_PERMANENTE_MS/1000/60}min`);
  console.log(`🔀 Host randomizado: ACTIVADO (anti-WAF)`);
  console.log(`   Ejemplo: ${randomizeHostCase(BASE_HOST)}`);
  console.log("======================================\n");

  // Cargar cookies del proxy
  if (!loadCookies()) {
    console.error(`❌ [${INSTANCE_ID}] No se pudieron cargar las cookies.`);
    console.error(`   Ejecutá primero: node cookie-refresher-proxy.js`);
    process.exit(1);
  }

  // Cargar token del proxy (sin hacer login)
  if (!loadToken()) {
    console.error(`❌ [${INSTANCE_ID}] No se pudo cargar el token.`);
    console.error(`   Ejecutá primero: node cookie-refresher-proxy.js`);
    process.exit(1);
  }
  
  console.log(`✅ [${INSTANCE_ID}] Token y cookies cargados desde archivos del proxy`);

  console.log(`\n🔍 [${INSTANCE_ID}] Obteniendo SeatIDs para sectores: ${assignedSectors.join(', ')}...`);
  sectorIdMap = await loadMultipleSectors(assignedSectors);
  
  if (!sectorIdMap) {
    console.error(`❌ [${INSTANCE_ID}] No se pudieron obtener SeatIDs. Saliendo...`);
    process.exit(1);
  }
  
  for (const [sector, seatId] of Object.entries(sectorIdMap)) {
    console.log(`✅ [${INSTANCE_ID}] Sector ${sector} → SeatID: ${seatId}`);
  }
  console.log('');

  console.log(`🎯 [${INSTANCE_ID}] Monitoreando sectores [${assignedSectors.join(', ')}] con proceso de 2 pasos...\n`);
  
  const monitorWithJitter = async () => {
    await checkAvailabilityAndReserve();
    if (!reservationMade) {
      const nextInterval = getNextInterval();
      setTimeout(monitorWithJitter, nextInterval);
    }
  };
  
  await monitorWithJitter();

  process.stdin.on('data', (data) => {
    const command = data.toString().trim();
    if (command === 'reset') {
      reservationMade = false;
      isValidating = false;
      console.log(`✅ [${INSTANCE_ID}] Estado reseteado`);
    }
  });
})();

