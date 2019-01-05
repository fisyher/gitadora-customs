import collections
import copy
import json
import os
import shutil
import struct
import threading
from lxml import etree
from lxml.builder import E
import uuid

import helper
import mdb
import eamxml
import audio
import vas3tool
import wavbintool
import tmpfile

import plugins.wav as wav

USE_THREADS = True

EVENT_ID_MAP = {
    0x00: "note",
    0x10: "measure",
    0x20: "note",
    0x40: "note",
    0x60: "note",
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


def add_song_info(charts, music_id, music_db):
    song_info = None

    if music_db and music_db.endswith(".csv") or not music_db:
        song_info = mdb.get_song_info_from_csv(music_db if music_db else "gitadora_music.csv", music_id)

    if song_info is None or music_db and music_db.endswith(".xml") or not music_db:
        song_info = mdb.get_song_info_from_mdb(music_db if music_db else "mdb_xg.xml", music_id)

    for chart_idx in range(len(charts)):
        chart = charts[chart_idx]

        if not song_info:
            continue

        game_type = ["drum", "guitar", "bass", "open"][chart['header']['game_type']]

        if 'title' in song_info:
            charts[chart_idx]['header']['title'] = song_info['title']

        if 'artist' in song_info:
            charts[chart_idx]['header']['artist'] = song_info['artist']

        if 'classics_difficulty' in song_info:
            diff_idx = (chart['header']['game_type'] * 4) + chart['header']['difficulty']

            if diff_idx < len(song_info['classics_difficulty']):
                difficulty = song_info['classics_difficulty'][diff_idx]
            else:
                difficulty = 0

            charts[chart_idx]['header']['level'] = {
                game_type: difficulty * 10
            }

        if 'bpm' in song_info:
            charts[chart_idx]['header']['bpm'] = song_info['bpm']

        if 'bpm2' in song_info:
            charts[chart_idx]['header']['bpm2'] = song_info['bpm2']

    return charts


def filter_charts(charts, params):
    filtered_charts = []

    for chart in charts:
        if chart['header']['is_metadata'] != 0:
            continue

        part = ["drum", "guitar", "bass", "open"][chart['header']['game_type']]
        has_all = 'all' in params['parts']
        has_part = part in params['parts']
        if not has_all and not has_part:
            filtered_charts.append(chart)
            continue

        diff = ['nov', 'bsc', 'adv', 'ext', 'mst'][chart['header']['difficulty']]
        has_min = 'min' in params['difficulty']
        has_max = 'max' in params['difficulty']
        has_all = 'all' in params['difficulty']
        has_diff = diff in params['difficulty']

        if not has_min and not has_max and not has_all and not has_diff:
            filtered_charts.append(chart)
            continue

    for chart in filtered_charts:
        charts.remove(chart)

    return charts


def split_charts_by_parts(charts):
    guitar_charts = []
    bass_charts = []
    open_charts = []

    for chart in charts:
        if chart['header']['is_metadata'] != 0:
            continue

        game_type = ["drum", "guitar", "bass", "open"][chart['header']['game_type']]
        if game_type == "guitar":
            guitar_charts.append(chart)
        elif game_type == "bass":
            bass_charts.append(chart)
        elif game_type == "open":
            open_charts.append(chart)

    # Remove charts from chart list
    for chart in guitar_charts:
        charts.remove(chart)

    for chart in bass_charts:
        charts.remove(chart)

    for chart in open_charts:
        charts.remove(chart)

    return charts, guitar_charts, bass_charts, open_charts


def combine_guitar_charts(guitar_charts, bass_charts):
    # Combine guitar and bass charts
    parsed_bass_charts = []

    for chart in guitar_charts:
        # Find equivalent chart
        for chart2 in bass_charts:
            if chart['header']['difficulty'] != chart2['header']['difficulty']:
                continue

            if 'level' in chart2['header']:
                if 'level' not in chart['header']:
                    chart['header']['level'] = {}

                for k in chart2['header']['level']:
                    chart['header']['level'][k] = chart2['header']['level'][k]

                for event in chart2['timestamp'][timestamp_key]:
                    if event['name'] != "note":
                        continue

                    if timestamp_key not in chart['timestamp']:
                        chart['timestamp'][timestamp_key] = []

                    chart['timestamp'][timestamp_key].append(event)

            parsed_bass_charts.append(chart2)

    for chart in parsed_bass_charts:
        bass_charts.remove(chart)

    return guitar_charts, bass_charts


def add_note_durations(chart, sound_metadata):
    duration_lookup = {}

    if not sound_metadata or 'entries' not in sound_metadata:
        return chart

    for entry in sound_metadata['entries']:
        duration_lookup[entry['sound_id']] = entry.get('duration', 0)

    for k in chart['timestamp']:
        for i in range(0, len(chart['timestamp'][k])):
            if chart['timestamp'][k][i]['name'] in ['note', 'auto']:
                chart['timestamp'][k][i]['data']['note_length'] = int(round(duration_lookup.get(chart['timestamp'][k][i]['data']['sound_id'], 0) * 300))

    return chart


def get_start_timestamp(chart):
    for timestamp_key in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        for beat in chart['timestamp'][timestamp_key]:
            if beat['name'] in ["startpos"]:
                return timestamp_key

    return sorted(chart['timestamp'].keys(), key=lambda x: int(x))[0]


def get_end_timestamp(chart):
    for timestamp_key in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        for beat in chart['timestamp'][timestamp_key]:
            if beat['name'] in ["endpos"]:
                return timestamp_key

    return sorted(chart['timestamp'].keys(), key=lambda x: int(x))[-1]


def generate_bpm_events(chart):
    bpms = []

    keys_sorted = sorted(chart['timestamp'].keys(), key=lambda x: int(x))
    last_bpm = 0

    for idx, timestamp_key in enumerate(keys_sorted[1:]):
        if timestamp_key == 0xffffffff:
            break

        cur_bpm = round(((300 / 4) / ((timestamp_key - keys_sorted[idx]) / 4)) * 240) # I came up with these numbers by plotting the BPM and first measure timestamp and finding the values that resulted in the least error over the entire dataset

        if cur_bpm != last_bpm:
            chart['timestamp'][keys_sorted[idx]].append({
                "data": {
                    "bpm": cur_bpm
                },
                "name": "bpm"
            })

            last_bpm = cur_bpm

    return chart


def generate_metadata(chart):
    chart = generate_bpm_events(chart)

    keys_sorted = sorted(chart['timestamp'].keys(), key=lambda x: int(x))

    chart['timestamp'][keys_sorted[0]].append({
        "data": {
            "numerator": 4,
            "denominator": 4,
        },
        "name": "barinfo"
    })

    chart['timestamp'][keys_sorted[0]].append({
        "name": "baron",
        "data": {}
    })

    chart['timestamp'][keys_sorted[0]].append({
        "name": "startpos",
        "data": {}
    })

    chart['timestamp'][keys_sorted[-1]].append({
        "name": "endpos",
        "data": {}
    })

    return chart


def generate_notes_metadata(chart):
    keys_sorted = sorted(chart['timestamp'].keys(), key=lambda x: int(x))

    chart['timestamp'][keys_sorted[0]].append({
        "name": "chipstart",
        "data": {}
    })

    return chart


########################
#   GSQ parsing code   #
########################
def parse_event_block(mdata, game, difficulty, is_metadata=False):
    packet_data = {}

    timestamp, param1, param2, cmd = struct.unpack("<HHHH", mdata[0:8])
    orig_cmd = cmd
    param3 = cmd & 0xff0f
    cmd &= 0x00f0

    if timestamp == 0xffff:
        timestamp = 0xffffffff
    else:
        timestamp *= 4

    if is_metadata and cmd not in [0x10]:
        return None

    if not is_metadata and cmd in [0x10]:
        return None

    game_type_id = {"drum": 0, "guitar": 1, "bass": 2, "open": 3}[game]

    event_name = EVENT_ID_MAP[cmd]

    if cmd in [0x00, 0x20, 0x40, 0x60]:
        packet_data['sound_id'] = param1
        packet_data['volume'] = 127

        if (cmd & 0x40) != 0:
            packet_data['note'] = NOTE_MAPPING[game][0x10] # open note
            packet_data['auto_unk'] = param3
        else:
            packet_data['note'] = NOTE_MAPPING[game][param3 & 0x0f] # note

        if packet_data['note'] == "auto":
            packet_data['auto_volume'] = 1
            packet_data['auto_note'] = 1

        is_wail = (cmd & 0x20) != 0
        packet_data['wail_misc'] = 1 if is_wail else 0
        packet_data['guitar_special'] = 1 if is_wail else 0

    elif cmd not in [0x10]:
        print("Unknown command %04x %02x" % (timestamp, cmd))
        exit(1)

    return {
        "name": event_name,
        'timestamp': timestamp,
        "data": packet_data
    }


def read_gsq2_data(data, game_type, difficulty, is_metadata):
    output = {
        "beat_data": []
    }

    if data is None:
        return None

    unk_sys = 0
    time_division = 300
    beat_division = 480

    output['header'] = {
        "unk_sys": unk_sys,
        "difficulty": difficulty,
        "is_metadata": is_metadata,
        "game_type": game_type,
        "time_division": time_division,
        "beat_division": beat_division,
    }

    header_size = 0
    entry_size = 0x08
    entry_count = len(data) // entry_size

    for i in range(entry_count):
        mdata = data[header_size + (i * entry_size):header_size + (i * entry_size) + entry_size]
        part = ["drum", "guitar", "bass", "open"][game_type]
        parsed_data = parse_event_block(mdata, part, difficulty, is_metadata=is_metadata)

        if parsed_data:
            output['beat_data'].append(parsed_data)

    return output


def convert_to_timestamp_chart(chart):
    chart['timestamp'] = collections.OrderedDict()

    for x in sorted(chart['beat_data'], key=lambda x: int(x['timestamp'])):
        if x['timestamp'] not in chart['timestamp']:
            chart['timestamp'][x['timestamp']] = []

        beat = x['timestamp']
        del x['timestamp']

        chart['timestamp'][beat].append(x)

    del chart['beat_data']

    return chart


def parse_chart_intermediate(chart, game_type, difficulty, is_metadata):
    chart_raw = read_gsq2_data(chart, game_type, difficulty, is_metadata)

    if not chart_raw:
        return None

    chart_raw = convert_to_timestamp_chart(chart_raw)

    start_timestamp = int(get_start_timestamp(chart_raw))
    end_timestamp = int(get_end_timestamp(chart_raw))

    # Handle events based on beat offset in ascending order
    for timestamp_key in sorted(chart_raw['timestamp'].keys(), key=lambda x: int(x)):
        if int(timestamp_key) < start_timestamp or int(timestamp_key) > end_timestamp:
            del chart_raw['timestamp'][timestamp_key]

    return chart_raw


def generate_json_from_gsq2(params):
    combine_guitars = params['merge_guitars'] if 'merge_guitars' in params else False
    output_data = {}

    def get_data(params, game_type, difficulty, is_metadata):
        part = ["drum", "guitar", "bass", "open"][game_type]
        diff = ['nov', 'bsc', 'adv', 'ext', 'mst'][difficulty]

        if 'input_split' in params and part in params['input_split'] and diff in params['input_split'][part] and params['input_split'][part][diff]:
            data = open(params['input_split'][part][diff], "rb").read()
            return (data, game_type, difficulty, is_metadata)

        return None

    raw_charts = [
        # Guitar
        get_data(params, 1, 0, False),
        get_data(params, 1, 1, False),
        get_data(params, 1, 2, False),
        get_data(params, 1, 3, False),
        get_data(params, 1, 4, False),

        # Bass
        get_data(params, 2, 0, False),
        get_data(params, 2, 1, False),
        get_data(params, 2, 2, False),
        get_data(params, 2, 3, False),
        get_data(params, 2, 4, False),

        # Open
        get_data(params, 3, 0, False),
        get_data(params, 3, 1, False),
        get_data(params, 3, 2, False),
        get_data(params, 3, 3, False),
        get_data(params, 3, 4, False),
    ]
    raw_charts = [x for x in raw_charts if x is not None]

    if len(raw_charts) > 0:
        raw_charts.append((raw_charts[0][0], raw_charts[0][1], raw_charts[0][2], True))

    musicid = -1
    if len(raw_charts) > 0:
        musicid = struct.unpack("<H", raw_charts[0][0][0x04:0x06])[0]

    output_data['musicid'] = musicid
    output_data['format'] = Gsq1Format.get_format_name()

    charts = []
    for chart_info in raw_charts:
        chart, game_type, difficulty, is_metadata = chart_info

        parsed_chart = parse_chart_intermediate(chart, game_type, difficulty, is_metadata)

        if not parsed_chart:
            continue

        game_type = ["drum", "guitar", "bass", "open"][parsed_chart['header']['game_type']]
        if game_type in ["guitar", "bass", "open"]:
            parsed_chart = add_note_durations(parsed_chart, params.get('sound_metadata', []))

        if is_metadata:
            parsed_chart = generate_metadata(parsed_chart)
        else:
            parsed_chart = generate_notes_metadata(parsed_chart)

        charts.append(parsed_chart)
        charts[-1]['header']['musicid'] = musicid

    charts = add_song_info(charts, musicid, params['musicdb'])
    charts = filter_charts(charts, params)
    charts, guitar_charts, bass_charts, open_charts = split_charts_by_parts(charts)

    if combine_guitars:
        guitar_charts, bass_charts = combine_guitar_charts(guitar_charts, bass_charts)

    # Merge all charts back together after filtering, merging guitars etc
    charts += guitar_charts
    charts += bass_charts
    charts += open_charts

    output_data['charts'] = charts

    return json.dumps(output_data, indent=4, sort_keys=True)


class Gsq1Format:
    @staticmethod
    def get_format_name():
        return "Gsq1"

    @staticmethod
    def to_json(params):
        return generate_json_from_gsq2(params)

    @staticmethod
    def to_chart(params):
        super()

    @staticmethod
    def is_format(filename):
        return False


def get_class():
    return Gsq1Format
