const fs = require('fs');
const puppeteer = require('puppeteer');
const axios = require('axios');

// === 🎫 CONFIGURACIÓN ===
const EVENT_ID = process.env.EVENT_ID || '868';

const EMAIL = process.env.BOCA_EMAIL || '';
const PASSWORD = Buffer.from(process.env.BOCA_PASSWORD || '').toString('base64');
if (!EMAIL || !PASSWORD) {
  console.error('Falta BOCA_EMAIL / BOCA_PASSWORD (variables de entorno)');
  process.exit(1);
}
// SIN PROXY - USA IP LOCAL
// El orquestador desconecta NordVPN antes de correr esto

const COOKIES_FILE = './queue-cookies-proxy.txt';
const TOKEN_FILE = './shared-token-proxy.json';
const SECTORS_FILE = `./sectors-event-${EVENT_ID}.json`;
const REFRESH_INTERVAL = 3 * 60 * 1000; // 3 minutos

// Modo --once: correr una vez y salir (para orquestador)
const ONCE_MODE = process.argv.includes('--once');

console.log("======================================");
console.log("Cookie + Token Refresher (IP LOCAL - SIN PROXY)");
if (ONCE_MODE) {
  console.log("MODO: Una vez (--once)");
} else {
  console.log("Actualiza cookies cada 3 minutos");
  console.log("Actualiza token cada 3 minutos");
}
console.log(`Evento: ${EVENT_ID}`);
console.log("IP: LOCAL (sin proxy, sin VPN)");
console.log("Archivos: queue-cookies-proxy.txt + shared-token-proxy.json");
console.log("======================================\n");

let browser = null;
let page = null;

// === OBTENER Y GUARDAR COOKIES ===
async function refreshCookies() {
  try {
    console.log(`[${new Date().toLocaleTimeString()}] Actualizando cookies con IP LOCAL...`);

    // Navegador SIN PROXY - IP local
    if (!browser || !page) {
      console.log(`Abriendo navegador SIN PROXY (IP local)...`);
      
      browser = await puppeteer.launch({ 
        headless: false,
        defaultViewport: null,
        args: [
          '--no-sandbox', 
          '--disable-setuid-sandbox', 
          '--start-maximized'
        ]
      });
      
      page = await browser.newPage();
      console.log("Navegador abierto (IP LOCAL)!");
      
      // Verificar IP
      try {
        await page.goto('https://api.ipify.org', { timeout: 15000 });
        const ip = await page.evaluate(() => document.body.textContent);
        console.log(`IP del navegador: ${ip}`);
      } catch (e) {
        console.log("No se pudo verificar IP");
      }
    }

    // Borrar cookies viejas
    const client = await page.target().createCDPSession();
    await client.send('Network.clearBrowserCookies');
    console.log("Cookies antiguas borradas");
    
    // Ir a la página de login
    console.log("Navegando a Boca Socios...");
    await page.goto('https://bocasocios.bocajuniors.com.ar/auth/login', {
      waitUntil: 'networkidle2',
      timeout: 60000
    });
    
    // Verificar si estamos en Queue-IT y esperar a pasar
    const currentUrl = page.url();
    if (currentUrl.includes('queue-it.net')) {
      console.log("⏳ Detectado Queue-IT - Esperando pasar la cola...");
      console.log("   URL: " + currentUrl);
      console.log("   (Esto puede tomar varios minutos si hay cola)");
      
      // Esperar hasta que salgamos de queue-it (máximo 10 minutos)
      try {
        await page.waitForFunction(
          () => !window.location.href.includes('queue-it.net'),
          { timeout: 600000 } // 10 minutos
        );
        console.log("✅ Cola pasada! Continuando...");
        await new Promise(resolve => setTimeout(resolve, 3000));
      } catch (e) {
        console.log("⚠️ Timeout esperando cola - continuando de todos modos");
      }
    } else {
      console.log("✅ No hay cola activa o ya pasamos");
      await new Promise(resolve => setTimeout(resolve, 3000));
    }

    // Obtener todas las cookies
    const cookies = await page.cookies();
    
    // Convertir a formato cookie string
    const cookieString = cookies
      .map(cookie => `${cookie.name}=${cookie.value}`)
      .join('; ');

    // Escritura atómica
    const TEMP_FILE = COOKIES_FILE + '.tmp';
    fs.writeFileSync(TEMP_FILE, cookieString, 'utf8');
    
    const writtenContent = fs.readFileSync(TEMP_FILE, 'utf8');
    if (writtenContent.length !== cookieString.length) {
      console.error(`Error: Archivo temporal incompleto`);
      return;
    }
    
    fs.renameSync(TEMP_FILE, COOKIES_FILE);
    
    console.log(`[${new Date().toLocaleTimeString()}] OK Cookies actualizadas (${cookies.length} cookies)`);
    console.log(`   Archivo: ${COOKIES_FILE}`);
    console.log(`   Tamano: ${cookieString.length} caracteres`);
    
    // Mostrar cookies importantes
    const importantCookies = ['HWWAFSESID', 'QueueITAccepted-SDFrts345E-V3_e20251123adh'];
    importantCookies.forEach(name => {
      const cookie = cookies.find(c => c.name === name);
      if (cookie) {
        console.log(`   OK ${name}: ${cookie.value.substring(0, 20)}...`);
      } else {
        console.log(`   WARN ${name}: NO ENCONTRADA`);
      }
    });
    
    // ============================================
    // HACER LOGIN Y GUARDAR TOKEN (IP LOCAL)
    // ============================================
    console.log(`\n[${new Date().toLocaleTimeString()}] Haciendo login con IP LOCAL...`);
    
    try {
      const loginUrl = 'https://bocasocios-gw.bocajuniors.com.ar/auth/login/baas';
      
      const loginHeaders = {
        'accept': 'application/json',
        'content-type': 'application/json',
        'cookie': cookieString
      };
      const loginData = { email: EMAIL, password: PASSWORD };
      
      const loginResponse = await axios.post(loginUrl, loginData, { 
        headers: loginHeaders,
        timeout: 30000
      });
      
      if (loginResponse.data && loginResponse.data.token) {
        const token = loginResponse.data.token;
        
        const tokenData = {
          token: token,
          timestamp: Date.now(),
          expires: Date.now() + (24 * 60 * 60 * 1000),
          email: EMAIL,
          proxy: false,
          ip: 'local'
        };
        
        // Escritura atómica del token
        const TEMP_TOKEN_FILE = TOKEN_FILE + '.tmp';
        fs.writeFileSync(TEMP_TOKEN_FILE, JSON.stringify(tokenData, null, 2), 'utf8');
        fs.renameSync(TEMP_TOKEN_FILE, TOKEN_FILE);
        
        console.log(`[${new Date().toLocaleTimeString()}] OK Token obtenido (IP LOCAL)`);
        console.log(`   Archivo: ${TOKEN_FILE}`);
        console.log(`   Token: ${token.substring(0, 50)}...`);
        
        return token;
      } else {
        console.error(`[${new Date().toLocaleTimeString()}] ERROR Login sin token en respuesta`);
        return null;
      }
    } catch (loginError) {
      console.error(`[${new Date().toLocaleTimeString()}] ERROR en login: ${loginError.message}`);
      if (loginError.response) {
        console.error(`   Status: ${loginError.response.status}`);
        console.error(`   Data: ${JSON.stringify(loginError.response.data)}`);
      }
      return null;
    }
    
  } catch (error) {
    console.error(`ERROR [${new Date().toLocaleTimeString()}] Error al actualizar cookies: ${error.message}`);
    
    if (browser) {
      try {
        await browser.close();
      } catch (e) {}
    }
    browser = null;
    page = null;
    return null;
  }
}

// === GENERAR SECTORES ===
async function fetchAndSaveSectors(token) {
  try {
    if (fs.existsSync(SECTORS_FILE)) {
      console.log(`\n[${new Date().toLocaleTimeString()}] OK Archivo de sectores ya existe: ${SECTORS_FILE}\n`);
      return true;
    }
    
    console.log(`\n[${new Date().toLocaleTimeString()}] Obteniendo sectores del evento ${EVENT_ID} (IP LOCAL)...`);
    
    if (!token) {
      console.error('ERROR No hay token disponible para obtener sectores');
      return false;
    }
    
    const url = `https://bocasocios-gw.bocajuniors.com.ar/event/${EVENT_ID}/seat/section/availability`;
    const cookieString = fs.readFileSync(COOKIES_FILE, 'utf8').trim();
    
    const headers = {
      'accept': 'application/json',
      'authorization': `Bearer ${token}`,
      'cookie': cookieString
    };
    
    const response = await axios.get(url, { 
      headers, 
      timeout: 10000
    });
    
    const secciones = response.data?.secciones || [];
    
    const laterales = ['F', 'G', 'H', 'I', 'J', 'K', 'M'];
    const sectorsMap = {};
    
    for (const seccion of secciones) {
      for (const letra of laterales) {
        if (seccion.nombre === `Seccion ${letra}` || seccion.nombre === `Seccion ${letra}` || seccion.nombre === `Sector ${letra}`) {
          sectorsMap[letra] = seccion.nid;
          console.log(`   OK Sector ${letra}: ${seccion.nid}`);
          break;
        }
      }
    }
    
    // Escritura atómica
    const TEMP_SECTORS_FILE = SECTORS_FILE + '.tmp';
    fs.writeFileSync(TEMP_SECTORS_FILE, JSON.stringify(sectorsMap, null, 2), 'utf8');
    fs.renameSync(TEMP_SECTORS_FILE, SECTORS_FILE);
    
    console.log(`[${new Date().toLocaleTimeString()}] OK Sectores guardados: ${SECTORS_FILE}\n`);
    return true;
  } catch (error) {
    console.error(`ERROR [${new Date().toLocaleTimeString()}] Error obteniendo sectores: ${error.message}`);
    if (error.response) {
      console.error(`   Status: ${error.response.status}`);
    }
    return false;
  }
}

// === MAIN ===
(async () => {
  // Primera actualización inmediata
  const token = await refreshCookies();
  
  if (token) {
    await fetchAndSaveSectors(token);
    
    // Si modo --once, cerrar y salir
    if (ONCE_MODE) {
      console.log(`\n✅ Modo --once completado exitosamente`);
      if (browser) {
        await browser.close();
      }
      process.exit(0);
    }
  } else {
    console.log(`\nWARN No se pudo obtener token inicial\n`);
    
    // Si modo --once, salir con error
    if (ONCE_MODE) {
      console.log(`❌ Modo --once falló`);
      if (browser) {
        await browser.close();
      }
      process.exit(1);
    }
  }
  
  // Modo normal: actualizar cada 3 minutos
  if (!ONCE_MODE) {
    setInterval(async () => {
      await refreshCookies();
    }, REFRESH_INTERVAL);

    console.log(`\nCookie refresher CON PROXY activo - actualizando cada 3 minutos`);
    console.log(`Archivos: ${COOKIES_FILE}, ${TOKEN_FILE}\n`);
    
    process.stdin.resume();
  }
})();

// Manejar cierre limpio
process.on('SIGINT', async () => {
  console.log('\n\nCerrando cookie refresher...');
  if (browser) {
    await browser.close();
  }
  process.exit(0);
});

