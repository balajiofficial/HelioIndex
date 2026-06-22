from helio_index.src.helio_index.utils import setEventData, setTimeStampData, TimeStampEventMatchTable, ObservationWindow, WindowLabeler, BuildForecastTable
import pprint


# First set Event and TimeStamp List Data
setEventData('events.csv')
setTimeStampData('files.txt')

# Code that implements TimeStampEventMatchTable

timestamps = []
with open("files.txt") as f:
    for line in f:
        name = line.strip()
        if not name:
            continue
        timestamps.append(name)
labeled = TimeStampEventMatchTable() # Returns a dictionary of each timestamp matched with a corresponding event with matching start time or FQ if not.
# pprint.pprint(labeled)


# Code that implements ObservationWindow
ow = ObservationWindow("20251001_001400", 4, 15, 60, "20251002_001400")
# pprint.pprint(ow)

# Code that Labels each Window
wl = WindowLabeler(
    ow,
    labeled,
    evals=["gc", "fx", "bl=C"]        # GOES class + flux + binary ≥ M
)
pprint.pprint(wl)

# Code that builds PredictionWindow
# bt = BuildForecastTable(240, 480, 60, labeled, 30, 150) # For every timestamp it goes back specified number of hours to get the observation window and forward to get the prediction window
# print(bt) # Then it labels the prediction window, for now it takes the max goes_class of all timestamps in the prediction window. it labels the observation window with this label