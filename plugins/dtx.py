# Docs:
# https://osdn.net/projects/dtxmania/wiki/DTX%20data%20format
# https://osdn.net/projects/dtxmania/wiki/%E3%83%81%E3%83%A3%E3%83%B3%E3%83%8D%E3%83%AB%E5%AE%9A%E7%BE%A9%E8%A1%A8

# Auto lane override details: https://osdn.net/projects/dtxmania/ticket/26338

# Unsupported DTX commands:
# GENRE
# COMMENT
# PANEL
# HIDDENLEVEL
# STAGEFILE
# PREMOVIE
# BACKGROUND
# BACKGROUND_GR
# WALL
# BMP
# SOUND_NOWLOADING
# SOUND_STAGEFAILED
# SOUND_FULLCOMBO
# SOUND_AUDIENCE
# RESULTIMAGE
# RESULTIMAGE_xx
# RESULTMOVIE
# RESULTMOVIE_xx
# RESULTSOUND
# RESULTSOUND_xx
# SIZEzz
# BMPzz
# BMPTEXzz
# BGAzz
# BGAPANzz
# AVIzz
# VIDEOzz
# AVIPANzz
# MIDINOTE
# RANDOM
# IF
# DTXVPLAYSPEED
# USE556X710BGAAVI
# MIDIFILE
# BLACKCOLORKEY


import copy
from fractions import Fraction
import json
import math
from numpy import base_repr
import os
import re

import audio

dtx_bonus_mapping = {
    "leftcymbal": 0x01,
    "hihat": 0x02,
    "leftpedal": 0x03,
    "snare": 0x04,
    "hightom": 0x05,
    "bass": 0x06,
    "lowtom": 0x07,
    "floortom": 0x08,
    "rightcymbal": 0x09,
}

drum_mapping = {
    "hihat": 0x11,
    "snare": 0x12,
    "bass": 0x13,
    "hightom": 0x14,
    "lowtom": 0x15,
    "rightcymbal": 0x16,
    "floortom": 0x17,
    "leftcymbal": 0x1a,
    "leftpedal": 0x1b,
}

guitar_mapping = {
    "g_open": 0x20,
    "g_xxbxx": 0x21,
    "g_xgxxx": 0x22,
    "g_xgbxx": 0x23,
    "g_rxxxx": 0x24,
    "g_rxbxx": 0x25,
    "g_rgxxx": 0x26,
    "g_rgbxx": 0x27,
    "g_xxb": 0x21,
    "g_xgx": 0x22,
    "g_xgb": 0x23,
    "g_rxx": 0x24,
    "g_rxb": 0x25,
    "g_rgx": 0x26,
    "g_rgb": 0x27,
    "g_xxxyx": 0x93,
    "g_xxbyx": 0x94,
    "g_xgxyx": 0x95,
    "g_xgbyx": 0x96,
    "g_rxxyx": 0x97,
    "g_rxbyx": 0x98,
    "g_rgxyx": 0x99,
    "g_rgbyx": 0x9a,
    "g_xxxxp": 0x9b,
    "g_xxbxp": 0x9c,
    "g_xgxxp": 0x9d,
    "g_xgbxp": 0x9e,
    "g_rxxxp": 0x9f,
    "g_rxbxp": 0xa9,
    "g_rgxxp": 0xaa,
    "g_rgbxp": 0xab,
    "g_xxxyp": 0xac,
    "g_xxbyp": 0xad,
    "g_xgxyp": 0xae,
    "g_xgbyp": 0xaf,
    "g_rxxyp": 0xd0,
    "g_rxbyp": 0xd1,
    "g_rgxyp": 0xd2,
    "g_rgbyp": 0xd3,
}

bass_mapping = {
    "b_open": 0xa0,
    "b_xxbxx": 0xa1,
    "b_xgxxx": 0xa2,
    "b_xgbxx": 0xa3,
    "b_rxxxx": 0xa4,
    "b_rxbxx": 0xa5,
    "b_rgxxx": 0xa6,
    "b_rgbxx": 0xa7,
    "b_xxb": 0xa1,
    "b_xgx": 0xa2,
    "b_xgb": 0xa3,
    "b_rxx": 0xa4,
    "b_rxb": 0xa5,
    "b_rgx": 0xa6,
    "b_rgb": 0xa7,
    "b_xxxyx": 0xc5,
    "b_xxbyx": 0xc6,
    "b_xgxyx": 0xc8,
    "b_xgbyx": 0xc9,
    "b_rxxyx": 0xca,
    "b_rxbyx": 0xcb,
    "b_rgxyx": 0xcc,
    "b_rgbyx": 0xcd,
    "b_xxxxp": 0xce,
    "b_xxbxp": 0xcf,
    "b_xgxxp": 0xda,
    "b_xgbxp": 0xdb,
    "b_rxxxp": 0xdc,
    "b_rxbxp": 0xdd,
    "b_rgxxp": 0xde,
    "b_rgbxp": 0xdf,
    "b_xxxyp": 0xe1,
    "b_xxbyp": 0xe2,
    "b_xgxyp": 0xe3,
    "b_xgbyp": 0xe4,
    "b_rxxyp": 0xe5,
    "b_rxbyp": 0xe6,
    "b_rgxyp": 0xe7,
    "b_rgbyp": 0xe8,
}

dtx_mapping = {
    "auto": 0x61,
}
dtx_mapping.update(drum_mapping)
dtx_mapping.update(guitar_mapping)
dtx_mapping.update(bass_mapping)

reverse_dtx_mapping = {dtx_mapping[k]: k for k in dtx_mapping if k != "auto"}
reverse_dtx_mapping[0x1c] = "leftpedal"  # Because there are multiple mappings for the left pedal
reverse_dtx_mapping[0x18] = "hihat"  # Because there are multiple mappings for hihat

# TODO: How to handle ride? For now, just put it as an auto field
reverse_dtx_mapping[0x19] = "auto"  # RideCymbal

# For default note chips
reverse_dtx_mapping[0xb1] = "hihat"
reverse_dtx_mapping[0xb2] = "snare"
reverse_dtx_mapping[0xb3] = "bass"
reverse_dtx_mapping[0xb4] = "hightom"
reverse_dtx_mapping[0xb5] = "lowtom"
reverse_dtx_mapping[0xb6] = "rightcymbal"
reverse_dtx_mapping[0xb7] = "floortom"
reverse_dtx_mapping[0xb8] = "hihat"
reverse_dtx_mapping[0xbc] = "leftcymbal"
reverse_dtx_mapping[0xbd] = "leftpedal"
reverse_dtx_mapping[0xbe] = "leftpedal"

auto_play_ranges = list(range(0x61, 0x69 + 1)) + \
    list(range(0x70, 0x79 + 1)) + \
    list(range(0x80, 0x89 + 1)) + \
    list(range(0x90, 0x92 + 1))

default_note_events = list(range(0xb1, 0xb8 + 1)) + \
    list(range(0xbc, 0xbf + 1))  # b9 = ride, but we can't use the ride

drum_range = list(range(0x11, 0x1b + 1))

guitar_range = list(range(0x20, 0x27 + 1)) + \
    list(range(0x93, 0x9f + 1)) + \
    list(range(0xa9, 0xaf + 1)) + \
    list(range(0xd0, 0xd3 + 1))

bass_range = list(range(0xa0, 0xa7 + 1)) + \
    list(range(0xc5, 0xcf + 1)) + \
    list(range(0xda, 0xe8 + 1))


# This is similar to Fraction, except it won't
# try to reduce the fraction.
class Fraction2:
    numerator = 4
    denominator = 4
    denominator_orig = 2

    def __init__(self, numerator, denominator):
        self.numerator = numerator
        self.denominator = denominator

        bits = "{0:b}".format(denominator)

        if len(bits.replace("0","")) > 1:
            print("Denominator %d is not a valid power of 2" % denominator)
            exit(1)

        if '1' in bits:
            self.denominator_orig = len(bits) - 1
        else:
            self.denominator_orig = 0


    def __str__(self):
        return "%d/%d" % (self.numerator, self.denominator)


########################
#   DTX reading code   #
########################

def get_value_from_dtx(target_tag, lines, default=None):
    for line in lines:
        matches = re.match(r"#(?P<tag>[A-Za-z0-9]+):?\s*(?P<value>.*)", line)

        if not matches:
            continue

        tag = matches.group('tag').upper()
        value = matches.group('value')

        if tag.startswith(target_tag):
            return value

    return default


def get_bpms_from_dtx(lines):
    bpms = {}
    base_bpm = 0

    for line in lines:
        matches = re.match(r"#(?P<tag>[A-Za-z0-9]+):?\s*(?P<value>.*)", line)

        if not matches:
            continue

        tag = matches.group('tag').upper()
        value = matches.group('value')

        if tag.startswith("BPM"):
            matches2 = re.match("BPM(?P<id>[0-9A-Z]{2})?", tag)

            if not matches2:
                pass

            bpm_id = matches2.group('id')

            if bpm_id:
                bpm_id = int(bpm_id, 36)
            else:
                bpm_id = 0

            bpms[bpm_id] = float(value)

        elif tag.startswith("BASEBPM"):
            base_bpm = float(value)

    return bpms, base_bpm


def get_wavs_from_dtx(lines, target_parts, sound_metadata, get_wav_length=True):
    wav_filenames = {}
    wav_lengths = {}

    for line in lines:
        if ';' in line:
            line = line[:line.index(';')].strip()

        matches = re.match(r"#(?P<tag>[A-Za-z0-9]+):?\s*(?P<value>.*)", line)

        if not matches:
            continue

        tag = matches.group('tag').upper()
        value = matches.group('value')

        if tag.startswith("WAV") and not tag.startswith("WAVPAN") and not tag.startswith("WAVVOL"):
            # Handle WAV tags
            # This can be exported for use by va3 creator

            matches2 = re.match("WAV(?P<id>[0-9A-Z]{2})?", tag)

            if not matches2:
                pass

            wav_id = matches2.group('id')

            if wav_id:
                wav_id = int(wav_id, 36)
            else:
                wav_id = 0

            wav_filenames[wav_id] = os.sep.join(value.split('\\'))

            if get_wav_length and ('guitar' in target_parts or 'bass' in target_parts or 'open' in target_parts):
                duration = audio.get_duration(os.path.join(sound_metadata['sound_folder'], value))
                wav_lengths[wav_id] = int(round(duration * 300))
            else:
                wav_lengths[wav_id] = 0

    return wav_filenames, wav_lengths


def get_wav_volumes_from_dtx(lines):
    wav_volumes = {}

    for line in lines:
        matches = re.match(r"#(?P<tag>[A-Za-z0-9]+):?\s*(?P<value>.*)", line)

        if not matches:
            continue

        tag = matches.group('tag').upper()
        value = matches.group('value')

        if tag.startswith("VOLUME"):
            valid_tag = "VOLUME"
        elif tag.startswith("WAVVOL"):
            valid_tag = "WAVVOL"
        else:
            valid_tag = None

        if valid_tag:
            # Handle VOLUME tags
            # This can be exported for use by va3 creator

            matches2 = re.match(valid_tag + "(?P<id>[0-9A-Z]{2})?", tag)

            if not matches2:
                pass

            vol_id = matches2.group('id')

            if vol_id:
                vol_id = int(vol_id, 36)
            else:
                vol_id = 0

            wav_volumes[vol_id] = int(value)

    return wav_volumes


def get_wav_pans_from_dtx(lines):
    wav_pans = {}

    for line in lines:
        matches = re.match(r"#(?P<tag>[A-Za-z0-9]+):?\s*(?P<value>.*)", line)

        if not matches:
            continue

        tag = matches.group('tag').upper()
        value = matches.group('value')

        if tag.startswith("PAN"):
            valid_tag = "PAN"
        elif tag.startswith("WAVPAN"):
            valid_tag = "WAVPAN"
        else:
            valid_tag = None


        if valid_tag:
            # Handle PAN tags
            # This can be exported for use by va3 creator

            matches2 = re.match(valid_tag + "(?P<id>[0-9A-Z]{2})?", tag)

            if not matches2:
                pass

            pan_id = matches2.group('id')

            if pan_id:
                pan_id = int(pan_id, 36)
            else:
                pan_id = 0

            wav_pans[pan_id] = int(value)

    return wav_pans


def get_bonus_notes_from_dtx(lines, start_offset_padding):
    bonus_notes = {}

    for line in lines:
        matches = re.match(r"#(?P<tag>[A-Za-z0-9]+):?\s*(?P<value>.*)", line)

        if not matches:
            continue

        tag = matches.group('tag').upper()
        value = matches.group('value')

        if tag[0].isdigit():
            matches2 = re.match("(?P<measure>[0-9]{3})(?P<event>[0-9A-F]{2})", tag)

            if not matches2:
                pass

            measure = int(matches2.group('measure')) + start_offset_padding
            event = int(matches2.group('event'), 16)

            if event in [0x4c, 0x4d, 0x4e, 0x4f]:  # Bonus notes
                data = [value[i:i+2] for i in range(0, len(value), 2)]
                for i in range(len(data)):
                    if measure not in bonus_notes:
                        bonus_notes[measure] = {}

                    if i not in bonus_notes[measure]:
                        bonus_notes[measure][i] = []

                    bonus_notes[measure][i].append(int(data[i], 36))

    return bonus_notes


def get_measure_lengths_from_dtx(lines, start_offset_padding):
    VALID_TIMESIG_DENOMINATORS = [1 << x for x in range(0, 256)]

    measure_lengths = {}

    for line in lines:
        matches = re.match(r"#(?P<tag>[A-Za-z0-9]+):?\s*(?P<value>.*)", line)

        if not matches:
            continue

        tag = matches.group('tag').upper()
        value = matches.group('value')

        if tag[0].isdigit():
            matches2 = re.match("(?P<measure>[0-9]{3})(?P<event>[0-9A-F]{2})", tag)

            if not matches2:
                pass

            measure = int(matches2.group('measure')) + start_offset_padding
            event = int(matches2.group('event'), 16)

            if event != 0x02:
                continue

            # Measure length event
            f1 = Fraction(float(value)).limit_denominator()
            numerator = f1.numerator
            denominator = f1.denominator

            # How to code this?
            if denominator == 1:
                numerator *= 4
                denominator = 4
            elif denominator == 2:
                numerator *= 2
                denominator = 4

            f2 = Fraction2(numerator, denominator)

            # Add check for impossible time signatures
            if denominator not in VALID_TIMESIG_DENOMINATORS:
                print("ERROR: This is an impossible to represent"
                      "time signature: {}".format(value))
                print("This came out to be", f2)
                print("Valid denominators for the time signature"
                      "must be a power of two...", VALID_TIMESIG_DENOMINATORS[:12])
                print("Please try simplifying all measures which"
                      "use the measure length {}".format(value))
                exit(1)

            measure_lengths[measure] = f2

    if 0 not in measure_lengths:
        measure_lengths[0] = Fraction2(4, 4)  # Default to 4/4

    return measure_lengths


def get_events_by_measure_from_dtx(lines, start_offset_padding):
    events_by_measure = {}

    for line in lines:
        matches = re.match(r"#(?P<tag>[A-Za-z0-9]+):?\s*(?P<value>.*)", line)

        if not matches:
            continue

        tag = matches.group('tag').upper()
        value = matches.group('value')

        if tag[0].isdigit():
            matches2 = re.match("(?P<measure>[0-9]{3})(?P<event>[0-9A-F]{2})", tag)

            if not matches2:
                pass

            measure = int(matches2.group('measure')) + start_offset_padding
            event = int(matches2.group('event'), 16)

            if event == 0x02:
                continue

            # Handle specific events
            if measure not in events_by_measure:
                events_by_measure[measure] = {}

            events_by_measure[measure][event] = [value[i:i+2] for i in range(0, len(value), 2)]

    return events_by_measure


def pad_events(events_by_measure, measure_lengths):
    # Pad all measures to appropriate sizes
    for measure in events_by_measure:
        for event in events_by_measure[measure]:
            scale = Fraction(4, 4)

            measure_lengths_keys = sorted(measure_lengths.keys(), key=lambda x: int(x))
            matched_measures = [x for x in measure_lengths_keys if int(x) <= measure]

            if len(matched_measures) > 0:
                scale = measure_lengths[matched_measures[-1]]

            event_count = len(events_by_measure[measure][event])
            beat_division = (1920 / scale.denominator) * scale.numerator

            new_chips = []
            for i in range(len(events_by_measure[measure][event])):
                c = events_by_measure[measure][event][i]

                new_chips.append(c)
                new_chips += ['00'] * (int(beat_division / len(events_by_measure[measure][event])) - 1)

            events_by_measure[measure][event] = new_chips

    return events_by_measure


def get_bpms_at_measure_beat(events, bpms):
    bpms_at_measure_beat = {}

    for measure in events:
        if 0x08 in events[measure]:
            for i in range(len(events[measure][0x08])):
                if events[measure][0x08][i] != "00":
                    if measure not in bpms_at_measure_beat:
                        bpms_at_measure_beat[measure] = {}

                    if i not in bpms_at_measure_beat[measure]:
                        bpms_at_measure_beat[measure][i] = {}

                    val = int(events[measure][0x08][i], 36)
                    bpms_at_measure_beat[measure][i] = bpms[val]

    if 0 not in bpms_at_measure_beat:
        bpms_at_measure_beat[0] = {0: bpms[0]}

    return bpms_at_measure_beat


def get_guitar_long_notes_at_measure_beat(events):
    guitar_long_notes_at_measure_beat = {}

    for measure in events:
        if 0x2a in events[measure]:
            for i in range(len(events[measure][0x2a])):
                if events[measure][0x2a][i] != "00":
                    if measure not in guitar_long_notes_at_measure_beat:
                        guitar_long_notes_at_measure_beat[measure] = {}

                    guitar_long_notes_at_measure_beat[measure][i] = True

    return guitar_long_notes_at_measure_beat


def get_bass_long_notes_at_measure_beat(events):
    bass_long_notes_at_measure_beat = {}

    for measure in events:
        if 0x2b in events[measure]:
            for i in range(len(events[measure][0x2b])):
                if events[measure][0x2b][i] != "00":
                    if measure not in bass_long_notes_at_measure_beat:
                        bass_long_notes_at_measure_beat[measure] = {}

                    bass_long_notes_at_measure_beat[measure][i] = True

    return bass_long_notes_at_measure_beat


def get_notes_by_measure_beat(events):
    notes_by_measure_beat = {}

    for measure in events:
        for event in events[measure]:
            if event in guitar_range or event in bass_range:
                for i in range(len(events[measure][event])):
                    if events[measure][event][i] != "00":
                        if measure not in notes_by_measure_beat:
                            notes_by_measure_beat[measure] = {}

                        if event in guitar_range:
                            notes_by_measure_beat[measure][i] = 1
                        elif event in bass_range:
                            notes_by_measure_beat[measure][i] = 2
                        else:
                            notes_by_measure_beat[measure][i] = 0

    return notes_by_measure_beat


def get_long_note_time_by_measure_beat(events_by_measure, long_notes_at_measure_beat, part):
    long_note_time_by_measure_beat = {}

    notes_by_measure_beat = get_notes_by_measure_beat(events_by_measure)

    for measure in long_notes_at_measure_beat:
        for beat in long_notes_at_measure_beat[measure]:
            if measure in notes_by_measure_beat:
                note_beats = [
                    note_beat
                    for note_beat in notes_by_measure_beat[measure]
                    if note_beat < beat
                ]
                last_note = (measure, sorted(note_beats)[-1])
            else:
                m = measure
                while m > 0 and m not in notes_by_measure_beat:
                    m -= 1

                note_beats = [note_beat for note_beat in notes_by_measure_beat[m]]
                last_note = (m, sorted(note_beats)[-1])

            if last_note[0] not in long_note_time_by_measure_beat:
                long_note_time_by_measure_beat[last_note[0]] = {}

            if notes_by_measure_beat[last_note[0]][last_note[1]] == part:
                long_note_time_by_measure_beat[last_note[0]][last_note[1]] = (measure, beat)

    return long_note_time_by_measure_beat


def generate_sound_metadata_map(sound_metadata, wav_filenames, wav_volumes, wav_pans, target_id=30):
    sound_metadata_map = {}

    for wav_id in wav_filenames:
        while target_id in sound_metadata['data']:
            target_id += 1

        md = {
            "sound_id": target_id,
            "filename": wav_filenames[wav_id],
            "volume": 127,  # Max
            "pan": 64  # Center
        }

        # Volume is broken for drum archives? Too many files causes things to crash
        if wav_id in wav_volumes:
            md['volume'] = int(round(127 * (wav_volumes[wav_id] / 100)))

        if wav_id in wav_pans:
            md['pan'] = int(round(((int(wav_pans[wav_id]) * (128/2)) / 100) + (128/2)))

        map_id = target_id
        found_match = False
        for k in sound_metadata['data']:
            item = sound_metadata['data'][k]

            # TODO: Add following to if statement if mixing volume in VA3 file
            # and item['volume'] == md['volume']:
            if item['filename'] == md['filename'] and item['pan'] == md['pan']:
                map_id = item['sound_id']
                found_match = True
                break

        sound_metadata_map[wav_id] = map_id

        if not found_match:
            sound_metadata['data'][map_id] = md

    return sound_metadata_map, sound_metadata


bpm_cache = {}
def find_last_bpm(measure, target_beat, bpms_at_measure_beat):
    global bpm_cache

    last_bpm = 0

    if measure in bpm_cache and target_beat in bpm_cache[measure]:
        return bpm_cache[measure][target_beat]

    for pk in sorted(bpms_at_measure_beat.keys()):
        if pk > measure:
            break

        if pk not in bpms_at_measure_beat:
            continue

        for subbeat_k in sorted(bpms_at_measure_beat[pk].keys()):
            is_start = measure == 0 and target_beat == 0
            if not is_start and pk == measure and subbeat_k > target_beat:
                break

            last_bpm = bpms_at_measure_beat[pk][subbeat_k]

    if measure not in bpm_cache:
        bpm_cache[measure] = {}

    bpm_cache[measure][target_beat] = last_bpm

    return last_bpm

def is_mid_bpm(measure, bpms_at_measure_beat):
    if measure not in bpms_at_measure_beat:
        return False

    if len(bpms_at_measure_beat[measure].keys()) > 1:
        return True

    for subbeat_k in sorted(bpms_at_measure_beat[measure].keys()):
        if subbeat_k > 0:
            return True

    return False


timestamp_cache = {}
timestamp_cache2 = {}
def calculate_current_timestamp(measure, target_beat, measure_lengths, bpms_at_measure_beat):
    global bpm_cache
    global timestamp_cache
    global timestamp_cache2

    def _calculate_current_timestamp(measure, target_beat, prev, timesig, bpm):
        cache_key = "%d_%d_%d_%d_%f" % (
            measure,
            target_beat,
            timesig.numerator,
            timesig.denominator,
            bpm
        )

        if cache_key in timestamp_cache2:
            return timestamp_cache2[cache_key]

        one_measure = (1920 / timesig.denominator) * timesig.numerator
        beat_ts = (60 / (bpm * (timesig.denominator / 4))) * 300
        beat_len = (beat_ts * timesig.numerator) / one_measure

        timestamp = (((measure * one_measure) + target_beat) * beat_len) / 300
        timestamp_cache2[cache_key] = timestamp

        return timestamp

    if measure in timestamp_cache and target_beat in timestamp_cache[measure]:
        return timestamp_cache[measure][target_beat]

    measure_lengths_before_target = {}
    results = [0]
    keys = sorted(measure_lengths.keys())

    if len(keys) > 0:
        measure_lengths_before_target[keys[0]] = 0

    for cur_measure in range(measure + 1):
        current_timesig = find_last_timesig(cur_measure, measure_lengths)

        if cur_measure == measure or is_mid_bpm(cur_measure, bpms_at_measure_beat):
            numerator = current_timesig.numerator
            denominator = current_timesig.denominator
            beat_division = int(round((1920 // denominator) * numerator))

            for cur_beat in range(beat_division):
                if cur_measure not in bpm_cache or cur_beat not in bpm_cache[cur_measure]:
                    current_bpm = find_last_bpm(cur_measure, cur_beat, bpms_at_measure_beat)
                else:
                    current_bpm = bpm_cache[cur_measure][cur_beat]

                if cur_measure >= measure and cur_beat >= target_beat:
                    break

                cache_key = "0_1_%d_%d_%f" % (
                    current_timesig.numerator,
                    current_timesig.denominator,
                    current_bpm
                )

                results.append(results[-1] + timestamp_cache2.get(cache_key, _calculate_current_timestamp(0, 1, results[-1], current_timesig, current_bpm)))
        else:
            cur_beat = 0

            if cur_measure not in bpm_cache or cur_beat not in bpm_cache[cur_measure]:
                current_bpm = find_last_bpm(cur_measure, cur_beat, bpms_at_measure_beat)
            else:
                current_bpm = bpm_cache[cur_measure][cur_beat]

            cache_key = "1_0_%d_%d_%f" % (
                current_timesig.numerator,
                current_timesig.denominator,
                current_bpm
            )

            if cache_key in timestamp_cache2:
                results.append(results[-1] + timestamp_cache2[cache_key])
            else:
                results.append(results[-1] + _calculate_current_timestamp(1, 0, results[-1], current_timesig, current_bpm))

    if measure not in timestamp_cache:
        timestamp_cache[measure] = {}

    result = int(round(results[-1] * 300))
    timestamp_cache[measure][target_beat] = result

    return result


def find_last_timesig(measure, measure_lengths):
    last_timesig = None

    for pk in sorted(measure_lengths.keys()):
        if pk > measure:
            break

        if pk not in measure_lengths:
            continue

        last_timesig = measure_lengths[pk]

    return last_timesig


def calculate_current_beat(measure, target_beat, measure_lengths):
    def _calculate_current_beat(measure, target_beat, prev, timesig):
        numerator = timesig.numerator
        denominator = timesig.denominator
        timesig = numerator / (timesig.denominator_orig / 2)
        beat_division = (1920 / denominator) * timesig
        return prev + measure * beat_division + target_beat

    measure_lengths_before_target = {}
    keys = sorted(measure_lengths.keys())

    if len(keys) > 0:
        measure_lengths_before_target[keys[0]] = 0

    last_key = 0
    for i in range(1, len(keys)):
        if keys[i] <= int(measure):
            pk = keys[i-1]

            measure_lengths_before_target[keys[i]] = _calculate_current_beat(
                keys[i] - pk,
                0,
                measure_lengths_before_target[keys[i-1]],
                measure_lengths[keys[i-1]]
            )
            last_key = keys[i]
        else:
            break

    return _calculate_current_beat(
        measure - last_key,
        0,
        measure_lengths_before_target[last_key],
        measure_lengths[last_key]
    )


def add_hold_notes(chart_data, long_note_time_by_measure_beat, long_note_info):
    for measure in long_note_time_by_measure_beat:
        for beat in long_note_time_by_measure_beat[measure]:
            if len(long_note_time_by_measure_beat[measure][beat]) != 2:
                print("Couldn't match long note")
                print(long_note_time_by_measure_beat[measure][beat])
                exit(1)

            m2, b2 = long_note_time_by_measure_beat[measure][beat][0]

            if m2 in long_note_info and b2 in long_note_info[m2]:
                end_time = long_note_info[m2][b2]
            else:
                print("Couldn't find long note end time")
                exit(1)

            for data in chart_data['beats'][long_note_time_by_measure_beat[measure][beat][1]]:
                if data['name'] == "note" and data['data']['note'] != "auto" and data['data']['auto_note'] == 0:
                    data['data']['guitar_special'] |= 0x02  # Hold note
                    data['data']['hold_duration'] = end_time - data['timestamp']

    return chart_data


def generate_timestamp_set(chart, last_event):
    chart['timestamp'] = {}

    for x in sorted(chart['beats'].keys()):
        # Remove anything past the end point
        if x > last_event[2]:
            print("skipped", x, chart['beats'][x], last_event)
            continue

        for x2 in chart['beats'][x]:
            if x2['timestamp'] not in chart['timestamp']:
                chart['timestamp'][x2['timestamp']] = []

            x2['beat'] = int(x)

            chart['timestamp'][x2['timestamp']].append(x2)

    return chart


def get_valid_chart(chart):
    # A chart must have at least 1 note (played) to be considered valid
    if not chart or 'timestamp' not in chart:
        return None

    if len(chart['timestamp']) == 0:
        return None

    for timestamp in chart['timestamp']:
        for x in chart['timestamp'][timestamp]:
            if x['name'] == "note" and x['data']['note'] != "auto":
                return chart

    return None


def get_chart_datas(chart_data, lines):
    song_title = get_value_from_dtx("TITLE", lines, default="")
    artist_name = get_value_from_dtx("ARTIST", lines, default="")
    drum_difficulty = get_value_from_dtx("DLEVEL", lines, default=0)
    guitar_difficulty = get_value_from_dtx("GLEVEL", lines, default=0)
    bass_difficulty = get_value_from_dtx("BLEVEL", lines, default=0)
    pre_image = get_value_from_dtx("PREIMAGE", lines)
    bpms, base_bpm = get_bpms_from_dtx(lines)
    first_bpm = bpms[sorted(bpms.keys(), key=lambda x:int(x))[0]]

    drum_chart_data = {
        "artist": artist_name,
        "title": song_title,
        "bpm": first_bpm,
        "level": drum_difficulty,
        "preimage": pre_image,
        "timestamp": {},
        "header": {
            "beat_division": 1920 // 4,
            "time_division": 300,
            "unk_sys": 0,
            "is_metadata": 0,
            "difficulty": 0,
            "game_type": 0,
        }
    }

    guitar_chart_data = {
        "artist": artist_name,
        "title": song_title,
        "bpm": first_bpm,
        "level": guitar_difficulty,
        "preimage": pre_image,
        "timestamp": {},
        "header": {
            "beat_division": 1920 // 4,
            "time_division": 300,
            "unk_sys": 0,
            "is_metadata": 0,
            "difficulty": 0,
            "game_type": 1,
        }
    }

    bass_chart_data = {
        "artist": artist_name,
        "title": song_title,
        "bpm": first_bpm,
        "level": bass_difficulty,
        "preimage": pre_image,
        "timestamp": {},
        "header": {
            "beat_division": 1920 // 4,
            "time_division": 300,
            "unk_sys": 0,
            "is_metadata": 0,
            "difficulty": 0,
            "game_type": 2,
        }
    }

    # Split chart_data based on type
    for k in chart_data['timestamp']:
        drum_chart_data['timestamp'][k] = []
        guitar_chart_data['timestamp'][k] = []
        bass_chart_data['timestamp'][k] = []

        for entry in chart_data['timestamp'][k]:
            if entry['name'] != 'note':
                drum_chart_data['timestamp'][k].append(entry)
                guitar_chart_data['timestamp'][k].append(entry)
                bass_chart_data['timestamp'][k].append(entry)
            else:
                if entry['data']['note'] == "auto":
                    drum_chart_data['timestamp'][k].append(entry)
                    guitar_chart_data['timestamp'][k].append(entry)
                    bass_chart_data['timestamp'][k].append(entry)
                elif entry['data']['note'] in drum_mapping:
                    drum_chart_data['timestamp'][k].append(entry)
                elif entry['data']['note'] in guitar_mapping:
                    guitar_chart_data['timestamp'][k].append(entry)
                elif entry['data']['note'] in bass_mapping:
                    bass_chart_data['timestamp'][k].append(entry)
                else:
                    print("Unknown note, don't know what chart it belongs to")
                    print(entry)
                    exit(1)

    return get_valid_chart(drum_chart_data), get_valid_chart(guitar_chart_data), get_valid_chart(bass_chart_data)


# TODO: Try to refactor this more later
def parse_dtx_to_intermediate(filename,
                              params,
                              sound_metadata,
                              target_parts=['drum', 'guitar', 'bass', 'open']):
    global timestamp_cache
    global bpm_cache
    global timestamp_cache2

    start_offset_padding = params.get('dtx_pad_start', 0)

    timestamp_cache = {}
    bpm_cache = {}
    timestamp_cache2 = {}
    bpms_at_measure_beat = {}

    if not filename or not os.path.exists(filename):
        return None, None, None, None, sound_metadata

    try:
        with open(filename, "r", encoding="shift-jis") as f:
            lines = [x.strip() for x in f if x.strip().startswith("#")]
    except:
        try:
            with open(filename, "r", encoding="utf-8") as f:
                lines = [x.strip() for x in f if x.strip().startswith("#")]
        except:
            with open(filename, "r", encoding="utf-16") as f:
                lines = [x.strip() for x in f if x.strip().startswith("#")]

    # Parse all commands
    bgm_info = []
    default_notes = {}

    preview_filename = get_value_from_dtx("PREVIEW", lines)
    wav_filenames, wav_lengths = get_wavs_from_dtx(lines, target_parts, sound_metadata, params.get('no_sound', False))
    wav_volumes = get_wav_volumes_from_dtx(lines)
    wav_pans = get_wav_pans_from_dtx(lines)
    bpms, base_bpm = get_bpms_from_dtx(lines)

    bonus_notes = get_bonus_notes_from_dtx(lines, start_offset_padding)
    measure_lengths = get_measure_lengths_from_dtx(lines, start_offset_padding)
    events_by_measure = get_events_by_measure_from_dtx(lines, start_offset_padding)

    # Build data for sound metadata file
    # This must be correct to get the right sound id for the note commands
    # It's not possible to store panning information in the chart data,
    # but volume data is possible.
    # As a result, all volume flags will be stored in the chart data
    # but the panning will be in the sound metadata.
    sound_metadata_map, sound_metadata = generate_sound_metadata_map(sound_metadata, wav_filenames, wav_volumes, wav_pans)
    sound_metadata_guitar = []
    sound_metadata_drum = []

    events_by_measure = pad_events(events_by_measure, measure_lengths)
    bpms_at_measure_beat = get_bpms_at_measure_beat(events_by_measure, bpms)

    guitar_long_notes_at_measure_beat = get_guitar_long_notes_at_measure_beat(events_by_measure)
    guitar_long_note_time_by_measure_beat = \
        get_long_note_time_by_measure_beat(events_by_measure, guitar_long_notes_at_measure_beat, 1)

    bass_long_notes_at_measure_beat = get_bass_long_notes_at_measure_beat(events_by_measure)
    bass_long_note_time_by_measure_beat = \
        get_long_note_time_by_measure_beat(events_by_measure, bass_long_notes_at_measure_beat, 2)

    metadata_chart_data = {
        "beats": {},
        "header": {
            "beat_division": 1920 // 4,
            "time_division": 300,
            "unk_sys": 0,
            "is_metadata": 1,
            "difficulty": 1,
            "game_type": 0,
        }
    }

    chart_data = {
        "beats": {},
        "header": {
            "beat_division": 1920 // 4,
            "time_division": 300,
            "unk_sys": 0,
            "is_metadata": 0,
            "difficulty": 0,
            "game_type": 0,
        }
    }

    # Add start events
    timestamp_cur = calculate_current_timestamp(0, 0, measure_lengths, bpms_at_measure_beat)
    chart_data['beats'][0] = []
    chart_data['beats'][0].append({
        "name": "startpos",
        'timestamp': timestamp_cur,
    })
    chart_data['beats'][0].append({
        "name": "chipstart",
        "data": {
            "unk": 0
        },
        'timestamp': timestamp_cur,
    })

    metadata_chart_data['beats'][0] = []
    metadata_chart_data['beats'][0].append({
        "name": "startpos",
        'timestamp': timestamp_cur,
    })

    metadata_chart_data['beats'][0].append({
        "name": "baron",
        'timestamp': timestamp_cur,
    })

    last_seen_bpm = bpms[sorted(bpms.keys(), key=lambda x:int(x))[0]]
    metadata_chart_data['beats'][0].append({
        "data": {
            "bpm": last_seen_bpm
        },
        "name": "bpm",
        'timestamp': timestamp_cur,
    })

    guitar_long_note_info = {}
    bass_long_note_info = {}
    last_event = (0, 0, 0)
    current_time_signature = Fraction(4, 4)
    keys = list(events_by_measure.keys()) + list(measure_lengths.keys())
    measure_list = sorted(list(set(keys)), key=lambda x: int(x))
    for measure in range(measure_list[-1] + 1):
        time_signature = find_last_timesig(measure, measure_lengths)
        same_numerator = time_signature.numerator == current_time_signature.numerator
        same_denominator = time_signature.denominator == current_time_signature.denominator
        updated_time_signature = not same_numerator or not same_denominator
        current_time_signature = time_signature

        global_beat_metadata = calculate_current_beat(
            measure,
            0,
            measure_lengths
        )

        global_beat_chart = calculate_current_beat(
            measure,
            0,
            measure_lengths
        )

        if global_beat_metadata not in metadata_chart_data['beats']:
            metadata_chart_data['beats'][global_beat_metadata] = []

        timestamp_cur = calculate_current_timestamp(measure, 0, measure_lengths, bpms_at_measure_beat)
        if updated_time_signature:
            metadata_chart_data['beats'][global_beat_metadata].append({
                "data": {
                    "numerator": time_signature.numerator,
                    "denominator": time_signature.denominator,
                },
                "name": "barinfo",
                'timestamp': timestamp_cur,
            })

        metadata_chart_data['beats'][global_beat_metadata].append({
            "name": "measure",
            "timestamp": timestamp_cur,
        })

        # x/16 time signature (and above?) only write half of the beat lines.
        # This can be seen in Lindwurm. I haven't found any other instances
        # of x/16 time signature to be able to check further.
        beat_lines = current_time_signature.numerator
        beat_lines_div = current_time_signature.denominator

        if current_time_signature.denominator >= 16:
            beat_lines /= 2
            beat_lines_div /= 2

        for j in range(1, int(round(beat_lines))):
            cb = int(round(j * (1920 / beat_lines_div)))
            beat = global_beat_metadata + cb

            if beat not in metadata_chart_data['beats']:
                metadata_chart_data['beats'][beat] = []

            metadata_chart_data['beats'][beat].append({
                "name": "beat",
                "timestamp": calculate_current_timestamp(measure, cb, measure_lengths, bpms_at_measure_beat),
            })

        global_beat_metadata = int(round(global_beat_metadata))
        global_beat_chart = int(round(global_beat_chart))

        beat = global_beat_metadata

        if measure in events_by_measure:
            for event in events_by_measure[measure]:
                auto_events = auto_play_ranges
                ignore_events = [
                    0x04,
                    0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2f,
                    0x4c, 0x4d, 0x4e, 0x4f,
                    0x51, 0x54,
                    0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7, 0xa8, 0xa8, 0xaf,
                    0xc2
                ]

                if event == 0x01:
                    # BGM item
                    data = events_by_measure[measure][event]
                    for i in range(len(data)):
                        if data[i] == '00':
                            continue

                        timestamp = calculate_current_timestamp(
                            measure,
                            i % len(data),
                            measure_lengths,
                            bpms_at_measure_beat
                        )

                        if int(data[i], 36) in wav_filenames:
                            bgm_info.append({
                                'filename': wav_filenames[int(data[i], 36)],
                                'timestamp': timestamp / 300
                            })

                elif event == 0x03:
                    # Base BPM addition
                    data = events_by_measure[measure][event]
                    for i in range(len(data)):
                        if data[i] == '00':
                            continue

                        beat = global_beat_metadata + i

                        if beat not in metadata_chart_data['beats']:
                            metadata_chart_data['beats'][beat] = []

                        new_bpm = int(data[i], 16) + base_bpm

                        metadata_chart_data['beats'][beat].append({
                            "data": {
                                "bpm": new_bpm
                            },
                            "name": "bpm",
                            "timestamp": calculate_current_timestamp(
                                measure,
                                i % len(data),
                                measure_lengths,
                                bpms_at_measure_beat
                            ),
                        })

                        if beat > last_event[2]:
                            last_event = (measure, i, beat)

                        last_seen_bpm = new_bpm

                elif event == 0x08:
                    # BPM event
                    data = events_by_measure[measure][event]
                    for i in range(len(data)):
                        if data[i] == '00':
                            continue

                        beat = global_beat_metadata + i

                        if beat not in metadata_chart_data['beats']:
                            metadata_chart_data['beats'][beat] = []

                        if last_seen_bpm == bpms[int(data[i], 36)]:
                            # Already the current BPM, don't write it again
                            continue

                        if not (measure == 0 and beat == 0):
                            metadata_chart_data['beats'][beat].append({
                                "data": {
                                    "bpm": base_bpm + bpms[int(data[i], 36)]
                                },
                                "name": "bpm",
                                "timestamp": calculate_current_timestamp(
                                    measure,
                                    i % len(data),
                                    measure_lengths,
                                    bpms_at_measure_beat
                                ),
                            })

                            if beat > last_event[2]:
                                last_event = (measure, i, beat)

                            last_seen_bpm = base_bpm + bpms[int(data[i], 36)]

                elif event == 0xc2:
                    # baron/off
                    data = events_by_measure[measure][event]
                    for i in range(len(data)):
                        if data[i] == '00':
                            continue

                        beat = global_beat_metadata + i

                        name = ""
                        if data[i] == '01':
                            name = "baron"
                        elif data[i] == '02':
                            name = "baroff"
                        else:
                            # Not a valid event, but we're using it anyway.
                            # This is being abused for the endpos event
                            # to properly calculate the exact end of a song.
                            last_event = (measure, i, beat)
                            continue

                        if beat not in metadata_chart_data['beats']:
                            metadata_chart_data['beats'][beat] = []

                        metadata_chart_data['beats'][beat].append({
                            "name": name,
                            "timestamp": calculate_current_timestamp(
                                measure,
                                i % len(data),
                                measure_lengths,
                                bpms_at_measure_beat
                            ),
                        })

                        if beat > last_event[2]:
                            last_event = (measure, i, beat)

                elif event in default_note_events:
                    data = events_by_measure[measure][event]
                    for i in range(len(data)):
                        if data[i] == '00':
                            continue

                        sound_id = int(data[i], 36)
                        mapped_sound_id = sound_metadata_map.get(sound_id, 0)
                        default_notes[reverse_dtx_mapping[event]] = mapped_sound_id

                elif event == 0x2a:
                    # Guitar long note
                    data = events_by_measure[measure][event]
                    for i in range(len(data)):
                        if data[i] == '00':
                            continue

                        if measure not in guitar_long_note_info:
                            guitar_long_note_info[measure] = {}

                        guitar_long_note_info[measure][i] = calculate_current_timestamp(
                            measure,
                            i % len(data),
                            measure_lengths,
                            bpms_at_measure_beat
                        )

                elif event == 0x2b:
                    # Bass long note
                    data = events_by_measure[measure][event]
                    for i in range(len(data)):
                        if data[i] == '00':
                            continue

                        if measure not in bass_long_note_info:
                            bass_long_note_info[measure] = {}

                        bass_long_note_info[measure][i] = calculate_current_timestamp(
                            measure,
                            i % len(data),
                            measure_lengths,
                            bpms_at_measure_beat
                        )

                elif event in reverse_dtx_mapping:
                    data = events_by_measure[measure][event]
                    for i in range(len(data)):
                        if data[i] == '00':
                            continue

                        beat = global_beat_chart + i

                        if beat not in chart_data['beats']:
                            chart_data['beats'][beat] = []

                        sound_id = int(data[i], 36)
                        mapped_sound_id = sound_metadata_map.get(sound_id, 0)

                        if event in drum_range:
                            sound_metadata_drum.append(mapped_sound_id)

                            if reverse_dtx_mapping[event] not in default_notes:
                                default_notes[reverse_dtx_mapping[event]] = mapped_sound_id

                        elif event in guitar_range or event in bass_range:
                            sound_metadata_guitar.append(mapped_sound_id)

                        if beat > last_event[2]:
                            last_event = (measure, i, beat)

                        if event in drum_range and 'drum' not in target_parts:
                            continue

                        elif event in guitar_range and 'guitar' not in target_parts:
                            continue

                        elif event in bass_range and 'bass' not in target_parts:
                            continue

                        wail_direction = 0
                        wail_flag = 0
                        wail_event = -1

                        if event in guitar_range:
                            wail_event = 0x28
                        elif event in bass_range:
                            wail_event = 0xa8

                        if wail_event != -1 and wail_event in events_by_measure[measure]:
                            if len(events_by_measure[measure][wail_event]) == len(events_by_measure[measure][event]) and events_by_measure[measure][wail_event][i] != "00":
                                wail_flag = 1

                        if event in guitar_range and measure in guitar_long_note_time_by_measure_beat and i in guitar_long_note_time_by_measure_beat[measure]:
                            guitar_long_note_time_by_measure_beat[measure][i] = (guitar_long_note_time_by_measure_beat[measure][i], beat)
                        elif event in bass_range and measure in bass_long_note_time_by_measure_beat and i in bass_long_note_time_by_measure_beat[measure]:
                            bass_long_note_time_by_measure_beat[measure][i] = (bass_long_note_time_by_measure_beat[measure][i], beat)

                        chart_data['beats'][beat].append({
                            "data": {
                                "auto_note": 0,
                                "auto_volume": 0,
                                "hold_duration": 0,
                                "note": reverse_dtx_mapping[event],
                                "note_length": 0,
                                "sound_id": mapped_sound_id,
                                "unk": 0,
                                "volume": 127 if sound_id not in wav_volumes else int(round(127 * (wav_volumes[sound_id] / 100))),
                                "wail_misc": wail_direction,
                                "guitar_special": wail_flag,
                                "bonus_note": 1 if measure in bonus_notes and i in bonus_notes[measure] and sound_id in bonus_notes[measure][i] else 0,
                            },
                            "name": "note",
                            "timestamp": calculate_current_timestamp(measure, i % len(data), measure_lengths, bpms_at_measure_beat),
                        })

                        if 'guitar' in target_parts or 'bass' in target_parts or 'open' in target_parts:
                            if sound_id in wav_lengths:
                                chart_data['beats'][beat][-1]['data']['note_length'] = wav_lengths[sound_id]

                elif event in auto_events:
                    if 'guitar' in target_parts or 'bass' in target_parts or 'open' in target_parts:
                        continue

                    data = events_by_measure[measure][event]

                    for i in range(len(data)):
                        if data[i] == '00':
                            continue

                        beat = global_beat_chart + i

                        if beat not in chart_data['beats']:
                            chart_data['beats'][beat] = []

                        # Auto note
                        sound_id = int(data[i], 36)

                        chart_data['beats'][beat].append({
                            "data": {
                                "auto_note": 1,
                                "auto_volume": 1,
                                "hold_duration": 0,
                                "note": "auto",
                                "note_length": 0,
                                "sound_id": 0 if sound_id not in sound_metadata_map else sound_metadata_map[sound_id],
                                "unk": 0,
                                "volume": 127 if sound_id not in wav_volumes else int(round(127 * (wav_volumes[sound_id] / 100))),
                                "wail_direction": 0,
                                "bonus_note": 0,
                                "guitar_special": 0,
                            },
                            "name": "note",
                            "timestamp": calculate_current_timestamp(measure, i % len(data), measure_lengths, bpms_at_measure_beat),
                        })

                        if 'guitar' in target_parts or 'bass' in target_parts or 'open' in target_parts:
                            if sound_id in wav_lengths:
                                chart_data['beats'][beat][-1]['data']['note_length'] = wav_lengths[sound_id]

                        if beat > last_event[2]:
                            last_event = (measure, i, beat)

                elif event not in ignore_events:
                    print("Unknown event %02x" % event)

    chart_data = add_hold_notes(chart_data, guitar_long_note_time_by_measure_beat, guitar_long_note_info)
    chart_data = add_hold_notes(chart_data, bass_long_note_time_by_measure_beat, bass_long_note_info)

    # Add end events
    if last_event[2] not in chart_data['beats']:
        chart_data['beats'][last_event[2]] = []

    if last_event[2] not in metadata_chart_data['beats']:
        metadata_chart_data['beats'][last_event[2]] = []

    chart_data['beats'][last_event[2]].append({
        "name": "chipend",
        "timestamp": calculate_current_timestamp(last_event[0], last_event[1], measure_lengths, bpms_at_measure_beat),
    })

    # Delayed end command
    pad_end = params.get('dtx_pad_end', 0)

    if pad_end > 0:
        one_measure = (1920 / measure_lengths[0].denominator) * (measure_lengths[0].numerator / (measure_lengths[0].denominator_orig / 2))
        last_event = (last_event[0] + 2, 0, last_event[2] + (one_measure *  pad_end))

    if last_event[2] not in chart_data['beats']:
        chart_data['beats'][last_event[2]] = []

    if last_event[2] not in metadata_chart_data['beats']:
        metadata_chart_data['beats'][last_event[2]] = []

    chart_data['beats'][last_event[2]].append({
        "name": "endpos",
        "timestamp": calculate_current_timestamp(last_event[0], last_event[1], measure_lengths, bpms_at_measure_beat),
    })

    metadata_chart_data['beats'][last_event[2]].append({
        "name": "endpos",
        "timestamp": calculate_current_timestamp(last_event[0], last_event[1], measure_lengths, bpms_at_measure_beat),
    })

    chart_data = generate_timestamp_set(chart_data, last_event)
    metadata_chart_data = generate_timestamp_set(metadata_chart_data, last_event)

    # Remove any BGMs from the sound metadata
    for bgm in bgm_info:
        remove_keys = []
        for k in sound_metadata['data']:
            if sound_metadata['data'][k]['filename'] == bgm['filename']:
                remove_keys.append(k)

        for k in remove_keys:
            del sound_metadata['data'][k]

    sound_metadata['drum'] = list(set(sound_metadata['drum'] + sound_metadata_drum))
    sound_metadata['guitar'] = list(set(sound_metadata['guitar'] + sound_metadata_guitar))
    sound_metadata['bgm'] = {
        'end': calculate_current_timestamp(last_event[0], last_event[1], measure_lengths, bpms_at_measure_beat) / 300,
        'data': bgm_info
    }
    sound_metadata['preview'] = preview_filename
    sound_metadata['defaults'] = default_notes

    drum_chart_data, guitar_chart_data, bass_chart_data = get_chart_datas(chart_data, lines)

    return metadata_chart_data, drum_chart_data, guitar_chart_data, bass_chart_data, sound_metadata


def create_json_from_dtx(params):
    def get_data(difficulty):
        output = {
            'drum': None,
            'guitar': None,
            'bass': None,
            'open': None
        }

        if 'input_dtx' not in params:
            return output

        for part in ['drum', 'guitar', 'bass', 'open']:
            if part in params['input_dtx'] and difficulty in params['input_dtx'][part]:
                filename = params['input_dtx'][part][difficulty]

                if filename and os.path.exists(filename):
                    output[part] = params['input_dtx'][part][difficulty]

        return output

    novice_data = get_data('nov')
    basic_data = get_data('bsc')
    adv_data = get_data('adv')
    ext_data = get_data('ext')
    master_data = get_data('mst')

    sound_metadata = {'sound_folder': params['sound_folder'] if 'sound_folder' in params else "", 'preview': "", 'bgm': {}, 'data': {}, 'guitar': [], 'drum': [], 'defaults': {}}

    def get_chart_data(data, sound_metadata, parts):
        metadatas = []

        chart_drum = None
        if "drum" in parts and 'drum' in data:
            metadata1, chart_drum, _, _, sound_metadata = parse_dtx_to_intermediate(data['drum'], params, sound_metadata, "drum")
            metadatas.append(metadata1)

        chart_guitar = None
        if "guitar" in parts and 'guitar' in data:
            metadata2, _, chart_guitar, _, sound_metadata = parse_dtx_to_intermediate(data['guitar'], params, sound_metadata, "guitar")
            metadatas.append(metadata2)

        chart_bass = None
        if "bass" in parts and 'bass' in data:
            metadata3, _,  _, chart_bass, sound_metadata = parse_dtx_to_intermediate(data['bass'], params, sound_metadata, "bass")
            metadatas.append(metadata3)

        chart_open = None
        # if "open" in parts and 'open' in data:
        #     metadata4, chart_bass, sound_metadata = parse_dtx_to_intermediate(data['open'], params, sound_metadata, "open")
        #     metadatas.append(metadata4)

        metadatas = [x for x in metadatas if x is not None]  # Filter bad metadata charts
        metadata = None if len(metadatas) == 0 else metadatas[0]

        return metadata, chart_drum, chart_guitar, chart_bass, chart_open, sound_metadata

    novice_metadata, novice_chart_drum, novice_chart_guitar, novice_chart_bass, novice_chart_open, sound_metadata = get_chart_data(novice_data, sound_metadata, params['parts'])
    basic_metadata, basic_chart_drum, basic_chart_guitar, basic_chart_bass, basic_chart_open, sound_metadata = get_chart_data(basic_data, sound_metadata, params['parts'])
    adv_metadata, adv_chart_drum, adv_chart_guitar, adv_chart_bass, adv_chart_open, sound_metadata = get_chart_data(adv_data, sound_metadata, params['parts'])
    ext_metadata, ext_chart_drum, ext_chart_guitar, ext_chart_bass, ext_chart_open, sound_metadata = get_chart_data(ext_data, sound_metadata, params['parts'])
    master_metadata, master_chart_drum, master_chart_guitar, master_chart_bass, master_chart_open, sound_metadata = get_chart_data(master_data, sound_metadata, params['parts'])

    # Create sound metadata file
    # Any notes not in the drums or guitar sound metadata fields should be added to both just in case
    sound_metadata_guitar = {
        "type": "GDXH",
        "version": 2,
        "gdx_type_unk1": 0,
        "gdx_volume_flag": 1,
        "defaults": {
            "default_snare": 0,
            "default_hihat": 0,
            "default_floortom": 65521,
            "default_leftcymbal": 65520,
            "default_rightcymbal": 0,
            "default_leftpedal": 65522,
            "default_lowtom": 0,
            "default_hightom": 0,
            "default_bass": 0
        },
        "entries": [],
    }

    for idx in sound_metadata['guitar']:
        if idx in sound_metadata['data']:
            sound_metadata_guitar['entries'].append(sound_metadata['data'][idx])

    for idx in list(set(sound_metadata['data'].keys()).difference(set(sound_metadata['guitar'] + sound_metadata['drum']))):
        if idx in sound_metadata['data']:
            sound_metadata_guitar['entries'].append(sound_metadata['data'][idx])

    sound_metadata_drums = {
        "type": "GDXG",
        "version": 2,
        "defaults": {
            "default_hihat": sound_metadata['defaults']['hihat'] if 'hihat' in sound_metadata['defaults'] else 0,
            "default_lowtom": sound_metadata['defaults']['lowtom'] if 'lowtom' in sound_metadata['defaults'] else 0,
            "default_snare": sound_metadata['defaults']['snare'] if 'snare' in sound_metadata['defaults'] else 0,
            "default_floortom": sound_metadata['defaults']['floortom'] if 'floortom' in sound_metadata['defaults'] else 0,
            "default_leftpedal": sound_metadata['defaults']['leftpedal'] if 'leftpedal' in sound_metadata['defaults'] else 0,
            "default_bass": sound_metadata['defaults']['bass'] if 'bass' in sound_metadata['defaults'] else 0,
            "default_leftcymbal": sound_metadata['defaults']['leftcymbal'] if 'leftcymbal' in sound_metadata['defaults'] else 0,
            "default_hightom": sound_metadata['defaults']['hightom'] if 'hightom' in sound_metadata['defaults'] else 0,
            "default_rightcymbal": sound_metadata['defaults']['rightcymbal'] if 'rightcymbal' in sound_metadata['defaults'] else 0,
        },
        "gdx_type_unk1": 0,
        "gdx_volume_flag": 1,
        "entries": [],
    }

    for idx in sound_metadata['drum']:
        if idx in sound_metadata['data']:
            sound_metadata_drums['entries'].append(sound_metadata['data'][idx])

    for idx in list(set(sound_metadata['data'].keys()).difference(set(sound_metadata['guitar'] + sound_metadata['drum']))):
        if idx in sound_metadata['data']:
            sound_metadata_drums['entries'].append(sound_metadata['data'][idx])

    metadata_charts = [x for x in [novice_metadata, basic_metadata, adv_metadata, ext_metadata, master_metadata] if x is not None]

    if 'drum' not in params['parts']:
        novice_chart_drum = None
        basic_chart_drum = None
        adv_chart_drum = None
        ext_chart_drum = None
        master_chart_drum = None

    if 'guitar' not in params['parts']:
        novice_chart_guitar = None
        basic_chart_guitar = None
        adv_chart_guitar = None
        ext_chart_guitar = None
        master_chart_guitar = None

    if 'bass' not in params['parts']:
        novice_chart_bass = None
        basic_chart_bass = None
        adv_chart_bass = None
        ext_chart_bass = None
        master_chart_bass = None

    if 'guitar' not in params['parts'] and 'bass' not in params['parts']:
        sound_metadata_guitar = None

    def set_chart_difficulty(charts, difficulty):
        for chart in charts:
            if chart:
                chart['header']['difficulty'] = difficulty

    novice_charts = [novice_chart_drum, novice_chart_guitar, novice_chart_bass]
    basic_charts = [basic_chart_drum, basic_chart_guitar, basic_chart_bass]
    adv_charts = [adv_chart_drum, adv_chart_guitar, adv_chart_bass]
    ext_charts = [ext_chart_drum, ext_chart_guitar, ext_chart_bass]
    master_charts = [master_chart_drum, master_chart_guitar, master_chart_bass]

    set_chart_difficulty(novice_charts, 0)
    set_chart_difficulty(basic_charts, 1)
    set_chart_difficulty(adv_charts, 2)
    set_chart_difficulty(ext_charts, 3)
    set_chart_difficulty(master_charts, 4)

    output_json = {
        "musicid": 0 if 'musicid' not in params or not params['musicid'] else params['musicid'],
        "charts": [x for x in ([metadata_charts[0]] if len(metadata_charts) > 0 else []) + ext_charts + master_charts + adv_charts + basic_charts + novice_charts if x is not None],
        "sound_metadata": {
            "guitar": sound_metadata_guitar,
            "drum": sound_metadata_drums,
        },
        "bgm": sound_metadata['bgm'],
        "preview": sound_metadata['preview'],
    }

    return json.dumps(output_json, indent=4, sort_keys=True)


#########################
#   DTX creation code   #
#########################

def combine_charts(metadata, chart):
    chart_combined = copy.deepcopy(chart)

    # Remove endpos command from chart but keep metadata's command
    for k in sorted(chart_combined['timestamp'].keys(), key=lambda x: int(x)):
        filter_list = ["endpos"]
        chart_combined['timestamp'][k] = [x for x in chart_combined['timestamp'][k] if x['name'] not in filter_list]

    for k in sorted(metadata['timestamp'].keys(), key=lambda x: int(x)):
        if k not in chart_combined['timestamp']:
            chart_combined['timestamp'][k] = []

        for d in metadata['timestamp'][k]:
            chart_combined['timestamp'][k].append(d)

    return chart_combined


def generate_hold_release_events(chart):
    for k in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        for beat in chart['timestamp'][k]:
            if beat['name'] == "note":
                if 'guitar_special' in beat['data'] and beat['data']['guitar_special'] & 0x02:
                    # Long note
                    new_note = copy.deepcopy(beat)
                    new_note['name'] = "_note_release"

                    if 'beat' in new_note:
                        del new_note['beat']

                    new_timestamp = str(int(k) + int(beat['data']['hold_duration']))
                    if new_timestamp not in chart['timestamp']:
                        chart['timestamp'][new_timestamp] = []

                    chart['timestamp'][new_timestamp].append(new_note)

    return chart


def get_time_signatures_by_timestamp(chart):
    time_signatures_by_timestamp = {}

    for k in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        for beat in chart['timestamp'][k]:
            if beat['name'] == "barinfo":
                time_signatures_by_timestamp[k] = {
                    'numerator': beat['data']['numerator'],
                    'denominator': beat['data']['denominator'],
                    'denominator_orig': Fraction2(beat['data']['numerator'], beat['data']['denominator']).denominator_orig,
                    'timesig': beat['data']['numerator'] / beat['data']['denominator']
                }

    return time_signatures_by_timestamp


def generate_time_signature_by_timestamp(chart):
    time_signatures_by_timestamp = get_time_signatures_by_timestamp(chart)

    # Generate a time_signature field for everything based on timestamp
    for k in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        idx = [x for x in sorted(time_signatures_by_timestamp.keys(), key=lambda x: int(x)) if int(x) <= int(k)][-1]
        time_signature = time_signatures_by_timestamp[idx]

        for idx in range(len(chart['timestamp'][k])):
            chart['timestamp'][k][idx]['time_signature'] = time_signature

    return chart


def force_dtx_time_signatures(chart):
    # Find time signatures that aren't x/4 and make them x/4 with approprate BPM changes

    last_bpm = None
    last_bpm_k = None
    last_bpm_real = None
    is_mod_bpm = False
    for k in sorted(chart['timestamp'].keys(), key=lambda x: int(x)):
        for data in chart['timestamp'][k]:
            if data['name'] == "bpm":
                last_bpm = data
                last_bpm_k = k
                last_bpm_real = data
                is_mod_bpm = False

        for data in chart['timestamp'][k]:
            if data['name'] == "barinfo":
                if data['data']['denominator'] != 4:
                    diff = data['data']['denominator'] / 4
                    data['data']['denominator'] = 4
                    data['data']['denominator_orig'] = 2

                    if last_bpm_k == k:
                        # Replace BPM in current timestamp
                        for data2 in chart['timestamp'][k]:
                            if data2['name'] == "bpm":
                                data2['data']['bpm'] *= diff
                    else:
                        # Add new BPM command
                        new_bpm = copy.deepcopy(last_bpm_real)
                        new_bpm['beat'] = data['beat']
                        new_bpm['data']['bpm'] *= diff
                        chart['timestamp'][k].append(new_bpm)
                        last_bpm = new_bpm
                        last_bpm_k = k

                    is_mod_bpm = True
                else:
                    if is_mod_bpm:
                        # Add new BPM command
                        new_bpm = copy.deepcopy(last_bpm_real)
                        new_bpm['beat'] = data['beat']
                        chart['timestamp'][k].append(new_bpm)
                        last_bpm = new_bpm
                        last_bpm_k = k


    return chart


def generate_metadata_fields(metadata, chart, is_forced_dtx_time_signatures=False):
    # Generate and add any important data that isn't guaranteed to be there (namely, beat markers for SQ3)

    if 'beat_division' not in metadata['header']:
        metadata['header']['beat_division'] = 480

    if 'time_division' not in metadata['header']:
        metadata['header']['time_division'] = 300

    chart = combine_charts(metadata, chart)

    if is_forced_dtx_time_signatures:
        chart = force_dtx_time_signatures(chart)

    chart = generate_hold_release_events(chart)
    chart = generate_time_signature_by_timestamp(chart)

    return chart


def get_chart_data_by_measure_beat(chart_data):
    chart_data_sorted = {}

    for k in sorted(chart_data['timestamp'].keys(), key=lambda x: int(x)):
        for idx in range(len(chart_data['timestamp'][k])):
            measure = chart_data['timestamp'][k][idx]['metadata']['measure']
            beat = chart_data['timestamp'][k][idx]['metadata']['beat']

            if measure not in chart_data_sorted:
                chart_data_sorted[measure] = {}

            if beat not in chart_data_sorted[measure]:
                chart_data_sorted[measure][beat] = []

            d = chart_data['timestamp'][k][idx]
            d['timestamp'] = k
            chart_data_sorted[measure][beat].append(d)

    return chart_data_sorted


def calculate_time_signatures_by_timestamp(chart_data):
    time_signatures_by_timestamp = {}
    last_timesig_timestamp = 0

    for k in sorted(chart_data['timestamp'].keys(), key=lambda x: int(x)):
        found_timesig = False

        for beat in chart_data['timestamp'][k]:
            if beat['name'] == "barinfo":
                time_signatures_by_timestamp[k] = {
                    'numerator': beat['data']['numerator'],
                    'denominator': beat['data']['denominator'],
                    'denominator_orig': Fraction2(beat['data']['numerator'], beat['data']['denominator']).denominator_orig,
                    'timesig': beat['data']['numerator'] / beat['data']['denominator']
                }

                last_timesig_timestamp = k
                found_timesig = True

        if not found_timesig and last_timesig_timestamp in time_signatures_by_timestamp:
            time_signatures_by_timestamp[k] = time_signatures_by_timestamp[last_timesig_timestamp]

    return time_signatures_by_timestamp


def add_time_signature_to_events(chart_data):
    time_signatures_by_timestamp = calculate_time_signatures_by_timestamp(chart_data)

    # Generate a time_signature field for everything based on timestamp
    time_signatures_by_timestamp_keys = list(sorted(time_signatures_by_timestamp.keys(), key=lambda x: int(x)))
    last_idx = 0
    for k in sorted(chart_data['timestamp'].keys(), key=lambda x: int(x)):
        idx = [x for x in time_signatures_by_timestamp_keys[last_idx:] if int(x) <= int(k)][-1]
        last_idx = time_signatures_by_timestamp_keys.index(idx)

        time_signature = time_signatures_by_timestamp[idx]

        for idx in range(len(chart_data['timestamp'][k])):
            chart_data['timestamp'][k][idx]['time_signature'] = time_signature

    return chart_data


def generate_measure_beat_for_chart(chart_data):
    chart_data = add_time_signature_to_events(chart_data)

    measure = -1
    beat = 0
    last_measure_timestamp = 0
    last_timesig = {'numerator': 4, 'denominator': 4}
    cur_bpm = None
    base_beat = 0
    for k in sorted(chart_data['timestamp'].keys(), key=lambda x: int(x)):
        for idx in range(len(chart_data['timestamp'][k])):
            if chart_data['timestamp'][k][idx]['name'] == "measure":
                measure += 1
                beat = 0
                last_measure_timestamp = int(k)
                last_timesig = chart_data['timestamp'][k][idx]['time_signature']
                base_beat = beat

            elif chart_data['timestamp'][k][idx]['name'] == "beat":
                #beat += int(round(1920 * (chart_data['timestamp'][k][idx]['time_signature']['numerator'] / chart_data['timestamp'][k][idx]['time_signature']['denominator']) / chart_data['timestamp'][k][idx]['time_signature']['numerator']))
                beat = base_beat + (1920 // chart_data['timestamp'][k][idx]['time_signature']['denominator'])
                last_measure_timestamp = int(k)
                last_timesig = chart_data['timestamp'][k][idx]['time_signature']
                base_beat = beat

            elif chart_data['timestamp'][k][idx]['name'] == "barinfo":
                last_measure_timestamp = int(k)
                last_timesig = chart_data['timestamp'][k][idx]['time_signature']

            elif cur_bpm == None and chart_data['timestamp'][k][idx]['name'] == "bpm":
                cur_bpm = chart_data['timestamp'][k][idx]['data']['bpm']
                last_timesig = chart_data['timestamp'][k][idx]['time_signature']

        # Calculate the difference between the current beat's timestamp and
        # the current note's timestamp Then calculate the beat difference
        # between those two
        diff = int(k) - last_measure_timestamp
        diff_sec = diff / 300
        diff_sec *= int(round(last_timesig['denominator_orig'] / 2))
        beats_per_sec = cur_bpm / 60
        measure_size = int((1920 / last_timesig['denominator']) * last_timesig['numerator'])
        beat_diff = (diff_sec * beats_per_sec) * (1920 // last_timesig['denominator'])

        measure_diff = 0
        # if beat + beat_diff >= measure_size:
        #     measure_diff = (beat + beat_diff) // measure_size
        #     beat_diff = (beat + beat_diff) - (measure_diff * measure_size)
        #     final_beat = beat_diff
        #     print(measure + measure_diff, beat + beat_diff)
        # else:
        #     final_beat = beat + round(beat_diff)

        final_beat = beat + round(beat_diff)
        final_beat *= int(last_timesig['denominator_orig'] / 2)

        for idx in range(len(chart_data['timestamp'][k])):
            chart_data['timestamp'][k][idx]['beat'] = 0
            chart_data['timestamp'][k][idx]['metadata'] = {
                'measure': measure + measure_diff if measure + measure_diff >= 0 else 0,
                'beat': int(round(final_beat)),
            }

        for idx in range(len(chart_data['timestamp'][k])):
            if chart_data['timestamp'][k][idx]['name'] == "bpm":
                cur_bpm = chart_data['timestamp'][k][idx]['data']['bpm']
                last_timesig = chart_data['timestamp'][k][idx]['time_signature']
                last_measure_timestamp = int(k)
                beat = int(round(final_beat))

    return chart_data


def get_clipped_wav(sound_metadata, sound_entry, duration):
    # Check if a clipped WAV exists of the same length
    # If one exists, return the existing entry
    # Otherwise return a newly created entry
    clipped_wav_entry = None

    duration = round(duration, 3) # Pydub only can handle 3 decimal places

    for entry in sound_metadata['entries']:
        if not entry.get('clipped', False):
            continue

        if entry['filename'] == sound_entry['filename'] and entry['duration'] == duration:
            return entry

    next_sound_id = 100
    for entry in sound_metadata['entries']:
        if entry['sound_id'] >= next_sound_id:
            next_sound_id = entry['sound_id'] + 1

    clipped_wav_entry = copy.deepcopy(sound_entry)
    clipped_wav_entry['sound_id'] = next_sound_id
    clipped_wav_entry['clipped'] = True
    clipped_wav_entry['duration'] = duration
    sound_metadata['entries'].append(clipped_wav_entry)

    if "NoFilename" not in sound_entry['flags']:
        orig_wav_filename = "%s.wav" % (sound_entry['filename'])
    else:
        orig_wav_filename = "%04d.wav" % (next_sound_id)

    if "NoFilename" not in sound_entry['flags']:
        wav_filename = "clipped_%d_%s.wav" % (next_sound_id, sound_entry['filename'])
    else:
        wav_filename = "clipped_%d_%04d.wav" % (next_sound_id, next_sound_id)

    sound_folder = sound_metadata['sound_folder'] if sound_metadata['sound_folder'] else ""
    orig_wav_filename = os.path.join(sound_folder, orig_wav_filename)
    wav_filename = os.path.join(sound_folder, wav_filename)

    audio.clip_audio(orig_wav_filename, wav_filename, duration)

    return clipped_wav_entry


def generate_dtx_info(chart_data, sound_metadata, game_type):
    sound_keys = [""]

    sound_files = {}
    volumes = {}
    pans = {}
    bpms = []
    dtx_info = {}
    cur_bpm = None

    last_sound_was_mutable = False
    last_played_note = None

    # TODO: Refactor this more eventually if possible}
    for measure in sorted(chart_data.keys(), key=lambda x: int(x)):
        for beat in sorted(chart_data[measure].keys(), key=lambda x: int(x)):

            for idx in range(len(chart_data[measure][beat])):
                cd = chart_data[measure][beat][idx]

                if not cd['name'] in ['note']:
                    continue

                if 'pan' not in cd['data']:
                    chart_data[measure][beat][idx]['data']['pan'] = 64

                if 'volume' not in cd['data']:
                    chart_data[measure][beat][idx]['data']['volume'] = 127

                pan = 64  # Center
                if sound_metadata and 'entries' in sound_metadata:
                    for sound_entry in sound_metadata['entries']:
                        if sound_entry['sound_id'] == cd['data']['sound_id']:
                            if 'volume' in sound_entry:
                                volume = sound_entry['volume']
                            if 'pan' in sound_entry:
                                pan = sound_entry['pan']
                            break

                pan_final = 0
                if cd['data'].get('pan') != 64:
                    pan_final = int(round((cd['data']['pan'] - ((128 - pan) / 2)) / 64 * 100))
                elif pan != 64:
                    pan_final = int(round((pan - 64) / 64 * 100))

                # Calculate correct pan
                # TODO: Put this behind some kind of flag check since it's probably not required for anything before Gitadora
                if (cd['data']['note'] in ['leftcymbal', 'hihat'] and pan_final > 0) or (cd['data']['note'] in ['floortom', 'rightcymbal'] and pan_final < 0):
                    pan_final = -pan_final

                chart_data[measure][beat][idx]['data']['pan'] = pan_final

                volume = 127  # 100% volume
                volume_final = 100
                if cd['data'].get('volume') != 127:
                    volume_final = int(round((cd['data']['volume'] / 127) * (volume / 127) * 100))
                elif volume != 127:
                    volume_final = int(round((volume / 127) * 100))

                chart_data[measure][beat][idx]['data']['volume'] = volume_final

            is_mutable_sound = False
            mutable_sound_data = None

            for cd in chart_data[measure][beat]:
                if not cd['name'] in ['note', 'auto']:
                    continue

                if cd['data']['sound_id'] >= 100 and game_type == 0:
                    is_mutable_sound = True
                    mutable_sound_data = cd

            if is_mutable_sound:
                for idx in range(len(chart_data[measure][beat])):
                    if not chart_data[measure][beat][idx]['name'] in ['note', 'auto']:
                        continue

                    if chart_data[measure][beat][idx]['data']['sound_id'] < 100:
                        continue

                    # Only the last played mutable sound is actually audible in-game
                    if chart_data[measure][beat][idx]['data']['sound_id'] != mutable_sound_data['data']['sound_id']:
                        chart_data[measure][beat][idx]['data']['volume'] = 0

            for cd in chart_data[measure][beat]:
                if measure not in dtx_info:
                    dtx_info[measure] = {}

                if cd['name'] == "bpm":
                    bpms.append(cd['data']['bpm'])

                    if measure in dtx_info and 0x08 not in dtx_info[measure]:
                        numerator = cd['time_signature']['numerator']
                        denominator = cd['time_signature']['denominator']
                        beat_division = int((1920 / denominator) * numerator)
                        dtx_info[measure][0x08] = ['00'] * beat_division
                    d = dtx_info[measure][0x08]
                    d[beat] = base_repr(len(bpms), 36, padding=2).upper()[-2:]
                    cur_bpm = cd['data']['bpm']

                    dtx_info[measure][0x08] = d

                elif cd['name'] == "barinfo":
                    if measure in dtx_info and 0x02 not in dtx_info[measure]:
                        dtx_info[measure][0x02] = {}

                    dtx_info[measure][0x02] = ["{}".format(
                        cd['time_signature']['numerator'] / cd['time_signature']['denominator']
                    )]

                elif cd['name'] == "baron":
                    if measure in dtx_info and 0xc2 not in dtx_info[measure]:
                        numerator = cd['time_signature']['numerator']
                        denominator = cd['time_signature']['denominator']
                        beat_division = int((1920 / denominator) * numerator)
                        dtx_info[measure][0xc2] = ['00'] * beat_division

                    d = dtx_info[measure][0xc2]
                    d[beat] = base_repr(0x01, 36, padding=2).upper()[-2:]

                    dtx_info[measure][0xc2] = d

                elif cd['name'] == "baroff":
                    if measure in dtx_info and 0xc2 not in dtx_info[measure]:
                        numerator = cd['time_signature']['numerator']
                        denominator = cd['time_signature']['denominator']
                        beat_division = int((1920 / denominator) * numerator)
                        dtx_info[measure][0xc2] = ['00'] * beat_division

                    d = dtx_info[measure][0xc2]
                    d[beat] = base_repr(0x02, 36, padding=2).upper()[-2:]

                    dtx_info[measure][0xc2] = d

                elif cd['name'] == "endpos":
                    if measure in dtx_info and 0xc2 not in dtx_info[measure]:
                        numerator = cd['time_signature']['numerator']
                        denominator = cd['time_signature']['denominator']
                        beat_division = int((1920 / denominator) * numerator)
                        dtx_info[measure][0xc2] = ['00'] * beat_division

                    d = dtx_info[measure][0xc2]
                    #d[beat] = base_repr(0x03, 36, padding=2).upper()[-2:]

                    dtx_info[measure][0xc2] = d

                elif cd['name'] == "_note_release":
                    # This is an automatically generated event based on
                    # guitar_special and note_length
                    longnote_field = [-1, 0x2a, 0x2b, 0x2a][game_type]

                    if measure in dtx_info and longnote_field not in dtx_info[measure]:
                        numerator = cd['time_signature']['numerator']
                        denominator = cd['time_signature']['denominator']
                        beat_division = int((1920 / denominator) * numerator)
                        dtx_info[measure][longnote_field] = ['00'] * beat_division

                    d = dtx_info[measure][longnote_field]
                    d[beat] = base_repr(0x01, 36, padding=2).upper()[-2:]

                    dtx_info[measure][longnote_field] = d

                elif cd['name'] == "note":
                    if is_mutable_sound and last_sound_was_mutable:
                        # Sound id >= 100
                        # Only one mutable sound can be played at once
                        sound_entry = None
                        if sound_metadata and 'entries' in sound_metadata:
                            for sound_entry in sound_metadata['entries']:
                                if sound_entry['sound_id'] == last_played_note['data']['data']['sound_id']:
                                    break

                        if sound_entry:
                            time_diff = (int(cd['timestamp']) - int(last_played_note['data']['timestamp'])) / 300

                            if time_diff < sound_entry['duration']:
                                # Set last_played_note['data']['sound_id'] to new sound id of clipped WAV
                                # Create list of WAVs to be clipped once parsing is done
                                clipped_wav_metadata = get_clipped_wav(sound_metadata, sound_entry, time_diff)

                                if clipped_wav_metadata:
                                    prev_sound_id = last_played_note['data']['data']['sound_id']
                                    last_played_note['data']['data']['sound_id'] = clipped_wav_metadata['sound_id']

                                    mapped_note = dtx_mapping[last_played_note['data']['data']['note']]
                                    d = dtx_info[last_played_note['measure']][mapped_note]

                                    # TODO: Refactor so this and the next instance of the same code are in their own function
                                    sound_key = "%04d_%03d_%03d" % (
                                        last_played_note['data']['data']['sound_id'],
                                        last_played_note['data']['data']['volume'],
                                        last_played_note['data']['data']['pan']
                                    )

                                    prev_sound_key = "%04d_%03d_%03d" % (
                                        prev_sound_id,
                                        last_played_note['data']['data']['volume'],
                                        last_played_note['data']['data']['pan']
                                    )

                                    if sound_key not in sound_keys:
                                        sound_keys.append(sound_key)
                                        sound_id = sound_keys.index(sound_key)
                                        prev_sound_id = sound_keys.index(prev_sound_key)

                                        sound_files[sound_id] = last_played_note['data']['data']['sound_id']
                                        volumes[sound_id] = volumes[prev_sound_id]
                                        pans[sound_id] = pans[prev_sound_id]

                                    sound_id = sound_keys.index(sound_key)
                                    d[last_played_note['beat']] = base_repr(sound_id, 36, padding=2).upper()[-2:]
                                    dtx_info[last_played_note['measure']][mapped_note] = d

                    mapped_note = dtx_mapping[cd['data']['note']]

                    # Fix mapped note for autoplay sounds
                    if mapped_note in auto_play_ranges:
                        while measure in dtx_info and mapped_note in dtx_info[measure]:
                            d = dtx_info[measure][mapped_note]

                            if d[beat] != "00" and mapped_note in auto_play_ranges:
                                if auto_play_ranges.index(mapped_note) + 1 >= len(auto_play_ranges):
                                    print("Ran out of auto play spaces")
                                    exit(1)

                                idx = auto_play_ranges.index(mapped_note)
                                mapped_note = auto_play_ranges[idx + 1]
                            else:
                                break

                    if measure in dtx_info and mapped_note not in dtx_info[measure]:
                        numerator = cd['time_signature']['numerator']
                        denominator = cd['time_signature']['denominator']
                        beat_division = int((1920 / denominator) * numerator)
                        dtx_info[measure][mapped_note] = ['00'] * beat_division

                    d = dtx_info[measure][mapped_note]

                    if 'auto_volume' in cd['data']:
                        if 'auto_note' not in cd['data'] or cd['data'].get('auto_note') == 1:
                            if cd['data']['auto_volume']:
                                # Change 2/3 later if other games use different ratios
                                cd['data']['volume'] = int(round(cd['data']['volume'] * (2/3)))

                    sound_key = "%04d_%03d_%03d" % (
                        cd['data']['sound_id'],
                        cd['data']['volume'],
                        cd['data']['pan']
                    )

                    if sound_key not in sound_keys:
                        sound_keys.append(sound_key)
                        sound_id = sound_keys.index(sound_key)
                        sound_files[sound_id] = cd['data']['sound_id']
                        volumes[sound_id] = cd['data']['volume']
                        pans[sound_id] = cd['data']['pan']

                    #print(measure, len(d), beat, cd['time_signature'], cur_bpm)

                    sound_id = sound_keys.index(sound_key)
                    d[beat] = base_repr(sound_id, 36, padding=2).upper()[-2:]
                    dtx_info[measure][mapped_note] = d

                    # Wail support
                    if 'guitar_special' in cd['data'] and cd['data']['guitar_special'] & 0x01:
                        if cd['data']['wail_misc'] == 2:
                            # Down wail
                            # Currently down wailing isn't supported by any simulator,
                            # so just use up wail's commands for now
                            wail_field = [-1, 0x28, 0xa8, 0x28][game_type]
                        else:  # 0, 1, ?
                            # Up wail
                            wail_field = [-1, 0x28, 0xa8, 0x28][game_type]

                        if measure in dtx_info and wail_field not in dtx_info[measure]:
                            numerator = cd['time_signature']['numerator']
                            denominator = cd['time_signature']['denominator']
                            timesig = numerator / denominator
                            beat_division = int(1920 * timesig)
                            dtx_info[measure][wail_field] = ['00'] * beat_division

                        wail_d = dtx_info[measure][wail_field]
                        wail_d[beat] = d[beat]

                        dtx_info[measure][wail_field] = wail_d

                    # Bonus note support
                    if cd['data'].get('bonus_note') and cd['data']['note'] in dtx_bonus_mapping:
                        bonus_note_lane = 0x4f

                        while bonus_note_lane >= 0x4c:
                            if measure in dtx_info and bonus_note_lane not in dtx_info[measure]:
                                numerator = cd['time_signature']['numerator']
                                denominator = cd['time_signature']['denominator']
                                beat_division = int((1920 / denominator) * numerator)
                                dtx_info[measure][bonus_note_lane] = ['00'] * beat_division

                            bonus_d = dtx_info[measure][bonus_note_lane]

                            if bonus_d[beat] != "00":
                                bonus_note_lane -= 1
                                continue

                            bonus_d[beat] = base_repr(dtx_bonus_mapping[cd['data']['note']], 16, padding=2).upper()[-2:]

                            dtx_info[measure][bonus_note_lane] = bonus_d
                            break

                        if bonus_note_lane < 0x4c:
                            print("Couldn't find enough bonus note lanes")


            last_sound_was_mutable = is_mutable_sound

            if is_mutable_sound:
                last_played_note = {
                    'data': mutable_sound_data,
                    'measure': measure,
                    'beat': beat,
                }
            else:
                last_played_note = None

    return dtx_info, bpms, sound_files, volumes, pans


def generate_dtx_chart_from_json(metadata, orig_chart_data, sound_metadata, params):
    game_type = orig_chart_data['header']['game_type']

    chart_data = generate_metadata_fields(metadata, orig_chart_data, params.get('dtx_fake_timesigs', False))
    chart_data = generate_measure_beat_for_chart(chart_data)
    chart_data = get_chart_data_by_measure_beat(chart_data)

    sound_metadata['sound_folder'] = params.get('sound_folder', None)

    dtx_info, bpms, sound_files, volumes, pans = generate_dtx_info(chart_data, sound_metadata, game_type)

    output = []
    if 'title' in orig_chart_data['header']:
        output.append("#TITLE %s" % orig_chart_data['header']['title'])
    else:
        output.append("#TITLE (no title)")

    if 'artist' in orig_chart_data['header']:
        output.append("#ARTIST %s" % orig_chart_data['header']['artist'])
    else:
        output.append("#ARTIST (no artist   )")

    if 'level' in orig_chart_data['header']:
        for k in orig_chart_data['header']['level']:
            level_map = {
                "drum": "DLEVEL",
                "guitar": "GLEVEL",
                "open": "GLEVEL",
                "bass": "BLEVEL"
            }
            output.append("#%s %s" % (level_map[k], orig_chart_data['header']['level'][k]))

    if 'level' in orig_chart_data['header']:
        has_drum = "drum" in orig_chart_data['header']['level']
        has_guitar = "guitar" in orig_chart_data['header']['level']
        has_bass = "bass" in orig_chart_data['header']['level']
        has_open = "open" in orig_chart_data['header']['level']
        if has_drum:
            output.append("#PREVIEW i%04ddm.wav" % orig_chart_data['header']['musicid'])
        elif has_guitar or has_bass or has_open:
            output.append("#PREVIEW i%04dgf.wav" % orig_chart_data['header']['musicid'])

    output.append("#PREIMAGE img_jk%04d.png" % orig_chart_data['header']['musicid'])
    output.append("#AVIZZ mv%04d.avi" % orig_chart_data['header']['musicid'])

    output.append("#BPM %s" % (bpms[0]))
    for i in range(0, len(bpms)):
        output.append("#BPM%s %s" % (base_repr(i+1, 36, padding=2).upper()[-2:], bpms[i]))

    for k in sorted(sound_files.keys()):
        wav_filename = "%04x.wav" % sound_files[k]

        if sound_metadata and 'entries' in sound_metadata:
            for sound_entry in sound_metadata['entries']:
                if sound_entry['sound_id'] != sound_files[k]:
                    continue

                if "NoFilename" not in sound_entry['flags']:
                    wav_filename = "%s.wav" % sound_entry['filename']

                if sound_entry.get('clipped', False):
                    wav_filename = "clipped_%d_%s" % (sound_entry['sound_id'], wav_filename)

                break

        output.append("#WAV%s %s" % (base_repr(int(k), 36, padding=2).upper()[-2:], wav_filename))

    bgm_filename = "bgm.wav"
    if 'level' in orig_chart_data['header']:
        has_drum = "drum" in orig_chart_data['header']['level']
        has_guitar = "guitar" in orig_chart_data['header']['level']
        has_bass = "bass" in orig_chart_data['header']['level']

        bgm_filename_part = "".join([
            "d" if not has_drum else "_",
            "g" if not has_guitar else "_",
            "b" if not has_bass else "_",
            "k"
        ])

        if bgm_filename_part == "__bk":
            # A BGM file with just the bass doesn't exist
            # Default to one without bass or guitar
            bgm_filename_part = "d__k"

        bgm_filename = "bgm%04d%s.wav" % (orig_chart_data['header']['musicid'],
                                          bgm_filename_part)

    output.append("#WAVZZ %s" % bgm_filename)

    for k in sorted(volumes.keys()):
        output.append("#VOLUME%s %d" % (base_repr(int(k), 36, padding=2).upper()[-2:], volumes[k]))

    for k in sorted(pans.keys()):
        output.append("#PAN%s %d" % (base_repr(int(k), 36, padding=2).upper()[-2:], pans[k]))

    output.append("#00001: ZZ")
    output.append("#00054: ZZ")
    for measure in sorted(dtx_info.keys(), key=lambda x: int(x)):
        for key in sorted(dtx_info[measure].keys(), key=lambda x: int(x)):
            output.append("#%03d%02X: %s" % (measure, key, "".join(dtx_info[measure][key])))

    return "\n".join(output)


def get_metadata_chart(charts):
    chart_metadata = [x for x in charts if x['header']['is_metadata'] == 1]

    if len(chart_metadata) == 0:
        raise Exception("Couldn't find metadata chart")

    return chart_metadata[0]


def get_charts_data(charts, sound_metadata, params):
    chart_metadata = get_metadata_chart(charts)

    return [{
        'chart': x,
        'data': generate_dtx_chart_from_json(copy.deepcopy(chart_metadata), x, sound_metadata, params)
    } for x in charts if x['header']['is_metadata'] == 0]


def create_dtx_from_json(params):
    dtx_data = params.get('input', None)
    sound_folder = params.get('sound_folder', None)
    json_dtx = json.loads(dtx_data)

    output_folder = params.get('output', None)
    if output_folder and not os.path.exists(output_folder):
        os.makedirs(output_folder)

    sound_metadata = params.get('sound_metadata', None)

    charts_data = get_charts_data(json_dtx['charts'], sound_metadata, params)
    create_dtx_files(json_dtx, params, charts_data)
    create_set_definition_file(json_dtx, params, charts_data)

    return None


def get_dtx_filename(json_dtx, chart):
    if 'format' in json_dtx:
        origin_format = "_%s" % json_dtx['format'].lower()
    else:
        origin_format = ""

    difficulty = ['nov', 'bsc', 'adv', 'ext', 'mst'][chart['chart']['header']['difficulty']]
    game_initial = ['d', 'g', 'b', 'o'][chart['chart']['header']['game_type']]
    output_filename = "%s%04d_%s%s.dtx" % (game_initial,
                                           json_dtx['musicid'],
                                           difficulty,
                                           origin_format)

    return output_filename


def create_dtx_files(json_dtx, params, charts_data):
    output_folder = params.get('output', None)

    for x in charts_data:
        output_filename = get_dtx_filename(json_dtx, x)

        if output_folder:
            output_filename = os.path.join(output_folder, output_filename)

        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(x['data'])


def create_set_definition_file(json_dtx, params, charts_data):
    output_folder = params.get('output', "")
    output_set_filename = os.path.join(output_folder, "set.def")

    song_title = None
    output_set_data = {}
    for x in charts_data:
        output_filename = get_dtx_filename(json_dtx, x)

        game_type = ['Drum', 'Guitar', 'Bass', 'Open'][x['chart']['header']['game_type']]
        if game_type not in output_set_data:
            output_set_data[game_type] = {}

        output_set_data[game_type][x['chart']['header']['difficulty']] = output_filename

        if 'title' in x['chart']['header']:
            song_title = x['chart']['header']['title']

    with open(output_set_filename, "a", encoding="utf-8") as outfile:
        for part in output_set_data:
            if song_title:
                outfile.write("#TITLE: {} ({})\n".format(song_title, part))

            for difficulty in sorted(output_set_data[part].keys(), key=lambda x: int(x)):
                outfile.write("#L{}FILE: {}\n".format(difficulty,
                                                      output_set_data[part][difficulty]))
            outfile.write("\n")


class DtxFormat:
    @staticmethod
    def get_format_name():
        return "DTX"

    @staticmethod
    def to_json(params):
        return create_json_from_dtx(params)

    @staticmethod
    def to_chart(params):
        return create_dtx_from_json(params)

    @staticmethod
    def is_format(filename):
        # How to determine a DTX?
        return False


def get_class():
    return DtxFormat
