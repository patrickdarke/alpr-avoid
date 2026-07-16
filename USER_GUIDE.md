# User Guide (for everyone)

A friendly, no-jargon walkthrough. If you've never used a "terminal" or written
code, you're in the right place — this guide assumes nothing.

---

## What is this?

Many roads have **ALPR cameras** — "Automated License-Plate Readers." These are
cameras that automatically photograph the license plate of every car that drives
past and record where and when it was seen.

This tool shows those cameras on a map and, when you enter a start and a
destination, tries to find a driving route that **steers around the ones it
knows about**. Think of it like a normal maps app, but it also tries to avoid
these cameras.

**Two honest things up front:**

1. It can only avoid cameras that people have already added to the map. It is
   **not complete** — there may be cameras it doesn't know about. Never assume a
   route is camera-free.
2. This is an early version that runs **on your own computer**, not on a website
   yet. That means there's a little bit of setup, explained below.

Avoiding public cameras like these is legal — this is a privacy tool.

---

## What you'll need

- A computer (Windows or Mac).
- About 5–10 minutes.
- A free program called **Python** (a way for your computer to run this tool).
  Many computers already have it. We'll check in a moment.
- An internet connection.

---

## Step 1 — Download the files

1. Go to the project page: **https://github.com/patrickdarke/alpr-avoid**
2. Click the green **"Code"** button near the top.
3. Click **"Download ZIP."**
4. Find the downloaded ZIP file (usually in your *Downloads* folder) and
   **double-click it** to unzip. You'll get a folder called `alpr-avoid-main`.

---

## Step 2 — Open the "Terminal"

The Terminal is a plain window where you type a command to start the tool. It
looks intimidating but you'll only type two short lines.

- **On a Mac:** press `Cmd` + `Space`, type **Terminal**, and press `Enter`.
- **On Windows:** click Start, type **Command Prompt**, and press `Enter`.

A window with a blinking cursor opens. That's it.

---

## Step 3 — Go to the folder and start it

In that window, type the word `cd` (which means "change to this folder"),
then a space, then drag the unzipped `alpr-avoid-main` folder onto the window
and drop it. It will fill in the folder location for you. Press `Enter`.

Now type this and press `Enter`:

```
python3 app.py
```

- If you see a line like **"ALPR-avoidance app on http://127.0.0.1:8787"**, it
  worked! Leave this window open — it's running the tool.
- If it says *"python3 is not found"* or similar, you need to install Python
  first: go to **https://www.python.org/downloads/**, install it, then try
  `python3 app.py` again. (On Windows, you can also try just `python app.py`.)

---

## Step 4 — Open it in your web browser

Open your normal web browser (Chrome, Safari, Edge…), click the address bar at
the top, type this exactly, and press `Enter`:

```
http://127.0.0.1:8787
```

You'll see a map of the United States covered in little blue arrows — each arrow
is a known camera, pointing the way it faces.

---

## Step 5 — Plan a route

On the left is a small panel:

1. In the **Start** box, type where you're leaving from (an address or a place
   name, e.g. *"Park Road Shopping Center, Charlotte, NC"*).
2. In the **Destination** box, type where you're going.
3. Click the red **"Route (avoid cameras)"** button.

The map zooms to your trip and draws the route.

---

## How to read the map

**The two lines:**

| What you see | What it means |
|---|---|
| **Grey dashed line** | The normal, fastest route (what a regular maps app would give you) |
| **Red line** | The camera-avoiding route this tool suggests |

If the two match exactly, it means the fastest route didn't need changing.

**The arrows (cameras):**

| Arrow | What it means |
|---|---|
| **Blue ➤** | A known camera, pointing the direction it looks |
| **Green ➤** | A camera on your route that is **facing away** from you — it can't read your plate, so the route leaves it alone |
| **Red ➤** | A camera on your route that **would photograph you** — the route tries to go around it |

**The numbers panel** shows how much longer the camera-avoiding route is (for
example, *"+0.9 km · +1.7 min"*) and how many cameras it dodged.

**The "Directional" checkbox:** When it's checked (the default), the tool only
avoids cameras that are actually pointed at you — so you don't take a longer
detour to dodge a camera that can't even see your direction of travel. Uncheck
it if you'd rather avoid *every* camera near your route, even the ones facing away.

---

## Common questions

**"It says the address can't be found."**
Try adding the city and state, e.g. *"Main Street, Asheville, NC."*

**"Nothing happens / the page won't load."**
Make sure the Terminal window from Step 3 is still open and running. If you
closed it, just run `python3 app.py` again.

**"I want to stop it."**
Close the browser tab, then go back to the Terminal window and press
`Ctrl` + `C`. You can close the window after that.

**"Is this legal?"**
Yes. These are cameras on public roads, and choosing a route to avoid them is
legal. This is a privacy tool.

**"How current is the camera list?"**
The cameras come from a public, community-maintained map. It's updated by
volunteers, so it grows over time but is never 100% complete — which is why you
should never treat any route as guaranteed camera-free.
