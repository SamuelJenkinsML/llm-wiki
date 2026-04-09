#!/usr/bin/env python3
"""FastAPI webhook receiver for Health Auto Export iOS app.

Receives POST requests with Apple Health data and writes to SQLite database.

Run with: uvicorn health_receiver:app --host 0.0.0.0 --port 9876
"""

import logging
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request

from db import get_db, init_db, log_run

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("health-receiver")

WEBHOOK_TOKEN = os.environ.get("HEALTH_WEBHOOK_TOKEN", "")

# Metrics where samples should be summed for a daily total
CUMULATIVE_METRICS = {
    "step_count", "active_energy", "active_energy_burned", "basal_energy_burned",
    "dietary_energy_consumed", "distance_walking_running", "walking_running_distance",
    "flights_climbed", "apple_exercise_time", "apple_stand_time",
}

# Metrics where samples should be averaged with min/max
AVERAGING_METRICS = {
    "heart_rate", "resting_heart_rate", "heart_rate_variability",
}

app = FastAPI(title="Jarvis Health Receiver")


def verify_token(authorization: str = Header(default="")):
    if not WEBHOOK_TOKEN:
        return  # No token configured, skip auth
    expected = f"Bearer {WEBHOOK_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid token")


def _extract_date(date_str: str) -> str:
    """Extract YYYY-MM-DD from a Health Auto Export date string like '2026-04-08 08:00:00 +0100'."""
    return date_str[:10] if len(date_str) >= 10 else ""


def _process_to_db(conn, data: dict):
    """Write health data to SQLite."""
    t0 = time.monotonic()
    metrics = data.get("metrics", [])
    workouts = data.get("workouts", [])
    rows = 0

    try:
        for metric in metrics:
            name = metric.get("name", "unknown")
            units = metric.get("units", "")
            values = metric.get("data", [])

            for v in values:
                date_str = v.get("date", "")
                day = _extract_date(date_str)
                if not day:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO health_samples (date, metric, timestamp, value, units) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (day, name, date_str, v.get("qty", v.get("value", 0)), units),
                )
                rows += 1

        # Recompute daily summaries for affected (date, metric) pairs
        affected = set()
        for metric in metrics:
            name = metric.get("name", "unknown")
            units = metric.get("units", "")
            for v in metric.get("data", []):
                day = _extract_date(v.get("date", ""))
                if day:
                    affected.add((day, name, units))

        for day, name, units in affected:
            all_vals = conn.execute(
                "SELECT value FROM health_samples WHERE date=? AND metric=? AND value != 0",
                (day, name),
            ).fetchall()
            all_vals_list = [r[0] for r in all_vals]
            sample_count = conn.execute(
                "SELECT COUNT(*) FROM health_samples WHERE date=? AND metric=?",
                (day, name),
            ).fetchone()[0]

            daily_total = None
            average = None
            min_val = None
            max_val = None
            latest = None

            if name in CUMULATIVE_METRICS:
                all_samples = conn.execute(
                    "SELECT value FROM health_samples WHERE date=? AND metric=?",
                    (day, name),
                ).fetchall()
                daily_total = round(sum(r[0] for r in all_samples), 2)
                latest = daily_total

            if name in AVERAGING_METRICS and all_vals_list:
                average = round(sum(all_vals_list) / len(all_vals_list), 1)
                min_val = round(min(all_vals_list), 1)
                max_val = round(max(all_vals_list), 1)
                latest = all_vals_list[-1] if all_vals_list else None

            # For metrics that are neither cumulative nor averaging, store latest
            if daily_total is None and average is None and all_vals_list:
                latest = all_vals_list[-1]

            conn.execute(
                "INSERT OR REPLACE INTO health_daily "
                "(date, metric, units, sample_count, daily_total, average, min_value, max_value, latest_value) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (day, name, units, sample_count, daily_total, average, min_val, max_val, latest),
            )

        # Workouts
        for workout in workouts:
            workout_type = workout.get("name", workout.get("workoutActivityType", "unknown"))
            workout_type = workout_type.replace("HKWorkoutActivityType", "").lower()
            start = workout.get("start", workout.get("startDate", ""))
            workout_day = _extract_date(start) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            duration_min = workout.get("duration", 0)
            if isinstance(duration_min, str):
                try:
                    duration_min = float(duration_min)
                except ValueError:
                    duration_min = 0

            conn.execute(
                "INSERT OR IGNORE INTO workouts "
                "(date, type, start_time, duration_minutes, distance_km, energy_kcal, avg_heart_rate, max_heart_rate) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    workout_day, workout_type, start, round(duration_min, 1),
                    round(workout.get("totalDistance", workout.get("distance", {}).get("qty", 0)), 2),
                    round(workout.get("totalEnergyBurned", workout.get("activeEnergy", {}).get("qty", 0)), 1),
                    workout.get("avgHeartRate", workout.get("heartRateAverage", 0)),
                    workout.get("maxHeartRate", workout.get("heartRateMax", 0)),
                ),
            )

        conn.commit()
        duration = time.monotonic() - t0
        log_run(conn, "health-receiver", "success", rows_affected=rows, duration_seconds=round(duration, 2))

    except Exception as e:
        duration = time.monotonic() - t0
        log_run(conn, "health-receiver", "error", error_message=str(e), duration_seconds=round(duration, 2))
        raise


@app.get("/health/status")
async def status():
    return {"status": "ok"}


@app.post("/health")
async def receive_health_data(request: Request, authorization: str = Header(default="")):
    verify_token(authorization)

    body = await request.json()
    data = body.get("data", body)
    metrics = data.get("metrics", [])
    workouts = data.get("workouts", [])

    total_samples = sum(len(m.get("data", [])) for m in metrics)
    log.info(f"Received {len(metrics)} metrics ({total_samples} samples) and {len(workouts)} workouts")

    db_conn = get_db()
    init_db(db_conn)
    _process_to_db(db_conn, data)
    db_conn.close()

    return {
        "status": "ok",
        "metrics_received": len(metrics),
        "workouts_received": len(workouts),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9876, timeout_keep_alive=300)
