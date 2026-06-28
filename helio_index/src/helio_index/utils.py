from datetime import datetime, timedelta
import pandas as pd


class GoesClass:
    """
    Stateless helper functions for parsing, comparing, and converting GOES
    flare-class strings (e.g. "FQ", "A", "B2.0", "M1.5", "X9.3").

    This class is never instantiated; all methods are staticmethods and act
    purely on the string/list arguments passed to them.
    """

    # Canonical ordering of GOES classes from weakest to strongest.
    # "FQ" ("flare quiet" / no flare) is treated as weaker than "A".
    ORDER = ["FQ", "A", "B", "C", "M", "X"]

    # Base flux (in W/m^2) for each letter class, i.e. the flux value
    # corresponding to a multiplier of 1.0 (e.g. "M1.0" -> 1e-5).
    FLUX_BASE = {
        "FQ": 0.0,
        "A": 1e-8,
        "B": 1e-7,
        "C": 1e-6,
        "M": 1e-5,
        "X": 1e-4,
    }

    @staticmethod
    def rank(cls: str) -> int:
        """
        Return the relative strength rank of a GOES class string.

        Higher rank = stronger flare. Used both for sorting/comparing
        classes and as the `key` function for `max()` in `max_class`.

        Parameters
        ----------
        cls : str
            A GOES class string such as "FQ", "A", "B2.0", "M1.5", "X9.3".
            Only the first character is examined (the letter); any trailing
            numeric magnitude is ignored for ranking purposes.

        Returns
        -------
        int
            Index of the class's letter within `GoesClass.ORDER`
            (0 = "FQ", 1 = "A", ..., 5 = "X"). Returns 0 (i.e. treated as
            "FQ"/weakest) if `cls` is empty, None, or starts with an
            unrecognized letter.

        Examples
        --------
        >>> GoesClass.rank("FQ")
        0
        >>> GoesClass.rank("M1.5")
        4
        >>> GoesClass.rank("X9.3")
        5
        """
        # Treat falsy values (None, "") and the literal "FQ" string as the
        # "FQ" class; otherwise take the first character as the letter.
        letter = cls[0].upper() if cls and cls != "FQ" else "FQ"
        return GoesClass.ORDER.index(letter) if letter in GoesClass.ORDER else 0

    @staticmethod
    def max_class(classes: list[str]) -> str:
        """
        Return the strongest (highest-ranked) GOES class in a list.

        Parameters
        ----------
        classes : list[str]
            A list of GOES class strings (e.g. the classes of all flares
            observed within some time window). Must not be empty.

        Returns
        -------
        str
            The class string from `classes` with the highest `rank()`.
            If multiple entries share the top rank, the first one
            encountered in `classes` is returned (Python's `max` behavior).

        Raises
        ------
        ValueError
            If `classes` is empty (since `max()` on an empty sequence
            raises ValueError).

        Examples
        --------
        >>> GoesClass.max_class(["FQ", "B1.0", "M2.5", "C3.0"])
        'M2.5'
        """
        return max(classes, key=GoesClass.rank)

    @staticmethod
    def to_flux(goes: str) -> float:
        """
        Convert a GOES class string to its corresponding X-ray flux value.

        Parameters
        ----------
        goes : str
            A GOES class string, e.g. "M2.5", "C", "X9.3", "FQ", "", or None.
            If only a letter is given with no trailing number (e.g. "C"),
            a multiplier of 1.0 is assumed.

        Returns
        -------
        float
            The flux in W/m^2: `FLUX_BASE[letter] * multiplier`.
            Returns 0.0 for falsy input or "FQ".
            Returns 0.0 base flux (times multiplier) for an unrecognized
            letter, since `FLUX_BASE.get(letter, 0.0)` defaults to 0.0.
            If the trailing characters after the letter cannot be parsed
            as a float (e.g. malformed input), the multiplier silently
            falls back to 1.0 rather than raising an error.

        Examples
        --------
        >>> GoesClass.to_flux("M2.5")
        2.5e-05
        >>> GoesClass.to_flux("C")
        1e-06
        >>> GoesClass.to_flux("FQ")
        0.0
        """
        if not goes or goes == "FQ":
            return 0.0
        letter = goes[0].upper()
        base = GoesClass.FLUX_BASE.get(letter, 0.0)
        try:
            # Everything after the letter is the numeric multiplier, e.g.
            # "M2.5" -> letter="M", multiplier=2.5. If there's no numeric
            # suffix (just the bare letter), default multiplier to 1.0.
            multiplier = float(goes[1:]) if len(goes) > 1 else 1.0
        except ValueError:
            # Malformed multiplier (e.g. unexpected suffix characters):
            # fall back to a multiplier of 1.0 rather than raising.
            multiplier = 1.0
        return base * multiplier

    @staticmethod
    def parse_threshold(bl_value: str) -> tuple[str, float]:
        """
        Parse a binary-label threshold specification used by
        `FullDiskLabeler` (the value following "bl=" in its `evals` list).

        Two threshold styles are supported:
          - Letter only (e.g. "M")     -> "rank" mode: a window is labeled
            positive if its max class's *rank* is >= the rank of this
            letter (i.e. "M and above", regardless of magnitude).
          - Full class (e.g. "M1.5")   -> "flux" mode: a window is labeled
            positive if its max class's *flux value* is >= the flux value
            of this specific class (a finer-grained, magnitude-aware cut).

        Parameters
        ----------
        bl_value : str
            The threshold string, e.g. "M" or "M1.5". Leading/trailing
            whitespace is stripped automatically.

        Returns
        -------
        tuple[str, float]
            A `(mode, threshold)` pair where `mode` is either "rank" or
            "flux", and `threshold` is the corresponding numeric value
            (an integer rank or a float flux) to compare against.

        Raises
        ------
        ValueError
            If the first character of `bl_value` is not a recognized GOES
            letter (A/B/C/M/X), or if it is literally "FQ" (since "FQ"
            represents the absence of a flare and isn't a valid lower
            bound to threshold against).

        Examples
        --------
        >>> GoesClass.parse_threshold("M")
        ('rank', 4)
        >>> GoesClass.parse_threshold("M1.5")
        ('flux', 1.5000000000000002e-05)  # note: float imprecision from 1e-5 * 1.5
        """
        bl_value = bl_value.strip()
        letter = bl_value[0].upper()
        if letter not in GoesClass.ORDER or letter == "FQ":
            raise ValueError(f"Invalid binary-label threshold: '{bl_value}'")
        if len(bl_value) == 1:
            # Bare letter -> compare by rank ("this letter or stronger").
            return "rank", GoesClass.rank(letter)
        # Letter + number -> compare by exact flux value.
        return "flux", GoesClass.to_flux(bl_value)


class EventData:
    """
    Wraps a CSV catalog of known solar flare events and provides fast
    lookups from (date, time) -> event name, and from event name -> GOES
    class.

    Expected CSV columns
    ---------------------
    - "Date"       : event date, formatted as e.g. "2014/01/12" (slashes
                      are stripped internally for lookup purposes).
    - "Start"      : event start time, formatted as e.g. "15:30:00"
                      (colons are stripped internally for lookup purposes).
    - "EName"      : a unique event name/identifier string.
    - "GOES Class" : the GOES class string for that event (e.g. "M2.5").

    Other columns may be present in the CSV but are not used by this class.
    """

    def __init__(self, csv_path: str):
        """
        Load the event catalog from disk and build internal lookup tables.

        Parameters
        ----------
        csv_path : str
            Path to the events CSV file (must contain at least the
            "Date", "Start", "EName", and "GOES Class" columns).
        """
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)
        # Maps (date_digits, time_digits) -> EName, for matching image
        # filenames (which encode timestamps) directly to events.
        self._datetime_lookup = self._build_datetime_lookup()
        # Maps EName -> GOES Class, for resolving a matched event's class.
        self._ename_to_goes = dict(zip(self.df["EName"], self.df["GOES Class"]))

    def _build_datetime_lookup(self) -> dict[tuple[str, str], str]:
        """
        Build a dict keyed by (date_part, time_part) -> EName, where both
        parts have had their separators ("/" and ":") removed so they can
        be matched directly against the digit-only date/time strings
        parsed out of image filenames (e.g. "20140112", "153000").

        Returns
        -------
        dict[tuple[str, str], str]
            Lookup table from a (compact date, compact time) pair to the
            event name (`EName`) that started at that date and time.
            If the CSV has duplicate (Date, Start) pairs, the later row
            in the CSV silently overwrites the earlier one in this dict.
        """
        lookup = {}
        for _, row in self.df.iterrows():
            date_key = row["Date"].replace("/", "")
            time_key = row["Start"].replace(":", "")
            lookup[(date_key, time_key)] = row["EName"]
        return lookup

    def lookup_event(self, date_part: str, time_part: str) -> str:
        """
        Look up the event name starting at a given (date, time).

        Parameters
        ----------
        date_part : str
            Compact date digits, e.g. "20140112" (no separators).
        time_part : str
            Compact time digits, e.g. "153000" (no separators).

        Returns
        -------
        str
            The matching `EName` if an event started at exactly this
            date/time, otherwise the literal string "FQ" (meaning: no
            known event at this timestamp, i.e. flare-quiet).
        """
        return self._datetime_lookup.get((date_part, time_part), "FQ")

    def goes_class_for(self, ename: str) -> str:
        """
        Resolve an event name to its GOES class string.

        Parameters
        ----------
        ename : str
            An event name as found in the "EName" column, or the literal
            string "FQ" to explicitly request the flare-quiet class.

        Returns
        -------
        str
            The GOES class associated with `ename`. Returns "FQ" if
            `ename` is "FQ", if `ename` isn't found in the catalog, or if
            the catalog's "GOES Class" value for that event is missing/
            falsy (e.g. NaN from a blank CSV cell).
        """
        if ename == "FQ":
            return "FQ"
        return self._ename_to_goes.get(ename, "FQ") or "FQ"


class TimestampSeries:
    """
    Wraps an ordered list of timestamped image filenames, read from a plain
    text file (one filename per line), and parses each filename's
    timestamp.

    Expected filename format: "YYYYMMDD_HHMMSS.jpg" (or any extension —
    only the part before the first "." is parsed as the timestamp).
    """

    def __init__(self, path: str):
        """
        Load filenames and parse their timestamps from a text file.

        Parameters
        ----------
        path : str
            Path to a text file containing one image filename per line,
            e.g.:
                20140112_000000.jpg
                20140112_001500.jpg
                ...
            Blank lines are skipped. Lines are not sorted; `filenames`
            and `datetimes` preserve the order they appear in the file,
            so for correct window-building behavior the file is expected
            to already be in chronological order.

        Attributes
        ----------
        path : str
            The path that was loaded from.
        filenames : list[str]
            Filenames in file order (whitespace-stripped), e.g.
            "20140112_000000.jpg".
        datetimes : list[datetime]
            Parsed `datetime` objects, parallel to `filenames` (same
            index refers to the same image).
        """
        self.path = path
        self.filenames: list[str] = []
        self.datetimes: list[datetime] = []
        self._load(path)

    def _load(self, path: str):
        """
        Read `path` line by line, populating `self.filenames` and
        `self.datetimes`. Each filename's timestamp is parsed from the
        portion before its first "." using the format "%Y%m%d_%H%M%S".
        """
        with open(path) as f:
            for line in f:
                name = line.strip()
                if not name:
                    continue
                self.filenames.append(name)
                # Strip the file extension (everything from the first ".")
                # before parsing, e.g. "20140112_000000.jpg" -> "20140112_000000".
                stem = name.split(".")[0]
                self.datetimes.append(datetime.strptime(stem, "%Y%m%d_%H%M%S"))

    def __len__(self):
        """Return the number of timestamped filenames loaded."""
        return len(self.datetimes)

    def closest(self, target: datetime) -> datetime:
        """
        Find the datetime in this series closest to `target`.

        Parameters
        ----------
        target : datetime
            The time to search around. Does not need to exist exactly in
            `self.datetimes`.

        Returns
        -------
        datetime
            The single entry of `self.datetimes` with the smallest
            absolute time difference from `target`. Ties are broken by
            whichever candidate is encountered first in list order.

        Notes
        -----
        This performs a linear scan (O(n)) over all datetimes every call;
        for very large series called many times (as in
        `ObservationWindowBuilder.build` and `ForecastTableBuilder.build`)
        this can become a performance bottleneck.
        """
        return min(self.datetimes, key=lambda t: abs(t - target))

    def in_range(self, start: datetime, end: datetime, inclusive_start: bool = False) -> list[datetime]:
        """
        Return all datetimes in this series falling within [start, end].

        Parameters
        ----------
        start : datetime
            Start of the range.
        end : datetime
            End of the range (always inclusive).
        inclusive_start : bool, default False
            If True, `start` itself is included in the range (closed
            interval `[start, end]`). If False (the default), `start` is
            excluded (half-open interval `(start, end]`) — this is the
            behavior used by `ForecastTableBuilder` to ensure a prediction
            window doesn't re-include the boundary timestamp already
            covered by the observation window.

        Returns
        -------
        list[datetime]
            Matching datetimes, in their original series order.
        """
        if inclusive_start:
            return [dt for dt in self.datetimes if start <= dt <= end]
        return [dt for dt in self.datetimes if start < dt <= end]

    def match_to_events(self, events: EventData) -> dict[str, str]:
        """
        Match every filename in this series to a known event, based on the
        timestamp encoded in the filename.

        For each filename, the timestamp is split into its date and time
        components (by splitting the "YYYYMMDD_HHMMSS" stem on "_") and
        looked up directly against `events`' (date, time) catalog — note
        this checks for an *exact* match between the filename's timestamp
        and an event's recorded start time, not a closest/nearest match.

        Parameters
        ----------
        events : EventData
            The event catalog to match against.

        Returns
        -------
        dict[str, str]
            A dict mapping each filename to either:
              - the `EName` of the event that started at exactly that
                filename's timestamp, or
              - "FQ" if no event started at that exact timestamp, or if
                the filename's stem doesn't split into exactly two
                "_"-separated parts (i.e. isn't in the expected
                "YYYYMMDD_HHMMSS" form).
        """
        result: dict[str, str] = {}
        for filename in self.filenames:
            # Drop only the final extension (rsplit with maxsplit=1), then
            # split the remaining "YYYYMMDD_HHMMSS" stem into its two parts.
            stem = filename.rsplit(".", 1)[0]
            parts = stem.split("_")
            if len(parts) == 2:
                date_part, time_part = parts
                result[filename] = events.lookup_event(date_part, time_part)
            else:
                result[filename] = "FQ"
        return result


class ObservationWindowBuilder:
    """
    Builds fixed-duration sliding windows of timestamps over a
    `TimestampSeries`, for use as model input sequences (e.g. "every
    window is N hours of images, sampled every C minutes").
    """

    def __init__(self, timestamps: TimestampSeries):
        """
        Parameters
        ----------
        timestamps : TimestampSeries
            The chronologically-ordered series of available image
            timestamps to slide windows across.
        """
        self.timestamps = timestamps

    def build(
        self,
        start_time: str,
        hours: int,
        cadence: int,
        sliding_window: int = None,
        end_time: str = None,
    ) -> list[list[datetime]]:
        """
        Build a list of sliding observation windows.

        Each window spans `hours` hours, starting at some `iter_start`
        timestamp, and is internally sampled every `cadence` minutes
        (snapped to the closest available timestamp in `self.timestamps`
        for each sample point). The window's start position then advances
        by `sliding_window` minutes (or by `cadence` minutes if
        `sliding_window` isn't given) and the process repeats, ending once
        a full window would extend past `end_time` or past the last
        available timestamp.

        Parameters
        ----------
        start_time : str
            Timestamp string for the first window's start, formatted as
            "%Y%m%d_%H%M%S" (e.g. "20140112_000000"). Must exactly match
            one of the datetimes in `self.timestamps` (see Returns/Notes
            below for what happens if it doesn't).
        hours : int
            Duration of each observation window, in hours.
        cadence : int
            Minutes between consecutive samples *within* a single window
            (e.g. cadence=15 means each window contains one sample every
            15 minutes across its `hours`-hour span).
        sliding_window : int, optional
            Minutes to advance the window start by, between successive
            windows (the "stride"). If omitted, defaults to `cadence`
            minutes — i.e. each window's start advances at the same rate
            as the in-window sampling cadence.
        end_time : str, optional
            Timestamp string (same format as `start_time`) marking the
            last point any window's sampling is allowed to reach. Must be
            given if and only if `sliding_window` is given (see Notes).

        Returns
        -------
        list[list[datetime]] or None
            A list of windows, where each window is itself a list of
            `datetime` objects (the closest available timestamp to each
            sample point within that window). Returns `None` (implicitly,
            via a bare `return` after a `print`) in three error cases:
              1. `start_time` does not exactly match any timestamp in
                 `self.timestamps`.
              2. Exactly one of `sliding_window` / `end_time` was provided
                 (they must both be provided, or both omitted).
              3. `end_time` does not exactly match any timestamp in
                 `self.timestamps`.
            Note that `end_time` is required for this method to do
            anything useful: if both `sliding_window` and `end_time` are
            omitted, `end_dt` is computed from `None`, which raises a
            `TypeError` inside `datetime.strptime` rather than returning
            cleanly — in practice, `end_time` should always be supplied.

        Notes
        -----
        - If `start_dt + hours_td > end_dt` (i.e. even the very first
          window wouldn't fit before `end_time`), a warning is printed
          ("observation window bigger than end_time") but window building
          proceeds anyway — the `while` loop condition below will then
          simply produce zero windows.
        - Within a window, each sample point `t` (starting at the window's
          start and stepping by `cadence_td` until `t > iter_start + hours_td`)
          is mapped to its closest actual timestamp via
          `self.timestamps.closest(t)` — this is a *nearest neighbor*
          match, not an exact one, so it will always return some
          timestamp even if no image exists exactly at `t`.
        - The window list as a whole stops growing once advancing the
          window start any further would make the window's span exceed
          either `end_time` or the last available timestamp in the series.
        """
        start_dt = datetime.strptime(start_time, "%Y%m%d_%H%M%S")
        end_dt = datetime.strptime(end_time, "%Y%m%d_%H%M%S")
        hours_td = timedelta(hours=hours)
        cadence_td = timedelta(minutes=cadence)
        # If no explicit stride is given, advance windows by the same
        # amount as the in-window sampling cadence.
        slide_td = timedelta(minutes=sliding_window) if sliding_window is not None else cadence_td

        if start_dt not in self.timestamps.datetimes:
            print("start_time not found in file list")
            return

        # sliding_window and end_time are a package deal: either both are
        # supplied or neither is.
        if (sliding_window is None) != (end_time is None):
            print("error, both sliding_window and end_time must have values")
            return

        if end_dt not in self.timestamps.datetimes:
            print("out of range error")
            return

        if start_dt + hours_td > end_dt:
            # Non-fatal warning: the very first window already doesn't
            # fit. Execution continues, but the loop below will produce
            # no windows in this case.
            print("observation window bigger than end_time")

        windows = []
        iter_start = start_dt
        last_dt = self.timestamps.datetimes[-1]

        # Keep producing windows as long as the *next* window's full span
        # still fits both before end_time and before the last available
        # timestamp in the series.
        while iter_start + hours_td <= end_dt and iter_start + hours_td <= last_dt:
            window = []
            t = iter_start
            # Sample every `cadence` minutes across the window's span,
            # snapping each sample point to its nearest available image.
            while t <= iter_start + hours_td:
                window.append(self.timestamps.closest(t))
                t += cadence_td
            windows.append(window)
            # Advance the window's start position for the next iteration.
            iter_start += slide_td

        return windows


class FullDiskLabeler:
    """
    Labels pre-built observation windows (as produced by
    `ObservationWindowBuilder.build`) with the strongest flare activity
    that occurred within each window, in one or more requested formats
    (GOES class string, raw flux value, and/or a thresholded binary
    label).
    """

    def __init__(self, events: EventData):
        """
        Parameters
        ----------
        events : EventData
            Event catalog used to resolve matched event names to GOES
            classes.
        """
        self.events = events

    def label(
        self,
        windows: list[list[datetime]],
        event_match: dict[str, str],
        evals: list[str] = None,
    ) -> pd.DataFrame:
        """
        Compute labels for each window and assemble them into a DataFrame.

        Parameters
        ----------
        windows : list[list[datetime]]
            Windows of timestamps to label, typically produced by
            `ObservationWindowBuilder.build`. Each inner list is converted
            to filenames via `"%Y%m%d_%H%M%S.jpg"` formatting before being
            looked up in `event_match`.
        event_match : dict[str, str]
            Mapping from image filename -> event name (`EName`), typically
            produced by `TimestampSeries.match_to_events`. Filenames not
            present in this dict are treated as "FQ" (no event).
        evals : list[str], optional
            Case-insensitive list of output columns/options to compute.
            Recognized values (others are silently ignored):
              - "goes-class" or "gc"  -> include a "GOES Class" column
                with each window's strongest GOES class string.
              - "flux" or "fx"        -> include a "Flux" column with the
                numeric flux (W/m^2) of each window's strongest class.
              - "bl=<threshold>"      -> include a "Binary Label" column.
                `<threshold>` is parsed by `GoesClass.parse_threshold`:
                  * a bare letter (e.g. "bl=M") thresholds by rank
                    ("M-class or stronger" counts as positive (1),
                    regardless of magnitude);
                  * a full class (e.g. "bl=M1.5") thresholds by exact flux
                    value (the window's peak flux must be >= the flux of
                    M1.5 to count as positive).
                Only the *first* "bl="-prefixed entry in `evals` is used;
                any additional ones are ignored.
            If `evals` is omitted or empty, the resulting DataFrame will
            contain only the "Window" column (i.e. no labels at all).

        Returns
        -------
        pandas.DataFrame
            One row per window, with columns:
              - "Window": list of filenames (strings) in that window,
                always present.
              - "GOES Class": present only if "goes-class"/"gc" was
                requested in `evals`.
              - "Flux": present only if "flux"/"fx" was requested.
              - "Binary Label": present only if a "bl=..." entry was
                found in `evals`.
            Column order is always Window, GOES Class, Flux, Binary Label
            (skipping any that weren't requested).

        Notes
        -----
        For each window, every timestamp in it is converted to a filename
        and looked up in `event_match` to find the GOES class active at
        that moment (or "FQ" if unmatched/no event). The window's overall
        label is then the *strongest* class among all of its timestamps
        (via `GoesClass.max_class`), i.e. a window is labeled by its worst
        (most energetic) moment, not an average.
        """
        # Normalize all eval options to lowercase, stripped strings for
        # case-insensitive matching below.
        evals = [e.strip().lower() for e in evals] if evals else []

        include_goes = any(e in ("goes-class", "gc") for e in evals)
        include_flux = any(e in ("flux", "fx") for e in evals)

        bl_mode = None
        bl_threshold = None
        for e in evals:
            if e.startswith("bl="):
                # Only the first "bl=" entry is honored; the threshold
                # text after "bl=" is parsed into a (mode, value) pair.
                bl_mode, bl_threshold = GoesClass.parse_threshold(e[3:])
                break

        rows = []
        for window in windows:
            # Convert each timestamp in the window back into the filename
            # format used as keys in `event_match`.
            filenames = [dt.strftime("%Y%m%d_%H%M%S") + ".jpg" for dt in window]

            flare_classes = []
            for filename in filenames:
                ename = event_match.get(filename, "FQ")
                flare_classes.append(self.events.goes_class_for(ename))

            # The window's label is the single strongest flare class
            # observed at any timestamp within it.
            max_class = GoesClass.max_class(flare_classes)

            row = {"Window": filenames}

            if include_goes:
                row["GOES Class"] = max_class

            if include_flux:
                row["Flux"] = GoesClass.to_flux(max_class)

            if bl_mode is not None:
                if bl_mode == "rank":
                    # "Letter or stronger" thresholding.
                    row["Binary Label"] = int(GoesClass.rank(max_class) >= bl_threshold)
                else:  # flux
                    # Exact-magnitude thresholding.
                    row["Binary Label"] = int(GoesClass.to_flux(max_class) >= bl_threshold)

            rows.append(row)

        # Build the column list in a fixed, predictable order, including
        # only the columns that were actually requested.
        cols = ["Window"]
        if include_goes:
            cols.append("GOES Class")
        if include_flux:
            cols.append("Flux")
        if bl_mode:
            cols.append("Binary Label")

        return pd.DataFrame(rows, columns=cols)


class ForecastTableBuilder:
    """
    Builds (observation window, prediction window) row pairs suitable for
    training a flare-forecasting model, with an optional time gap between
    the two windows to prevent label leakage (i.e. to ensure the model
    cannot "see" the very beginning of the event it's meant to predict).

    Unlike `ObservationWindowBuilder` + `FullDiskLabeler` (which build
    independent, non-overlapping-by-construction labeled windows),
    `ForecastTableBuilder` is centered on *every* timestamp in the series:
    for each one, it looks backward to assemble the observation window and
    forward (after skipping a gap) to assemble the prediction window whose
    peak activity becomes that row's label.
    """

    def __init__(self, timestamps: TimestampSeries, events: EventData):
        """
        Parameters
        ----------
        timestamps : TimestampSeries
            Chronologically-ordered series of available image timestamps.
        events : EventData
            Event catalog used to resolve matched event names to GOES
            classes for prediction-window labeling.
        """
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
        Build the full forecast table, one row per timestamp in the
        series (or per the first `limit` timestamps, if given).

        For each timestamp `current_dt` in `self.timestamps.datetimes`:

        1. **Observation window** (look-back): starting at
           `current_dt - obs_minutes` and stepping forward every
           `cadence_minutes` up to and including `current_dt`, each step
           is snapped to its closest real timestamp via
           `self.timestamps.closest`. Duplicate timestamps (which can
           happen if multiple nearby steps snap to the same closest real
           timestamp) are skipped so each observation window has no
           repeated entries.
        2. **Prediction window** (look-ahead): starts at
           `current_dt + separation_minutes` (skipping the separation gap)
           and includes every real timestamp up to
           `current_dt + separation_minutes + pred_minutes`, using
           `TimestampSeries.in_range` with its default `inclusive_start`
           of `False` — so the boundary timestamp at exactly
           `pred_start` is *excluded* and `current_dt` itself is never
           reused as part of the prediction window (preventing leakage of
           the observation window's own endpoint into the label).
        3. **Label**: the strongest GOES class among all events matched to
           filenames in the prediction window (via `labeled`), using
           `GoesClass.max_class`. If the prediction window ends up empty
           (e.g. it's a tail-end timestamp near the end of the series),
           the label defaults to "FQ".

        Parameters
        ----------
        obs_minutes : int
            How far back (in minutes) the observation window looks,
            relative to each row's reference timestamp.
        pred_minutes : int
            Duration (in minutes) of the forward-looking prediction
            window, measured from `pred_start` (see `separation_minutes`).
        cadence_minutes : int
            Spacing (in minutes) between sampled points within the
            observation window.
        labeled : dict[str, str]
            Mapping from image filename -> event name (`EName`), typically
            produced by `TimestampSeries.match_to_events`. Used to resolve
            each prediction-window timestamp to its matched event (and
            then to a GOES class). Filenames not found default to "FQ".
        separation_minutes : int, default 0
            Size of the gap (in minutes) inserted between the reference
            timestamp and the start of the prediction window. Use this to
            ensure the model is forecasting genuinely *future* activity,
            not activity that overlaps with or immediately follows the
            observation window. A value of 0 means the prediction window
            starts immediately after the reference timestamp (since
            `in_range`'s default exclusive start still excludes the
            reference timestamp itself).
        limit : int, optional
            If given, only the first `limit` timestamps in the series are
            used as reference points (useful for quick testing on a
            subset rather than the full series). If omitted, every
            timestamp in the series gets a row.

        Returns
        -------
        pandas.DataFrame
            One row per reference timestamp, with columns:
              - "Observation Window": list of `datetime` objects making up
                the look-back window (deduplicated, in chronological
                order, always including the reference timestamp itself as
                the last entry if `cadence_minutes` divides evenly, or the
                closest match to it otherwise).
              - "Prediction Window": list of `datetime` objects making up
                the look-ahead window (may be empty).
              - "Label": the strongest GOES class string found anywhere in
                the prediction window, or "FQ" if the prediction window is
                empty or contains no matched events.

        Notes
        -----
        - This method does not check for `obs_minutes`, `pred_minutes`, or
          `cadence_minutes` being negative, zero, or otherwise invalid;
          such values will produce degenerate (possibly empty or
          single-element) windows rather than raising an error.
        - Because `closest()` performs nearest-neighbor snapping rather
          than exact matching, the observation window may include
          timestamps from outside the literal `[current_dt - obs_minutes,
          current_dt]` range if the series has gaps larger than
          `cadence_minutes` near the edges of that range.
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
                # Avoid duplicate entries when consecutive sample points
                # snap to the same nearest real timestamp.
                if closest not in obs_window:
                    obs_window.append(closest)
                t += cadence_td

            # --- Prediction window (skip separation gap, then look forward N minutes) ---
            pred_start = current_dt + sep_td
            # inclusive_start=False (the default) ensures pred_start
            # itself is excluded, so the prediction window never overlaps
            # the timestamp it's offset from.
            pred_window = self.timestamps.in_range(pred_start, pred_start + pred_td)

            # --- Label: max GOES class in prediction window ---
            flare_classes = []
            for dt in pred_window:
                filename = dt.strftime("%Y%m%d_%H%M%S") + ".jpg"
                ename = labeled.get(filename, "FQ")
                flare_classes.append(self.events.goes_class_for(ename))

            # Default to "FQ" if the prediction window is empty (e.g. near
            # the very end of the series), since GoesClass.max_class
            # cannot operate on an empty list.
            label = GoesClass.max_class(flare_classes) if flare_classes else "FQ"

            rows.append({
                "Observation Window": obs_window,
                "Prediction Window": pred_window,
                "Label": label,
            })

        return pd.DataFrame(rows, columns=["Observation Window", "Prediction Window", "Label"])