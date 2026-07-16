#!/usr/bin/env python3
"""
Bake app.py + index.html + data/cameras.bin into a single self-contained script:
dist/alpravoid.py. That one file needs no other files — copy it anywhere with
Python 3 and `curl`, run it, and it serves the whole app (data embedded).

    python3 build_standalone.py
    python3 dist/alpravoid.py        # -> http://127.0.0.1:8787

Dev workflow is unchanged: run app.py directly and it reads the files on disk.
"""
import base64
import gzip
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read(path, mode="rb"):
    with open(os.path.join(HERE, path), mode) as f:
        return f.read()


def main():
    app = read("app.py", "r")
    html_b64 = base64.b64encode(read("index.html")).decode()
    bin_gz_b64 = base64.b64encode(gzip.compress(read("data/cameras.bin"), 9)).decode()

    # Replace the empty placeholders with the baked-in payloads.
    for name, value in (("EMBED_HTML_B64", html_b64), ("EMBED_BIN_GZ_B64", bin_gz_b64)):
        placeholder = f'{name} = ""'
        if placeholder not in app:
            raise SystemExit(f"placeholder {placeholder!r} not found in app.py")
        app = app.replace(placeholder, f'{name} = "{value}"', 1)

    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    out = os.path.join(HERE, "dist", "alpravoid.py")
    with open(out, "w") as f:
        f.write(app)

    mb = os.path.getsize(out) / 1e6
    print(f"Wrote {out}  ({mb:.1f} MB, self-contained)")
    print("Run it anywhere:  python3 dist/alpravoid.py")


if __name__ == "__main__":
    main()
