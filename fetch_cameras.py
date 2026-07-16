#!/usr/bin/env python3
"""
Fetch ALPR camera locations from OpenStreetMap (the same data DeFlock
is built on) via the Overpass API, and write two artifacts into ./data:

  cameras.geojson  human-readable source of truth (ODbL-shareable, regenerable)
  cameras.bin      compact packed binary the app actually loads at runtime

The app only needs lon, lat, and facing direction, so the packed form stores
exactly that — float32 lon, float32 lat, int16 direction (-1 = unknown) — which
shrinks ~30 MB of GeoJSON to ~1.4 MB and cuts runtime memory from ~240 MB to a
few MB. See pack_bin().

Usage:
  fetch_cameras.py                  Huntsville default (fetch + pack)
  fetch_cameras.py usa | nc | ...   named region (fetch + pack)
  fetch_cameras.py S W N E          explicit bbox (fetch + pack)
  fetch_cameras.py pack             re-pack existing data/cameras.geojson only
  fetch_cameras.py --from RAW.json  normalize a pre-downloaded Overpass raw

Uses curl via subprocess because macOS system Python 3.9 ships an OpenSSL that
cannot TLS-handshake with several of these hosts; curl handles them fine.
"""
import array
import json
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
GEOJSON = os.path.join(DATA_DIR, "cameras.geojson")
BIN = os.path.join(DATA_DIR, "cameras.bin")

# Ordered by observed reliability. overpass-api.de is frequently overloaded (504);
# mirrors fill in.
MIRRORS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]
UA = "AlprAvoidPrototype/0.1 (research; contact: local)"

# Named regions (S, W, N, E). "usa" = continental US (excludes AK/HI).
REGIONS = {
    "huntsville": (34.55, -86.80, 34.90, -86.45),
    "nc": (33.75, -84.35, 36.60, -75.40),
    "usa": (24.0, -125.0, 49.5, -66.5),             # ~118k cameras
}
DEFAULT_BBOX = REGIONS["huntsville"]

QUERY_TIMEOUT = 220           # Overpass server-side; curl wall-clock must exceed it
CURL_TIMEOUT = "240"

BIN_MAGIC = b"FLK1"           # packed format: magic, u32 count, lon[f32], lat[f32], dir[i16]


def build_query(bbox):
    s, w, n, e = bbox
    # NOTE: "Flock Safety" here is a literal OSM `manufacturer` tag value, not
    # branding — it must stay verbatim to match those camera nodes in the data.
    return f"""[out:json][timeout:{QUERY_TIMEOUT}];
(
  node["man_made"="surveillance"]["surveillance:type"="ALPR"]({s},{w},{n},{e});
  node["man_made"="surveillance"]["manufacturer"="Flock Safety"]({s},{w},{n},{e});
);
out body;"""


def fetch(bbox):
    query = build_query(bbox)
    for url in MIRRORS:
        try:
            p = subprocess.run(
                ["curl", "-s", "-m", CURL_TIMEOUT, "-X", "POST", url,
                 "-H", f"User-Agent: {UA}", "--data-urlencode", f"data={query}"],
                capture_output=True, text=True)
            els = json.loads(p.stdout).get("elements", [])
            if els:
                print(f"  [{url}] -> {len(els)} elements", file=sys.stderr)
                return els
            print(f"  [{url}] -> empty/failed, trying next", file=sys.stderr)
        except (json.JSONDecodeError, subprocess.SubprocessError) as ex:
            print(f"  [{url}] -> error {ex}, trying next", file=sys.stderr)
    raise SystemExit("All Overpass mirrors failed. Try again later.")


def normalize(els):
    """OSM node -> GeoJSON Feature, deduped."""
    features, seen = [], set()
    for e in els:
        oid = e["id"]
        if oid in seen:
            continue
        seen.add(oid)
        tags = e.get("tags", {})
        d = tags.get("direction")
        try:
            d = float(d) if d is not None else None
        except ValueError:
            d = None  # some are compass words like "N"; ignore for now
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [e["lon"], e["lat"]]},
            "properties": {
                "id": oid, "operator": tags.get("operator"),
                "manufacturer": tags.get("manufacturer"), "direction": d,
                "mount": tags.get("camera:mount"), "zone": tags.get("surveillance:zone"),
                "source": "osm-overpass",
            },
        })
    return features


def pack_bin(features, path):
    """Write the compact runtime binary. Little-endian (all target machines are)."""
    lons, lats, dirs = array.array("f"), array.array("f"), array.array("h")
    for f in features:
        lon, lat = f["geometry"]["coordinates"]
        d = f["properties"]["direction"]
        lons.append(lon)
        lats.append(lat)
        dirs.append(-1 if d is None else max(0, min(360, int(round(d)))))
    if sys.byteorder != "little":
        lons.byteswap(); lats.byteswap(); dirs.byteswap()
    with open(path, "wb") as fh:
        fh.write(BIN_MAGIC)
        fh.write(struct.pack("<I", len(features)))
        fh.write(lons.tobytes()); fh.write(lats.tobytes()); fh.write(dirs.tobytes())
    return len(features)


def write_outputs(features):
    os.makedirs(DATA_DIR, exist_ok=True)
    with_dir = sum(1 for f in features if f["properties"]["direction"] is not None)
    with open(GEOJSON, "w") as fh:
        json.dump({"type": "FeatureCollection",
                   "metadata": {"count": len(features), "with_direction": with_dir},
                   "features": features}, fh)
    pack_bin(features, BIN)
    gj = os.path.getsize(GEOJSON) / 1e6
    bn = os.path.getsize(BIN) / 1e6
    print(f"Wrote {len(features)} cameras ({with_dir} with direction)")
    print(f"  {GEOJSON}  {gj:.1f} MB (source)")
    print(f"  {BIN}  {bn:.1f} MB (runtime, {gj / bn:.0f}x smaller)")


def main():
    args = sys.argv[1:]
    if args[:1] == ["pack"]:
        print("Re-packing existing cameras.geojson ...", file=sys.stderr)
        feats = json.load(open(GEOJSON))["features"]
        pack_bin(feats, BIN)
        print(f"Packed {len(feats)} cameras -> {BIN} ({os.path.getsize(BIN)/1e6:.1f} MB)")
        return
    if args[:1] == ["--from"]:
        print(f"Normalizing cached raw {args[1]} ...", file=sys.stderr)
        feats = normalize(json.load(open(args[1]))["elements"])
    else:
        bbox = DEFAULT_BBOX
        if len(args) == 1 and args[0] in REGIONS:
            bbox = REGIONS[args[0]]
        elif len(args) == 4:
            bbox = tuple(float(x) for x in args)
        print(f"Fetching ALPR cameras for bbox (S,W,N,E)={bbox} ...", file=sys.stderr)
        feats = normalize(fetch(bbox))
    write_outputs(feats)


if __name__ == "__main__":
    main()
