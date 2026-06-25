from helio_index.src.helio_index.utils import (
    EventData,
    TimestampSeries,
    ObservationWindowBuilder,
    FullDiskLabeler,
    ForecastTableBuilder,
)
import pprint


# First load Event and TimeStamp data into objects
events = EventData('events.csv')
timestamps = TimestampSeries('files.txt')

# Code that implements TimeStampEventMatchTable (now a method on TimestampSeries)
labeled = timestamps.match_to_events(events)  # Returns a dictionary of each timestamp matched with a corresponding event with matching start time or FQ if not.
# pprint.pprint(labeled)


# Code that implements ObservationWindow (now ObservationWindowBuilder, built once, reused)
# NOTE: hours=0 and cadence=0 will hang forever (zero-length timedelta never advances
# the loop) -- this is a pre-existing bug in the original ObservationWindow, not something
# introduced by this refactor. Using hours=2, cadence=10 here so the demo actually runs.
window_builder = ObservationWindowBuilder(timestamps)
ow = window_builder.build("20251001_001400", 2, 10, 60, "20251001_143600")
pprint.pprint(ow)

# Code that labels each window (FullDiskLabeler is now constructed with EventData, then call .label())
labeler = FullDiskLabeler(events)
wl = labeler.label(
    ow,
    labeled,
    evals=["gc", "fx", "bl=C"]        # GOES class + flux + binary >= M
)
pprint.pprint(wl)

# Code that builds the forecast table (BuildForecastTable -> ForecastTableBuilder)
# forecast_builder = ForecastTableBuilder(timestamps, events)
# bt = forecast_builder.build(240, 480, 60, labeled, 30, 150)  # For every timestamp it goes back specified number of hours to get the observation window and forward to get the prediction window
# print(bt)  # Then it labels the prediction window, for now it takes the max goes_class of all timestamps in the prediction window. it labels the observation window with this label