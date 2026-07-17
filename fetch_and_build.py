#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lofoten Hike Window Finder
Traukia Open-Meteo prognozes (4 modeliai: MEPS, ECMWF, ICON-EU, GFS)
žygių taškams, skaičiuoja viršūnės matomumo score (0-100) kiekvienai
valandai kaip modelių vidurkį, grupuoja į langus ir generuoja index.html.

Paleidimas: python fetch_and_build.py  (rakto nereikia)
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
# Open-Meteo — nemokamas, be rakto, keli modeliai vienu užklausimu.
# M = MEPS/MET Nordic (1 km, norvegų), E = ECMWF IFS, I = ICON-EU, G = GFS.
OM_URL = "https://api.open-meteo.com/v1/forecast"
OM_MODELS = [("metno_seamless", "M"), ("ecmwf_ifs025", "E"),
             ("icon_eu", "I"), ("gfs_seamless", "G")]
OM_VARS = ["temperature_2m", "dew_point_2m", "relative_humidity_2m",
           "cloud_cover_low", "cloud_cover_mid", "precipitation",
           "wind_speed_10m", "wind_gusts_10m"]
_BASE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(_BASE, "docs", "index.html")
# Rašom ir į repo šaknį — tada Pages veikia nesvarbu, ar folderis / ar /docs
ROOT_PATH = os.path.join(_BASE, "index.html")


def write_html(html):
    for path in (OUT_PATH, ROOT_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

# Skrendam 07-23 ryte — po šio laiko langų neberodom
DEADLINE = dt.datetime(2026, 7, 23, 6, 0, tzinfo=OSLO)
# Langai rodomi tik nuo šio laiko (ankstesni intervalai nebeaktualūs)
DISPLAY_FROM = dt.datetime(2026, 7, 17, 20, 0, tzinfo=OSLO)
# Iki 07-19 bazė Ramberg, po to Reine
BASE_SWITCH = dt.datetime(2026, 7, 19, 12, 0, tzinfo=OSLO)
# "tonight" žygis po šios nakties tampa done
TONIGHT_UNTIL = dt.datetime(2026, 7, 18, 6, 0, tzinfo=OSLO)

HIKES = [
    {"id": 1, "name": "Festvågtinden", "elev_m": 541, "lat": 68.1717, "lon": 14.2208,
     "zone": "Henningsvær", "drive_from_ramberg_min": 60, "drive_from_reine_min": 90,
     "status": "planned", "prio": 1, "note": "D2 · stadionas, Henningsvær zona"},
    {"id": 2, "name": "Fløya", "elev_m": 590, "lat": 68.2449, "lon": 14.5776,
     "zone": "Svolvær", "drive_from_ramberg_min": 80, "drive_from_reine_min": 110,
     "status": "planned", "prio": 2, "note": "D3 · Djevelporten, virš Svolvær"},
    {"id": 3, "name": "Offersøykammen", "elev_m": 436, "lat": 68.1545, "lon": 13.5145,
     "zone": "Leknes", "drive_from_ramberg_min": 30, "drive_from_reine_min": 60,
     "status": "done", "prio": 3, "note": "D4 · PADARYTA 07-16"},
    {"id": 4, "name": "Volandstinden", "elev_m": 457, "lat": 68.0709, "lon": 13.2139,
     "zone": "Fredvang", "drive_from_ramberg_min": 10, "drive_from_reine_min": 40,
     "status": "planned", "prio": 4, "note": "D5 · Shark Fin, kartu su Haukland + Uttakleiv"},
    {"id": 5, "name": "Ryten", "elev_m": 543, "lat": 68.0855, "lon": 13.1426,
     "zone": "Fredvang", "drive_from_ramberg_min": 20, "drive_from_reine_min": 45,
     "status": "planned", "prio": 5, "note": "D8 · TOP · RYTOJ NAKTĮ · sunset virš Kvalvika"},
    {"id": 6, "name": "Reinebringen", "elev_m": 448, "lat": 67.9223, "lon": 13.0784,
     "zone": "Reine", "drive_from_ramberg_min": 40, "drive_from_reine_min": 5,
     "status": "planned", "prio": 6, "note": "D9 · sunrise timing · ~1600 sherpa laiptų"},
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

# ---------------------------------------------------------------- Open-Meteo API

def fetch_point(lat, lon):
    """GET vienam taškui — visi modeliai vienu užklausimu."""
    params = {
        "latitude": round(lat, 4), "longitude": round(lon, 4),
        "hourly": ",".join(OM_VARS),
        "models": ",".join(m for m, _ in OM_MODELS),
        "timezone": "UTC", "forecast_days": 7, "wind_speed_unit": "ms",
    }
    last_err = None
    for attempt in range(4):
        try:
            r = requests.get(OM_URL, params=params, timeout=30)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:250]}")
            return r.json()
        except Exception as e:  # tinklo/API klaida — retry su pauze
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Open-Meteo nepavyko ({lat},{lon}): {last_err}")

# ---------------------------------------------------------------- vertinimas

def band_score(lclouds, mclouds, precip, wind, gust, rh, cbase, elev, fog=None):
    """View Score 0-100: viršūnės matomumo tikimybė. hclouds nebaudžiami."""
    score = 100.0
    low = lclouds or 0
    score -= low * 0.9
    # cloud base bauda tik kai žemų debesų realiai yra — kitaip proxy
    # (125×(T−Td)) prie vandenyno visada rodo "žemai" net giedrą dieną
    if cbase is not None and low >= 30:
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
    if fog is not None:
        if fog > 40:
            score -= 25
    elif rh is not None and lclouds is not None and rh > 95 and lclouds > 60:
        score -= 25
    return max(0.0, min(100.0, score))


def parse_bands(data, elev, now):
    """Open-Meteo atsakymą paverčia į valandines juostas su per-modelio score."""
    h = data.get("hourly") or {}
    times = h.get("time") or []

    def col(var, model):
        return h.get(f"{var}_{model}") or h.get(var)

    def at(arr, i):
        v = arr[i] if arr is not None and i < len(arr) else None
        return v

    bands = []
    for i, ts in enumerate(times):
        t = dt.datetime.fromisoformat(ts).replace(tzinfo=dt.timezone.utc).astimezone(OSLO)
        if t < now - dt.timedelta(hours=1) or t < DISPLAY_FROM or t >= DEADLINE:
            continue
        per_model = {}
        lcls, prs, winds = [], [], []
        for model, letter in OM_MODELS:
            lcl = at(col("cloud_cover_low", model), i)
            if lcl is None:  # modelis šiam laikui duomenų nebeturi
                continue
            mcl = at(col("cloud_cover_mid", model), i)
            rh = at(col("relative_humidity_2m", model), i)
            pr = at(col("precipitation", model), i) or 0.0
            wind = at(col("wind_speed_10m", model), i)
            gust = at(col("wind_gusts_10m", model), i)
            t_c = at(col("temperature_2m", model), i)
            d_c = at(col("dew_point_2m", model), i)
            cb = None
            if t_c is not None and d_c is not None:
                cb = max(0.0, 125.0 * (t_c - d_c))
            elif t_c is not None and rh is not None:
                cb = max(0.0, 125.0 * (100.0 - rh) / 5.0)
            s = band_score(lcl, mcl, pr * 3.0, wind, gust, rh, cb, elev)
            per_model[letter] = round(s)
            lcls.append(lcl); prs.append(pr); winds.append(wind or 0)
        if not per_model:
            continue
        bands.append({
            "t": t, "dur": 1,
            "score": sum(per_model.values()) / len(per_model),
            "models": per_model,
            "lcl": sum(lcls) / len(lcls),
            "precip": sum(prs) / len(prs),
            "wind": sum(winds) / len(winds),
        })
    return bands


def find_windows(bands, golden_check):
    """Langas = ištisinis laikotarpis su score >= 60, trunkantis >= 3 val."""
    windows = []
    run = []

    def flush():
        if run:
            start = run[0]["t"]
            end = run[-1]["t"] + dt.timedelta(hours=run[-1]["dur"])
            if end - start >= dt.timedelta(hours=3):
                avg = sum(b["score"] for b in run) / len(run)
                golden = golden_check(start, end)
                disp = min(100, round(avg) + (5 if golden else 0))
                windows.append({"start": start, "end": end, "avg": round(avg),
                                "display": disp, "golden": golden})
        run.clear()

    prev_end = None
    for b in bands:
        contiguous = prev_end is not None and b["t"] == prev_end
        if b["score"] >= 60 and (not run or contiguous):
            run.append(b)
        elif b["score"] >= 60:
            flush()
            run.append(b)
        else:
            flush()
        prev_end = b["t"] + dt.timedelta(hours=b["dur"])
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

    # iki kada realiai siekia gauti duomenys (trial raktas duoda ~48-72h)
    horizon = max((b["t"] + dt.timedelta(hours=b["dur"]) for h in hikes_data
                   for b in h.get("bands", [])), default=None)
    horizon_txt = f"{day_label(horizon, now)} {horizon.strftime('%H:%M')}" if horizon else "—"

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
        hero = f"Prognozės ribose (iki {horizon_txt}) gerų langų nėra. Atnaujinam kas 3 val. 🤞"
        hero_color = "#f87171"

    main_list = sorted((h for h in hikes_data if h["hike"].get("prio")),
                       key=lambda x: x["hike"]["prio"])
    rest = ([h for h in active if not h["hike"].get("prio")]
            + [h for h in done if not h["hike"].get("prio")])

    cards = []
    for h in main_list + rest:
        if rest and h is rest[0]:
            cards.append('<div class="seclbl">PAPILDOMI ŽYGIAI</div>')
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
            badges = f'<div class="win" style="background:#450a0a;color:#f87171">😕 gerų langų nerasta (prognozė iki {horizon_txt})</div>'
        else:
            for w in top3:
                v, fg, bg = verdict(w["display"])
                golden = " 🌅" if w["golden"] else ""
                badges += (f'<div class="win" style="background:{bg};color:{fg}">'
                           f'<b>{fmt_window(w, now)}</b>{golden} · score {w["display"]} · {v}</div>')

        # Juostelė iki pat išvykimo: kiekvienos valandos score,
        # sugrupuota pagal dienas — matosi ir tarpiniai 40-59 ("rizikinga")
        strip = ""
        if not is_done:
            days = {}
            for b in h.get("bands", []):
                if b["t"] + dt.timedelta(hours=b["dur"]) <= now:
                    continue
                days.setdefault(b["t"].date(), []).append(b)
            for day, bs in sorted(days.items()):
                cells = ""
                for b in bs:
                    _, fg, bg = verdict(b["score"])
                    # priežastys po score: žemi debesys visada, lietus/vėjas kai reikšmingi
                    why = f'☁{round(b.get("lcl") or 0)}%'
                    if (b.get("precip") or 0) >= 0.1:
                        why += f' 🌧{b["precip"]:.1f}'
                    if (b.get("wind") or 0) > 8:
                        why += f' 💨{round(b["wind"])}'
                    mm = " ".join(f"{k}{v}" for k, v in b.get("models", {}).items())
                    cells += (f'<span class="b" style="background:{bg};color:{fg}">'
                              f'{b["t"].strftime("%H:%M")}<br><b>{round(b["score"])}</b>'
                              f'<br><span class="x">{why}</span>'
                              f'<br><span class="m">{mm}</span></span>')
                lbl = day_label(bs[0]["t"], now).capitalize()
                strip += f'<div class="striplbl">{lbl}</div><div class="strip">{cells}</div>'

        note = ""
        if not is_done and hike.get("note"):
            note = f'<div class="note">💡 {hike["note"]}</div>'

        title_prefix = "✅ " if is_done else ("🌙 ŠĮVAKAR: " if is_tonight else "")
        cls = "card done" if is_done else "card"
        body = "" if is_done else badges + strip + note
        cards.append(f"""
    <div class="{cls}">
      <div class="hname">{title_prefix}{hike['name']} <span class="meta">{hike['elev_m']} m · {hike['zone']} · 🚗 {hike[drive_key]} min nuo {base_name}</span></div>
      {body}
    </div>""")

    updated = now.strftime("%Y-%m-%d %H:%M")
    model_txt = "Open-Meteo · 4 modelių vidurkis: M=MEPS E=ECMWF I=ICON-EU G=GFS"
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
  .striplbl {{ font-size:12px; color:#9ca3af; margin-top:8px; }}
  .strip {{ display:flex; flex-wrap:wrap; gap:4px; margin-top:4px; }}
  .b {{ border-radius:6px; padding:3px 7px; font-size:13px; line-height:1.25;
       text-align:center; min-width:44px; }}
  .x {{ font-size:10px; opacity:0.85; }}
  .m {{ font-size:9px; opacity:0.7; letter-spacing:0.5px; }}
  .stale {{ background:#7f1d1d; color:#fecaca; border-radius:10px; padding:10px 14px;
            margin-bottom:16px; font-size:16px; }}
  .seclbl {{ font-size:13px; letter-spacing:2px; color:#9ca3af; margin:22px 0 10px; }}
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
  <div class="footer">Atnaujinta: {updated} (Oslo laiku) · Duomenys: {model_txt} ·
  Score = viršūnės matomumo tikimybė · 🌅 = golden light · ☁ žemi debesys % · 🌧 mm · 💨 m/s ·
  Prognozė siekia: {horizon_txt}</div>
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
        write_html(html)
        return
    with open(OUT_PATH, encoding="utf-8") as f:
        html = f.read()
    warn = ('<div class="stale" style="background:#7f1d1d;color:#fecaca;border-radius:10px;'
            'padding:10px 14px;margin-bottom:16px;font-size:16px">'
            '⚠️ DUOMENYS PASENĘ — nepavyko atnaujinti prognozės</div>')
    if "DUOMENYS PASENĘ" not in html:
        html = html.replace("<body>", "<body>\n  " + warn, 1)
    write_html(html)

# ---------------------------------------------------------------- main

def main():
    now = dt.datetime.now(OSLO)
    hikes_data = []
    failures = 0
    for hike in HIKES:
        if hike["status"] == "done":
            hikes_data.append({"hike": hike, "windows": [], "error": False})
            continue
        try:
            data = fetch_point(hike["lat"], hike["lon"])
            bands = parse_bands(data, hike["elev_m"], now)
            windows = find_windows(bands, is_golden)
            hikes_data.append({"hike": hike, "windows": windows, "bands": bands,
                               "error": False})
            print(f"OK  {hike['name']}: {len(bands)} juostų, {len(windows)} langų")
        except Exception as e:
            failures += 1
            hikes_data.append({"hike": hike, "windows": [], "error": True})
            print(f"FAIL {hike['name']}: {e}", file=sys.stderr)

    active_count = sum(1 for h in HIKES if h["status"] != "done")
    if failures == active_count:
        mark_stale("Open-Meteo nepasiekiamas")
        print("Visi užklausimai nepavyko — paliktas senas puslapis su įspėjimu", file=sys.stderr)
        sys.exit(1)

    html = build_html(hikes_data, now)
    write_html(html)
    print(f"Sugeneruota: {OUT_PATH} ir {ROOT_PATH}")


if __name__ == "__main__":
    main()
