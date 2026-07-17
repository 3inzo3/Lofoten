#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lofoten Hike Window Finder
Traukia Windy Point Forecast API prognozes 6 žygių taškams,
skaičiuoja viršūnės matomumo score (0-100) kiekvienai 3h juostai,
grupuoja į langus ir generuoja docs/index.html.

Paleidimas: WINDY_API_KEY=xxx python fetch_and_build.py
"""

import json
import math
import os
import sys
import time
import datetime as dt
from zoneinfo import ZoneInfo

import requests

# ---------------------------------------------------------------- konfigūracija

OSLO = ZoneInfo("Europe/Oslo")
API_URL = "https://api.windy.com/api/point-forecast/v2"
# Trial/Premium raktai ECMWF neturi — ICON-EU (~7 km) geriausias prieinamas
# modelis Norvegijai; jei jo nepriimtų, krentam į GFS.
MODEL = "iconEu"
FALLBACK_MODEL = "gfs"
MODEL_LABELS = {"iconEu": "ICON-EU", "gfs": "GFS", "ecmwf": "ECMWF"}
USED_MODELS = set()
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "index.html")

# Skrendam 07-23 ryte — po šio laiko langų neberodom
DEADLINE = dt.datetime(2026, 7, 23, 6, 0, tzinfo=OSLO)
# Iki 07-19 bazė Ramberg, po to Reine
BASE_SWITCH = dt.datetime(2026, 7, 19, 12, 0, tzinfo=OSLO)
# "tonight" žygis po šios nakties tampa done
TONIGHT_UNTIL = dt.datetime(2026, 7, 18, 6, 0, tzinfo=OSLO)

HIKES = [
    {"id": 1, "name": "Festvågtinden", "elev_m": 541, "lat": 68.1717, "lon": 14.2208,
     "zone": "Henningsvær", "drive_from_ramberg_min": 60, "drive_from_reine_min": 90,
     "status": "planned", "note": "virš Henningsvær stadiono"},
    {"id": 2, "name": "Fløya", "elev_m": 590, "lat": 68.2449, "lon": 14.5776,
     "zone": "Svolvær", "drive_from_ramberg_min": 80, "drive_from_reine_min": 110,
     "status": "planned", "note": "Djevelporten"},
    {"id": 3, "name": "Offersøykammen", "elev_m": 436, "lat": 68.1545, "lon": 13.5145,
     "zone": "Leknes", "drive_from_ramberg_min": 30, "drive_from_reine_min": 60,
     "status": "done", "note": "PADARYTA 07-16"},
    {"id": 4, "name": "Volandstinden", "elev_m": 457, "lat": 68.0709, "lon": 13.2139,
     "zone": "Fredvang", "drive_from_ramberg_min": 10, "drive_from_reine_min": 40,
     "status": "planned", "note": "Shark Fin, Fredvang tiltai"},
    {"id": 5, "name": "Ryten", "elev_m": 543, "lat": 68.0855, "lon": 13.1426,
     "zone": "Fredvang", "drive_from_ramberg_min": 20, "drive_from_reine_min": 45,
     "status": "planned", "note": "TOP prioritetas, Kvalvika vaizdas, geriausia sunset/vakaras"},
    {"id": 6, "name": "Reinebringen", "elev_m": 448, "lat": 67.9223, "lon": 13.0784,
     "zone": "Reine", "drive_from_ramberg_min": 40, "drive_from_reine_min": 5,
     "status": "tonight", "note": "šįvakar 07-17 naktį, sherpa laiptai"},
    {"id": 7, "name": "Mannen", "elev_m": 400, "lat": 68.2020, "lon": 13.5200,
     "zone": "Haukland", "drive_from_ramberg_min": 40, "drive_from_reine_min": 70,
     "status": "planned", "note": "Haukland/Uttakleiv paplūdimių vaizdai, lengvas"},
    {"id": 8, "name": "Himmeltindan", "elev_m": 962, "lat": 68.1680, "lon": 13.4700,
     "zone": "Haukland", "drive_from_ramberg_min": 40, "drive_from_reine_min": 70,
     "status": "planned", "note": "aukščiausia Vestvågøy viršūnė, rimtas žygis"},
    {"id": 9, "name": "Justadtinden", "elev_m": 738, "lat": 68.1960, "lon": 13.8700,
     "zone": "Leknes", "drive_from_ramberg_min": 50, "drive_from_reine_min": 80,
     "status": "planned", "note": "360° panorama, nuo Hagskaret"},
    {"id": 10, "name": "Nonstinden", "elev_m": 457, "lat": 68.0800, "lon": 13.5600,
     "zone": "Ballstad", "drive_from_ramberg_min": 40, "drive_from_reine_min": 70,
     "status": "planned", "note": "Ballstad fjordų vaizdai"},
    {"id": 11, "name": "Stornappstinden", "elev_m": 740, "lat": 68.0800, "lon": 13.4150,
     "zone": "Napp", "drive_from_ramberg_min": 20, "drive_from_reine_min": 50,
     "status": "planned", "note": "Flakstadøya panorama"},
    {"id": 12, "name": "Nubben", "elev_m": 380, "lat": 68.0970, "lon": 13.2640,
     "zone": "Ramberg", "drive_from_ramberg_min": 5, "drive_from_reine_min": 35,
     "status": "planned", "note": "trumpas vakarinis, Ramberg paplūdimio vaizdas"},
    {"id": 13, "name": "Munkebu / Munken", "elev_m": 775, "lat": 67.9180, "lon": 12.9800,
     "zone": "Sørvågen", "drive_from_ramberg_min": 45, "drive_from_reine_min": 10,
     "status": "planned", "note": "ežerai + Reinefjord vaizdai, ~6-7 h"},
    {"id": 14, "name": "Hermannsdalstinden", "elev_m": 1029, "lat": 67.9300, "lon": 12.9280,
     "zone": "Sørvågen", "drive_from_ramberg_min": 45, "drive_from_reine_min": 10,
     "status": "planned", "note": "aukščiausia Moskenesøya, ilgas ~8-10 h"},
    {"id": 15, "name": "Helvetestinden", "elev_m": 602, "lat": 67.9750, "lon": 12.9350,
     "zone": "Bunes", "drive_from_ramberg_min": 40, "drive_from_reine_min": 5,
     "status": "planned", "note": "reikia kelto iš Reine į Vindstad, Bunes paplūdimys"},
    {"id": 16, "name": "Hoven", "elev_m": 368, "lat": 68.3300, "lon": 14.1200,
     "zone": "Gimsøya", "drive_from_ramberg_min": 70, "drive_from_reine_min": 100,
     "status": "planned", "note": "lengvas, vidurnakčio saulės klasika"},
    {"id": 17, "name": "Tjeldbergtinden", "elev_m": 367, "lat": 68.2220, "lon": 14.5120,
     "zone": "Svolvær", "drive_from_ramberg_min": 75, "drive_from_reine_min": 105,
     "status": "planned", "note": "trumpas, Svolvær/Kabelvåg vaizdai"},
]

WEEKDAYS_LT = ["pirmadienis", "antradienis", "trečiadienis", "ketvirtadienis",
               "penktadienis", "šeštadienis", "sekmadienis"]

# ---------------------------------------------------------------- Windy API

def fetch_point(lat, lon, api_key):
    """Vienas POST vienam taškui. Grąžina žodyną su laiko eilutėmis arba meta išimtį.
    400 atveju prisitaiko: keičia modelį į atsarginį, meta lauk nepalaikomus parametrus."""
    params = ["temp", "dewpoint", "precip", "wind", "windGust",
              "lclouds", "mclouds", "hclouds", "rh", "cbase"]
    model = MODEL
    last_err = None
    for attempt in range(5):
        payload = {"lat": round(lat, 4), "lon": round(lon, 4), "model": model,
                   "parameters": params, "levels": ["surface"], "key": api_key}
        try:
            r = requests.post(API_URL, json=payload, timeout=30)
            if r.status_code == 400:
                if "model must be" in r.text and model != FALLBACK_MODEL:
                    model = FALLBACK_MODEL
                    continue
                bad = [p for p in params if p in r.text]
                if bad and len(bad) < len(params):
                    params = [p for p in params if p not in bad]
                    continue
            if r.status_code >= 400:
                # įtraukiam atsakymo tekstą — kitaip logai nieko nepasako
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            USED_MODELS.add(model)
            return r.json()
        except Exception as e:  # tinklo/API klaida — retry su pauze
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Windy API nepavyko ({lat},{lon}): {last_err}")


def series(data, name):
    """Ištraukia parametro masyvą ('temp' -> 'temp-surface')."""
    for key in (f"{name}-surface", name):
        if key in data:
            return data[key]
    return None


def to_celsius(values, units):
    if values is None:
        return None
    unit = (units or {}).get("temp-surface", "")
    if unit == "K" or (values and values[0] is not None and values[0] > 150):
        return [None if v is None else v - 273.15 for v in values]
    return values

# ---------------------------------------------------------------- vertinimas

def band_score(lclouds, mclouds, precip, wind, gust, rh, cbase, elev):
    """View Score 0-100: viršūnės matomumo tikimybė. hclouds nebaudžiami."""
    score = 100.0
    score -= (lclouds or 0) * 0.9
    if cbase is not None:
        if cbase < elev + 150:
            score -= 40
        elif cbase < elev + 400:
            score -= 15
    score -= (mclouds or 0) * 0.15
    score -= (precip or 0) * 12
    if wind is not None and wind > 8:
        score -= (wind - 8) * 4
    if gust is not None and gust > 14:
        score -= 10
    if rh is not None and lclouds is not None and rh > 95 and lclouds > 60:
        score -= 25
    return max(0.0, min(100.0, score))


def parse_bands(data, elev, now):
    """API atsakymą paverčia į [{t, score}, ...] 3h juostas iki DEADLINE."""
    ts = data.get("ts") or []
    units = data.get("units") or {}
    temp = to_celsius(series(data, "temp"), units)
    dew = to_celsius(series(data, "dewpoint"), units)
    lcl = series(data, "lclouds")
    mcl = series(data, "mclouds")
    rh = series(data, "rh")
    gust = series(data, "gust") or series(data, "windGust")
    cbase = series(data, "cbase")
    precip = series(data, "past3hprecip") or series(data, "precip")
    wu = series(data, "wind_u")
    wv = series(data, "wind_v")

    def at(arr, i):
        return arr[i] if arr is not None and i < len(arr) else None

    bands = []
    for i, ms in enumerate(ts):
        t = dt.datetime.fromtimestamp(ms / 1000, tz=OSLO)
        if t < now - dt.timedelta(hours=3) or t >= DEADLINE:
            continue
        u, v = at(wu, i), at(wv, i)
        wind = math.sqrt(u * u + v * v) if u is not None and v is not None else None

        cb = at(cbase, i)
        if cb is None:
            # proxy: cloud base ~ 125 m * (T - Td); be dew point — vertinam iš rh
            t_c, d_c, rh_i = at(temp, i), at(dew, i), at(rh, i)
            if t_c is not None and d_c is not None:
                cb = max(0.0, 125.0 * (t_c - d_c))
            elif t_c is not None and rh_i is not None:
                cb = max(0.0, 125.0 * (100.0 - rh_i) / 5.0)

        bands.append({
            "t": t,
            "score": band_score(at(lcl, i), at(mcl, i), at(precip, i),
                                wind, at(gust, i), at(rh, i), cb, elev),
        })
    return bands


def find_windows(bands, golden_check):
    """Langas = >=2 iš eilės 3h juostos su score >= 60. Grąžina visų langų sąrašą."""
    windows = []
    run = []
    def flush():
        if len(run) >= 2:
            start = run[0]["t"]
            end = run[-1]["t"] + dt.timedelta(hours=3)
            avg = sum(b["score"] for b in run) / len(run)
            golden = golden_check(start, end)
            disp = min(100, round(avg) + (5 if golden else 0))
            windows.append({"start": start, "end": end, "avg": round(avg),
                            "display": disp, "golden": golden})
        run.clear()

    prev_t = None
    for b in bands:
        contiguous = prev_t is not None and (b["t"] - prev_t) == dt.timedelta(hours=3)
        if b["score"] >= 60 and (not run or contiguous):
            run.append(b)
        elif b["score"] >= 60:
            flush()
            run.append(b)
        else:
            flush()
        prev_t = b["t"]
    flush()
    return windows


def is_golden(start, end):
    """Ar langas kliudo 19:00-01:00 (golden light, vidurnakčio saulė)."""
    t = start
    while t < end:
        if t.hour >= 19 or t.hour < 1:
            return True
        t += dt.timedelta(hours=1)
    return False


def verdict(score):
    if score >= 80:
        return "PUIKUS — eikit", "#22c55e", "#052e16"
    if score >= 60:
        return "GERAS — verta", "#86efac", "#14532d"
    if score >= 40:
        return "RIZIKINGA — 50/50", "#facc15", "#422006"
    return "NEVERTA — viršūnė debesyse", "#f87171", "#450a0a"

# ---------------------------------------------------------------- formatavimas

def day_label(t, now):
    if t.date() == now.date():
        return "šiandien"
    if t.date() == (now + dt.timedelta(days=1)).date():
        return "rytoj"
    return f"{t.strftime('%m-%d')} ({WEEKDAYS_LT[t.weekday()]})"


def fmt_window(w, now):
    return f"{day_label(w['start'], now)} {w['start'].strftime('%H:%M')}–{w['end'].strftime('%H:%M')}"

# ---------------------------------------------------------------- HTML

def build_html(hikes_data, now, stale_note=""):
    base_name = "Ramberg" if now < BASE_SWITCH else "Reine"
    drive_key = "drive_from_ramberg_min" if now < BASE_SWITCH else "drive_from_reine_min"

    # aktyvūs (planned/tonight) ir done
    active, done = [], []
    for h in hikes_data:
        status = h["hike"]["status"]
        if status == "tonight" and now >= TONIGHT_UNTIL:
            status = "done"
        if status == "done":
            done.append(h)
        else:
            active.append(h)

    # rikiavimas: pagal artimiausią gerą langą (kas neturi — gale)
    def next_good(h):
        good = [w for w in h["windows"] if w["display"] >= 60 and w["end"] > now]
        return min((w["start"] for w in good), default=dt.datetime.max.replace(tzinfo=OSLO))
    active.sort(key=next_good)

    # top blokas: geriausias langas artimiausiu 24h
    soon, later = [], []
    for h in active:
        for w in h["windows"]:
            if w["display"] < 60 or w["end"] <= now:
                continue
            (soon if w["start"] <= now + dt.timedelta(hours=24) else later).append((h, w))

    if soon:
        h, w = max(soon, key=lambda x: (x[1]["display"], -x[1]["start"].timestamp()))
        v, _, _ = verdict(w["display"])
        golden = " 🌅" if w["golden"] else ""
        hero = (f"🏔️ <b>{h['hike']['name']}</b> — {fmt_window(w, now)}{golden} — "
                f"score {w['display']} — <b>{v.split('—')[0].strip()}"
                f"{', eikit!' if w['display'] >= 80 else ', verta!'}</b>")
        hero_color = "#22c55e" if w["display"] >= 80 else "#86efac"
    elif later:
        h, w = min(later, key=lambda x: x[1]["start"])
        hero = (f"Artimiausiu metu (24h) gerų langų nėra. Kitas kandidatas: "
                f"<b>{h['hike']['name']}</b> — {fmt_window(w, now)} — score {w['display']}")
        hero_color = "#facc15"
    else:
        hero = "Gerų langų iki išvykimo prognozė kol kas nerodo. Tikrinam kas 3 val. 🤞"
        hero_color = "#f87171"

    cards = []
    for h in active + done:
        hike = h["hike"]
        status = hike["status"]
        is_done = status == "done" or (status == "tonight" and now >= TONIGHT_UNTIL)
        is_tonight = status == "tonight" and now < TONIGHT_UNTIL

        top3 = sorted([w for w in h["windows"] if w["end"] > now],
                      key=lambda w: -w["display"])[:3]
        top3.sort(key=lambda w: w["start"])

        badges = ""
        if h.get("error"):
            badges = '<div class="win" style="background:#450a0a;color:#f87171">⚠️ nėra duomenų (API klaida)</div>'
        elif not top3 and not is_done:
            badges = '<div class="win" style="background:#450a0a;color:#f87171">😕 gerų langų nerasta iki 07-23</div>'
        else:
            for w in top3:
                v, fg, bg = verdict(w["display"])
                golden = " 🌅" if w["golden"] else ""
                badges += (f'<div class="win" style="background:{bg};color:{fg}">'
                           f'<b>{fmt_window(w, now)}</b>{golden} · score {w["display"]} · {v}</div>')

        note = ""
        if not is_done:
            if hike["name"] == "Ryten":
                note = '<div class="note">💡 geriausia vakare (sunset virš Kvalvika)</div>'
            elif hike.get("note"):
                note = f'<div class="note">💡 {hike["note"]}</div>'

        title_prefix = "✅ " if is_done else ("🌙 ŠĮVAKAR: " if is_tonight else "")
        cls = "card done" if is_done else "card"
        body = "" if is_done else badges + note
        cards.append(f"""
    <div class="{cls}">
      <div class="hname">{title_prefix}{hike['name']} <span class="meta">{hike['elev_m']} m · {hike['zone']} · 🚗 {hike[drive_key]} min nuo {base_name}</span></div>
      {body}
    </div>""")

    updated = now.strftime("%Y-%m-%d %H:%M")
    model_txt = "/".join(sorted(MODEL_LABELS.get(m, m) for m in USED_MODELS)) or "—"
    stale_html = f'<div class="stale">⚠️ {stale_note}</div>' if stale_note else ""

    return f"""<!DOCTYPE html>
<html lang="lt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lofoten žygių langai</title>
<style>
  body {{ margin:0; padding:16px; background:#0b1020; color:#e5e7eb;
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
         font-size:18px; line-height:1.45; }}
  .hero {{ background:#111a33; border:2px solid {hero_color}; border-radius:16px;
           padding:18px; font-size:21px; margin-bottom:20px; }}
  .hero-label {{ font-size:13px; letter-spacing:1px; color:#9ca3af; margin-bottom:6px; }}
  .card {{ background:#111a33; border-radius:14px; padding:14px 16px; margin-bottom:14px; }}
  .card.done {{ opacity:0.45; }}
  .hname {{ font-size:20px; font-weight:700; margin-bottom:8px; }}
  .meta {{ font-size:14px; font-weight:400; color:#9ca3af; display:block; margin-top:2px; }}
  .win {{ border-radius:10px; padding:8px 12px; margin:6px 0; font-size:16px; }}
  .note {{ font-size:14px; color:#fbbf24; margin-top:6px; }}
  .stale {{ background:#7f1d1d; color:#fecaca; border-radius:10px; padding:10px 14px;
            margin-bottom:16px; font-size:16px; }}
  .footer {{ margin-top:24px; font-size:12px; color:#6b7280; text-align:center; }}
</style>
</head>
<body>
  {stale_html}
  <div class="hero">
    <div class="hero-label">GERIAUSIAS ARTIMIAUSIAS LANGAS</div>
    {hero}
  </div>
  {''.join(cards)}
  <div class="footer">Atnaujinta: {updated} (Oslo laiku) · Duomenys: Windy {model_txt} ·
  Score = viršūnės matomumo tikimybė · 🌅 = golden light langas</div>
</body>
</html>
"""

# ---------------------------------------------------------------- stale fallback

def mark_stale(reason):
    """API nepasiekiamas — paliekam seną puslapį su įspėjimu viršuje."""
    if not os.path.exists(OUT_PATH):
        html = build_html([{"hike": h, "windows": [], "error": True} for h in HIKES],
                          dt.datetime.now(OSLO),
                          stale_note=f"Nepavyko gauti duomenų: {reason}")
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            f.write(html)
        return
    with open(OUT_PATH, encoding="utf-8") as f:
        html = f.read()
    warn = ('<div class="stale" style="background:#7f1d1d;color:#fecaca;border-radius:10px;'
            'padding:10px 14px;margin-bottom:16px;font-size:16px">'
            '⚠️ DUOMENYS PASENĘ — nepavyko atnaujinti prognozės</div>')
    if "DUOMENYS PASENĘ" not in html:
        html = html.replace("<body>", "<body>\n  " + warn, 1)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            f.write(html)

# ---------------------------------------------------------------- main

def main():
    api_key = os.environ.get("WINDY_API_KEY", "").strip()
    if not api_key:
        print("KLAIDA: nėra WINDY_API_KEY aplinkos kintamojo", file=sys.stderr)
        mark_stale("nėra API rakto")
        sys.exit(1)

    now = dt.datetime.now(OSLO)
    hikes_data = []
    failures = 0
    for hike in HIKES:
        if hike["status"] == "done":
            hikes_data.append({"hike": hike, "windows": [], "error": False})
            continue
        try:
            data = fetch_point(hike["lat"], hike["lon"], api_key)
            bands = parse_bands(data, hike["elev_m"], now)
            windows = find_windows(bands, is_golden)
            hikes_data.append({"hike": hike, "windows": windows, "error": False})
            print(f"OK  {hike['name']}: {len(bands)} juostų, {len(windows)} langų")
        except Exception as e:
            failures += 1
            hikes_data.append({"hike": hike, "windows": [], "error": True})
            print(f"FAIL {hike['name']}: {e}", file=sys.stderr)

    active_count = sum(1 for h in HIKES if h["status"] != "done")
    if failures == active_count:
        mark_stale("Windy API nepasiekiamas")
        print("Visi užklausimai nepavyko — paliktas senas puslapis su įspėjimu", file=sys.stderr)
        sys.exit(1)

    html = build_html(hikes_data, now)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Sugeneruota: {OUT_PATH}")


if __name__ == "__main__":
    main()
