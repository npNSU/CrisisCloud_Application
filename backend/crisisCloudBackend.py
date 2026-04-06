import os
import sqlite3
from copy import deepcopy
import requests
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv

# LOOKUP: BACKEND-SETUP
# This section loads environment variables, creates the Flask app, and defines the
# shared constants used across the backend. The NWS values are kept here so the
# weather endpoints can reuse one base URL and one configurable User-Agent.
load_dotenv()

app = Flask(__name__)
ICON_DIRECTORY = os.path.join(app.root_path, "templates", "CrisisCloud_Application", "newIcons")
DATABASE_PATH = os.path.join(app.root_path, "crisiscloud.db")

NWS_BASE = "https://api.weather.gov"
NWS_UA = os.getenv("NWS_USER_AGENT", "CrisisCloud/1.0 (demo@example.com)")

# LOOKUP: BACKEND-RESOURCE-DATA
# Resource records now live in the SQLite database file at DATABASE_PATH. Keeping the
# source of truth in one place makes multi-user demos easier to manage because Flask,
# the org portal, and every browser session all read the same saved resource rows.

# LOOKUP: BACKEND-RESOURCE-SERIALIZE
# The frontend should never work directly with raw SQLite rows, so these helpers
# normalize database records into the same JSON shape the frontend already expects.
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_resource(row):
    resource = dict(row)
    return {key: value for key, value in resource.items() if value is not None}


def fetch_all_resources():
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id, type, name, city, address, lat, lon, status, phone,
                spaceLeft, foodLeft, unitsAvailable, trucksAvailable,
                bedsAvailable, towTrucksAvailable, updated_at
            FROM resources
            ORDER BY rowid
            """
        ).fetchall()
    return [row_to_resource(row) for row in rows]


# LOOKUP: BACKEND-RESOURCE-METADATA
# Different resource types track different count fields. This lookup table lets the
# update logic stay generic instead of hard-coding a separate branch for every type.
RESOURCE_COUNT_FIELDS = {
    "shelter": "spaceLeft",
    "food": "foodLeft",
    "police": "unitsAvailable",
    "fire": "trucksAvailable",
    "hospital": "bedsAvailable",
    "towing": "towTrucksAvailable",
}


# LOOKUP: BACKEND-DATABASE-SETUP
# SQLite gives the demo a lightweight persistent backend without changing how the
# frontend talks to Flask. The app auto-creates the database file and schema, while
# the saved rows inside crisiscloud.db remain the single source of truth.
def init_db():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resources (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                address TEXT,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                status TEXT NOT NULL,
                phone TEXT,
                spaceLeft INTEGER,
                foodLeft INTEGER,
                unitsAvailable INTEGER,
                trucksAvailable INTEGER,
                bedsAvailable INTEGER,
                towTrucksAvailable INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.commit()


# LOOKUP: BACKEND-RESOURCE-UPDATES
# This function applies organization portal edits to one resource record. It updates
# shared fields like status and phone, then updates the type-specific capacity field
# based on the metadata map above.
def merge_resource_update(resource, payload):
    if payload.get("status"):
        resource["status"] = str(payload["status"]).lower()

    if "phone" in payload:
        resource["phone"] = str(payload["phone"]).strip()

    count_field = RESOURCE_COUNT_FIELDS.get(resource["type"])
    if count_field and count_field in payload:
        resource[count_field] = max(0, int(payload[count_field]))

    return resource


# LOOKUP: BACKEND-WEATHER-FORECAST
# The NWS /points endpoint provides a forecast URL for the selected location. This
# helper fetches that weekly forecast data and normalizes the first seven periods
# so the frontend can render forecast cards without understanding the raw NWS schema.
def extract_weekly_forecast(points_properties):
    forecast_url = points_properties.get("forecast")
    if not forecast_url:
        return []

    forecast_data = nws_get(forecast_url)
    periods = (forecast_data.get("properties") or {}).get("periods", [])

    weekly_periods = []
    for period in periods[:7]:
        weekly_periods.append({
            "name": period.get("name"),
            "temperature": period.get("temperature"),
            "temperature_unit": period.get("temperatureUnit"),
            "wind_speed": period.get("windSpeed"),
            "wind_direction": period.get("windDirection"),
            "short_forecast": period.get("shortForecast"),
            "detailed_forecast": period.get("detailedForecast"),
            "is_daytime": period.get("isDaytime"),
        })

    return weekly_periods


# LOOKUP: BACKEND-NWS-REQUEST
# All National Weather Service requests go through this helper. Centralizing the
# HTTP call keeps headers, timeout rules, and error handling consistent across
# current weather, forecast, and alert requests.
def nws_get(url: str):
    r = requests.get(
        url,
        headers={
            "User-Agent": NWS_UA,
            "Accept": "application/geo+json"  # commonly supported by NWS endpoints
        },
        timeout=20
    )

    # If NWS returns an error, try to capture JSON detail for debugging
    try:
        data = r.json()
    except Exception:
        data = {"raw_text": r.text}

    if not r.ok:
        # Return structured error so your frontend can show "unavailable"
        raise requests.HTTPError(
            f"NWS HTTP {r.status_code} for {url}",
            response=r
        )

    return data


# LOOKUP: BACKEND-PAGE-ROUTES
# These routes render the main HTML page and handle the empty favicon request that
# browsers make automatically.
@app.route("/")
def home():
    return render_template("crisisCloud.html")


@app.get("/assets/icons/<path:filename>")
def icon_assets(filename):
    return send_from_directory(ICON_DIRECTORY, filename)


@app.get("/favicon.ico")
def favicon():
    return "", 204


# LOOKUP: BACKEND-RESOURCE-API
# These endpoints power the live resource map and sidebar directories. The GET route
# sends the current shared resource list to the frontend, and the POST route applies
# org portal edits to one selected record.
@app.get("/api/resources")
def get_resources():
    return jsonify({"resources": fetch_all_resources()})


@app.post("/api/resources/<resource_id>")
def update_resource(resource_id):
    payload = request.get_json(silent=True) or {}

    try:
        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id, type, name, city, address, lat, lon, status, phone,
                    spaceLeft, foodLeft, unitsAvailable, trucksAvailable,
                    bedsAvailable, towTrucksAvailable, updated_at
                FROM resources
                WHERE id = ?
                """,
                (resource_id,),
            ).fetchone()

            if row is None:
                return jsonify({"error": "Resource not found"}), 404

            resource = row_to_resource(row)
            updated = merge_resource_update(resource, payload)
            count_field = RESOURCE_COUNT_FIELDS.get(resource["type"])

            conn.execute(
                f"""
                UPDATE resources
                SET status = ?, phone = ?, {count_field} = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    updated["status"],
                    updated.get("phone"),
                    updated.get(count_field),
                    resource_id,
                ),
            )
            conn.commit()
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid update payload"}), 400

    return jsonify({"resource": deepcopy(updated), "resources": fetch_all_resources()})


# LOOKUP: BACKEND-WEATHER-API
# This endpoint is called whenever the frontend wants live weather for the current
# map center. It validates latitude/longitude, resolves NWS point metadata, loads
# the latest station observation, weekly forecast, and active alerts, then returns
# a single JSON payload that the dashboard can render.
@app.get("/api/weather/live")
def weather_live():
    # Validate query params
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except (KeyError, ValueError):
        return jsonify({
            "error": "Missing or invalid lat/lon. Example: /api/weather/live?lat=36.9&lon=-76.3"
        }), 400

    try:
        # 1) Resolve /points -> get station + forecast URLs
        points = nws_get(f"{NWS_BASE}/points/{lat},{lon}")

        if "properties" not in points:
            # Print the unexpected payload for debugging
            print("Unexpected /points response:", points)
            return jsonify({
                "error": "Unexpected response from NWS /points endpoint",
                "details": points
            }), 502

        p = points["properties"]

        # 2) Current observation (stations -> latest)
        current = None
        stations_url = p.get("observationStations")

        if stations_url:
            stations = nws_get(stations_url)
            features = stations.get("features", [])

            if features:
                station_id = features[0].get("properties", {}).get("stationIdentifier")
                if station_id:
                    obs = nws_get(f"{NWS_BASE}/stations/{station_id}/observations/latest")
                    op = obs.get("properties", {})

                    temp_c = (op.get("temperature") or {}).get("value")
                    temp_f = (temp_c * 9/5 + 32) if temp_c is not None else None

                    current = {
                        "station_id": station_id,
                        "observed_at": op.get("timestamp"),
                        "temperature_f": temp_f,
                        "text_description": op.get("textDescription"),
                    }

        # 3) Weekly forecast for the Hampton Roads area / current map center
        forecast = extract_weekly_forecast(p)

        # 4) Active alerts for this point
        alerts_data = nws_get(f"{NWS_BASE}/alerts/active?point={lat},{lon}")
        alert_features = alerts_data.get("features", [])

        alerts = []
        for a in alert_features:
            ap = a.get("properties", {}) or {}
            alerts.append({
                "id": a.get("id"),
                "event": ap.get("event"),
                "headline": ap.get("headline"),
                "severity": ap.get("severity"),
                "expires": ap.get("expires"),
            })

        return jsonify({"current": current, "forecast": forecast, "alerts": alerts})

    except requests.HTTPError as e:
        # Print server-side so you can see it in your terminal
        print("NWS HTTPError:", str(e))
        # Also try to include NWS response body if present
        body = None
        try:
            body = e.response.json() if e.response is not None else None
        except Exception:
            body = e.response.text if e.response is not None else None

        return jsonify({
            "error": "NWS API request failed",
            "details": str(e),
            "nws_body": body
        }), 502

    except requests.RequestException as e:
        print("Network error:", str(e))
        return jsonify({"error": "Network error contacting NWS", "details": str(e)}), 502

    except Exception as e:
        print("Server error:", str(e))
        return jsonify({"error": "Server error", "details": str(e)}), 500


# LOOKUP: BACKEND-APP-START
# Running this file directly starts the Flask development server. This is the entry
# point teammates use from the terminal during local development and demo prep.
init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
