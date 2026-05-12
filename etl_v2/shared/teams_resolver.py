"""Resolver de GO (Grupo Operativo) a partir de la cadena de teams.

API Zenput entrega `location.teams` solo con el team hoja. Hay que subir la
cadena de `parent.id` hasta encontrar uno cuyo `parent.id == EPL_TEAMS_ROOT`.
Ese ancestro inmediato es el GO de la sucursal.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

EPL_TEAMS_ROOT = 115095  # team "El Pollo Loco México"

EPL_CAS_GO_IDS = {
    115097,  # TEPEYAC
    115098,  # EXPO
    115100,  # OGAS
    115101,  # EFM
    115102,  # RAP
    115103,  # CRR
    115104,  # TEC
    115105,  # EPL SO
    115108,  # GRUPO SALTILLO
    115109,  # OCHTER Tampico
    115110,  # GRUPO CANTERA ROSA (MORELIA)
    115111,  # GRUPO MATAMOROS
    115112,  # GRUPO PIEDRAS NEGRAS
    115113,  # GRUPO CENTRITO
    115114,  # GRUPO SABINAS HIDALGO
    115115,  # GRUPO RIO BRAVO
    115116,  # GRUPO NUEVO LAREDO (RUELAS)
    123266,  # Grupo CADE
}

# GOs explícitamente excluidos del scope EPL CAS
EXCLUDED_GO_IDS = {115099, 115106, 115107}  # PLOG NL, PLOG Laguna, PLOG Queretaro


def build_team_tree(teams: list[dict]) -> dict[int, int | None]:
    """Retorna map {team_id → go_id ancestro} para todos los teams.

    Si un team no rastrea hasta EPL_TEAMS_ROOT, retorna None.
    """
    team_by_id = {t["id"]: t for t in teams}
    cache: dict[int, int | None] = {}

    def resolve_go(team_id: int, seen: set[int] | None = None) -> int | None:
        if team_id in cache:
            return cache[team_id]
        seen = seen or set()
        if team_id in seen:
            return None
        seen.add(team_id)
        t = team_by_id.get(team_id)
        if not t:
            cache[team_id] = None
            return None
        parent_id = (t.get("parent") or {}).get("id")
        if parent_id == EPL_TEAMS_ROOT:
            cache[team_id] = team_id
            return team_id
        if not parent_id:
            cache[team_id] = None
            return None
        result = resolve_go(parent_id, seen)
        cache[team_id] = result
        return result

    return {t["id"]: resolve_go(t["id"]) for t in teams}


def resolve_location_go(location: dict, team_to_go: dict[int, int | None]
                        ) -> tuple[int | None, str | None]:
    """Dado un location y el mapa team→go, retorna (go_id, go_nombre)."""
    teams = location.get("teams") or []
    for t in teams:
        tid = t.get("id") if isinstance(t, dict) else t
        if tid is None:
            continue
        go_id = team_to_go.get(tid)
        if go_id and go_id in EPL_CAS_GO_IDS:
            return go_id, t.get("name") if isinstance(t, dict) else None
    return None, None


def is_epl_cas_go(go_id: int | None) -> bool:
    return go_id is not None and go_id in EPL_CAS_GO_IDS
