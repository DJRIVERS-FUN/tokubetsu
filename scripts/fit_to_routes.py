#!/usr/bin/env python3

"""
Convert Garmin FIT ride files into a routes.json file
for the interactive telemetry route dashboard.

Expected output:
/docs/data/routes.json

Usage:
python3 scripts/fit_to_routes.py rides/

Recommended:
- remove first/last GPS sections for privacy
- avoid publishing precise home coordinates
"""

import json
import math
import sys
from pathlib import Path

SEMICIRCLE_TO_DEG = 180 / (2 ** 31)


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(dlambda / 2) ** 2
    )

    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def trim_route(coords, trim_km=1.5):
    if len(coords) < 50:
        return coords

    def trim_start(points):
        dist = 0
        idx = 0

        while idx < len(points) - 1 and dist < trim_km:
            dist += haversine(
                points[idx][0],
                points[idx][1],
                points[idx + 1][0],
                points[idx + 1][1],
            )
            idx += 1

        return points[idx:]

    trimmed = trim_start(coords)
    trimmed.reverse()
    trimmed = trim_start(trimmed)
    trimmed.reverse()

    return trimmed


def extract_value(record, field_name):
    """Robust extraction across Garmin SDK structures."""

    # attribute access
    value = getattr(record, field_name, None)
    if value is not None:
        return value

    # dictionary-style access
    if isinstance(record, dict):
        value = record.get(field_name)
        if value is not None:
            return value

    # fields list access
    fields = getattr(record, 'fields', None)
    if fields:
        for field in fields:
            name = getattr(field, 'name', None)
            if name == field_name:
                return getattr(field, 'value', None)

    return None


def parse_fit_file(filepath):
    try:
        from garmin_fit_sdk import Decoder, Stream
    except ImportError:
        print(
            "ERROR: garmin-fit-sdk is not installed.\n"
            "Install with:\n"
            "pip install garmin-fit-sdk",
            file=sys.stderr,
        )
        sys.exit(1)

    stream = Stream.from_file(str(filepath))
    decoder = Decoder(stream)

    messages, errors = decoder.read()

    if errors:
        print(f"Warning: FIT decode warnings in {filepath.name}")

    coords = []

    records = messages.get("record_mesgs", [])

    print(f"  Found {len(records)} FIT records")

    for record in records:
        lat = extract_value(record, "position_lat")
        lon = extract_value(record, "position_long")

        if lat is None or lon is None:
            continue

        try:
            lat_deg = float(lat) * SEMICIRCLE_TO_DEG
            lon_deg = float(lon) * SEMICIRCLE_TO_DEG
        except Exception:
            continue

        coords.append([
            round(lat_deg, 6),
            round(lon_deg, 6)
        ])

    return coords


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/fit_to_routes.py rides/")
        sys.exit(1)

    fit_dir = Path(sys.argv[1])

    if not fit_dir.exists():
        print(f"Directory not found: {fit_dir}")
        sys.exit(1)

    fit_files = sorted(fit_dir.glob("*.fit"))

    if not fit_files:
        print("No FIT files found")
        sys.exit(1)

    routes = []

    for fit_file in fit_files:
        print(f"Processing {fit_file.name}...")

        coords = parse_fit_file(fit_file)

        if not coords:
            print("  No GPS coordinates found")
            continue

        coords = trim_route(coords, trim_km=1.5)

        routes.append({
            "ride_id": fit_file.stem,
            "coordinates": coords,
        })

        print(f"  Exported {len(coords)} GPS points")

    output = {
        "routes": routes
    }

    output_dir = Path("docs/data")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "routes.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved route archive to: {output_file}")
    print(f"Total rides exported: {len(routes)}")


if __name__ == "__main__":
    main()
