# ALPR-Avoidance Navigation — Prototype

A working proof-of-concept web service that routes **around known ALPR
(automated license-plate reader) cameras**, using the crowdsourced camera data
that [DeFlock](https://deflock.me) is built on (OpenStreetMap).

It proves the concept end-to-end with **live data and live routing**: real
cameras pulled from Overpass, real routes from a public Valhalla server that
bend around cameras on the path. It's a demo harness — it draws and compares
routes on a map rather than giving live turn-by-turn guidance.

> 👋 **Not a programmer?** Start with the **[User Guide](USER_GUIDE.md)** — a
> step-by-step, no-jargon walkthrough for getting this running and using the map.

## What's here

Four files. No dependencies — system Python 3 + `curl` only.

```
app.py               single server: serves the UI + /cameras, /geocode, /route
index.html           the whole web UI (Leaflet map, address search, controls)
fetch_cameras.py     data pipeline: Overpass -> data/cameras.{geojson,bin}
build_standalone.py  bakes everything into one self-contained dist/alpravoid.py
data/cameras.bin     packed runtime data (~1.1 MB; app loads this)
data/cameras.geojson human-readable source of truth (~30 MB; ODbL-shareable)
```

## Single-file deploy

For a copy-anywhere deployment, bake the UI + data into one script:

```bash
python3 build_standalone.py       # -> dist/alpravoid.py  (~1.2 MB, self-contained)
python3 dist/alpravoid.py        # needs no other files; open http://127.0.0.1:8787
```

`dist/alpravoid.py` embeds the HTML and the gzipped camera binary — drop it on
any box with Python 3 + `curl` and run it. (Routing/geocoding still call the
external Valhalla/Nominatim services; only the app + data are self-contained.)

## Run it (one command)

```bash
# (optional) refresh camera data — writes both cameras.geojson and cameras.bin
python3 fetch_cameras.py usa      # ~118k nationwide (~75s)  ·  or: nc | huntsville | "S W N E"
python3 fetch_cameras.py pack     # just re-pack an existing geojson -> bin

# start everything (UI + API on one port)
python3 app.py                    # -> open http://127.0.0.1:8787
```

Type a start and destination, toggle directional avoidance, and hit Route.

## Efficiency notes

The app loads a **packed binary** (`cameras.bin`: float32 lon/lat + int16 heading),
not the 30 MB GeoJSON — the UI/routing only need those three fields per camera.

| | Before | After |
|---|---|---|
| Runtime data size | 30 MB GeoJSON | **1.1 MB** packed (27×) |
| Server memory (118k cameras) | 243 MB | **29 MB** (8×) |
| Camera lookups | scan all 118k | **spatial grid** index (O(cells)) |
| Camera-list transfer | plain JSON | **gzip** (~40 KB → ~7 KB) |
| Processes / ports | 2 (API + static, CORS) | **1** (same origin) |

Bbox queries return in ~50 ms (capped at 4,000 markers so the browser survives);
an avoidance route computes in <1 s.

## How avoidance works

1. **Data** — `fetch_cameras.py` queries OSM for
   `man_made=surveillance` + `surveillance:type=ALPR` (plus the
   `manufacturer=Flock Safety` OSM tag — a literal data value, not branding).
   ~118k cameras nationwide, ~86% with a `direction` tag.
   The `/cameras` endpoint filters by bbox and caps the result so a zoomed-out
   view never ships six figures of markers; `/route` bbox-prefilters cameras
   to the route's bounding box before the per-segment classification.
2. **On-route classification (two-pass)** — the BFF routes once, then finds the
   cameras that actually sit on that path (within `near_m`) — not just near the
   straight line. This fixes the "corridor ≠ route" gap where nearby cameras on
   parallel roads were wrongly counted.
3. **Directional filter** — for each on-route camera it compares your travel
   heading to the camera's `direction` and only avoids cameras that would *read
   your plate* (facing roughly toward you). Cameras facing away are left alone,
   so you don't detour for cameras that can't see you. Toggle off in the UI to
   avoid every on-route camera regardless of facing.
4. **Avoidance** — each camera to avoid becomes a small `exclude_polygon`;
   Valhalla re-routes around them.

**Directional model (tunable, honestly uncertain):** a camera facing `D°` is
assumed to read vehicles approaching head-on — travelling within
`capture_window` (default 70°) of `D+180`. Real ALPR capture geometry varies;
this is a defensible default, not ground truth. Cameras with no `direction` tag
are always avoided.

## Prototype vs. production (deliberate shortcuts)

| Concern | Prototype | Production |
|---|---|---|
| Routing engine | public Valhalla, `exclude_polygons` (**hard** avoid) | self-hosted **GraphHopper** `custom_model` (**soft** penalty — degrades gracefully in dense areas) |
| Camera store | flat GeoJSON file | PostGIS + nightly cron |
| Directionality | ✅ implemented — avoid only cameras facing your travel (toggle in UI) | same, refined with real per-lane capture geometry |
| Nav UI | draw & compare routes on a Leaflet map | in-browser turn-by-turn + live reroute-with-avoidance |
| Geocoding | OSM Nominatim `/geocode` (dev fair-use only) | self-hosted Nominatim or a paid geocoder |
| HTTP | `curl` subprocess (system-Python TLS workaround) | proper async HTTP client |

> **Going public?** The prototype's free-infrastructure shortcuts (public tiles,
> Overpass, Valhalla, Nominatim) are not allowed for a production service. See
> [COMPLIANCE.md](COMPLIANCE.md) for the full pre-launch checklist — self-hosting,
> ODbL share-alike, privacy policy, and trademark.

## Known limits / honesty notes

- **Coverage is incomplete.** This avoids *known, mapped* cameras only. Never
  present a route as camera-free — the UI says so.
- Hard-avoid can produce odd detours or fail in camera-dense areas; that's
  exactly why production uses soft penalties.
- Public Overpass/Valhalla are shared, rate-limited services — fine for a demo,
  not for production traffic.
- Data is OSM (ODbL): attribution + share-alike apply if you redistribute.

## Next steps

1. Stand up GraphHopper in Docker on one region; port `/route` to a
   soft-penalty `custom_model`.
2. Refine the directional capture model with real ALPR per-lane geometry, and
   make the two-pass iterative (re-classify after each reroute).
3. Add in-browser turn-by-turn guidance + live reroute-with-avoidance.
4. Work through [COMPLIANCE.md](COMPLIANCE.md) before any public launch
   (self-hosting, ODbL share-alike, privacy policy).

Done: live nationwide camera data, corridor→on-route classification,
**directional avoidance** with facing-arrow visualization and a UI toggle,
address geocoding, and OSM/ODbL attribution.

## License

- **Code** — MIT ([LICENSE](LICENSE)).
- **Camera data** (`data/cameras.bin` / `data/cameras.geojson`) — © OpenStreetMap
  contributors, under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).
  Attribution + share-alike apply if you redistribute or adapt it. See [DATA_LICENSE](DATA_LICENSE).
