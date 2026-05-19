#!/usr/bin/env python3
"""Re-backfill MASIVO: pagina 10K submissions por activity UNA vez,
reparte a daily_compliance para todo el rango cubierto por la data.

Cubrir ~14 meses de history (lo que cabe en 10K = ~2025-03 a 2026-05).

Reglas:
- Bucket por smetadata.date_created_local (= date_due, "task date")
- on_time si date_completed_local hour está en ventana de la activity
- late si fuera de ventana (antes o después)
- No fabricar missed (Zenput no crea task → no row)
- Solo procesar sucursales con tag EPL CAS (has_epl_cas_tag=true)
"""
import urllib.request, json, datetime as dt, sys, os, time
import psycopg
from collections import defaultdict

TOKEN = open('/Users/robertodavila/.epl-cas-secrets/zenput_token.txt').read().strip()
DB_URL = open('/Users/robertodavila/.epl-cas-secrets/operacion_diaria_DATABASE_URL.txt').read().strip()

# (activity_id, form_key, project_id, form_template_id, window_start_hour, window_end_hour)
ACTIVITIES = [
    (864763, 'apertura', 511091345, 877142,  7, 11),
    (864761, 'entrega',  511091348, 877140, 14, 17),
    (864762, 'cierre',   511091349, 877141, 19, 23),
]

LOG = open('/tmp/backfill_full.log', 'a')
def log(msg):
    line = f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.write(line + "\n")
    LOG.flush()

def fetch_all_submissions(activity_id):
    out = []
    offset = 0
    while offset < 10000:
        url = (f"https://www.zenput.com/api/v3/submissions/?"
               f"activity_id={activity_id}&limit=100&offset={offset}")
        req = urllib.request.Request(url, headers={'X-API-TOKEN': TOKEN})
        try:
            r = urllib.request.urlopen(req, timeout=30)
            d = json.loads(r.read())
        except Exception as e:
            log(f"  ERR offset={offset}: {e}")
            time.sleep(5)
            continue
        items = d.get('data', [])
        if not items:
            break
        out.extend(items)
        if len(items) < 100:
            break
        offset += 100
        if offset % 1000 == 0:
            log(f"    progress activity={activity_id} offset={offset}")
    return out

def parse_iso(ts):
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None

def main():
    log("=== BACKFILL FULL START ===")
    t0 = time.time()

    # Get active sucursales (EPL CAS tag)
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT location_id FROM operacion_diaria.dim_sucursales "
                        "WHERE has_epl_cas_tag = true")
            active_ids = {row[0] for row in cur.fetchall()}
    log(f"Active sucursales (EPL CAS): {len(active_ids)}")

    # Collect rows per activity
    all_rows = {}  # (sucursal_id, day, form_key) -> row
    stats = defaultdict(int)

    for act_id, form_key, proj_id, tmpl_id, win_start, win_end in ACTIVITIES:
        log(f"\n--- {form_key.upper()} act={act_id} ---")
        t = time.time()
        subs = fetch_all_submissions(act_id)
        log(f"  fetched {len(subs)} submissions in {time.time()-t:.1f}s")

        kept = 0
        for s in subs:
            meta = s.get('smetadata') or {}
            loc = meta.get('location') or {}
            loc_id = loc.get('id')
            if loc_id not in active_ids:
                continue

            created_local = parse_iso(meta.get('date_created_local'))
            if not created_local:
                continue
            day = created_local.date()

            completed_local = parse_iso(meta.get('date_completed_local'))
            if not completed_local:
                # Submission sin completar → skipear (no fabricar nada)
                continue

            # CLASIFICACIÓN POR FECHA + HORA:
            # - completed otro día → Zenput la auto-archivó como Cut/Failed → missed
            # - completed mismo día, dentro de ventana → on_time
            # - completed mismo día, fuera de ventana → late
            if completed_local.date() != day:
                status, score = 'missed', 0.0
            else:
                h = completed_local.hour
                if win_start <= h < win_end:
                    status, score = 'on_time', 1.0
                else:
                    status, score = 'late', 0.5

            key = (loc_id, day, form_key)
            # Priority: on_time(3) > late(2) > missed(1)
            PRIO = {'on_time': 3, 'late': 2, 'missed': 1}
            prev = all_rows.get(key)
            if prev is None:
                all_rows[key] = {
                    'sucursal_id': loc_id, 'day': day, 'form_key': form_key,
                    'project_id': proj_id, 'form_template_id': tmpl_id,
                    'status': status, 'score': score,
                    'submission_id': s.get('id'),
                    'task_id': (meta.get('task') or {}).get('id'),
                    'completed_at': completed_local,
                }
                kept += 1
            elif PRIO[status] > PRIO[prev['status']]:
                prev['status'] = status
                prev['score'] = score
                prev['submission_id'] = s.get('id')
                prev['completed_at'] = completed_local
        log(f"  rows kept: {kept}")
        stats[form_key] = kept

    log(f"\nTotal rows in memory: {len(all_rows)}")
    by_status = defaultdict(int)
    by_year = defaultdict(int)
    for r in all_rows.values():
        by_status[r['status']] += 1
        by_year[r['day'].year] += 1
    log(f"By status: {dict(by_status)}")
    log(f"By year: {dict(by_year)}")

    # DELETE all rows in date range covered, then INSERT fresh.
    # Source of truth = los submissions clasificados arriba.
    log("\n--- DELETE + INSERT (fresh) ---")
    rows = list(all_rows.values())
    min_day = min(r['day'] for r in rows)
    max_day = max(r['day'] for r in rows)
    log(f"  Date range: {min_day} a {max_day} ({len(rows)} rows)")

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            # Solo borramos rows que provienen de los 3 form_keys EPL CAS
            # para sucursales activas (las del catálogo EPL CAS).
            cur.execute("""
                DELETE FROM operacion_diaria.daily_compliance
                WHERE day BETWEEN %s AND %s
                  AND form_key IN ('apertura','entrega','cierre')
                  AND sucursal_id IN (
                      SELECT location_id FROM operacion_diaria.dim_sucursales
                      WHERE has_epl_cas_tag = true
                  )
            """, (min_day, max_day))
            deleted = cur.rowcount
            log(f"  deleted {deleted} pre-existing rows in range")

            sql_insert = """
                INSERT INTO operacion_diaria.daily_compliance
                    (sucursal_id, day, form_key, project_id, form_template_id,
                     status, score, submission_id, task_id, completed_at, last_updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
            """
            total = 0
            for i in range(0, len(rows), 500):
                batch = rows[i:i+500]
                params = [(r['sucursal_id'], r['day'], r['form_key'], r['project_id'],
                           r['form_template_id'], r['status'], r['score'],
                           r['submission_id'], r['task_id'], r['completed_at'])
                          for r in batch]
                cur.executemany(sql_insert, params)
                total += len(batch)
            conn.commit()
            log(f"  inserted {total} fresh rows")

    elapsed = time.time() - t0
    log(f"\n=== DONE in {elapsed:.1f}s ({elapsed/60:.1f} min) ===")
    LOG.close()

if __name__ == "__main__":
    main()
