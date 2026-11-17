from sensors.envea_analyzer import EnveaAnalyzer


class O342e(EnveaAnalyzer):
    NAME = "O342e"

    SEPARATOR = ";"
    TIME_INDEX = 0
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    GAS_FIELDS = [(1, "O3", "ppb")]
    HEADER_MARKERS = ("O3(ppb)", "DATE")
    POLL_COMMAND = ""

    # --- Modbus ---
    MODBUS_FIELDS = [
        (782, "O3", "ppb"),
    ]
    MODBUS_WORD_SWAP = True
