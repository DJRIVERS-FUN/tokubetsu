from pathlib import Path
import json
import csv
import math
import statistics as stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT = ROOT / "processed"
OUT.mkdir(exist_ok=True)

rides = json.loads((DATA / "ride_index.json").read_text())
segments = json.loads((DATA / "segment_registry.json").read_text())
routes = json.loads((DATA / "routes.json").read_text()).get("routes", [])

route_by_ride = {r["ride_id"]: r["coordinates"] for r in routes}

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

def cumulative_distances(coords):
    dists = [0.0]
    for i in range(1, len(coords)):
        lat1, lon1 = coords[i-1]
        lat2, lon2 = coords[i]
        dists.append(dists[-1] + haversine_m(lat1, lon1, lat2, lon2))
    return dists

def nearest_index(coords, lat, lon):
    best_i = None
    best_d = float("inf")
    for i, (clat, clon) in enumerate(coords):
        d = haversine_m(clat, clon, lat, lon)
        if d < best_d:
            best_i = i
            best_d = d
    return best_i, best_d

rows = []

for ride in rides:
    ride_id = ride["ride_id"]
    coords = route_by_ride.get(ride_id)

    if not coords:
        print(f"Skipping {ride_id}: no route coordinates")
        continue

    dists = cumulative_distances(coords)

    timeline_path = DATA / ride["timeline"].replace("data/", "")
    timeline = json.loads(timeline_path.read_text())
    points = timeline.get("points", [])

    for seg in segments:
        start_i, start_error_m = nearest_index(coords, seg["start_lat"], seg["start_lng"])
        end_i, end_error_m = nearest_index(coords, seg["end_lat"], seg["end_lng"])

        if start_i is None or end_i is None:
            continue

        if end_i < start_i:
            start_i, end_i = end_i, start_i

        start_m = dists[start_i]
        end_m = dists[end_i]

        seg_points = [
            p for p in points
            if start_m <= float(p.get("distance_m", 0) or 0) <= end_m
        ]

        if not seg_points:
            print(f"No telemetry points for {ride_id} / {seg['name']}")
            continue

        powers = [float(p.get("power", 0) or 0) for p in seg_points]
        cadences = [float(p.get("cadence", 0) or 0) for p in seg_points]
        speeds = [float(p.get("speed_kph", 0) or 0) for p in seg_points]
        grades = [float(p.get("grade", 0) or 0) for p in seg_points]
        shifts = sum(1 for p in seg_points if p.get("shift_event"))

        gears = [p.get("gear") for p in seg_points if p.get("gear")]
        dominant_gear = max(set(gears), key=gears.count) if gears else ""

        elapsed_s = (
            max(float(p.get("time_s", 0) or 0) for p in seg_points)
            - min(float(p.get("time_s", 0) or 0) for p in seg_points)
        )

        distance_km = max((end_m - start_m) / 1000, 0.001)

        rows.append({
            "ride_id": ride_id,
            "segment_id": seg["segment_id"],
            "segment_name": seg["name"],
            "segment_url": seg.get("url", ""),
            "start_m": round(start_m, 1),
            "end_m": round(end_m, 1),
            "distance_km_registered": seg.get("distance_km"),
            "distance_km_matched": round(distance_km, 3),
            "start_match_error_m": round(start_error_m, 1),
            "end_match_error_m": round(end_error_m, 1),
            "elapsed_s": round(elapsed_s, 1),
            "avg_power": round(stats.mean(powers), 1),
            "avg_cadence": round(stats.mean(cadences), 1),
            "cadence_sd": round(stats.stdev(cadences), 1) if len(cadences) > 1 else 0,
            "avg_speed_kph": round(stats.mean(speeds), 1),
            "avg_grade": round(stats.mean(grades), 4),
            "shift_count": shifts,
            "shift_density_per_km": round(shifts / distance_km, 2),
            "dominant_gear": dominant_gear
        })

if not rows:
    raise SystemExit("No segment rows were generated.")

with open(OUT / "segment_stats.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

(DATA / "segment_stats.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

print(f"Wrote {OUT / 'segment_stats.csv'}")
print(f"Wrote {DATA / 'segment_stats.json'}")
print(f"Rows: {len(rows)}")
