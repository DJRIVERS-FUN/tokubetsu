import json
import pandas as pd
from pathlib import Path

base = Path('.')
metadata_dir = base / 'metadata'
processed_dir = base / 'processed'
processed_dir.mkdir(exist_ok=True)

ride_log = pd.read_csv(metadata_dir / 'ride_log.csv')
segments = pd.read_csv(metadata_dir / 'segment_registry.csv')

summary = {
    'project': 'TOKUBETSU',
    'rides_analyzed': int(len(ride_log)),
    'registered_segments': int(len(segments)),
    'registered_setups': int(ride_log['cassette'].nunique()) if 'cassette' in ride_log.columns else 0,
}

if len(ride_log) > 0:
    latest = ride_log.iloc[-1]

    summary['current_ride'] = {
        'ride_id': latest.get('ride_id', ''),
        'bike': latest.get('bike', ''),
        'cassette': latest.get('cassette', ''),
        'chainring': latest.get('chainring', ''),
        'wheelset': latest.get('wheelset', ''),
        'front_tyre': latest.get('tyre_front', ''),
        'rear_tyre': latest.get('tyre_rear', ''),
    }

with open(processed_dir / 'summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print('Dashboard summary written to processed/summary.json')
