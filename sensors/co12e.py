from sensors.envea_analyzer import EnveaAnalyzer


class CO12e(EnveaAnalyzer):
    NAME = "CO12e"

    SEPARATOR = ";"
    TIME_INDEX = 0
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    GAS_FIELDS = [(1, "CO", "ppm")]
    HEADER_MARKERS = ("CO(ppm)", "DATE")
    POLL_COMMAND = ""

    # --- Modbus ---
    MODBUS_FIELDS = [
        (778, "CO", "ppm"),
    ]
    MODBUS_WORD_SWAP = True
