# helio_index

A Python library for matching solar image timestamps to flare events and building observation/prediction windows for solar flare forecasting.

---

## Table of Contents

- [Background](#background)
  - [GOES flare classes](#goes-flare-classes)
  - [Typical workflow](#typical-workflow)
  - [File naming convention](#file-naming-convention)
- [Directory Structure](#directory-structure)
- [Classes (in `utils.py`)](#classes-in-utilspy)
- [Examples (`test.py`)](#examples-testpy)
- [Known Issues](#known-issues)
- [Changelog](#changelog)

---

## Background

This module provides tools for working with time series of solar images and labeling them according to solar flare activity, based on the GOES (Geostationary Operational Environmental Satellite) flare classification system. It is intended for building machine learning datasets for solar flare forecasting / nowcasting.

### GOES flare classes

NOAA classifies solar flares by their peak X-ray flux (in W/m²) using a letter + number scheme, from weakest to strongest:

```
A < B < C < M < X
```

Each letter corresponds to a power-of-ten range of flux, and the number after the letter is a linear multiplier within that range. For example:

- `C1.0` means flux = 1e-6 W/m² (C-base) * 1.0
- `M2.5` means flux = 1e-5 W/m² (M-base) * 2.5
- `X9.3` means flux = 1e-4 W/m² (X-base) * 9.3

`"FQ"` ("flare quiet") is used throughout this module as a placeholder class meaning "no flare" / below detectable background level. It is not a standard GOES letter, but is treated as the lowest possible class so it naturally sorts below `"A"`.

### Typical workflow

1. Load the event catalog with `EventData` (one row per known flare event, with its start date/time, name, and GOES class).
2. Load a list of timestamped image filenames with `TimestampSeries`.
3. Either:
   - Build fixed-length sliding windows over the images with `ObservationWindowBuilder`, then label each window's peak flare activity with `FullDiskLabeler`; or
   - Build paired (observation window → prediction window) rows for forecasting with `ForecastTableBuilder`, which keeps a configurable gap between what the model "sees" and what it must "predict" to avoid information leakage.

### File naming convention

Image filenames are expected to look like `YYYYMMDD_HHMMSS.jpg`, e.g. `20140112_153000.jpg` for 2014-01-12 at 15:30:00. This module relies on that format to parse timestamps from filenames.

---

## Directory Structure

```
helio_index/
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
| `pyproject.toml` | Project metadata and build configuration (name, version, author, Python version requirement, Poetry build system) |
| `README.md` | Placeholder README inside the package directory |
| `src/helio_index/__init__.py` | Package initializer that exports the public API classes from `utils.py` |
| `src/helio_index/__main__.py` | Entry point for running the package as a module (currently empty) |
| `src/helio_index/utils.py` | **All core library functions live here** (see note below) |

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

---

## Known Issues

- **`ObservationWindowBuilder.build` hangs on `hours=0` and `cadence=0`.** Both produce zero-length `timedelta`s, so the inner sampling loop never advances and the call never returns. This is a pre-existing bug, not introduced by the June 25, 2026 refactor. `test.py` uses non-zero values and documents this in a comment as a workaround; a future fix should validate these arguments and raise instead of hanging.

---

## Changelog

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

### June 27, 2026
- Added comprehensive documentation to `utils.py`
- Reorganized the structure to make content more accessible