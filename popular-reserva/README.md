# popular-reserva

Confirma / reserva popular por API para cada socio de `socios.csv`.

Antes: instalación del [README principal](../README.md).

Todos los comandos se corren **desde esta carpeta**:

| Git Bash | PowerShell |
|---|---|
| `cd /c/projects/boquita-v2/popular-reserva` | `cd C:\projects\boquita-v2\popular-reserva` |

Los comandos `python ...` son iguales en Git Bash y PowerShell.

## 1. Crear socios.csv (una vez)

No está en el repo (tiene contraseñas). Crear `popular-reserva/socios.csv` con este formato, una línea por socio:

```
email,password
socio@gmail.com,clave
otro@hotmail.com,otraclave
```

Abrirlo para editar:

| Git Bash | PowerShell |
|---|---|
| `notepad socios.csv` | `notepad socios.csv` |

## 2. Número de evento

Sale de la URL de Boca Socios: `.../matches/870/...` → evento `870`.

## 3. Cookies de la cola

Hay dos formas de tener las cookies:

### Opción A (Recomendada): Descargar del Worker con token

Si el `queue_bot.py` ya pasó la cola y subió las cookies (o se subieron desde otra PC):

```bash
python download_latest_cookies.py
```

- Usa por defecto el token `Cangele2015` (o podés pasar `--token TU_TOKEN`).
- **Guarda automáticamente en dos lugares:**
  1. En `Downloads` (`C:\Users\moret\Downloads\boca_cookies_worker.json`)
  2. En la carpeta local (`boca_cookies_worker.json`)
- Muestra la antigüedad de las cookies y si contienen `QueueITAccepted`.
- **Los scripts de popular (`order-popu*`) detectan y usan este archivo automáticamente** porque eligen el archivo de cookies más nuevo disponible.

**Consultar estado y fecha de generación de las cookies en el Worker:**
```bash
# Desde la terminal:
python download_latest_cookies.py --status

# O directo en el navegador / celular:
https://boca-cookies.rosaleseze86.workers.dev/api/cookies/status
```

### Opción B: Exportar manual desde el Chrome que pasó la fila

1. En el Chrome que **pasó la cola** (el del queue_bot o uno manual), estar en Boca Socios.
2. `F12` → pestaña **Console** → escribir `allow pasting` + Enter.
3. Pegar esto + Enter:

```javascript
(function(){function exp(){var c=document.cookie.split(';').map(function(x){var p=x.trim().split('=');return{name:p[0],value:p.slice(1).join('=')}});var d={timestamp:new Date().toISOString(),url:location.href,cookies:c,cookie_string:document.cookie};var b=new Blob([JSON.stringify(d,null,2)],{type:'application/json'});var a=document.createElement('a');var t=new Date();var pad=function(n){return String(n).padStart(2,'0')};var name='boca_cookies_'+t.getFullYear()+pad(t.getMonth()+1)+pad(t.getDate())+'_'+pad(t.getHours())+pad(t.getMinutes())+pad(t.getSeconds())+'.json';a.href=URL.createObjectURL(b);a.download=name;a.click();console.log('['+t.toLocaleTimeString()+'] Exportado '+name+' ('+c.length+' cookies)')}exp();setInterval(exp,120000);console.log('Auto-export activado: cada 2 minutos (archivo nuevo, no pisa)')})()
```

4. Dejar la pestaña abierta: baja un `boca_cookies_*.json` nuevo a **Descargas** cada 2 min.

Los scripts toman solos el más nuevo de Descargas. Para usar uno específico: `--cookies C:\ruta\boca_cookies_xxx.json`.

## 4. Correr el script del caso

Primero se puede probar sin confirmar nada agregando `--dry-run`.

| Caso | Comando |
|---|---|
| **Activos / plenos** (titular + familia), el recomendado | `python order-popu-familia-rapido.py --evento 870 --workers 8 --delay 1` |
| Activos, lanzando más lento | `python order-popu-familia.py --evento 870 --workers 3` |
| Activos, solo el titular | `python order-popu.py --evento 870` |
| **Adherentes** (adicional, sin pago) | `python adherentes.py --evento 869` |
| **Copa** (adicional + pago en efectivo) | `python adicional_copa.py --evento 869` |
| **Pagar**: abre un Chrome logueado por socio | `python abrir-pago.py --csv socios.csv --evento 868` |

- `--workers`: cuántos socios en paralelo. `--delay` (solo en `-rapido`): segundos entre lanzamientos.
- `--dry-run`: en order-popu*, adherentes y adicional_copa (no en abrir-pago).
- Si un socio falla (clave mal, adherente, rechazo) sigue con el resto. Al final imprime un **RESUMEN** con OK / YA CONFIRMADO / NO HABILITADO / LOGIN FAIL / FAIL.
- Si Boca devuelve 403 seguido: subir `--delay` o bajar `--workers`.
- Un solo socio para pagar: `python abrir-pago.py --email socio@gmail.com --password clave --evento 868`.

## 5. Pagar sin fila (extensión)

### 5.1 Subir las cookies al worker

Toma el `boca_cookies_*.json` más nuevo de Descargas (necesita `WORKER_API_KEY`):

```bash
python upload_latest_cookies.py
python upload_latest_cookies.py --evento 870 --force
```

### 5.2 Instalar la extensión (una vez por navegador)

- **Firefox (recomendado):** abrir el perfil Boca que ya trae la extensión:

  | Git Bash | PowerShell |
  |---|---|
  | `cmd //c abrir-firefox.bat` | `.\abrir-firefox.bat` |

  O doble click en `abrir-firefox.bat` desde el Explorador.
  Manual: `about:addons` → engranaje → *Instalar complemento desde archivo* → `boca-cookies-firefox.xpi`.
- **Chrome:** `chrome://extensions` → activar *Modo desarrollador* → *Cargar descomprimida* → carpeta `popular-reserva/extension`.

### 5.3 Entrar

Abrir https://boca-cookies.rosaleseze86.workers.dev/go/Cangele2015 en ese navegador y después entrar a Boca Socios.

## Worker (solo si hay que redeployar)

**Git Bash**

```bash
cd /c/projects/boquita-v2/popular-reserva/server
npx wrangler login
npx wrangler secret put API_KEY
npx wrangler secret put ACCESS_CODE
npx wrangler deploy
```

**PowerShell**

```powershell
cd C:\projects\boquita-v2\popular-reserva\server
npx wrangler login
npx wrangler secret put API_KEY
npx wrangler secret put ACCESS_CODE
npx wrangler deploy
```

## 6. Referencia de scripts en esta carpeta

| Script | Para qué sirve | Parámetros principales |
|---|---|---|
| `download_latest_cookies.py` | Descarga las últimas cookies del Worker usando el token | `--token`, `--status`, `--force`, `--output` |
| `order-popu-familia-rapido.py` | **Principal reserva:** titular + grupo familiar con delay fijo rápido | `--evento` (req), `--workers` (def: 5), `--delay` (def: 1.5), `--dry-run`, `--cookies` |
| `order-popu-familia.py` | Variante familiar con delay incremental escalonado | `--evento` (req), `--workers`, `--dry-run`, `--cookies` |
| `order-popu.py` | Reserva solo para titulares (sin grupo familiar) | `--evento` (req), `--workers`, `--dry-run`, `--cookies` |
| `adherentes.py` | Reserva adicional para adherentes (sin pasarela) | `--evento` (req), `--workers`, `--dry-run`, `--cookies` |
| `adicional_copa.py` | Reserva adicional para partidos de copa | `--evento` (req), `--workers`, `--dry-run`, `--cookies` |
| `abrir-pago.py` | Abre un Chrome por socio logueado listo para abonar | `--csv socios.csv`, `--evento`, `--email`, `--password` |
| `upload_latest_cookies.py` | Sube el archivo `boca_cookies*.json` más reciente de Downloads al Worker | `--evento`, `--force`, `--file` |

## Problemas

| Síntoma | Solución |
|---|---|
| `No hay socios para procesar` | Falta `socios.csv` o no tiene la línea `email,password` arriba. |
| No encuentra cookies | Correr el paso 3 o pasar `--cookies ruta.json`. |
| Todos dan 403 | Cookies viejas (repetir paso 3) o bajar `--workers`. |
| `npx` bloqueado en PowerShell | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force` |
