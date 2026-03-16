import re
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_cadence(cadence: str) -> timedelta:
    """
    Parse a human-readable cadence string into a timedelta.
    Examples: '1 sec', '3 minutes', '2 hrs', '30s', '1hour', '10min'
    """
    cadence = cadence.strip().lower()
    match = re.match(r"(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)", cadence)
    if not match:
        raise ValueError(f"Cannot parse cadence: '{cadence}'")
    value = float(match.group(1))
    unit = match.group(2)
    if unit in ("s", "sec", "secs", "second", "seconds"):
        return timedelta(seconds=value)
    elif unit in ("m", "min", "mins", "minute", "minutes"):
        return timedelta(minutes=value)
    elif unit in ("h", "hr", "hrs", "hour", "hours"):
        return timedelta(hours=value)


def goes_class_key(label: str):
    """
    Return a sort key for a GOES class string like 'C3.9', 'M1.6', 'X2.1'.
    Class letter order: A < B < C < M < X
    """
    label = label.strip()
    order = {"A": 0, "B": 1, "C": 2, "M": 3, "X": 4}
    if not label or label[0].upper() not in order:
        return (-1, 0.0)  # unknown / missing → lowest
    letter = label[0].upper()
    try:
        number = float(label[1:])
    except ValueError:
        number = 0.0
    return (order[letter], number)


def extract_datetime_from_path(path: str) -> datetime:
    """
    Extract datetime from a path like:
    /Users/.../input/20260115_020000.jpg  →  2026-01-15 02:00:00
    """
    stem = Path(path).stem  # e.g. '20260115_020000'
    return datetime.strptime(stem, "%Y%m%d_%H%M%S")


def load_goes_lookup(csv_path: str) -> dict:
    """
    Load the GOES event CSV and return a dict mapping
    datetime (floored to second) → GOES class string.
    The 'Start' column is used as the timestamp key.
    """
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    df["Start"] = pd.to_datetime(df["Start"], format="%Y/%m/%d %H:%M:%S")
    df["GOES Class"] = df["GOES Class"].str.strip()
    return dict(zip(df["Start"].dt.to_pydatetime(), df["GOES Class"]))


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def select_files(
    csv_path: str,
    jpg_files: list[str],
    cadence: str,
    start_datetime: datetime,
    finish_datetime: datetime,
    evaluation: int,          # 0 = max GOES class, 1 = last GOES class
) -> dict:
    """
    Select JPG files from jpg_files starting at start_datetime, stepping by
    cadence, up to (but not exceeding) finish_datetime.

    Parameters
    ----------
    csv_path        : path to the GOES events CSV
    jpg_files       : list of file paths (sorted, 1-second intervals)
    cadence         : interval string e.g. '1 sec', '3 minutes', '2 hrs'
    start_datetime  : first timestamp to include
    finish_datetime : upper bound (inclusive if exact match exists)
    evaluation      : 0 → max GOES class over window; 1 → last timestamp's class

    Returns
    -------
    {
        "selected_files": [...],   # list of selected jpg paths
        "goes_class": str          # assigned GOES class label
    }
    """
    # --- Build a fast datetime → path lookup from the jpg list --------------
    dt_to_path = {extract_datetime_from_path(p): p for p in jpg_files}
    sorted_dts = sorted(dt_to_path)  # sorted list of available datetimes

    # --- Load GOES lookup table ---------------------------------------------
    goes_lookup = load_goes_lookup(csv_path)

    # --- Walk through timestamps at the requested cadence -------------------
    step = parse_cadence(cadence)
    selected_files = []
    selected_dts = []

    current = start_datetime
    while current <= finish_datetime:
        # Find the closest available jpg file <= current
        # (handles gaps — picks the last file that doesn't exceed current)
        candidates = [dt for dt in sorted_dts if dt <= current]
        if candidates:
            best = max(candidates)
            path = dt_to_path[best]
            if path not in selected_files:  # avoid duplicates at boundaries
                selected_files.append(path)
                selected_dts.append(best)
        current += step

    if not selected_files:
        return {"selected_files": [], "goes_class": None}

    # --- Determine GOES class -----------------------------------------------
    if evaluation == 1:
        # Value at the last selected timestamp
        last_dt = selected_dts[-1]
        goes_class = goes_lookup.get(last_dt, "A0.0")  # default = no event
    else:
        # Maximum GOES class across all selected timestamps
        classes = [goes_lookup.get(dt, "A0.0") for dt in selected_dts]
        goes_class = max(classes, key=goes_class_key)

    return {
        "selected_files": selected_files,
        "goes_class": goes_class,
    }


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    files = open('file_list.txt').read().splitlines()

    result = select_files(
        csv_path="file1.csv",
        jpg_files=files,
        cadence="3 minutes",
        start_datetime=datetime(2026, 2, 6, 2, 23, 0),
        finish_datetime=datetime(2026, 2, 6, 3, 0, 0),
        evaluation=0, # Evaluation: 0 → max GOES class over window; 1 → last timestamp's class
    )

    print(f"Selected {len(result['selected_files'])} files")
    print(f"GOES Class: {result['goes_class']}")
    for f in result["selected_files"]:
        print(" ", f)