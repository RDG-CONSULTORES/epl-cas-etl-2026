"""Acceso al catálogo de formularios PLOG (catalogo.json = semilla de config)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CATALOGO = Path(__file__).resolve().parents[1] / "config" / "catalogo.json"

ZONAS = ("nuevo_leon", "laguna", "queretaro")


@lru_cache(maxsize=1)
def cargar() -> dict:
    return json.loads(_CATALOGO.read_text())


def familias() -> dict[str, dict]:
    return cargar()["familias"]


@lru_cache(maxsize=1)
def ft_a_familia() -> dict[int, str]:
    """Mapa form_template_id -> familia (todas las variantes/series/zonas)."""
    out: dict[int, str] = {}
    for fam, e in familias().items():
        fts = e.get("form_templates")
        if isinstance(fts, dict):
            out.update({int(ft): fam for ft in fts})
        elif isinstance(fts, list):
            out.update({int(ft): fam for ft in fts})
        for zfts in (e.get("form_templates_por_zona") or {}).values():
            out.update({int(ft): fam for ft in zfts})
    return out


def todos_los_fts() -> list[int]:
    return sorted(ft_a_familia().keys())
