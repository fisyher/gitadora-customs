import copy
import json
import os
import struct

from plugins.sq import generate_json_from_data

VALID_METACOMMANDS = ['startpos', 'endpos', 'baron', 'baroff', 'measure', 'beat', 'unk0c', 'bpm', 'barinfo']

EVENT_ID_MAP = {
    0x10: "bpm",
    0x20: "barinfo",
    0x30: "baron",
    0x40: "baroff",
    0x50: "measure",
    0x60: "beat",
    0x70: "chipstart",
    0x80: "chipend",
    0xe0: "startpos",
    0xf0: "endpos",
    0x00: "note",
    0x01: "auto",
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
        0xff: "auto",
    },
    'guitar': {
        0x01: "g_rxx",
        0x02: "g_xgx",
        0x03: "g_rgx",
        0x04: "g_xxb",
        0x05: "g_rxb",
        0x06: "g_xgb",
        0x07: "g_rgb",
        0x10: 'g_open',
        0xff: "auto",
    },
    'bass': {
        0x01: "b_rxx",
        0x02: "b_xgx",
        0x03: "b_rgx",
        0x04: "b_xxb",
        0x05: "b_rxb",
        0x06: "b_xgb",
        0x07: "b_rgb",
        0x10: 'b_open',
        0xff: "auto",
    },
    'open': {
        0x01: "g_rxx",
        0x02: "g_xgx",
        0x03: "g_rgx",
        0x04: "g_xxb",
        0x05: "g_rxb",
        0x06: "g_xgb",
        0x07: "g_rgb",
        0x10: "g_open",
        0xff: "auto",
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
    "auto": 0xff,

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


def generate_sq2_from_json(params):
    def build_command(event, game_type):
        output = bytearray(0x10)

        output[0x00:0x04] = struct.pack("<I", event['timestamp'])
        output[0x05] = EVENT_ID_REVERSE[event['name']] & 0xff

        if event['name'] == "bpm":
            if event['data']['bpm'] < 1:
                event['data']['bpm'] = 1

            elif event['data']['bpm'] > 60000000:
                event['data']['bpm'] = 60000000

            output[0x08:0x0c] = struct.pack("<I", int(round(60000000 / event['data']['bpm'])))

        elif event['name'] == "barinfo":
            output[0x0c] = event['data']['numerator'] & 0xff

            denominator = 1 << (event['data']['denominator'].bit_length() - 1)
            if denominator != event['data']['denominator']:
                raise Exception("ERROR: The time signature denominator must be divisible by 2."
                                "Found {}".format(event['data']['denominator']))

            output[0x0d] = (event['data']['denominator'].bit_length() - 1) & 0xff

        elif event['name'] == "note":
            if event['data']['note'] not in REVERSE_NOTE_MAPPING:
                # Set all unknown events to auto play
                REVERSE_NOTE_MAPPING[event['data']['note']] = 0xff

            if 'sound_id' in event['data']:
                output[0x08:0x0a] = struct.pack("<H", event['data']['sound_id'])

            if 'unk' in event['data']:
                output[0x0a:0x0c] = struct.pack("<H", event['data']['unk'])

            if 'volume' in event['data']:
                output[0x0c] = event['data']['volume'] & 0xff

            if 'note' in event['data']:
                output[0x04] = REVERSE_NOTE_MAPPING[event['data']['note']] & 0xff

            if event['data'].get('note') == "auto":
                output[0x04] = 0
                output[0x05] = EVENT_ID_REVERSE["auto"] & 0xff

        elif event['name'] == "auto":
            output[0x04] = 0
            output[0x08:0x0a] = struct.pack("<H", event['data'].get('sound_id', 0))
            output[0x0a:0x0c] = struct.pack("<H", event['data'].get('unk', 0))
            output[0x0c] = event['data'].get('volume', 0) & 0xff

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


    def create_final_sq2_chart(params, charts_data):
        # Create actual sq2 data
        archive_size = 0x20 + (0x30 * len(charts_data)) + sum([len(x['data']) for x in charts_data])

        output_data = bytearray(0x20)
        output_data[0x00:0x04] = b'SEQP'
        output_data[0x06] = 0x02
        output_data[0x0a] = 0x01
        output_data[0x0c:0x10] = struct.pack("<I", archive_size)
        output_data[0x14:0x18] = struct.pack("<I", params['musicid'])
        output_data[0x18:0x1c] = struct.pack("<I", len(charts_data))

        output_data = bytearray(output_data)
        for chart_data in charts_data:
            data = chart_data['data']

            seqt_data = bytearray(0x20)
            seqt_data[0x00:0x04] = b'SEQT'
            seqt_data[0x06] = 0x02  # sq2 flag
            seqt_data[0x0a] = 0x01  # sq2 flag 2?
            seqt_data[0x0c:0x10] = struct.pack("<I", 0x20)  # Size of header
            seqt_data[0x10:0x14] = struct.pack("<I", len(data) // 0x10)  # Number of events
            seqt_data[0x14] = chart_data['header'].get('unk_sys', 0) & 0xff
            seqt_data[0x15] = chart_data['header']['is_metadata'] & 0xff
            seqt_data[0x16] = chart_data['header']['difficulty'] & 0xff
            seqt_data[0x17] = chart_data['header']['game_type'] & 0xff

            if chart_data['header']['is_metadata'] != 0:
                seqt_data[0x15] = 0x01
                seqt_data[0x16] = 0x01

            file_header = bytearray(0x10)
            file_header[0x00:0x04] = struct.pack("<I", len(data) + 0x30)
            file_header[0x04] = 0x10

            output_data += file_header
            output_data += seqt_data
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


    json_sq2 = json.loads(params['input']) if 'input' in params else None

    if not json_sq2:
        print("Couldn't find input data")
        return

    chart_metadata = [x for x in json_sq2['charts'] if x['header']['is_metadata'] == 1]
    charts = [x for x in json_sq2['charts'] if x['header']['is_metadata'] != 1]

    if not json_sq2['charts']:
        return

    if not chart_metadata:
        chart_metadata = copy.deepcopy(json_sq2['charts'][0])

    else:
        chart_metadata = chart_metadata[0]

    parts = ["drum", "guitar", "bass", "open", "guitar1", "guitar2"]
    found_parts = []
    parsed_charts = []
    for valid_parts in [['drum'], ['guitar', 'bass', 'open', 'guitar1', 'guitar2']]:
        metadata_chart = generate_metadata_chart(chart_metadata)

        # Step 2: Generate note charts from input charts
        filtered_charts = [
            x for x in json_sq2['charts']
            if x['header']['is_metadata'] == 0
            and x['header']['game_type'] < len(parts)
            and parts[x['header']['game_type']] in valid_parts
        ]

        if not filtered_charts:
            continue

        found_parts += [parts[x['header']['game_type']] for x in json_sq2['charts'] if x['header']['is_metadata'] == 0]

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

        output_data = create_final_sq2_chart(params, parsed_charts)

        output_filename = "%s%04d.sq2" % ('d' if 'drum' in valid_parts else 'g', params['musicid'])
        with open(os.path.join(params['output'], output_filename), "wb") as outfile:
            outfile.write(output_data)


def read_sq2_data(data, events, other_params):
    def parse_event_block(mdata, game, is_metadata=False):
        packet_data = {}

        timestamp = struct.unpack("<I", mdata[0x00:0x04])[0]

        event_name = EVENT_ID_MAP[mdata[0x05]]

        if mdata[0x05] == 0x10:
            bpm_bpm = struct.unpack("<I", mdata[0x08:0x0c])[0]
            packet_data['bpm'] = 60000000 / bpm_bpm
        elif mdata[0x05] == 0x20:
            # Time signature is represented as numerator/(1<<denominator)
            packet_data['numerator'] = mdata[0x0c]
            packet_data['denominator'] = 1 << mdata[0x0d]
        elif mdata[0x05] == 0x00:
            packet_data['sound_id'] = struct.unpack("<H", mdata[0x08:0x0A])[0]
            packet_data['sound_unk'] = struct.unpack("<H", mdata[0x0A:0x0C])[0]
            packet_data['volume'] = mdata[0x0c]

            if (mdata[0x04] & 0x10) == 0x10:
                # Open note
                packet_data['note'] = NOTE_MAPPING[game][mdata[0x04] & 0x10] # note
            else:
                packet_data['note'] = NOTE_MAPPING[game][mdata[0x04] & 0x0f] # note

            is_wail = (mdata[0x04] & 0x20) == 0x20

            packet_data['wail_misc'] = 1 if is_wail else 0
            packet_data['guitar_special'] = 1 if is_wail else 0

            # TODO: Update code to work with .EVT file data
            # if beat in events:
            #     for event in events[beat]:
            #         is_gametype = event['game_type'] == game_type_id
            #         is_eventtype = event['event_type'] == 0
            #         is_note = packet_data['sound_id'] == event['note']
            #         is_diff = (event['gamelevel'] & (1 << difficulty)) != 0

            #         if is_gametype and is_eventtype and is_note and is_diff:
            #             packet_data['bonus_note'] = True

            if is_metadata:
                event_name = "meta"

        elif mdata[0x05] == 0x01:
            # Auto note
            packet_data['sound_id'] = struct.unpack("<H", mdata[0x08:0x0A])[0]
            packet_data['sound_unk'] = struct.unpack("<H", mdata[0x0A:0x0C])[0]
            packet_data['volume'] = mdata[0x0c]
            packet_data['note'] = "auto"
            packet_data['auto_volume'] = 1
            packet_data['auto_note'] = 1
            event_name = "note"

        timestamp = struct.unpack("<I", mdata[0x00:0x04])[0]

        return {
            "id": mdata[0x04],
            "name": event_name,
            'timestamp': timestamp,
            'timestamp_ms': timestamp / 300,
            "data": packet_data
        }

    output = {
        "beat_data": []
    }

    if data is None:
        return None

    magic = data[0:4]
    if magic != bytearray("SEQT", encoding="ascii"):
        print("Not a valid SEQT chart")
        exit(-1)

    # TODO: What is unk_sys? Look into that
    unk_sys, is_metadata, difficulty, game_type = data[0x14:0x18]
    header_size = struct.unpack("<I", data[0x0c:0x10])[0]
    entry_count = struct.unpack("<I", data[0x10:0x14])[0]
    time_division = 300
    beat_division = 480
    entry_size = 0x10

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
        part = ["drum", "guitar", "bass", "open", "guitar1", "guitar2"][game_type]
        parsed_data = parse_event_block(mdata, part, is_metadata=is_metadata)
        output['beat_data'].append(parsed_data)

    return output


def generate_json_from_sq2(params):
    data = open(params['input'], "rb").read() if 'input' in params else None

    if not data:
        print("No input file data")
        return

    output_data = {}

    magic = data[0:4]
    if magic != bytearray("SEQP", encoding="ascii"):
        print("Not a valid SQ2 file")
        exit(-1)

    data_offset = 0x20
    musicid, num_charts = struct.unpack("<II", data[0x14:0x1c])

    raw_charts = []
    for i in range(num_charts):
        data_size = struct.unpack("<I", data[data_offset:data_offset+4])[0]
        chart_data = data[data_offset+0x10:data_offset+0x10+data_size]
        raw_charts.append((chart_data, None, None, None))
        data_offset += data_size

    output_data = generate_json_from_data(params, read_sq2_data, raw_charts)
    output_data['musicid'] = musicid
    output_data['format'] = Sq2Format.get_format_name()

    return json.dumps(output_data, indent=4, sort_keys=True)


class Sq2Format:
    @staticmethod
    def get_format_name():
        return "SQ2"

    @staticmethod
    def to_json(params):
        return generate_json_from_sq2(params)

    @staticmethod
    def to_chart(params):
        generate_sq2_from_json(params)

    @staticmethod
    def is_format(filename):
        header = open(filename, "rb").read(0x40)

        try:
            is_seqp = header[0x00:0x04].decode('ascii') == "SEQP"
            is_seqt = header[0x30:0x34].decode('ascii') == "SEQT"
            is_ver2 = header[0x36] == 0x02
            if is_seqp and is_ver2 and is_seqt:
                return True
        except:
            return False

        return False


def get_class():
    return Sq2Format
