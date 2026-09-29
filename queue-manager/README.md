# queue-manager

Abre varias sesiones de Chrome en la cola de Boca Socios y muestra un dashboard.
Cuando una sesión pasa, guarda `session_N_cookies.json` (cookies HttpOnly + localStorage) y lo sube al worker.

Antes: instalación del [README principal](../README.md) (Python, Chrome, `pip install`, `WORKER_API_KEY`).

## 1. Arrancar el bot

**Git Bash**

```bash
cd /c/projects/boquita-v2/queue-manager
python queue_bot.py
```

**PowerShell**

```powershell
cd C:\projects\boquita-v2\queue-manager
python queue_bot.py
```

Dejar esa terminal abierta. `Ctrl+C` para cortar.

## 2. Usar el dashboard

1. Abrir http://localhost:5000 en el navegador.
2. Lanzar las sesiones desde el dashboard.
3. Esperar que alguna pase la cola: aparece como pasada y se sube sola al worker.

## 3. Subir a mano una sesión al worker (si la subida automática falló)

`3` es el número de sesión (`session_3_cookies.json`). Igual en las dos terminales, desde `queue-manager`:

```bash
python upload_cookies.py 3
python upload_cookies.py 3 --evento 870 --force
```

## 4. Capturar cookies de un Chrome manual (sin el bot)

Abre Chrome en Boca Socios. Si estás en la cola, espera solo a que pases; ahí captura cookies + localStorage y las sube. Después `Enter` en la terminal cierra Chrome.

```bash
python capture_browser.py --upload
```

Sin `--upload` solo guarda `browser_cookies.json`. Sube como evento 868.

## Archivos

| Archivo | Para qué |
|---|---|
| `queue_bot.py` | El que se usa. |
| `queue_manager-v4.py` | Versión anterior estable (sin subida al worker). Solo de respaldo: `python queue_manager-v4.py`. |
| `upload_cookies.py` | Paso 3. |
| `capture_browser.py` | Paso 4. |

## Problemas

| Síntoma | Solución |
|---|---|
| `WORKER_API_KEY` vacía / 401 al subir | Hacer el `setx WORKER_API_KEY` del README principal y reabrir la terminal. |
| El dashboard no abre | Ver que `queue_bot.py` siga corriendo y que nada más use el puerto 5000. |
| Error de Chrome / chromedriver | Actualizar Chrome (`winget upgrade Google.Chrome`) y `python -m pip install -U selenium`. |
