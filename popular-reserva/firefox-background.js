const SERVER_URL = 'https://boca-cookies.rosaleseze86.workers.dev';
const POLL_INTERVAL_MINUTES = 2;
const BOCA_DOMAINS = [
  'bocasocios.bocajuniors.com.ar',
  'bocasocios-gw.bocajuniors.com.ar',
];
const BOCA_PARENT = 'bocajuniors.com.ar';

console.log('Boca FF: background vivo', new Date().toISOString());

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create('refreshCookies', { periodInMinutes: POLL_INTERVAL_MINUTES });
  console.log('Boca FF: onInstalled');
  fetchAndInjectCookies();
});

chrome.runtime.onStartup.addListener(() => {
  fetchAndInjectCookies();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'refreshCookies') fetchAndInjectCookies();
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'forceRefresh') {
    console.log('Boca FF: forceRefresh');
    fetchAndInjectCookies().then((result) => {
      console.log('Boca FF: resultado', result);
      sendResponse(result);
    });
    return true;
  }
  if (msg.action === 'getStatus') {
    chrome.storage.local.get(['lastUpdate', 'cookieCount', 'lastError'], (data) => {
      sendResponse(data);
    });
    return true;
  }
  if (msg.action === 'setAccessCode') {
    chrome.storage.local.set({ accessCode: msg.code }, () => sendResponse({ ok: true }));
    return true;
  }
  if (msg.action === 'setServerUrl') {
    chrome.storage.local.set({ serverUrl: msg.url }, () => sendResponse({ ok: true }));
    return true;
  }
});

async function getServerUrl() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['serverUrl'], (data) => resolve(data.serverUrl || SERVER_URL));
  });
}

async function getAccessCode() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['accessCode'], (data) => resolve(data.accessCode || ''));
  });
}

function normalizeExpiry(expirationDate) {
  if (!expirationDate) return Math.floor(Date.now() / 1000) + 86400;
  return expirationDate > 1e12 ? Math.floor(expirationDate / 1000) : expirationDate;
}

async function setCookieOnTarget(cookie, target) {
  const url = `https://${target.host}${cookie.path || '/'}`;
  let sameSite = (cookie.sameSite || 'Lax').toLowerCase();
  if (sameSite === 'none') sameSite = 'no_restriction';
  else if (sameSite === 'unspecified') sameSite = 'lax';

  const base = {
    url,
    name: cookie.name,
    value: cookie.value,
    path: cookie.path || '/',
    secure: true,
    httpOnly: Boolean(cookie.httpOnly),
    domain: target.domain,
    sameSite,
    expirationDate: normalizeExpiry(cookie.expirationDate),
  };

  const attempts = [
    { ...base },
    { ...base, firstPartyDomain: '' },
    { ...base, partitionKey: { topLevelSite: `https://${target.host}` } },
    { ...base, firstPartyDomain: '', partitionKey: { topLevelSite: `https://${target.host}` } },
    { ...base, partitionKey: { topLevelSite: 'https://bocasocios.bocajuniors.com.ar' } },
  ];

  for (const details of attempts) {
    try {
      const set = await chrome.cookies.set(details);
      if (set) return true;
    } catch (e) {
      console.warn(`Boca Cookies FF: set fail ${cookie.name}`, e.message || e);
    }
  }
  return false;
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
      chrome.storage.local.set({ lastError: `HTTP ${resp.status}`, lastCheck: new Date().toISOString() });
      return { ok: false, error: `HTTP ${resp.status}` };
    }

    const data = await resp.json();
    if (!data.critical_cookies || data.critical_cookies.length === 0) {
      chrome.storage.local.set({ lastError: 'Sin cookies criticas', lastCheck: new Date().toISOString() });
      return { ok: false, error: 'Sin cookies criticas' };
    }
    if (data.active === false) {
      chrome.storage.local.set({ lastError: 'Evento no activo', lastCheck: new Date().toISOString() });
      return { ok: false, error: 'Evento no activo' };
    }

    try {
      const domainsToClean = [BOCA_PARENT, 'queue-it.net'];
      for (const parent of domainsToClean) {
        const existing = await chrome.cookies.getAll({ domain: parent });
        for (const c of existing) {
          const host = c.domain.startsWith('.') ? c.domain.slice(1) : c.domain;
          await chrome.cookies.remove({ url: `https://${host}${c.path || '/'}`, name: c.name });
        }
      }
    } catch (e) {
      console.warn('Boca Cookies FF: clean', e);
    }

    let injected = 0;
    const pageCookies = [];
    for (const cookie of data.cookies || data.critical_cookies || []) {
      const n = cookie.name || '';
      const skipQueue = n.startsWith('QueueIT') && /RedirectType(?:=|%3D)queue/i.test(cookie.value || '');
      for (const target of resolveCookieTargets(cookie)) {
        if (!skipQueue && (await setCookieOnTarget(cookie, target))) injected++;
        const n = cookie.name || '';
        if (n.startsWith('_ga') || n.startsWith('_cl')) continue;
        const val = cookie.value || '';
        if (n.startsWith('QueueIT') && /RedirectType(?:=|%3D)queue/i.test(val)) continue;
        pageCookies.push({
          name: cookie.name,
          value: cookie.value,
          domain: target.domain.startsWith('.') ? target.domain : `.${target.domain}`,
          path: cookie.path || '/',
        });
      }
    }

    const verify = await chrome.cookies.getAll({ domain: BOCA_PARENT });
    await chrome.storage.local.set({
      bocaPageCookies: pageCookies,
      bocaLocalStorage: data.local_storage || {},
      bocaLSTimestamp: Date.now(),
      lastUpdate: new Date().toISOString(),
      lastCheck: new Date().toISOString(),
      serverTimestamp: data.updated_at,
      cookieCount: data.critical_cookies.length,
      evento: data.evento,
      lastError: null,
    });

    return {
      ok: true,
      injected,
      verify: verify.length,
      names: verify.map((c) => c.name).join(','),
    };
  } catch (e) {
    chrome.storage.local.set({ lastError: e.message, lastCheck: new Date().toISOString() });
    return { ok: false, error: e.message };
  }
}
