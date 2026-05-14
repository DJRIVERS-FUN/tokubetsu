# TOKUBETSU

Research data-management repository for the drivetrain segment study.

## Purpose

TOKUBETSU supports a longitudinal study of how GRX Di2 shifting behaviour, cassette configuration, cadence, and power interact across fixed Strava segments.

The repository separates:

- ride metadata
- drivetrain and bicycle setup metadata
- segment definitions
- processed/anonymized summaries
- analysis notebooks
- figures
- hidden dashboard files

Raw ride files should normally remain local and should not be committed to GitHub.

## Core workflow

Each ride receives one stable `ride_id`. Every file and metadata row for that ride uses the same ID.

Example:

```text
R2026_0514_A.fit
R2026_0514_A_di2.csv
R2026_0514_A_strava_segments.csv
```

Recommended ride ID format:

```text
RYYYY_MMDD_A
```

Examples:

```text
R2026_0514_A
R2026_0514_B
R2026_0515_A
```

## Repository structure

```text
TOKUBETSU/
├── README.md
├── .gitignore
├── metadata/
│   ├── ride_log.csv
│   ├── setup_registry.csv
│   ├── segment_registry.csv
│   └── file_manifest.csv
├── raw_fit/          # local only; ignored by Git
├── raw_di2/          # local only; ignored by Git
├── raw_strava/       # local only; ignored by Git
├── processed/        # shareable derived data
├── notebooks/        # analysis notebooks/scripts
├── figures/          # exported plots and publication figures
└── docs/
    └── hidden_dashboard.html
```

## After each ride

1. Export the Garmin `.fit` file.
2. Export the Di2Stats shift `.csv` file.
3. Save both using the same `ride_id`.
4. Add one row to `metadata/ride_log.csv`.
5. Add or update rows in `metadata/file_manifest.csv`.
6. Process raw files into segment-level summaries.
7. Save shareable/anonymized outputs in `processed/`.

## Privacy rule

Do not commit raw `.fit`, `.gpx`, `.tcx`, `.zip`, or raw Di2 exports unless there is a deliberate reason. These can reveal exact routes, home location, timestamps, and private ride patterns.

Use GitHub for:

- metadata
- reproducible scripts
- processed summaries
- anonymized outputs
- figures
- dashboard pages

Keep raw files in a local archive or cloud-synced private folder.

## Research framing

Fixed Strava segments are treated as repeated ecological test environments. Cassette configuration and drivetrain setup are treated as human-machine system constraints. Cadence, power, gear choice, and shift-event timing are treated as behavioural regulation outputs.
