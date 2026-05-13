"""Carga y resuelve las 68 sucursales EPL CAS desde Zenput.

Una sucursal está in-scope si tiene tag EPL CAS (id=59266) Y pertenece a
uno de los 18 GOs EPL CAS.
"""
from __future__ import annotations

import logging
from typing import Any

from etl_v2.shared.db import execute_many, fetch_all, get_conn
from etl_v2.shared.teams_resolver import (
    EPL_CAS_GO_IDS,
    build_team_tree,
    is_epl_cas_go,
    resolve_location_go,
)
from etl_v2.shared.zenput_client import ZenputClient

log = logging.getLogger(__name__)

EPL_CAS_TAG_ID = 59266


def _has_epl_cas_tag(location: dict) -> bool:
    tags = location.get("tags") or []
    for t in tags:
        tid = t.get("id") if isinstance(t, dict) else t
        if tid == EPL_CAS_TAG_ID:
            return True
    return False


async def sync_dim_sucursales(client: ZenputClient | None = None) -> dict[str, int]:
    """Pull locations + teams desde Zenput, persiste dim_sucursales y dim_grupos_operativos.

    Retorna métricas: {n_locations_api, n_in_scope, n_upserted}.
    """
    owns_client = client is None
    if owns_client:
        client = ZenputClient()
        await client.__aenter__()
    try:
        teams = await client.list_teams()
        locations = await client.list_locations()
    finally:
        if owns_client:
            await client.__aexit__(None, None, None)

    team_to_go = build_team_tree(teams)
    team_name_by_id = {t["id"]: t.get("name") or "" for t in teams}

    suc_rows: list[tuple] = []
    go_counts: dict[int, int] = {}
    in_scope = 0
    for loc in locations:
        loc_id = loc.get("id")
        if loc_id is None:
            continue
        has_tag = _has_epl_cas_tag(loc)
        go_id, _ = resolve_location_go(loc, team_to_go)
        is_active = has_tag and is_epl_cas_go(go_id)
        go_nombre = team_name_by_id.get(go_id) if go_id else None
        suc_rows.append(
            (loc_id, loc.get("name") or "", go_id, go_nombre, has_tag, is_active)
        )
        if is_active:
            in_scope += 1
            go_counts[go_id] = go_counts.get(go_id, 0) + 1

    n_upserted = execute_many(
        """
        INSERT INTO dim_sucursales (location_id, nombre, go_id, go_nombre, has_epl_cas_tag, is_active, last_synced_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (location_id) DO UPDATE SET
            nombre          = EXCLUDED.nombre,
            go_id           = EXCLUDED.go_id,
            go_nombre       = EXCLUDED.go_nombre,
            has_epl_cas_tag = EXCLUDED.has_epl_cas_tag,
            is_active       = EXCLUDED.is_active,
            last_synced_at  = NOW()
        """,
        suc_rows,
    )

    go_rows = [
        (go_id, team_name_by_id.get(go_id) or f"GO {go_id}", n_suc)
        for go_id, n_suc in go_counts.items()
    ]
    for missing in EPL_CAS_GO_IDS - set(go_counts.keys()):
        go_rows.append((missing, team_name_by_id.get(missing) or f"GO {missing}", 0))

    execute_many(
        """
        INSERT INTO dim_grupos_operativos (go_id, nombre, n_sucursales, is_epl_cas, last_synced_at)
        VALUES (%s, %s, %s, TRUE, NOW())
        ON CONFLICT (go_id) DO UPDATE SET
            nombre         = EXCLUDED.nombre,
            n_sucursales   = EXCLUDED.n_sucursales,
            is_epl_cas     = TRUE,
            last_synced_at = NOW()
        """,
        go_rows,
    )

    metrics = {
        "n_locations_api": len(locations),
        "n_in_scope": in_scope,
        "n_upserted": n_upserted,
        "n_gos": len(go_counts),
    }
    log.info("sync_dim_sucursales metrics=%s", metrics)
    return metrics


def get_active_sucursales() -> list[dict[str, Any]]:
    """Lista las sucursales in-scope desde DB."""
    return fetch_all(
        """
        SELECT location_id, nombre, go_id, go_nombre
        FROM dim_sucursales
        WHERE is_active = TRUE
        ORDER BY go_nombre, nombre
        """
    )
