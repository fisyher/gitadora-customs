import copy
import json
import os
import struct

import eamxml

from lxml import etree
from lxml.builder import E

from plugins.sq import generate_json_from_data

VALID_METACOMMANDS = ['startpos', 'endpos', 'baron', 'baroff', 'measure', 'beat', 'unk0c', 'bpm', 'barinfo']

EVENT_ID_MAP = {
    0x01: "bpm",
    0x02: "barinfo",
    0x03: "baron",
    0x04: "baroff",
    0x05: "measure",
    0x06: "beat",
    0x07: "chipstart",
    0x08: "chipend",
    0x0c: "unk0c", # Almost never used, no idea what it's for. Part of the metadata chart
    0x0e: "startpos",
    0x0f: "endpos",
    0x10: "note",
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
        0x06: "leftcymbal",
        0x07: "floortom",
        0x08: "leftpedal",
        0xff: "auto",
    },
    'guitar': {
        0x00: "g_open",
        0x01: "g_rxxxx",
        0x02: "g_xgxxx",
        0x03: "g_rgxxx",
        0x04: "g_xxbxx",
        0x05: "g_rxbxx",
        0x06: "g_xgbxx",
        0x07: "g_rgbxx",
        0x08: "g_xxxyx",
        0x09: "g_rxxyx",
        0x0a: "g_xgxyx",
        0x0b: "g_rgxyx",
        0x0c: "g_xxbyx",
        0x0d: "g_rxbyx",
        0x0e: "g_xgbyx",
        0x0f: "g_rgbyx",
        0x10: "g_xxxxp",
        0x11: "g_rxxxp",
        0x12: "g_xgxxp",
        0x13: "g_rgxxp",
        0x14: "g_xxbxp",
        0x15: "g_rxbxp",
        0x16: "g_xgbxp",
        0x17: "g_rgbxp",
        0x18: "g_xxxyp",
        0x19: "g_rxxyp",
        0x1a: "g_xgxyp",
        0x1b: "g_rgxyp",
        0x1c: "g_xxbyp",
        0x1d: "g_rxbyp",
        0x1e: "g_xgbyp",
        0x1f: "g_rgbyp",
        0xff: "auto",
    },
    'bass': {
        0x00: "b_open",
        0x01: "b_rxxxx",
        0x02: "b_xgxxx",
        0x03: "b_rgxxx",
        0x04: "b_xxbxx",
        0x05: "b_rxbxx",
        0x06: "b_xgbxx",
        0x07: "b_rgbxx",
        0x08: "b_xxxyx",
        0x09: "b_rxxyx",
        0x0a: "b_xgxyx",
        0x0b: "b_rgxyx",
        0x0c: "b_xxbyx",
        0x0d: "b_rxbyx",
        0x0e: "b_xgbyx",
        0x0f: "b_rgbyx",
        0x10: "b_xxxxp",
        0x11: "b_rxxxp",
        0x12: "b_xgxxp",
        0x13: "b_rgxxp",
        0x14: "b_xxbxp",
        0x15: "b_rxbxp",
        0x16: "b_xgbxp",
        0x17: "b_rgbxp",
        0x18: "b_xxxyp",
        0x19: "b_rxxyp",
        0x1a: "b_xgxyp",
        0x1b: "b_rgxyp",
        0x1c: "b_xxbyp",
        0x1d: "b_rxbyp",
        0x1e: "b_xgbyp",
        0x1f: "b_rgbyp",
        0xff: "auto",
    }
}

REVERSE_NOTE_MAPPING = {
    # Drum
    "hihat": 0x00,
    "snare": 0x01,
    "bass": 0x02,
    "hightom": 0x03,
    "lowtom": 0x04,
    "rightcymbal": 0x05,
    "leftcymbal": 0x06,
    "floortom": 0x07,
    "leftpedal": 0x08,
    "auto": 0xff,

    # Guitar
    "g_open": 0x00,
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
    "g_xxxyx": 0x08,
    "g_rxxyx": 0x09,
    "g_xgxyx": 0x0a,
    "g_rgxyx": 0x0b,
    "g_xxbyx": 0x0c,
    "g_rxbyx": 0x0d,
    "g_xgbyx": 0x0e,
    "g_rgbyx": 0x0f,
    "g_xxxxp": 0x10,
    "g_rxxxp": 0x11,
    "g_xgxxp": 0x12,
    "g_rgxxp": 0x13,
    "g_xxbxp": 0x14,
    "g_rxbxp": 0x15,
    "g_xgbxp": 0x16,
    "g_rgbxp": 0x17,
    "g_xxxyp": 0x18,
    "g_rxxyp": 0x19,
    "g_xgxyp": 0x1a,
    "g_rgxyp": 0x1b,
    "g_xxbyp": 0x1c,
    "g_rxbyp": 0x1d,
    "g_xgbyp": 0x1e,
    "g_rgbyp": 0x1f,

    # Bass
    "b_open": 0x00,
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
    "b_xxxyx": 0x08,
    "b_rxxyx": 0x09,
    "b_xgxyx": 0x0a,
    "b_rgxyx": 0x0b,
    "b_xxbyx": 0x0c,
    "b_rxbyx": 0x0d,
    "b_xgbyx": 0x0e,
    "b_rgbyx": 0x0f,
    "b_xxxxp": 0x10,
    "b_rxxxp": 0x11,
    "b_xgxxp": 0x12,
    "b_rgxxp": 0x13,
    "b_xxbxp": 0x14,
    "b_rxbxp": 0x15,
    "b_xgbxp": 0x16,
    "b_rgbxp": 0x17,
    "b_xxxyp": 0x18,
    "b_rxxyp": 0x19,
    "b_xgxyp": 0x1a,
    "b_rgxyp": 0x1b,
    "b_xxbyp": 0x1c,
    "b_rxbyp": 0x1d,
    "b_xgbyp": 0x1e,
    "b_rgbyp": 0x1f,
}


def create_event_file(params, charts):
    output_folder = params['output']

    # Gather bonus note info
    # Use a dictionary for the first pass because it's
    # easier to handle the data for multiple difficulties
    bonus_notes = {}
    for chart in charts:
        for x in sorted(chart['beat_data'], key=lambda x: int(x['timestamp'])):
            if not (x['name'] == "note" and x['data'].get('bonus_note', 0) == 1):
                continue

            if x['timestamp'] not in bonus_notes:
                bonus_notes[x['timestamp']] = {}

            gamelevel = 1 << chart['header']['difficulty']
            if x['data']['sound_id'] in bonus_notes[x['timestamp']]:
                gamelevel |= bonus_notes[x['timestamp']][x['data']['sound_id']]['gamelevel']

            bonus_notes[x['timestamp']][x['data']['sound_id']] = {
                'sound_id': x['data']['sound_id'],
                'time': x['timestamp'],
                'gamelevel': gamelevel,
            }

    # Convert the dictionary into a flat list
    bonus_notes_flat = []
    for beat in sorted(bonus_notes.keys(), key=lambda x: int(x)):
        for sound_id in bonus_notes[beat]:
            bonus_notes_flat.append(bonus_notes[beat][sound_id])

    # Create XML for bonus notes
    event_xml = E.xg_eventdata(
        E.version("2", __type="u32"),
        E.music(
            E.musicid("{}".format(params['musicid']), __type="u32"),
            E.game(
                E.gametype("2", __type="u32"),  # Bass?
                E.events(
                    E.eventtype("1", __type="u32"),  # ?
                )
            ),
            E.game(
                E.gametype("0", __type="u32"),  # Drum
                E.events(
                    E.eventtype("0", __type="u32"),  # ?
                    *[E.event(
                        E.eventtype("0", __type="u32"),
                        E.value("0", __type="u32"),  # ?
                        E.time("{}".format(x['time']), __type="u32"),
                        E.note("{}".format(x['sound_id']), __type="u32"),
                        E.gamelevel("{}".format(x['gamelevel']), __type="u32"),
                    ) for x in bonus_notes_flat]
                ),
            ),
        ),
    )

    # Write binary XML event file
    event_xml_text = etree.tostring(event_xml, pretty_print=True).decode('utf-8')
    event_xml_filename = os.path.join(output_folder, "event%04d.ev2" % (params['musicid']))

    with open(event_xml_filename, "wb") as f:
        f.write(eamxml.get_binxml(event_xml_text))


def generate_sq3_from_json(params):
    def build_command(event, game_type):
        output = bytearray(0x40)

        output[0x00:0x04] = struct.pack("<I", event['timestamp'])
        output[0x04] = EVENT_ID_REVERSE[event['name']] & 0xff

        if event['name'] == "bpm":
            if event['data']['bpm'] < 1:
                event['data']['bpm'] = 1

            elif event['data']['bpm'] > 60000000:
                event['data']['bpm'] = 60000000

            output[0x34:0x38] = struct.pack("<I", int(round(60000000 / event['data']['bpm'])))

        elif event['name'] == "barinfo":
            output[0x34] = event['data']['numerator'] & 0xff

            denominator = 1 << (event['data']['denominator'].bit_length() - 1)
            if denominator != event['data']['denominator']:
                raise Exception("ERROR: The time signature denominator must be divisible by 2."
                                "Found {}".format(event['data']['denominator']))

            output[0x35] = (event['data']['denominator'].bit_length() - 1) & 0xff

        elif event['name'] == "chipstart":
            if 'unk' in event['data']:
                output[0x14:0x18] = struct.pack("<I", event['data']['unk'])

            else:
                output[0x14:0x18] = struct.pack("<I", 0x16c)

        elif event['name'] == "note":
            if event['data']['note'] not in REVERSE_NOTE_MAPPING:
                # Set all unknown events to auto play
                REVERSE_NOTE_MAPPING[event['data']['note']] = 0xff

            if 'hold_duration' in event['data']:
                output[0x08:0x0c] = struct.pack("<I", event['data']['hold_duration'])

            if 'unk' in event['data']:
                output[0x14:0x18] = struct.pack("<I", event['data']['unk'])

            else:
                output[0x14:0x18] = struct.pack("<I", 0x16c)

            if 'sound_id' in event['data']:
                output[0x20:0x24] = struct.pack("<I", event['data']['sound_id'])

            if game_type != 0:
                if 'note_length' in event['data']:
                    output[0x24:0x28] = struct.pack("<I", event['data']['note_length'])

                else:
                    output[0x24:0x28] = struct.pack("<I", 0x40)

            if 'volume' in event['data']:
                output[0x2d] = event['data']['volume'] & 0xff

            if 'auto_volume' in event['data']:
                output[0x2e] = event['data']['auto_volume'] & 0xff

            if 'note' in event['data']:
                output[0x30] = REVERSE_NOTE_MAPPING[event['data']['note']] & 0xff

            if 'wail_misc' in event['data']:
                output[0x31] = event['data']['wail_misc'] & 0xff

            if 'guitar_special' in event['data']:
                output[0x32] = event['data']['guitar_special'] & 0xff

            if 'auto_note' in event['data']:
                output[0x34] = event['data']['auto_note'] & 0xff

            if event['data'].get('note') == "auto":
                output[0x34] = 1  # Auto note
                output[0x2e] = 1  # Auto volume

        return output


    def contains_command(chart, command):
        for event in chart:
            if event['name'] == command:
                return True

        return False


    def calculate_last_measure_duration(chart):
        measure_timestamps = []

        for event in chart:
            if event['name'] == "measure":
                measure_timestamps.append(event['timestamp'])

        if len(measure_timestamps) < 2:
            return 0x100

        return measure_timestamps[-1] - measure_timestamps[-2]


    def create_final_sq3_chart(params, charts_data):
        # Create actual SQ3 data
        archive_size = 0x20 + (0x30 * len(charts_data)) + sum([len(x['data']) for x in charts_data])

        output_data = bytearray(0x20)
        output_data[0x00:0x04] = b'SEQP'
        output_data[0x04] = 0x01
        output_data[0x06] = 0x01
        output_data[0x0a] = 0x03
        output_data[0x0c:0x10] = struct.pack("<I", archive_size)
        output_data[0x10:0x14] = struct.pack("<I", 0x20)  # Size of header
        output_data[0x14:0x18] = struct.pack("<I", params['musicid'])
        output_data[0x18:0x1c] = struct.pack("<I", len(charts_data))
        output_data[0x1c:0x20] = struct.pack("<I", 0x12345678)

        output_data = bytearray(output_data)
        for chart_data in charts_data:
            data = chart_data['data']

            sq3t_data = bytearray(0x20)
            sq3t_data[0x00:0x04] = b'SQ3T'
            sq3t_data[0x06] = 0x03  # SQ3 flag
            sq3t_data[0x0a] = 0x03  # SQ3 flag 2?
            sq3t_data[0x0c:0x10] = struct.pack("<I", 0x20)  # Size of header
            sq3t_data[0x10:0x14] = struct.pack("<I", len(data) // 0x40)  # Number of events
            sq3t_data[0x14] = chart_data['header'].get('unk_sys', 0) & 0xff
            sq3t_data[0x15] = chart_data['header']['is_metadata'] & 0xff
            sq3t_data[0x16] = chart_data['header']['difficulty'] & 0xff
            sq3t_data[0x17] = chart_data['header']['game_type'] & 0xff
            sq3t_data[0x18:0x1a] = struct.pack("<H", chart_data['header'].get('time_division', 300))
            sq3t_data[0x1a:0x1c] = struct.pack("<H", chart_data['header'].get('beat_division', 480))
            sq3t_data[0x1c:0x20] = struct.pack("<I", 0x40)  # Size of each entry

            if chart_data['header']['is_metadata'] != 0:
                sq3t_data[0x15] = 0x01
                sq3t_data[0x16] = 0x01

            file_header = bytearray(0x10)
            file_header[0x00:0x04] = struct.pack("<I", len(data) + 0x30)
            file_header[0x04] = 0x10

            output_data += file_header
            output_data += sq3t_data
            output_data += data

        return output_data


    def generate_metadata_chart(chart):
        output = bytearray()

        global last_beat, beat_by_timestamp
        last_beat = 0

        if not contains_command(chart['beat_data'], 'startpos'):
            output += build_command({
                'name': 'startpos',
                'timestamp': 0,
                'timestamp_ms': 0,
                'data': {},
            }, 0)

        if not contains_command(chart['beat_data'], 'baron'):
            output += build_command({
                'name': 'baron',
                'timestamp': 0,
                'timestamp_ms': 0,
                'data': {},
            }, 0)

        for event in sorted(chart['beat_data'], key=lambda x:x['timestamp']):
            if event['name'] not in EVENT_ID_REVERSE:
                print("Couldn't find %s in EVENT_ID_REVERSE" % event['name'])
                exit(1)

            if event['name'] not in VALID_METACOMMANDS:
                continue

            output += build_command(event, chart['header']['game_type'])

        last_measure_duration = calculate_last_measure_duration(chart['beat_data'])
        last_event = sorted(chart['beat_data'], key=lambda x:x['timestamp'])[-1]
        last_timestamp = last_event['timestamp'] + last_measure_duration

        if not contains_command(chart['beat_data'], 'endpos'):
            output += build_command({
                'name': 'endpos',
                'timestamp': last_timestamp,
                'timestamp_ms': last_timestamp,
                'data': {},
            }, 0)

        return output


    def generate_chart(chart):
        output = bytearray()

        if not contains_command(chart['beat_data'], 'startpos'):
            output += build_command({
                'name': 'startpos',
                'timestamp': 0,
                'timestamp_ms': 0,
                'data': {},
            }, 0)

        if not contains_command(chart['beat_data'], 'chipstart'):
            output += build_command({
                'name': 'chipstart',
                'timestamp': 0,
                'timestamp_ms': 0,
                'data': {},
            }, 0)

        for event in sorted(chart['beat_data'], key=lambda x:x['timestamp']):
            if event['name'] not in EVENT_ID_REVERSE:
                print("Couldn't find %s in EVENT_ID_REVERSE" % event['name'])
                exit(1)

            if event['name'] in VALID_METACOMMANDS:
                continue

            output += build_command(event, chart['header']['game_type'])

        last_measure_duration = calculate_last_measure_duration(chart['beat_data'])
        last_event = sorted(chart['beat_data'], key=lambda x:x['timestamp'])[-1]
        last_timestamp = last_event['timestamp'] + last_measure_duration

        if not contains_command(chart['beat_data'], 'chipend'):
            output += build_command({
                'name': 'chipend',
                'timestamp': last_timestamp,
                'timestamp_ms': last_timestamp,
                'data': {},
            }, 0)

        if not contains_command(chart['beat_data'], 'endpos'):
            output += build_command({
                'name': 'endpos',
                'timestamp': last_timestamp,
                'timestamp_ms': last_timestamp,
                'data': {},
            }, 0)

        return output


    json_sq3 = json.loads(params['input']) if 'input' in params else None

    if not json_sq3:
        print("Couldn't find input data")
        return

    chart_metadata = [x for x in json_sq3['charts'] if x['header']['is_metadata'] == 1]
    charts = [x for x in json_sq3['charts'] if x['header']['is_metadata'] != 1]

    if not json_sq3['charts']:
        return

    if not chart_metadata:
        chart_metadata = copy.deepcopy(json_sq3['charts'][0])

    else:
        chart_metadata = chart_metadata[0]

    parts = ["drum", "guitar", "bass", "open", "guitar1", "guitar2"]
    found_parts = []
    parsed_charts = []
    for valid_parts in [['drum'], ['guitar', 'bass', 'open', 'guitar1', 'guitar2']]:
        metadata_chart = generate_metadata_chart(chart_metadata)

        # Step 2: Generate note charts from input charts
        filtered_charts = [
            x for x in json_sq3['charts']
            if x['header']['is_metadata'] == 0
            and x['header']['game_type'] < len(parts)
            and parts[x['header']['game_type']] in valid_parts
        ]

        if not filtered_charts:
            continue

        found_parts += [parts[x['header']['game_type']] for x in json_sq3['charts'] if x['header']['is_metadata'] == 0]

        chart_metadata['header']['is_metadata'] = 1
        parsed_charts.append({
            'data': metadata_chart,
            'header': chart_metadata['header']
        })

        for chart in filtered_charts:
            parsed_charts.append({
                'data': generate_chart(chart),
                'header': chart['header']
            })

        output_data = create_final_sq3_chart(params, parsed_charts)

        output_filename = "%s%04d.sq3" % ('d' if 'drum' in valid_parts else 'g', params['musicid'])
        with open(os.path.join(params['output'], output_filename), "wb") as outfile:
            outfile.write(output_data)

        create_event_file(params, filtered_charts)


def read_sq3_data(data, events, other_params):
    def parse_event_block(output, game, events={}):
        packet_data = {}

        timestamp = struct.unpack("<I", output[0x00:0x04])[0]
        beat = struct.unpack("<I", output[0x10:0x14])[0]
        game_type_id = {"drum": 0, "guitar": 1, "bass": 2}[game]

        if output[0x04] == 0x01:
            bpm_mpm = struct.unpack("<I", output[0x34:0x38])[0]
            packet_data['bpm'] = 60000000 / bpm_mpm
            # print(timestamp, packet_data)

        elif output[0x04] == 0x02:
            # Time signature is represented as numerator/(1<<denominator)
            packet_data['numerator'] = output[0x34]
            packet_data['denominator'] = 1 << output[0x35]
            packet_data['denominator_orig'] = output[0x35]

            # print(timestamp, packet_data)

        elif output[0x04] == 0x07:
            packet_data['unk'] = struct.unpack("<I", output[0x14:0x18])[0]  # What is this?

        elif output[0x04] == 0x10:
            packet_data['hold_duration'] = struct.unpack("<I", output[0x08:0x0c])[0]
            packet_data['unk'] = struct.unpack("<I", output[0x14:0x18])[0]  # What is this?
            packet_data['sound_id'] = struct.unpack("<I", output[0x20:0x24])[0]

            # Note length (relation to hold duration)
            packet_data['note_length'] = struct.unpack("<I", output[0x24:0x28])[0]

            packet_data['volume'] = output[0x2d]
            packet_data['auto_volume'] = output[0x2e]
            packet_data['note'] = NOTE_MAPPING[game][output[0x30]]

            # wail direction? 0/1 = up, 2 = down. Seems to alternate 0 and 1 if wailing in succession
            packet_data['wail_misc'] = output[0x31]

            # 2 = hold note, 1 = wail (bitmasks, so 3 = wail + hold)
            packet_data['guitar_special'] = output[0x32]

            # Auto note
            packet_data['auto_note'] = output[0x34]

            if packet_data['auto_note'] == 1:
                packet_data['note'] = "auto"

            if beat in events:
                for event in events[beat]:
                    is_gametype = event['game_type'] == game_type_id
                    is_eventtype = event['event_type'] == 0
                    is_note = packet_data['sound_id'] == event['note']

                    # This field seems to be maybe left over from previous games?
                    # 1852 doesn't work properly set the gamelevel fields
                    #is_diff = (event['gamelevel'] & (1 << difficulty)) != 0

                    if is_gametype and is_eventtype and is_note:
                        packet_data['bonus_note'] = True

        timestamp = struct.unpack("<I", output[0x00:0x04])[0]

        return {
            "id": output[0x04],
            "name": EVENT_ID_MAP[output[0x04]],
            'timestamp': timestamp,
            'timestamp_ms': timestamp / 300,
            'beat': beat,
            "data": packet_data
        }

    output = {
        "beat_data": []
    }

    if data is None:
        return None

    magic = data[0:4]
    if magic != b"SQ3T":
        print("Not a valid SQ3 file")
        exit(-1)

    # TODO: What is unk_sys? Look into that
    unk_sys, is_metadata, difficulty, game_type = data[0x14:0x18]
    header_size = struct.unpack("<I", data[0x0c:0x10])[0]
    entry_count = struct.unpack("<I", data[0x10:0x14])[0]
    time_division, beat_division, entry_size = struct.unpack("<HHI", data[0x18:0x20])

    if is_metadata not in [0, 1]: # Only support metadata and note charts. Not sure what type 2 is yet
        return None

    output['header'] = {
        "unk_sys": unk_sys,
        "is_metadata": is_metadata,
        "difficulty": difficulty,
        "game_type": game_type,
        "time_division": time_division,
        "beat_division": beat_division,
    }

    for i in range(entry_count):
        mdata = data[header_size + (i * entry_size):header_size + (i * entry_size) + entry_size]
        part = ["drum", "guitar", "bass"][game_type]
        parsed_data = parse_event_block(mdata, part, events)
        output['beat_data'].append(parsed_data)

    return output


def generate_json_from_sq3(params):
    data = open(params['input'], "rb").read() if 'input' in params else None

    if not data:
        print("No input file data")
        return

    magic = data[0:4]
    if magic != b"SEQP":
        print("Not a valid SEQ3 file")
        exit(-1)

    data_offset, musicid, num_charts = struct.unpack("<III", data[0x10:0x1c])

    if not params.get('musicid', None):
        params['musicid'] = musicid

    raw_charts = []
    for i in range(num_charts):
        data_size = struct.unpack("<I", data[data_offset:data_offset+4])[0]
        chart_data = data[data_offset+0x10:data_offset+0x10+data_size]
        raw_charts.append((chart_data, None, None, None))
        data_offset += data_size

    output_data = generate_json_from_data(params, read_sq3_data, raw_charts)
    output_data['musicid'] = musicid
    output_data['format'] = Sq3Format.get_format_name()

    return json.dumps(output_data, indent=4, sort_keys=True)


class Sq3Format:
    @staticmethod
    def get_format_name():
        return "SQ3"

    @staticmethod
    def to_json(params):
        return generate_json_from_sq3(params)

    @staticmethod
    def to_chart(params):
        generate_sq3_from_json(params)

    @staticmethod
    def is_format(filename):
        header = open(filename, "rb").read(0x40)

        try:
            is_seqp = header[0x00:0x04].decode('ascii') == "SEQP"
            is_sq3t = header[0x30:0x34].decode('ascii') == "SQ3T"
            is_ver3 = header[0x36] == 0x03
            if is_seqp and is_ver3 and is_sq3t:
                return True
        except:
            return False

        return False


def get_class():
    return Sq3Format
