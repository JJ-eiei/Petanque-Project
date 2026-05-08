# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Browser-only petanque (French boules) scoring detector. Each `.html` file is a fully self-contained app (CSS + JS inline). No build step, no dependencies, no backend — just open in a browser served via `localhost`.

**Camera API requires `localhost` or HTTPS.** Never open via `file://`.

```bash
# Serve locally (pick any):
python3 -m http.server 8080
npx serve .
```

## File Versions (iterative evolution)

| File | Key addition |
|---|---|
| `petanque_detector.html` | v1 — click to set jack center, ring-based scoring |
| `petanque_detector2.html` | v2 — multi-color ball selection, sensitivity slider |
| `petanque_detector3.html` | v3 — frame-count stability gate before scoring |
| `pet4.html` | v4 — 4-point homography for perspective-correct distances |
| `pet5.html` | v5 — time-based stability (5s countdown ring) |
| `pet6.html` | **v6 (latest)** — auto-detects pink jack via color; jack gets its own 1.5s lock timer |

`pet6.html` is the canonical version. Changes should usually start there.

## Core Architecture (pet6.html)

**Detection** — `detectBoth(data, cw, ch)`: scans every 4th pixel via raw `ImageData`, accumulates centroid of pink pixels (jack) and selected-color pixels (player). Returns `{jack, player}` as centroid `{x, y}` or `null`. No ML; pure RGB thresholding in `matchPlayerC(r, g, b, s)`.

**Homography** — `createHomography(src, dst)` + `solve(A, b)`: builds an 8×8 linear system (Gaussian elimination) from 4 point-pairs to compute a projective transform. User clicks 4 field corners → `toFlat(x,y)` maps screen pixels to a virtual 1000×1000 flat plane; `toScreen(x,y)` inverts. This corrects perspective so Euclidean distance on the flat plane equals real-world distance.

**Scoring zones** — `ZONES` array: 5 concentric rings (50/40/30/20/10 pts), radius defined as a fraction of 500 flat-plane units. `getZone(bx, by, cw, ch)` converts ball and jack to flat coords, measures `Math.hypot`, finds innermost zone.

**Stability timers** — both jack and player require the centroid to stay within 15px for a continuous duration:
- Jack: `JACK_WAIT_MS = 1500 ms` → locks `lockedJack`
- Player: `WAIT_MS = 3000 ms` → calls `recordScore()`
- Progress drawn as arc sweep around the ball centroid.

**Main loop** — `loop()` runs via `requestAnimationFrame`. Each frame: draw video → draw zones (warped through homography) → detect → handle jack lock → handle player scoring.

## Tuning Parameters

All constants are at the top of `<script>`:

- `WAIT_MS` / `JACK_WAIT_MS` — stability dwell time before committing a score/lock
- `sensitivity` (1–5, slider) — multiplied by 12 to shift RGB thresholds in `matchPlayerC` and `detectBoth`
- `ZONES[i].r` — zone radius as a fraction of 0.52 (outermost); change to resize rings
- Pink jack detection: `r > 150 && b > 120 && g < 120 && r > g * 1.5` — tweak for lighting conditions
- `minP = Math.max(4, 15 - sensitivity*2)` — minimum pixel count to confirm a detection

## Common Changes

**Add a new ball color**: extend `matchPlayerC` switch + add a `.color-btn` element in HTML with a matching `data-c` attribute.

**Adjust zone points or count**: edit the `ZONES` array; `drawZones` and `getZone` derive everything from it.

**Change camera resolution**: edit the `getUserMedia` constraints (`width.ideal`, `height.ideal`).
