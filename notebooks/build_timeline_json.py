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
df = df.loc[:, ~df.columns.astype(str).str.contains('^Unnamed')]

cols = {str(c).lower().strip(): c for c in df.columns}
cols = {str(c).lower().strip(): c for c in df.columns}

def find_col(*terms):
    for lc, original in cols.items():
        if any(t in lc for t in terms):
            return original
    return None

gear_col = find_col("gear")
power_col = find_col("power")
cadence_col = find_col("cadence")
speed_col = find_col("speed")
grade_col = find_col("grade", "gradient")
time_col = find_col("time")
distance_col = find_col("distance")

if gear_col is None:
    raise SystemExit("Could not identify gear column")

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
        v = row.get(col, default)
        try:
            if pd.isna(v):
                return default
        except Exception:
            pass
        return v

    time_s = float(val(time_col, idx))
    power = float(val(power_col, 0))
    cadence = float(val(cadence_col, 0))
    speed_kph = float(val(speed_col, 0))
    grade = float(val(grade_col, 0))
    distance_m = float(val(distance_col, 0))

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
