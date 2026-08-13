"""Scoping: traduce los scopes del usuario a un filtro SQL (zona + sucursales).

El backend IMPONE el alcance; el frontend solo esconde. Todo endpoint de datos
pasa por aquí para que cada quien vea SOLO sus zonas/sucursales.
"""
from __future__ import annotations


def clausula_scope(scopes: list[dict], alias: str = "") -> tuple[str, list]:
    """-> (sql_where, params). WHERE que limita a lo que el usuario puede ver.

    scopes vacío  -> no ve nada ('FALSE').
    scope con zona NULL           -> todas las zonas.
    scope con location_ids NULL   -> toda la zona.
    scope con location_ids [...]  -> solo esas sucursales de esa zona.
    """
    p = f"{alias}." if alias else ""
    if not scopes:
        return "FALSE", []

    ors, params = [], []
    for sc in scopes:
        zona, locs = sc.get("zona"), sc.get("location_ids")
        if zona is None:
            return "TRUE", []                      # acceso total
        if locs:
            ors.append(f"({p}zona = %s AND {p}location_id = ANY(%s))")
            params += [zona, list(locs)]
        else:
            ors.append(f"{p}zona = %s")
            params.append(zona)
    return "(" + " OR ".join(ors) + ")", params


def zonas_visibles(scopes: list[dict]) -> set[str] | None:
    """-> conjunto de zonas que ve, o None si ve todas."""
    zs = set()
    for sc in scopes:
        if sc.get("zona") is None:
            return None
        zs.add(sc["zona"])
    return zs
