import { CRX_B64 } from './crx-data.js';

const EXT_ID = 'gpijhapcpdimkcgoppjekdbabilnganf';
const EXT_VERSION = '1.1.3';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, X-API-Key',
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    if (path === '/api/cookies' && request.method === 'POST') {
      return handlePost(request, env);
    }

    if (path === '/api/cookies/latest' && request.method === 'GET') {
      return handleGetLatest(request, env);
    }

    if (path === '/api/cookies/status' && request.method === 'GET') {
      return handleGetStatus(env);
    }

    if ((path === '/api/queue/status' || path === '/api/queue') && request.method === 'GET') {
      return handleGetQueueStatus(env);
    }

    if (path === '/api/queue/heartbeat' && request.method === 'POST') {
      return handleQueueHeartbeat(request, env);
    }

    if (path === '/api/cookies/clear' && request.method === 'POST') {
      const apiKey = request.headers.get('X-API-Key');
      if (apiKey !== env.API_KEY) return json({ error: 'Unauthorized' }, 401);
      await env.COOKIES_KV.delete('latest');
      return json({ ok: true, message: 'Cookies borradas' });
    }

    if (path === '/ext/update.xml' && request.method === 'GET') {
      const origin = url.origin;
      const xml = `<?xml version='1.0' encoding='UTF-8'?>
<gupdate xmlns='http://www.google.com/update2/response' protocol='2.0'>
  <app appid='${EXT_ID}'>
    <updatecheck codebase='${origin}/ext/extension.crx' version='${EXT_VERSION}' />
  </app>
</gupdate>`;
      return new Response(xml, {
        headers: { 'Content-Type': 'application/xml; charset=utf-8', ...CORS_HEADERS },
      });
    }

    if (path === '/ext/extension.crx' && request.method === 'GET') {
      const raw = Uint8Array.from(atob(CRX_B64), (c) => c.charCodeAt(0));
      return new Response(raw, {
        headers: {
          'Content-Type': 'application/x-chrome-extension',
          'Content-Disposition': 'attachment; filename="extension.crx"',
          ...CORS_HEADERS,
        },
      });
    }

    const goMatch = path.match(/^\/go\/(.+)$/);
    if (goMatch) {
      return handleGoPage(goMatch[1], env);
    }

    return json({ error: 'Not found' }, 404);
  },
};

async function handlePost(request, env) {
  const apiKey = request.headers.get('X-API-Key');
  if (apiKey !== env.API_KEY) {
    return json({ error: 'Unauthorized' }, 401);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const cookies = body.cookies;
  if (!cookies || !Array.isArray(cookies) || cookies.length === 0) {
    return json({ error: 'cookies array required' }, 400);
  }

  const critical = cookies.filter(
    (c) =>
      c.name &&
      (c.name.startsWith('QueueITAccepted') ||
        c.name === 'HWWAFSESID' ||
        c.name === 'HWWAFSESTIME')
  );

  const data = {
    cookies: cookies,
    critical_cookies: critical,
    evento: body.evento || null,
    cookie_string: body.cookie_string || '',
    local_storage: body.local_storage || {},
    updated_at: new Date().toISOString(),
    source: body.source || 'unknown',
    active: body.active !== undefined ? body.active : true,
  };

  await env.COOKIES_KV.put('latest', JSON.stringify(data));

  return json({
    ok: true,
    critical_count: critical.length,
    total_count: cookies.length,
    updated_at: data.updated_at,
  });
}

async function handleGetLatest(request, env) {
  const url = new URL(request.url);
  const code = url.searchParams.get('code') || request.headers.get('X-Access-Code');
  if (!code || code !== env.ACCESS_CODE) {
    return json({ error: 'Codigo de acceso invalido' }, 403);
  }

  const raw = await env.COOKIES_KV.get('latest');
  if (!raw) {
    return json({ error: 'No cookies stored yet' }, 404);
  }

  const data = JSON.parse(raw);
  return json(data);
}

async function handleGetStatus(env) {
  const raw = await env.COOKIES_KV.get('latest');
  const queueRaw = await env.COOKIES_KV.get('queue_status');
  let queue = queueRaw ? JSON.parse(queueRaw) : null;

  if (queue && queue.updated_at) {
    const qAgeMs = Date.now() - new Date(queue.updated_at).getTime();
    queue.age_seconds = Math.max(0, Math.round(qAgeMs / 1000));
    queue.online = queue.age_seconds < 180;
  }

  if (!raw) {
    return json({ has_cookies: false, queue: queue });
  }

  const data = JSON.parse(raw);
  const updatedAt = new Date(data.updated_at);
  const ageMs = Date.now() - updatedAt.getTime();
  const ageMins = Math.round(ageMs / 60000);

  return json({
    has_cookies: true,
    updated_at: data.updated_at,
    age_minutes: ageMins,
    fresh: ageMins < 5,
    critical_count: data.critical_cookies ? data.critical_cookies.length : 0,
    evento: data.evento,
    queue: queue,
  });
}

async function handleGetQueueStatus(env) {
  const queueRaw = await env.COOKIES_KV.get('queue_status');
  let queue = queueRaw ? JSON.parse(queueRaw) : null;

  if (!queue) {
    return json({
      online: false,
      message: 'No hay bot de cola reportando actualmente',
      queue: null,
    });
  }

  const qAgeMs = Date.now() - new Date(queue.updated_at).getTime();
  queue.age_seconds = Math.max(0, Math.round(qAgeMs / 1000));
  queue.online = queue.age_seconds < 180;

  return json({
    online: queue.online,
    best_time_minutes: queue.best_time,
    avg_time_minutes: queue.avg_time,
    active_sessions: queue.active_sessions,
    total_sessions: queue.total_sessions,
    passed_sessions: queue.passed_sessions,
    age_seconds: queue.age_seconds,
    updated_at: queue.updated_at,
  });
}

async function handleQueueHeartbeat(request, env) {
  const apiKey = request.headers.get('X-API-Key');
  if (apiKey !== env.API_KEY) {
    return json({ error: 'Unauthorized' }, 401);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const queueData = {
    best_time: body.best_time !== undefined ? body.best_time : null,
    avg_time: body.avg_time !== undefined ? body.avg_time : null,
    active_sessions: body.active_sessions || 0,
    total_sessions: body.total_sessions || 0,
    passed_sessions: body.passed_sessions || 0,
    opening_time: body.opening_time || null,
    updated_at: new Date().toISOString(),
  };

  await env.COOKIES_KV.put('queue_status', JSON.stringify(queueData), { expirationTtl: 600 });

  return json({ ok: true, updated_at: queueData.updated_at });
}

function handleGoPage(code, env) {
  const html = `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Boca Socios - Acceso</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a1628;color:#e0e0e0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#111b2e;border-radius:12px;padding:32px;max-width:400px;width:90%;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.4)}
h1{color:#f0c040;font-size:20px;margin-bottom:8px}
.sub{color:#888;font-size:13px;margin-bottom:24px}
.status{padding:12px;border-radius:8px;margin:16px 0;font-size:14px}
.loading{background:#1a2a40;border:1px solid #2a4a60;color:#6ab0ff}
.ok{background:#0d2818;border:1px solid #2d6a3e;color:#4caf50}
.err{background:#2a0a0a;border:1px solid #6a2a2a;color:#ff5555}
.btn{display:inline-block;background:#f0c040;color:#000;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;margin-top:16px;border:none;cursor:pointer}
.btn:hover{background:#ffd700}
.btn:disabled{opacity:.4;cursor:wait}
.hidden{display:none}
.spinner{display:inline-block;width:18px;height:18px;border:2px solid #6ab0ff;border-top-color:transparent;border-radius:50%;animation:spin .8s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes spin{to{transform:rotate(360deg)}}
.step{font-size:12px;color:#666;margin-top:12px}
</style>
</head>
<body>
<div class="card">
  <h1>Boca Socios</h1>
  <p class="sub">Acceso sin fila virtual</p>
  
  <div id="status" class="status loading">
    <span class="spinner"></span> Verificando acceso...
  </div>
  
  <a id="btnGo" class="btn hidden" href="https://bocasocios.bocajuniors.com.ar/auth/login" target="_blank">Entrar a Boca Socios</a>
  
  <div id="noExt" class="hidden">
    <div class="status err">No se detecto la extension.</div>
    <p class="step">1. chrome://extensions → Developer mode → Load unpacked</p>
    <p class="step">2. Elegi la carpeta popular-reserva/extension</p>
    <p class="step">3. Recarga esta pagina</p>
  </div>
</div>

<script>
const CODE = '${code}';
const SERVER = '${env.API_KEY ? new URL('/', 'https://boca-cookies.rosaleseze86.workers.dev').origin : ''}';

let extDetected = false;

window.addEventListener('message', function(e) {
  if (e.data && e.data.type === 'BOCA_EXT_READY') {
    extDetected = true;
    document.getElementById('status').innerHTML = '<span class="spinner"></span> Cargando cookies...';
  }
  if (e.data && e.data.type === 'BOCA_EXT_DONE') {
    const s = document.getElementById('status');
    if (e.data.ok) {
      s.className = 'status ok';
      s.textContent = 'Listo. set=' + (e.data.injected || 0) + ' getAll=' + (e.data.verify || 0) + (e.data.names ? ' (' + e.data.names + ')' : '');
      document.getElementById('btnGo').classList.remove('hidden');
    } else {
      s.className = 'status err';
      s.textContent = 'Error: ' + (e.data.error || 'desconocido') + ' set=' + (e.data.injected || 0) + ' getAll=' + (e.data.verify || 0);
    }
  }
});

setTimeout(function() {
  if (!extDetected) {
    document.getElementById('status').classList.add('hidden');
    document.getElementById('noExt').classList.remove('hidden');
  }
}, 8000);
</script>
</body>
</html>`;

  return new Response(html, {
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });
}
