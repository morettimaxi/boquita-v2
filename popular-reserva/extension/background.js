const SERVER_URL = 'https://boca-cookies.rosaleseze86.workers.dev';
const POLL_INTERVAL_MINUTES = 2;
const BOCA_DOMAINS = [
  'bocasocios.bocajuniors.com.ar',
  'bocasocios-gw.bocajuniors.com.ar',
];
const BOCA_PARENT = 'bocajuniors.com.ar';

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create('refreshCookies', { periodInMinutes: POLL_INTERVAL_MINUTES });
  console.log('Boca Cookies: extension instalada, polling cada', POLL_INTERVAL_MINUTES, 'min');
  fetchAndInjectCookies();
});

chrome.runtime.onStartup.addListener(() => {
  fetchAndInjectCookies();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'refreshCookies') {
    fetchAndInjectCookies();
  }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'forceRefresh') {
    fetchAndInjectCookies().then((result) => sendResponse(result));
    return true;
  }
  if (msg.action === 'getStatus') {
    chrome.storage.local.get(['lastUpdate', 'cookieCount', 'lastError'], (data) => {
      sendResponse(data);
    });
    return true;
  }
  if (msg.action === 'setAccessCode') {
    chrome.storage.local.set({ accessCode: msg.code }, () => {
      sendResponse({ ok: true });
    });
    return true;
  }
  if (msg.action === 'setServerUrl') {
    chrome.storage.local.set({ serverUrl: msg.url }, () => {
      sendResponse({ ok: true });
    });
    return true;
  }
});

async function getServerUrl() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['serverUrl'], (data) => {
      resolve(data.serverUrl || SERVER_URL);
    });
  });
}

async function getAccessCode() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['accessCode'], (data) => {
      resolve(data.accessCode || '');
    });
  });
}

function resolveCookieTargets(cookie) {
  const name = cookie.name || '';
  if (cookie.domain) {
    const host = cookie.domain.replace(/^\./, '');
    return [{ host, domain: cookie.domain }];
  }
  if (name.startsWith('QueueITAccepted') || name.startsWith('_ga') || name.startsWith('_cl')) {
    return [{ host: BOCA_PARENT, domain: `.${BOCA_PARENT}` }];
  }
  if (name.startsWith('HWWAF') || name === 'CLID') {
    return BOCA_DOMAINS.map((host) => ({ host, domain: host }));
  }
  return [{ host: BOCA_PARENT, domain: `.${BOCA_PARENT}` }];
}

async function fetchAndInjectCookies() {
  const serverUrl = await getServerUrl();
  const accessCode = await getAccessCode();

  if (!accessCode) {
    chrome.storage.local.set({ lastError: 'Falta codigo de acceso', lastCheck: new Date().toISOString() });
    return { ok: false, error: 'Falta codigo de acceso' };
  }

  try {
    const resp = await fetch(`${serverUrl}/api/cookies/latest?code=${encodeURIComponent(accessCode)}`);

    if (!resp.ok) {
      const errText = await resp.text();
      console.warn('Boca Cookies: server error', resp.status, errText);
      chrome.storage.local.set({ lastError: `HTTP ${resp.status}`, lastCheck: new Date().toISOString() });
      return { ok: false, error: `HTTP ${resp.status}` };
    }

    const data = await resp.json();

    if (!data.critical_cookies || data.critical_cookies.length === 0) {
      console.warn('Boca Cookies: no hay cookies criticas en el server');
      chrome.storage.local.set({ lastError: 'Sin cookies criticas', lastCheck: new Date().toISOString() });
      return { ok: false, error: 'Sin cookies criticas' };
    }

    if (data.active === false) {
      console.log('Boca Cookies: evento no activo, no inyectando cookies');
      chrome.storage.local.set({ lastError: 'Evento no activo', lastCheck: new Date().toISOString() });
      return { ok: false, error: 'Evento no activo' };
    }

    const ageMs = Date.now() - new Date(data.updated_at).getTime();
    if (ageMs > 3600000) {
      console.log('Boca Cookies: cookies tienen mas de 1 hora, no inyectando');
      chrome.storage.local.set({ lastError: 'Cookies viejas (>1h)', lastCheck: new Date().toISOString() });
      return { ok: false, error: 'Cookies viejas (>1h)' };
    }

    const lastUpdate = await new Promise((r) =>
      chrome.storage.local.get(['serverTimestamp'], (d) => r(d.serverTimestamp))
    );
    if (lastUpdate === data.updated_at) {
      console.log('Boca Cookies: cookies sin cambios, skip');
      chrome.storage.local.set({ lastCheck: new Date().toISOString(), lastError: null });
      return { ok: true, skipped: true };
    }

    // Limpiar TODAS las cookies de bocajuniors (incluido .bocajuniors.com.ar)
    // Si no, un QueueITAccepted viejo queda mezclado y causa redirect loop
    try {
      const domainsToClean = [BOCA_PARENT, 'queue-it.net'];
      let removed = 0;
      for (const parent of domainsToClean) {
        const existing = await chrome.cookies.getAll({ domain: parent });
        for (const c of existing) {
          const host = c.domain.startsWith('.') ? c.domain.slice(1) : c.domain;
          const url = `https://${host}${c.path || '/'}`;
          await chrome.cookies.remove({ url, name: c.name });
          removed++;
        }
      }
      console.log(`Boca Cookies: limpiadas ${removed} cookies viejas`);
    } catch (e) {
      console.warn('Boca Cookies: error limpiando cookies:', e);
    }

    let injected = 0;
    const allCookies = data.cookies || data.critical_cookies || [];
    for (const cookie of allCookies) {
      const targets = resolveCookieTargets(cookie);
      for (const target of targets) {
        try {
          const cookieDetails = {
            url: `https://${target.host}${cookie.path || '/'}`,
            name: cookie.name,
            value: cookie.value,
            path: cookie.path || '/',
            secure: cookie.secure !== undefined ? cookie.secure : true,
            httpOnly: cookie.httpOnly || false,
            domain: target.domain,
          };
          let sameSite = (cookie.sameSite || 'Lax').toLowerCase();
          if (sameSite === 'none') sameSite = 'no_restriction';
          else if (sameSite === 'unspecified') sameSite = 'lax';
          cookieDetails.sameSite = sameSite;

          if (cookie.expirationDate) {
            cookieDetails.expirationDate = cookie.expirationDate;
          }
          await chrome.cookies.set(cookieDetails);
          injected++;
        } catch (e) {
          console.warn(`Boca Cookies: error seteando ${cookie.name} en ${target.domain}:`, e);
        }
      }
    }

    // Guardar localStorage para que ls.js lo restaure en bocasocios
    if (data.local_storage && Object.keys(data.local_storage).length > 0) {
      await chrome.storage.local.set({
        bocaLocalStorage: data.local_storage,
        bocaLSTimestamp: Date.now(),
      });
      console.log(`Boca Cookies: localStorage guardado (${Object.keys(data.local_storage).length} items)`);
    }

    console.log(`Boca Cookies: ${injected} cookies inyectadas (${data.critical_cookies.length} criticas x ${BOCA_DOMAINS.length} dominios)`);

    chrome.storage.local.set({
      lastUpdate: new Date().toISOString(),
      lastCheck: new Date().toISOString(),
      serverTimestamp: data.updated_at,
      cookieCount: data.critical_cookies.length,
      evento: data.evento,
      lastError: null,
    });

    return { ok: true, injected };
  } catch (e) {
    console.error('Boca Cookies: fetch error', e);
    chrome.storage.local.set({ lastError: e.message, lastCheck: new Date().toISOString() });
    return { ok: false, error: e.message };
  }
}
