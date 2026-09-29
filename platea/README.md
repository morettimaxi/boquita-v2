# Platea laterales

`laterales-v22-multi.js` consulta los sectores asignados de un evento y reserva cuando hay lugar.
Usa las cookies y el token que genera `cookie-refresher-proxy.js`.

## Instalar

```bash
cd platea
npm install
```

## Variables

| Variable | Uso |
|---|---|
| `BOCA_EMAIL` / `BOCA_PASSWORD` | Login del socio (password en texto plano) |
| `EVENT_ID` | Evento (default `868`) |
| `ASSIGNED_SECTORS` | Sectores, ej. `I,H` |
| `INSTANCE_ID` | Nombre de la instancia para el log (default `inst1`) |
| `PROXY_USER` / `PROXY_PASS` | Opcional, IPRoyal |

## Correr (Git Bash, dos terminales)

```bash
# 1) cookies + token (se refresca cada 3 min, abre Chrome)
BOCA_EMAIL=socio@mail.com BOCA_PASSWORD='clave' EVENT_ID=868 node cookie-refresher-proxy.js

# 2) laterales
EVENT_ID=868 ASSIGNED_SECTORS=I,H node laterales-v22-multi.js
```

Genera `queue-cookies-proxy.txt`, `shared-token-proxy.json`, `sectors-event-<id>.json`,
`log-<fecha>-<inst>.txt` y `reserva.txt` (no se suben al repo).
