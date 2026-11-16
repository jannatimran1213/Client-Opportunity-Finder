"""Search businesses and cities in the local SQLite database."""
import math
import os
import sqlite3

DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data", "osm_places.sqlite")
)

_COUNTRY_ALIASES = {
    "usa": "US", "us": "US", "united states": "US", "america": "US",
    "uk": "GB", "united kingdom": "GB", "gb": "GB", "britain": "GB",
    "uae": "AE", "united arab emirates": "AE",
}


def _distance_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def search_local(lat, lon, radius_m, tags, business_type, limit=500):
    """Returns a list of records, or None if the local database does not exist."""
    if not os.path.exists(DB_PATH):
        return None

    dlat = radius_m / 111320
    dlon = radius_m / (111320 * max(math.cos(math.radians(lat)), 0.01))

    if tags:
        cond = " OR ".join(["kv LIKE ?"] * len(tags))
        params = [f"%|{k}={v}|%" for k, v in tags]
    else:
        cond = "name LIKE ?"
        params = [f"%{business_type}%"]

    sql = (
        "SELECT name, lat, lon, phone, website, email, facebook, instagram, address "
        "FROM places WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ? "
        f"AND ({cond})"
    )
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute(sql, [lat - dlat, lat + dlat, lon - dlon, lon + dlon] + params).fetchall()
    except sqlite3.OperationalError:
        return None          # the places table does not exist yet
    finally:
        con.close()

    found = []
    for name, la, lo, phone, website, email, fb, ig, address in rows:
        d = _distance_m(lat, lon, la, lo)
        if d <= radius_m:
            found.append((d, {
                "business_name": name, "website": website, "email": email, "phone": phone,
                "facebook": fb, "instagram": ig, "latitude": la, "longitude": lo, "address": address,
            }))
    found.sort(key=lambda x: x[0])
    return [rec for _, rec in found[:limit]]


def geocode_local(city, country):
    """Offline city lookup. Returns (lat, lon, display_name, cc) or None."""
    if not os.path.exists(DB_PATH):
        return None
    city_l = (city or "").strip().lower()
    country_l = (country or "").strip().lower()
    if not city_l:
        return None
    con = sqlite3.connect(DB_PATH)
    try:
        cc = _COUNTRY_ALIASES.get(country_l)
        if cc is None and country_l:
            row = con.execute(
                "SELECT cc FROM countries WHERE lower(name)=? OR lower(cc)=?", (country_l, country_l)
            ).fetchone()
            cc = row[0] if row else None
        if cc:
            row = con.execute(
                "SELECT lat, lon, cc FROM cities WHERE name=? AND cc=? ORDER BY pop DESC LIMIT 1", (city_l, cc)
            ).fetchone()
        else:
            row = con.execute(
                "SELECT lat, lon, cc FROM cities WHERE name=? ORDER BY pop DESC LIMIT 1", (city_l,)
            ).fetchone()
    except sqlite3.OperationalError:
        return None          # the cities table does not exist yet
    finally:
        con.close()
    if not row:
        return None
    lat, lon, found_cc = row
    display = ", ".join(x for x in (city.strip().title(), (country or "").strip()) if x)
    return lat, lon, display, found_cc