import pandas as pd
from pathlib import Path

print('TOKUBETSU Ride Processor')
print('-------------------------')

base = Path('.')
metadata = base / 'metadata' / 'ride_log.csv'

if metadata.exists():
    rides = pd.read_csv(metadata)
    print(f'Loaded {len(rides)} ride metadata entries')
else:
    print('No metadata file found')

print('\nNext development stage:')
print('- FIT parsing')
print('- Di2 shift synchronization')
print('- Segment extraction')
print('- Cadence/power analysis')
print('- Dashboard JSON generation')
