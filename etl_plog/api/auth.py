"""Auth: hashing bcrypt, sesiones server-side, scoping por zona+sucursal.

Sin self-signup: solo el admin da de alta usuarios. Sesión = cookie HttpOnly con
token opaco (la validación vive en la BD, no en el cliente).
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt

from etl_plog.shared.db import conn

SESION_DIAS = 30
MAX_INTENTOS = 5
BLOQUEO_MIN = 15


def hash_password(plano: str) -> str:
    return bcrypt.hashpw(plano.encode(), bcrypt.gensalt()).decode()


def verifica_password(plano: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(plano.encode(), hash_.encode())
    except (ValueError, TypeError):
        return False


def _audit(cur, usuario: str | None, evento: str, detalle: str = "") -> None:
    cur.execute("INSERT INTO acceso_audit (usuario, evento, detalle) VALUES (%s,%s,%s)",
                (usuario, evento, detalle))


def login(usuario: str, password: str, user_agent: str = "") -> str | None:
    """-> token de sesión, o None si credenciales inválidas / bloqueado."""
    ahora = datetime.now(timezone.utc)
    with conn() as c:
        cur = c.cursor()
        u = cur.execute(
            "SELECT * FROM usuarios WHERE usuario=%s AND activo", (usuario,)).fetchone()
        if not u:
            _audit(cur, usuario, "login_fail", "usuario inexistente/inactivo")
            return None
        if u["bloqueado_hasta"] and u["bloqueado_hasta"] > ahora:
            _audit(cur, usuario, "bloqueado", "intento durante bloqueo")
            return None
        if not verifica_password(password, u["password_hash"]):
            intentos = u["intentos_fallidos"] + 1
            bloqueo = ahora + timedelta(minutes=BLOQUEO_MIN) if intentos >= MAX_INTENTOS else None
            cur.execute("UPDATE usuarios SET intentos_fallidos=%s, bloqueado_hasta=%s WHERE id=%s",
                        (intentos, bloqueo, u["id"]))
            _audit(cur, usuario, "login_fail", f"intento {intentos}")
            return None
        token = secrets.token_urlsafe(32)
        cur.execute(
            """INSERT INTO sesiones (token, user_id, expira_at, user_agent)
               VALUES (%s,%s,%s,%s)""",
            (token, u["id"], ahora + timedelta(days=SESION_DIAS), user_agent[:300]))
        cur.execute("UPDATE usuarios SET ultimo_login=now(), intentos_fallidos=0, bloqueado_hasta=NULL WHERE id=%s",
                    (u["id"],))
        _audit(cur, usuario, "login_ok")
    return token


def logout(token: str) -> None:
    with conn() as c:
        c.cursor().execute("DELETE FROM sesiones WHERE token=%s", (token,))


def usuario_de_sesion(token: str | None) -> dict | None:
    """Valida el token; -> {id, usuario, rol, nombre, scopes} o None."""
    if not token:
        return None
    ahora = datetime.now(timezone.utc)
    with conn() as c:
        cur = c.cursor()
        s = cur.execute(
            """SELECT s.token, u.id, u.usuario, u.rol, u.nombre
               FROM sesiones s JOIN usuarios u ON u.id=s.user_id
               WHERE s.token=%s AND s.expira_at>%s AND u.activo""",
            (token, ahora)).fetchone()
        if not s:
            return None
        cur.execute("UPDATE sesiones SET ultimo_uso=now() WHERE token=%s", (token,))
        scopes = cur.execute(
            "SELECT zona, location_ids FROM user_scopes WHERE user_id=%s", (s["id"],)).fetchall()
    return {"id": s["id"], "usuario": s["usuario"], "rol": s["rol"],
            "nombre": s["nombre"], "scopes": scopes}


def crea_usuario(usuario: str, password: str, rol: str = "viewer",
                 nombre: str | None = None, scopes: list[dict] | None = None) -> int:
    """Alta por admin. scopes = [{'zona': 'laguna', 'location_ids': [..]|None}] o [] = todo."""
    with conn() as c:
        cur = c.cursor()
        uid = cur.execute(
            """INSERT INTO usuarios (usuario, nombre, password_hash, rol)
               VALUES (%s,%s,%s,%s)
               ON CONFLICT (usuario) DO UPDATE SET password_hash=EXCLUDED.password_hash,
                   rol=EXCLUDED.rol, nombre=EXCLUDED.nombre, activo=TRUE
               RETURNING id""",
            (usuario, nombre, hash_password(password), rol)).fetchone()["id"]
        cur.execute("DELETE FROM user_scopes WHERE user_id=%s", (uid,))
        for sc in (scopes or []):
            cur.execute(
                "INSERT INTO user_scopes (user_id, zona, location_ids) VALUES (%s,%s,%s)",
                (uid, sc.get("zona"), sc.get("location_ids")))
    return uid
