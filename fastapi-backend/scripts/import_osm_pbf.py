"""
Import businesses from a Geofabrik .osm.pbf file into a small SQLite file.
Run from the fastapi-backend folder:
    python scripts/import_osm_pbf.py data/pbf/pakistan-latest.osm.pbf
"""
import os
import sqlite3
import sys
import time

import osmium

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from app.services.osm.overpass_client import osm_element_to_record  # noqa: E402

DB_PATH = os.path.join(BASE, "data", "osm_places.sqlite")

MAIN_KEYS = {"amenity", "shop", "healthcare", "leisure", "tourism", "office", "craft"}
KV_KEYS = MAIN_KEYS | {"cuisine", "religion"}


class Handler(osmium.SimpleHandler):
    def __init__(self, con):
        super().__init__()
        self.con = con
        self.batch = []
        self.total = 0

    def _save(self, ref, tags, lat, lon):
        rec = osm_element_to_record({"tags": tags, "lat": lat, "lon": lon})
        if not rec.get("business_name"):
            return
        kv = "|" + "|".join(f"{k}={tags[k]}" for k in KV_KEYS if k in tags) + "|"
        self.batch.append((
            ref, rec["business_name"], lat, lon, kv, rec["phone"], rec["website"],
            rec["email"], rec["facebook"], rec["instagram"], rec["address"],
        ))
        if len(self.batch) >= 20000:
            self.flush()

    def flush(self):
        if not self.batch:
            return
        self.con.executemany(
            "INSERT OR REPLACE INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?)", self.batch
        )
        self.con.commit()
        self.total += len(self.batch)
        self.batch = []
        print(f"  saved {self.total} places...")

    def node(self, n):
        if n.tags.get("name") is None:
            return
        if not n.location.valid():
            return
        tags = {t.k: t.v for t in n.tags}
        if not (MAIN_KEYS & tags.keys()):
            return
        self._save(f"n{n.id}", tags, n.location.lat, n.location.lon)

    def way(self, w):
        if w.tags.get("name") is None:
            return
        tags = {t.k: t.v for t in w.tags}
        if not (MAIN_KEYS & tags.keys()):
            return
        try:
            pts = [(nd.location.lat, nd.location.lon) for nd in w.nodes if nd.location.valid()]
        except Exception:
            return
        if not pts:
            return
        lat = sum(p[0] for p in pts) / len(pts)
        lon = sum(p[1] for p in pts) / len(pts)
        self._save(f"w{w.id}", tags, lat, lon)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_osm_pbf.py <file.osm.pbf>")
        sys.exit(1)
    pbf = sys.argv[1]
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS places (
            ref TEXT PRIMARY KEY, name TEXT, lat REAL, lon REAL, kv TEXT,
            phone TEXT, website TEXT, email TEXT, facebook TEXT, instagram TEXT, address TEXT)"""
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_places_lat_lon ON places(lat, lon)")
    start = time.time()
    h = Handler(con)
    h.apply_file(pbf, locations=True, idx="flex_mem")
    h.flush()
    print(f"Done. {h.total} places imported in {time.time() - start:.0f}s -> {DB_PATH}")
    con.close()


if __name__ == "__main__":
    main()