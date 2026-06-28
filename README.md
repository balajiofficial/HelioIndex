# helio_index (repo)

This is the outer repository for `helio_index`. It is **not** the `helio_index` Python package itself — the package lives in the `helio_index/` subdirectory (an installable, self-contained project with its own `pyproject.toml`, source, and tests).

This outer repo wraps that package with an example implementation and the sample data needed to run it: a small driver script, a synthetic timestamp list, and a flare event catalog. Think of it as a "consumer" repo demonstrating how someone would actually use the `helio_index` package end-to-end, rather than the library code itself.

---

## Directory Structure

```
helio_index/                  (outer repo, this README)
├── test.py
├── timestamps.txt
├── flare_events.csv
├── generate_time_stamps.py
├── .gitignore
└── helio_index/               <- the actual helio_index package (see its own README)
```

## File Descriptions

| File | Description |
|------|-------------|
| `test.py` | An example user implementation of the `helio_index` package. Imports `EventData`, `TimestampSeries`, `ObservationWindowBuilder`, `FullDiskLabeler`, and `ForecastTableBuilder` from the package and walks through loading data, matching timestamps to flare events, building observation windows, and labeling those windows with GOES flare classes. This is sample/demo code, not part of the package itself. |
| `timestamps.txt` | A generated example list of image timestamp filenames, in `YYYYMMDD_HHMMSS.jpg` format, one per minute. This is the sample data `test.py` loads via `TimestampSeries` to demonstrate the package. |
| `flare_events.csv` | A list of flare events for a specific timeline, with columns for event name, date, start/stop/peak times, GOES class, and derived position. This is the sample data `test.py` loads via `EventData` to demonstrate the package. |
| `generate_time_stamps.py` | Standalone script that generates a timestamp filename list (the kind of data found in `timestamps.txt`). Given a start and end `datetime`, it writes one `YYYYMMDD_HHMMSS.jpg` filename per minute to an output file (`files.txt` by default — pass `output_file=` to change the name). |
| `.gitignore` | Ignore rules for this repo: build artifacts (`dist/`, `build/`, `*.egg-info/`), Python cache files (`__pycache__/`, `*.pyc`, `*.pyo`), virtual environments (`.venv/`, `env/`), `.env` files, `.vscode/`, `.DS_Store`, and a `Processing/file_list.txt` path. |

---

## The `helio_index/` package

The `helio_index/` subdirectory is the actual library: an installable Python package (Poetry-based) containing the core classes — `EventData`, `TimestampSeries`, `GoesClass`, `ObservationWindowBuilder`, `FullDiskLabeler`, and `ForecastTableBuilder` — used for matching solar image timestamps to flare events and building observation/prediction windows for solar flare forecasting.

See `helio_index/README.md` for details on the package's classes, API, and usage examples.