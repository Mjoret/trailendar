#!/usr/bin/env python3
"""Crawler Trailendar : découvre les trails par département, lit chaque fiche,
et met à jour trails.json. Nécessite FIRECRAWL_API_KEY.
Variables : DISCOVER=1 (liste les départements), MAX_EVENTS (budget de fiches/run),
ONLY_DEPS="74,73" (limiter à certains départements, utile pour tester),
EXCLUDE_DEPS="971,972,973,974,976,2A,2B" (départements à ignorer)."""
import os, re, json, sys, time, unicodedata, datetime as dt
from urllib.parse import urljoin, urlparse
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "trails.json")
REPORT = os.path.join(ROOT, "crawl-report.json")
DEPS = json.load(open(os.path.join(ROOT, "data", "departments.json"), encoding="utf-8"))
KEY = os.environ.get("FIRECRAWL_API_KEY")
API = "https://api.firecrawl.dev/v1"
BASE = "https://fr.milesrepublic.com"
MAX_EVENTS = int(os.environ.get("MAX_EVENTS", "120"))
DISCOVER = os.environ.get("DISCOVER") == "1"
ONLY = [d.strip() for d in os.environ.get("ONLY_DEPS", "").split(",") if d.strip()]
EXCLUDE = {d.strip() for d in os.environ.get("EXCLUDE_DEPS", "").split(",") if d.strip()}
MAX_PAGES = 6
TODAY = dt.date.today()
MOIS = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return "".join(c if c.isalnum() else "-" for c in s).strip("-").replace("--", "-")

def fc(path, body, tries=3):
    err = None
    for i in range(tries):
        try:
            r = requests.post(f"{API}/{path}", json=body, timeout=120,
                              headers={"Authorization": f"Bearer {KEY}"})
            if r.status_code == 429:
                time.sleep(10 * (i + 1)); continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            err = e; time.sleep(3)
    print("ECHEC", path, body.get("url"), err, file=sys.stderr)
    return None

def extract(url, schema, prompt):
    j = fc("scrape", {"url": url, "formats": ["json"],
                      "jsonOptions": {"schema": schema, "prompt": prompt}})
    return ((j or {}).get("data") or {}).get("json")

LIST_SCHEMA = {"type": "object", "properties": {"events": {"type": "array", "items": {
    "type": "object", "properties": {
        "name": {"type": "string"}, "month": {"type": "integer"}, "year": {"type": "integer"},
        "city": {"type": "string"}, "url": {"type": "string"}}, "required": ["name"]}}}}
LIST_PROMPT = ("Liste tous les trails/courses de la page. month = mois de 1 à 12, year = année, "
               "url = lien de la fiche de l'événement. Ne rien inventer, null si absent.")

EVENT_SCHEMA = {"type": "object", "properties": {
    "name": {"type": "string"}, "date_iso": {"type": "string"}, "date_text": {"type": "string"},
    "city": {"type": "string"}, "official_website": {"type": "string"},
    "registration_url": {"type": "string"},
    "races": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"}, "distance_km": {"type": "number"},
        "elevation_gain_m": {"type": "number"}, "elevation_loss_m": {"type": "number"},
        "start_time": {"type": "string"}}}},
    "registration_dates_stated": {"type": "boolean"}, "registration_dates_text": {"type": "string"}}}
EVENT_PROMPT = ("Réponds uniquement avec ce qui est écrit sur la page, null si absent. "
                "date_iso = AAAA-MM-JJ de la prochaine édition. start_time = HH:MM. "
                "registration_dates_stated = true UNIQUEMENT si une date d'ouverture ou de clôture "
                "des inscriptions de la prochaine édition est écrite ; registration_dates_text la recopie en une phrase.")
REG_SCHEMA = {"type": "object", "properties": {
    "registration_dates_stated": {"type": "boolean"}, "registration_dates_text": {"type": "string"}}}
REG_PROMPT = ("Cette page indique-t-elle une date d'ouverture ou de clôture des inscriptions "
              "de la prochaine édition ? true seulement si une date est écrite. Ne rien déduire.")

def interval_days(e):
    iso = e.get("iso")
    if iso:
        d = (dt.date.fromisoformat(iso) - TODAY).days
    else:
        d = ((e["m"] + 1 - TODAY.month) % 12) * 30
    return 1 if d <= 60 else 7 if d <= 180 else 30

def due(e):
    if e.get("manual"): return False
    chk = e.get("chk")
    return not chk or (TODAY - dt.date.fromisoformat(chk)).days >= interval_days(e)

def fix_url(u, base=None):
    """Retourne une URL absolue http(s) ou None (gère '//x', 'www.x.fr/...', '/chemin')."""
    if not u or not isinstance(u, str): return None
    u = u.strip()
    if u.startswith("//"): u = "https:" + u
    p = urlparse(u)
    if p.scheme in ("http", "https") and p.netloc: return u
    if p.scheme: return None
    if re.match(r"^[^\s/?#]+\.[a-z]{2,}([/?#]|$)", u): return "https://" + u
    return urljoin(base, u) if base else None

def num(x):
    return round(x) if isinstance(x, (int, float)) else None

def build(dep, listed, det, reg):
    iso = (det.get("date_iso") or "")[:10]
    try: dt.date.fromisoformat(iso)
    except ValueError: iso = None
    m = int(iso[5:7]) - 1 if iso else (listed.get("month") or 1) - 1
    year = int(iso[:4]) if iso else listed.get("year") or TODAY.year
    races = []
    for r in det.get("races") or []:
        km = r.get("distance_km")
        if not isinstance(km, (int, float)) or km <= 0: continue
        races.append([r.get("name") or f"{km:g} km", km, num(r.get("elevation_gain_m")),
                      num(r.get("elevation_loss_m")), r.get("start_time")])
    races.sort(key=lambda r: -r[1])
    stated = bool(reg.get("registration_dates_stated"))
    text = (reg.get("registration_dates_text") or "").strip()[:160]
    return {"id": f"{dep}-{slug(det.get('name') or listed['name'])}", "dep": dep,
            "n": det.get("name") or listed["name"], "m": m, "iso": iso,
            "lieu": det.get("city") or listed.get("city") or DEPS[dep],
            "date": (det.get("date_text") or f"{MOIS[m]} {year}"),
            "url": fix_url(det.get("registration_url"), listed.get("url")), "lurl": None,
            "src": "milesrepublic.com" + (" + site officiel" if det.get("official_website") else ""),
            "reg": {"k": 1 if stated and text else 0,
                    "t": text if stated and text else "Aucune date d’inscription communiquée trouvée",
                    "c": 1},
            "r": races, "chk": TODAY.isoformat()}

def main():
    if not KEY: sys.exit("FIRECRAWL_API_KEY manquante")
    db = json.load(open(DATA, encoding="utf-8"))
    ev = {e["id"]: e for e in db["events"]}
    report = {"date": TODAY.isoformat(), "listing_errors": [], "detail_errors": [], "new": 0, "updated": 0}
    todo = []  # (dep, listed)
    deps = [d for d in (ONLY or list(DEPS)) if d not in EXCLUDE]
    if DISCOVER:
        for dep in deps:
            if dep not in DEPS: continue
            found = 0
            for p in range(1, MAX_PAGES + 1):
                url = f"{BASE}/trail/{slug(DEPS[dep])}" + (f"?page={p}" if p > 1 else "")
                out = extract(url, LIST_SCHEMA, LIST_PROMPT)
                items = (out or {}).get("events") or []
                if not items: break
                for it in items:
                    if it.get("url"):
                        it["url"] = urljoin(BASE, it["url"]); todo.append((dep, it)); found += 1
                time.sleep(1)
            if not found: report["listing_errors"].append({"dep": dep, "name": DEPS[dep]})
    else:
        for e in ev.values():
            if due(e) and e.get("src_url") and e["dep"] not in EXCLUDE and (not ONLY or e["dep"] in ONLY):
                todo.append((e["dep"], {"name": e["n"], "url": e["src_url"], "month": e["m"] + 1}))
    seen, queue = set(), []
    for dep, it in todo:
        if it["url"] in seen: continue
        seen.add(it["url"])
        existing = next((e for e in ev.values() if e.get("src_url") == it["url"]), None)
        if existing and not due(existing): continue
        if existing and existing.get("manual"): continue
        queue.append((dep, it))
    queue.sort(key=lambda x: (x[1].get("year") or 9999, x[1].get("month") or 13))
    for dep, it in queue[:MAX_EVENTS]:
        det = extract(it["url"], EVENT_SCHEMA, EVENT_PROMPT)
        if not det:
            report["detail_errors"].append(it["url"]); continue
        reg = det
        if not det.get("registration_dates_stated"):
            site = fix_url(det.get("registration_url"), it["url"]) or fix_url(det.get("official_website"), it["url"])
            if site:
                reg = extract(site, REG_SCHEMA, REG_PROMPT) or det
        e = build(dep, it, det, reg)
        e["src_url"] = it["url"]
        old = ev.get(e["id"])
        if old and old.get("manual"): continue
        report["updated" if old else "new"] += 1
        ev[e["id"]] = e
        time.sleep(1)
    keep = [e for e in ev.values() if e.get("manual") or not e.get("iso") or e["iso"] >= TODAY.isoformat()]
    keep.sort(key=lambda e: (e["dep"], e["m"], e["n"]))
    json.dump({"updated": TODAY.isoformat(), "events": keep}, open(DATA, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(report, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}))

if __name__ == "__main__":
    main()
