# Machete de Comandos — boquita-v2

Comandos rápidos para tener a mano el día del partido o al instalar de cero.

---

## 🚀 Instalación en PC nueva (Windows de cero)

Abrir **PowerShell**:

```powershell
winget install -e --id Git.Git
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Google.Chrome
winget install -e --id Mozilla.Firefox
winget install -e --id GitHub.cli
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
```

Cerrar y abrir una terminal nueva:

```powershell
gh auth login
mkdir C:\projects -Force
cd C:\projects
gh repo clone morettimaxi/boquita-v2
cd C:\projects\boquita-v2
python -m pip install -r requirements.txt
cd platea; npm install; cd ..
setx WORKER_API_KEY "6HHGGVfCch0U80-3kfBZS5e8EbmeiEKE5kTea8FWn1o"
setx PYTHONUTF8 1
```

> **Nota:** Crear `popular-reserva\socios.csv` con tus socios (no se sube al repo por seguridad).

---

## 🔑 Tokens y Claves del Worker (Cloudflare)

Como este repositorio es privado, acá están los tokens vigentes y explicados:

| Token / Clave | Valor Actual | Permisos / Función | Dónde se usa |
|---|---|---|---|
| **API Key (Escritura)** | `6HHGGVfCch0U80-3kfBZS5e8EbmeiEKE5kTea8FWn1o` | Permite **subir** cookies al Worker (`POST /api/cookies`) | `queue_bot.py`, `upload_cookies.py`, `capture_browser.py`, `upload_latest_cookies.py` |
| **Access Code (Lectura)** | `Cangele2015` | Permite **descargar** cookies y entrar por extensión (`GET /api/cookies/latest` y `/go/...`) | `download_latest_cookies.py` (`--token`), link de extensión `/go/Cangele2015` |

> 💡 **Cómo cambiarlos más adelante por unos nuevos:**
> 1. En `popular-reserva/server`:
>    ```bash
>    npx wrangler secret put API_KEY       # Ingresás la nueva API Key de subida
>    npx wrangler secret put ACCESS_CODE   # Ingresás el nuevo token de descarga
>    ```
> 2. En tu Windows:
>    ```powershell
>    setx WORKER_API_KEY "TU_NUEVA_API_KEY"
>    ```

---

## ⚡ El día del partido (Paso a Paso)

### 1. Pasar la fila
En una terminal:
```bash
cd C:\projects\boquita-v2\queue-manager
python queue_bot.py
```
Abrir `http://localhost:5000` y lanzar sesiones. Apenas pasa la cola, **sube las cookies automáticamente al Worker**.

---

### 2. Cookies: Consultar y Descargar del Worker
En otra terminal (o desde cualquier PC):
```bash
cd C:\projects\boquita-v2\popular-reserva

# A) Ver si ya estan disponibles y que tan frescas son:
python download_latest_cookies.py --status

# (O miralo desde el cel en: https://boca-cookies.rosaleseze86.workers.dev/api/cookies/status)

# B) Descargar las cookies (las guarda en Downloads y en la carpeta actual):
python download_latest_cookies.py
```

*(Si hiciste la fila manual en Chrome, podés usar el script de consola F12 de más abajo).*

---

### 3. Reservar Popular
Desde `C:\projects\boquita-v2\popular-reserva`:

```bash
# Activos / Plenos (Titular + Grupo Familiar) - RÁPIDO RECOMENDADO:
python order-popu-familia-rapido.py --evento 870 --workers 8 --delay 1

# Variante escalonada lenta:
python order-popu-familia.py --evento 870 --workers 3

# Solo titulares (sin familia):
python order-popu.py --evento 870

# Probar login y conexion sin confirmar (dry run):
python order-popu-familia-rapido.py --evento 870 --dry-run
```

---

### 4. Adherentes y Copa
Desde `C:\projects\boquita-v2\popular-reserva`:

```bash
# Adherentes (adicional, sin pago en pasarela):
python adherentes.py --evento 869

# Copa (adicional + efectivo):
python adicional_copa.py --evento 869
```

---

### 5. Pagar sin hacer la cola

**Opción A: Abrir Chromes automáticos por socio**
```bash
cd C:\projects\boquita-v2\popular-reserva
python abrir-pago.py --csv socios.csv --evento 868
```

**Opción B: Extensión (Firefox / Chrome)**
1. Abrir Firefox con el perfil Boca:
   - PowerShell: `.\abrir-firefox.bat`
   - Git Bash: `cmd //c abrir-firefox.bat`
2. Ir a: `https://boca-cookies.rosaleseze86.workers.dev/go/Cangele2015`
3. Entrar a Boca Socios a pagar.

---

### 6. Plateas (Laterales Node.js)
Desde `C:\projects\boquita-v2\platea`:

```bash
# Terminal 1: Generador y Refresher de cookies/token (mantener abierto):
# Git Bash:
BOCA_EMAIL=socio@mail.com BOCA_PASSWORD='clave' EVENT_ID=868 node cookie-refresher-proxy.js
# PowerShell:
$env:BOCA_EMAIL="socio@mail.com"; $env:BOCA_PASSWORD="clave"; $env:EVENT_ID="868"; node cookie-refresher-proxy.js

# Terminal 2: Bot de laterales:
# Git Bash:
EVENT_ID=868 ASSIGNED_SECTORS=I,H node laterales-v22-multi.js
# PowerShell:
$env:EVENT_ID="868"; $env:ASSIGNED_SECTORS="I,H"; node laterales-v22-multi.js
```

---

## 📋 Machetes auxiliares

### Formato de `popular-reserva/socios.csv`
```csv
email,password
socio1@gmail.com,clave123
socio2@hotmail.com,clave456
```

### Script de consola (F12) para export manual
Si pasaste la fila a mano en Chrome, pegás esto en la consola F12 y dejás la pestaña abierta:
```javascript
(function(){function exp(){var c=document.cookie.split(';').map(function(x){var p=x.trim().split('=');return{name:p[0],value:p.slice(1).join('=')}});var d={timestamp:new Date().toISOString(),url:location.href,cookies:c,cookie_string:document.cookie};var b=new Blob([JSON.stringify(d,null,2)],{type:'application/json'});var a=document.createElement('a');var t=new Date();var pad=function(n){return String(n).padStart(2,'0')};var name='boca_cookies_'+t.getFullYear()+pad(t.getMonth()+1)+pad(t.getDate())+'_'+pad(t.getHours())+pad(t.getMinutes())+pad(t.getSeconds())+'.json';a.href=URL.createObjectURL(b);a.download=name;a.click();console.log('['+t.toLocaleTimeString()+'] Exportado '+name+' ('+c.length+' cookies)')}exp();setInterval(exp,120000);console.log('Auto-export activado: cada 2 minutos (archivo nuevo, no pisa)')})()
```
Y si querés subir ese archivo al Worker:
```bash
python upload_latest_cookies.py
```
