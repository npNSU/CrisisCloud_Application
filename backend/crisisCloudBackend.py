import os
from copy import deepcopy
import requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

NWS_BASE = "https://api.weather.gov"
NWS_UA = os.getenv("NWS_USER_AGENT", "CrisisCloud/1.0 (demo@example.com)")

DEMO_RESOURCES = [
    {
        "id": "sh_blair",
        "type": "shelter",
        "name": "Blair Middle School Shelter",
        "city": "Norfolk, VA",
        "address": "730 Spotswood Avenue, Norfolk, VA 23517",
        "lat": 36.866306,
        "lon": -76.292577,
        "status": "open",
        "spaceLeft": 120,
        "phone": "(757) 628-2400",
    },
    {
        "id": "sh_granby",
        "type": "shelter",
        "name": "Granby High School Shelter",
        "city": "Norfolk, VA",
        "address": "7101 Granby Street, Norfolk, VA 23505",
        "lat": 36.907194,
        "lon": -76.277139,
        "status": "limited",
        "spaceLeft": 85,
        "phone": "(757) 451-4110",
    },
    {
        "id": "sh_norview_high",
        "type": "shelter",
        "name": "Norview High School Shelter",
        "city": "Norfolk, VA",
        "address": "6501 Chesapeake Blvd, Norfolk, VA 23513",
        "lat": 36.900139,
        "lon": -76.240306,
        "status": "open",
        "spaceLeft": 140,
        "phone": "(757) 852-4500",
    },
    {
        "id": "fb1",
        "type": "food",
        "name": "Peninsula Food Bank",
        "city": "Newport News, VA",
        "address": "1201 29th Street, Newport News, VA 23607",
        "lat": 37.0871,
        "lon": -76.4730,
        "status": "open",
        "foodLeft": 340,
        "phone": "(757) 555-0130",
    },
    {
        "id": "pd1",
        "type": "police",
        "name": "Hampton Police Department",
        "city": "Hampton, VA",
        "address": "40 Lincoln Street, Hampton, VA 23669",
        "lat": 37.0340,
        "lon": -76.3407,
        "status": "available",
        "unitsAvailable": 12,
        "phone": "(757) 727-6111",
    },
    {
        "id": "fd1",
        "type": "fire",
        "name": "Norfolk Fire-Rescue Station",
        "city": "Norfolk, VA",
        "address": "701 Granby Street, Norfolk, VA 23510",
        "lat": 36.8515,
        "lon": -76.2871,
        "status": "available",
        "trucksAvailable": 6,
        "phone": "(757) 664-6510",
    },
    {
        "id": "tw1",
        "type": "towing",
        "name": "Bayview Towing Services",
        "city": "Virginia Beach, VA",
        "address": "3505 Shore Drive, Virginia Beach, VA 23455",
        "lat": 36.8529,
        "lon": -75.9780,
        "status": "available",
        "towTrucksAvailable": 4,
        "phone": "(757) 555-0199",
    },
]
resource_state = {item["id"]: deepcopy(item) for item in DEMO_RESOURCES}


def serialize_resources():
    return [deepcopy(item) for item in resource_state.values()]


RESOURCE_COUNT_FIELDS = {
    "shelter": "spaceLeft",
    "food": "foodLeft",
    "police": "unitsAvailable",
    "fire": "trucksAvailable",
    "towing": "towTrucksAvailable",
}


def merge_resource_update(resource, payload):
    if payload.get("status"):
        resource["status"] = str(payload["status"]).lower()

    if "phone" in payload:
        resource["phone"] = str(payload["phone"]).strip()

    count_field = RESOURCE_COUNT_FIELDS.get(resource["type"])
    if count_field and count_field in payload:
        resource[count_field] = max(0, int(payload[count_field]))

    return resource


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

@app.route("/")
def home():
    # Make sure templates/CrisisCloudDb.html exists
    return render_template("crisisCloud.html")

@app.get("/favicon.ico")
def favicon():
    return "", 204


@app.get("/api/resources")
def get_resources():
    return jsonify({"resources": serialize_resources()})


@app.post("/api/resources/<resource_id>")
def update_resource(resource_id):
    resource = resource_state.get(resource_id)
    if resource is None:
        return jsonify({"error": "Resource not found"}), 404

    payload = request.get_json(silent=True) or {}

    try:
        updated = merge_resource_update(resource, payload)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid update payload"}), 400

    return jsonify({"resource": deepcopy(updated), "resources": serialize_resources()})

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


if __name__ == "__main__":
    app.run(debug=True)


