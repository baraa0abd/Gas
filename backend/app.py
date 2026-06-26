"""SeparatorSizer Pro — Flask API."""

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from separator_engine import recommend_retention_minutes, run_sizing

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"

app = Flask(__name__, static_folder=str(FRONTEND_DIST), static_url_path="")
CORS(app)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "app": "SeparatorSizer Pro"})


@app.post("/api/calculate")
def calculate():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(run_sizing(payload))
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.get("/api/retention-recommendation")
def retention_recommendation():
    phase_mode = request.args.get("phase_mode", "2-phase")
    pressure = float(request.args.get("pressure_psia", 100))
    temperature = float(request.args.get("temperature_f", 60))
    oil_min, water_min, note = recommend_retention_minutes(phase_mode, pressure, temperature)
    return jsonify(
        {
            "oil_minutes": oil_min,
            "water_minutes": water_min,
            "note": note,
        }
    )


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    dist = Path(app.static_folder)
    if path and (dist / path).exists():
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="0.0.0.0", port=port)
