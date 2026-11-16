# Decisiones de Elaris

## Producto

- Elaris es una app interna para profesionales de la belleza. No hay cuentas de clientes, reserva online, links de cancelación/reprogramación, páginas públicas ni personalización visual por negocio.
- Elaris es la única marca. El nombre del negocio es una etiqueta interna y no altera tema, URL ni identidad visual.
- Una cuenta equivale a una profesional y a un negocio en el MVP. No hay equipo ni múltiples negocios por cuenta.
- Los rubros iniciales son fijos: Uñas, Pestañas y Cejas. No se incluye “Otro” por ahora.
- El catálogo inicial se siembra con servicios y duraciones estimadas. Los precios quedan vacíos para completarlos después.
- El onboarding crea el negocio, asocia los rubros elegidos y copia los servicios seleccionados. Archivar un servicio no borra historial.
- Los clientes y los servicios se archivan y se reactivan; no se eliminan desde el panel.

## Cuenta y acceso

- Registro e inicio de sesión con email y contraseña. En el MVP no hay verificación de email ni login con Google.
- La recuperación de contraseña usa las vistas de Django y un link por email de un solo uso, válido 24 horas por defecto (`DJANGO_PASSWORD_RESET_TIMEOUT`).
- El pedido de recuperación no revela si el email existe: siempre muestra la misma pantalla y solo envía el correo cuando la cuenta está activa.
- En producción el envío requiere SMTP configurado. Si no, el check `elaris.W001` avisa y el link queda en los logs en lugar de llegar por email.
- No hay 2FA ni preguntas de seguridad en el MVP.

## Stack

- Django 5.2 LTS + templates server-side + HTMX + Tailwind CSS 4.
- PostgreSQL en producción. SQLite queda como fallback explícito para desarrollo local cuando no hay `DATABASE_URL`.
- El deploy de producción usa Vercel (preset Django) y Neon como PostgreSQL del Marketplace. Vercel tiene filesystem de solo lectura, así que SQLite no se usa en producción.
- Sin SPA ni API REST para el MVP.
- Autenticación por email y contraseña con modelo de usuario propio (`accounts.User`).
- Tailwind se compila con la CLI y se sirve como archivo estático; no se usa CDN para el CSS de la app.
- Gunicorn + WhiteNoise para servir la app fuera de Vercel; en Vercel la app corre como función serverless con `collectstatic` en el build.

## Datos y aislamiento

- Una sola base y un solo esquema con `business_id` como límite de pertenencia. No se usa schema-per-tenant.
- Las consultas de negocio se filtran siempre por la profesional autenticada. Las vistas de edición usan `get_object_or_404(..., business=business)` para impedir acceso cruzado.
- Se agregan tests de aislamiento entre dos negocios.
- `User` 1:1 `Business`; `Business` M2M `Specialty`; `Business` 1:N `Service`; `Business` 1:N `Client`; `Business` 1:N `Appointment`, `ScheduleBlock` y `TimeOff`.
- `Business` guarda un `whatsapp` opcional que se agrega al final de los recordatorios.
- `Appointment` guarda snapshot de `service_name`, `duration_minutes` y `price`. Así el historial no cambia si después se edita el servicio.
- `Appointment` también guarda `reminded_at`, `amount_paid` y `payment_method` para el seguimiento de recordatorios y cobros.
- En PostgreSQL, la migración `agenda.0003_exclude_overlapping_appointments` agrega `btree_gist` y una restricción `EXCLUDE` sobre `business_id` y `tstzrange(start_at, end_at, '[)')`, excluyendo turnos cancelados. SQLite no soporta esa restricción: en desarrollo la validación de superposición es de aplicación.

## Catálogo inicial

- Uñas: Belleza de manos, Semi permanente, Capping, Soft gel, Esculpidas en gel, Esculpidas en acrílico, Esculpidas en polygel, Esmaltado semi en pies, Service (mantenimiento/retiro).
- Pestañas: Lifting, Clásicas, Efecto rímel, Volumen brasilero, Volumen 3D, Volumen 4D, Volumen 5D, Foxy, Efecto coreano.
- Cejas: Perfilado, Laminado, Henna.
- “Service” se interpreta como mantenimiento/retiro y dura 60 minutos.
- Las duraciones son estimadas y editables.

## Servicios

- Cada servicio pertenece a uno de los rubros elegidos por el negocio.
- El nombre es único por negocio y rubro, sin distinguir mayúsculas.
- La duración se valida entre 5 y 600 minutos.
- El precio es opcional; los precios se muestran en pesos argentinos.
- Archivar un servicio lo saca de la oferta de turnos nuevos sin borrar turnos anteriores.

## Clientes

- La ficha guarda nombre, teléfono/WhatsApp, email y notas privadas.
- La búsqueda es por nombre, teléfono o email.
- El listado se pagina de a 20.
- Un cliente archivado no se ofrece para turnos nuevos, pero su ficha y su historial siguen disponibles.
- No hay datos de clientes compartidos entre negocios.

## Horarios y disponibilidad

- `ScheduleBlock` representa un bloque de atención dentro de un día de la semana.
- Se permiten varios bloques por día; los huecos entre bloques son descansos.
- `TimeOff` es un rango de días libres con motivo opcional.
- Los turnos se validan contra bloques, días libres y otros turnos no cancelados.
- La disponibilidad se calcula en intervalos de 15 minutos, con la duración del servicio elegido.
- El horario sugerido crea lunes a viernes de 9 a 13 y de 15 a 19, y sábado de 9 a 13. Es solo un punto de partida editable.
- La agenda diaria muestra la disponibilidad del servicio elegido. El selector usa HTMX para actualizar el panel sin recargar.

## Turnos

- Un turno tiene un cliente y un servicio.
- Al guardar se calcula `end_at` a partir de `start_at` y la duración.
- Se guarda un snapshot de nombre, duración y precio del servicio.
- Si el precio se deja vacío, se copia el precio actual del servicio. Si se ingresa `0`, se respeta como turno sin cargo.
- Estados: `scheduled`, `completed`, `cancelled`, `no_show`.
- Las transiciones permitidas son:
  - programado → completado, cancelado o no asistió;
  - cancelado o no asistió → programado (reabrir), siempre que el horario siga disponible.
- Los turnos se muestran en la agenda semanal, la agenda diaria, la ficha de cliente, el panel y el detalle del turno.
- La agenda semanal no cuenta turnos cancelados; el detalle diario sí los muestra para conservar contexto.

## Cobros

- Un turno puede registrar `amount_paid` y `payment_method`.
- Los medios de pago son efectivo, transferencia y otro.
- Los estados de cobro se derivan:
  - sin monto: “Sin registrar”;
  - monto en cero: “Pendiente”;
  - monto mayor a cero y menor al precio: “Seña”;
  - monto mayor o igual al precio: “Pagado”.
- Si se ingresa un monto, el medio de pago es obligatorio. Si se ingresa un medio, el monto también.
- El monto no puede superar el precio del turno cuando el turno tiene precio.
- Dejar monto y medio vacíos borra el cobro registrado.
- Se puede registrar una seña antes del turno; el cobro se conserva al cambiar de estado.
- El cobro no modifica el ingreso facturado: son dos lecturas distintas del mismo turno.

## Ingresos

- El resumen de ingresos trabaja por mes calendario.
- Solo se suman turnos con estado completado.
- Un turno completado sin precio no suma al total ni al ticket promedio.
- El detalle incluye cantidad de turnos completados, ticket promedio, cancelados, ausencias y agrupación por rubro y servicio.
- El resumen muestra por separado lo facturado, lo cobrado y lo pendiente de cobro.
- Lo cobrado se toma de `amount_paid` de los turnos completados; lo pendiente es la diferencia contra el precio.
- Lo cobrado en un turno completado sin precio se cuenta como cobrado, pero no altera el ingreso facturado.
- No hay liquidación de comisiones ni impuestos en el MVP.

## Recordatorios

- El recordatorio es manual.
- Se prepara desde `/panel/recordatorios/` o desde el detalle del turno.
- La página muestra por defecto los turnos de mañana y permite navegar por fecha.
- Solo lista turnos programados; los recordados siguen visibles para poder desmarcarlos.
- Elaris arma un texto con el nombre del cliente, servicio, negocio, fecha y hora.
- Si el negocio tiene WhatsApp cargado, se agrega al final del mensaje.
- El botón “Abrir WhatsApp” usa `wa.me` con el teléfono del cliente normalizado. Si no hay teléfono, solo se puede copiar el mensaje.
- “Marcar recordado” guarda `reminded_at`; se puede desmarcar.
- El panel avisa cuántos turnos de mañana están agendados y cuántos siguen sin recordar.
- No se integra la API de WhatsApp en el MVP: no hay envío automático.

## Branding

- Los assets se derivan del PNG provisto en `design/logo-elaris-source.png` con `scripts/build_brand_assets.py`.
- Paleta base: crema `#FAF5EC`, azul grisáceo `#5D7084`, celeste `#8BBFDE`.
- Se usa logo horizontal en landing/login, isotipo en ícono y marca de agua del panel, y favicon derivado del isotipo.
- La bajada “turnos de belleza” se usa en la landing; el panel prioriza el logo horizontal sin bajada.

## Fuera del MVP

- Cuentas de clientes o login de clientes.
- Reserva online, links de cancelación/reprogramación y páginas públicas.
- Branding por negocio, logo propio, galería o temas personalizados.
- Mercado Pago, cobros online, suscripciones, planes y límites.
- Equipo, múltiples profesionales por negocio o múltiples negocios por cuenta.
- Reseñas, promociones, fidelidad y analítica avanzada.
- Integración con la API de WhatsApp.
- Directorio público de profesionales.
