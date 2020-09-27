import os

import plugins.sq as sq

EVENT_ID_MAP = {
    0x00: "note",
    0x10: "measure",
    0x20: "note",
    0x40: "note",
    0x60: "note",
    0xa0: "endpos"
}

EVENT_ID_REVERSE = {EVENT_ID_MAP[k]: k for k in EVENT_ID_MAP}

NOTE_MAPPING = {
    'guitar': {
        0x01: "g_rxx",
        0x02: "g_xgx",
        0x03: "g_rgx",
        0x04: "g_xxb",
        0x05: "g_rxb",
        0x06: "g_xgb",
        0x07: "g_rgb",
        0x08: "auto",
        0x10: 'g_open',
    },

    'bass': {
        0x01: "b_rxx",
        0x02: "b_xgx",
        0x03: "b_rgx",
        0x04: "b_xxb",
        0x05: "b_rxb",
        0x06: "b_xgb",
        0x07: "b_rgb",
        0x08: "auto",
        0x10: 'b_open',
    },

    'open': {
        0x01: "g_rxx",
        0x02: "g_xgx",
        0x03: "g_rgx",
        0x04: "g_xxb",
        0x05: "g_rxb",
        0x06: "g_xgb",
        0x07: "g_rgb",
        0x08: "auto",
        0x10: 'g_open',
    },
}

REVERSE_NOTE_MAPPING = {
    "auto": 0x08,

    # Guitar
    "g_rxx": 0x01,
    "g_xgx": 0x02,
    "g_rgx": 0x03,
    "g_xxb": 0x04,
    "g_rxb": 0x05,
    "g_xgb": 0x06,
    "g_rgb": 0x07,
    "g_rxxxx": 0x01,
    "g_xgxxx": 0x02,
    "g_rgxxx": 0x03,
    "g_xxbxx": 0x04,
    "g_rxbxx": 0x05,
    "g_xgbxx": 0x06,
    "g_rgbxx": 0x07,
    "g_open": 0x10,

    # Bass
    "b_rxx": 0x01,
    "b_xgx": 0x02,
    "b_rgx": 0x03,
    "b_xxb": 0x04,
    "b_rxb": 0x05,
    "b_xgb": 0x06,
    "b_rgb": 0x07,
    "b_rxxxx": 0x01,
    "b_xgxxx": 0x02,
    "b_rgxxx": 0x03,
    "b_xxbxx": 0x04,
    "b_rxbxx": 0x05,
    "b_xgbxx": 0x06,
    "b_rgbxx": 0x07,
}


def generate_json_from_data(params, read_data_callback):
    def get_data(params, part_type, difficulty, is_metadata):
        part = ["drum", "guitar", "bass", "open", "guitar1", "guitar2"][part_type]
        diff = ["nov", "bsc", "adv", "ext", "mst"][difficulty]

        if 'input_split' in params and part in params['input_split'] and diff in params['input_split'][part] and params['input_split'][part][diff] and os.path.exists(params['input_split'][part][diff]):
            data = open(params['input_split'][part][diff], "rb").read()
            return (data, part_type, difficulty, is_metadata)

        return None

    raw_charts = [
        # Drum
        get_data(params, 0, 4, False),
        get_data(params, 0, 3, False),
        get_data(params, 0, 2, False),
        get_data(params, 0, 1, False),

        # Guitar
        get_data(params, 1, 4, False),
        get_data(params, 1, 3, False),
        get_data(params, 1, 2, False),
        get_data(params, 1, 1, False),

        # Bass
        get_data(params, 2, 4, False),
        get_data(params, 2, 3, False),
        get_data(params, 2, 2, False),
        get_data(params, 2, 1, False),

        # Open
        get_data(params, 3, 4, False),
        get_data(params, 3, 3, False),
        get_data(params, 3, 2, False),
        get_data(params, 3, 1, False),

        # Guitar 1
        get_data(params, 4, 4, False),
        get_data(params, 4, 3, False),
        get_data(params, 4, 2, False),
        get_data(params, 4, 1, False),

        # Guitar 2
        get_data(params, 5, 4, False),
        get_data(params, 5, 3, False),
        get_data(params, 5, 2, False),
        get_data(params, 5, 1, False),
    ]
    raw_charts = [x for x in raw_charts if x is not None]

    return sq.generate_json_from_data(params, read_data_callback, raw_charts)


def get_class():
    return None
