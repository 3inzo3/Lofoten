# 🏔️ Lofoten žygių langų radaras

Automatiškai atsinaujinanti svetainė, rodanti geriausius žygių langus Lofotenuose
pagal Windy (ECMWF) orų prognozę. Kas 3 valandas GitHub Actions atnaujina
`docs/index.html` — svetainė rodo, **kada ir į kurią viršūnę verta eiti**, kad
nuo viršaus matytųsi vaizdai.

**Score = viršūnės matomumo tikimybė (0–100).** Svarbiausia — žemi debesys ir
cloud base aukštis, lietus antraeilis. Aukšti debesys nebaudžiami (gražina dangų).

## Setup — 5 žingsniai

1. **Įdėk Windy API raktą kaip Secret.**
   Repo puslapyje: *Settings → Secrets and variables → Actions → New repository
   secret*. Pavadinimas: `WINDY_API_KEY`, reikšmė — tavo raktas iš
   [api.windy.com](https://api.windy.com) (Point Forecast API, Premium).

2. **Įjunk GitHub Pages.**
   *Settings → Pages → Build and deployment*: Source = **Deploy from a branch**,
   Branch = **main**, Folder = **/docs**. Išsaugok.

3. **Paleisk pirmą atnaujinimą ranka.**
   *Actions → „Atnaujinti prognozę" → Run workflow*. Po ~1 min. workflow
   sugeneruos ir užcommit'ins `docs/index.html`.

4. **Atsidaryk svetainę.**
   Adresas bus `https://<tavo-username>.github.io/<repo-pavadinimas>/`.
   Pridėk į telefono Home Screen — atsidaro kaip app'as.

5. **Viskas.** Toliau atsinaujina automatiškai kas 3 val. (cron `0 */3 * * *`).
   Jei Windy API nulūžta — puslapis lieka senas su įspėjimu „DUOMENYS PASENĘ".

> ⚠️ Cron veikia tik iš **default šakos** (main) — įsitikink, kad šie failai
> yra main šakoje.

## Kaip veikia score

Kiekvienai 3h prognozės juostai iki 2026-07-23 06:00:

| Baudos | Kiek |
|---|---|
| Žemi debesys | `lclouds% × 0.9` |
| Cloud base žemiau viršūnės +150 m | −40 (viršūnė debesyje) |
| Cloud base žemiau viršūnės +400 m | −15 (rizika) |
| Vidutiniai debesys | `mclouds% × 0.15` |
| Krituliai | `mm × 12` |
| Vėjas > 8 m/s | `(vėjas−8) × 4`, gūsiai > 14 m/s: dar −10 |
| Rūko rizika (rh > 95 % ir lclouds > 60 %) | −25 |

Jei ECMWF neduoda `cbase` — naudojamas proxy: `125 × (temp − dew_point)`.

**Langas** = ≥2 iš eilės juostos su score ≥ 60. Langai 19:00–01:00 gauna 🌅
golden light žymę (+5 rodomam score). Verdiktai: 80+ „PUIKUS", 60+ „GERAS",
40+ „RIZIKINGA", <40 „NEVERTA".

## Failai

- `fetch_and_build.py` — traukia Windy API (6 taškai, ~48 req/parą, telpa į limitą), skaičiuoja, generuoja HTML
- `.github/workflows/update.yml` — cron kas 3 val. + rankinis paleidimas
- `docs/index.html` — sugeneruota svetainė (necommit'inti ranka)

Visi laikai — Europe/Oslo (vietos laiku).
