import json
import struct

from plugins.gsq import EVENT_ID_MAP, NOTE_MAPPING, generate_json_from_data


def read_gsq2_data(data, events, other_params):
    def parse_event_block(mdata, game):
        packet_data = {}

        timestamp, param1, param2, cmd = struct.unpack("<IIII", mdata[0:16])
        param3 = cmd & 0xffffff0f
        cmd &= 0x00f0

        if timestamp == 0xffffffff:
            return None

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

        return {
            "name": event_name,
            'timestamp': timestamp,
            'timestamp_ms': timestamp / 300,
            "data": packet_data
        }


    if data[0x00:0x04] == b"GSQ1":
        data = data[0x10:]

    part = [None, "guitar", "bass", "open", "guitar", "guitar"][other_params['game_type']]

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
    entry_size = 0x10
    entry_count = len(data) // entry_size

    for i in range(entry_count):
        mdata = data[header_size + (i * entry_size):header_size + (i * entry_size) + entry_size]
        parsed_data = parse_event_block(mdata, part)

        if parsed_data:
            output['beat_data'].append(parsed_data)

    return output


class Gsq15Format:
    @staticmethod
    def get_format_name():
        return "Gsq15"

    @staticmethod
    def to_json(params):
        output_data = generate_json_from_data(params, read_gsq2_data)
        output_data['format'] = Gsq15Format.get_format_name()
        return json.dumps(output_data, indent=4, sort_keys=True)

    @staticmethod
    def to_chart(params):
        raise NotImplementedError()

    @staticmethod
    def is_format(filename):
        return False


def get_class():
    return Gsq15Format
