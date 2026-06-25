# helio_index

A Python library for matching solar image timestamps to flare events and building observation/prediction windows for solar flare forecasting.

---

## Directory Structure

```
helio_index/
├── events.csv
├── files.txt
├── generate_time_stamps.py
├── test.py
├── .gitignore
└── helio_index/
    ├── pyproject.toml
    ├── README.md
    └── src/
        └── helio_index/
            ├── __init__.py
            ├── __main__.py
            └── utils.py
```

### File Descriptions

| File | Description |
|------|-------------|
| `events.csv` | Solar flare event data with columns for event name, date, start/stop/peak times, GOES class, and derived position |
| `files.txt` | A list of JPG image filenames in `YYYYMMDD_HHMMSS.jpg` format, one per minute, representing available solar image timestamps |
| `generate_time_stamps.py` | Script that generates the `files.txt` file by producing one filename per minute between a given start and end datetime |
| `test.py` | Usage examples demonstrating how to call each function in the library |
| `.gitignore` | Specifies files and directories excluded from version control (build artifacts, pycache, `.env`, `.DS_Store`, etc.) |
| `helio_index/pyproject.toml` | Project metadata and build configuration (name, version, author, Python version requirement, Poetry build system) |
| `helio_index/README.md` | Placeholder README inside the package directory |
| `helio_index/src/helio_index/__init__.py` | Package initializer that exports the public API classes from `utils.py` |
| `helio_index/src/helio_index/__main__.py` | Entry point for running the package as a module (currently empty) |
| `helio_index/src/helio_index/utils.py` | **All core library functions live here** (see note below) |

> **Note: Currently, all functions are implemented in `utils.py`.**

---

## Classes (in `utils.py`)

### `EventData(csv_path)`
Wraps a CSV file of solar flare events, loading it into an internal DataFrame on construction. Provides `lookup_event(date_part, time_part)` to match a date/time pair to an event name, and `goes_class_for(ename)` to look up an event's GOES class.

### `TimestampSeries(path)`
Wraps a text file of image filenames, parsing both the raw filenames and their `datetime` values on construction. Provides `closest(target)` to find the nearest available timestamp, `in_range(start, end)` to filter timestamps within a window, and `match_to_events(events)` to match each filename to a solar flare event by comparing date and start time, returning a dictionary mapping each filename to an event name (`EName`) or `"FQ"` (quiet sun) if no event matches.

### `GoesClass`
A stateless helper class centralizing GOES flare-class logic: `rank(cls)` for ordinal comparison, `max_class(classes)` for the highest class in a list, `to_flux(goes)` for converting a class string to flux in W/m², and `parse_threshold(bl_value)` for parsing binary-label thresholds.

### `ObservationWindowBuilder(timestamps)`
Constructed with a `TimestampSeries`. Its `build(start_time, hours, cadence, sliding_window, end_time)` method generates a list of sliding observation windows between two timestamps, where each window spans a given number of hours and samples timestamps at a specified cadence (in minutes).

### `FullDiskLabeler(events)`
Constructed with an `EventData` instance. Its `label(windows, event_match, evals)` method takes a list of observation windows and the event match dictionary, then returns a DataFrame labeling each window with the highest GOES flare class (`A`, `B`, `C`, `M`, `X`, or `FQ`) observed within it, plus optional flux and binary-label columns depending on `evals`.

### `ForecastTableBuilder(timestamps, events)`
Constructed with a `TimestampSeries` and an `EventData` instance. Its `build(obs_minutes, pred_minutes, cadence_minutes, labeled, separation_minutes, limit)` method builds, for each timestamp, a lookback observation window and a lookahead prediction window, then labels each row with the maximum GOES class found in the prediction window — producing a DataFrame ready for machine learning.

---

## Examples (`test.py`)

`test.py` demonstrates the full pipeline from data loading to forecast table construction.

### 1. Loading data
```python
events = EventData('events.csv')
timestamps = TimestampSeries('files.txt')
```
Both data sources are loaded into their own objects up front, rather than into module-level globals, so each object owns its own state.

### 2. `match_to_events`
```python
labeled = timestamps.match_to_events(events)
```
Reads the loaded timestamps and event list and returns a dictionary. Each image filename maps to its corresponding `EName` if the date and start time match an event in `events.csv`, or `"FQ"` if no event matches.

### 3. `ObservationWindowBuilder`
```python
# window_builder = ObservationWindowBuilder(timestamps)
# ow = window_builder.build("20251001_001400", 4, 15, 60, "20251002_001400")
```
Generates 4-hour observation windows starting at `20251001_001400`, sampled every 15 minutes, sliding forward by 60 minutes at a time until `20251002_001400`. *(Commented out in test.py.)*

### 4. `FullDiskLabeler`
```python
# labeler = FullDiskLabeler(events)
# wl = labeler.label(ow, labeled)
```
Takes the windows from `ObservationWindowBuilder` and the `labeled` dictionary to produce a DataFrame where each window is tagged with its peak flare class. *(Commented out in test.py.)*

### 5. `ForecastTableBuilder`
```python
# forecast_builder = ForecastTableBuilder(timestamps, events)
# bt = forecast_builder.build(240, 480, 60, labeled, limit=150)
```
For each of the first 150 timestamps: looks back 240 minutes (observation window sampled hourly) and forward 480 minutes (prediction window), then labels the row with the maximum GOES class in the prediction window. Returns a DataFrame with `Observation Window`, `Prediction Window`, and `Label` columns. *(Commented out in test.py.)*

## Changes

### June 21, 2026
- Added `separation_minutes` parameter to `BuildForecastTable` to introduce a configurable gap between the current timestamp and the start of the prediction window, preventing data leakage between observation and prediction periods.
### June 22, 2026
- Added `evals` parameter to `WindowLabeler` to support configurable output columns: `goes-class`/`gc` includes the max GOES class per window, `flux`/`fx` derives and includes the peak flux in W/m², and `bl=<threshold>` adds a binary label indicating whether the window's peak class meets or exceeds a specified GOES class or numeric flux threshold.
### June 25, 2026
- Refactored `utils.py` from standalone functions and module-level globals (`event_list`, `datetimes`, `timestamps`, `csv_path`) into classes: `EventData` and `TimestampSeries` wrap the event CSV and timestamp file respectively, `GoesClass` centralizes the GOES-class/flux/threshold logic previously duplicated across `WindowLabeler` and `BuildForecastTable`, and `ObservationWindowBuilder`, `FullDiskLabeler` (formerly `WindowLabeler`), and `ForecastTableBuilder` (formerly `BuildForecastTable`) now take their data dependencies explicitly via the constructor instead of reading module globals.
- `setEventData`, `setTimeStampData`, and `TimeStampEventMatchTable` are removed; their behavior now lives on `EventData.__init__`, `TimestampSeries.__init__`, and `TimestampSeries.match_to_events`, respectively.
- Updated `__init__.py` to export the new classes (`GoesClass`, `EventData`, `TimestampSeries`, `ObservationWindowBuilder`, `FullDiskLabeler`, `ForecastTableBuilder`) in place of the old function names.
- Updated `test.py` to use the new class-based API.
- Identified a pre-existing bug (not introduced by this refactor): calling the observation-window builder with `hours=0` and `cadence=0` produces zero-length `timedelta`s, so the inner sampling loop never advances and hangs indefinitely. `test.py` now uses non-zero values and documents this in a comment.