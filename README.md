# ⚽ GoalPath 🥅

A web-based navigation game: walk your soccer ball to a randomly placed goal along the shortest walkable route.

> Home assignment for High Lander — Part 1.

## Features

- **Live player marker**: a soccer ball shown at the player's real-time location.
- **Goal generation**: on game start, a static goal marker is placed within a configurable radius of the player.
- **Shortest path**: the shortest walkable path from player to goal is computed and drawn on the map.
- **Goal detection**: "Goal reached" feedback when the player is within a proximity threshold.
- **Dynamic re-routing (bonus)**: the route updates when the player deviates from it.
- **Coverage**: central Tel Aviv-Yafo (pre-bundled walk graph, works fully offline). Outside it, the game shows a clear error.
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
| `GOAL_THRESHOLD_M` | `20` | Distance (m) at which the goal counts as reached (must be < `GOAL_MIN_DISTANCE_M`) |
| `REROUTE_THRESHOLD_M` | `25` | Deviation (m) from the path that triggers a re-route |
| `GOAL_MAX_ATTEMPTS` | `20` | Goal placement retries before giving up |
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
│  OSM walk graph, bundled     │
│  (central Tel Aviv-Yafo)     │
│  A* (haversine) on NetworkX  │
└──────────────────────────────┘
```

Backend modules (`backend/app/`):

| Module | Role |
|---|---|
| `config.py` | Settings from env vars, validated at startup |
| `geo.py` | Haversine distance, destination point |
| `graph_store.py` | Loads the bundled graph once; coverage check |
| `routing.py` | Nearest node, A*, route coordinates |
| `goal.py` | Goal candidate sampling, snapping and reachability |
| `game.py` | Game session: goal, route, progress, goal detection (no FastAPI) |
| `main.py` | FastAPI app: REST endpoints, WebSocket, in-memory session store |

Frontend: TBD.

### API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | `{"status": "ok", "graph_nodes": n}` |
| `GET` | `/api/coverage` | Covered area bounds: `min_lat`, `min_lon`, `max_lat`, `max_lon` |
| `POST` | `/api/games` | Body `{lat, lon}`. Returns `session_id`, `player`, `goal`, `route` (list of `[lat, lon]`), `route_length_m`, `coverage_bounds`. `422` for invalid input or outside coverage; `503` if no goal could be placed |
| `WS` | `/ws/games/{session_id}` | Live position stream (below). Unknown session → close code `4404` |

Interactive docs: <http://localhost:8000/docs>.

### WebSocket messages

Client → server, on every position fix (`accuracy` optional, display-only):

```json
{"lat": 32.0809, "lon": 34.7806, "accuracy": 35}
```

Server → client:

```json
{"type": "state", "player": {"lat": 32.0809, "lon": 34.7806}, "accuracy_m": 35,
 "distance_to_goal_m": 268.6, "reached": false, "just_reached": false,
 "elapsed_s": 4.1, "distance_walked_m": 0.0}
{"type": "goal_reached", "elapsed_s": 93.2, "distance_walked_m": 431.0}
{"type": "error", "detail": "..."}
```

`goal_reached` is sent once, right after the `state` that reached the goal. Further positions return the frozen final `state`. An invalid message gets an `error` reply and the connection stays open.

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
| 10 | ~~Road graph downloaded on game start and cached; Tel Aviv pre-bundled~~ (superseded by #19) | Fast repeat starts; works offline for the main area. |
| 11 | All parameters from environment variables | Configurable without code changes. |
| 12 | Run locally with `docker compose up`; no paid services or API keys | One-command setup, free to run. |
| 13 | LF line endings enforced (`.gitattributes`) | Code runs in Linux containers; CRLF can break scripts. |
| 14 | Goal sampled uniformly by area (sqrt of uniform in ring) | Avoids clustering near the player. |
| 15 | Config validated at startup | Misconfiguration fails fast, not mid-game. |
| 16 | Injectable seeded RNG for goal generation | Deterministic tests. |
| 17 | Pedestrian network (OSM walk) | Player is a person; ~500 m radius is walking scale. |
| 18 | Self-implemented A* + haversine heuristic | Optimal like Dijkstra, explores fewer nodes, fully explainable. |
| 19 | Single bundled Tel Aviv graph, loaded once into memory | Fully offline, simple, fast; dynamic per-location loading is the next step. |
| 20 | Outside coverage → clear error + manual start point | A reviewer anywhere can still play; no fake data. |
| 21 | Goal snapped to a reachable node | A goal inside a building or with no route would break the game. |
| 22 | Brute-force nearest node | Simple, no dependency; spatial index is the scaling path. |
| 23 | Routing tests on a hand-built graph | Fast, deterministic, test the algorithm not OSM data. |
| 24 | Domain logic separated from transport (`game.py` vs `main.py`) | Testable without a server; Part 2 adds players without rewriting it. |
| 25 | Server-side goal detection | Single source of truth; required for "first to reach" in Part 2. |
| 26 | Goal detection by threshold only, accuracy display-only | Desktop Wi-Fi accuracy is coarse; gating would block the requirement. |
| 27 | Goal reached is final, triggered once | No duplicate feedback; ready for winner logic in Part 2. |
| 28 | In-memory session store | Enough for Part 1; Redis in Part 2 for multiple instances. |
| 29 | `GOAL_THRESHOLD_M` < `GOAL_MIN_DISTANCE_M` validated | Prevents a goal reached at spawn. |
| 30 | Radius measured straight-line | Reading of "within a defined radius"; walking route may be longer. |
| 31 | Manual start point only in labeled demo mode | Real host location stays the default, per the requirement. |

## Local development without Docker (Windows)

From the repo root:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r backend/requirements.txt
copy .env.example .env   # optional; defaults apply without it
py -m pytest
```

With the venv activated, `py` uses the venv interpreter.

The walk graph is already bundled in `backend/data/`. To rebuild it (needs internet):

```powershell
py backend/scripts/build_graph.py
```

Run the backend (from the repo root, venv activated):

```powershell
py -m uvicorn app.main:app --app-dir backend --reload
```

Then open <http://localhost:8000/docs>. Running the frontend: TBD.

## Testing

From the repo root (`pytest.ini` puts `backend/` on the import path):

```powershell
py -m pytest
```

Tests are derived from the assignment requirements: for each major component, a normal case, the most important edge case, and invalid input.

## Known limitations / next steps

- Location accuracy depends on the device; desktop positioning can be coarse.
- Coverage is central Tel Aviv-Yafo only (lat 32.045–32.095, lon 34.760–34.800). The player must be at least `GOAL_RADIUS_M` inside its edges. Next step: dynamic per-location graph loading.
- Single player only.
- **Part 2 (not in scope):** multiplayer, shared state in Redis, CI/CD pipeline.
