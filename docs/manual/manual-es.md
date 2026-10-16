<p align="center">
  <img src="../../static/logo.png" alt="KMtracker" width="320">
</p>

# Manual de usuario de KMtracker

**Kilometraje, combustible, gastos y mantenimiento para todos tus vehículos, en tu propia casa.**

Esta guía explica, pantalla por pantalla, cómo usar KMtracker. No necesitas
conocimientos técnicos: si sabes usar una web, sabes usar KMtracker. Para
instalarlo, consulta la sección de instalación del [README](../../README.es.md)
o el capítulo [Instalación y configuración](#16-instalación-y-configuración) de
este manual.

> **Idioma:** este manual está también disponible en inglés
> ([`manual-en.md`](manual-en.md)).

---

## Índice

1. [Qué es KMtracker](#1-qué-es-kmtracker)
2. [Primeros pasos](#2-primeros-pasos)
3. [El panel de inicio](#3-el-panel-de-inicio)
4. [Vehículos](#4-vehículos)
5. [Kilometraje](#5-kilometraje)
6. [Combustible](#6-combustible)
7. [Gastos](#7-gastos)
8. [Mantenimiento](#8-mantenimiento)
9. [Documentos](#9-documentos)
10. [Informes](#10-informes)
11. [Historial](#11-historial)
12. [Ajustes](#12-ajustes)
13. [Administración](#13-administración)
14. [El bot de Telegram](#14-el-bot-de-telegram)
15. [Copias de seguridad](#15-copias-de-seguridad)
16. [Instalación y configuración](#16-instalación-y-configuración)
17. [Preguntas frecuentes y problemas](#17-preguntas-frecuentes-y-problemas)

---

## 1. Qué es KMtracker

KMtracker es una **aplicación web** que se ejecuta en tu propio equipo (un
ordenador, un mini-PC, una Raspberry Pi o un NAS). Sirve para llevar el control
de tus coches y motos: los kilómetros que haces, lo que gastas en combustible, en
reparaciones y en mantenimiento.

Tres ideas sencillas:

- **Tus datos son tuyos.** Se guardan en tu máquina, en un único archivo. Nada se
  envía a servicios externos.
- **Se usa desde el navegador** del móvil, la tablet o el ordenador. No hace
  falta instalar nada en tus dispositivos.
- **Opcionalmente**, puedes apuntar cosas desde el móvil con un **bot de
  Telegram**.

Todos los menús de la aplicación están siempre en la barra superior:

**Panel · Registrar · KM · Combustible · Mantenimiento · Coches · Informes ·
Historial · Ajustes · Admin**

---

## 2. Primeros pasos

### Entrar en la aplicación

Abre la dirección de tu KMtracker en el navegador (por ejemplo
`http://localhost:5050`) e introduce la contraseña que se definió al instalar.

![Pantalla de acceso](img/login.png)

- La contraseña es **única** para toda la instalación (no hay usuarios ni
  cuentas). Está pensada para uso personal o familiar.
- Tras varios intentos fallidos, la aplicación bloquea temporalmente nuevos
  intentos para evitar ataques de fuerza bruta.
- Para salir, usa el enlace de **cerrar sesión** de la esquina superior derecha.

### El menú "Registrar"

El botón **Registrar** es un atajo que reúne las cuatro acciones más habituales
del día a día:

![Menú de registro](img/registrar.png)

- **Kilómetros** — apuntar un viaje o una lectura del cuentakilómetros.
- **Combustible** — apuntar un repostaje.
- **Gastos** — apuntar un gasto.
- **Documentos** — añadir un documento.

Cada una de estas opciones también está disponible en su propio menú de la barra
superior.

---

## 3. El panel de inicio

El **Panel** es la pantalla principal y el resumen de toda tu flota. Se abre solo
al entrar.

![Panel de inicio](img/panel.png)

### Tarjetas por vehículo

Cada coche o moto aparece en una tarjeta con sus datos del momento:

- **Total** — kilómetros acumulados del vehículo.
- **Este mes** — kilómetros hechos en el mes actual, comparados con el mes
  anterior.
- **Consumo** — consumo real en **L/100 km**.
- **Gasto mes** — gasto del mes, con el importe del mes anterior como
  referencia.
- **Gasto año** — lo gastado en el año en curso.
- **Gasto total** — todo lo gastado desde que diste de alta el vehículo.
- **Coste total / km** — el coste real por kilómetro.

Si un vehículo tiene avisos activos (mantenimiento próximo, seguro, ITV o
impuesto), aparecen resaltados en la parte baja de su tarjeta.

### Estadísticas globales

Debajo de las tarjetas, el panel muestra gráficas del conjunto de la flota:

- **Uso por coche** — reparto de kilómetros entre vehículos.
- **Gastos: combustible vs mantenimiento** — a qué se va el dinero.

### Gasto mensual (12 meses)

Una gráfica de barras con el gasto de los últimos doce meses, separado por
combustible, gastos y mantenimiento. Puedes filtrar por vehículo y moverte hacia
atrás o hacia delante en el tiempo con los botones **Filtrar**, **← Anterior** y
**Siguiente →**.

### Estadísticas mensuales

El bloque inferior permite elegir un **coche**, un **año** y un **mes** y ver:

- el **gasto por día** de ese mes,
- el **gasto por coche** de ese mes.

> Qué tarjetas y bloques se muestran en el panel se decide en
> [Ajustes](#12-ajustes).

---

## 4. Vehículos

### Dar de alta un vehículo

Entra en **Coches**, donde tienes la lista de vehículos y el formulario para
añadir uno nuevo.

![Lista de vehículos](img/vehiculos.png)

Al añadir un vehículo se piden estos datos:

- **Matrícula** — con validación para matrículas de **España y Portugal**.
- **Modelo** — por ejemplo, "Seat León".
- **Año** — año de matriculación.
- **Modo de kilometraje** — cómo mides los kilómetros:
  - **Total**: usas el odómetro que nunca se reinicia.
  - **Parcial**: usas el cuentakilómetros de viaje que se pone a cero.
- **Kilómetros iniciales** — la lectura con la que empiezas a controlarlo.
- **Foto** (opcional) — una imagen del vehículo.

### La ficha de un vehículo

Pulsa sobre un vehículo para abrir su **ficha**, el centro de operaciones de ese
coche concreto.

![Ficha de vehículo](img/ficha.png)

En la parte superior tienes sus datos, los indicadores resumidos (este mes,
consumo, gasto mes, coste/km, gasto total) y los **avisos** de renovaciones. Los
botones de acción rápida (**KM**, **Gasolina**, **Taller**, **Gasto**, **Docs**,
**PDF**) llevan directamente al formulario correspondiente de ese vehículo.

A continuación se listan sus secciones, cada una con sus propias filas y botones
de **editar** (lápiz) y **borrar** (aspa):

- **Viajes / Kilometraje**
- **Combustible**
- **Mantenimiento** (con las tareas, su próximo vencimiento y su restante)
- **Historial de mantenimiento**
- **Gastos**

### Marcar un vehículo como "de prueba" o "vendido"

Desde la ficha puedes editar el vehículo para marcarlo como **de prueba** o como
**vendido/dado de baja**. Un vehículo archivado **no se borra**: conserva todo su
histórico, simplemente deja de aparecer como activo.

---

## 5. Kilometraje

En **KM** se registran los kilómetros recorridos. Primero se elige el vehículo:

![Selección de vehículo](img/km_seleccion.png)

Y después se rellena el formulario:

![Formulario de kilometraje](img/km_formulario.png)

Según cómo tengas configurado el vehículo:

- **Cuentakilómetros total** — apuntas la **lectura del odómetro** (por ejemplo
  `90600`) y KMtracker calcula la distancia desde la lectura anterior.
- **Cuentakilómetros parcial** — apuntas los **kilómetros del viaje**.

El resultado se calcula de forma automática, no tienes que hacer cuentas.

### Corregir un error

Si te equivocaste al teclear, pulsa el **lápiz** de la fila y corrige el dato.
KMtracker **recalcula en cadena** todas las distancias y consumos afectados. El
histórico completo de kilómetros de cada vehículo está siempre disponible en su
ficha.

---

## 6. Combustible

En **Combustible** se registran los repostajes y se calcula el consumo real.

![Combustible](img/combustible.png)

Para cada repostaje se guarda:

- **Litros** repostados.
- **Precio por litro** y **total** (el importe).
- **Kilómetros** — la lectura del cuentakilómetros en ese momento.
- **Tipo** — gasolina o diésel.
- **Depósito lleno** — marca esta casilla cuando llenas el depósito por completo.

> **Truco:** para que el cálculo del consumo sea exacto, marca **"depósito
> lleno"** solo cuando realmente lo hayas llenado. Entre dos llenados completos,
> la diferencia de kilómetros y los litros repostados dan el consumo real en
> **L/100 km**.

### Historial de precios

El enlace **Precios** abre un histórico de precios del combustible, útil para ver
cómo ha evolucionado el precio a lo largo del tiempo.

![Historial de precios](img/combustible_precios.png)

Si hace falta, puedes **editar** un repostaje para corregir el odómetro o
cualquier otro dato.

---

## 7. Gastos

En la ficha del vehículo, la sección **Gastos** recoge todo lo que no es
combustible ni mantenimiento.

![Gastos](img/gastos.png)

Cada gasto tiene:

- **Fecha**
- **Concepto** — descripción libre (por ejemplo, "Seguro anual").
- **Categoría** — una de estas:
  **seguro · ITV · impuesto · reparación · limpieza · mantenimiento · mejoras ·
  otro**.
- **Coste**
- **Factura** (opcional) — una **foto** del ticket o factura.
- **Nota** (opcional)

Los gastos se totalizan por vehículo y por periodo, y se tienen en cuenta en
todas las estadísticas del panel y de los informes.

---

## 8. Mantenimiento

KMtracker distingue entre **tareas** (lo que hay que hacer cada cierto número de
kilómetros) y **servicios realizados** (lo que ya has hecho).

### Las tareas de mantenimiento

En **Mantenimiento** gestionas la lista de tareas de control y sus intervalos en
kilómetros.

![Mantenimiento](img/mantenimiento.png)

- Cada tarea tiene un **intervalo** (por ejemplo, "aceite cada 15.000 km").
- La aplicación muestra cuántos kilómetros faltan (**restante**) para cada tarea
  y te avisa cuando está **próxima** o **vencida**.

### Registrar un servicio realizado

Para apuntar un mantenimiento hecho, entra en el vehículo y pulsa **Nuevo** en la
sección de mantenimiento.

![Registrar mantenimiento](img/mantenimiento_form.png)

Se registra:

- La **fecha** y los **kilómetros** a los que se hizo.
- El **coste** y una **nota**.
- Las **tareas** que se han cubierto (marcándolas de la lista), para que se
  reinicie su cuenta atrás.
- Opcionalmente, **fotos**.

### Ticket térmico (58 mm)

Cada servicio realizado se puede imprimir como **ticket térmico de 58 mm**, ideal
para una impresora de recibos. La página del ticket también permite guardarlo como
**PNG**.

![Ticket de mantenimiento](img/ticket58.png)

También puedes generar un **PDF** con el resumen de mantenimiento de cada vehículo
desde su ficha (botón **PDF**).

---

## 9. Documentos

En la sección **Docs** de la ficha de cada vehículo puedes guardar su
documentación: permiso de circulación, ficha técnica, pólizas de seguro,
contratos, etc.

![Documentos](img/documentos.png)

Los documentos se guardan **dentro de la base de datos**, así que viajan siempre
con tus copias de seguridad. Puedes **descargarlos** cuando los necesites.

---

## 10. Informes

En **Informes** obtienes resúmenes por rango de meses y por vehículo.

![Informes](img/informes.png)

- Elige el **rango de meses** y, si quieres, un **vehículo** concreto (o todos).
- Se muestra el total de kilómetros, combustible, gastos y mantenimiento del
  periodo.
- Puedes **exportar a CSV**, un formato que se abre directamente en Excel o en
  cualquier hoja de cálculo.
- Hay un **informe diario** de movimientos y un **ticket de informe** listo para
  imprimir.

![Ticket de informe](img/informe_ticket.png)

El CSV también está disponible desde la ficha de cada vehículo, para exportar solo
sus datos.

---

## 11. Historial

En **Historial** tienes el registro cronológico de la actividad.

![Historial](img/historial.png)

Es la vista más cómoda para revisar "qué ha pasado" en un vehículo o en toda la
flota: lecturas de kilómetros, repostajes y demás movimientos, en orden.

---

## 12. Ajustes

En **Ajustes** personalizas el panel y los avisos.

![Ajustes](img/ajustes.png)

### Widgets del panel

Marca o desmarca las estadísticas que quieres ver en las tarjetas del panel:

- Km total · Km este mes · Consumo L/100 km · Gasto combustible del mes · Gasto
  total del año · Coste total €/km · Gasto total acumulado · Alertas de
  mantenimiento · Alertas seguro / ITV / impuesto.

### Umbrales de alertas

- **Km para alerta ROJA** de mantenimiento (por defecto, 500 km): cuando a una
  tarea le quedan menos de esos kilómetros, se marca en rojo.
- **Km para alerta AMARILLA** de mantenimiento (por defecto, 3.000 km): aviso
  previo.
- **Días antes de renovación** (por defecto, 45): con cuánta antelación quieres
  que te avise de las renovaciones de **seguro, ITV e impuesto**.

---

## 13. Administración

En **Admin** se configura el bot y se gestionan las copias de seguridad.

![Administración](img/admin.png)

- **Bot de Telegram** — el token del bot y la lista de IDs autorizados (ver el
  apartado siguiente).
- **Copias de seguridad** — crear una copia ahora, listar las existentes,
  descargarlas, **restaurarlas** o borrarlas, y descargar/subir el archivo de base
  de datos directamente.

> Estas funciones son sensibles. Protege bien la contraseña de acceso.

---

## 14. El bot de Telegram

El **bot de Telegram** es opcional y sirve para apuntar cosas desde el móvil sin
abrir el navegador.

### Puesta en marcha

1. Habla con [@BotFather](https://t.me/BotFather) en Telegram, crea un bot y copia
   el **token** que te da.
2. Averigua tu **ID numérico** de Telegram (por ejemplo, con
   [@userinfobot](https://t.me/userinfobot)).
3. Introduce el token y tu ID en la sección **Admin** de KMtracker (o en el
   archivo `.env`, ver [Instalación y configuración](#16-instalación-y-configuración)).
4. Reinicia el bot para aplicar los cambios.

> **Importantísimo:** configura siempre la **lista blanca** de IDs autorizados.
> Sin ella, cualquiera que encuentre tu bot podría leer y modificar tus datos.

### Comandos disponibles

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

---

## 15. Copias de seguridad

Tus datos viven en un único archivo (la base de datos SQLite). Hacer copias es
por tanto muy sencillo.

Desde **Admin** puedes:

- **Crear una copia ahora** (se guarda como `kmtracker_<fecha>.tar.gz`).
- **Listar**, **descargar**, **restaurar** y **borrar** las copias existentes.
- **Descargar** o **subir** directamente el archivo de base de datos `.db`.

Las copias se crean y se **purgar solas** según antigüedad, con dos ajustes:

- `KM_BACKUP_KEEP_COUNT` — cuántas copias se conservan siempre (por defecto 10).
- `KM_BACKUP_KEEP_DAYS` — se borran las más antiguas que estos días (por defecto
  30).

> **Truco:** apunta la carpeta de copias (`KM_BACKUP_DIR`) a un **NAS montado** o
> a una carpeta **sincronizada en la nube**, y tendrás copias fuera del servidor
> sin hacer nada más.

---

## 16. Instalación y configuración

KMtracker se puede ejecutar de dos formas:

### Con Docker (recomendado)

Requisitos: **Docker** y **Docker Compose**.

```bash
git clone https://github.com/Robertomola18/kmtracker.git
cd kmtracker
cp .env.example .env          # edita .env y define KMTRACKER_PASSWORD
docker compose up -d --build
```

Abre `http://localhost:5050` y entra con la contraseña que pusiste.

### Sin Docker (Python)

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
KMTRACKER_DB_PATH=./kmtracker.db KMTRACKER_PASSWORD=tu-contrasena \
  python3 app.py
```

### Variables de configuración (`.env`)

| Variable | Por defecto | Qué hace |
|---|---|---|
| `KMTRACKER_PASSWORD` | — | Contraseña del acceso web. **Obligatoria** la primera vez. |
| `KMTRACKER_DB_PATH` | `/data/kmtracker.db` | Ruta del archivo de base de datos SQLite. |
| `KMTRACKER_SECRET_KEY` | se genera en `/data/.secret_key` | Clave para las sesiones de Flask. |
| `TZ` | `Europe/Madrid` | Zona horaria. |
| `KM_BACKUP_DIR` | carpeta de la BD + `/backups` | Carpeta donde se guardan las copias. |
| `KM_BACKUP_KEEP_COUNT` | `10` | Nº de copias que se conservan siempre. |
| `KM_BACKUP_KEEP_DAYS` | `30` | Días de antigüedad máxima de las copias. |
| `TELEGRAM_TOKEN` | — | Token del bot de Telegram (también en **Admin**). |
| `TELEGRAM_ALLOWED_USER_IDS` | — | IDs de Telegram autorizados, separados por comas. |

### Datos de ejemplo (opcional)

¿Quieres probar la aplicación con datos ficticios?

```bash
docker compose exec kmtracker python3 /app/seed.py
```

### Actualizar

```bash
git pull
docker compose up -d --build
```

Tus datos se conservan en el volumen `kmtracker_data`.

> **Recomendación de seguridad:** no expongas KMtracker directamente a Internet.
> Ponlo detrás de un proxy inverso con **HTTPS** (Caddy, nginx, Traefik) o de una
> **VPN** como Tailscale o WireGuard, y publica el puerto **solo en tu red local**.

---

## 17. Preguntas frecuentes y problemas

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
Puedes editar cualquier lectura (icono del lápiz). KMtracker recalcula
automáticamente las distancias y consumos afectados.

**¿Funciona en una Raspberry Pi?**
Sí. Está pensado para hardware modesto: Flask + SQLite consumen muy poco.

**He olvidado la contraseña.**
Se cambia definiendo de nuevo `KMTRACKER_PASSWORD` en el archivo `.env` (o
variable de entorno) y reiniciando la aplicación.

**El bot de Telegram no responde.**
Comprueba que el token es correcto, que el bot está arrancado y que tu ID de
Telegram está en la lista blanca. Reinicia el bot tras cambiar la configuración.

**¿Cómo reporto un error o pido una función?**
Abre una [incidencia en GitHub](https://github.com/Robertomola18/kmtracker/issues).
Para problemas de **seguridad**, usa un
[Security Advisory](https://github.com/Robertomola18/kmtracker/security/advisories/new)
privado.

---

## Contacto y licencia

- **Preguntas y sugerencias:** [Discusiones de GitHub](https://github.com/Robertomola18/kmtracker/discussions).
- **Errores y funciones:** [incidencias](https://github.com/Robertomola18/kmtracker/issues).

Este proyecto se distribuye bajo la licencia **GNU AGPL-3.0** (consulta
[LICENSE](../../LICENSE)).

<p align="center">
  <img src="../firma.png" alt="R. Silva" width="200"><br>
  Creado por <b>Rober Da Silva (DjGuesh)</b> · Rsilva Corp Limited
</p>
