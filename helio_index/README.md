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
| `helio_index/src/helio_index/__init__.py` | Package initializer that exports the public API functions from `utils.py` |
| `helio_index/src/helio_index/__main__.py` | Entry point for running the package as a module (currently empty) |
| `helio_index/src/helio_index/utils.py` | **All core library functions live here** (see note below) |

> **Note: Currently, all functions are implemented in `utils.py`.**

---

## Functions (in `utils.py`)

### `setEventData(path)`
Loads a CSV file of solar flare events into the global `event_list` DataFrame.

### `setTimeStampData(path)`
Reads a text file of image filenames and populates the global `timestamps` and `datetimes` lists.

### `TimeStampEventMatchTable()`
Matches each image filename to a solar flare event by comparing date and start time; returns a dictionary mapping each filename to an event name (`EName`) or `"FQ"` (quiet sun) if no event matches.

### `ObservationWindow(start_time, hours, cadence, sliding_window, end_time)`
Generates a list of sliding observation windows between two timestamps, where each window spans a given number of hours and samples timestamps at a specified cadence (in minutes).

### `WindowLabeler(windows, event_match)`
Takes a list of observation windows and the event match dictionary, then returns a DataFrame labeling each window with the highest GOES flare class (`A`, `B`, `C`, `M`, `X`, or `FQ`) observed within it.

### `BuildForecastTable(obs_minutes, pred_minutes, cadence_minutes, labeled, limit)`
For each timestamp, builds a lookback observation window and a lookahead prediction window, then labels each row with the maximum GOES class found in the prediction window — producing a DataFrame ready for machine learning.

---

## Examples (`test.py`)

`test.py` demonstrates the full pipeline from data loading to forecast table construction.

### 1. Loading data
```python
setEventData('events.csv')
setTimeStampData('files.txt')
```
Both data sources are loaded into module-level globals before any other functions are called.

### 2. `TimeStampEventMatchTable`
```python
labeled = TimeStampEventMatchTable()
```
Reads the loaded timestamps and event list and returns a dictionary. Each image filename maps to its corresponding `EName` if the date and start time match an event in `events.csv`, or `"FQ"` if no event matches.

### 3. `ObservationWindow`
```python
# ow = ObservationWindow("20251001_001400", 4, 15, 60, "20251002_001400")
```
Generates 4-hour observation windows starting at `20251001_001400`, sampled every 15 minutes, sliding forward by 60 minutes at a time until `20251002_001400`. *(Commented out in test.py.)*

### 4. `WindowLabeler`
```python
# wl = WindowLabeler(ow, labeled)
```
Takes the windows from `ObservationWindow` and the `labeled` dictionary to produce a DataFrame where each window is tagged with its peak flare class. *(Commented out in test.py.)*

### 5. `BuildForecastTable`
```python
# bt = BuildForecastTable(240, 480, 60, labeled, 150)
```
For each of the first 150 timestamps: looks back 240 minutes (observation window sampled hourly) and forward 480 minutes (prediction window), then labels the row with the maximum GOES class in the prediction window. Returns a DataFrame with `Observation Window`, `Prediction Window`, and `Label` columns. *(Commented out in test.py.)*

## Changes

### June 21, 2026
- Added `separation_minutes` parameter to `BuildForecastTable` to introduce a configurable gap between the current timestamp and the start of the prediction window, preventing data leakage between observation and prediction periods.