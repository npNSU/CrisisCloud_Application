import os
import requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

NWS_BASE = "https://api.weather.gov"
NWS_UA = os.getenv("NWS_USER_AGENT", "CrisisCloud/1.0 (demo@example.com)")

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

        # 3) Active alerts for this point
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

        return jsonify({"current": current, "alerts": alerts})

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
