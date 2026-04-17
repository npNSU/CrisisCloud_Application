import os
import bcrypt
import secrets
from copy import deepcopy
import psycopg
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from psycopg.rows import dict_row

# LOOKUP: BACKEND-SETUP
# This section loads environment variables, creates the Flask app, and defines the
# shared constants used across the backend. The NWS values are kept here so the
# weather endpoints can reuse one base URL and one configurable User-Agent.
load_dotenv()

STATIC_DIRECTORY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "newIcons",
)
app = Flask(__name__, static_folder=STATIC_DIRECTORY, static_url_path="/static/icons")
DATABASE_URL = os.getenv("DATABASE_URL")

NWS_BASE = "https://api.weather.gov"
NWS_UA = os.getenv("NWS_USER_AGENT", "CrisisCloud/1.0 (demo@example.com)")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required in the .env file.")

# LOOKUP: BACKEND-SUPABASE-CONNECTION
# This app uses the Supabase-hosted Postgres database referenced by DATABASE_URL.
# The Flask app serves frontend templates and local icon assets while reading and
# writing shared crisis data through that one hosted connection string.

# LOOKUP: BACKEND-RESOURCE-DATA
# Resource records now live in the hosted Postgres database configured by
# DATABASE_URL. Keeping the source of truth in one place lets every browser and
# every Flask instance read the same shared data instead of relying on local files.

# LOOKUP: BACKEND-RESOURCE-SERIALIZE
# The frontend should never work directly with raw database rows, so these helpers
# normalize Postgres records into the same JSON shape the frontend already expects.
def get_db_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def row_to_resource(row):
    resource = dict(row)
    return {key: value for key, value in resource.items() if value is not None}


def fetch_all_resources():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, type, name, city, address, lat, lon, status, phone,
                    "spaceLeft", "foodLeft", "unitsAvailable", "trucksAvailable",
                    "bedsAvailable", "towTrucksAvailable", updated_at
                FROM public.resources
                ORDER BY city, type, name
                """
            )
            rows = cur.fetchall()
    return [row_to_resource(row) for row in rows]


def fetch_all_reports():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, type, city, address, lat, lon,
                    description, reporter_name, submitted_at
                FROM public.reports
                ORDER BY submitted_at DESC
                LIMIT 50
                """
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]

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
# Supabase provides the hosted Postgres database. This startup check ensures the
# expected tables exist so the app fails early with a clear error if the schema is
# missing or the connection string is invalid.
def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.resources (
                    id text PRIMARY KEY,
                    type text NOT NULL,
                    name text NOT NULL,
                    city text NOT NULL,
                    address text,
                    lat double precision NOT NULL,
                    lon double precision NOT NULL,
                    status text NOT NULL,
                    phone text,
                    "spaceLeft" integer,
                    "foodLeft" integer,
                    "unitsAvailable" integer,
                    "trucksAvailable" integer,
                    "bedsAvailable" integer,
                    "towTrucksAvailable" integer,
                    updated_at timestamp with time zone DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.reports (
                    id serial PRIMARY KEY,
                    type text NOT NULL,
                    city text NOT NULL,
                    address text,
                    lat double precision,
                    lon double precision,
                    description text NOT NULL,
                    reporter_name text,
                    submitted_at timestamp with time zone DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.users (
                    id serial PRIMARY KEY,
                    username text UNIQUE NOT NULL,
                    password_hash text NOT NULL,
                    resource_id text REFERENCES public.resources(id),
                    created_at timestamp with time zone DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.sessions (
                    token text PRIMARY KEY,
                    user_id integer REFERENCES public.users(id),
                    resource_id text,
                    created_at timestamp with time zone DEFAULT now(),
                    expires_at timestamp with time zone DEFAULT now() + interval '24 hours'
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
            "Accept": "application/geo+json"
        },
        timeout=20
    )

    try:
        data = r.json()
    except Exception:
        data = {"raw_text": r.text}

    if not r.ok:
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

@app.route("/simulation")
def simulation():
    return render_template("simulation.html")

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
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id, type, name, city, address, lat, lon, status, phone,
                        "spaceLeft", "foodLeft", "unitsAvailable", "trucksAvailable",
                        "bedsAvailable", "towTrucksAvailable", updated_at
                    FROM public.resources
                    WHERE id = %s
                    """,
                    (resource_id,),
                )
                row = cur.fetchone()

                if row is None:
                    return jsonify({"error": "Resource not found"}), 404

                resource = row_to_resource(row)
                updated = merge_resource_update(resource, payload)
                count_field = RESOURCE_COUNT_FIELDS.get(resource["type"])

                cur.execute(
                    f"""
                    UPDATE public.resources
                    SET status = %s, phone = %s, "{count_field}" = %s, updated_at = now()
                    WHERE id = %s
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
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except (KeyError, ValueError):
        return jsonify({
            "error": "Missing or invalid lat/lon. Example: /api/weather/live?lat=36.9&lon=-76.3"
        }), 400

    try:
        points = nws_get(f"{NWS_BASE}/points/{lat},{lon}")

        if "properties" not in points:
            print("Unexpected /points response:", points)
            return jsonify({
                "error": "Unexpected response from NWS /points endpoint",
                "details": points
            }), 502

        p = points["properties"]

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
                    temp_f = (temp_c * 9 / 5 + 32) if temp_c is not None else None

                    current = {
                        "station_id": station_id,
                        "observed_at": op.get("timestamp"),
                        "temperature_f": temp_f,
                        "text_description": op.get("textDescription"),
                    }

        forecast = extract_weekly_forecast(p)

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
        print("NWS HTTPError:", str(e))
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



# LOOKUP: BACKEND-REPORTS-API
# These endpoints power the live field reporting workflow. The GET route returns
# the latest submitted reports for the dashboard feed, and the POST route saves
# a new report so it can appear on the map and in the live alert list.
@app.get("/api/reports")
def get_reports():
    try:
        reports = fetch_all_reports()
        for r in reports:
            if r.get("submitted_at"):
                r["submitted_at"] = r["submitted_at"].isoformat()
        return jsonify({"reports": reports})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/reports")
def create_report():
    payload = request.get_json(silent=True) or {}
    report_type = str(payload.get("type", "")).strip()
    city = str(payload.get("city", "")).strip()
    description = str(payload.get("description", "")).strip()
    if not report_type or not city or not description:
        return jsonify({"error": "type, city, and description are required"}), 400
    address = str(payload.get("address", "")).strip() or None
    lat = payload.get("lat")
    lon = payload.get("lon")
    reporter_name = str(payload.get("reporter_name", "")).strip() or None
    try:
        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None
    except (TypeError, ValueError):
        lat = None
        lon = None
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.reports
                        (type, city, address, lat, lon, description, reporter_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, submitted_at
                    """,
                    (report_type, city, address, lat, lon, description, reporter_name),
                )
                row = cur.fetchone()
            conn.commit()
        return jsonify({"success": True, "id": row["id"], "submitted_at": row["submitted_at"].isoformat(), "reports": fetch_all_reports()}), 201
    except Exception as e:
        print("Report insert error:", str(e))
        return jsonify({"error": "Failed to save report"}), 500

# LOOKUP: BACKEND-AUTH
# These endpoints handle real authentication. Login checks the username and
# password against bcrypt hashes in Supabase, creates a session token, and
# returns it to the frontend. Logout deletes the token. Me verifies a token.
@app.post("/api/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, password_hash, resource_id FROM public.users WHERE username = %s",
                    (username,)
                )
                user = cur.fetchone()
                if not user:
                    return jsonify({"error": "Invalid username or password"}), 401
                if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                    return jsonify({"error": "Invalid username or password"}), 401
                token = secrets.token_hex(32)
                cur.execute(
                    """
                    INSERT INTO public.sessions (token, user_id, resource_id)
                    VALUES (%s, %s, %s)
                    """,
                    (token, user["id"], user["resource_id"])
                )
            conn.commit()
        return jsonify({"token": token, "resource_id": user["resource_id"]})
    except Exception as e:
        print("Login error:", str(e))
        return jsonify({"error": "Login failed"}), 500


@app.post("/api/logout")
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        return jsonify({"ok": True})
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.sessions WHERE token = %s", (token,))
            conn.commit()
    except Exception:
        pass
    return jsonify({"ok": True})


@app.get("/api/me")
def me():
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        return jsonify({"error": "No token"}), 401
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.resource_id, u.username
                    FROM public.sessions s
                    JOIN public.users u ON u.id = s.user_id
                    WHERE s.token = %s AND s.expires_at > now()
                    """,
                    (token,)
                )
                row = cur.fetchone()
        if not row:
            return jsonify({"error": "Invalid or expired token"}), 401
        return jsonify({"resource_id": row["resource_id"], "username": row["username"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/register")
def register():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    resource_id = str(payload.get("resource_id", "")).strip()
    if not username or not password or not resource_id:
        return jsonify({"error": "username, password, and resource_id are required"}), 400
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.users (username, password_hash, resource_id)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (username, password_hash, resource_id)
                )
                user_id = cur.fetchone()["id"]
            conn.commit()
        return jsonify({"ok": True, "id": user_id}), 201
    except Exception as e:
        if "unique" in str(e).lower():
            return jsonify({"error": "Username already taken"}), 409
        return jsonify({"error": str(e)}), 500

# LOOKUP: BACKEND-APP-START
# Running this file directly starts the Flask development server. This is the entry
# point teammates use from the terminal during local development and demo prep.
init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
