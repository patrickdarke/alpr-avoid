#!/usr/bin/env python3
"""
ALPR-avoidance prototype — single consolidated server.

Serves the web UI *and* the API from one port, loading the compact packed camera
binary (cameras.bin, ~1 MB) rather than the 30 MB GeoJSON. A spatial grid index
makes bbox/route lookups O(cells) instead of scanning all ~118k cameras, and
responses are gzipped when the client accepts it.

  GET  /                     the map UI (index.html)
  GET  /cameras?bbox=W,S,E,N cameras in view (grid-indexed, capped)
  GET  /geocode?q=addr       address -> {lat, lon, label}   (Nominatim; dev only)
  POST /route {from,to,...}   baseline + camera-avoiding route + stats

Prototype shortcuts (routing via public Valhalla, geocoding via Nominatim,
tiles via OSM) are dev/fair-use only — see COMPLIANCE.md before any public launch.
Stdlib only; shells out to curl (system-Python SSL can't handshake the routing host).
"""
import array
import base64
import gzip
import json
import math
import os
import struct
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, urlencode

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "data", "cameras.bin")
INDEX = os.path.join(HERE, "index.html")
VALHALLA = "https://valhalla1.openstreetmap.de/route"
NOMINATIM = "https://nominatim.openstreetmap.org/search"

CELL = 0.05  # spatial-index cell size in degrees (~5.5 km)

# Single-file deploy: build_standalone.py bakes the HTML and the gzipped camera
# binary into these two constants. Empty here -> dev mode reads the files on disk.
EMBED_HTML_B64 = ""
EMBED_BIN_GZ_B64 = ""


# ---- packed data + spatial index -------------------------------------------

def camera_bytes():
    """Raw packed bytes — from the embedded blob (single-file deploy) or disk."""
    if EMBED_BIN_GZ_B64:
        return gzip.decompress(base64.b64decode(EMBED_BIN_GZ_B64))
    with open(BIN, "rb") as f:
        return f.read()


def parse_cameras(buf):
    """Packed bytes -> (count, lons, lats, dirs) as flat arrays."""
    if buf[:4] != b"FLK1":
        raise SystemExit("bad cameras.bin magic — re-run: fetch_cameras.py pack")
    (n,) = struct.unpack("<I", buf[4:8])
    o = 8
    lons = array.array("f"); lons.frombytes(buf[o:o + 4 * n]); o += 4 * n
    lats = array.array("f"); lats.frombytes(buf[o:o + 4 * n]); o += 4 * n
    dirs = array.array("h"); dirs.frombytes(buf[o:o + 2 * n])
    if __import__("sys").byteorder != "little":
        lons.byteswap(); lats.byteswap(); dirs.byteswap()
    return n, lons, lats, dirs


COUNT, LONS, LATS, DIRS = parse_cameras(camera_bytes())

GRID = {}
for _i in range(COUNT):
    GRID.setdefault((int(LONS[_i] // CELL), int(LATS[_i] // CELL)), []).append(_i)
print(f"Loaded {COUNT} cameras into {len(GRID)} grid cells from {BIN}")


def dir_of(i):
    return None if DIRS[i] < 0 else float(DIRS[i])


def indices_in_bbox(w, s, e, n):
    out = []
    for gx in range(int(w // CELL), int(e // CELL) + 1):
        for gy in range(int(s // CELL), int(n // CELL) + 1):
            for i in GRID.get((gx, gy), ()):
                if w <= LONS[i] <= e and s <= LATS[i] <= n:
                    out.append(i)
    return out


# ---- geometry ---------------------------------------------------------------

def meters_per_deg(lat):
    return (111_320.0, 111_320.0 * math.cos(math.radians(lat)))


def point_to_segment_m(p, a, b):
    mlat, mlon = meters_per_deg((a[1] + b[1]) / 2)
    ax, ay, bx, by = a[0] * mlon, a[1] * mlat, b[0] * mlon, b[1] * mlat
    px, py = p[0] * mlon, p[1] * mlat
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def bearing(a, b):
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    dlon = math.radians(b[0] - a[0])
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def ang_diff(a, b):
    d = abs((a - b) % 360)
    return min(d, 360 - d)


def nearest_on_route(p, line):
    best_d, best_h = float("inf"), 0.0
    for i in range(len(line) - 1):
        d = point_to_segment_m(p, line[i], line[i + 1])
        if d < best_d:
            best_d, best_h = d, bearing(line[i], line[i + 1])
    return best_d, best_h


def captures(travel_heading, cam_direction, window_deg):
    """Would a camera facing `cam_direction` read a vehicle at `travel_heading`?
    Assumes it reads vehicles approaching head-on (heading ~= direction+180),
    tunable via window. Unknown-direction cameras always count as capturing."""
    if cam_direction is None:
        return True
    return ang_diff(travel_heading, (cam_direction + 180) % 360) <= window_deg


def box_polygon(lon, lat, size_m):
    mlat, mlon = meters_per_deg(lat)
    dlat, dlon = size_m / mlat, size_m / mlon
    return [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat],
            [lon + dlon, lat + dlat], [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]


def classify_on_route(route_line, near_m, window_deg):
    """Cameras on the actual route, split into (capturing, passed) — grid-prefiltered."""
    lons = [p[0] for p in route_line]
    lats = [p[1] for p in route_line]
    mlat, mlon = meters_per_deg((min(lats) + max(lats)) / 2)
    padlat, padlon = near_m / mlat, near_m / mlon
    capturing, passed = [], []
    for i in indices_in_bbox(min(lons) - padlon, min(lats) - padlat,
                             max(lons) + padlon, max(lats) + padlat):
        dist, heading = nearest_on_route((LONS[i], LATS[i]), route_line)
        if dist > near_m:
            continue
        d = dir_of(i)
        entry = {"lon": LONS[i], "lat": LATS[i], "direction": d,
                 "travel_heading": round(heading, 1)}
        (capturing if captures(heading, d, window_deg) else passed).append(entry)
    return capturing, passed


def decode_polyline6(s):
    coords, lat, lon, i = [], 0, 0, 0
    while i < len(s):
        for k in range(2):
            shift = result = 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if k == 0:
                lat += delta
            else:
                lon += delta
        coords.append([lon / 1e6, lat / 1e6])
    return coords


# ---- external services (via curl) ------------------------------------------

def geocode(query):
    url = NOMINATIM + "?" + urlencode(
        {"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "us"})
    p = subprocess.run(["curl", "-s", "-m", "15", url, "-H", f"User-Agent: {UA}"],
                       capture_output=True, text=True)
    try:
        arr = json.loads(p.stdout)
    except json.JSONDecodeError:
        return None
    if not arr:
        return None
    r = arr[0]
    return {"lat": float(r["lat"]), "lon": float(r["lon"]), "label": r["display_name"]}


def valhalla_route(frm, to, exclude_polygons=None):
    payload = {"locations": [{"lat": frm[1], "lon": frm[0]}, {"lat": to[1], "lon": to[0]}],
               "costing": "auto", "directions_options": {"units": "kilometers"}}
    if exclude_polygons:
        payload["exclude_polygons"] = exclude_polygons
    p = subprocess.run(["curl", "-s", "-m", "30", VALHALLA, "-H", f"User-Agent: {UA}",
                        "--data", json.dumps(payload)], capture_output=True, text=True)
    data = json.loads(p.stdout)
    return {"coordinates": decode_polyline6(data["trip"]["legs"][0]["shape"]),
            "length_km": round(data["trip"]["summary"]["length"], 3),
            "time_min": round(data["trip"]["summary"]["time"] / 60, 1)}


def linestring(route, props):
    return {"type": "Feature",
            "geometry": {"type": "LineString", "coordinates": route["coordinates"]},
            "properties": {**props, "length_km": route["length_km"],
                           "time_min": route["time_min"]}}


UA = "AlprAvoidPrototype/0.1"


# ---- HTTP -------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj=None, body=None, ctype="application/json"):
        if body is None:
            body = json.dumps(obj).encode()
        headers = [("Content-Type", ctype)]
        if len(body) > 1024 and "gzip" in self.headers.get("Accept-Encoding", ""):
            body = gzip.compress(body, 5)
            headers.append(("Content-Encoding", "gzip"))
        self.send_response(code)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            html = (base64.b64decode(EMBED_HTML_B64) if EMBED_HTML_B64
                    else open(INDEX, "rb").read())
            return self._send(200, body=html, ctype="text/html; charset=utf-8")
        if u.path == "/cameras":
            q = parse_qs(u.query)
            if "bbox" in q:
                w, s, e, n = (float(x) for x in q["bbox"][0].split(","))
                idx = indices_in_bbox(w, s, e, n)
            else:
                idx = range(COUNT)
            MAX, total = 4000, len(idx) if hasattr(idx, "__len__") else COUNT
            feats = [{"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": [LONS[i], LATS[i]]},
                      "properties": {"direction": dir_of(i)}} for i in list(idx)[:MAX]]
            return self._send(200, {"type": "FeatureCollection", "features": feats,
                                    "total": total, "truncated": total > MAX})
        if u.path == "/geocode":
            qv = parse_qs(u.query).get("q", [""])[0].strip()
            if not qv:
                return self._send(400, {"error": "missing q"})
            res = geocode(qv)
            return self._send(200, res) if res else self._send(404, {"error": "no match"})
        if u.path in ("/health", "/healthz"):
            return self._send(200, {"ok": True, "cameras": COUNT})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/route":
            return self._send(404, {"error": "not found"})
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        frm, to = req["from"], req["to"]
        avoid = req.get("avoid", True)
        directional = req.get("directional", True)
        near_m = req.get("near_m", 35)
        box_m = req.get("box_m", 50)
        window = req.get("capture_window", 70)

        baseline = valhalla_route(frm, to)
        features = [linestring(baseline, {"kind": "baseline", "color": "#888"})]
        stats = {"baseline_km": baseline["length_km"], "baseline_min": baseline["time_min"]}

        if avoid:
            capturing, passed = classify_on_route(baseline["coordinates"], near_m, window)
            if not directional:
                capturing, passed = capturing + passed, []
            polys = [box_polygon(c["lon"], c["lat"], box_m) for c in capturing]
            avoided = valhalla_route(frm, to, exclude_polygons=polys) if polys else baseline
            features.append(linestring(avoided, {"kind": "avoided", "color": "#e6194B"}))
            stats.update({
                "avoided_km": avoided["length_km"], "avoided_min": avoided["time_min"],
                "directional": directional,
                "cameras_captured": len(capturing), "cameras_passed": len(passed),
                "extra_km": round(avoided["length_km"] - baseline["length_km"], 3),
                "extra_min": round(avoided["time_min"] - baseline["time_min"], 1),
                "capturing_cameras": capturing, "passed_cameras": passed,
            })
        return self._send(200, {"type": "FeatureCollection", "features": features, "stats": stats})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8787"))
    host = os.environ.get("HOST", "127.0.0.1")  # container sets HOST=0.0.0.0
    print(f"ALPR-avoidance app on http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
