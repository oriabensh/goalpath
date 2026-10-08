# ⚽ GoalPath 🥅

## What it does

GoalPath is a web navigation game: the ball (the player, shown at the host's real location) must reach a goal generated nearby.
The shortest walkable path to the goal is computed, drawn on the map, and updated as the player moves.

```
Browser (Leaflet, Geolocation)
        │  REST: start game  ·  WebSocket: position ↑ / state + route ↓
FastAPI (game logic, A*)
        │
Bundled Tel Aviv walk graph (OpenStreetMap)
```

Every Part 1 requirement, and where it's met: [requirements coverage](docs/DETAILS.md#requirements-coverage).

## How to run

**Prerequisite:** [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
docker compose up --build -d   # then open http://localhost:8080 and allow location access
docker compose down            # stop
```

Covers central Tel Aviv; outside it or without location, turn on **Demo** (click a start point, then arrow keys or **Auto-walk**).

Tests: `docker compose run --rm backend python -m pytest`

## Key decisions

| Decision | Why |
|---|---|
| Self-implemented A* on the OSM walk network | No cloud dependency; optimal (verified vs Dijkstra) |
| Location from the browser on the host | A container can't access location hardware |
| Bundled Tel Aviv graph | Offline routing, simple; dynamic loading is the next step |
| Goal sampled uniformly by area, snapped to a reachable node | Fair spread; always reachable |
| Server-side goal detection, triggered once | Single source of truth; ready for "first to reach" |
| Re-route only on deviation (max(25 m, GPS accuracy)) | Cheap updates, no flicker |
| Demo mode on the same pipeline as real location | Demos test the real system; off by default |
| Domain logic separated from transport | Testable without a server; extendable to multiplayer |

Full decision log: [docs/DETAILS.md](docs/DETAILS.md#decision-log)

## With more time

- Dynamic map loading for any location (or a local OSRM)
- Redis sessions → stateless backends; multiplayer (Part 2)
- Spatial index for nearest-node lookup
- Reverse proxy (single origin) + HTTPS for phones
- Full dependency lock file; slimmer backend image
- CI/CD pipeline (Part 2)
