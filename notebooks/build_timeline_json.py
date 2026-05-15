
```python
from pathlib import Path
import argparse
import json
import pandas as pd


def normalize_gear(g):
    g = str(g).strip()

    replacements = {
        "79x24": "1x24",
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

    return replacements.get(g, g)


parser = argparse.ArgumentParser(
    description="Convert Di2Stats XLSX timeline export into dashboard JSON"
)

parser.add_argument(
    "xlsx",
    help="Path to Di2Stats timeline XLSX file"
)

parser.add_argument(
    "--out",
    default="docs/data",
    help="Output directory"
)

args = parser.parse_args()

xlsx_path = Path(args.xlsx)
out_dir = Path(args.out)
out_dir.mkdir(parents=True, exist_ok=True)

ride_id = xlsx_path.stem.replace("_di2_timeline", "")
out_path = out_dir / f"{ride_id}_timeline.json"

print(f"Using Di2Stats timeline XLSX: {xlsx_path}")
print(f"Ride ID: {ride_id}")
print(f"Writing timeline JSON to: {out_path}")

# ------------------------------------------------------------------
# Load XLSX
# ------------------------------------------------------------------

try:
    df = pd.read_excel(xlsx_path)
except Exception as e:
    raise SystemExit(f"Failed to read XLSX: {e}")

# ------------------------------------------------------------------
# Column normalization
# ------------------------------------------------------------------

cols = {c.lower().strip(): c for c in df.columns}

# Attempt to detect likely columns
gear_col = None
power_col = None
cadence_col = None
speed_col = None
grade_col = None
time_col = None
distance_col = None

for c in cols:
    if "gear" in c:
        gear_col = cols[c]
    elif "power" in c:
        power_col = cols[c]
    elif "cadence" in c:
        cadence_col = cols[c]
    elif "speed" in c:
        speed_col = cols[c]
    elif "grade" in c or "gradient" in c:
        grade_col = cols[c]
    elif "time" in c:
        time_col = cols[c]
    elif "distance" in c:
        distance_col = cols[c]

if gear_col is None:
    raise SystemExit("Could not identify gear column in XLSX")

# ------------------------------------------------------------------
# Build timeline points
# ------------------------------------------------------------------

points = []
shift_events = 0
prev_gear = None

for idx, row in df.iterrows():
    gear = normalize_gear(row.get(gear_col, ""))

    if not gear:
        continue

    try:
        time_s = float(row.get(time_col, idx))
    except Exception:
        time_s = float(idx)

    power = float(row.get(power_col, 0) or 0)
    cadence = float(row.get(cadence_col, 0) or 0)
    speed_kph = float(row.get(speed_col, 0) or 0)
    grade = float(row.get(grade_col, 0) or 0)
    distance_m = float(row.get(distance_col, 0) or 0)

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

# ------------------------------------------------------------------
# Output structure
# ------------------------------------------------------------------

output = {
    "ride_id": ride_id,
    "source_type": "di2stats_timeline_xlsx",
    "has_real_gear_timeline": True,
    "timeline_points": len(points),
    "shift_event_count": shift_events,
    "gear_states_found": sorted(list(set(p["gear"] for p in points))),
    "points": points
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False)

print(f"Wrote {out_path}")
print(f"Timeline points: {len(points)}")
print(f"Real gear timeline: True")
print(f"Shift events: {shift_events}")
```

Then run future rides like this:

```bash
python3 notebooks/build_timeline_json.py \
  data/raw/R003_XXXX_GR_di2_timeline.xlsx
```

The script will now:

* automatically derive the ride ID
* write correctly named output JSON
* normalize gear names
* detect shift events dynamically
* avoid hard-coded R001 references
* write directly into `docs/data/`
