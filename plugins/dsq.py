EVENT_ID_MAP = {
    0x00: "note",
    0x01: "note",
    0x02: "note",
    0x03: "note",
    0x04: "note",
    0x05: "note",
    0x06: "note",
    0x07: "measure",
    0x08: "beat",
    0x09: "endpos",
    0x0a: "endpos",
    0x0b: "endnotes",
    0x0c: "endpos",

    # Just how many of these are they, and what are they for?
    0x18: "unk8",
    0x19: "unk9",
    0x1a: "unk10",
    0x1b: "unk11",
    0x1c: "unk12",
    0x1d: "unk13",
    0x1e: "unk14",
    0x1f: "unk1",
    0x20: "unk2",
    0x21: "unk3",
    0x22: "unk4",
    0x23: "unk5",
    0x24: "unk6",
    0x25: "unk7",
}

EVENT_ID_REVERSE = {EVENT_ID_MAP[k]: k for k in EVENT_ID_MAP}

NOTE_MAPPING = {
    'drum': {
        0x00: "hihat",
        0x01: "snare",
        0x02: "bass",
        0x03: "hightom",
        0x04: "lowtom",
        0x05: "rightcymbal",
        0x06: "auto",
    },
}

REVERSE_NOTE_MAPPING = {
    # Drum
    "hihat": 0x00,
    "snare": 0x01,
    "bass": 0x02,
    "hightom": 0x03,
    "lowtom": 0x04,
    "rightcymbal": 0x05,
    "auto": 0x06,
}


def get_class():
    return None
