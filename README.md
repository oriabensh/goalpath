# ⚽ GoalPath 🥅

A web-based navigation game: walk your soccer ball to a randomly placed goal along the shortest walkable route.

> Home assignment for High Lander — Part 1.

## Features

- **Live player marker**: a soccer ball shown at the player's real-time location.
- **Goal generation**: on game start, a static goal marker is placed within a configurable radius of the player.
- **Shortest path**: the shortest walkable path from player to goal is computed and drawn on the map.
- **Goal detection**: "Goal reached" feedback when the player is within a proximity threshold.
- **Dynamic re-routing (bonus)**: the route updates when the player deviates from it.
- **Demo mode**: clearly labeled and off by default. Moves the ball along the route or via arrow keys, for demoing on a stationary laptop.

## Quick start

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
docker compose up
```

Open <http://localhost:8080> (or your `FRONTEND_PORT`) and allow location access when the browser asks.

## Troubleshooting location

Geolocation works on `localhost` without HTTPS, since browsers treat it as a secure context.
If the ball does not appear, check that location services are enabled at the OS level:

- **Windows 11**: Settings → Privacy & security → Location → turn on *Location services* and *Let desktop apps access your location*.
- **macOS**: System Settings → Privacy & Security → Location Services → turn it on and enable it for your browser.
- **Browser**: click the icon left of the address bar and set *Location* to *Allow* for the site, then reload.

Desktop machines without GPS use Wi-Fi/IP-based positioning, which can be off by tens of meters. Use demo mode if needed.

## Configuration

All parameters are set through environment variables (see `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `GOAL_RADIUS_M` | `500` | Maximum distance (m) of the goal from the player |
| `GOAL_MIN_DISTANCE_M` | `100` | Minimum distance (m) of the goal from the player |
| `GOAL_THRESHOLD_M` | `20` | Distance (m) at which the goal counts as reached |
| `REROUTE_THRESHOLD_M` | `25` | Deviation (m) from the path that triggers a re-route |
| `BACKEND_PORT` | `8000` | FastAPI port |
| `FRONTEND_PORT` | `8080` | Web page port |

## Architecture

```
┌──────────────────────────────┐
│ Browser (Leaflet + JS)       │
│  Geolocation.watchPosition   │
└──────────────┬───────────────┘
               │ WebSocket: position ↑ / route, goal, status ↓
┌──────────────▼───────────────┐
│ FastAPI backend              │
│  game state, goal detection, │
│  deviation check / re-route  │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│ Routing                      │
│  OSMnx pedestrian graph      │
│  (cache / bundled Tel Aviv)  │
│  A* (haversine) on NetworkX  │
└──────────────────────────────┘
```

Module layout: TBD.

## Decision Log

| # | Decision | Why |
|---|---|---|
| 1 | Backend in Python + FastAPI | Async WebSocket support, small footprint, strong geo ecosystem. |
| 2 | Routing on the OSM pedestrian network (OSMnx + NetworkX) | Free, real walkable paths, no API keys. |
| 3 | Self-implemented A* with a haversine heuristic | Admissible heuristic on geographic graphs; shows the algorithm explicitly. |
| 4 | Frontend: plain HTML/JS with Leaflet | No build step, no Node; minimal moving parts. |
| 5 | Location via browser Geolocation API (`watchPosition`) streamed over WebSocket | A container can't access host location hardware; the browser is the bridge. |
| 6 | Goal detection is server-side | Single source of truth for game state. |
| 7 | Goal: uniform random point in radius, min distance, snapped to nearest walkable node, guaranteed reachable | Fair placement, avoids trivial goals, never unreachable. |
| 8 | Re-route only when deviation exceeds a configurable threshold | Avoids recomputing on GPS jitter. |
| 9 | Demo mode: labeled, off by default (auto-walk or arrow keys) | Demo on a stationary laptop; real location stays the default. |
| 10 | Road graph downloaded on game start and cached; Tel Aviv pre-bundled | Fast repeat starts; works offline for the main area. |
| 11 | All parameters from environment variables | Configurable without code changes. |
| 12 | Run locally with `docker compose up`; no paid services or API keys | One-command setup, free to run. |
| 13 | LF line endings enforced (`.gitattributes`) | Code runs in Linux containers; CRLF can break scripts. |

## Local development without Docker (Windows)

TBD — expected commands:

```powershell
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r backend/requirements.txt
py -m uvicorn app.main:app --reload --port 8000 --app-dir backend   # entry point TBD
```

Serve the frontend with any static server, e.g. `py -m http.server 8080 --directory frontend`.

## Testing

TBD — run from the repo root:

```powershell
py -m pytest
```

Tests are derived from the assignment requirements: for each major component, a normal case, the most important edge case, and invalid input.

## Known limitations / next steps

- Location accuracy depends on the device; desktop positioning can be coarse.
- Areas outside Tel Aviv require internet access on first start to download the graph.
- Single player only.
- **Part 2 (not in scope):** multiplayer, shared state in Redis, CI/CD pipeline.
