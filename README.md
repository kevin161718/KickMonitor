# Kick Guard — Dashboard (solo lectura)

Panel multicanal con Flask, gráficos de espectadores, detección de anomalías, marcado manual de raids confirmadas y exportación CSV.

## Windows (local)

```powershell
py -m pip install -r requirements.txt
py app.py
```

Abrí [https://kickmonitor.vercel.app/](https://kickmonitor.vercel.app/)

## Datos y limitaciones

- La interfaz almacena históricos y eventos en `localStorage` del navegador; son específicos de ese navegador. No se sincronizan entre usuarios ni dispositivos.
- En Windows/local, `app.py` guarda muestras también en SQLite `kick_guard.db`. Vercel no ofrece almacenamiento SQLite persistente: en Vercel **solo se guarda en navegador**.
- Kick puede rechazar solicitudes del endpoint `kick.com/api/v2/channels/<usuario>`, que no forma parte de su API oficial contractual. Hay un segundo endpoint opcional para recuperar viewers si faltan.
- Consultas mínimas por canal cada 10 segundos; se hacen solo mientras el dashboard está abierto. No es monitor 24/7 ni garantiza que el contador cambie tan rápido.
- Cuando falla la consulta, el panel muestra un error y **no** registra 0 viewers falsamente.
- Una subida brusca **no prueba** viewbotting. Confirmá una raid en el panel de eventos del streamer, e introducí la evidencia al marcarla como confirmada.
- No se ejecuta ni incluye ninguna rutina de creación de conexiones para inflar audiencia. No identifica las IP ni la persona que contrató viewbots.

## Seguridad

El panel no tiene autenticación: no subas datos confidenciales o sensibles. Los datos históricos quedan en el navegador; si compartís el enlace, cada persona verá sus propios canales y mediciones. Para monitoreo centralizado 24/7 usar una base externa (Postgres) y un scheduler/worker autorizado.

## Nuevas gráficas automáticas

- Audiencia en vivo (muestras individuales).
- Selector Hoy / Últimos 7 días / Últimos 30 días.
- Cuatro gráficos históricos simultáneos: período elegido, semanal, últimos 30 días y últimos 12 meses.
- Barras: promedio de espectadores por intervalo. Línea amarilla: máximo registrado.
- Resúmenes horarios por canal guardados en el navegador hasta 400 días, incluso cuando las muestras individuales antiguas se recortan. Las muestras anteriores que sigan disponibles se agregan al abrir la versión actualizada.
- `GET /api/stats/<canal>`: cálculo automático de grupos por hora, día y mes a partir de SQLite local (`ANALYTICS_TIMEZONE` configurable; predeterminado `America/Montevideo`).

