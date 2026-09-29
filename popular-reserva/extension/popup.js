const statusBox = document.getElementById('statusBox');
const details = document.getElementById('details');
const btnRefresh = document.getElementById('btnRefresh');
const btnGo = document.getElementById('btnGo');
const accessCodeInput = document.getElementById('accessCode');
const btnSaveCode = document.getElementById('btnSaveCode');
const serverUrlInput = document.getElementById('serverUrl');
const btnSave = document.getElementById('btnSave');

function updateUI(data) {
  const hasError = data.lastError;
  const hasUpdate = data.lastUpdate;

  if (hasError) {
    statusBox.className = 'status err';
    statusBox.textContent = 'Error: ' + data.lastError;
  } else if (hasUpdate) {
    statusBox.className = 'status ok';
    statusBox.textContent = 'Cookies activas';
  } else {
    statusBox.className = 'status warn';
    statusBox.textContent = 'Sin cookies cargadas';
  }

  let html = '';
  if (data.cookieCount) {
    html += `<div class="row"><span class="label">Cookies criticas:</span><span class="value">${data.cookieCount}</span></div>`;
  }
  if (data.evento) {
    html += `<div class="row"><span class="label">Evento:</span><span class="value">${data.evento}</span></div>`;
  }
  if (data.lastUpdate) {
    const ago = Math.round((Date.now() - new Date(data.lastUpdate).getTime()) / 60000);
    const cls = ago < 5 ? 'fresh' : 'stale';
    html += `<div class="row"><span class="label">Ultima actualizacion:</span><span class="value ${cls}">hace ${ago} min</span></div>`;
  }
  if (data.lastCheck) {
    const ago = Math.round((Date.now() - new Date(data.lastCheck).getTime()) / 60000);
    html += `<div class="row"><span class="label">Ultimo check:</span><span class="value">hace ${ago} min</span></div>`;
  }

  details.innerHTML = html;
}

function loadStatus() {
  chrome.runtime.sendMessage({ action: 'getStatus' }, (data) => {
    if (data) updateUI(data);
  });
}

btnRefresh.addEventListener('click', () => {
  btnRefresh.disabled = true;
  btnRefresh.textContent = 'Actualizando...';
  chrome.runtime.sendMessage({ action: 'forceRefresh' }, (result) => {
    btnRefresh.disabled = false;
    btnRefresh.textContent = 'Actualizar cookies ahora';
    loadStatus();
  });
});

btnGo.addEventListener('click', () => {
  chrome.tabs.create({ url: 'https://bocasocios.bocajuniors.com.ar/auth/login' });
});

btnSave.addEventListener('click', () => {
  const url = serverUrlInput.value.trim();
  if (url) {
    chrome.runtime.sendMessage({ action: 'setServerUrl', url }, () => {
      btnSave.textContent = 'Guardado!';
      setTimeout(() => { btnSave.textContent = 'Guardar URL'; }, 1500);
    });
  }
});

chrome.storage.local.get(['serverUrl', 'accessCode'], (data) => {
  if (data.serverUrl) serverUrlInput.value = data.serverUrl;
  if (data.accessCode) accessCodeInput.value = data.accessCode;
});

btnSaveCode.addEventListener('click', () => {
  const code = accessCodeInput.value.trim();
  if (code) {
    chrome.runtime.sendMessage({ action: 'setAccessCode', code }, () => {
      btnSaveCode.textContent = 'Guardado!';
      setTimeout(() => { btnSaveCode.textContent = 'Guardar codigo'; }, 1500);
    });
  }
});

loadStatus();
