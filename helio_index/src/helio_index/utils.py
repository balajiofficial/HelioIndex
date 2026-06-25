from datetime import datetime, timedelta
import pandas as pd

GOES_ORDER = ["FQ", "A", "B", "C", "M", "X"]
GOES_FLUX_BASE = {
    "FQ": 0.0,
    "A": 1e-8,
    "B": 1e-7,
    "C": 1e-6,
    "M": 1e-5,
    "X": 1e-4,
}


class GoesClass:
    """Stateless helpers for working with GOES flare-class strings."""

    @staticmethod
    def rank(cls: str) -> int:
        letter = cls[0].upper() if cls and cls != "FQ" else "FQ"
        return GOES_ORDER.index(letter) if letter in GOES_ORDER else 0

    @staticmethod
    def max_class(classes: list[str]) -> str:
        return max(classes, key=GoesClass.rank)

    @staticmethod
    def to_flux(goes: str) -> float:
        """Convert a GOES class string (e.g. 'M2.5', 'C', 'FQ') to flux in W/m^2."""
        if not goes or goes == "FQ":
            return 0.0
        letter = goes[0].upper()
        base = GOES_FLUX_BASE.get(letter, 0.0)
        try:
            multiplier = float(goes[1:]) if len(goes) > 1 else 1.0
        except ValueError:
            multiplier = 1.0
        return base * multiplier

    @staticmethod
    def parse_threshold(bl_value: str) -> tuple[str, float]:
        """
        Parse a binary-label threshold string.
        - Letter only (e.g. 'M')   -> compare by GOES rank (letter and above)
        - Full class (e.g. 'M1.5') -> compare by numeric flux value
        Returns (mode, threshold) where mode is 'rank' or 'flux'.
        """
        bl_value = bl_value.strip()
        letter = bl_value[0].upper()
        if letter not in GOES_ORDER or letter == "FQ":
            raise ValueError(f"Invalid binary-label threshold: '{bl_value}'")
        if len(bl_value) == 1:
            return "rank", GoesClass.rank(letter)
        return "flux", GoesClass.to_flux(bl_value)


class EventData:
    """Wraps the event CSV (Date, Start, EName, GOES Class, ...)."""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)
        self._datetime_lookup = self._build_datetime_lookup()
        self._ename_to_goes = dict(zip(self.df["EName"], self.df["GOES Class"]))

    def _build_datetime_lookup(self) -> dict[tuple[str, str], str]:
        lookup = {}
        for _, row in self.df.iterrows():
            date_key = row["Date"].replace("/", "")
            time_key = row["Start"].replace(":", "")
            lookup[(date_key, time_key)] = row["EName"]
        return lookup

    def lookup_event(self, date_part: str, time_part: str) -> str:
        return self._datetime_lookup.get((date_part, time_part), "FQ")

    def goes_class_for(self, ename: str) -> str:
        if ename == "FQ":
            return "FQ"
        return self._ename_to_goes.get(ename, "FQ") or "FQ"


class TimestampSeries:
    """Wraps a list of timestamped image filenames (YYYYMMDD_HHMMSS.jpg)."""

    def __init__(self, path: str):
        self.path = path
        self.filenames: list[str] = []
        self.datetimes: list[datetime] = []
        self._load(path)

    def _load(self, path: str):
        with open(path) as f:
            for line in f:
                name = line.strip()
                if not name:
                    continue
                self.filenames.append(name)
                stem = name.split(".")[0]
                self.datetimes.append(datetime.strptime(stem, "%Y%m%d_%H%M%S"))

    def __len__(self):
        return len(self.datetimes)

    def closest(self, target: datetime) -> datetime:
        return min(self.datetimes, key=lambda t: abs(t - target))

    def in_range(self, start: datetime, end: datetime, inclusive_start: bool = False) -> list[datetime]:
        if inclusive_start:
            return [dt for dt in self.datetimes if start <= dt <= end]
        return [dt for dt in self.datetimes if start < dt <= end]

    def match_to_events(self, events: EventData) -> dict[str, str]:
        """
        Match timestamp-formatted image filenames to events.

        Returns a dict where:
          - key   = original filename
          - value = EName if a matching event exists, else "FQ"
        """
        result: dict[str, str] = {}
        for filename in self.filenames:
            stem = filename.rsplit(".", 1)[0]
            parts = stem.split("_")
            if len(parts) == 2:
                date_part, time_part = parts
                result[filename] = events.lookup_event(date_part, time_part)
            else:
                result[filename] = "FQ"
        return result


class ObservationWindowBuilder:
    """Builds sliding observation windows over a TimestampSeries."""

    def __init__(self, timestamps: TimestampSeries):
        self.timestamps = timestamps

    def build(
        self,
        start_time: str,
        hours: int,
        cadence: int,
        sliding_window: int = None,
        end_time: str = None,
    ) -> list[list[datetime]]:
        start_dt = datetime.strptime(start_time, "%Y%m%d_%H%M%S")
        end_dt = datetime.strptime(end_time, "%Y%m%d_%H%M%S")
        hours_td = timedelta(hours=hours)
        cadence_td = timedelta(minutes=cadence)
        slide_td = timedelta(minutes=sliding_window) if sliding_window is not None else cadence_td

        if start_dt not in self.timestamps.datetimes:
            print("start_time not found in file list")
            return

        if (sliding_window is None) != (end_time is None):
            print("error, both sliding_window and end_time must have values")
            return

        if end_dt not in self.timestamps.datetimes:
            print("out of range error")
            return

        if start_dt + hours_td > end_dt:
            print("observation window bigger than end_time")

        windows = []
        iter_start = start_dt
        last_dt = self.timestamps.datetimes[-1]

        while iter_start + hours_td <= end_dt and iter_start + hours_td <= last_dt:
            window = []
            t = iter_start
            while t <= iter_start + hours_td:
                window.append(self.timestamps.closest(t))
                t += cadence_td
            windows.append(window)
            iter_start += slide_td

        return windows


class FullDiskLabeler:
    """Labels pre-built windows (from ObservationWindowBuilder) with GOES class / flux / binary label."""

    def __init__(self, events: EventData):
        self.events = events

    def label(
        self,
        windows: list[list[datetime]],
        event_match: dict[str, str],
        evals: list[str] = None,
    ) -> pd.DataFrame:
        evals = [e.strip().lower() for e in evals] if evals else []

        include_goes = any(e in ("goes-class", "gc") for e in evals)
        include_flux = any(e in ("flux", "fx") for e in evals)

        bl_mode = None
        bl_threshold = None
        for e in evals:
            if e.startswith("bl="):
                bl_mode, bl_threshold = GoesClass.parse_threshold(e[3:])
                break

        rows = []
        for window in windows:
            filenames = [dt.strftime("%Y%m%d_%H%M%S") + ".jpg" for dt in window]

            flare_classes = []
            for filename in filenames:
                ename = event_match.get(filename, "FQ")
                flare_classes.append(self.events.goes_class_for(ename))

            max_class = GoesClass.max_class(flare_classes)

            row = {"Window": filenames}

            if include_goes:
                row["GOES Class"] = max_class

            if include_flux:
                row["Flux"] = GoesClass.to_flux(max_class)

            if bl_mode is not None:
                if bl_mode == "rank":
                    row["Binary Label"] = int(GoesClass.rank(max_class) >= bl_threshold)
                else:  # flux
                    row["Binary Label"] = int(GoesClass.to_flux(max_class) >= bl_threshold)

            rows.append(row)

        cols = ["Window"]
        if include_goes:
            cols.append("GOES Class")
        if include_flux:
            cols.append("Flux")
        if bl_mode:
            cols.append("Binary Label")

        return pd.DataFrame(rows, columns=cols)


class ForecastTableBuilder:
    """Builds observation/prediction window pairs for forecasting, with leakage-safe separation."""

    def __init__(self, timestamps: TimestampSeries, events: EventData):
        self.timestamps = timestamps
        self.events = events

    def build(
        self,
        obs_minutes: int,
        pred_minutes: int,
        cadence_minutes: int,
        labeled: dict[str, str],
        separation_minutes: int = 0,
        limit: int = None,
    ) -> pd.DataFrame:
        """
        For each timestamp, looks back M minutes (observation window) with cadence C
        and forward N minutes (prediction window), then labels the row with the max
        GOES class found in the prediction window.
        """
        obs_td = timedelta(minutes=obs_minutes)
        pred_td = timedelta(minutes=pred_minutes)
        cadence_td = timedelta(minutes=cadence_minutes)
        sep_td = timedelta(minutes=separation_minutes)

        dts = self.timestamps.datetimes
        limit = len(dts) if limit is None else limit

        rows = []
        for current_dt in dts[:limit]:
            # --- Observation window (look back M minutes at cadence C) ---
            obs_window = []
            t = current_dt - obs_td
            while t <= current_dt:
                closest = self.timestamps.closest(t)
                if closest not in obs_window:
                    obs_window.append(closest)
                t += cadence_td

            # --- Prediction window (skip separation gap, then look forward N minutes) ---
            pred_start = current_dt + sep_td
            pred_window = self.timestamps.in_range(pred_start, pred_start + pred_td)

            # --- Label: max GOES class in prediction window ---
            flare_classes = []
            for dt in pred_window:
                filename = dt.strftime("%Y%m%d_%H%M%S") + ".jpg"
                ename = labeled.get(filename, "FQ")
                flare_classes.append(self.events.goes_class_for(ename))

            label = GoesClass.max_class(flare_classes) if flare_classes else "FQ"

            rows.append({
                "Observation Window": obs_window,
                "Prediction Window": pred_window,
                "Label": label,
            })

        return pd.DataFrame(rows, columns=["Observation Window", "Prediction Window", "Label"])