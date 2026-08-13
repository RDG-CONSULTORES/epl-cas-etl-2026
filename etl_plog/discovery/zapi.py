"""Cliente mínimo Zenput v3 para discovery PLOG (urllib, sin deps)."""
import json, time, urllib.request, urllib.error, os

BASE = "https://www.zenput.com/api/v3/"
TOKEN = None

def _token():
    global TOKEN
    if TOKEN: return TOKEN
    env = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    for line in open(env):
        if line.startswith("ZENPUT_TOKEN="):
            TOKEN = line.strip().split("=", 1)[1]
    return TOKEN

def get(path, params=None, retries=3):
    qs = "&".join(f"{k}={v}" for k, v in (params or {}).items())
    url = BASE + path + ("?" + qs if qs else "")
    req = urllib.request.Request(url, headers={"X-API-TOKEN": _token()})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError) as e:
            if i == retries - 1: raise
            time.sleep(2 ** (i + 1))

def get_all(path, params=None, limit=100, max_pages=200, sleep=0.3):
    """Pagina offset/limit hasta agotar (cap offset 10000)."""
    out, offset = [], 0
    params = dict(params or {})
    for _ in range(max_pages):
        params.update({"limit": limit, "offset": offset})
        resp = get(path, params)
        data = resp.get("data", [])
        out.extend(data)
        if not data or len(data) < limit or offset + limit > 10000: break
        offset += limit
        time.sleep(sleep)
    return out
