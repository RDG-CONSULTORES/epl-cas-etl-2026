"""Endpoints de administración (config viva). TODOS gated a rol=admin.

Cada edición valida server-side y escribe a config_audit (quién cambió qué).
El frontend edita; el backend impone y audita.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from psycopg.types.json import Jsonb

from etl_plog.api import auth
from etl_plog.shared.db import conn

router = APIRouter(prefix="/api/admin")

FRECUENCIAS = {"diario", "diario_por_dia", "semanal", "quincenal", "semana_del_mes",
               "mensual", "bimestral", "trimestral", "semestral", "anual", "por_visita"}
MEDICIONES = {"cumplimiento", "calificacion", "ambos"}
ROLES = {"admin", "director", "viewer"}


def admin_req(request: Request) -> dict:
    u = auth.usuario_de_sesion(request.cookies.get("plog_sesion"))
    if not u:
        raise HTTPException(401, "No autenticado")
    if u["rol"] != "admin":
        raise HTTPException(403, "Requiere rol admin")
    return u


def _audit_cfg(cur, familia, zona, cambios, usuario):
    cur.execute("INSERT INTO config_audit (familia, zona, cambios, usuario) VALUES (%s,%s,%s,%s)",
                (familia, zona, Jsonb(cambios), usuario))


# ── FORMULARIOS ──────────────────────────────────────────────────────────
@router.get("/formularios")
def list_formularios(admin: dict = Depends(admin_req)):
    with conn() as c:
        rows = c.execute("""
            SELECT familia, zona, activo, nombre, medicion, frecuencia,
                   to_char(hora_limite,'HH24:MI') hora_limite, dias_gracia,
                   origen, quien_llena, caso_uso, updated_at, updated_by
            FROM config_formularios ORDER BY nombre, zona""").fetchall()
    return {"formularios": rows}


@router.put("/formularios/{familia}/{zona}")
def edit_formulario(familia: str, zona: str, payload: dict, admin: dict = Depends(admin_req)):
    campos = {}
    if "activo" in payload:
        campos["activo"] = bool(payload["activo"])
    if "frecuencia" in payload:
        if payload["frecuencia"] not in FRECUENCIAS:
            raise HTTPException(400, f"frecuencia inválida: {payload['frecuencia']}")
        campos["frecuencia"] = payload["frecuencia"]
    if "medicion" in payload:
        if payload["medicion"] not in MEDICIONES:
            raise HTTPException(400, "medicion inválida")
        campos["medicion"] = payload["medicion"]
    if "hora_limite" in payload:
        campos["hora_limite"] = payload["hora_limite"] or None
    if "dias_gracia" in payload:
        g = int(payload["dias_gracia"])
        if g < 0:
            raise HTTPException(400, "días de gracia no puede ser negativo")
        campos["dias_gracia"] = g
    if not campos:
        raise HTTPException(400, "nada que actualizar")

    with conn() as c:
        cur = c.cursor()
        antes = cur.execute(
            "SELECT activo, frecuencia, to_char(hora_limite,'HH24:MI') hora_limite, dias_gracia, medicion FROM config_formularios WHERE familia=%s AND zona=%s",
            (familia, zona)).fetchone()
        if not antes:
            raise HTTPException(404, "formulario/zona no encontrado")
        sets = ", ".join(f"{k}=%s" for k in campos)
        cur.execute(f"UPDATE config_formularios SET {sets}, updated_at=now(), updated_by=%s WHERE familia=%s AND zona=%s",
                    list(campos.values()) + [admin["usuario"], familia, zona])
        diff = {k: {"antes": antes[k], "despues": v} for k, v in campos.items() if antes.get(k) != v}
        if diff:
            _audit_cfg(cur, familia, zona, diff, admin["usuario"])
    return {"ok": True, "cambios": diff}


# ── SUCURSALES ───────────────────────────────────────────────────────────
@router.get("/sucursales")
def list_sucursales(admin: dict = Depends(admin_req)):
    with conn() as c:
        rows = c.execute("""SELECT location_id, nombre, zona, director, activo,
                                   es_comisariato, serie_requerida, serie_alistamiento
                            FROM sucursales ORDER BY zona, nombre""").fetchall()
    return {"sucursales": rows}


@router.put("/sucursales/{location_id}")
def edit_sucursal(location_id: int, payload: dict, admin: dict = Depends(admin_req)):
    campos = {}
    for k in ("activo", "es_comisariato"):
        if k in payload:
            campos[k] = bool(payload[k])
    if "serie_requerida" in payload:
        v = payload["serie_requerida"]
        if v not in ("A", "L", None, ""):
            raise HTTPException(400, "serie inválida")
        campos["serie_requerida"] = v or None
    if not campos:
        raise HTTPException(400, "nada que actualizar")
    with conn() as c:
        cur = c.cursor()
        sets = ", ".join(f"{k}=%s" for k in campos)
        n = cur.execute(f"UPDATE sucursales SET {sets}, updated_at=now() WHERE location_id=%s",
                        list(campos.values()) + [location_id]).rowcount
        if not n:
            raise HTTPException(404, "sucursal no encontrada")
        _audit_cfg(cur, f"sucursal:{location_id}", "-", campos, admin["usuario"])
    return {"ok": True}


# ── USUARIOS ─────────────────────────────────────────────────────────────
@router.get("/usuarios")
def list_usuarios(admin: dict = Depends(admin_req)):
    with conn() as c:
        rows = c.execute("""
            SELECT u.id, u.usuario, u.nombre, u.rol, u.activo, u.ultimo_login,
                   u.bloqueado_hasta,
                   coalesce(json_agg(json_build_object('zona', s.zona, 'location_ids', s.location_ids))
                            FILTER (WHERE s.id IS NOT NULL), '[]') scopes
            FROM usuarios u LEFT JOIN user_scopes s ON s.user_id=u.id
            GROUP BY u.id ORDER BY u.usuario""").fetchall()
    return {"usuarios": rows}


@router.post("/usuarios")
def crea_usuario(payload: dict, admin: dict = Depends(admin_req)):
    usuario = str(payload.get("usuario", "")).strip()
    password = str(payload.get("password", ""))
    rol = payload.get("rol", "viewer")
    if not usuario or len(password) < 6:
        raise HTTPException(400, "usuario requerido y contraseña ≥6 caracteres")
    if rol not in ROLES:
        raise HTTPException(400, "rol inválido")
    uid = auth.crea_usuario(usuario, password, rol, payload.get("nombre"),
                            payload.get("scopes") or [])
    with conn() as c:
        c.cursor().execute("INSERT INTO acceso_audit (usuario, evento, detalle) VALUES (%s,'alta',%s)",
                           (usuario, f"por {admin['usuario']}, rol {rol}"))
    return {"ok": True, "id": uid}


@router.put("/usuarios/{uid}")
def edit_usuario(uid: int, payload: dict, admin: dict = Depends(admin_req)):
    with conn() as c:
        cur = c.cursor()
        if "activo" in payload:
            cur.execute("UPDATE usuarios SET activo=%s, bloqueado_hasta=NULL, intentos_fallidos=0 WHERE id=%s",
                        (bool(payload["activo"]), uid))
        if payload.get("rol") in ROLES:
            cur.execute("UPDATE usuarios SET rol=%s WHERE id=%s", (payload["rol"], uid))
        if payload.get("password"):
            if len(payload["password"]) < 6:
                raise HTTPException(400, "contraseña ≥6 caracteres")
            cur.execute("UPDATE usuarios SET password_hash=%s, intentos_fallidos=0, bloqueado_hasta=NULL WHERE id=%s",
                        (auth.hash_password(payload["password"]), uid))
            cur.execute("DELETE FROM sesiones WHERE user_id=%s", (uid,))  # invalidar sesiones
        if "scopes" in payload:
            cur.execute("DELETE FROM user_scopes WHERE user_id=%s", (uid,))
            for sc in payload["scopes"]:
                cur.execute("INSERT INTO user_scopes (user_id, zona, location_ids) VALUES (%s,%s,%s)",
                            (uid, sc.get("zona"), sc.get("location_ids")))
        cur.execute("INSERT INTO acceso_audit (usuario, evento, detalle) VALUES (%s,'editado',%s)",
                    (str(uid), f"por {admin['usuario']}"))
    return {"ok": True}


# ── BITÁCORA ─────────────────────────────────────────────────────────────
@router.get("/audit")
def get_audit(admin: dict = Depends(admin_req), limite: int = 100):
    with conn() as c:
        cfg = c.execute("""SELECT 'config' tipo, familia entidad, zona, cambios::text detalle, usuario, ts
                           FROM config_audit ORDER BY ts DESC LIMIT %s""", (limite,)).fetchall()
        acc = c.execute("""SELECT 'acceso' tipo, usuario entidad, NULL zona, evento||' '||coalesce(detalle,'') detalle, usuario, ts
                           FROM acceso_audit ORDER BY ts DESC LIMIT %s""", (limite,)).fetchall()
    todos = sorted(cfg + acc, key=lambda r: r["ts"], reverse=True)[:limite]
    return {"eventos": todos}


# ── REPORTES ─────────────────────────────────────────────────────────────
from datetime import date

from fastapi.responses import HTMLResponse


@router.get("/reportes")
def list_reportes(admin: dict = Depends(admin_req)):
    with conn() as c:
        rows = c.execute("SELECT * FROM report_schedules ORDER BY creado_at DESC").fetchall()
        envs = c.execute("SELECT canal, cadencia, destinatarios, enviado, detalle, ts FROM envios ORDER BY ts DESC LIMIT 20").fetchall()
    return {"reportes": rows, "envios": envs}


@router.get("/reportes/preview", response_class=HTMLResponse)
def preview_reporte(admin: dict = Depends(admin_req), cadencia: str = "semanal"):
    from etl_plog.reportes import generador, render
    d = generador.datos(cadencia, date.today(), admin["scopes"])
    return render.html(d).replace("{{APP_URL}}", "/")


@router.post("/reportes/enviar")
def enviar_reporte(payload: dict, admin: dict = Depends(admin_req)):
    from etl_plog.reportes import generador, render, envio
    cadencia = payload.get("cadencia", "semanal")
    dest = payload.get("destinatarios") or []
    if not dest:
        raise HTTPException(400, "sin destinatarios")
    d = generador.datos(cadencia, date.today(), admin["scopes"])
    html = render.html(d)
    asunto = f"Cumplimiento PLOG · {d['periodo']['label']}"
    res = envio.envia_correo(dest, asunto, html)
    envio.registra_envio(cadencia, dest, asunto, res)
    return {"enviado": res.get("enviado"), "detalle": res.get("error") or res.get("id")}
