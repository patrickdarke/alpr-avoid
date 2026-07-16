# Compliance & Pre-Launch Checklist

Requirements for turning this prototype into a **free, public web service**. The
prototype takes shortcuts that are fine for local development but **not allowed
for a public production service**. This file tracks what must change before launch.

> This is an engineering checklist based on a plain reading of the relevant
> licenses and usage policies — **not legal advice**. Have a lawyer review before
> launch, especially given Flock Safety's known litigiousness.

Status legend: ✅ done · ⚠️ partial · ❌ not started

---

## 1. Stop using shared/free infrastructure (the big one)

The prototype leans on four free services that all prohibit production/third-party
service use. Each must be self-hosted or replaced with a paid provider.

| Dependency | Prototype uses | Why it's not allowed | Production action | Status |
|---|---|---|---|---|
| **Map tiles** | `tile.openstreetmap.org` | OSMF tile usage policy bars third-party apps/heavy use | Self-host tiles, or paid provider (MapTiler, Mapbox, Protomaps/PMTiles) | ❌ |
| **Camera data** | public Overpass API | Overpass fair-use bars powering a service / bulk scraping | Ingest from OSM **planet/region extracts** (e.g. Geofabrik) on a schedule | ❌ |
| **Routing** | `valhalla1.openstreetmap.de` | FOSSGIS **demo** server, not for production | Self-host **Valhalla or GraphHopper** (Docker) built from OSM extracts | ❌ |
| **Geocoding** | OSM Nominatim | Nominatim usage policy bars heavy/service use (1 req/s, no bulk) | Self-host Nominatim, or paid geocoder | ❌ |

Notes:
- The production design already favors **GraphHopper with a soft-penalty
  `custom_model`** over Valhalla hard-avoidance (graceful degradation in
  camera-dense areas). See [README](README.md).
- Self-hosting all four also removes rate-limit fragility (the 504s / mirror
  fallbacks seen during development).

---

## 2. OpenStreetMap / ODbL obligations

The camera data and map are OSM, under the **Open Database License (ODbL)**.
"Free to the public" does **not** exempt you — ODbL keys off *public use*, not price.

- ✅ **Attribution — data + tiles.** "© OpenStreetMap contributors (ODbL)" shown
  in the map corner and the panel credits. Keep it visible on every view that
  shows the data or a derived route.
- ❌ **Share-alike (Derivative Database).** The pipeline *adapts* OSM data
  (normalizes, parses `direction`, adds computed fields) → a Derivative Database.
  ODbL's "publicly used" trigger means offering it *as a service* counts, even
  without distributing files. **Action:** publish the adapted camera dataset
  under ODbL — a "Download data (ODbL)" link or an endpoint + notice pointing to
  it. (Quick win — can expose the existing GeoJSON.)
- ✅ **Produced Works.** Rendered maps/route lines must carry attribution (they
  do) but need not themselves be ODbL.
- ⚠️ **Keep source attribution current** if you add other data sources later.

---

## 3. You are now a service operator — your own legal pages

New obligations that have nothing to do with OSM or DeFlock.

- ❌ **Terms of Service** for your site — usage terms + an **"as is" liability
  disclaimer**.
- ❌ **Accuracy disclaimer, prominent.** "Known/mapped cameras only; coverage is
  crowdsourced and incomplete; never assume a route is camera-free." The
  prototype already shows this in-app — it must also live in the ToS. This is a
  genuine liability shield against reliance claims.
- ❌ **Privacy Policy** — and this one matters more than people expect:
  - Users enter **origin/destination** = location data about identifiable people.
  - **Minimize by design:** compute the route and discard it. Don't log
    route queries tied to IPs; don't retain search history.
  - If you serve **EU (GDPR)** or **California (CCPA/CPRA)** users, disclosure +
    data-subject rights apply. Data minimization is the cheapest path to
    compliance.
  - If you self-host Nominatim/tiles, geocoding queries stay on your infra
    (good). If you use a paid geocoder, user addresses go to that third party —
    disclose it.

---

## 4. Trademark & branding

- ⚠️ **"Flock" is Flock Safety's trademark.** Describing function factually
  ("routes around Flock Safety / ALPR cameras") is normally OK nominative use.
  **Naming or branding** the product around "Flock" is riskier and can invite a
  cease-and-desist regardless of merit.
- ✅ **Done in-code:** the app/UI/docs are now branded **"ALPR"** (product name,
  titles, User-Agents, the standalone `alpravoid.py`). The only remaining
  "Flock" references are (a) the literal `manufacturer=Flock Safety` OSM data
  query, which is factual nominative use and must stay, (b) this section's
  discussion of the trademark itself, and (c) "DeFlock", a separate project's name.
- ✅ **Folder renamed** to `alpr-avoid/`. No "Flock" branding remains in the
  product name or files.

---

## 5. DeFlock Terms of Service — assessed, no conflict

Reviewed `deflock.org/terms` (effective 2024-12-26). **No conflict**, because:
- We pull data **directly from OpenStreetMap**, not from DeFlock's platform/API,
  so most of their ToS (termination, their systems, their content/logos) doesn't
  bind us.
- Their "commercial products or services" clause applies to services regardless
  of price, but only requires **OSM attribution + license compliance** — covered
  by sections 2 above.
- Their prohibited uses (OSM vandalism, impersonation, hacking DeFlock, illegal
  activity) don't apply — routing around public cameras is legal, and we never
  edit OSM or touch their infrastructure.
- Their source is MIT-licensed (reusable with attribution); their branding is not.

---

## 6. Distribution note (positive)

Shipping as a **website avoids app-store gatekeeping** entirely — no store review
that could reject a tool framed as avoiding law-enforcement cameras. Web
distribution is the path of least resistance for this project.

---

## Pre-launch gate (must all be ✅)

- [ ] Self-hosted tiles, data pipeline (extracts), routing, geocoding — §1
- [ ] ODbL share-alike: adapted dataset offered under ODbL — §2
- [ ] Terms of Service + accuracy/liability disclaimer — §3
- [ ] Privacy policy + data-minimization implemented (no route logging) — §3
- [x] Renamed/rebranded away from "Flock" — §4 (code, UI, and folder done)
- [ ] Legal review completed — top of file

## Nice-to-have before launch

- [ ] Directional capture model refined with real per-lane geometry — [README](README.md)
- [ ] Soft-penalty routing (GraphHopper `custom_model`) replacing hard-avoid
- [ ] Alaska/Hawaii added to the data bbox if desired
