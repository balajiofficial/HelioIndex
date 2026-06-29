# helio_index

A Python library for matching solar image timestamps to flare events and building observation/prediction windows for solar flare forecasting.

---

## Table of Contents

- [helio\_index](#helio_index)
  - [Table of Contents](#table-of-contents)
  - [Background](#background)
    - [GOES flare classes](#goes-flare-classes)
    - [Typical workflow](#typical-workflow)
    - [File naming convention](#file-naming-convention)
  - [Directory Structure](#directory-structure)
    - [File Descriptions](#file-descriptions)
  - [Classes (in `utils.py`)](#classes-in-utilspy)
    - [`GoesClass`](#goesclass)
    - [`EventData(csv_path)`](#eventdatacsv_path)
    - [`TimestampSeries(path)`](#timestampseriespath)
    - [`ObservationWindowBuilder(timestamps)`](#observationwindowbuildertimestamps)
    - [`FullDiskLabeler(events)`](#fulldisklabelerevents)
    - [`ForecastTableBuilder(timestamps, events)`](#forecasttablebuildertimestamps-events)
  - [Returns a DataFrame with columns `"Observation Window"`, `"Prediction Window"` (lists of `datetime` objects), and `"Label"` (a GOES class string). Does not validate that `obs_minutes`, `pred_minutes`, or `cadence_minutes` are positive — invalid values silently produce degenerate windows rather than raising.](#returns-a-dataframe-with-columns-observation-window-prediction-window-lists-of-datetime-objects-and-label-a-goes-class-string-does-not-validate-that-obs_minutes-pred_minutes-or-cadence_minutes-are-positive--invalid-values-silently-produce-degenerate-windows-rather-than-raising)
  - [Known Issues](#known-issues)
  - [Changelog](#changelog)
    - [June 21, 2026](#june-21-2026)
    - [June 22, 2026](#june-22-2026)
    - [June 25, 2026](#june-25-2026)
    - [June 27, 2026](#june-27-2026)

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

### `GoesClass`
A stateless helper class (all `staticmethod`s, never instantiated) centralizing GOES flare-class parsing, comparison, and conversion logic.

- `rank(cls)` — Returns the ordinal strength of a class string (0 = `"FQ"` through 5 = `"X"`), based only on its leading letter. Unrecognized or empty input defaults to rank 0 (`"FQ"`).
- `max_class(classes)` — Returns the strongest class string in a list, by `rank()`. Raises `ValueError` on an empty list.
- `to_flux(goes)` — Converts a class string (e.g. `"M2.5"`) to its X-ray flux in W/m², as `FLUX_BASE[letter] * multiplier`. Returns `0.0` for falsy input, `"FQ"`, or an unrecognized letter; falls back to a multiplier of `1.0` if the numeric suffix can't be parsed.
- `parse_threshold(bl_value)` — Parses a binary-label threshold string into a `(mode, value)` pair: a bare letter (e.g. `"M"`) yields `("rank", <rank>)` (matches "this letter or stronger"); a full class (e.g. `"M1.5"`) yields `("flux", <flux value>)` (matches by exact magnitude). Raises `ValueError` for an unrecognized or `"FQ"` leading letter.

### `EventData(csv_path)`
Wraps a CSV file of solar flare events (must contain `Date`, `Start`, `EName`, and `GOES Class` columns), loading it into an internal DataFrame on construction and building lookup tables for fast matching.

- `lookup_event(date_part, time_part)` — Looks up the event name for a compact `(date, time)` digit pair (e.g. `"20140112"`, `"153000"`), matching it against an internal `(date, time) -> EName` table built from the CSV's `Date`/`Start` columns with separators stripped. Returns `"FQ"` if no event started at that exact timestamp.
- `goes_class_for(ename)` — Resolves an event name to its GOES class string via an internal `EName -> GOES Class` table. Returns `"FQ"` for the literal input `"FQ"`, an unrecognized event name, or a missing/blank class value in the catalog.

### `TimestampSeries(path)`
Wraps a plain text file of image filenames (one per line, format `YYYYMMDD_HHMMSS.<ext>`), parsing both the raw filenames and their `datetime` values on construction. Assumes the file is already in chronological order.

- `__len__()` — Number of timestamped filenames loaded.
- `closest(target)` — Returns the single `datetime` in the series with the smallest absolute difference from `target` (linear scan; ties go to the first match in list order).
- `in_range(start, end, inclusive_start=False)` — Returns all datetimes falling in `(start, end]` by default, or `[start, end]` if `inclusive_start=True`.
- `match_to_events(events)` — Matches each filename's timestamp to an `EventData` catalog by splitting its `YYYYMMDD_HHMMSS` stem into date/time parts and doing an **exact** lookup (not nearest-neighbor). Returns a dict mapping each filename to its matched `EName`, or `"FQ"` if unmatched or malformed.

### `ObservationWindowBuilder(timestamps)`
Constructed with a `TimestampSeries`. Builds fixed-duration sliding windows of timestamps for use as model input sequences.

- `build(start_time, hours, cadence, sliding_window=None, end_time=None)` — Generates a list of sliding observation windows, each spanning `hours` hours and internally sampled every `cadence` minutes (snapped to the closest real timestamp). Window starts advance by `sliding_window` minutes between windows (defaulting to `cadence` if not given), stopping once a full window would exceed `end_time` or the series' last timestamp. `sliding_window` and `end_time` must be supplied together or not at all. Returns `None` (with a printed message) if `start_time` or `end_time` doesn't exactly match a timestamp in the series, or if only one of `sliding_window`/`end_time` is given. Note: omitting both `sliding_window` and `end_time` will raise a `TypeError` rather than returning cleanly, since `end_time` is required internally — in practice it should always be supplied.

### `FullDiskLabeler(events)`
Constructed with an `EventData` instance. Labels pre-built observation windows with the strongest flare activity observed within each.

- `label(windows, event_match, evals=None)` — For each window, converts its timestamps to filenames, looks each up in `event_match` (defaulting to `"FQ"` if absent), resolves to GOES classes via `events.goes_class_for`, and takes the window's strongest class via `GoesClass.max_class`. Returns a DataFrame with one row per window. The `evals` list controls which columns are included (case-insensitive, others ignored):
  - `"goes-class"` / `"gc"` → adds a `"GOES Class"` column.
  - `"flux"` / `"fx"` → adds a `"Flux"` column (via `GoesClass.to_flux`).
  - `"bl=<threshold>"` → adds a `"Binary Label"` column, thresholded per `GoesClass.parse_threshold` (rank-based for a bare letter, flux-based for a full class string). Only the first `"bl="` entry is honored.
  
  A `"Window"` column (list of filenames) is always present. If `evals` is omitted, only `"Window"` is returned.

### `ForecastTableBuilder(timestamps, events)`
Constructed with a `TimestampSeries` and an `EventData` instance. Unlike `ObservationWindowBuilder` + `FullDiskLabeler`, this builds one row **per timestamp** in the series, pairing a look-back observation window with a look-ahead prediction window (with an optional separation gap to prevent label leakage).

- `build(obs_minutes, pred_minutes, cadence_minutes, labeled, separation_minutes=0, limit=None)` — For each reference timestamp (or the first `limit` timestamps, if given):
  - **Observation window**: steps from `current_dt - obs_minutes` to `current_dt` every `cadence_minutes`, snapping each step to its closest real timestamp via `closest()` and skipping duplicates.
  - **Prediction window**: starts at `current_dt + separation_minutes` and spans forward `pred_minutes`, via `TimestampSeries.in_range` with its default exclusive start (so the reference timestamp is never reused in the prediction window).
  - **Label**: the strongest GOES class (`GoesClass.max_class`) among events matched (via `labeled`) to filenames in the prediction window; defaults to `"FQ"` if the prediction window is empty.
  
  Returns a DataFrame with columns `"Observation Window"`, `"Prediction Window"` (lists of `datetime` objects), and `"Label"` (a GOES class string). Does not validate that `obs_minutes`, `pred_minutes`, or `cadence_minutes` are positive — invalid values silently produce degenerate windows rather than raising.
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