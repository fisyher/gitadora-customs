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

drum_note_map = {
    0x00: "Hi-hat (left Blue)",
    0x01: "Snare (yellow)",
    0x02: "Bass pedal",
    0x03: "High tom (Green)",
    0x04: "Low tom (Red)",
    0x05: "Right cymbal (Right Blue)",
    0x06: "Left cymbal (Left Pink)",
    0x07: "Floor tom (Orange)",
    0x08: "Left pedal",
    0xff: "Auto"
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
    0x03: "Bass"
}

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
    # to be there (namely, beat markers for SQ3)

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


def create_preview(json_sq3, params, part):
    print("Creating preview file", part)

    running_threads = []
    output_folder = params['output']

    filename = os.path.join(output_folder,
                            "i%04d%s.bin" % (json_sq3['musicid'], part))

    if not os.path.exists(os.path.join(params['sound_folder'], json_sq3['preview'])):
        return []

    if USE_THREADS:
        bgm_thread = threading.Thread(target=wavbintool.parse_wav,
                                      args=(os.path.join(params['sound_folder'],
                                            json_sq3['preview']),
                                            filename))
        bgm_thread.start()
        running_threads.append(bgm_thread)
    else:
        wavbintool.parse_wav(os.path.join(params['sound_folder'],
                             json_sq3['preview']),
                             filename)

    return running_threads


def create_bgm_render(json_sq3, params, target_parts, output_bgm_filename):
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


def create_bgm(json_sq3, params, output_bgm_filename):
    def _create_bgm(bgm_filename, sound_folder, output_bgm_filename):
        # Create BGM file render
        merged_wav_filename = audio.merge_bgm(bgm_filename, sound_folder)
        wavbintool.parse_wav(merged_wav_filename, output_bgm_filename)

    print("Creating BGM file")

    running_threads = []

    if USE_THREADS:
        bgm_thread = threading.Thread(target=_create_bgm,
                                      args=(json_sq3['bgm'],
                                            params['sound_folder'],
                                            output_bgm_filename))
        bgm_thread.start()
        running_threads.append(bgm_thread)
    else:
        _create_bgm(json_sq3['bgm'], params['sound_folder'], output_bgm_filename)

    return running_threads


def create_va3(json_sq3, params, part):
    print("Creating VA3 archive")

    running_threads = []

    if part not in json_sq3['sound_metadata']:
        return []

    output_folder = params['output']

    va3_filename = "spu%04d%s.va3" % (json_sq3['musicid'], part[0])
    output_filename = os.path.join(output_folder, va3_filename)

    if USE_THREADS:
        va3_thread = threading.Thread(target=vas3tool.write_vas3,
                                      args=(params['sound_folder'],
                                            output_filename,
                                            json_sq3['sound_metadata'][part]))
        va3_thread.start()
        running_threads.append(va3_thread)
    else:
        vas3tool.write_vas3(params['sound_folder'],
                            output_filename,
                            json_sq3['sound_metadata'][part])

    return running_threads


def create_event_file(json_sq3, params, charts):
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
            E.musicid("{}".format(json_sq3['musicid']), __type="u32"),
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
    event_xml_filename = os.path.join(output_folder, "event%04d.ev2" % (json_sq3['musicid']))

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


def create_package_file(json_sq3, params, song_metadata_drum, song_metadata_guitar, parts):
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
            "event": "event%04d.ev2" % (json_sq3['musicid']),
            "bgm": {
                "___k": "bgm%04d___k.bin" % (json_sq3['musicid']),
                "__bk": "bgm%04d__bk.bin" % (json_sq3['musicid']),
                "_gbk": "bgm%04d_gbk.bin" % (json_sq3['musicid']),
                "d__k": "bgm%04dd__k.bin" % (json_sq3['musicid']),
                "d_bk": "bgm%04dd_bk.bin" % (json_sq3['musicid']),
            }
        },
        "graphics": {
            "jacket": song_metadata.get("pre_image", "pre.jpg"),
        },
        "notes": notes
    }

    if 'drum' in parts:
        package_info['files']['drum'] = {
            "seq": "d%04d.sq3" % (json_sq3['musicid']),
            "sound": "spu%04dd.va3" % (json_sq3['musicid']),
            "preview": "i%04ddm.bin" % (json_sq3['musicid']),
        }

    if 'guitar' in parts or 'bass' in parts or 'open' in parts:
        package_info['files']['guitar'] = {
            "seq": "g%04d.sq3" % (json_sq3['musicid']),
            "sound": "spu%04dg.va3" % (json_sq3['musicid']),
            "preview": "i%04dgf.bin" % (json_sq3['musicid']),
        }

    with open(os.path.join(output_folder, "package.json"), "w", encoding="utf-8") as f:
        json.dump(package_info, f, ensure_ascii=False, indent=4, separators=(', ', ': '))


def generate_song_metadata(charts):
    note_counts = {
        'drum': {},
        'guitar': {},
        'bass': {}
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
        }
    }

    pre_image = "jacket.png"

    for x in charts:
        game_type = ["drum", "guitar", "bass"][x['header']['game_type']]
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


def create_sq3_file(json_sq3, params, target_parts, charts_data):
    output_folder = params['output']

    # Create actual SQ3 data
    archive_size = 0x20 + (0x10 * len(charts_data)) + sum([len(x['data']) for x in charts_data])

    output_data = [0] * 0x20
    output_data[0x00:0x04] = b'SEQP'
    output_data[0x04] = 0x01
    output_data[0x06] = 0x01
    output_data[0x0a] = 0x03
    output_data[0x0c:0x10] = struct.pack("<I", archive_size)
    output_data[0x10:0x14] = struct.pack("<I", 0x20)  # Size of header
    output_data[0x14:0x18] = struct.pack("<I", json_sq3['musicid'])
    output_data[0x18:0x1c] = struct.pack("<I", len(charts_data))
    output_data[0x1c:0x20] = struct.pack("<I", 0x12345678)

    output_data = bytearray(output_data)
    for chart_data in charts_data:
        data = chart_data['data']

        file_header = [0] * 0x10
        file_header[0x00:0x04] = struct.pack("<I", len(data) + 0x10)
        file_header[0x04] = 0x10

        output_data += bytearray(file_header)
        output_data += data

    if 'drum' in target_parts:
        output_filename = 'd%04d.sq3' % (json_sq3['musicid'])
    elif 'guitar' in target_parts or 'bass' in target_parts:
        output_filename = 'g%04d.sq3' % (json_sq3['musicid'])
    else:
        raise Exception("Unknown chart type")

    with open(os.path.join(output_folder, output_filename), "wb") as f:
        f.write(output_data)


def create_sound_files(json_sq3, params, target_parts):
    running_threads = []
    output_folder = params['output']

    # Make audio files here if sound_metadata exists?
    if 'sound_metadata' in json_sq3:
        if 'sound_folder' not in params:
            print("A sound folder must be specified using --sound-folder for this operation")
            exit(1)

        # Create sound archives
        output_bgm_filename = os.path.join(output_folder, 'bgm%04d___k.bin' % (json_sq3['musicid']))
        running_threads += create_bgm(json_sq3, params, output_bgm_filename)

        if params.get('generate_bgms', False):
            if 'guitar' in target_parts or 'bass' in target_parts:
                running_threads += create_bgm_render(json_sq3, params, ['bass'], os.path.join(output_folder, 'bgm%04d__bk.bin' % (json_sq3['musicid'])))
                running_threads += create_bgm_render(json_sq3, params, ['guitar', 'bass', 'open'], os.path.join(output_folder, 'bgm%04d_gbk.bin' % (json_sq3['musicid'])))

            if 'drum' in target_parts:
                running_threads += create_bgm_render(json_sq3, params, ['drum'], os.path.join(output_folder, 'bgm%04dd__k.bin' % (json_sq3['musicid'])))

            running_threads += create_bgm_render(json_sq3, params, ['drum', 'bass'], os.path.join(output_folder, 'bgm%04dd_bk.bin' % (json_sq3['musicid'])))

        if 'drum' in target_parts:
            running_threads += create_va3(json_sq3, params, 'drum')

        elif 'guitar' in target_parts or 'bass' in target_parts:
            running_threads += create_va3(json_sq3, params, 'guitar')

        # Create preview files
        if json_sq3.get('preview', None):
            running_threads += create_preview(json_sq3, params, 'dm')
            running_threads += create_preview(json_sq3, params, 'gf')

        if USE_THREADS:
            # Wait for threads to finish so the BGMs can be copied as required
            for thread in running_threads:
                thread.join()

        # Create missing BGMs if needed
        all_bgm_filenames = [
            os.path.join(output_folder, 'bgm%04d___k.bin' % (json_sq3['musicid'])),
            os.path.join(output_folder, 'bgm%04d__bk.bin' % (json_sq3['musicid'])),
            os.path.join(output_folder, 'bgm%04d_gbk.bin' % (json_sq3['musicid'])),
            os.path.join(output_folder, 'bgm%04dd__k.bin' % (json_sq3['musicid'])),
            os.path.join(output_folder, 'bgm%04dd_bk.bin' % (json_sq3['musicid'])),
        ]

        for alt_bgm_filename in all_bgm_filenames:
            if os.path.exists(alt_bgm_filename):
                continue

            if not os.path.exists(alt_bgm_filename):
                shutil.copy(output_bgm_filename, alt_bgm_filename)

    if USE_THREADS:
        for thread in running_threads:
            thread.join()


def generate_sq3_file_from_json(params):
    json_sq3 = json.loads(params['input']) if 'input' in params else None

    if not json_sq3:
        print("Couldn't find input data")
        return

    # Generate metadata charts for each chart
    chart_metadata = [x for x in json_sq3['charts'] if x['header']['is_metadata'] == 1]

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
            generate_metadata_fields(metadata_chart, x) for x in json_sq3['charts']
            if x['header']['is_metadata'] == 0
            and x['header']['game_type'] < len(parts)
            and parts[x['header']['game_type']] in valid_parts
        ]

        found_parts += [parts[x['header']['game_type']] for x in json_sq3['charts'] if x['header']['is_metadata'] == 0]

        if len(filtered_charts) == 0:
            continue

        charts_data = [{
            'data': generate_sq3_chart_data_from_json(metadata_chart),
            'metadata': metadata_chart,
        }]

        charts_data += [{
            'data': generate_sq3_chart_data_from_json(x),
            'metadata': x
        } for x in filtered_charts]

        if 'drum' in valid_parts:
            song_metadata_drum = generate_song_metadata(filtered_charts)
        else:
            song_metadata_guitar = generate_song_metadata(filtered_charts)

        create_sq3_file(json_sq3, params, valid_parts, charts_data)
        create_event_file(json_sq3, params, filtered_charts)

    found_parts = list(set(found_parts))

    if not params.get('no_sounds', False):
        create_sound_files(json_sq3, params, found_parts)

    song_metadata = song_metadata_drum if song_metadata_drum else song_metadata_guitar

    pre_image = song_metadata.get("pre_image", None)

    if pre_image and params.get('sound_folder', None):
        pre_image = os.path.join(params['sound_folder'], pre_image)
        pre_image_output = "pre" + os.path.splitext(pre_image)[-1]
        song_metadata['pre_image'] = pre_image_output

        pre_image_path = os.path.join(output_folder, pre_image_output)
        if os.path.exists(pre_image):
            shutil.copy(pre_image, pre_image_path)

    create_package_file(json_sq3, params, song_metadata_drum, song_metadata_guitar, found_parts)


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


def generate_sq3_chart_data_from_json(chart):
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
                "note"
            ]

            metadata_events = [
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

            mdata = [0] * 0x40  # Use proper section size here

            mdata[0x00:0x04] = struct.pack("<I", int(timestamp_key))
            mdata[0x04] = EVENT_ID_REVERSE[beat['name']] & 0xff
            mdata[0x10:0x14] = struct.pack("<I", beat['beat'])

            if beat['name'] == "bpm":
                mdata[0x34:0x38] = struct.pack("<I", int(round(60000000 / beat['data']['bpm'])))
            elif beat['name'] == "barinfo":
                mdata[0x34] = beat['data']['numerator'] & 0xff

                denominator = 1 << (beat['data']['denominator'].bit_length() - 1)
                if denominator != beat['data']['denominator']:
                    raise Exception("ERROR: The time signature denominator must be divisible by 2."
                                    "Found {}".format(beat['data']['denominator']))

                mdata[0x35] = (beat['data']['denominator'].bit_length() - 1) & 0xff
            elif beat['name'] == "chipstart":
                if 'unk' in beat['data']:
                    mdata[0x14:0x18] = struct.pack("<I", beat['data']['unk'])
            elif beat['name'] == "note":
                if beat['data']['note'] not in REVERSE_NOTE_MAPPING:
                    # Set all unknown events to auto play
                    REVERSE_NOTE_MAPPING[beat['data']['note']] = 0xff

                if 'hold_duration' in beat['data']:
                    mdata[0x08:0x0c] = struct.pack("<I", beat['data']['hold_duration'])

                if 'unk' in beat['data']:
                    mdata[0x14:0x18] = struct.pack("<I", beat['data']['unk'])
                else:
                    mdata[0x14:0x18] = struct.pack("<I", 0x16c)

                if 'sound_id' in beat['data']:
                    mdata[0x20:0x24] = struct.pack("<I", beat['data']['sound_id'])

                if chart['header']['game_type'] != 0:
                    if 'note_length' in beat['data']:
                        mdata[0x24:0x28] = struct.pack("<I", beat['data']['note_length'])
                    else:
                        mdata[0x24:0x28] = struct.pack("<I", 0x40)

                if 'volume' in beat['data']:
                    mdata[0x2d] = beat['data']['volume'] & 0xff

                if 'auto_volume' in beat['data']:
                    mdata[0x2e] = beat['data']['auto_volume'] & 0xff

                if 'note' in beat['data']:
                    mdata[0x30] = REVERSE_NOTE_MAPPING[beat['data']['note']] & 0xff

                if 'wail_misc' in beat['data']:
                    mdata[0x31] = beat['data']['wail_misc'] & 0xff

                if 'guitar_special' in beat['data']:
                    mdata[0x32] = beat['data']['guitar_special'] & 0xff

                if 'auto_note' in beat['data']:
                    mdata[0x34] = beat['data']['auto_note'] & 0xff

                if beat['data'].get('note') == "auto":
                    mdata[0x34] = 1  # Auto note
                    mdata[0x2e] = 1  # Auto volume

            event_data.append(bytearray(mdata))

    output_data = [0] * 0x20
    output_data[0x00:0x04] = b'SQ3T'
    output_data[0x06] = 0x03  # SQ3 flag
    output_data[0x0a] = 0x03  # SQ3 flag 2?
    output_data[0x0c:0x10] = struct.pack("<I", 0x20)  # Size of header
    output_data[0x10:0x14] = struct.pack("<I", len(event_data))  # Number of events
    output_data[0x14] = chart['header']['unk_sys'] & 0xff
    output_data[0x15] = chart['header']['is_metadata'] & 0xff
    output_data[0x16] = chart['header']['difficulty'] & 0xff
    output_data[0x17] = chart['header']['game_type'] & 0xff
    output_data[0x18:0x1a] = struct.pack("<H", chart['header']['time_division'])
    output_data[0x1a:0x1c] = struct.pack("<H", chart['header']['beat_division'])
    output_data[0x1c:0x20] = struct.pack("<I", 0x40)  # Size of each entry

    if metadata:
        output_data[0x15] = 0x01
        output_data[0x16] = 0x01

    output_data = bytearray(output_data)
    for data in event_data:
        output_data += data

    return output_data


########################
#   SQ3 parsing code   #
########################

def parse_event_block(mdata, game, difficulty, events={}):
    packet_data = {}

    timestamp = struct.unpack("<I", mdata[0x00:0x04])[0]
    beat = struct.unpack("<I", mdata[0x10:0x14])[0]
    game_type_id = {"drum": 0, "guitar": 1, "bass": 2, "open": 3}[game]

    if mdata[0x04] == 0x01:
        bpm_mpm = struct.unpack("<I", mdata[0x34:0x38])[0]
        packet_data['bpm'] = 60000000 / bpm_mpm
    elif mdata[0x04] == 0x02:
        # Time signature is represented as numerator/(1<<denominator)
        packet_data['numerator'] = mdata[0x34]
        packet_data['denominator'] = 1 << mdata[0x35]
        packet_data['denominator_orig'] = mdata[0x35]
    elif mdata[0x04] == 0x07:
        packet_data['unk'] = struct.unpack("<I", mdata[0x14:0x18])[0]  # What is this?
    elif mdata[0x04] == 0x10:
        packet_data['hold_duration'] = struct.unpack("<I", mdata[0x08:0x0c])[0]
        packet_data['unk'] = struct.unpack("<I", mdata[0x14:0x18])[0]  # What is this?
        packet_data['sound_id'] = struct.unpack("<I", mdata[0x20:0x24])[0]

        # Note length (relation to hold duration)
        packet_data['note_length'] = struct.unpack("<I", mdata[0x24:0x28])[0]

        packet_data['volume'] = mdata[0x2d]
        packet_data['auto_volume'] = mdata[0x2e]
        packet_data['note'] = NOTE_MAPPING[game][mdata[0x30]]

        # wail direction? 0/1 = up, 2 = down. Seems to alternate 0 and 1 if wailing in succession
        packet_data['wail_misc'] = mdata[0x31]

        # 2 = hold note, 1 = wail (bitmasks, so 3 = wail + hold)
        packet_data['guitar_special'] = mdata[0x32]

        # Auto note
        packet_data['auto_note'] = mdata[0x34]

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

    return {
        "id": mdata[0x04],
        "name": EVENT_ID_MAP[mdata[0x04]],
        'timestamp': struct.unpack("<I", mdata[0x00:0x04])[0],
        'beat': beat,
        "data": packet_data
    }


def read_sq3_data(data, events):
    output = {
        "beat_data": []
    }

    if data is None:
        return None

    magic = data[0:4]
    if magic != bytearray("SQ3T", encoding="ascii"):
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
        parsed_data = parse_event_block(mdata, part, difficulty, events)
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
    chart_raw = read_sq3_data(chart, events)

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

        game_type = ["drum", "guitar", "bass"][chart['header']['game_type']]

        if 'title' in song_info:
            charts[chart_idx]['header']['title'] = song_info['title']

        if 'artist' in song_info:
            charts[chart_idx]['header']['artist'] = song_info['artist']

        if 'difficulty' in song_info:
            diff_idx = (chart['header']['game_type'] * 5) + chart['header']['difficulty']
            charts[chart_idx]['header']['level'] = {
                game_type: int(song_info['difficulty'][diff_idx])
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

        part = ["drum", "guitar", "bass"][chart['header']['game_type']]
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

    for chart in charts:
        if chart['header']['is_metadata'] != 0:
            continue

        game_type = ["drum", "guitar", "bass"][chart['header']['game_type']]
        if game_type == "guitar":
            guitar_charts.append(chart)
        elif game_type == "bass":
            bass_charts.append(chart)

    # Remove charts from chart list
    for chart in guitar_charts:
        charts.remove(chart)

    for chart in bass_charts:
        charts.remove(chart)

    return charts, guitar_charts, bass_charts


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

            # Add all bass notes to guitar chart data
            for timestamp_key in chart2['timestamp']:
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


def generate_json_from_sq3(params):
    combine_guitars = params['merge_guitars'] if 'merge_guitars' in params else False
    data = open(params['input'], "rb").read() if 'input' in params else None
    events = params['events'] if 'events' in params else {}

    if not data:
        print("No input file data")
        return

    output_data = {}

    magic = data[0:4]
    if magic != bytearray("SEQP", encoding="ascii"):
        print("Not a valid SEQ3 file")
        exit(-1)

    data_offset, musicid, num_charts = struct.unpack("<III", data[0x10:0x1c])

    raw_charts = []
    for i in range(num_charts):
        data_size = struct.unpack("<I", data[data_offset:data_offset+4])[0]
        chart_data = data[data_offset+0x10:data_offset+0x10+data_size]
        raw_charts.append(chart_data)
        data_offset += data_size

    output_data['musicid'] = musicid
    output_data['format'] = Sq3Format.get_format_name()

    charts = []
    for chart in raw_charts:
        parsed_chart = parse_chart_intermediate(chart, events)

        if not parsed_chart:
            continue

        charts.append(parsed_chart)
        charts[-1]['header']['musicid'] = musicid

    charts = add_song_info(charts, musicid, params['musicdb'])
    charts = filter_charts(charts, params)
    charts, guitar_charts, bass_charts = split_charts_by_parts(charts)

    if combine_guitars:
        guitar_charts, bass_charts = combine_guitar_charts(guitar_charts, bass_charts)

    # Merge all charts back together after filtering, merging guitars etc
    charts += guitar_charts
    charts += bass_charts

    output_data['charts'] = charts

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
        generate_sq3_file_from_json(params)

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
