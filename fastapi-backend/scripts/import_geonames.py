"""
Import city centres from GeoNames into the same SQLite file (for offline city lookup).
Run from the fastapi-backend folder:
    python scripts/import_geonames.py data/geonames/cities15000.txt data/geonames/countryInfo.txt
"""
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "data", "osm_places.sqlite")


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/import_geonames.py <cities15000.txt> <countryInfo.txt>")
        sys.exit(1)
    cities_file, country_file = sys.argv[1], sys.argv[2]

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS cities (name TEXT, lat REAL, lon REAL, cc TEXT, pop INTEGER)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_cities_name ON cities(name)")
    con.execute("CREATE TABLE IF NOT EXISTS countries (cc TEXT PRIMARY KEY, name TEXT)")
    con.execute("DELETE FROM cities")
    con.execute("DELETE FROM countries")

    rows = []
    with open(cities_file, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 15:
                continue
            lat, lon, cc = float(p[4]), float(p[5]), p[8]
            pop = int(p[14] or 0)
            names = {p[1], p[2]} | set(p[3].split(","))
            for n in names:
                n = n.strip().lower()
                if n and len(n) <= 60:
                    rows.append((n, lat, lon, cc, pop))
    con.executemany("INSERT INTO cities VALUES (?,?,?,?,?)", rows)

    countries = []
    with open(country_file, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) > 4:
                countries.append((p[0], p[4]))
    con.executemany("INSERT OR REPLACE INTO countries VALUES (?,?)", countries)

    con.commit()
    con.close()
    print(f"Done. {len(rows)} city names and {len(countries)} countries saved -> {DB_PATH}")


if __name__ == "__main__":
    main()