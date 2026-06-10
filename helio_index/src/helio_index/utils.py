from datetime import datetime, timedelta
import pandas as pd
import pprint

event_list = None
datetimes = []
timestamps = []
csv_path = None

def setEventData(path):
    global event_list, csv_path
    csv_path = path
    event_list = pd.read_csv(path)


def setTimeStampData(path):
    global timestamps
    global datetimes
    datetimes = []
    timestamps = []
    
    with open(path) as f:
        for line in f:
            name = line.strip()
            if not name:
                continue
            timestamps.append(name)
            stem = name.split(".")[0]
            datetimes.append(datetime.strptime(stem, "%Y%m%d_%H%M%S"))

def TimeStampEventMatchTable():
    global timestamps
    global event_list
    """
    Match timestamp-formatted image filenames to events in a CSV file.
 
    Filename format: YYYYMMDD_HHMMSS.jpg  (e.g. 20240224_200000.jpg)
    CSV columns used: 'Date' (YYYY/MM/DD), 'Start' (HH:MM:SS), 'EName'
 
    Returns a dict where:
      - key   = original filename
      - value = EName if a matching event exists, else "FQ"
    """
    df = event_list
    filenames = timestamps
 
    event_lookup: dict[tuple[str, str], str] = {}
    for _, row in df.iterrows():
        date_key = row["Date"].replace("/", "")
        time_key = row["Start"].replace(":", "")
        event_lookup[(date_key, time_key)] = row["EName"]
 
    result: dict[str, str] = {}
    for filename in filenames:
        stem = filename.rsplit(".", 1)[0]      
        parts = stem.split("_")          
 
        if len(parts) == 2:
            date_part, time_part = parts        
        else:
            result[filename] = "FQ"
            continue
 
        result[filename] = event_lookup.get((date_part, time_part), "FQ")
 
    return result

def ObservationWindow(start_time: str, hours: int, cadence: int, sliding_window: int = None, end_time: int = None):
    start_time = datetime.strptime(start_time, "%Y%m%d_%H%M%S")
    end_time = datetime.strptime(end_time, "%Y%m%d_%H%M%S")
    hours_td = timedelta(hours=hours)
    cadence_td = timedelta(minutes=cadence)
    slide_td = timedelta(minutes=sliding_window) if sliding_window is not None else cadence_td
    if cadence < 1:
        print("Invalid cadence")
        return

    if start_time not in datetimes:
        print("start_time not found in file list")
        return

    if sliding_window is not None and end_time is None or end_time is not None and sliding_window is None:
        print("error, both sliding_window and end_time must have values")
        return
    
    if end_time not in datetimes:
        print("out of range error")
        return

    if start_time + hours_td > end_time:
        print("observation window bigger than end_time")

    l = []
    iter_start_time = start_time

    while iter_start_time + hours_td <= end_time and iter_start_time + hours_td <= datetimes[-1]:
        window = []
        iter_time = iter_start_time

        while iter_time <= iter_start_time + hours_td:
            closest = min(datetimes, key=lambda t: abs(t - iter_time))
            window.append(closest)
            iter_time += cadence_td

        l.append(window)
        iter_start_time += slide_td

    return l

def WindowLabeler(windows: list[list[datetime]], event_match: dict[str, str]) -> pd.DataFrame:
    GOES_ORDER = ["FQ", "A", "B", "C", "M", "X"]

    def goes_rank(cls: str) -> int:
        letter = cls[0].upper() if cls and cls != "FQ" else "FQ"
        return GOES_ORDER.index(letter) if letter in GOES_ORDER else 0

    def max_goes(classes: list[str]) -> str:
        return max(classes, key=goes_rank)

    ename_to_goes: dict[str, str] = {}
    for _, row in event_list.iterrows():
        ename_to_goes[row["EName"]] = row["GOES Class"]

    rows = []
    for window in windows:
        filenames = [dt.strftime("%Y%m%d_%H%M%S") + ".jpg" for dt in window]

        flare_classes = []
        for filename in filenames:
            ename = event_match.get(filename, "FQ")
            if ename == "FQ":
                flare_classes.append("FQ")
            else:
                goes = ename_to_goes.get(ename, "FQ")
                flare_classes.append(goes if goes else "FQ")

        rows.append({
            "Window": filenames,
            "Flare": max_goes(flare_classes)
        })

    return pd.DataFrame(rows, columns=["Window", "Flare"])

def BuildForecastTable(
    obs_minutes: int,
    pred_minutes: int,
    cadence_minutes: int,
    labeled: dict[str, str],
    limit: int = None
) -> pd.DataFrame:
    """
    For each timestamp, looks back M minutes (observation window) with cadence C
    and forward N minutes (prediction window), then labels the row with the max
    GOES class found in the prediction window.

    Parameters:
        obs_minutes    : M - how far back to collect observation timestamps
        pred_minutes   : N - how far forward to scan for flares
        cadence_minutes: C - step size when collecting observation window timestamps
        labeled        : output of TimeStampEventMatchTable(), maps filename -> EName or "FQ"

    Returns a DataFrame with columns:
        'Observation Window' : list of timestamps in the lookback window
        'Prediction Window'  : list of timestamps in the lookahead window
        'Label'              : max GOES class in the prediction window, or "FQ"
    """
    GOES_ORDER = ["FQ", "A", "B", "C", "M", "X"]

    def goes_rank(cls: str) -> int:
        letter = cls[0].upper() if cls and cls != "FQ" else "FQ"
        return GOES_ORDER.index(letter) if letter in GOES_ORDER else 0

    def max_goes(classes: list[str]) -> str:
        return max(classes, key=goes_rank)

    obs_td     = timedelta(minutes=obs_minutes)
    pred_td    = timedelta(minutes=pred_minutes)
    cadence_td = timedelta(minutes=cadence_minutes)

    # Build EName -> GOES class lookup from event_list
    ename_to_goes: dict[str, str] = {}
    for _, row in event_list.iterrows():
        ename_to_goes[row["EName"]] = row["GOES Class"]

    rows = []
    limit = len(datetimes) if limit is None else limit
    for current_dt in datetimes[:limit]:

        # --- Observation window (look back M minutes at cadence C) ---
        obs_window = []
        t = current_dt - obs_td
        while t <= current_dt:
            closest = min(datetimes, key=lambda x: abs(x - t))
            if closest not in obs_window:
                obs_window.append(closest)
            t += cadence_td

        # --- Prediction window (look forward N minutes, every timestamp) ---
        pred_window = [
            dt for dt in datetimes
            if current_dt < dt <= current_dt + pred_td
        ]

        # --- Label: max GOES class in prediction window ---
        flare_classes = []
        for dt in pred_window:
            filename = dt.strftime("%Y%m%d_%H%M%S") + ".jpg"
            ename = labeled.get(filename, "FQ")
            goes = ename_to_goes.get(ename, "FQ") if ename != "FQ" else "FQ"
            flare_classes.append(goes if goes else "FQ")

        label = max_goes(flare_classes) if flare_classes else "FQ"

        rows.append({
            "Observation Window": obs_window,
            "Prediction Window" : pred_window,
            "Label"             : label
        })

    return pd.DataFrame(rows, columns=["Observation Window", "Prediction Window", "Label"])