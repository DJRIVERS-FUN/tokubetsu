from pathlib import Path
import argparse
import json
import pandas as pd


def normalize_gear(g):
    s = str(g).strip()

    if not s or s.lower() == "nan":
        return ""

    # Di2Stats sometimes stores metadata after commas, e.g. "1x15,1,10"
    # or malformed states such as "79x24,1,6".
    if "," in s:
        s = s.split(",")[0].strip()

    replacements = {
        "79x24": "1x24",
        "74x24": "1x24",
        "1x11": "1x10",
        "1x13": "1x12",
        "1x15": "1x14",
        "1x17": "1x16",
        "1x19": "1x18",
        "1x22": "1x21",
        "1x25": "1x24",
        "1x32": "1x33",
        "1x36": "1x39",
        "1x42": "1x45",
        "1x50": "1x51",
    }

    return replacements.get(s, s)


parser = argparse.ArgumentParser()
parser.add_argument("xlsx")
parser.add_argument("--out", default="docs/data")
args = parser.parse_args()

xlsx_path = Path(args.xlsx)
ride_id = xlsx_path.stem.replace("_di2_timeline", "")
out_dir = Path(args.out)
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / f"{ride_id}_timeline.json"

# Robust Di2Stats XLSX loader
df_raw = pd.read_excel(xlsx_path, header=None)

header_row = 0
for i in range(min(10, len(df_raw))):
    row = [str(v).lower() for v in df_raw.iloc[i].tolist()]
    joined = " ".join(row)
    if "gear" in joined and ("spd" in joined or "speed" in joined):
        header_row = i
        break

df = pd.read_excel(xlsx_path, header=header_row)

# remove unnamed columns
df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

cols = {str(c).lower().strip(): c for c in df.columns}


def find_col(*terms):
    for lc, original in cols.items():
        if any(t in lc for t in terms):
            return original
    return None


gear_col = find_col("gear")
power_col = find_col("power", "pow")
cadence_col = find_col("cadence", "cad")
speed_col = find_col("speed", "spd")
grade_col = find_col("grade", "gradient")
# Di2Stats uses TS for Unix timestamp seconds.
time_col = find_col("time", "timestamp", "ts")
distance_col = find_col("distance", "dist")

if gear_col is None:
    raise SystemExit("Could not identify gear column")


def safe_float(v, default=0.0):
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return default


# Establish a real elapsed-time baseline. If the source column is TS, values are
# Unix timestamps; subtract the first valid timestamp so JSON stores elapsed s.
if time_col is not None:
    time_values = [safe_float(v, None) for v in df[time_col].tolist()]
    time_values = [v for v in time_values if v is not None]
    first_time = time_values[0] if time_values else 0.0
else:
    first_time = 0.0

# Di2Stats SPD is metres/second. Convert to km/h for dashboard display.
speed_name = str(speed_col).lower() if speed_col is not None else ""
speed_factor = 3.6 if speed_name == "spd" else 1.0

points = []
shift_events = 0
prev_gear = None

for idx, row in df.iterrows():
    gear = normalize_gear(row.get(gear_col, ""))
    if not gear or gear.lower() == "nan":
        continue

    def val(col, default=0):
        if col is None:
            return default
        return row.get(col, default)

    if time_col is not None:
        time_s = safe_float(val(time_col, first_time), first_time) - first_time
    else:
        time_s = float(idx)

    power = safe_float(val(power_col, 0))
    cadence = safe_float(val(cadence_col, 0))
    speed_kph = safe_float(val(speed_col, 0)) * speed_factor
    grade = safe_float(val(grade_col, 0))
    distance_m = safe_float(val(distance_col, 0))

    shift_event = prev_gear is not None and gear != prev_gear
    if shift_event:
        shift_events += 1

    points.append({
        "time_s": round(time_s, 2),
        "gear": gear,
        "power": round(power, 1),
        "cadence": round(cadence, 1),
        "speed_kph": round(speed_kph, 2),
        "grade": round(grade, 4),
        "distance_m": round(distance_m, 1),
        "shift_event": shift_event
    })
    prev_gear = gear

output = {
    "ride_id": ride_id,
    "source_type": "di2stats_timeline_xlsx",
    "has_real_gear_timeline": True,
    "timeline_points": len(points),
    "shift_event_count": shift_events,
    "gear_states_found": sorted(set(p["gear"] for p in points)),
    "points": points
}

out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

print(f"Using Di2Stats timeline XLSX: {xlsx_path}")
print(f"Wrote {out_path}")
print(f"Timeline points: {len(points)}")
print(f"Shift events: {shift_events}")