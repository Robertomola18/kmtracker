<p align="center">
  <img src="static/logo.png" alt="KMtracker" width="360">
</p>

<h1 align="center">KMtracker</h1>

<p align="center">
  <b>Tu taller de vehículos, en tu propia casa.</b><br>
  Kilometraje, combustible, gastos y mantenimiento para todos tus coches y motos,
  todo en un sitio y bajo tu control.
</p>

<p align="center">
  <a href="README.md">Read in English 🇬🇧</a>
</p>

<p align="center">
  <b>¿Usas Windows?</b> <a href="#windows-1011-docker-desktop">Instalación con Docker Desktop</a>
</p>

<p align="center">
  📖 <b><a href="docs/manual/manual-es.md">Manual de usuario</a></b> ·
  <a href="docs/manual/manual-es.pdf">versión PDF</a> ·
  <a href="docs/manual/manual-en.md">English manual</a>
</p>

---

## Índice

- [Manual de usuario](docs/manual/manual-es.md)
- [Capturas](#capturas)
- [¿Qué es KMtracker?](#qué-es-kmtracker)
- [¿Para quién es?](#para-quién-es)
- [Todo lo que puedes hacer](#todo-lo-que-puedes-hacer)
- [Cómo se usa en el día a día](#cómo-se-usa-en-el-día-a-día)
- [Instalación con Docker (5 minutos)](#instalación-con-docker-5-minutos)
- [Instalación en Windows](#windows-1011-docker-desktop)
- [Configuración](#configuración)
- [Bot de Telegram (opcional)](#bot-de-telegram-opcional)
- [Copias de seguridad](#copias-de-seguridad)
- [Preguntas frecuentes](#preguntas-frecuentes)
- [Para desarrolladores](#para-desarrolladores)
- [Tecnologías](#tecnologías)
- [Contacto](#contacto)
- [Licencia y autor](#licencia-y-autor)

---

## Capturas

<p align="center">
  <img src="docs/capturas/demo.gif" alt="Demo de KMtracker" width="620">
</p>

<table>
  <tr>
    <td align="center" width="50%"><b>Panel</b><br><a href="docs/capturas/panel.png"><img src="docs/capturas/panel.png" width="440" alt="Panel"></a></td>
    <td align="center" width="50%"><b>Ficha de vehículo</b><br><a href="docs/capturas/coche.png"><img src="docs/capturas/coche.png" width="440" alt="Ficha de vehículo"></a></td>
  </tr>
  <tr>
    <td align="center" width="50%"><b>Combustible</b><br><a href="docs/capturas/combustible.png"><img src="docs/capturas/combustible.png" width="440" alt="Combustible"></a></td>
    <td align="center" width="50%"><b>Mantenimiento</b><br><a href="docs/capturas/mantenimiento.png"><img src="docs/capturas/mantenimiento.png" width="440" alt="Mantenimiento"></a></td>
  </tr>
  <tr>
    <td align="center" width="50%"><b>Gastos</b><br><a href="docs/capturas/gastos.png"><img src="docs/capturas/gastos.png" width="440" alt="Gastos"></a></td>
    <td align="center" width="50%"><b>Informes</b><br><a href="docs/capturas/informes.png"><img src="docs/capturas/informes.png" width="440" alt="Informes"></a></td>
  </tr>
  <tr>
    <td align="center" width="50%"><b>Administración</b><br><a href="docs/capturas/admin.png"><img src="docs/capturas/admin.png" width="440" alt="Administración"></a></td>
    <td align="center" width="50%"><b>Acceso</b><br><a href="docs/capturas/login.png"><img src="docs/capturas/login.png" width="440" alt="Acceso"></a></td>
  </tr>
</table>

---

## ¿Qué es KMtracker?

KMtracker es una **aplicación web** que instalas en tu propio ordenador, mini-PC,
Raspberry Pi o NAS. Sirve para llevar el control de tus coches y motos: los
kilómetros que haces, lo que gastas en combustible, en reparaciones y en
mantenimiento.

Tres ideas simples:

- **Tus datos son tuyos.** Viven en tu máquina, en un único archivo. Nada se envía
  a ningún servicio externo.
- **Se usa desde el navegador** del móvil, la tablet o el ordenador. Es una web
  normal, no hace falta instalar nada en tus dispositivos.
- **Opcionalmente**, puedes apuntar cosas desde el móvil con un **bot de Telegram**.

Todo cabe en **una sola imagen Docker**: la app web, la base de datos y, si
quieres, el bot.

---

## ¿Para quién es?

- Para quien tiene **uno o varios vehículos** y quiere saber cuánto gasta de
  verdad.
- Para quien está harto de hojas de cálculo y de perder tickets de gasolinera.
- Para quien quiere **recordatorios** de mantenimiento (cambios de aceite, ITV,
  seguro, impuestos) sin depender de una app de pago en la nube.
- Para quien valora la **privacidad**: aquí no hay cuentas, ni nubes, ni anuncios.

---

## Todo lo que puedes hacer

### 🚗 Vehículos (coches y motos)

- Da de alta **tantos vehículos como quieras**, coches y motos.
- Matrículas **de España y de Portugal** (con validación).
- Ficha por vehículo con modelo, año, motor, bastidor y una **foto** del coche.
- Marca vehículos **de prueba** o **vendidos/dados de baja** (se archivan sin
  borrar su histórico).
- Elige cómo mides los kilómetros:
  - **Cuentakilómetros total** (el odómetro que no se reinicia nunca).
  - **Cuentakilómetros parcial** (cuentakilómetros de viaje que se pone a cero).

### 🛣️ Kilometraje

- Apunta **viajes** (lecturas parciales) o **lecturas del odómetro** (totales).
- El sistema calcula la distancia recorrida de forma automática.
- ¿Te equivocaste al teclear? Puedes **corregir** cualquier lectura y todo se
  recalcula en cadena.
- Histórico completo de todos los kilómetros por vehículo.

### ⛽ Combustible

- Registra **repostajes**: litros, precio por litro, importe, kilómetros y tipo
  (gasolina/diésel).
- Marca si llenaste el **depósito completo** para que el cálculo sea exacto.
- Calcula el **consumo real en L/100 km** de cada vehículo.
- Guarda un **histórico de precios** del combustible.
- Corrige el odómetro de un repostaje si hace falta.

### 💸 Gastos

- Registra cualquier gasto con su **categoría**:
  **seguro · ITV · impuesto · reparación · limpieza · mantenimiento · mejoras ·
  otro**.
- Añade **fotos de las facturas** para tenerlo todo justificado.
- Notas libres por gasto.
- Se totaliza por vehículo y por periodo.

### 🛠️ Mantenimiento

- Crea **tareas de mantenimiento por kilómetros** (por ejemplo, "aceite cada
  10.000 km").
- La app te avisa cuando una tarea está **próxima** o **vencida**.
- Registra cada **servicio realizado** con su coste, kilómetros y fotos.
- Genera **tickets imprimibles en formato térmico (58 mm)** para usar con una
  impresora de recibos.
- Genera un **PDF** con el resumen de mantenimiento de cada vehículo.

### 📄 Documentos

- Guarda la **documentación de cada vehículo** (permiso de circulación, ficha
  técnica, seguros, contratos, etc.) directamente dentro de la base de datos.
- Descárgala cuando la necesites.

### 📊 Panel e informes

- **Panel de inicio** con tarjetas por vehículo: km del mes, consumo, gasto del
  mes, gasto anual, gasto total y €/km.
- **Elige qué widgets ver** en el panel (tú decides qué tarjetas aparecen).
- **Gráficas** de gasto mensual con [Chart.js](https://www.chartjs.org/).
- **Informes** por rango de meses y por vehículo, con exportación a **CSV**
  (se abre directamente en Excel).
- **Informe diario** de movimientos.
- **Ticket de informe** para imprimir.

### 🔔 Avisos automáticos

- **Alertas de mantenimiento** por kilómetros.
- **Alertas de renovación**: seguro, ITV e impuesto de circulación, con los días
  de antelación que tú configures.

### 🤖 Bot de Telegram (opcional)

Apunta cosas desde el móvil sin abrir el navegador. Ver
[Bot de Telegram](#bot-de-telegram-opcional).

### 🔐 Acceso y seguridad

- **Login con una sola contraseña** (tú la eliges al instalar).
- Protección **CSRF** en todos los formularios.
- **Límite de intentos** de inicio de sesión para evitar ataques de fuerza bruta.
- Cabeceras de seguridad (no-sniff, no-frame).

### 💾 Copias de seguridad

- Copias **locales rotativas** (se crean y se purgan solas según antigüedad), sin
  depender de ningún servicio externo.
- Crea, lista, **descarga, restaura y borra** copias desde el panel de
  administración.
- Descarga o sube el archivo de base de datos `.db` completo.

---

## Cómo se usa en el día a día

1. **Da de alta tu vehículo.** Menú **Coches → Añadir**. Pon matrícula, modelo,
   año, y elige si mides los km en modo total o parcial.
2. **Apunta tus repostajes.** Menú **Combustible**. Con el depósito lleno, la app
   calcula el consumo real por ti.
3. **Registra tus gastos** (seguro, ITV, taller...) con su categoría y, si
   quieres, una foto del ticket.
4. **Crea tus tareas de mantenimiento** con su intervalo en km. La app te irá
   avisando.
5. **Mira el panel** cada mes para ver cuánto has gastado y cuánto consumes.
6. **Saca un informe** en CSV o PDF cuando lo necesites (por ejemplo, para la
   declaración o para vender el coche con todo el histórico).

---

## Instalación con Docker (5 minutos)

Requisitos: **Docker** y **Docker Compose** instalados.

```bash
git clone https://github.com/Robertomola18/kmtracker.git
cd kmtracker
cp .env.example .env          # edita .env y define KMTRACKER_PASSWORD
docker compose up -d --build
```

Abre en el navegador:

```
http://localhost:5050
```

Y entra con la contraseña que pusiste en `KMTRACKER_PASSWORD`.

Los datos se guardan en el volumen `kmtracker_data` (carpeta `/data` dentro del
contenedor), así que **sobreviven a las actualizaciones**.

¿Quieres probarlo con **datos de ejemplo** (coches, repostajes y gastos de
mentira)?

```bash
docker compose exec kmtracker python3 /app/seed.py
```

> **Recomendación de seguridad:** pon KMtracker detrás de un proxy inverso con
> HTTPS (Caddy, nginx, Traefik) o de una VPN como Tailscale/WireGuard, y expón el
> puerto 5050 **solo en tu red local**. No lo publiques directamente en Internet.

### Windows 10/11 (Docker Desktop)

KMtracker también se puede ejecutar en Windows 10/11 mediante **Docker Desktop
con WSL2 y contenedores Linux**. No hace falta instalar Python, Pango ni
WeasyPrint en Windows: todo va dentro de la imagen.

Requisitos: Windows 10/11 de 64 bits, virtualización activada y Docker Desktop
con el backend WSL2 usando contenedores Linux.

1. Instala Docker Desktop y asegúrate de que usa **contenedores Linux**.
2. Clona el repositorio y entra en la carpeta:

   ```powershell
   git clone https://github.com/Robertomola18/kmtracker.git
   cd kmtracker
   ```

3. Crea `.env`, define una contraseña fuerte y guarda el archivo en UTF-8 sin
   BOM:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

4. Arranca la aplicación:

   ```powershell
   docker compose up -d --build
   ```

5. Abre <http://localhost:5050> e inicia sesión con la contraseña configurada.

Para parar: `docker compose stop`. Para actualizar: `git pull --ff-only` y
`docker compose up -d --build`. Los datos de los volúmenes se conservan.

> **Windows:** el puerto se publica por defecto en todas las interfaces. Si solo
> lo usas en este PC, consulta cómo restringirlo a `127.0.0.1` en la guía.

Guía completa (Docker Desktop, WSL2, acceso desde móvil, bot, copias de
seguridad, actualización y solución de problemas):
[windows/README.es.md](windows/README.es.md).

---

## Configuración

Toda la configuración se hace con variables de entorno en el archivo `.env`:

| Variable | Por defecto | Qué hace |
|---|---|---|
| `KMTRACKER_PASSWORD` | — | Contraseña del acceso web. **Obligatoria** la primera vez. |
| `KMTRACKER_DB_PATH` | `/data/kmtracker.db` | Ruta del archivo de base de datos SQLite. |
| `KMTRACKER_SECRET_KEY` | se genera en `/data/.secret_key` | Clave para las sesiones de Flask. |
| `TZ` | `Europe/Madrid` | Zona horaria. |
| `KM_BACKUP_DIR` | carpeta de la BD + `/backups` | Carpeta donde se guardan las copias. |
| `KM_BACKUP_KEEP_COUNT` | `10` | Nº de copias que se conservan siempre. |
| `KM_BACKUP_KEEP_DAYS` | `30` | Las copias más antiguas que esto se borran. |
| `TELEGRAM_TOKEN` | — | Token del bot de Telegram (también se pone en `/admin`). |
| `TELEGRAM_ALLOWED_USER_IDS` | — | IDs de Telegram autorizados, separados por comas (recomendado). |

Desde la web, en **Ajustes** puedes configurar los widgets del panel y los
umbrales de las alertas (km para avisos y días de antelación de renovaciones). En
**/admin** puedes configurar el bot y gestionar las copias.

---

## Bot de Telegram (opcional)

Con el bot puedes apuntar kilómetros, repostajes, gastos y mantenimiento desde el
móvil, y pedir el resumen de un coche.

**Puesta en marcha:**

1. Habla con [@BotFather](https://t.me/BotFather) en Telegram, crea un bot y copia
   el **token**.
2. Averigua tu **ID numérico** de Telegram (por ejemplo, con [@userinfobot](https://t.me/userinfobot)).
3. Ponlo en tu `.env`:

   ```env
   TELEGRAM_TOKEN=123456:ABC-DEF...
   TELEGRAM_ALLOWED_USER_IDS=111111111
   ```

4. Arranca también el bot:

   ```bash
   docker compose --profile bot up -d
   ```

También puedes configurar el token y la lista blanca desde la web, en `/admin`
(se guardan en la base de datos).

**Comandos disponibles:**

| Comando | Para qué sirve |
|---|---|
| `/start` | Bienvenida y lista de comandos. |
| `/menu` | Menú con botones. |
| `/km` | Registrar un viaje. |
| `/repostar` | Registrar un repostaje. |
| `/gasto` | Registrar un gasto. |
| `/mantenimiento` | Gestionar tareas de mantenimiento. |
| `/check` | Resumen de un coche. |
| `/alertas` | Alertas de todos los coches. |
| `/cancel` | Cancelar la operación en curso. |

> **Importantísimo:** configura siempre la **lista blanca**
> (`TELEGRAM_ALLOWED_USER_IDS`). Sin ella, cualquiera que encuentre tu bot puede
> leer y modificar tus datos.

---

## Copias de seguridad

En **/admin** puedes **crear, listar, descargar, restaurar y borrar** copias
locales. Cada copia es un archivo `kmtracker_<fecha>.tar.gz` con la base de datos
dentro. También puedes descargar o subir el archivo `.db` directamente.

Truco: apunta `KM_BACKUP_DIR` a una carpeta de un **NAS montado** o a una carpeta
**sincronizada en la nube**, y tendrás copias fuera del servidor sin esfuerzo.

Ejemplo de copia automática diaria a las 05:00 con cron:

```
0 5 * * * docker compose -f /ruta/kmtracker/docker-compose.yml exec -T kmtracker \
  python3 -c "import backup,os;backup.create_backup(os.environ['KMTRACKER_DB_PATH'])"
```

---

## Preguntas frecuentes

**¿Necesito Internet para usarlo?**
No. Solo lo necesitas para el bot de Telegram (opcional). El resto funciona en tu
red local.

**¿Dónde se guardan mis datos?**
En un único archivo SQLite dentro del volumen `kmtracker_data`. Puedes copiarlo y
llevártelo cuando quieras.

**¿Puedo usarlo con varias personas?**
El acceso es con una contraseña compartida. Está pensado para uso personal o
familiar, no multiusuario con cuentas.

**¿Y si me equivoco al apuntar los kilómetros?**
Puedes editar cualquier lectura. La app recalcula automáticamente las distancias y
consumos afectados.

**¿Funciona en una Raspberry Pi?**
Sí. Está pensado para hardware modesto: Flask + SQLite consumen muy poco.

**¿Cómo lo actualizo?**
```bash
git pull
docker compose up -d --build
```
Tus datos se conservan en el volumen.

---

## Para desarrolladores

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
KMTRACKER_DB_PATH=/tmp/km.db KMTRACKER_PASSWORD=dev pytest -q
```

Estructura básica del proyecto:

- `app.py` — aplicación web Flask (rutas y vistas).
- `models.py` — base de datos SQLite y toda la lógica de datos.
- `bot.py` — bot de Telegram (opcional).
- `backup.py` — creación y rotación de copias de seguridad.
- `templates/` y `static/` — vistas y recursos.
- `tests/` — pruebas automáticas.

---

## Tecnologías

Flask · SQLite (modo WAL) · Jinja2 · Chart.js · WeasyPrint (PDF) ·
python-telegram-bot · gunicorn · Docker.

---

## Contacto

- **Preguntas y sugerencias:** abre un hilo en las
  [Discusiones](https://github.com/Robertomola18/kmtracker/discussions).
- **Errores y peticiones de funciones:** abre una
  [incidencia (issue)](https://github.com/Robertomola18/kmtracker/issues).
- **Problemas de seguridad:** repórtalos de forma **privada** mediante un
  [Security Advisory](https://github.com/Robertomola18/kmtracker/security/advisories/new)
  en lugar de un issue público. Consulta [SECURITY.md](SECURITY.md).

---

## Licencia y autor

Este proyecto se distribuye bajo la licencia **GNU AGPL-3.0**. Consulta el archivo
[LICENSE](LICENSE).

En resumen: puedes usar, estudiar y modificar KMtracker libremente, pero si lo
distribuyes o lo ofreces como servicio, **debes publicar también el código fuente**
de tus cambios. Así se mantiene libre para todos.

<p align="center">
  <img src="docs/firma.png" alt="R. Silva" width="220"><br>
  Creado por <b>Rober Da Silva (DjGuesh)</b> · Rsilva Corp Limited
</p>

<h2 align="center">
  <img src="docs/bandera-espana.png" alt="España" height="48">&nbsp;&nbsp;
  Producto 100% español&nbsp;&nbsp;
  <img src="docs/bandera-bierzo.png" alt="El Bierzo" height="48">
</h2>
