#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lofoten Hike Window Finder
Traukia Open-Meteo prognozes (MEPS 45% + ECMWF 35% + ICON-EU 20%)
žygių taškams, skaičiuoja viršūnės matomumo score (0-100) kiekvienai
valandai kaip svertinį modelių vidurkį, grupuoja į langus ir generuoja index.html.

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
# Svertinis konsensusas: M = MEPS (norvegų, tiksliausias čia), E = ECMWF,
# I = ICON-EU kaip arbitras. GFS (25 km) išmestas — per grubus fjordams.
OM_URL = "https://api.open-meteo.com/v1/forecast"
OM_MODELS = [("metno_seamless", "M", 0.45), ("ecmwf_ifs025", "E", 0.35),
             ("icon_eu", "I", 0.20)]
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


MAP_PATHS = (os.path.join(_BASE, "docs", "map.html"), os.path.join(_BASE, "map.html"))


def write_map(html):
    for path in MAP_PATHS:
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
        "models": ",".join(m for m, _, _ in OM_MODELS),
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

def fetch_model_runs():
    """Kada paskutinį kartą inicializuotas kiekvienas modelis (best-effort)."""
    paths = {"M": ["metno_nordic_pp", "metno_nordic", "met_no_nordic"],
             "E": ["ecmwf_ifs025"],
             "I": ["dwd_icon_eu"]}
    runs = {}
    for letter, cands in paths.items():
        for p in cands:
            try:
                r = requests.get(f"https://api.open-meteo.com/data/{p}/static/meta.json",
                                 timeout=15)
                if r.status_code != 200:
                    continue
                ts = r.json().get("last_run_initialisation_time")
                if isinstance(ts, (int, float)):
                    runs[letter] = dt.datetime.fromtimestamp(ts, tz=OSLO)
                    break
            except Exception:
                continue
    return runs


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
        weights = {}
        lcls, prs, winds = [], [], []
        for model, letter, weight in OM_MODELS:
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
            weights[letter] = weight
            lcls.append(lcl); prs.append(pr); winds.append(wind or 0)
        if not per_model:
            continue
        wsum = sum(weights.values())
        bands.append({
            "t": t, "dur": 1,
            "score": sum(per_model[k] * weights[k] for k in per_model) / wsum,
            "models": per_model,
            "lcl": sum(lcls) / len(lcls),
            "precip": sum(prs) / len(prs),
            "wind": sum(winds) / len(winds),
        })
    return bands


def find_windows(bands, golden_check):
    """Langas = ištisinis laikotarpis su score >= 50, trunkantis >= 3 val."""
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
        if b["score"] >= 50 and (not run or contiguous):
            run.append(b)
        elif b["score"] >= 50:
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
    if score >= 50:
        return "VERTA BANDYTI — 50/50", "#fde047", "#422006"
    if score >= 40:
        return "RIZIKINGA", "#f59e0b", "#422006"
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

def build_html(hikes_data, now, stale_note="", model_runs=None):
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
            badges = '<div class="win"><span style="color:#f87171">⚠️ nėra duomenų (API klaida)</span></div>'
        elif not top3 and not is_done:
            badges = f'<div class="win"><span style="color:#f87171">😕 gerų langų nerasta (prognozė iki {horizon_txt})</span></div>'
        else:
            for w in top3:
                v, fg, _ = verdict(w["display"])
                golden = " 🌅" if w["golden"] else ""
                badges += (f'<div class="win"><b>{fmt_window(w, now)}</b>{golden} · '
                           f'<b style="color:{fg}">score {w["display"]} · {v}</b></div>')

        # Valandinė lentelė iki išvykimo (kaip yr.no): diena — antraštė,
        # eilutė = valanda su score, priežastim ir modelių balais
        strip = ""
        if not is_done:
            rows = ""
            cur_day = None
            for b in h.get("bands", []):
                if b["t"] + dt.timedelta(hours=b["dur"]) <= now:
                    continue
                if b["t"].date() != cur_day:
                    cur_day = b["t"].date()
                    rows += (f'<tr class="dayrow"><td colspan="6">'
                             f'{day_label(b["t"], now).capitalize()}</td></tr>')
                _, fg, _ = verdict(b["score"])
                pr = b.get("precip") or 0
                pr_txt = f"{pr:.1f}" if pr >= 0.1 else ""
                w = b.get("wind")
                w_txt = f"{round(w)}" if w is not None else ""
                mm = " ".join(f"{k}{v}" for k, v in b.get("models", {}).items())
                rows += (f'<tr><td class="t">{b["t"].strftime("%H:%M")}</td>'
                         f'<td class="s" style="color:{fg}">{round(b["score"])}</td>'
                         f'<td>{round(b.get("lcl") or 0)}%</td>'
                         f'<td>{pr_txt}</td><td>{w_txt}</td>'
                         f'<td class="mods">{mm}</td></tr>')
            if rows:
                strip = ('<table class="fx"><tr class="hdr"><td>Laikas</td><td>Score</td>'
                         '<td>☁ žemi</td><td>🌧 mm</td><td>💨 m/s</td><td>Modeliai</td></tr>'
                         + rows + '</table>')

        note = ""
        if not is_done and hike.get("note"):
            note = f'<div class="note">💡 {hike["note"]}</div>'

        title_prefix = "✅ " if is_done else ("🌙 ŠĮVAKAR: " if is_tonight else "")
        cls = "card done" if is_done else "card"
        body = "" if is_done else badges + strip + note

        # suskleistoje kortelėje — geriausio artėjančio lango ženkliukas
        pill = ""
        if not is_done:
            best = max(top3, key=lambda w: w["display"], default=None)
            if best:
                _, fg, _ = verdict(best["display"])
                pill = (f'<span class="pill">{fmt_window(best, now)} · '
                        f'<b style="color:{fg}">{best["display"]}</b></span>')
            else:
                pill = '<span class="pill"><span style="color:#f87171">langų nėra</span></span>'
        cards.append(f"""
    <details class="{cls}">
      <summary><span class="chev">▸</span><div class="hname">{title_prefix}{hike['name']} <span class="meta">{hike['elev_m']} m · {hike['zone']}</span></div>{pill}</summary>
      {body}
    </details>""")

    updated = now.strftime("%Y-%m-%d %H:%M")
    updated_short = now.strftime("%H:%M")
    runs_txt = ""
    if model_runs:
        runs_txt = ("<br>Modelių leidimai: "
                    + " · ".join(f"{k} {v.strftime('%m-%d %H:%M')}"
                                 for k, v in sorted(model_runs.items())))
    model_txt = "Open-Meteo · svertinis vidurkis: M=MEPS 45% · E=ECMWF 35% · I=ICON-EU 20%"
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
  .topbar {{ display:flex; justify-content:space-between; align-items:center;
             margin-bottom:12px; }}
  .refresh {{ background:#2563eb; color:#fff; border:none; border-radius:10px;
              padding:12px 18px; font-size:16px; font-weight:600; }}
  .maplink {{ background:#334155; text-decoration:none; margin-left:8px; }}
  .upd {{ font-size:14px; color:#9ca3af; }}
  .legend {{ background:#111a33; border-radius:12px; padding:12px 14px;
             margin-bottom:16px; font-size:14px; color:#cbd5e1; }}
  .legend summary {{ cursor:pointer; font-size:15px; }}
  .legend p {{ margin:8px 0 0; }}
  .card {{ background:#111a33; border-radius:14px; padding:14px 16px; margin-bottom:14px; }}
  .card summary {{ cursor:pointer; list-style:none; }}
  .card summary::-webkit-details-marker {{ display:none; }}
  .chev {{ float:right; color:#9ca3af; transition:transform .15s; display:inline-block; }}
  details[open] .chev {{ transform:rotate(90deg); }}
  .pill {{ display:inline-block; border-radius:8px; padding:2px 10px; font-size:14px;
           margin-top:6px; background:#182142; color:#94a3b8; }}
  .card.done {{ opacity:0.45; }}
  .hname {{ font-size:20px; font-weight:700; margin-bottom:8px; }}
  .meta {{ font-size:14px; font-weight:400; color:#9ca3af; display:block; margin-top:2px; }}
  .win {{ border-radius:10px; padding:8px 12px; margin:6px 0; font-size:16px;
         background:#182142; color:#e5e7eb; }}
  .note {{ font-size:14px; color:#fbbf24; margin-top:6px; }}
  .fx {{ width:100%; border-collapse:collapse; margin-top:10px; }}
  .fx td {{ padding:6px 4px; border-bottom:1px solid #1c2647; font-size:14px;
           text-align:right; color:#cbd5e1; }}
  .fx td.t {{ text-align:left; color:#94a3b8; }}
  .fx .hdr td {{ font-size:11px; color:#64748b; letter-spacing:0.5px;
                border-bottom:1px solid #2a3660; }}
  .fx .dayrow td {{ text-align:left; color:#9ca3af; font-size:13px;
                   padding-top:16px; letter-spacing:1px; border-bottom:1px solid #2a3660; }}
  .fx .s {{ font-weight:700; font-size:16px; }}
  .fx .mods {{ font-size:11px; color:#64748b; white-space:nowrap; }}
  .stale {{ background:#7f1d1d; color:#fecaca; border-radius:10px; padding:10px 14px;
            margin-bottom:16px; font-size:16px; }}
  .seclbl {{ font-size:13px; letter-spacing:2px; color:#9ca3af; margin:22px 0 10px; }}
  .footer {{ margin-top:24px; font-size:12px; color:#6b7280; text-align:center; }}
</style>
</head>
<body>
  {stale_html}
  <div class="topbar">
    <button class="refresh" onclick="location.href=location.pathname+'?r='+Date.now()">🔄 Atnaujinti</button>
    <a class="refresh maplink" href="map.html">🗺️ Žemėlapis</a>
    <span class="upd">Atnaujinta {updated_short}</span>
  </div>
  <details class="legend">
    <summary>ℹ️ Kaip skaičiuojamas score? Kas yra M E I G?</summary>
    <p><b>Score 0–100</b> — tikimybė, kad nuo viršūnės matysis vaizdai (ne oro
    „gerumas"!). Tai <b>svertinis 3 modelių vidurkis</b>; po langeliu — kiekvieno
    modelio balas atskirai:</p>
    <p><b>M</b> = MEPS (norvegų, 2.5 km — tiksliausias Lofotenams, svoris 45 %)<br>
    <b>E</b> = ECMWF (europinis, 9 km, svoris 35 %)<br>
    <b>I</b> = ICON-EU (vokiečių, 7 km, svoris 20 %)</p>
    <p>Kai visi rodo panašiai — prognozė patikima; kai išsiskiria (pvz. M80 E75 I0) — 50/50, spręsk pagal dangų.</p>
    <p><b>Baudos:</b> daugiausiai atima žemi debesys (dengia viršūnę) ir debesų
    pagrindas žemiau viršūnės; toliau lietus, vėjas &gt;8 m/s, rūkas. Aukšti
    plunksniniai debesys nebaudžiami — jie tik gražina dangų.</p>
    <p><b>Spalvos:</b> <span style="color:#22c55e">≥80 PUIKUS</span> ·
    <span style="color:#86efac">60–79 GERAS</span> ·
    <span style="color:#fde047">50–59 VERTA BANDYTI</span> · <span style="color:#f59e0b">40–49 RIZIKINGA</span> ·
    <span style="color:#f87171">&lt;40 NEVERTA</span>.
    <b>Langas</b> = ištisinis ≥3 val. periodas su score ≥50 —
    nuo 50 jau verta bandyti (debesys Lofotenuose juda greitai).</p>
  </details>
  {''.join(cards)}
  <div class="footer">Atnaujinta: {updated} (Oslo laiku) · Duomenys: {model_txt} ·
  Score = viršūnės matomumo tikimybė · 🌅 = golden light · ☁ žemi debesys % · 🌧 mm · 💨 m/s ·
  Prognozė siekia: {horizon_txt}{runs_txt}</div>
</body>
</html>
"""

def build_map_html(hikes_data, now):
    """Žemėlapis su laiko slankikliu: viršūnės spalvinamos pagal score."""
    active = [h for h in hikes_data if h["hike"]["status"] != "done" and h.get("bands")]
    all_times = sorted({b["t"] for h in active for b in h["bands"]})
    idx = {t: i for i, t in enumerate(all_times)}
    labels = [f"{day_label(t, now).capitalize()} {t.strftime('%H:%M')}" for t in all_times]
    hikes_js = []
    for h in active:
        scores = [None] * len(all_times)
        for b in h["bands"]:
            scores[idx[b["t"]]] = round(b["score"])
        hikes_js.append({"n": h["hike"]["name"], "e": h["hike"]["elev_m"],
                         "la": h["hike"]["lat"], "lo": h["hike"]["lon"], "s": scores})
    data = json.dumps({"times": labels, "hikes": hikes_js}, ensure_ascii=False)
    updated = now.strftime("%H:%M")
    return f"""<!DOCTYPE html>
<html lang="lt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lofoten žygių žemėlapis</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body {{ margin:0; background:#0b1020; color:#e5e7eb;
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; }}
  #map {{ position:fixed; top:0; left:0; right:0; bottom:96px; }}
  .bar {{ position:fixed; left:0; right:0; bottom:0; height:96px; background:#111a33;
          padding:10px 16px; box-sizing:border-box; z-index:1000; }}
  .bar .lbl {{ font-size:15px; margin-bottom:6px; display:flex;
               justify-content:space-between; align-items:center; }}
  .bar input {{ width:100%; }}
  .back {{ color:#93c5fd; text-decoration:none; font-size:14px; }}
  .mk {{ width:36px; height:36px; border-radius:50%; display:flex; align-items:center;
        justify-content:center; font-weight:700; font-size:14px; color:#0b1020;
        border:2px solid #0b1020; box-shadow:0 1px 4px rgba(0,0,0,.6); }}
</style>
</head>
<body>
<div id="map"></div>
<div class="bar">
  <div class="lbl"><b id="tlabel"></b><a class="back" href="index.html">← sąrašas</a></div>
  <input id="slider" type="range" min="0" value="0" step="1">
</div>
<script>
const D = {data};
const map = L.map('map', {{zoomControl:false}}).setView([68.12, 13.8], 8);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
  {{attribution:'© OpenStreetMap', maxZoom:15}}).addTo(map);
function color(s) {{
  if (s === null) return '#475569';
  if (s >= 80) return '#22c55e';
  if (s >= 60) return '#86efac';
  if (s >= 50) return '#fde047';
  if (s >= 40) return '#f59e0b';
  return '#ef4444';
}}
const markers = D.hikes.map(h => {{
  const m = L.marker([h.la, h.lo], {{icon: L.divIcon({{className:'', iconSize:[36,36]}})}}).addTo(map);
  m.bindPopup('');
  return m;
}});
const slider = document.getElementById('slider');
slider.max = D.times.length - 1;
function render(i) {{
  document.getElementById('tlabel').textContent = D.times[i];
  D.hikes.forEach((h, j) => {{
    const s = h.s[i];
    markers[j].setIcon(L.divIcon({{className:'', iconSize:[36,36],
      html:`<div class="mk" style="background:${{color(s)}}">${{s === null ? '–' : s}}</div>`}}));
    markers[j].setPopupContent(`<b>${{h.n}}</b><br>${{h.e}} m · score ${{s === null ? 'nėra duomenų' : s}}<br>${{D.times[i]}}`);
  }});
}}
slider.addEventListener('input', () => render(+slider.value));
render(0);
</script>
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

    try:
        model_runs = fetch_model_runs()
        print("Modelių leidimai:", {k: v.strftime('%m-%d %H:%M') for k, v in model_runs.items()})
    except Exception as e:
        model_runs = None
        print(f"Modelių meta nepavyko: {e}", file=sys.stderr)
    html = build_html(hikes_data, now, model_runs=model_runs)
    write_map(build_map_html(hikes_data, now))
    write_html(html)
    print(f"Sugeneruota: {OUT_PATH} ir {ROOT_PATH}")


if __name__ == "__main__":
    main()
