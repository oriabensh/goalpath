# ⚽ GoalPath 🥅

A web-based navigation game: walk your soccer ball to a randomly placed goal along the shortest walkable route.

> Home assignment for High Lander — Part 1.

## Features

- **Live player marker**: a soccer ball shown at the player's real-time location.
- **Goal generation**: on game start, a static goal marker is placed within a configurable radius of the player.
- **Shortest path**: the shortest walkable path from player to goal is computed and drawn on the map.
- **Goal detection**: "Goal reached" feedback when the player is within a proximity threshold.
- **Dynamic re-routing (bonus)**: the route updates as the player moves. It is trimmed while on route and recomputed with A* when the player deviates.
- **Coverage**: central Tel Aviv-Yafo (pre-bundled walk graph, works fully offline). Outside it, the game shows a clear error.
- **Demo mode**: off by default, marked with a DEMO badge. Before the game, click the map to set the start point; during the game, arrow keys walk the ball 10 m per press. For demoing on a stationary laptop.

## Quick start

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
docker compose up --build -d   # start (first build takes a few minutes)
docker compose ps              # backend should be "healthy"
docker compose down            # stop
```

Open <http://localhost:8080> (or your `FRONTEND_PORT`) and allow location access when the browser asks. The API runs on <http://localhost:8000> (fixed port). No `.env` is needed; copy `.env.example` to `.env` to override the defaults.

Run the tests in the container: `docker compose run --rm backend python -m pytest`.

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
| `FRONTEND_PORT` | `8080` | Web page port (the backend is fixed at `8000`) |
| `LOG_LEVEL` | `INFO` | Backend log level (`DEBUG` adds per-position logs) |

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
| `geo.py` | Haversine distance, destination point, point-to-segment distance |
| `graph_store.py` | Loads the bundled graph once; coverage check |
| `routing.py` | Nearest node, A*, route coordinates |
| `goal.py` | Goal candidate sampling, snapping and reachability |
| `game.py` | Game session: goal, route updates and rerouting, progress, goal detection (no FastAPI) |
| `main.py` | FastAPI app: REST endpoints, WebSocket, in-memory session store |

Frontend (`frontend/`, no build): `index.html`, `app.js` (map, geolocation, WebSocket, demo mode), `style.css`. It calls the backend at `http://<page host>:8000`.

### API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | `{"status": "ok", "graph_nodes": n}` |
| `GET` | `/api/coverage` | Covered area bounds: `min_lat`, `min_lon`, `max_lat`, `max_lon` |
| `POST` | `/api/games` | Body `{lat, lon}`. Returns `session_id`, `player`, `goal`, `route` (list of `[lat, lon]`), `route_length_m`, `coverage_bounds`. `422` for invalid input, or `{"detail": {"code": "outside_coverage" \| "near_edge", "message"}}`; `503` if no goal could be placed |
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
 "elapsed_s": 4.1, "distance_walked_m": 0.0,
 "route": [[32.0809, 34.7806], ...], "route_length_m": 412.3, "rerouted": false, "off_coverage": false}
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
| 8 | Re-route only when deviation exceeds a configurable threshold (see #44–45) | Avoids recomputing on GPS jitter. |
| 9 | Demo mode: labeled, off by default (click/arrow keys; auto-walk optional, not built yet) | Demo on a stationary laptop; real location stays the default. |
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
| 20 | ~~Outside coverage → clear error + manual start point~~ (replaced by #31) | A reviewer anywhere can still play; no fake data. |
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
| 32 | Vanilla JS + Leaflet, no build | Simple, fast to run, nothing to install. |
| 33 | Route starts at the player's real position (dashed connector) | The ball stays at the true location; the line visibly connects it to the street. |
| 34 | Walked distance ignores steps under GPS accuracy | Stationary jitter doesn't inflate the distance. |
| 35 | Demo positions use the same pipeline as real ones | Demo tests the real system, not a separate path. |
| 36 | Backend port fixed at 8000 | The frontend calls it directly; reverse proxy is the next step. |
| 37 | Structured logging with `LOG_LEVEL` | Observability without per-position noise. |
| 38 | Two containers (FastAPI + nginx) | Separate concerns; static files served efficiently. |
| 39 | Healthcheck + `depends_on: service_healthy` | The frontend starts only when the API is ready. |
| 40 | `restart: unless-stopped` | Recovers from crashes without manual action. |
| 41 | Pinned versions tested in the image | Reproducible builds. |
| 42 | Non-root container user | Basic container security. |
| 43 | Demo: click = start point, arrows = walking | Each demo action mirrors a real one; no teleporting mid-game. |
| 44 | Trim on route, A* only on deviation | Cheap updates; full recompute only when needed. |
| 45 | Deviation threshold = max(`REROUTE_THRESHOLD_M`, GPS accuracy) | Poor accuracy doesn't cause constant reroutes. |
| 46 | Outside coverage keeps the last route | The game degrades gracefully instead of failing. |
| 47 | Monotonic trimming | A route that doubles back can't skip ahead. |
| 48 | Reroute A* in a worker thread | Doesn't block other WebSocket messages. |

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

API docs: <http://localhost:8000/docs>. Serve the frontend in a second terminal:

```powershell
py -m http.server 8080 --directory frontend
```

Open <http://localhost:8080> and allow location access. Demo mode: tick **Demo**, click the map to place the ball, and use the arrow keys to move it.

## Testing

From the repo root (`pytest.ini` puts `backend/` on the import path):

```powershell
py -m pytest
```

Tests are derived from the assignment requirements: for each major component, a normal case, the most important edge case, and invalid input.

## Scaling

- Move sessions to Redis → stateless backends behind a load balancer (today: one worker, in-memory).
- Fan out WebSocket updates across instances via Redis pub/sub.
- Replace the brute-force nearest-node scan with a spatial index (KD-tree / R-tree).
- Wider coverage: per-region graphs loaded on demand, or a local OSRM/Valhalla routing service.

## Known limitations / next steps

- Location accuracy depends on the device; desktop positioning can be coarse.
- Coverage is central Tel Aviv-Yafo only (lat 32.045–32.095, lon 34.760–34.800). The player must be at least `GOAL_RADIUS_M` inside its edges. Next step: dynamic per-location graph loading.
- Geolocation works only on `localhost` over HTTP; other devices need HTTPS.
- Single player only.
- Sessions are kept in memory with no expiry (Part 2: TTL / Redis).
- Only direct dependencies are pinned; transitive versions can drift (next: a full lock file).
- Backend image is ~690 MB, mostly the OSMnx/geopandas stack.
- Demo walking needs arrow keys; no phone support.
- With real desktop location (Wi-Fi accuracy), reroutes are rare by design; demo mode shows them.
- **Part 2 (not in scope):** multiplayer, shared state in Redis, CI/CD pipeline.
