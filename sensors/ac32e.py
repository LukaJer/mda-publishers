from sensors.envea_analyzer import EnveaAnalyzer


class AC32e(EnveaAnalyzer):
    NAME = "AC32e"

    
    SEPARATOR = ";"
    TIME_INDEX = 0
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    GAS_FIELDS = [(1, "NO", "ppb"), (2, "NO2", "ppb"), (3, "NOx", "ppb")]
    HEADER_MARKERS = ("NO(ppb)", "NOx", "DATE")
    POLL_COMMAND = ""

    # --- Modbus ---
    MODBUS_FIELDS = [
        (1280, "NO", "ppb"),
        (1282, "NOx", "ppb"),
        (1284, "NO2", "ppb"),
    ]
    MODBUS_WORD_SWAP = True
