# boquita-v2

| Carpeta | Qué hace | Guía |
|---|---|---|
| `queue-manager/` | Pasa la cola de Boca Socios con varias sesiones de Chrome | [queue-manager/README.md](queue-manager/README.md) |
| `popular-reserva/` | Confirma / reserva popular por API para los socios de `socios.csv` + extensión para pagar sin fila | [popular-reserva/README.md](popular-reserva/README.md) |
| `platea/` | Laterales (Node): reserva plateas por sector | [platea/README.md](platea/README.md) |
| `cloud/` | **Nuevo:** Operación remota entre 2 PCs, telemetría de fila en vivo y auto-descarga de cookies | [cloud/README.md](cloud/README.md) |

En Windows los comandos están en **Git Bash** y **PowerShell**. En Mac se usa la **Terminal** (zsh). El día del partido, el detalle de cada comando está en [commands-correr.md](commands-correr.md).

| | Git Bash | PowerShell |
|---|---|---|
| Rutas | `/c/projects/boquita-v2` | `C:\projects\boquita-v2` |
| Variable para un comando | `EVENT_ID=868 node x.js` | `$env:EVENT_ID="868"; node x.js` |
| Correr un `.bat` | `cmd //c abrir-firefox.bat` | `.\abrir-firefox.bat` |
| Cortar un script | `Ctrl+C` | `Ctrl+C` |

---

## 1. Instalar (una sola vez por PC)

### 1.1 Programas

Abrir **PowerShell** (winget se corre ahí):

```powershell
winget install -e --id Git.Git
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Google.Chrome
winget install -e --id Mozilla.Firefox
winget install -e --id GitHub.cli
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
```

`Set-ExecutionPolicy` es para que PowerShell deje correr `npm` / `npx`. Cerrar **todas** las terminales y abrir una nueva.

### 1.2 Bajar el repo e instalar dependencias

**Git Bash**

```bash
gh auth login
mkdir -p /c/projects && cd /c/projects
gh repo clone morettimaxi/boquita-v2
cd /c/projects/boquita-v2
python -m pip install -r requirements.txt
cd platea && npm install && cd ..
```

**PowerShell**

```powershell
gh auth login
mkdir C:\projects -Force
cd C:\projects
gh repo clone morettimaxi/boquita-v2
cd C:\projects\boquita-v2
python -m pip install -r requirements.txt
cd platea; npm install; cd ..
```

`gh auth login`: elegir GitHub.com → HTTPS → login con el navegador, con la cuenta que tiene acceso al repo.
Si `python` abre la Microsoft Store, usar `py` en lugar de `python`.

### 1.3 Variables fijas (quedan guardadas en Windows)

Sirve igual en Git Bash y PowerShell:

```bash
setx WORKER_API_KEY "6HHGGVfCch0U80-3kfBZS5e8EbmeiEKE5kTea8FWn1o"
setx PYTHONUTF8 1
```

- `WORKER_API_KEY`: clave para subir cookies al Worker (`POST /api/cookies`) desde los bots y scripts de upload.
- `PYTHONUTF8=1`: evita errores de acentos/emojis en la consola.

#### 🔑 Tokens del Worker (Cloudflare)
Como este repositorio es privado, quedan documentadas las claves actuales:
* **API Key de subida (escritura):** `6HHGGVfCch0U80-3kfBZS5e8EbmeiEKE5kTea8FWn1o` (va en `WORKER_API_KEY`).
* **Código de acceso / Token de descarga (lectura):** `Cangele2015` (usado por `download_latest_cookies.py` y el enlace de la extensión `/go/Cangele2015`).

*(Si más adelante los cambiás en Cloudflare vía `npx wrangler secret put`, solo actualizás el `setx WORKER_API_KEY` en tu Windows).*

Cerrar y abrir la terminal para que las tome. Comprobar:

| Git Bash | PowerShell |
|---|---|
| `echo $WORKER_API_KEY` | `echo $env:WORKER_API_KEY` |

### 1.4 Actualizar el repo (cuando haya cambios)

| Git Bash | PowerShell |
|---|---|
| `cd /c/projects/boquita-v2 && git pull` | `cd C:\projects\boquita-v2; git pull` |

### 1.5 Instalar en Mac

El README de arriba es Windows. En Mac, una sola vez, en la Terminal:

```bash
# Si no tenés Homebrew: https://brew.sh
brew install git python@3.12 node gh
brew install --cask google-chrome firefox
```

Cerrar y abrir la Terminal. Después:

```bash
gh auth login
mkdir -p ~/projects && cd ~/projects
gh repo clone morettimaxi/boquita-v2
cd ~/projects/boquita-v2
python3 -m pip install -r requirements.txt
cd platea && npm install && cd ..
```

`gh auth login`: GitHub.com, HTTPS, con la cuenta que tiene acceso al repo.

La clave del Worker ya está escrita en `queue_bot.py`, `queue_bot_cloud.py`, `upload_latest_cookies.py`, `upload_cookies.py` y `capture_browser.py`. En Mac no hace falta `setx`.

`socios.csv` no está en el repo. Copiarlo desde la PC de Windows a la Mac, en:

```text
~/projects/boquita-v2/popular-reserva/socios.csv
```

Desde la Mac, si la PC de Windows está prendida y comparte la carpeta, o pasándolo por AirDrop / pendrive. El archivo tiene que llamarse `socios.csv` y quedar en `popular-reserva/`.

Chrome tiene que estar instalado. Selenium baja el driver solo la primera vez que corre `queue_bot.py`.

Comprobar:

```bash
python3 --version
node --version
google-chrome --version || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --version
```

Actualizar después:

```bash
cd ~/projects/boquita-v2 && git pull
```

Para correr, los mismos Python del día del partido, cambiando la ruta:

```bash
cd ~/projects/boquita-v2/queue-manager
python3 queue_bot.py
```

```bash
cd ~/projects/boquita-v2/popular-reserva
python3 download_latest_cookies.py --watch
python3 adicional_copa.py --evento 869
python3 abrir-pago.py --csv socios.csv --evento 869
```

Si en la Mac `python3` es el que funciona y `python` no existe, usá `python3` en todos los comandos de [commands-correr.md](commands-correr.md). El dashboard sigue siendo `http://localhost:5000`.

El `.bat` de Firefox es de Windows. En Mac abrí Firefox a mano y entrá a:

`https://boca-cookies.rosaleseze86.workers.dev/go/Cangele2015`

---

## 2. Orden de un día de partido

1. **Pasar la cola** → [queue-manager](queue-manager/README.md): `python queue_bot.py`, dashboard en http://localhost:5000. Cuando una sesión pasa, **sube automáticamente las cookies al Worker**.
2. **Obtener cookies para popular** → En `popular-reserva`:
   - Monitorear la cola en vivo: `python download_latest_cookies.py --watch` (o solo ver: `python download_latest_cookies.py --queue`)
   - Ver estado completo y vigencia de cookies: `python download_latest_cookies.py --status` (o abrí en el cel `https://boca-cookies.rosaleseze86.workers.dev/api/queue/status`)
   - Bajar las cookies ni bien pasan: `python download_latest_cookies.py` (las guarda en `Downloads` y local).
3. **Popular**: correr el script de reserva → [popular-reserva](popular-reserva/README.md):
   `python order-popu-familia-rapido.py --evento 870 --workers 8 --delay 1`
4. **Pagar sin fila**: abrir la extensión en Firefox o Chrome con el link `/go/Cangele2015` → [popular-reserva, paso 5](popular-reserva/README.md#5-pagar-sin-fila-extensión).
5. **Plateas**: primero `cookie-refresher-proxy.js`, después `laterales-v22-multi.js` → [platea](platea/README.md).
