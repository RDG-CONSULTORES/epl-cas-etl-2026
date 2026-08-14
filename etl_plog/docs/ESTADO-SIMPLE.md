# PLOG — Qué entró y qué falta (en simple)
**2026-08-13** · Para Roberto, sin jerga.

## 🌐 Cómo entrar
- **App / tablero:** https://plog-web-production.up.railway.app
- **Admin (configurar reglas):** https://plog-web-production.up.railway.app/admin
- **Cuenta que ve TODO + configura:** `admin` / `PLOG-Roberto-2608`
- **Cuenta de director (ve solo su zona):** `director.laguna` / `laguna-2026`

## ✅ Lo que YA FUNCIONA (vivo en internet, se actualiza solo cada 3 horas)

| Capacidad | ¿Entró? | Qué hace |
|---|---|---|
| Jala los datos de Zenput | ✅ | Solo las 18 tiendas PLOG, cada 3h automático |
| Cumplimiento (¿lo hicieron a tiempo?) | ✅ | Por tienda y por formulario, con 4 estados |
| Calificaciones con desglose por área | ✅ | El "qué tan bien", por sección del formulario |
| **Fotos, videos y firmas de evidencia** | ✅ | La foto/video/firma real de cada formulario |
| Tablero para directores (ve solo su zona) | ✅ | Login, tiendas peor-primero, drill-down |
| **Ver Hoy / Esta semana / Este mes** | ✅ | Selector de periodo (ya no clavado en semana) |
| **Admin panel para afinar reglas** | ✅ | Editor en español: "se espera cada día antes de las 3pm…" |
| Usuarios y accesos (por zona) | ✅ | Alta de gente, cada quien ve solo lo suyo |
| Reportes (vista previa de todas las cadencias) | ✅ | Semanal…anual con comparativos |
| Bitácora (quién cambió qué) | ✅ | Auditoría de cada cambio de config |

## 🔴 Lo que FALTA (y qué necesito de ti)

| Falta | Por qué / qué necesito |
|---|---|
| **Enviar los reportes por correo** | Decidiste dejarlo al final. Falta elegir: Google SMTP (con tu @plog.com.mx) o Resend. El reporte YA se genera, solo falta el "enviar". |
| **Confirmar las reglas de cada formulario** | Las reglas salieron del Excel + la data. Falta que TÚ (o los directores) revisen en el admin y confirmen: "sí, RL1 es antes de las 3pm". Esto es lo que hace que se sienta tuyo. |
| **Apps nativas iOS/Android** | La cereza. Hoy funciona como app instalable en el navegador. |
| **Agente de IA (chat)** | La otra cereza. |
| PDF de evidencia (bajar el formulario) | Existe en la API, falta cablearlo (opcional). |

## 🎯 Lo que hace que ESTO SE SIENTA REAL (tu preocupación)
El sistema ya funciona. Lo que falta para que **haga sentido humano** es que TÚ te sientes en el **admin** (con la cuenta admin) y **revises las reglas formulario por formulario** — ahora cada una se lee en español claro y se actualiza en vivo. Cuando confirmes que las reglas son las correctas para tu operación, el sistema deja de ser "de la computadora" y pasa a ser **tuyo**.

## El flujo del director, en 4 toques
1. Entra → ve solo su zona.
2. Ve sus tiendas, peor primero.
3. Toca la peor → ve qué formulario falla.
4. Toca el formulario → ve los días que faltaron + la evidencia (foto/video/firma).
