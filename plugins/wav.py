import glob
import json
import math
import pydub
import os
import re
import string

import audio
import helper
import mdb
import tmpfile

import imageio
imageio.plugins.ffmpeg.download()

VOLUME_OVERHEAD_PERCENT = 75


def percentage_to_db(percentage):
    if percentage == 0:
        return None

    return 20 * math.log10(percentage / 100)


def get_base_audio(input_foldername, bgm_filename, chart_data, no_bgm):
    if no_bgm:
        # Find last timestamp
        last_timestamp = sorted([x['timestamp_ms'] for x in chart_data['beat_data']])[-1]

        # TODO: Find a better way to calculate the ending of the audio
        # Convert last timestamp into a duration and add 2 seconds in
        # case the final notes ring out for long
        duration = last_timestamp + 2 #((last_timestamp) / 0x12c) + 2

        # Create silent audio file
        output_audio = pydub.AudioSegment.silent(duration=duration * 1000)
    else:
        filename = os.path.join(input_foldername, bgm_filename)
        filename = helper.getCaseInsensitivePath(filename)
        output_audio = audio.get_audio_file(filename)

    return output_audio


def make_silent(audio):
    return pydub.AudioSegment.silent(duration=len(audio))


def find_sound_filename(path):
    files = glob.glob(path + "*")

    if len(files) > 0:
        return files[0]

    return path


def create_wav_from_chart(chart_data,
                          input_foldername,
                          sound_metadata,
                          output_filename,
                          bgm_filename="bgm.wav",
                          tags=None,
                          no_bgm=False,
                          ext="mp3",
                          quality="320k",
                          volume_part=100,
                          volume_bgm=100,
                          volume_auto=100,
                          ignore_auto=False):

    volume_part = 50

    output_audio = get_base_audio(input_foldername, bgm_filename, chart_data, no_bgm)
    output_audio = make_silent(output_audio)

    if volume_bgm != 100:
        volume_bgm_db = percentage_to_db(volume_bgm)
        if volume_bgm_db == 0:
            output_audio = make_silent(output_audio)

        elif volume_bgm_db != 0:
            output_audio += volume_bgm_db

    sound_files = {}

    for cd in chart_data['beat_data']:
        if cd['name'] != "note":
            continue

        if ignore_auto and (cd['data'].get('auto_volume', 0) != 0 or cd['data'].get('auto_note', 0) != 0):
            continue

        if 'volume' not in cd['data']:
            cd['data']['volume'] = 127

        is_auto = cd['data'].get('auto_volume') == 1 and cd['data'].get('auto_note') != 0
        if is_auto:
            # Change 2/3 later if other games use different ratios
            cd['data']['volume'] = int(round(cd['data']['volume'] * (2/3)))

        if 'pan' not in cd['data']:
            cd['data']['pan'] = 64

        volume = 127  # 100% volume
        pan = 64  # Center
        wav_filename = "%04x.wav" % int(cd['data']['sound_id'])

        sound_key = "%04d_%03d_%03d" % (cd['data']['sound_id'],
                                        cd['data']['volume'],
                                        cd['data']['pan'])

        if sound_metadata and 'entries' in sound_metadata:
            for sound_entry in sound_metadata['entries']:
                if int(sound_entry['sound_id']) == int(cd['data']['sound_id']):
                    volume = sound_entry.get('volume', volume)
                    pan = sound_entry.get('pan', pan)

                    if 'flags' not in sound_entry or "NoFilename" not in sound_entry['flags']:
                        wav_filename = sound_entry['filename']

                    wav_filename = "%s_%04x" % ("d" if chart_data['header']['game_type'] == 0 else "g", sound_entry['sound_id'])

                    break

        if sound_key not in sound_files:
            if cd['data'].get('volume'):
                volume = (cd['data']['volume'] / 127) * (volume / 127) * 127

            if cd['data'].get('pan') != 64 or pan != 64:
                print(cd['data'].get('pan'), pan)
                exit(1)

            if cd['data'].get('pan') != 64 or pan != 64:
                print(cd['data'].get('pan'), pan)
                exit(1)

            if cd['data'].get('pan'):
                pan = (pan - (128 / 2)) / (128 / 2)
                pan = (cd['data']['pan'] - (128 / 2)) / (128 / 2)

            else:
                pan = (pan - (128 / 2)) / (128 / 2)

            wav_filename = find_sound_filename(helper.getCaseInsensitivePath(os.path.join(input_foldername, wav_filename)))
            if os.path.exists(wav_filename):
                keysound = audio.get_audio_file(wav_filename)
                keysound = keysound.pan(-pan)
                db = percentage_to_db((volume / 127) * 100)
                keysound += db

                if is_auto:
                    volume_key = volume_auto

                else:
                    volume_key = volume_part

                if volume_key != 100:
                    volume_db = percentage_to_db(volume_key)
                    if not volume_db:
                        keysound = make_silent(keysound)
                    elif volume_db != 0:
                        keysound += volume_db

                keysound += percentage_to_db(VOLUME_OVERHEAD_PERCENT)

                sound_files[sound_key] = keysound
            else:
                print("Couldn't find file: %s" % wav_filename)

        if sound_key in sound_files:
            position = cd['timestamp_ms'] #int(timestamp_key) / 0x12c
            print("Overlaying sound at %f" % position)
            output_audio = output_audio.overlay(sound_files[sound_key], position=position * 1000)

    return output_audio


def get_selected_difficulty(json_data, params):
    max_difficulty = None
    min_difficulty = None
    selected_difficulty = None

    for chart_data in json_data['charts']:
        if chart_data['header']['is_metadata'] != 0:
            continue

        if max_difficulty is None or chart_data['header']['difficulty'] > max_difficulty:
            max_difficulty = chart_data['header']['difficulty']

        if min_difficulty is None or chart_data['header']['difficulty'] < min_difficulty:
            min_difficulty = chart_data['header']['difficulty']

        diff = ['nov', 'bsc', 'adv', 'ext', 'mst'][chart_data['header']['difficulty']]
        if diff in params['difficulty']:
            selected_difficulty = chart_data['header']['difficulty']

    if 'min' in params['difficulty']:
        selected_difficulty = min_difficulty
    elif 'max' in params['difficulty']:
        selected_difficulty = max_difficulty

    return selected_difficulty


def get_sound_metadata(params, json_data, input_foldername, game_type):
    if 'sound_metadata' in json_data and game_type in json_data['sound_metadata']:
        return json_data['sound_metadata'][game_type]

    elif 'sound_metadata' in params:
        return params['sound_metadata']

    else:
        sound_metadata_filename = os.path.join(input_foldername, "metadata.json")
        if os.path.exists(sound_metadata_filename):
            with open(sound_metadata_filename, "r") as f:
                sound_metadata = f.read()
        else:
            sound_metadata = None

        if not sound_metadata:
            return None

        json_sound_metadata = json.loads(sound_metadata) if sound_metadata else None

    if game_type in json_sound_metadata:
        return json_sound_metadata[game_type]

    return None


def get_sanitized_filename(filename, invalid_chars='<>:;\"\\/|?*'):
    for c in invalid_chars:
        filename = filename.replace(c, "_")

    return filename


def get_output_filename(json_data, chart_data, params):
    output_filename = None
    ext = params.get('render_ext', "mp3")
    game_type = ['Drum', 'Guitar', 'Bass'][chart_data['header']['game_type']]
    title = chart_data['header'].get('title')

    if title:
        title = title.strip()

    difficulty = ['NOV', 'BSC', 'ADV', 'EXT', 'MST'][chart_data['header']['difficulty']]

    artist = chart_data['header'].get('artist')
    if artist and artist.strip():
        output_filename = "[%04d] %s - %s (%s %s).%s" % (json_data['musicid'],
                                                            artist,
                                                            title,
                                                            game_type,
                                                            difficulty,
                                                            ext)
    else:
        output_filename = "[%04d] %s (%s %s).%s" % (json_data['musicid'],
                                                    title,
                                                    game_type,
                                                    difficulty,
                                                    ext)

    if not output_filename:
        output_filename = "%s%04d_%s.%s" % (game_type[0],
                                            json_data['musicid'],
                                            difficulty,
                                            ext)

    return get_sanitized_filename(output_filename)


def get_tags(json_data, chart_data):
    tags = {}

    mdb_tags = mdb.get_song_info_from_csv("gitadora_music.csv", json_data['musicid'])

    if 'title' in chart_data['header'] and chart_data['header']['title']:
        tags['title'] = chart_data['header']['title']

    elif 'title' in mdb_tags and mdb_tags['title']:
        tags['title'] = mdb_tags['title']

    if 'artist' in chart_data['header'] and chart_data['header']['artist']:
        tags['artist'] = chart_data['header']['artist']

    elif 'artist' in mdb_tags and mdb_tags['artist']:
        tags['artist'] = mdb_tags['artist']

    game_type = ['Drum', 'Guitar', 'Bass'][chart_data['header']['game_type']]
    difficulty = ['NOV', 'BSC', 'ADV', 'EXT', 'MST'][chart_data['header']['difficulty']]
    tags['comments'] = "%s %s %s" % (json_data['musicid'], game_type, difficulty)
    tags['track'] = json_data['musicid']

    if 'gf_version' in mdb_tags:
        tags['album'] = {
            0: None,
            20: "GITADORA",
            21: "GITADORA Overdrive",
            22: "GITADORA Tri-Boost",
            23: "GITADORA Tri-Boost Re:EVOLVE",
            24: "GITADORA Matixx",
            25: "GITADORA EXCHAIN",
            26: "GITADORA NEXTAGE",
        }[mdb_tags['gf_version']]

        tags['date'] = {
            0: None,
            20: 2013,
            21: 2014,
            22: 2015,
            23: 2016,
            24: 2017,
            25: 2018,
            26: 2019,
        }[mdb_tags['gf_version']]

    return tags


def get_bgm_filename(json_data, chart_data, input_foldername):
    if 'bgm' in json_data:
        bgm_filename = audio.merge_bgm(json_data['bgm'], input_foldername)

    else:
        # Get BGM filename based on game type (XG style)
        bgm_type = ['_gbk', 'd_bk', 'd__k'][chart_data['header']['game_type']]
        bgm_filename = "bgm%04d%s.wav" % (json_data['musicid'], bgm_type)

    return bgm_filename


def generate_wav_from_json(params, generate_output_filename=True):
    input_json = params.get('input')
    input_foldername = params.get('sound_folder')
    output_filename = params.get('output')

    if not params.get('render_ext'):
        ext = os.path.splitext(output_filename)[-1]
        ext = ext.replace('.', '').strip()

        if not ext:
            ext = "mp3"

        params['render_ext'] = ext

    if not input_json:
        raise Exception("Couldn't find input data")

    json_data = json.loads(input_json)
    selected_difficulty = get_selected_difficulty(json_data, params)

    if not selected_difficulty:
        raise Exception("Couldn't find selected difficulty")

    bgms = []
    bgm_filename = None
    for chart_data in json_data['charts']:
        # Skip metadata charts and stuff not specified by the user
        if chart_data['header']['is_metadata'] != 0:
            continue

        if chart_data['header']['difficulty'] != selected_difficulty:
            continue

        game_type = ['drum', 'guitar', 'bass'][chart_data['header']['game_type']]
        if game_type not in params['parts']:
            continue

        tags = get_tags(json_data, chart_data)
        if 'title' in tags:
            chart_data['header']['title'] = tags['title']

        if 'artist' in tags:
            chart_data['header']['artist'] = tags['artist']

        output_filename = get_output_filename(json_data, chart_data, params)

        if not bgm_filename:
            bgm_filename = get_bgm_filename(json_data, chart_data, input_foldername)

        sound_metadata_type = ['drum', 'guitar', 'guitar'][chart_data['header']['game_type']]
        json_sound_metadata = get_sound_metadata(params, json_data, input_foldername, sound_metadata_type)
        if not json_sound_metadata:
            raise Exception("Couldn't find sound metadata")

        print("Exporting %s..." % output_filename)

        volume_bgm = params.get('render_volume_bgm', 100)
        volume_part = params.get('render_volume', 100)

        bgms.append(create_wav_from_chart(chart_data,
                              input_foldername,
                              json_sound_metadata,
                              output_filename,
                              bgm_filename,
                              tags=tags,
                              no_bgm=params.get('render_no_bgm', False),
                              ext=params.get('render_ext', "mp3"),
                              quality=params.get('render_quality', '320k'),
                              volume_part=volume_part,
                              volume_bgm=volume_bgm,
                              volume_auto=params.get('render_volume_auto', 100),
                              ignore_auto=params.get('render_ignore_auto', False)))


        if not bgm_filename:
            return

        bgm_filename = os.path.join(input_foldername, bgm_filename)

        print("Saving to %s..." % output_filename)

        if not params.get('render_no_bgm', False):
            output_audio = audio.get_audio_file(bgm_filename)

        else:
            if len(bgms) == 0:
                return

            output_audio = bgms[0]
            bgms = bgms[1:]

        if volume_bgm != 100:
            volume_bgm_db = percentage_to_db(volume_bgm)

            if volume_bgm_db == 0:
                output_audio = make_silent(output_audio)

            elif volume_bgm_db != 0:
                output_audio += volume_bgm_db

        output_audio += percentage_to_db(VOLUME_OVERHEAD_PERCENT)

        for bgm in bgms:
            output_audio = output_audio.overlay(bgm)

        output_audio.export(output_filename, format=params.get('render_ext', "mp3"), tags=tags, bitrate=params.get('render_quality', '320k'))

class WavFormat:
    @staticmethod
    def get_format_name():
        return "WAV"

    @staticmethod
    def to_chart(params):
        return generate_wav_from_json(params)

    @staticmethod
    def is_format(filename):
        return False


def get_class():
    return WavFormat
