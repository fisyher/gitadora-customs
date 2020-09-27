import json
import struct

from plugins.gsq import generate_json_from_data
from plugins.dsq import EVENT_ID_MAP, NOTE_MAPPING


def read_dsq1_data(data, events, other_params):
    def parse_event_block(mdata, game):
        packet_data = {}

        timestamp, cmd, param1, param2 = struct.unpack("<IBBH", mdata[0:8])
        timestamp *= 4

        event_name = EVENT_ID_MAP[cmd] if cmd in EVENT_ID_MAP else "unk"

        if event_name == "note":
            packet_data['sound_id'] = param2
            packet_data['volume'] = param1
            packet_data['note'] = NOTE_MAPPING[game][cmd]

            if packet_data['note'] == "auto":
                packet_data['auto_volume'] = 1
                packet_data['auto_note'] = 1

        return {
            "name": event_name,
            'timestamp': timestamp,
            'timestamp_ms': timestamp / 300,
            "data": packet_data
        }

    part = ["drum", None, None, None, None, None][other_params['game_type']]

    if not part:
        return None

    output = {
        "beat_data": []
    }

    if data is None:
        return None

    output['header'] = {
        "unk_sys": 0,
        "difficulty": other_params['difficulty'],
        "is_metadata": other_params['is_metadata'],
        "game_type": other_params['game_type'],
        "time_division": 300,
        "beat_division": 480,
    }

    header_size = 0
    entry_size = 0x08
    entry_count = len(data) // entry_size

    for i in range(entry_count):
        mdata = data[header_size + (i * entry_size):header_size + (i * entry_size) + entry_size]
        parsed_data = parse_event_block(mdata, part)

        if parsed_data:
            output['beat_data'].append(parsed_data)

    return output


class Dsq1Format:
    @staticmethod
    def get_format_name():
        return "Dsq1"

    @staticmethod
    def to_json(params):
        output_data = generate_json_from_data(params, read_dsq1_data)
        output_data['format'] = Dsq1Format.get_format_name()
        return json.dumps(output_data, indent=4, sort_keys=True)

    @staticmethod
    def to_chart(params):
        raise NotImplementedError()

    @staticmethod
    def is_format(filename):
        return False


def get_class():
    return Dsq1Format
