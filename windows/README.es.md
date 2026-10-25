# KMtracker en Windows 10/11

KMtracker se ejecuta en Windows mediante **Docker Desktop con contenedores
Linux**. No hace falta instalar Python, Pango, Cairo ni WeasyPrint en Windows:
todo va dentro de la imagen de la aplicación.

Esta es la forma compatible de ejecutarlo en Windows. Todavía no hay una versión
nativa `.exe`.

- [Requisitos](#requisitos)
- [1. Instalar Docker Desktop](#1-instalar-docker-desktop)
- [2. Obtener el código](#2-obtener-el-código)
- [3. Configurar `.env`](#3-configurar-env)
- [4. Arrancar KMtracker](#4-arrancar-kmtracker)
- [5. Parar, arrancar y actualizar](#5-parar-arrancar-y-actualizar)
- [6. Copias de seguridad](#6-copias-de-seguridad)
- [7. Bot de Telegram (opcional)](#7-bot-de-telegram-opcional)
- [8. Acceso desde otros dispositivos](#8-acceso-desde-otros-dispositivos)
- [9. Datos y volúmenes](#9-datos-y-volúmenes)
- [10. Solución de problemas](#10-solución-de-problemas)
- [11. Desinstalar](#11-desinstalar)

## Requisitos

- Windows 10/11 de 64 bits (Home o Pro), actualizado.
- Virtualización activada en la BIOS/UEFI.
- Permisos de administrador para instalar Docker Desktop y WSL2.
- **Docker Desktop** con el backend WSL2, usando **contenedores Linux**.
- Conexión a Internet para construir la imagen la primera vez.
- Git para Windows, o el repositorio descargado como ZIP.

Docker Desktop es gratuito para uso personal. Incluye Docker Compose v2, así que
usa `docker compose` (con espacio), no el antiguo `docker-compose`.

## 1. Instalar Docker Desktop

1. Instala Docker Desktop desde la web oficial:
   <https://www.docker.com/products/docker-desktop/>
2. Durante la instalación, deja activado el backend **WSL 2**. Si WSL2 no está
   instalado, ejecuta lo siguiente en un PowerShell de administrador y reinicia:

   ```powershell
   wsl --install
   ```

3. Arranca Docker Desktop y espera a que indique que el motor está funcionando.
4. Asegúrate de que Docker Desktop usa **contenedores Linux**. Si el menú de la
   bandeja ofrece “Switch to Linux containers”, elige esa opción.
5. Abre una ventana nueva de PowerShell y comprueba:

   ```powershell
   docker version
   docker compose version
   docker info --format '{{.OSType}}'
   ```

   El último comando debe mostrar `linux`. Si muestra `windows`, vuelve a cambiar
   Docker Desktop a contenedores Linux.

Si `docker` no se reconoce, cierra y vuelve a abrir PowerShell. Si sigue
fallando, repara o reinstala Docker Desktop.

## 2. Obtener el código

```powershell
git clone https://github.com/Robertomola18/kmtracker.git
cd kmtracker
```

Si no tienes Git, descarga el ZIP desde GitHub, extráelo y abre una ventana de
PowerShell dentro de la carpeta extraída. Todos los comandos siguientes deben
ejecutarse desde la carpeta que contiene `docker-compose.yml`.

El repositorio incluye un archivo `.gitattributes` que mantiene `entrypoint.sh`
en formato LF, así que un clonado normal en Windows funciona correctamente.

## 3. Configurar `.env`

Crea tu archivo de configuración local:

```powershell
Copy-Item .env.example .env
notepad .env
```

Define un valor fuerte para `KMTRACKER_PASSWORD`. No dejes el valor de ejemplo
`cambia-esta-contrasena`. El archivo `.env` está ignorado por Git y no se debe
subir al repositorio.

Configuración recomendada:

```dotenv
KMTRACKER_PASSWORD='una contraseña larga y única'
TZ=Europe/Madrid
```

Notas:

- Guarda `.env` en **UTF-8 sin BOM**. Un BOM puede hacer que Docker Compose
  ignore la primera variable.
- Si la contraseña contiene `#`, `$`, comillas dobles o espacios, ponla entre
  comillas simples como en el ejemplo. Si contiene una comilla simple, usa la
  variable de entorno de PowerShell que se explica abajo solo para el primer
  arranque.
- La contraseña solo se usa para crear el hash en el **primer arranque**.
  Cambiar `KMTRACKER_PASSWORD` después no cambia la contraseña existente.
- Para no guardar la contraseña en `.env`, pásala solo durante el primer
  arranque:

  ```powershell
  $env:KMTRACKER_PASSWORD = "una contraseña larga y única"
  docker compose up -d --build
  Remove-Item Env:\KMTRACKER_PASSWORD
  ```

  Después del primer arranque, el hash queda guardado en el volumen de datos.

## 4. Arrancar KMtracker

Desde la carpeta del repositorio:

```powershell
docker compose up -d --build
docker compose ps
```

La primera construcción puede tardar varios minutos. Abre:

<http://localhost:5050>

Entra con la contraseña que hayas configurado. Para seguir los logs:

```powershell
docker compose logs -f kmtracker
```

Si el contenedor se reinicia en bucle en vez de quedarse arrancado, consulta
[Solución de problemas](#10-solución-de-problemas).

Datos de ejemplo opcionales (coches, repostajes y gastos falsos):

```powershell
docker compose exec kmtracker python3 /app/seed.py
```

No cargues datos de ejemplo en una base de datos que ya tenga tus datos reales.

## 5. Parar, arrancar y actualizar

Para parar la aplicación sin borrar datos:

```powershell
docker compose stop
```

Para volver a arrancarla:

```powershell
docker compose start
```

Para actualizar KMtracker, haz primero una copia de seguridad y después:

```powershell
git pull --ff-only
docker compose up -d --build
```

La base de datos y los archivos subidos están en volúmenes con nombre, así que
sobreviven a las reconstrucciones. Si `git pull` avisa de cambios locales,
haz commit o guárdalos antes de actualizar. No ejecutes `git reset --hard` si
tienes trabajo que quieres conservar.

## 6. Copias de seguridad

La opción más sencilla es la interfaz web:

1. Abre `/admin`.
2. Crea una copia y descárgala.
3. Restaura una copia desde la misma página.

Las copias se guardan en `/data/backups`, dentro del volumen `kmtracker_data`.
Para copiar una copia a Windows:

```powershell
docker cp kmtracker:/data/backups/<nombre-de-la-copia>.tar.gz .
```

Guarda una copia exportada fuera de Docker. Una copia que solo existe en el mismo
volumen se pierde si ese volumen se borra.

No copies `kmtracker.db` con la aplicación en marcha; SQLite puede estar en medio
de una escritura. Usa `/admin` o el comando de copia seguro de SQLite. Para una
restauración manual, para el contenedor primero.

## 7. Bot de Telegram (opcional)

Arranca primero la aplicación web y después el bot:

```powershell
docker compose --profile bot up -d
```

Configura el token en `.env` (`TELEGRAM_TOKEN`) o en `/admin`. Define
`TELEGRAM_ALLOWED_USER_IDS` (o el ajuste equivalente en `/admin`); si no,
cualquiera que encuentre el bot podrá usarlo.

Si cambias el token en `/admin`, reinicia el bot:

```powershell
docker compose --profile bot restart bot
```

El bot solo hace conexiones salientes a Telegram; no hay que abrir ningún puerto
de entrada para él.

## 8. Acceso desde otros dispositivos

Por defecto, `docker-compose.yml` publica el puerto 5050 en todas las
interfaces. Eso significa que otros dispositivos de tu red podrían acceder.

Para que solo esté disponible en **este PC**, edita `docker-compose.yml` y
cambia:

```yaml
ports:
  - "5050:5050"
```

por:

```yaml
ports:
  - "127.0.0.1:5050:5050"
```

Para acceder desde un móvil o tablet en la misma Wi-Fi, deja el puerto publicado,
permite Docker Desktop en **redes privadas** en el firewall de Windows y abre
`http://<ip-de-tu-pc>:5050`.

Para acceso remoto, usa una VPN como Tailscale o WireGuard, o pon KMtracker
detrás de un proxy inverso con HTTPS. No abras el puerto 5050 en el router ni lo
expongas directamente a Internet.

## 9. Datos y volúmenes

KMtracker usa dos volúmenes con nombre:

- `kmtracker_data`: base de datos SQLite, clave secreta y copias locales.
- `kmtracker_uploads`: archivos subidos.

Compose añade el nombre del proyecto al principio del volumen, que normalmente
sale del nombre de la carpeta. Si renombras o mueves la carpeta del proyecto,
Docker puede crear volúmenes nuevos y vacíos. Mantén el nombre de la carpeta o
exporta una copia antes de moverla.

No sustituyas `/data` por un bind mount a una carpeta de Windows como `C:\...`.
SQLite y el bloqueo WAL no son fiables en bind mounts NTFS. Mantén los volúmenes
con nombre y usa las herramientas de copia.

- `docker compose down` para y elimina los contenedores, pero conserva los
  volúmenes.
- `docker compose down -v` también elimina los volúmenes y todos los datos de
  KMtracker. Es irreversible.
- Resetear Docker Desktop, desinstalarlo o borrar sus datos de WSL2 también puede
  eliminar volúmenes. Exporta copias con regularidad.

## 10. Solución de problemas

| Problema | Solución |
| --- | --- |
| No se reconoce `docker` | Instala/arranca Docker Desktop y abre una ventana nueva de PowerShell. |
| `Cannot connect to the Docker daemon` | Arranca Docker Desktop y espera al motor. Comprueba con `docker info`. |
| `docker info` muestra `OSType: windows` | Haz clic derecho en el icono de Docker Desktop y cambia a contenedores Linux. |
| No se reconoce `docker compose` | Actualiza Docker Desktop. Usa `docker compose`, no `docker-compose`. |
| `entrypoint.sh: bad interpreter` o `$'\r'` | El archivo tiene finales CRLF. Actualiza el repositorio, ejecuta `git checkout -- entrypoint.sh` y reconstruye con `docker compose up -d --build`. El Dockerfile también normaliza el archivo durante la construcción. |
| `KMTRACKER_PASSWORD no definida` | Define `KMTRACKER_PASSWORD` en `.env` y ejecuta `docker compose up -d --force-recreate`. Revisa `docker compose logs kmtracker`. |
| El contenedor se reinicia en bucle | Ejecuta `docker compose logs kmtracker`. Las causas habituales son falta de contraseña, conflicto de puerto o un fallo de construcción. |
| `port is already allocated` | Busca el proceso con `Get-NetTCPConnection -LocalPort 5050`, o cambia el puerto host a `5051:5050` y abre `http://localhost:5051`. |
| El nombre de contenedor `kmtracker` ya está en uso | Ejecuta `docker ps -a --filter "name=kmtracker"`. Para la instancia antigua con `docker compose down` en su carpeta, o elimina el contenedor antiguo. Usa una sola instancia. |
| `git pull` falla por cambios locales | Ejecuta `git status`. Haz commit o guarda los cambios. No uses `git reset --hard` si quieres conservarlos. |
| Errores de WSL2 o Docker Desktop no arranca | Ejecuta `wsl --update`, después `wsl --shutdown`, y vuelve a arrancar Docker Desktop. Comprueba que la virtualización está activada en la BIOS/UEFI. |
| No puedo entrar después de cambiar `.env` | El hash de la contraseña se creó en el primer arranque. Cambiar la variable de entorno no lo actualiza. Usa [Resetear una contraseña olvidada](#resetear-una-contraseña-olvidada); en esta versión no hay pantalla para cambiarla. |
| No queda espacio en disco | Libera espacio en Docker Desktop o mueve su imagen de disco a otra unidad. No borres volúmenes sin una copia. |

### Resetear una contraseña olvidada

Cambiar `KMTRACKER_PASSWORD` en `.env` no actualiza el hash de una contraseña ya
existente. Si aún puedes entrar, haz primero una copia de seguridad. Escribe la
nueva contraseña en `.env` y arranca el contenedor si está parado
(`docker compose up -d`); después ejecuta estos comandos:

```powershell
docker compose exec kmtracker python3 -c "from models import get_db; conn = get_db(); conn.execute('DELETE FROM settings WHERE key = ?', ('password_hash',)); conn.commit(); conn.close()"
docker compose up -d --force-recreate
```

El primer comando borra el hash guardado. El segundo recrea el contenedor para
que el entrypoint cree un hash nuevo a partir de `KMTRACKER_PASSWORD`. Esto no
borra tus vehículos, gastos ni el resto de datos.

## 11. Desinstalar

Para la aplicación:

```powershell
docker compose down
```

Esto conserva los datos. Para eliminar los contenedores **y todos los volúmenes
de datos**:

```powershell
docker compose down -v
```

El segundo comando es irreversible. Exporta una copia antes si puedes necesitar
los datos más adelante.

Después puedes borrar la carpeta del repositorio y desinstalar Docker Desktop si
ya no lo necesitas. Haz una copia de los volúmenes antes de desinstalar Docker
Desktop o resetear sus datos.

## Notas de seguridad

- Usa una contraseña larga y única. La interfaz web usa una sola contraseña.
- Mantén el puerto 5050 en localhost o en tu red privada siempre que puedas.
- No expongas KMtracker directamente a Internet sin HTTPS o una VPN.
- Define `TELEGRAM_ALLOWED_USER_IDS` si usas el bot.
- Mantén Docker Desktop y la imagen de KMtracker actualizados.
- No subas `.env` ni copias de seguridad con datos personales al repositorio.

## Limitaciones conocidas

- KMtracker en Windows requiere Docker Desktop; todavía no hay un `.exe` nativo.
- Docker Desktop tiene que estar arrancado para poder usar KMtracker.
- Esta instalación no crea un servicio de Windows ni arranca automáticamente al
  iniciar sesión.
- La contraseña se crea en el primer arranque; cambiar `KMTRACKER_PASSWORD`
  después no actualiza la contraseña existente.
- El compose por defecto publica el puerto 5050 en todas las interfaces. Consulta
  [Acceso desde otros dispositivos](#8-acceso-desde-otros-dispositivos) para
  restringirlo.
