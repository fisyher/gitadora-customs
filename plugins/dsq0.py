import json
import struct

from plugins.gsq import generate_json_from_data
from plugins.dsq import NOTE_MAPPING

EVENT_ID_MAP = {
    0x00: "note",
    0x01: "note",
    0x02: "note",
    0x03: "note",
    0x04: "note",
    0x05: "note",
    0x06: "measure",
    0x07: "beat",

    0x0c: "endpos",
}

def read_dsq0_data(data, events, other_params):
    def parse_event_block(mdata, game):
        packet_data = {}

        timestamp, _, cmd, param1, param2, visibility = struct.unpack("<HHBBBB", mdata[0:8])
        timestamp *= 4

        if cmd not in EVENT_ID_MAP:
            event_name = "unk"

        else:
            event_name = EVENT_ID_MAP[cmd]

        if event_name == "note" and visibility != 0 and visibility not in [1, 2, 4]:
            import hexdump
            hexdump.hexdump(mdata)
            exit(1)

        if event_name == "note":
            packet_data['sound_id'] = param2
            packet_data['volume'] = param1
            packet_data['note'] = NOTE_MAPPING[game][cmd]

            if visibility != 0:
                packet_data['note'] = "auto"

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


class Dsq0Format:
    @staticmethod
    def get_format_name():
        return "Dsq0"

    @staticmethod
    def to_json(params):
        output_data = generate_json_from_data(params, read_dsq0_data)
        output_data['format'] = Dsq0Format.get_format_name()
        return json.dumps(output_data, indent=4, sort_keys=True)

    @staticmethod
    def to_chart(params):
        raise NotImplementedError()

    @staticmethod
    def is_format(filename):
        return False


def get_class():
    return Dsq0Format
