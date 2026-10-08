import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.game import GameSession
from app.geo import haversine_m
from app.goal import GoalPlacementError
from app.graph_store import OutsideCoverageError, ensure_covered, get_bounds, get_graph

settings = get_settings()  # fail fast on invalid config, before the app is built

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("goalpath")

# In-memory session store; moves to Redis in Part 2 (multiple instances, shared state).
sessions: dict[str, GameSession] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    G = get_graph()  # load the bundled graph once, before serving requests
    log.info("startup graph_nodes=%d graph_edges=%d", G.number_of_nodes(), G.number_of_edges())
    yield


app = FastAPI(title="GoalPath", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

Lat = Field(ge=-90, le=90, allow_inf_nan=False)
Lon = Field(ge=-180, le=180, allow_inf_nan=False)


class StartRequest(BaseModel):
    lat: float = Lat
    lon: float = Lon


class PositionMessage(BaseModel):
    lat: float = Lat
    lon: float = Lon
    accuracy: float | None = Field(None, ge=0, allow_inf_nan=False)


def _bounds() -> dict:
    min_lat, min_lon, max_lat, max_lon = get_bounds()
    return {"min_lat": min_lat, "min_lon": min_lon, "max_lat": max_lat, "max_lon": max_lon}


@app.get("/health")
def health():
    return {"status": "ok", "graph_nodes": get_graph().number_of_nodes()}


@app.get("/api/coverage")
def coverage():
    return _bounds()


@app.post("/api/games")
def start_game(req: StartRequest):
    # Sync handler: FastAPI runs it in a thread pool, so routing doesn't block the event loop.
    try:
        ensure_covered(req.lat, req.lon, settings.goal_radius_m)
    except OutsideCoverageError as e:
        log.info("game_rejected reason=%s start=%.5f,%.5f", e.code, req.lat, req.lon)
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
    try:
        session = GameSession(
            get_graph(),
            req.lat,
            req.lon,
            min_m=settings.goal_min_distance_m,
            max_m=settings.goal_radius_m,
            threshold_m=settings.goal_threshold_m,
            max_attempts=settings.goal_max_attempts,
        )
    except GoalPlacementError as e:
        log.warning("goal_placement_failed start=%.5f,%.5f error=%s", req.lat, req.lon, e)
        raise HTTPException(status_code=503, detail=f"{e}. Try again.")

    session_id = uuid.uuid4().hex
    sessions[session_id] = session
    log.info(
        "game_started session=%s start=%.5f,%.5f goal_distance_m=%.0f route_m=%.0f",
        session_id, req.lat, req.lon, haversine_m(req.lat, req.lon, *session.goal), session.route_length_m,
    )
    return {
        "session_id": session_id,
        "player": {"lat": req.lat, "lon": req.lon},
        "goal": {"lat": session.goal[0], "lon": session.goal[1]},
        "route": session.route,
        "route_length_m": session.route_length_m,
        "coverage_bounds": _bounds(),
    }


@app.websocket("/ws/games/{session_id}")
async def game_socket(ws: WebSocket, session_id: str):
    await ws.accept()  # accept first so the client receives the close code and reason
    session = sessions.get(session_id)
    if session is None:
        log.warning("ws_unknown_session session=%s", session_id)
        await ws.close(code=4404, reason="unknown session")
        return
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = PositionMessage.model_validate_json(raw)
                state = session.update_position(msg.lat, msg.lon, msg.accuracy)
            except ValueError as e:  # includes pydantic.ValidationError
                log.warning("ws_invalid_message session=%s", session_id)
                await ws.send_json({"type": "error", "detail": str(e)})
                continue
            log.debug("position session=%s lat=%.5f lon=%.5f", session_id, msg.lat, msg.lon)
            await ws.send_json({"type": "state", **state})
            if state["just_reached"]:
                log.info(
                    "goal_reached session=%s elapsed_s=%.1f walked_m=%.0f",
                    session_id, state["elapsed_s"], state["distance_walked_m"],
                )
                await ws.send_json(
                    {
                        "type": "goal_reached",
                        "elapsed_s": state["elapsed_s"],
                        "distance_walked_m": state["distance_walked_m"],
                    }
                )
    except WebSocketDisconnect:
        pass
