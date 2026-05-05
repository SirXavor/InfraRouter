# InfraRouter

Zero-Touch Provisioning y SD-WAN ligero para routers OpenWrt (GL.iNet, Teltonika RUTX50/RUTC50).

Un agente Go instalado en cada router se conecta a una API central, se registra, espera aprobación del operador y a partir de ahí sincroniza su configuración periódicamente. El servidor genera las claves WireGuard, asigna las IPs y distribuye la config completa: WireGuard, GRE, LAN, OSPF, DHCP/DNS, PXE.

---

## Arquitectura

```
   router (spoke)                     k8s cluster (hub)
  ┌─────────────────┐                ┌────────────────────────────┐
  │  infrarouter    │  POST /sync    │  FastAPI + SQLite          │
  │  agent (Go)  ───┼───────────────▶│  /panel/  → web panel      │
  │                 │◀───────────────┼─  /devices/ → agente API   │
  │  aplica config  │  JSON config   │  /admin/  → operador API   │
  │  via UCI / FRR  │                │                            │
  └────────┬────────┘                │  wg set wg0 peer ...       │
           │ WireGuard               │  (hostNetwork + NET_ADMIN) │
           └────────────────────────▶│  wg0 en el host            │
                    192.168.254.X    └────────────────────────────┘
```

**Hub:** `192.168.254.1` — interfaz `wg0` del nodo k8s, gestionada por wg-easy. InfraRouter añade peers de forma no destructiva (nunca borra los peers de wg-easy).

**Spokes:** `192.168.254.X` (X = peer index asignado por el servidor, empieza en 2).

---

## Flujo de enrollamiento

```
1. Instalar agente con tres variables de entorno:
      INFRAROUTER_URL       = https://infrarouter.hermes.ranabo.com
      INFRAROUTER_DEVICE_ID = nombre-unico-del-router
      INFRAROUTER_TOKEN     = token-secreto

2. El agente hace POST /devices/enroll  →  queda en estado "pending"

3. El operador aprueba en el panel web  →  servidor genera keypair WireGuard,
   asigna peer index, añade el peer al hub, config_version = 1

4. El agente detecta la aprobación y entra en el loop de sync cada 60s:
      POST /devices/{id}/sync  {"applied_version": N}
   Si hay config nueva  →  responde con el JSON completo
   Si ya está al día    →  responde con config: null
```

---

## Configuración que distribuye el servidor

Cada config se construye determinísticamente a partir del `wg_peer_index` (X):

| Parámetro         | Valor                        |
|-------------------|------------------------------|
| WG address spoke  | `192.168.254.X/32`           |
| WG hub            | `192.168.254.1` (endpoint configurable) |
| GRE local / remoto | `10.0.X.2` / `10.0.X.1`    |
| GRE network       | `10.0.X.0/30`                |
| OSPF router-id    | `192.168.254.X`              |
| OSPF area         | `0.0.0.0`                    |
| LAN IP / red      | configurable por dispositivo |

La config global (DNS, NTP, PXE) se aplica a todos los dispositivos aprobados. Cualquier cambio incrementa `config_version` y los agentes la reciben en el siguiente sync.

---

## Componentes

### `src/api/` — Orquestador (FastAPI + SQLite)

| Ruta | Función |
|------|---------|
| `POST /devices/enroll` | Registro inicial del agente |
| `GET /devices/{id}/status` | Estado del dispositivo (requiere Bearer token) |
| `POST /devices/{id}/sync` | Heartbeat + entrega de config |
| `POST /admin/devices/{id}/approve` | Aprobación de operador |
| `DELETE /admin/devices/{id}` | Revocación |
| `PUT /config/{id}/local` | Config de LAN por dispositivo |
| `PUT /config/global` | Config global (DNS/NTP/PXE) |
| `GET /panel/` | Panel web |

### `src/agent/` — Agente (Go, cross-compile para OpenWrt)

Binario estático sin dependencias. Aplica la config recibida vía UCI (red, DHCP) y escribe ficheros de configuración para FRR/Quagga (OSPF). Soporta modo dry-run (`INFRAROUTER_DRY_RUN=1`) para pruebas sin ejecutar nada.

Targets de compilación:
```bash
# GL-AR300M (MIPS little-endian)
GOOS=linux GOARCH=mipsle GOMIPS=softfloat go build -o infrarouter-agent-mipsle ./src/agent

# GL-SFT1200 / GL-A1300 (ARMv7)
GOOS=linux GOARCH=arm GOARM=7 go build -o infrarouter-agent-armv7 ./src/agent

# GL-MT2500 Brume2 / Teltonika (ARM64)
GOOS=linux GOARCH=arm64 go build -o infrarouter-agent-arm64 ./src/agent
```

---

## Variables de entorno del agente

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `INFRAROUTER_URL` | Sí | URL base del servidor |
| `INFRAROUTER_DEVICE_ID` | Sí | Identificador único del router |
| `INFRAROUTER_TOKEN` | Sí | Token de autenticación |
| `INFRAROUTER_SYNC_INTERVAL` | No (60s) | Intervalo de sync en segundos |
| `INFRAROUTER_DRY_RUN` | No | Si es `1`, logea sin ejecutar nada |

---

## Instalación del agente en un router OpenWrt

```sh
# Copiar el binario
scp infrarouter-agent-armv7 root@192.168.1.1:/usr/bin/infrarouter-agent
chmod +x /usr/bin/infrarouter-agent

# Crear fichero de arranque
cat > /etc/init.d/infrarouter << 'EOF'
#!/bin/sh /etc/rc.common
START=99
USE_PROCD=1

start_service() {
    procd_open_instance
    procd_set_param command /usr/bin/infrarouter-agent
    procd_set_param env \
        INFRAROUTER_URL=https://infrarouter.hermes.ranabo.com \
        INFRAROUTER_DEVICE_ID=router-sede-01 \
        INFRAROUTER_TOKEN=token-secreto
    procd_set_param respawn
    procd_close_instance
}
EOF

chmod +x /etc/init.d/infrarouter
/etc/init.d/infrarouter enable
/etc/init.d/infrarouter start
```

---

## Deploy en Kubernetes

```bash
# 1. Construir y publicar la imagen
./scripts/redeploy.sh          # build + push + rollout restart

# 2. Crear el secret en Vault (una vez)
kubectl apply -k external-secrets/infrarouter-hermes/

# 3. ArgoCD gestiona el resto desde deploy/infrarouter/
```

El panel estará disponible en `https://infrarouter.hermes.ranabo.com/panel/`.

### ConfigMap — valores a revisar tras el primer deploy

```yaml
WG_HUB_PUBLIC_KEY   # wg show wg0 public-key en el nodo del hub
WG_ENDPOINT         # host:puerto público del hub WireGuard
```

---

## Estructura del repositorio

```
InfraRouter/
├── src/
│   ├── api/          # Orquestador Python (FastAPI)
│   │   ├── app/
│   │   │   ├── routes/       # admin, devices, config, panel
│   │   │   ├── db/           # modelos SQLAlchemy + CRUD
│   │   │   ├── templates/    # panel HTML (Jinja2)
│   │   │   ├── config_builder.py
│   │   │   ├── wg_hub.py     # gestión directa de wg0
│   │   │   └── settings.py
│   │   └── tests/
│   └── agent/        # Agente Go (OpenWrt)
│       ├── main.go
│       ├── client.go
│       ├── config.go
│       └── apply.go
├── deploy/
│   └── infrarouter/  # Kustomize: namespace, secrets, PVC, deployment, ingress
├── scripts/
│   ├── build.sh      # docker build
│   ├── push.sh       # docker push
│   ├── redeploy.sh   # build + push + restart
│   └── restart.sh    # kubectl rollout restart
└── readme.md
```
