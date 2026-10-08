"""One-off: download the central Tel Aviv-Yafo walk graph and save it to backend/data/.

Run from the repo root: py backend/scripts/build_graph.py
"""
from pathlib import Path

import osmnx as ox

# (west, south, east, north): coast to Ayalon, Jaffa to Yarkon
BBOX = (34.760, 32.045, 34.800, 32.095)
OUT = Path(__file__).resolve().parents[1] / "data" / "tel_aviv_walk.graphml"


def main() -> None:
    ox.settings.use_cache = False  # one-off build; don't leave an HTTP cache in the repo
    G = ox.graph_from_bbox(BBOX, network_type="walk")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, OUT)
    size_mb = OUT.stat().st_size / 1_000_000
    print(f"saved {OUT} | {size_mb:.1f} MB | {len(G.nodes)} nodes | {len(G.edges)} edges")


if __name__ == "__main__":
    main()
