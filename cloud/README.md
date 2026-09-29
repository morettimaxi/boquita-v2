# Módulo Cloud (Operación con 2 PCs y Monitoreo Remoto)

Esta carpeta contiene todo lo necesario para operar el sistema entre dos computadoras:
1. **PC 2 (o servidor/otra máquina):** Corre las sesiones de Chrome en segundo plano (`queue_bot_cloud.py`) y le envía al Worker en tiempo real cuánto tiempo le falta a la mejor sesión y sube las cookies automáticamente al pasar.
2. **PC 1 (tu máquina principal):** Monitorea la fila en vivo (`monitor.py --watch`) y, ni bien el bot pasa la fila, descarga las cookies automáticamente para que reserves con `popular-reserva/order-popu-familia-rapido.py`.

---

## 📂 Archivos en esta carpeta

- **`queue_bot_cloud.py`**: Bot de cola de Queue-it con envío de telemetría (heartbeat) y subida automática de cookies al Worker.
- **`monitor.py`**: Monitor CLI en tiempo real para ver los mejores tiempos del bot desde tu PC principal.
- **`download_cookies.py`**: Descargador de cookies desde el Worker a `Downloads` y a `popular-reserva/`.
- **`upload_cookies.py`**: Script para subir manualmente cualquier archivo de cookies al Worker.
- **`worker/`**: Código fuente y configuración del Cloudflare Worker desplegado en `https://boca-cookies.rosaleseze86.workers.dev`.

---

## 🚀 Guía de Operación Paso a Paso

### Paso 1: En la otra PC (donde corre la cola)
Clonar o actualizar el repositorio `boquita-v2` y ejecutar:

```bash
cd C:\projects\boquita-v2\cloud
python queue_bot_cloud.py
```
- Abrir `http://localhost:5000` en el navegador y lanzar las sesiones deseadas.
- El bot reporta automáticamente cada 10-12 segundos el **mejor tiempo restante** al Worker.
- Apenas una sesión pasa la fila, captura las cookies y el `localStorage` y los sube de forma automática.

---

### Paso 2: En tu PC principal (donde hacés la reserva)
En una terminal en tu máquina:

```bash
cd C:\projects\boquita-v2\cloud

# Monitorear la fila en vivo (refresca cada 4 segundos):
python monitor.py --watch
```

**Salida en pantalla:**
```text
[*] Monitoreando estado de la fila en vivo desde https://boca-cookies.rosaleseze86.workers.dev
[15:50:02] Bot: ONLINE           | MEJOR: 4 min      | Promedio: 12 min   | Sesiones: 30/30 | Pasadas: 0
[15:50:06] Bot: ONLINE           | MEJOR: 3 min      | Promedio: 11.5 min | Sesiones: 30/30 | Pasadas: 0
```

> ⚡ **Descarga Automática:** Cuando una sesión pasa la cola en la otra PC, `monitor.py --watch` detecta el cambio, te avisa en pantalla y descarga las cookies de forma automática a `Downloads` y a `popular-reserva/`.

---

### Paso 3: En tu PC principal (hacer la reserva)
Apenas las cookies están descargadas:

```bash
cd C:\projects\boquita-v2\popular-reserva

# Reservar populares para todos los socios de socios.csv:
python order-popu-familia-rapido.py --evento 870 --workers 8 --delay 1
```

---

## 📱 Monitoreo desde el Celular o Navegador

Podés chequear el estado en vivo desde cualquier dispositivo entrando a:
- **Ver solo la fila y tiempos:**  
  👉 `https://boca-cookies.rosaleseze86.workers.dev/api/queue/status`
- **Ver fila + estado de cookies:**  
  👉 `https://boca-cookies.rosaleseze86.workers.dev/api/cookies/status`

---

## 🔑 Credenciales del Worker
- **URL Base:** `https://boca-cookies.rosaleseze86.workers.dev`
- **Token de Descarga (Lectura):** `Cangele2015`
- **API Key de Subida (Escritura):** `6HHGGVfCch0U80-3kfBZS5e8EbmeiEKE5kTea8FWn1o`
- *(Ambas credenciales ya vienen configuradas por defecto en los scripts).*
