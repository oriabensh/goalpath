"use strict";

const API = `http://${location.hostname}:8000`;
const WS_BASE = `ws://${location.hostname}:8000`;
const TEL_AVIV = [32.0809, 34.7806];
const DEMO_STEP_M = 10;
const ROUTE_COLOR = "#1f6feb";

const $ = (id) => document.getElementById(id);

// --- Map -------------------------------------------------------------------

const map = L.map("map", { keyboard: false }).setView(TEL_AVIV, 14); // arrow keys are used by demo mode
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

const ballIcon = L.icon({ iconUrl: "assets/ball.png", iconSize: [32, 32], iconAnchor: [16, 16] });
const goalIcon = L.icon({ iconUrl: "assets/goal.png", iconSize: [56, 24], iconAnchor: [28, 12] });

const state = {
  pos: null, // {lat, lon, accuracy} currently shown and sent
  lastReal: null, // last real fix, restored when demo mode is turned off
  demo: false,
  centered: false,
  ws: null,
  finished: false,
  layers: [], // goal marker + route lines of the current game
};
let ball = null;
let accuracyCircle = null;
let coverageRect = null;

// --- Position (real and demo share this path) ------------------------------

function setPosition(lat, lon, accuracy) {
  state.pos = { lat, lon, accuracy };
  const latlng = [lat, lon];

  if (!ball) ball = L.marker(latlng, { icon: ballIcon, zIndexOffset: 1000 }).addTo(map);
  else ball.setLatLng(latlng);

  if (accuracy != null) {
    if (!accuracyCircle) {
      accuracyCircle = L.circle(latlng, { radius: accuracy, weight: 1, color: ROUTE_COLOR, fillOpacity: 0.08 }).addTo(map);
    } else {
      accuracyCircle.setLatLng(latlng).setRadius(accuracy);
    }
  } else if (accuracyCircle) {
    accuracyCircle.remove();
    accuracyCircle = null;
  }

  $("acc").textContent = accuracy != null ? Math.round(accuracy) : "–";
  if (!state.centered) {
    map.setView(latlng, 16);
    state.centered = true;
  }
  $("start").disabled = false;
  if (!state.demo) setHint("");
  sendPosition();
}

function sendPosition() {
  const { ws, pos } = state;
  if (ws && ws.readyState === WebSocket.OPEN && !state.finished && pos) {
    ws.send(JSON.stringify({ lat: pos.lat, lon: pos.lon, accuracy: pos.accuracy }));
  }
}

function onFix(p) {
  const { latitude, longitude, accuracy } = p.coords;
  state.lastReal = { lat: latitude, lon: longitude, accuracy };
  if (state.demo) return; // demo mode ignores real location
  hidePanel("location");
  setPosition(latitude, longitude, accuracy);
}

function onFixError(err) {
  if (state.demo) return;
  if (err.code === err.TIMEOUT && state.lastReal) return; // transient; keep the last fix
  showLocationError();
}

function startLocation() {
  if (!("geolocation" in navigator)) return showLocationError();
  navigator.geolocation.watchPosition(onFix, onFixError, { enableHighAccuracy: true, maximumAge: 0, timeout: 30000 });
}

// --- Game ------------------------------------------------------------------

async function startGame() {
  if (!state.pos) return;
  resetGame();
  const btn = $("start");
  btn.disabled = true;
  btn.textContent = "Starting…";
  try {
    const res = await fetch(`${API}/api/games`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat: state.pos.lat, lon: state.pos.lon }),
    });
    const data = await res.json().catch(() => ({}));
    const code = data.detail && data.detail.code;
    if (code === "outside_coverage" || code === "near_edge") return showCoverageError(code);
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Server error (${res.status}).`);
    drawGame(data);
    openSocket(data.session_id);
  } catch (e) {
    const msg = e instanceof TypeError ? `Can't reach the server at ${API}. Is the backend running?` : e.message;
    showPanel("error", "Couldn't start the game", textBlock(msg), [{ label: "OK", primary: true }]);
  } finally {
    btn.disabled = false;
    btn.textContent = state.layers.length ? "New game" : "Start game";
  }
}

function drawGame(data) {
  const route = data.route; // [[lat, lon], ...]; route[0] is the player's real position
  const goal = [data.goal.lat, data.goal.lon];
  state.layers = [
    L.polyline(route.slice(0, 2), { color: ROUTE_COLOR, weight: 4, dashArray: "6 8" }), // ball -> street
    L.polyline(route.slice(1), { color: ROUTE_COLOR, weight: 5, opacity: 0.85 }),
    L.marker(goal, { icon: goalIcon }),
  ].map((layer) => layer.addTo(map));
  map.fitBounds(L.latLngBounds(route).extend(goal), { padding: [40, 40] });
  updateDemoHint();
}

function resetGame() {
  closeSocket();
  state.layers.forEach((layer) => layer.remove());
  state.layers = [];
  state.finished = false;
  $("dist").textContent = "–";
  $("goal-overlay").hidden = true;
  updateDemoHint();
}

function onGoalReached(msg) {
  state.finished = true;
  closeSocket();
  const s = Math.round(msg.elapsed_s);
  $("goal-time").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  $("goal-dist").textContent = Math.round(msg.distance_walked_m);
  $("goal-overlay").hidden = false;
  updateDemoHint();
}

// --- WebSocket -------------------------------------------------------------

function openSocket(sessionId) {
  hidePanel("socket");
  const ws = new WebSocket(`${WS_BASE}/ws/games/${sessionId}`);
  state.ws = ws;
  ws.onopen = sendPosition;
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "state") $("dist").textContent = Math.round(msg.distance_to_goal_m);
    else if (msg.type === "goal_reached") onGoalReached(msg);
    else if (msg.type === "error") console.warn("Server rejected position:", msg.detail);
  };
  ws.onclose = (ev) => {
    if (state.ws !== ws || state.finished) return; // closed on purpose
    state.ws = null;
    if (ev.code === 4404) {
      showPanel("socket", "Game not found", textBlock("The server no longer has this game (it may have restarted)."), [
        { label: "Start new game", primary: true, onClick: startGame },
      ]);
    } else {
      showPanel("socket", "Connection lost", textBlock("The live connection to the server closed."), [
        { label: "Retry", primary: true, onClick: () => openSocket(sessionId) },
      ]);
    }
  };
}

function closeSocket() {
  const ws = state.ws;
  state.ws = null; // mark as intentional before closing
  if (ws) ws.close();
}

// --- Demo mode -------------------------------------------------------------

function setDemo(on) {
  state.demo = on;
  $("demo-toggle").checked = on;
  $("demo-badge").hidden = !on;
  document.body.classList.toggle("demo", on);
  if (on) {
    updateDemoHint();
    showCoverageArea();
  } else {
    setHint(state.lastReal ? "" : "Waiting for your location…");
    if (coverageRect) coverageRect.remove();
    coverageRect = null;
    if (state.lastReal) {
      setPosition(state.lastReal.lat, state.lastReal.lon, state.lastReal.accuracy);
    } else {
      // No real fix: drop the demo position so a game can't start from it outside demo mode.
      state.pos = null;
      if (ball) ball.remove();
      ball = null;
      $("start").disabled = true;
    }
  }
}

function useDemo() {
  hidePanel();
  setDemo(true);
}

async function showCoverageArea() {
  try {
    const b = await (await fetch(`${API}/api/coverage`)).json();
    if (!state.demo) return;
    const bounds = [[b.min_lat, b.min_lon], [b.max_lat, b.max_lon]];
    if (coverageRect) coverageRect.remove();
    coverageRect = L.rectangle(bounds, { color: "#d9480f", weight: 2, dashArray: "4 6", fill: false, interactive: false }).addTo(map);
    if (!state.pos || !L.latLngBounds(bounds).contains([state.pos.lat, state.pos.lon])) map.fitBounds(bounds);
  } catch {
    // Coverage outline is a convenience; ignore if the backend is unreachable.
  }
}

const inGame = () => state.layers.length > 0 && !state.finished;

function updateDemoHint() {
  if (state.demo) setHint(inGame() ? "Use arrow keys to walk" : "Click the map to set your start point");
}

// Click = choose a start point (before the game only); arrows = walking. No teleporting mid-game.
map.on("click", (e) => {
  if (state.demo && !inGame()) setPosition(e.latlng.lat, e.latlng.lng, null);
});

document.addEventListener("keydown", (e) => {
  if (!state.demo || !state.pos) return;
  const dir = { ArrowUp: [1, 0], ArrowDown: [-1, 0], ArrowRight: [0, 1], ArrowLeft: [0, -1] }[e.key];
  if (!dir) return;
  e.preventDefault();
  const mPerDegLat = 111320;
  const mPerDegLon = mPerDegLat * Math.cos((state.pos.lat * Math.PI) / 180);
  setPosition(state.pos.lat + (dir[0] * DEMO_STEP_M) / mPerDegLat, state.pos.lon + (dir[1] * DEMO_STEP_M) / mPerDegLon, null);
});

// --- Panels and hints ------------------------------------------------------

let panelKind = null;

function showPanel(kind, title, body, actions) {
  panelKind = kind;
  $("panel-title").textContent = title;
  $("panel-body").replaceChildren(body);
  $("panel-actions").replaceChildren(
    ...actions.map(({ label, primary, onClick }) => {
      const btn = document.createElement("button");
      btn.textContent = label;
      if (primary) btn.className = "primary";
      btn.onclick = () => {
        hidePanel();
        if (onClick) onClick();
      };
      return btn;
    })
  );
  $("panel").hidden = false;
}

function hidePanel(kind) {
  if (kind && kind !== panelKind) return;
  $("panel").hidden = true;
  panelKind = null;
}

function textBlock(text) {
  const p = document.createElement("p");
  p.textContent = text;
  return p;
}

function setHint(text) {
  $("hint").textContent = text;
}

function showLocationError() {
  const body = document.createElement("div");
  body.innerHTML = `
    <p>GoalPath needs your device's location. Enable it, then reload:</p>
    <ul>
      <li><b>Windows:</b> Settings → Privacy &amp; security → Location → turn on <i>Location services</i> and <i>Let desktop apps access your location</i>.</li>
      <li><b>macOS:</b> System Settings → Privacy &amp; Security → Location Services → turn on for your browser.</li>
      <li><b>Browser:</b> allow location for this site (icon left of the address bar).</li>
    </ul>`;
  showPanel("location", "Location unavailable", body, [
    { label: "Reload", onClick: () => location.reload() },
    { label: "Use demo mode", primary: true, onClick: useDemo },
  ]);
}

function showCoverageError(code) {
  const text =
    code === "near_edge"
      ? "Too close to the edge of the covered area (central Tel Aviv)."
      : "This area isn't supported yet. GoalPath currently covers central Tel Aviv.";
  showPanel("coverage", "Outside the play area", textBlock(text), [
    { label: "Close" },
    { label: "Use demo mode", primary: true, onClick: useDemo },
  ]);
}

// --- Wire up ---------------------------------------------------------------

$("start").onclick = startGame;
$("play-again").onclick = startGame;
$("demo-toggle").onchange = (e) => setDemo(e.target.checked);
startLocation();
