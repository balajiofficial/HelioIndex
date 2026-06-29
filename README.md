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

## Example Script Walkthrough

The snippet below exercises the full `helio_index` pipeline end-to-end: load data → match timestamps to events → build observation windows → label those windows. Each step is explained in detail.

```python
from helio_index.src.helio_index.utils import (
    EventData,
    TimestampSeries,
    ObservationWindowBuilder,
    FullDiskLabeler,
    ForecastTableBuilder,
)
import pprint
```

### 1. Loading data — `EventData` and `TimestampSeries`

```python
events = EventData('flare_events.csv')
timestamps = TimestampSeries('timestamps.txt')
```

- **`EventData('flare_events.csv')`** reads the flare-event catalog into a `pandas.DataFrame` and builds two internal lookup tables: `(date, time) -> EName` and `EName -> GOES Class`. The CSV is expected to have `Date`, `Start`, `EName`, and `GOES Class` columns. These lookups power `lookup_event()` and `goes_class_for()`, which every other class in the module relies on to resolve an event name to a GOES class.
- **`TimestampSeries('timestamps.txt')`** reads a plain text file of image filenames (one per line, formatted `YYYYMMDD_HHMMSS.jpg`) and parses each into a `datetime`. It keeps two parallel lists, `filenames` and `datetimes`, in file order — so the file must already be chronologically sorted for window-building to behave correctly.

Both classes are self-contained: each owns its own state instead of relying on module-level globals, which is what lets `ObservationWindowBuilder`, `FullDiskLabeler`, and `ForecastTableBuilder` each take the data they need explicitly through their constructors.

### 2. Matching timestamps to events — `TimestampSeries.match_to_events`

```python
labeled = timestamps.match_to_events(events)
```

For every filename in `timestamps`, this splits the embedded date/time out of the filename stem and looks it up against `events`' catalog for an **exact** match (not nearest-neighbor). The result is a `dict[str, str]` mapping each filename to either the `EName` of the event that started at that exact timestamp, or `"FQ"` ("flare quiet") if nothing matches. This dictionary, `labeled`, is the bridge between raw timestamps and event identities and gets reused by both `FullDiskLabeler` and `ForecastTableBuilder`.

### 3. Building sliding windows — `ObservationWindowBuilder`

```python
window_builder = ObservationWindowBuilder(timestamps)
ow = window_builder.build("20251001_001400", 2, 10, 60, "20251001_143600")
```

`ObservationWindowBuilder` is constructed once with a `TimestampSeries`, then reused across calls to `build()`. Each call generates a list of fixed-duration sliding windows of timestamps:

| Argument | Value here | Meaning |
|---|---|---|
| `start_time` | `"20251001_001400"` | First window's start. Must exactly match a timestamp in `timestamps` or `build()` prints an error and returns `None`. |
| `hours` | `2` | Each window spans 2 hours. |
| `cadence` | `10` | Within a window, sample every 10 minutes (snapped to the closest real timestamp). |
| `sliding_window` | `60` | Each successive window's start advances by 60 minutes (the "stride"). |
| `end_time` | `"20251001_143600"` | Last point any window is allowed to reach; must also exactly match a timestamp in `timestamps`. |

`sliding_window` and `end_time` are a package deal — both must be supplied together or both omitted. The builder keeps producing windows until the next one would extend past `end_time` or past the last available timestamp.

> ⚠️ **Known bug, not introduced by this refactor:** calling `build()` with `hours=0` and `cadence=0` produces zero-length `timedelta`s, so the inner sampling loop's step never advances and the call hangs indefinitely. The demo above deliberately uses non-zero `hours=2, cadence=10` so it actually terminates.

### 4. Labeling windows — `FullDiskLabeler`

```python
labeler = FullDiskLabeler(events)
wl = labeler.label(
    ow,
    labeled,
    evals=["gc", "fx", "bl=C"]        # GOES class + flux + binary >= M
)
```

`FullDiskLabeler` is constructed with the `EventData` instance, then `.label()` is called with the windows from step 3 and the `labeled` dict from step 2. For each window, every timestamp is converted back to a filename, looked up in `labeled`/`events` to get a GOES class, and the window's overall label becomes the **strongest** class seen at any point in that window.

The `evals` list controls which columns appear in the returned DataFrame, and is checked case-insensitively:

- **`"gc"`** (or `"goes-class"`) → adds a `GOES Class` column with the window's peak class string (e.g. `"M2.5"`).
- **`"fx"`** (or `"flux"`) → adds a `Flux` column with that class converted to W/m².
- **`"bl=C"`** → adds a `Binary Label` column. The text after `bl=` is parsed by `GoesClass.parse_threshold()`:
  - A bare letter like `"C"` thresholds **by rank** — the window is labeled `1` if its peak class is C-or-stronger, regardless of magnitude.
  - A full class like `"C3.0"` would instead threshold **by exact flux value**.

  > Note: the comment in the snippet (`# GOES class + flux + binary >= M`) describes the *intent* behind `evals`, but the threshold actually passed is `"bl=C"`, so the binary label here triggers on **C-class or stronger**, not M-class. Use `"bl=M"` if M-and-above is the intended cutoff.

Only the first `bl=`-prefixed entry in `evals` is honored if more than one is present, and any unrecognized strings in `evals` are silently ignored.

### 5. (Commented out) Building a forecast table — `ForecastTableBuilder`

```python
# forecast_builder = ForecastTableBuilder(timestamps, events)
# bt = forecast_builder.build(240, 480, 60, labeled, 30, 150)
```

This step is present but disabled in the snippet. When enabled, `ForecastTableBuilder` takes a different approach than steps 3–4: rather than building independent fixed windows, it centers on **every timestamp** in the series and builds a matched pair of windows around it:

- **Observation window** — looks *backward* `obs_minutes` (here, `240` = 4 hours), sampled every `cadence_minutes` (`60`), ending at the reference timestamp.
- **Prediction window** — skips a `separation_minutes` gap (`30`) after the reference timestamp, then looks *forward* `pred_minutes` (`480` = 8 hours).
- **Label** — the maximum GOES class found anywhere in the prediction window (via `labeled`), defaulting to `"FQ"` if the prediction window is empty.

The `separation_minutes` gap exists specifically to prevent label leakage — without it, the prediction window could start immediately adjacent to (or overlapping) the observation window's own endpoint. `limit=150` restricts this to only the first 150 timestamps in the series, useful for quick testing rather than processing the entire file. The result is a DataFrame with `Observation Window`, `Prediction Window`, and `Label` columns, ready to feed into model training.

### Inspecting results

```python
pprint.pprint(ow)
pprint.pprint(wl)
```

`pprint` is used here purely for readability when eyeballing intermediate results in a terminal/notebook — `ow` is a list of lists of `datetime` objects, and `wl` is a `pandas.DataFrame`, both of which can get visually dense with the default `print()`.