# Elaris

Elaris es el espacio de gestión para profesionales de la belleza. La marca es siempre Elaris: cada profesional crea su cuenta, usa el nombre de su negocio como etiqueta interna y elige sus rubros y servicios. No hay página pública ni personalización visual por negocio.

## Estado actual

El MVP está implementado de punta a punta: cuenta, onboarding, servicios, clientes, horarios, agenda de turnos, estados, disponibilidad, recordatorios manuales, cobros y resumen de ingresos. La app funciona con SQLite para desarrollo local y con PostgreSQL en producción. En Vercel se usa Neon como base PostgreSQL porque el sistema de archivos serverless es de solo lectura.

## Funcionalidades

### Cuenta y onboarding

- Registro e inicio de sesión con email y contraseña.
- Recuperación de contraseña con un link por email, válido 24 horas y de un solo uso.
- Una cuenta equivale a una profesional y a un negocio.
- Onboarding con nombre del negocio, rubros (Uñas, Pestañas y Cejas) y selección de servicios iniciales.
- Catálogo de 21 servicios precargados con duraciones estimadas y precios vacíos.
- Aislamiento de datos: todas las consultas del panel se filtran por el negocio de la profesional autenticada.

### Servicios

- Alta, edición, archivado y reactivación de servicios.
- Cada servicio pertenece a uno de los rubros del negocio.
- Duración editable y precio opcional.
- El servicio archivado deja de ofrecerse en turnos nuevos, pero conserva su historial.

### Clientes

- Alta, edición, búsqueda, archivado y reactivación.
- Ficha con teléfono, email, notas, próximos turnos e historial.
- Los turnos y los clientes archivados no se borran.

### Horarios y disponibilidad

- Bloques de atención por día de la semana, con varios bloques por día.
- Los espacios entre bloques funcionan como descansos.
- Días libres por rango de fechas, con motivo opcional.
- Horario sugerido para empezar rápido.
- Disponibilidad calculada en pasos de 15 minutos, respetando duración del servicio, bloques, descansos, días libres y turnos existentes.

### Turnos y agenda

- Alta y edición de turnos con un cliente y un servicio por turno.
- Validación de que el turno entre completo en un bloque y no se superponga con otro.
- Snapshot de nombre de servicio, duración y precio al crear el turno.
- Estados: programado, completado, cancelado y no asistió.
- Acciones para completar, cancelar, marcar ausencia y reabrir turnos cancelados o con ausencia.
- Vista semanal y vista diaria con accesos a la ficha del turno.
- Panel de disponibilidad con actualización por HTMX, sin recargar la página.
- Recordatorio manual: Elaris arma el mensaje y lo copia para enviarlo por WhatsApp. No hay integración con la API de WhatsApp.
- Página de recordatorios con los turnos del día siguiente, cantidad pendiente y recordada, envío por WhatsApp y marca de “recordado”.
- El WhatsApp del negocio se agrega al final del mensaje para que el cliente pueda responder.

### Cobros

- Registro del monto cobrado y del medio de pago por turno.
- Estados de cobro: sin registrar, pendiente, seña y pagado.
- Se puede registrar una seña o el total, y borrar el cobro dejando el monto vacío.
- El monto no puede superar el precio del turno.
- El cobro es independiente del ingreso facturado: el resumen de ingresos sigue calculándose por el precio de los turnos completados.

### Panel e ingresos

- Panel con turnos del día, próximos turnos, clientes activos, ingresos del mes, servicios y checklist de puesta en marcha.
- Aviso de recordatorios de mañana con acceso a la página de recordatorios.
- Resumen mensual de ingresos, cobrado, pendiente de cobro, ticket promedio, turnos cancelados, ausencias y detalle por rubro y servicio.
- Solo los turnos completados con precio suman ingresos.
- Los turnos cancelados o marcados como “no asistió” no suman.

## Stack

- Python 3.13
- Django 5.2 LTS
- PostgreSQL en producción, SQLite como fallback local
- Vercel como hosting y Neon como PostgreSQL administrado en producción
- Tailwind CSS 4
- HTMX
- Gunicorn y WhiteNoise para producción

## Desarrollo local

### 1. Dependencias de Python

El proyecto usa `uv` para manejar el entorno. Si no lo tenés:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Crear el entorno e instalar dependencias:

```bash
~/.local/bin/uv venv --python 3.13 .venv
~/.local/bin/uv pip install --python .venv/bin/python -r requirements-dev.txt
```

### 2. Variables de entorno

```bash
cp .env.example .env
```

Para desarrollo alcanza con los valores por defecto. Si no configurás `DATABASE_URL`, se usa SQLite.

### 3. Base de datos

```bash
.venv/bin/python manage.py migrate
```

El catálogo se carga automáticamente con la migración `catalog.0002_seed_catalog`.

Para entrar al admin:

```bash
.venv/bin/python manage.py createsuperuser
```

### 4. Frontend

```bash
npm install
npm run css:build
```

Para desarrollar con recarga de estilos:

```bash
npm run css:watch
```

Si cambiás clases de Tailwind en templates o JS, volvé a correr `npm run css:build` antes de cerrar el cambio.

### 5. Correr la app

```bash
.venv/bin/python manage.py runserver 0.0.0.0:8000
```

Abrí `http://localhost:8000/`. Si estás en Windows con WSL y `localhost` no resuelve, probá con la IP de WSL, por ejemplo `http://192.168.226.254:8000/` (la IP puede cambiar). En desarrollo, `DEBUG=1` permite ese acceso; en producción configurá `DJANGO_ALLOWED_HOSTS`.

## Rutas principales

- `/` landing
- `/cuenta/crear/` registro
- `/cuenta/ingresar/` login
- `/onboarding/` armado del espacio
- `/panel/` panel principal
- `/panel/agenda/` agenda semanal
- `/panel/agenda/dia/` agenda diaria
- `/panel/recordatorios/` recordatorios y mensajes para WhatsApp
- `/panel/agenda/turnos/nuevo/` nuevo turno
- `/panel/clientes/` clientes
- `/panel/servicios/` servicios
- `/panel/horarios/` horarios y días libres
- `/panel/ingresos/` ingresos
- `/admin/` administración
- `/health/` health check

## Pruebas y calidad

```bash
.venv/bin/python manage.py test
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python manage.py makemigrations --check --dry-run
npm run css:build
```

La suite incluye tests de onboarding, servicios, clientes, horarios, disponibilidad, turnos, estados, recordatorios, cobros, ingresos, aislamiento entre negocios y rutas protegidas.

## PostgreSQL en producción

En producción la app exige `DATABASE_URL`; SQLite queda reservado para desarrollo local. Configurar en el entorno:

```bash
DATABASE_URL=postgres://usuario:clave@host:5432/elaris
DJANGO_SECRET_KEY=una-clave-larga-y-segura
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=tu-dominio.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://tu-dominio.com
```

Luego:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
gunicorn config.wsgi:application
```

La migración `agenda.0003_exclude_overlapping_appointments` agrega la extensión `btree_gist` y una restricción `EXCLUDE` para impedir turnos superpuestos a nivel de base. El usuario de la base necesita permisos para crear la extensión o un administrador debe crearla antes de migrar. Si ya existen turnos superpuestos, la migración va a fallar hasta resolverlos.

### Vercel + Neon

El proyecto `elaris` en Vercel usa el preset Django y una base PostgreSQL de Neon conectada desde el Marketplace. En Vercel el sistema de archivos es de solo lectura: SQLite no puede usarse en producción porque falla al guardar usuarios, sesiones, turnos y cobros.

La integración de Neon inyecta `DATABASE_URL` (pooled). Además hay que configurar en Production:

```bash
DJANGO_SECRET_KEY=una-clave-larga-y-segura
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=elaris-six-bice.vercel.app,elaris-th208.vercel.app
DJANGO_CSRF_TRUSTED_ORIGINS=https://elaris-six-bice.vercel.app,https://elaris-th208.vercel.app
```

Para aplicar migraciones a la base de producción desde una copia local:

```bash
npx vercel env pull .env.production --environment=production
set -a
source .env.production
set +a
.venv/bin/python manage.py migrate
```

Después de cambiar el modelo, generá y commiteá la migración, aplicála en producción y volvé a desplegar. Si `DJANGO_DEBUG=0` y falta `DJANGO_SECRET_KEY` o `DATABASE_URL`, la app no arranca a propósito.

### Email y recuperación de contraseña

La recuperación de contraseña necesita un proveedor SMTP en producción. Sin configurarlo, Django usa el backend de consola: el link se escribe en los logs y no llega a la persona. El check `elaris.W001` avisa de esa situación en `manage.py check --deploy`.

Variables necesarias en Production:

```bash
DJANGO_EMAIL_HOST=smtp-relay.brevo.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=el-usuario-smtp-que-muestra-brevo
DJANGO_EMAIL_HOST_PASSWORD=tu-clave-smtp
DJANGO_EMAIL_USE_TLS=1
DEFAULT_FROM_EMAIL=Elaris <tu@email.com>
```

Opciones:

- **Brevo** (recomendado si todavía no hay dominio): plan free, verificás un email como remitente y generás una clave SMTP. El usuario SMTP es el que muestra Brevo en **Transactional → SMTP & API** (suele terminar en `@smtp-brevo.com`), no tu email de login. Permite enviar a cualquier destinatario.
- **Resend** (recomendado con dominio propio): verificás el dominio y usás `smtp.resend.com`, usuario `resend` y la API key como clave.
- **Gmail**: `smtp.gmail.com`, puerto 587, tu email y una contraseña de aplicación.

El remitente de `DEFAULT_FROM_EMAIL` tiene que estar verificado en el proveedor. El link usa el host de la request, así que funciona igual en Vercel o en un dominio propio. `DJANGO_PASSWORD_RESET_TIMEOUT` define la vigencia en segundos (86400 por defecto).

## Documentación

- `docs/DECISIONS.md`: decisiones de producto, datos, catálogo y brand.

## Fuera del MVP

- Cuentas de clientes o login de clientes.
- Reserva online, links de cancelación o reprogramación y páginas públicas.
- Branding por negocio, logo propio, galería o temas personalizados.
- Mercado Pago, cobros online, suscripciones, planes y límites.
- Equipo, múltiples profesionales por negocio o múltiples negocios por cuenta.
- Reseñas, promociones, fidelidad y analítica avanzada.
- Integración con la API de WhatsApp; los recordatorios son manuales.
- Directorio público de profesionales.
