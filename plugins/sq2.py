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

drum_note_map = {
    0x00: "Hi-hat (left Blue)",
    0x01: "Snare (yellow)",
    0x02: "Bass pedal",
    0x03: "High tom (Green)",
    0x04: "Low tom (Red)",
    0x05: "Right cymbal (Right Blue)",
}

DIFFICULTY_LEVELS_MAP = {
    0x00: "NOV",
    0x01: "BSC",
    0x02: "ADV",
    0x03: "EXT",
    0x04: "MST"
}

GAMES_MAP = {
    0x00: "Drums",
    0x01: "Guitar",
    0x02: "Bass",
    0x03: "Open",
}

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


def combine_metadata_with_chart(metadata, chart):
    chart_combined = copy.deepcopy(chart)

    for timestamp_key in sorted(metadata['timestamp'].keys(), key=lambda x: int(x)):
        if timestamp_key not in chart_combined['timestamp']:
            chart_combined['timestamp'][timestamp_key] = []

        for d in metadata['timestamp'][timestamp_key]:
            chart_combined['timestamp'][timestamp_key].append(d)

    return chart_combined


def get_timesigs_by_timestamp(chart_combined):
    time_signatures_by_timestamp = {
        0: {
            'numerator': 4,
            'denominator': 4,
            'timesig': 1,
        }
    }

    for k in sorted(chart_combined['timestamp'].keys(), key=lambda x: int(x)):
        for beat in chart_combined['timestamp'][k]:
            if beat['name'] == "barinfo":
                time_signatures_by_timestamp[k] = {
                    'numerator': beat['data']['numerator'],
                    'denominator': beat['data']['denominator'],
                    'timesig': beat['data']['numerator'] / beat['data']['denominator']
                }

    return time_signatures_by_timestamp


def generate_timesigs_for_events(chart):
    time_signatures_by_timestamp = get_timesigs_by_timestamp(chart)

    # Generate a time_signature field for everything based on timestamp
    for k in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        idx = [x for x in sorted(time_signatures_by_timestamp.keys(),
                                 key=lambda x: int(x)) if int(x) <= int(k)][-1]
        time_signature = time_signatures_by_timestamp[idx]

        for idx in range(len(chart['timestamp'][k])):
            chart['timestamp'][k][idx]['time_signature'] = time_signature

    return chart


def generate_beats_by_timestamp(chart):
    # Generate beats based on measures and line markers
    current_timesig = {'numerator': 4, 'denominator': 4}
    current_measures = 0
    current_beats = 0
    beats_by_timestamp = {}

    found_first = False

    hold_timesig = None
    for timestamp_key in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        for beat in chart['timestamp'][timestamp_key]:
            name = beat['name']
            timestamp = int(timestamp_key)

            if not found_first:
                current_timesig = beat['time_signature']
                hold_timesig = current_timesig
            else:
                hold_timesig = beat['time_signature']

            if name == "measure":
                if found_first:
                    current_beats = 0
                    current_measures += (1920 // current_timesig['denominator']) * current_timesig['numerator']

                found_first = True

            if name == "beat":
                current_beats += (1920 // current_timesig['denominator'])

            if name in ["measure", "beat"]:
                last_beat = current_measures + current_beats
                beats_by_timestamp[timestamp] = last_beat

        current_timesig = hold_timesig

    return beats_by_timestamp


def correct_auto_notes(chart):
    for timestamp_key in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        for beat in chart['timestamp'][timestamp_key]:
            if beat['name'] != "note":
                continue

            if beat['data']['note'] not in REVERSE_NOTE_MAPPING:
                # Set all unknown events to auto play
                REVERSE_NOTE_MAPPING[beat['data']['note']] = 0xff

            is_auto_note = beat['data'].get('auto_note', 0)
            is_auto_name = beat['data'].get('note', "auto") == "auto"
            is_auto_mapping = REVERSE_NOTE_MAPPING[beat['data']['note']] == 0xff

            if is_auto_note or is_auto_name or is_auto_mapping:
                beat['name'] = "auto"

    return chart


def generate_beats_for_events(chart):
    beats_by_timestamp = generate_beats_by_timestamp(chart)

    # Set base beat for every event at timestamp
    last_timestamp = 0
    for timestamp_key in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        for beat in chart['timestamp'][timestamp_key]:
            name = beat['name']
            timestamp = int(timestamp_key)

            if timestamp in beats_by_timestamp:
                last_timestamp = timestamp
                break

        for beat in chart['timestamp'][timestamp_key]:
            name = beat['name']
            beat['beat'] = beats_by_timestamp[last_timestamp]

    last_timestamp = 0
    cur_bpm = 0
    for timestamp_key in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        for beat in chart['timestamp'][timestamp_key]:
            name = beat['name']
            timestamp = int(timestamp_key)

            if timestamp in beats_by_timestamp:
                last_timestamp = timestamp
                break

        for beat in chart['timestamp'][timestamp_key]:
            if beat['name'] == "bpm":
                cur_bpm = beat['data']['bpm']
                break

        for beat in chart['timestamp'][timestamp_key]:
            name = beat['name']
            timestamp = int(timestamp_key)

            keys = list(sorted(beats_by_timestamp.keys(), key=lambda x: int(x))) + [0]
            next_timestamp = keys[keys.index(last_timestamp) + 1]
            if timestamp not in beats_by_timestamp:
                diff = int(timestamp_key) - last_timestamp
                tf = ((diff / 300) * (cur_bpm / 60)) * (1920 // beat['time_signature']['denominator'])

                beat['beat'] = beat['beat'] + int(tf)

    return chart


def generate_metadata_fields(metadata, chart):
    # Generate and add any important data that isn't guaranteed
    # to be there

    # TODO: This code is slow

    # I know they're read, but I'm curious if these are actually
    # ever used in game or not. The required info can be calculated
    # using the time signature and deriving it from the value 1920.
    # For example 0x1e0 (480) is 1920 / (1 << (4 / 2)) where 4 is
    # the denominator of the time signature.
    if 'beat_division' not in metadata['header']:
        metadata['header']['beat_division'] = 480  # 4/4 time signature

    if 'time_division' not in metadata['header']:
        metadata['header']['time_division'] = 300

    chart_combined = combine_metadata_with_chart(metadata, chart)
    chart_combined = generate_timesigs_for_events(chart_combined)
    chart_combined = correct_auto_notes(chart_combined)
    chart_combined = generate_beats_for_events(chart_combined)

    return chart_combined


def get_note_counts_from_json(chart, part):
    note_counts = {}

    total_notes = 0
    for k in chart['timestamp']:
        for event in chart['timestamp'][k]:
            if 'data' not in event:
                continue

            is_note = event['name'] == "note"
            is_auto = event['data'].get('note') == "auto"
            is_auto_note = event['data'].get('auto_note') == 1

            if is_note and not is_auto and not is_auto_note:
                # Drum and guitar must be calculated separately because
                # Guitar needs R G B Y P Open calculated by bit flag may be the most accurate

                if part == "drum":
                    if event['data']['note'] not in note_counts:
                        note_counts[event['data']['note']] = 0
                    note_counts[event['data']['note']] += 1
                    total_notes += 1
                elif part in ['guitar', 'bass']:
                    n = event['data']['note'][2:]

                    if n == "open":
                        if n not in note_counts:
                            note_counts[n] = 0
                        note_counts[n] += 1
                        total_notes += 1
                    else:
                        for note in [c for c in n if c != 'x']:
                            if note not in note_counts:
                                note_counts[note] = 0
                            note_counts[note] += 1
                        total_notes += 1

    return {'total': total_notes, 'notes': note_counts}


def create_preview(json_sq2, params, part):
    print("Creating preview file", part)

    running_threads = []
    output_folder = params['output']

    filename = os.path.join(output_folder,
                            "i%04d%s.bin" % (json_sq2['musicid'], part))

    if not os.path.exists(os.path.join(params['sound_folder'], json_sq2['preview'])):
        return []

    if USE_THREADS:
        bgm_thread = threading.Thread(target=wavbintool.parse_wav,
                                      args=(os.path.join(params['sound_folder'],
                                            json_sq2['preview']),
                                            filename))
        bgm_thread.start()
        running_threads.append(bgm_thread)
    else:
        wavbintool.parse_wav(os.path.join(params['sound_folder'],
                             json_sq2['preview']),
                             filename)

    return running_threads


def create_bgm_render(json_sq2, params, target_parts, output_bgm_filename):
    def _create_bgm_render(params_bgm, target_parts, output_bgm_filename):
        wav.generate_wav_from_json(params_bgm, generate_output_filename=False)
        wavbintool.parse_wav(params_bgm['output'], output_bgm_filename)

    print("Creating BGM render", target_parts)

    params_bgm = copy.deepcopy(params)
    params_bgm['render_ext'] = "wav"
    params_bgm['output'] = tmpfile.mkstemp(suffix="." + params_bgm.get('render_ext', 'wav'))

    if os.path.exists(params_bgm['output']):
        os.unlink(params_bgm['output'])

    if 'guitar' in target_parts or 'bass' in target_parts or 'open' in target_parts:
        params_bgm['render_ignore_auto'] = True

    params_bgm['parts'] = target_parts
    params_bgm['difficulty'] = ['max']

    running_threads = []

    if USE_THREADS:
        bgm_thread = threading.Thread(target=_create_bgm_render,
                                      args=(params_bgm,
                                            target_parts,
                                            output_bgm_filename))
        bgm_thread.start()
        running_threads.append(bgm_thread)
    else:
        _create_bgm_render(params_bgm, target_parts, output_bgm_filename)

    return running_threads


def create_bgm(json_sq2, params, output_bgm_filename):
    def _create_bgm(bgm_filename, sound_folder, output_bgm_filename):
        # Create BGM file render
        merged_wav_filename = audio.merge_bgm(bgm_filename, sound_folder)
        wavbintool.parse_wav(merged_wav_filename, output_bgm_filename)

    print("Creating BGM file")

    running_threads = []

    if USE_THREADS:
        bgm_thread = threading.Thread(target=_create_bgm,
                                      args=(json_sq2['bgm'],
                                            params['sound_folder'],
                                            output_bgm_filename))
        bgm_thread.start()
        running_threads.append(bgm_thread)
    else:
        _create_bgm(json_sq2['bgm'], params['sound_folder'], output_bgm_filename)

    return running_threads


def create_va3(json_sq2, params, part):
    print("Creating VA3 archive")

    running_threads = []

    if part not in json_sq2['sound_metadata']:
        return []

    output_folder = params['output']

    va3_filename = "spu%04d%s.va3" % (json_sq2['musicid'], part[0])
    output_filename = os.path.join(output_folder, va3_filename)

    if USE_THREADS:
        va3_thread = threading.Thread(target=vas3tool.write_vas3,
                                      args=(params['sound_folder'],
                                            output_filename,
                                            json_sq2['sound_metadata'][part]))
        va3_thread.start()
        running_threads.append(va3_thread)
    else:
        vas3tool.write_vas3(params['sound_folder'],
                            output_filename,
                            json_sq2['sound_metadata'][part])

    return running_threads


def create_event_file(json_sq2, params, charts):
    output_folder = params['output']

    # Gather bonus note info
    # Use a dictionary for the first pass because it's
    # easier to handle the data for multiple difficulties
    bonus_notes = {}
    for chart in charts:
        for x in chart['timestamp']:
            for x2 in chart['timestamp'][x]:
                if not (x2['name'] == "note" and x2['data'].get('bonus_note', 0) == 1):
                    continue

                if x2['beat'] not in bonus_notes:
                    bonus_notes[x2['beat']] = {}

                gamelevel = 1 << chart['header']['difficulty']
                if x2['data']['sound_id'] in bonus_notes[x2['beat']]:
                    gamelevel |= bonus_notes[x2['beat']][x2['data']['sound_id']]['gamelevel']

                bonus_notes[x2['beat']][x2['data']['sound_id']] = {
                    'sound_id': x2['data']['sound_id'],
                    'time': x2['beat'],
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
            E.musicid("{}".format(json_sq2['musicid']), __type="u32"),
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
    event_xml_filename = os.path.join(output_folder, "event%04d.ev2" % (json_sq2['musicid']))

    with open(event_xml_filename, "wb") as f:
        f.write(eamxml.get_binxml(event_xml_text))


def get_package_unique_identifier(filename):
    unique_id = None

    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            package_data = json.load(f)

            unique_id = package_data.get('unique_id', None)

    if unique_id is None:
        # Generate a unique id
        unique_id = str(uuid.uuid4()).replace("-","")

    return unique_id


def create_package_file(json_sq2, params, song_metadata_drum, song_metadata_guitar, parts):
    output_folder = params['output']

    unique_id = get_package_unique_identifier(os.path.join(output_folder, "package.json"))

    basic_levels = {
        "novice": 0,
        "basic": 0,
        "advanced": 0,
        "extreme": 0,
        "master": 0
    }

    if os.path.exists(os.path.join(output_folder, "package.json")):
        j = json.load(open(os.path.join(output_folder, "package.json"), "r", encoding="utf-8"))

        if not song_metadata_drum:
            levels = j.get('difficulty', {}).get('drum', basic_levels)
            notes = j.get('notes', {}).get('drum', {})

            if notes:
                parts.append("drum")

            song_metadata_drum = {
                'difficulty_levels': {
                    'drum': levels
                },
                'note_counts': {
                    'drum': notes
                },
            }

        if not song_metadata_guitar:
            guitar_levels = j.get('difficulty', {}).get('guitar', basic_levels)
            bass_levels = j.get('difficulty', {}).get('bass', basic_levels)
            open_levels = j.get('difficulty', {}).get('open', basic_levels)

            guitar_notes = j.get('notes', {}).get('guitar', {})
            bass_notes = j.get('notes', {}).get('bass', {})
            open_notes = j.get('notes', {}).get('open', {})

            if guitar_notes or bass_notes or open_notes:
                parts.append("guitar")

            song_metadata_guitar = {
                'difficulty_levels': {
                    'guitar': guitar_levels,
                    'bass': bass_levels,
                    'open': open_levels,
                },
                'note_counts': {
                    'guitar': guitar_notes,
                    'bass': bass_notes,
                    'open': open_notes,
                },
            }


    song_metadata = song_metadata_drum if song_metadata_drum else song_metadata_guitar

    difficulties = {
        'drum': song_metadata_drum.get("difficulty_levels", {}).get('drum', basic_levels),
        'guitar': song_metadata_guitar.get("difficulty_levels", {}).get('guitar', basic_levels),
        'bass': song_metadata_guitar.get("difficulty_levels", {}).get('bass', basic_levels),
        'open': song_metadata_guitar.get("difficulty_levels", {}).get('open', basic_levels),
    }

    notes = {
        'drum': song_metadata_drum.get("note_counts", {}).get('drum', {}),
        'guitar': song_metadata_guitar.get("note_counts", {}).get('guitar', {}),
        'bass': song_metadata_guitar.get("note_counts", {}).get('bass', {}),
        'open': song_metadata_guitar.get("note_counts", {}).get('open', {}),
    }

    package_info = {
        "unique_id": unique_id,
        "artist": song_metadata.get("artist_name", ""),
        "artist_ascii": helper.romanize(song_metadata.get("artist_name", "")),
        "title": song_metadata.get("song_title", ""),
        "title_ascii": helper.romanize(song_metadata.get("song_title", "")),
        "bpm": song_metadata.get("bpm", 0),
        "bpm2": song_metadata.get("bpm2", 0),
        "difficulty": difficulties,
        "files": {
            "event": "event%04d.ev2" % (json_sq2['musicid']),
            "bgm": {
                "___k": "bgm%04d___k.bin" % (json_sq2['musicid']),
                "__bk": "bgm%04d__bk.bin" % (json_sq2['musicid']),
                "_gbk": "bgm%04d_gbk.bin" % (json_sq2['musicid']),
                "d__k": "bgm%04dd__k.bin" % (json_sq2['musicid']),
                "d_bk": "bgm%04dd_bk.bin" % (json_sq2['musicid']),
            }
        },
        "graphics": {
            "jacket": song_metadata.get("pre_image", "pre.jpg"),
        },
        "notes": notes
    }

    if json_sq2['musicid'] != None:
        package_info.update({
            "real_song": 1,
            "music_id": json_sq2['musicid'],
        })

    if 'drum' in parts:
        package_info['files']['drum'] = {
            "seq": "d%04d.sq2" % (json_sq2['musicid']),
            "sound": "spu%04dd.va3" % (json_sq2['musicid']),
            "preview": "i%04ddm.bin" % (json_sq2['musicid']),
        }

    if 'guitar' in parts or 'bass' in parts or 'open' in parts:
        package_info['files']['guitar'] = {
            "seq": "g%04d.sq2" % (json_sq2['musicid']),
            "sound": "spu%04dg.va3" % (json_sq2['musicid']),
            "preview": "i%04dgf.bin" % (json_sq2['musicid']),
        }

    with open(os.path.join(output_folder, "package.json"), "w", encoding="utf-8") as f:
        json.dump(package_info, f, ensure_ascii=False, indent=4, separators=(', ', ': '))


def generate_song_metadata(charts):
    note_counts = {
        'drum': {},
        'guitar': {},
        'bass': {},
        'open': {},
    }

    artist_name = ""
    song_title = ""
    bpm = 0

    difficulty_levels = {
        "drum": {
            "novice": 0,
            "basic": 0,
            "advanced": 0,
            "extreme": 0,
            "master": 0
        },
        "guitar": {
            "novice": 0,
            "basic": 0,
            "advanced": 0,
            "extreme": 0,
            "master": 0
        },
        "bass": {
            "novice": 0,
            "basic": 0,
            "advanced": 0,
            "extreme": 0,
            "master": 0
        },
        "open": {
            "novice": 0,
            "basic": 0,
            "advanced": 0,
            "extreme": 0,
            "master": 0
        }
    }

    pre_image = "jacket.png"

    for x in charts:
        game_type = ["drum", "guitar", "bass", "open"][x['header']['game_type']]
        difficulty = ['nov', 'bsc', 'adv', 'ext', 'mst'][x['header']['difficulty']]
        note_counts[game_type][difficulty] = get_note_counts_from_json(x, game_type)

        artist_name = x.get('header', {}).get('artist', "")
        song_title = x.get('header', {}).get('title', "")
        bpm = x.get('header', {}).get('bpm', 0)
        bpm2 = x.get('header', {}).get('bpm2', 0)

        if 'preimage' in x and x['preimage']:
            pre_image = x['preimage']

        if 'level' in x['header']:
            levels = ['novice', 'basic', 'advanced', 'extreme', 'master']
            difficulty = levels[x['header']['difficulty']]
            difficulty_levels[game_type][difficulty] = int(x['header']['level'][game_type])

    return {
        "note_counts": note_counts,
        "artist_name": artist_name,
        "song_title": song_title,
        "bpm": bpm,
        "bpm2": bpm2,
        "difficulty_levels": difficulty_levels,
        "pre_image": pre_image
    }


def create_sq2_file(json_sq2, params, target_parts, charts_data):
    output_folder = params['output']

    # Create actual SQ2 data
    archive_size = 0x20 + (0x10 * len(charts_data)) + sum([len(x['data']) for x in charts_data])

    output_data = [0] * 0x20
    output_data[0x00:0x04] = b'SEQP'
    output_data[0x06] = 0x02
    output_data[0x0a] = 0x01
    output_data[0x0c:0x10] = struct.pack("<I", archive_size)
    output_data[0x14:0x18] = struct.pack("<I", json_sq2['musicid'])
    output_data[0x18:0x1c] = struct.pack("<I", len(charts_data))

    output_data = bytearray(output_data)
    for chart_data in charts_data:
        data = chart_data['data']

        file_header = [0] * 0x10
        file_header[0x00:0x04] = struct.pack("<I", len(data) + 0x10)

        output_data += bytearray(file_header)
        output_data += data

    if 'drum' in target_parts:
        output_filename = 'd%04d.sq2' % (json_sq2['musicid'])
    elif 'guitar' in target_parts or 'bass' in target_parts:
        output_filename = 'g%04d.sq2' % (json_sq2['musicid'])
    else:
        raise Exception("Unknown chart type")

    with open(os.path.join(output_folder, output_filename), "wb") as f:
        f.write(output_data)


def create_sound_files(json_sq2, params, target_parts):
    running_threads = []
    output_folder = params['output']

    # Make audio files here if sound_metadata exists?
    if 'sound_metadata' in json_sq2:
        if 'sound_folder' not in params:
            print("A sound folder must be specified using --sound-folder for this operation")
            exit(1)

        # Create sound archives
        if params.get('generate_bgms', False):
            output_bgm_filename = os.path.join(output_folder, 'bgm%04d___k.bin' % (json_sq2['musicid']))
            running_threads += create_bgm(json_sq2, params, output_bgm_filename)

            if 'guitar' in target_parts or 'bass' in target_parts:
                running_threads += create_bgm_render(json_sq2, params, ['bass'], os.path.join(output_folder, 'bgm%04d__bk.bin' % (json_sq2['musicid'])))
                running_threads += create_bgm_render(json_sq2, params, ['guitar', 'bass', 'open'], os.path.join(output_folder, 'bgm%04d_gbk.bin' % (json_sq2['musicid'])))

            if 'drum' in target_parts:
                running_threads += create_bgm_render(json_sq2, params, ['drum'], os.path.join(output_folder, 'bgm%04dd__k.bin' % (json_sq2['musicid'])))

            running_threads += create_bgm_render(json_sq2, params, ['drum', 'bass'], os.path.join(output_folder, 'bgm%04dd_bk.bin' % (json_sq2['musicid'])))

        else:
            if 'drum' in target_parts:
                running_threads += create_va3(json_sq2, params, 'drum')
                output_bgm_filename = os.path.join(output_folder, 'bgm%04d_gbk.bin' % (json_sq2['musicid']))

            elif 'guitar' in target_parts or 'bass' in target_parts:
                running_threads += create_va3(json_sq2, params, 'guitar')
                output_bgm_filename = os.path.join(output_folder, 'bgm%04dd__k.bin' % (json_sq2['musicid']))

            running_threads += create_bgm(json_sq2, params, output_bgm_filename)

        # Create preview files
        if 'preview' in json_sq2:
            running_threads += create_preview(json_sq2, params, 'dm')
            running_threads += create_preview(json_sq2, params, 'gf')

        if USE_THREADS:
            # Wait for threads to finish so the BGMs can be copied as required
            for thread in running_threads:
                thread.join()

        # Create missing BGMs if needed
        all_bgm_filenames = [
            os.path.join(output_folder, 'bgm%04d___k.bin' % (json_sq2['musicid'])),
            os.path.join(output_folder, 'bgm%04d__bk.bin' % (json_sq2['musicid'])),
            os.path.join(output_folder, 'bgm%04d_gbk.bin' % (json_sq2['musicid'])),
            os.path.join(output_folder, 'bgm%04dd__k.bin' % (json_sq2['musicid'])),
            os.path.join(output_folder, 'bgm%04dd_bk.bin' % (json_sq2['musicid'])),
        ]

        for alt_bgm_filename in all_bgm_filenames:
            if os.path.exists(alt_bgm_filename):
                continue

            if not os.path.exists(alt_bgm_filename):
                shutil.copy(output_bgm_filename, alt_bgm_filename)

    if USE_THREADS:
        for thread in running_threads:
            thread.join()


def generate_sq2_file_from_json(params):
    json_sq2 = json.loads(params['input']) if 'input' in params else None

    if not json_sq2:
        print("Couldn't find input data")
        return

    # Generate metadata charts for each chart
    chart_metadata = [x for x in json_sq2['charts'] if x['header']['is_metadata'] == 1]

    if len(chart_metadata) == 0:
        print("Couldn't find metadata chart")
        exit(1)

    output_folder = params['output']
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    parts = ["drum", "guitar", "bass", "open"]
    found_parts = []
    song_metadata_drum = {}
    song_metadata_guitar = {}
    for valid_parts in [['drum'], ['guitar', 'bass', 'open']]:
        metadata_chart = chart_metadata[0]

        filtered_charts = [
            generate_metadata_fields(metadata_chart, x) for x in json_sq2['charts']
            if x['header']['is_metadata'] == 0
            and x['header']['game_type'] < len(parts)
            and parts[x['header']['game_type']] in valid_parts
        ]

        found_parts += [parts[x['header']['game_type']] for x in json_sq2['charts'] if x['header']['is_metadata'] == 0]

        if len(filtered_charts) == 0:
            continue

        charts_data = [{
            'data': generate_sq2_chart_data_from_json(metadata_chart),
            'metadata': metadata_chart,
        }]

        charts_data += [{
            'data': generate_sq2_chart_data_from_json(x),
            'metadata': x
        } for x in filtered_charts]

        if 'drum' in valid_parts:
            song_metadata_drum = generate_song_metadata(filtered_charts)
        else:
            song_metadata_guitar = generate_song_metadata(filtered_charts)

        create_sq2_file(json_sq2, params, valid_parts, charts_data)
        #create_event_file(json_sq2, params, filtered_charts)

    found_parts = list(set(found_parts))

    if not params.get('no_sounds', False):
        create_sound_files(json_sq2, params, found_parts)

    song_metadata = song_metadata_drum if song_metadata_drum else song_metadata_guitar

    pre_image = song_metadata.get("pre_image", None)

    if pre_image and params.get('sound_folder', None):
        pre_image = os.path.join(params['sound_folder'], pre_image)
        pre_image_output = "pre" + os.path.splitext(pre_image)[-1]
        song_metadata['pre_image'] = pre_image_output

        pre_image_path = os.path.join(output_folder, pre_image_output)
        if os.path.exists(pre_image):
            shutil.copy(pre_image, pre_image_path)

    create_package_file(json_sq2, params, song_metadata_drum, song_metadata_guitar, found_parts)


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


def generate_sq2_chart_data_from_json(chart):
    metadata = True if chart['header']['is_metadata'] == 1 else False

    event_data = []
    found_events = []

    start_timestamp = int(get_start_timestamp(chart))
    end_timestamp = int(get_end_timestamp(chart))

    # Handle events based on beat offset in ascending order
    for timestamp_key in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        if int(timestamp_key) < start_timestamp or int(timestamp_key) > end_timestamp:
            continue

        for beat in chart['timestamp'][timestamp_key]:
            chart_events = [
                "chipstart",
                "chipend",
                "startpos",
                "endpos",
                "note",
                "auto"
            ]

            metadata_events = [
                "meta",
                "bpm",
                "barinfo",
                "baron",
                "baroff",
                "measure",
                "beat",
                "startpos",
                "endpos"
            ]

            if not metadata and beat['name'] not in chart_events:
                continue

            elif metadata and beat['name'] not in metadata_events:
                continue

            if beat['name'] in ["startpos", "endpos"] and EVENT_ID_REVERSE[beat['name']] in found_events:
                # Don't duplicate these events
                continue

            found_events.append(EVENT_ID_REVERSE[beat['name']])

            mdata = [0] * 0x10

            mdata[0x00:0x04] = struct.pack("<I", int(timestamp_key))
            mdata[0x05] = EVENT_ID_REVERSE[beat['name']] & 0xff

            if beat['name'] == "meta":
                # How to handle?
                pass
            elif beat['name'] == "bpm":
                mdata[0x08:0x0c] = struct.pack("<I", int(round(60000000 / beat['data']['bpm'])))

            elif beat['name'] == "barinfo":
                mdata[0x0c] = beat['data']['numerator'] & 0xff

                denominator = 1 << (beat['data']['denominator'].bit_length() - 1)
                if denominator != beat['data']['denominator']:
                    raise Exception("ERROR: The time signature denominator must be divisible by 2."
                                    "Found {}".format(beat['data']['denominator']))

                mdata[0x0d] = (beat['data']['denominator'].bit_length() - 1) & 0xff

            elif beat['name'] == "note":
                mdata[0x08:0x0A] = struct.pack("<H", beat['data'].get('sound_id', 0))
                mdata[0x0A:0x0c] = struct.pack("<H", beat['data'].get('sound_unk', 0))
                mdata[0x0c] = beat['data'].get('volume', 0) & 0xff

                if 'note' in beat['data']:
                    if REVERSE_NOTE_MAPPING[beat['data']['note']] == 0xff:
                        beat['name'] = "auto"
                        mdata[0x04] = 0
                        mdata[0x05] = EVENT_ID_REVERSE["auto"] & 0xff
                    else:
                        mdata[0x04] = REVERSE_NOTE_MAPPING[beat['data']['note']] & 0xff

            elif beat['name'] == "auto":
                mdata[0x04] = 0
                mdata[0x08:0x0A] = struct.pack("<H", beat['data'].get('sound_id', 0))
                mdata[0x0A:0x0c] = struct.pack("<H", beat['data'].get('sound_unk', 0))
                mdata[0x0c] = beat['data'].get('volume', 0) & 0xff

            event_data.append(bytearray(mdata))

    output_data = [0] * 0x20
    output_data[0x00:0x04] = b'SEQT'
    output_data[0x06] = 0x02  # SQ2 flag
    output_data[0x0a] = 0x01  # SQ2 flag 2?
    output_data[0x0c:0x10] = struct.pack("<I", 0x20)  # Size of header
    output_data[0x10:0x14] = struct.pack("<I", len(event_data))  # Number of events
    output_data[0x14] = chart['header']['unk_sys'] & 0xff
    output_data[0x15] = chart['header']['is_metadata'] & 0xff
    output_data[0x16] = chart['header']['difficulty'] & 0xff
    output_data[0x17] = chart['header']['game_type'] & 0xff

    if metadata:
        output_data[0x15] = 0x01
        output_data[0x16] = 0x01

    output_data = bytearray(output_data)
    for data in event_data:
        output_data += data

    return output_data


########################
#   SQ2 parsing code   #
########################
def parse_event_block(mdata, game, difficulty, events={}, is_metadata=False):
    packet_data = {}

    timestamp = struct.unpack("<I", mdata[0x00:0x04])[0]
    game_type_id = {"drum": 0, "guitar": 1, "bass": 2, "open": 3}[game]

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

    return {
        "id": mdata[0x04],
        "name": event_name,
        'timestamp': struct.unpack("<I", mdata[0x00:0x04])[0],
        "data": packet_data
    }


def read_sq2_data(data, events):
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
        part = ["drum", "guitar", "bass", "open"][game_type]
        parsed_data = parse_event_block(mdata, part, difficulty, events, is_metadata=is_metadata)
        output['beat_data'].append(parsed_data)

    return output


def convert_to_timestamp_chart(chart):
    chart['timestamp'] = {}

    for x in chart['beat_data']:
        if x['timestamp'] not in chart['timestamp']:
            chart['timestamp'][x['timestamp']] = []

        beat = x['timestamp']
        del x['timestamp']

        chart['timestamp'][beat].append(x)

    del chart['beat_data']

    return chart


def parse_chart_intermediate(chart, events):
    chart_raw = read_sq2_data(chart, events)

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

def generate_json_from_sq2(params):
    combine_guitars = params['merge_guitars'] if 'merge_guitars' in params else False
    data = open(params['input'], "rb").read() if 'input' in params else None
    events = params['events'] if 'events' in params else {}

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
        raw_charts.append(chart_data)
        data_offset += data_size

    output_data['musicid'] = musicid
    output_data['format'] = Sq2Format.get_format_name()

    charts = []
    for chart in raw_charts:
        parsed_chart = parse_chart_intermediate(chart, events)

        if not parsed_chart:
            continue

        game_type = ["drum", "guitar", "bass", "open"][parsed_chart['header']['game_type']]
        if game_type in ["guitar", "bass", "open"]:
            parsed_chart = add_note_durations(parsed_chart, params.get('sound_metadata', []))

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


class Sq2Format:
    @staticmethod
    def get_format_name():
        return "SQ2"

    @staticmethod
    def to_json(params):
        return generate_json_from_sq2(params)

    @staticmethod
    def to_chart(params):
        generate_sq2_file_from_json(params)

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
