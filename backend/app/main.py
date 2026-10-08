import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.game import GameSession
from app.goal import GoalPlacementError
from app.graph_store import OutsideCoverageError, ensure_covered, get_bounds, get_graph

settings = get_settings()  # fail fast on invalid config, before the app is built

# In-memory session store; moves to Redis in Part 2 (multiple instances, shared state).
sessions: dict[str, GameSession] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_graph()  # load the bundled graph once, before serving requests
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
        raise HTTPException(status_code=422, detail=str(e))
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
        raise HTTPException(status_code=503, detail=f"{e}. Try again.")

    session_id = uuid.uuid4().hex
    sessions[session_id] = session
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
        await ws.close(code=4404, reason="unknown session")
        return
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = PositionMessage.model_validate_json(raw)
                state = session.update_position(msg.lat, msg.lon, msg.accuracy)
            except ValueError as e:  # includes pydantic.ValidationError
                await ws.send_json({"type": "error", "detail": str(e)})
                continue
            await ws.send_json({"type": "state", **state})
            if state["just_reached"]:
                await ws.send_json(
                    {
                        "type": "goal_reached",
                        "elapsed_s": state["elapsed_s"],
                        "distance_walked_m": state["distance_walked_m"],
                    }
                )
    except WebSocketDisconnect:
        pass
