"""Acuña una API key para un consumidor externo (ej. sistemas EPL / Homero).

La llave en claro se imprime UNA sola vez: cópiala y entrégala por canal seguro.
En la BD solo queda su hash. Para revocar: UPDATE plog.api_keys SET activo=FALSE WHERE id=...

Uso:
  python -m etl_plog.scripts.mint_api_key "EPL - Homero (sistemas)"
  python -m etl_plog.scripts.mint_api_key "EPL - Homero" --zonas nuevo_leon,laguna
  python -m etl_plog.scripts.mint_api_key "EPL - Homero" --notas "integración Zenput"
"""
from __future__ import annotations

import argparse

from etl_plog.api import apikeys


def main() -> None:
    ap = argparse.ArgumentParser(description="Acuña una API key read-only para /api/v1")
    ap.add_argument("etiqueta", help='Nombre del consumidor, ej. "EPL - Homero (sistemas)"')
    ap.add_argument("--zonas", help="Acota por zonas (coma-separadas). Sin esto = todas.")
    ap.add_argument("--notas", help="Nota libre (contexto de la integración).")
    ap.add_argument("--por", default="admin", help="Quién la crea (para la bitácora).")
    args = ap.parse_args()

    zonas = [z.strip() for z in args.zonas.split(",")] if args.zonas else None
    r = apikeys.crea_api_key(args.etiqueta, zonas=zonas, creado_por=args.por, notas=args.notas)

    print("\n=== API KEY CREADA (guárdala, solo se muestra esta vez) ===")
    print(f"  id       : {r['id']}")
    print(f"  etiqueta : {r['etiqueta']}")
    print(f"  zonas    : {zonas or 'todas'}")
    print(f"  API KEY  : {r['llave']}")
    print("  Enví­ala por canal seguro. En la BD solo queda el hash.\n")


if __name__ == "__main__":
    main()
