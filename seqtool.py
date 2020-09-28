# Gitadora Re:evolve SQ3 format
import argparse
import glob
import importlib
import json
import os
import shutil
import sys
import threading

import tmpfile

import wavbintool
import vas3tool
import ifs
import eamxml
import event
import mdb

import plugins

running_threads = []

def find_handler(input_filename, input_format):
    formats = [importlib.import_module('plugins.' + name).get_class() for name in plugins.__all__]

    for handler in formats:
        if not handler:
            continue

        if input_format is not None and handler.get_format_name().lower() == input_format.lower():
            return handler
        elif input_filename is not None and handler.is_format(input_filename):
            return handler

    return None


def filter_charts(json_data, params):
    json_data = json.loads(json_data)

    if 'charts' not in json_data:
        return json_data

    min_diff = None
    max_diff = None
    for chart in json_data['charts']:
        if min_diff == None or chart['header']['difficulty'] < min_diff:
            min_diff = chart['header']['difficulty']

        if max_diff == None or chart['header']['difficulty'] > max_diff:
            max_diff = chart['header']['difficulty']

    filtered_charts = []
    for chart in json_data['charts']:
        if chart['header']['is_metadata'] != 0:
            continue

        part = ["drum", "guitar", "bass", "open"][chart['header']['game_type']]
        has_all = 'all' in params['parts']
        has_part = part in params['parts']

        if not has_all and not has_part:
            filtered_charts.append(chart)
            continue

        diff = ["nov", "bsc", "adv", "ext", "mst"][chart['header']['difficulty']]
        has_min = 'min' in params['difficulty'] and chart['header']['difficulty'] == min_diff
        has_max = 'max' in params['difficulty'] and chart['header']['difficulty'] == max_diff
        has_all = 'all' in params['difficulty']
        has_diff = diff in params['difficulty']

        if not has_min and not has_max and not has_all and not has_diff:
            filtered_charts.append(chart)
            continue

    for chart in filtered_charts:
        json_data['charts'].remove(chart)

    return json.dumps(json_data, indent=4)


def process_file(params):
    input = params['input'] if 'input' in params else None
    input_format = params['input_format'] if 'input_format' in params else None
    output_format = params['output_format'] if 'output_format' in params else None

    if output_format == "same":
        output_format = input_format

    input_handler = find_handler(input, input_format)
    output_handler = find_handler(None, output_format)

    if output_handler is None:
        output_handler = input_handler

    if input_handler is None:
        print("Could not find a handler for input file")
        exit(1)

    if output_handler is None:
        print("Could not find a handler for output file")
        exit(1)

    print("Using {} handler to process this file...".format(input_handler.get_format_name()))

    json_data = input_handler.to_json(params)

    # Filter based on difficulty and parts here
    json_data = filter_charts(json_data, params)

    if output_format.lower() != 'wav' and 'output' in params and not os.path.exists(params['output']):
        os.makedirs(params['output'])

    # Add music information from database
    if params.get('musicdb', None) and params.get('musicid', None):
        try:
            csv_info = mdb.get_song_info_from_csv("gitadora_music.csv", params['musicid'])

        except:
            csv_info = None

        mdb_info = mdb.get_song_info_from_mdb(params['musicdb'], params['musicid'])

        if csv_info:
            # Pull properly named Japanese artist and title fields from csv if it exists
            mdb_info['title'] = csv_info['title']
            mdb_info['artist'] = csv_info['artist']

            if 'movie_filename' in csv_info:
                mdb_info['movie_filename'] = csv_info['movie_filename']

        if mdb_info:
            json_data = json.loads(json_data)

            for chart in json_data['charts']:
                if chart['header']['is_metadata']:
                    continue

                chart['header']['level'] = {}

                diffs = [chart['header']['game_type']]

                if chart['header']['game_type'] == 1 and params.get('merge_guitars', False):
                    diffs.append(2)

                for x in diffs:
                    k = {
                        0: "drum",
                        1: "guitar",
                        2: "bass",
                        3: "open",
                    }[x]

                    diff = mdb_info['difficulty'][x * 5 + chart['header']['difficulty']]

                    if diff > 0:
                        chart['header']['level'][k] = diff

                chart['header']['title'] = mdb_info['title']
                chart['header']['artist'] = mdb_info['artist']
                chart['header']['bpm'] = mdb_info['bpm']

            json_data = json.dumps(json_data)

    params['input'] = json_data

    output_handler.to_chart(params)


def get_sound_metadata(sound_folder):
    if not sound_folder:
        return None

    sound_metadata = {}
    sound_metadata_filename_guitar = os.path.join(sound_folder, "g_metadata.json")
    if os.path.exists(sound_metadata_filename_guitar):
        with open(sound_metadata_filename_guitar, "r") as f:
            sound_metadata['guitar'] = json.loads(f.read())

    sound_metadata_filename_drum = os.path.join(sound_folder, "d_metadata.json")
    if os.path.exists(sound_metadata_filename_drum):
        with open(sound_metadata_filename_drum, "r") as f:
            sound_metadata['drum'] = json.loads(f.read())

    return sound_metadata if sound_metadata else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    input_group = parser.add_argument_group('input')
    input_group.add_argument('--input', help='Input file/folder')
    input_group.add_argument('--input-format', help='Input file format')
    input_group.add_argument('--sound-folder', help='Input folder containing sounds', default="")
    input_group.add_argument('--event-file', help='Input file containing event information (for SQ2/SQ3)')

    input_split_group = parser.add_argument_group('input_split')
    for part in ['drum', 'guitar', 'bass', 'open']:
        input_split_group.add_argument('--input-%s-nov' % part, help="DTX novice %s chart input (for creation)" % part)
        input_split_group.add_argument('--input-%s-bsc' % part, help="DTX basic %s chart input (for creation)" % part)
        input_split_group.add_argument('--input-%s-adv' % part, help="DTX advanced %s chart input (for creation)" % part)
        input_split_group.add_argument('--input-%s-ext' % part, help="DTX extreme %s chart input (for creation)" % part)
        input_split_group.add_argument('--input-%s-mst' % part, help="DTX master %s chart input (for creation)" % part)

    input_ifs_group = parser.add_argument_group('input_ifs')
    input_ifs_group.add_argument('--input-ifs-seq', help='Input file/folder for SEQ (IFS)')
    input_ifs_group.add_argument('--input-ifs-bgm', help='Input file/folder for BGM (IFS)')
    input_ifs_group.add_argument('--ifs-target', help="Target specific chart type within IFS", default=None, choices=['sq3', 'sq2'])

    parser.add_argument('--output', help='Output file/folder', required=True)
    parser.add_argument('--output-format', help='Output file format', required=True)

    parser.add_argument('--parts', nargs='*', choices=['drum', 'guitar', 'bass', 'open', 'all'], default="all")
    parser.add_argument('--difficulty', nargs='*', choices=['nov', 'bsc', 'adv', 'ext', 'mst', 'all', 'max', 'min'], default="all")
    parser.add_argument('--merge-guitars', action='store_true', help="Merge guitar charts")
    parser.add_argument('--no-sounds', action='store_true', help="Don't convert sound files", default=False)
    parser.add_argument('--copy-raw-files', action='store_true', help="Copy the raw files without processing", default=False)
    parser.add_argument('--generate-bgms', action='store_true', help="Generate BGMs for various combination of instruments as needed (SQ2/SQ3)", default=False)

    parser.add_argument('--music-db', help="Music database file to read metadata about song")
    parser.add_argument('--music-id', type=int, help="Force a music ID", default=None)

    parser.add_argument('--render-auto-name', action='store_true', help="Automatically name output file")
    parser.add_argument('--render-ext', help="Force extension when rendering audio file", default=None)
    parser.add_argument('--render-quality', help="Force quality (320k, etc) when rendering audio file", default="320k")
    parser.add_argument('--render-volume', help="Force volume of selected part during rendering", default=100, type=int)
    parser.add_argument('--render-volume-bgm', help="Force volume of BGM during rendering", default=100, type=int)
    parser.add_argument('--render-volume-auto', help="Force volume of auto notes during rendering", default=100, type=int)
    parser.add_argument('--render-no-bgm', action='store_true', help="Mute BGM during render", default=False)
    parser.add_argument('--render-ignore-auto', action='store_true', help="Mute auto notes during render", default=False)

    parser.add_argument('--dtx-pad-start', help="Pad the start of the song by x measures", default=0, type=int)
    parser.add_argument('--dtx-pad-end', help="Pad the end of the song by x measures", default=2, type=int)
    parser.add_argument('--dtx-fake-timesigs', help="Fake time signatures when converting to DTX to work around x/4 limitation", default=False, action='store_true')

    parser.add_argument('--single-threaded', help="Process charts in single threads", default=False, action='store_true')

    args = parser.parse_args()

    if args.output_format.lower() == "dtx" and os.path.exists(os.path.join(args.output, "set.def")):
        # Crappy hack but I don't want to solve this properly
        os.unlink(os.path.join(args.output, "set.def"))

    # Clean parts and difficulty
    if 'all' in args.parts:
        args.parts = ['drum', 'guitar', 'bass', 'open']

    if 'all' in args.difficulty:
        args.difficulty = ['nov', 'bsc', 'adv', 'ext', 'mst']
    elif 'min' in args.difficulty:
        args.difficulty = ['min']
    elif 'max' in args.difficulty:
        args.difficulty = ['max']

    if args.output_format.lower() == "wav":
        if 'all' in args.difficulty or len(args.difficulty) > 1:
            raise Exception("Can only specify one difficulty for WAV export mode")

    if args.input_ifs_seq:
        if os.path.isdir(args.input_ifs_seq):
            filenames = glob.glob(args.input_ifs_seq + "/*")
            ifs_path = args.input_ifs_seq
        else:
            filenames, ifs_path = ifs.extract(args.input_ifs_seq)

        # Try to match charts with sound files, then extract as required
        guitar = {}
        drum = {}
        for filename in filenames:
            base_filename = os.path.basename(filename)

            target_charts = [".sq3", ".sq2"]
            target_events = [".ev2", ".evt"]
            if args.ifs_target:
                if args.ifs_target.lower() == "sq2":
                    target_charts = [".sq2"]
                    target_events = [".evt", ".ev2"]
                elif args.ifs_target.lower() == "sq3":
                    target_charts = [".sq3"]
                    target_events = [".ev2", ".evt"]
                else:
                    raise Exception("Invalid IFS target selected")

            if base_filename[-4:] in target_charts:
                if base_filename[0] == 'd':
                    drum['seq'] = filename
                elif base_filename[0] == 'g':
                    guitar['seq'] = filename
            elif base_filename[-4:] == ".va3" and not args.no_sounds:
                if base_filename[-5] == 'd':
                    drum['sound'] = filename
                elif base_filename[-5] == 'g':
                    guitar['sound'] = filename
            elif base_filename[-4:] in target_events:
                # Give priority to the events file at the top of the list
                if base_filename[-4:] != target_events[0] and 'events' in drum:
                    continue

                event_xml = eamxml.get_raw_xml(open(filename, "rb").read())

                if len(event_xml) > 0:
                    events = event.get_bonus_notes_by_timestamp(event_xml)
                    drum['events'] = events
                    guitar['events'] = events

        if args.sound_folder:
            sound_folder = args.sound_folder
        elif args.output:
            sound_folder = args.output
        else:
            sound_folder = tmpfile.mkdtemp(prefix="sounds")

        if not os.path.exists(sound_folder) and not args.no_sounds:
            os.makedirs(sound_folder)

        if args.input_ifs_bgm and args.copy_raw_files:
            if os.path.isdir(args.input_ifs_bgm):
                filenames_bgm = glob.glob(args.input_ifs_bgm + "/*.bin")
                ifs_path = args.input_ifs_bgm
            else:
                filenames_bgm, ifs_path = ifs.extract(args.input_ifs_bgm)

            if not os.path.exists(args.output):
                os.makedirs(args.output)

            for filename in filenames_bgm:
                output_filename = os.path.join(args.output, os.path.basename(filename))
                shutil.copy2(filename, output_filename)

        if args.input_ifs_bgm and not args.no_sounds:
            if os.path.isdir(args.input_ifs_bgm):
                filenames_bgm = glob.glob(args.input_ifs_bgm + "/*.bin")
                ifs_path = args.input_ifs_bgm
            else:
                filenames_bgm, ifs_path = ifs.extract(args.input_ifs_bgm)

            for filename in filenames_bgm:
                # Convert to WAV
                output_filename = filename.replace(".bin", ".wav")
                output_filename = os.path.join(sound_folder, os.path.basename(filename).replace(".bin", ".wav"))

                print("Converting %s..." % output_filename)

                if not args.single_threaded:
                    bgm_thread = threading.Thread(target=wavbintool.parse_bin, args=(filename, output_filename))
                    bgm_thread.start()
                    running_threads.append(bgm_thread)
                else:
                    wavbintool.parse_bin(filename, output_filename)
        else:
            filenames_bgm = None

        def handle_set(file_set):
            if 'seq' not in file_set or not file_set['seq']:
                return

            # Extract va3 files
            if 'sound' in file_set and not args.no_sounds:
                print("Parsing %s..." % file_set['sound'])
                vas3tool.read_vas3(file_set['sound'], sound_folder, force_game=("drum" if file_set['sound'][-5] == 'd' else "guitar"))

            params = {
                "input": file_set['seq'],
                "input_format": None,
                "output": args.output,
                "output_format": args.output_format,
                "sound_folder": sound_folder,
                "sound_metadata": get_sound_metadata(sound_folder),
                "event_file": file_set['event'] if 'event' in file_set else None,
                "parts": args.parts,
                "difficulty": args.difficulty,
                "merge_guitars": args.merge_guitars,
                "events": file_set['events'] if 'events' in file_set else {},
                "musicdb": args.music_db,
                "musicid": args.music_id,
                "input_split": {
                    "drum": {
                        "nov": args.input_drum_nov,
                        "bsc": args.input_drum_bsc,
                        "adv": args.input_drum_adv,
                        "ext": args.input_drum_ext,
                        "mst": args.input_drum_mst,
                    },
                    "guitar": {
                        "nov": args.input_guitar_nov,
                        "bsc": args.input_guitar_bsc,
                        "adv": args.input_guitar_adv,
                        "ext": args.input_guitar_ext,
                        "mst": args.input_guitar_mst,
                    },
                    "bass": {
                        "nov": args.input_bass_nov,
                        "bsc": args.input_bass_bsc,
                        "adv": args.input_bass_adv,
                        "ext": args.input_bass_ext,
                        "mst": args.input_bass_mst,
                    },
                    "open": {
                        "nov": args.input_open_nov,
                        "bsc": args.input_open_bsc,
                        "adv": args.input_open_adv,
                        "ext": args.input_open_ext,
                        "mst": args.input_open_mst,
                    }
                },
                "render_no_bgm": args.render_no_bgm,
                "render_auto_name": args.render_auto_name,
                "render_ext": args.render_ext,
                "render_quality": args.render_quality,
                "render_volume": args.render_volume,
                "render_volume_bgm": args.render_volume_bgm,
                "render_ignore_auto": args.render_ignore_auto,
                "dtx_pad_start": args.dtx_pad_start,
                "dtx_pad_end": args.dtx_pad_end,
                "dtx_fake_timesigs": args.dtx_fake_timesigs,
                "no_sounds": args.no_sounds,
                "generate_bgms": args.generate_bgms,
            }

            process_file(params)

            if args.input_ifs_seq and args.copy_raw_files:
                if os.path.isdir(args.input_ifs_seq):
                    filenames_seq = glob.glob(args.input_ifs_seq + "/*")
                    ifs_path = args.input_ifs_seq
                else:
                    filenames_seq, ifs_path = ifs.extract(args.input_ifs_seq)

                for filename in filenames_seq:
                    output_filename = os.path.join(sound_folder, os.path.basename(filename))
                    shutil.copy2(filename, output_filename)

        if "guitar" in args.parts or "bass" in args.parts or "open" in args.parts:
            if not args.single_threaded:
                guitar_thread = threading.Thread(target=handle_set, args=(guitar,))
                guitar_thread.start()
                running_threads.append(guitar_thread)
            else:
                handle_set(guitar)

        if "drum" in args.parts:
            if not args.single_threaded:
                drum_thread = threading.Thread(target=handle_set, args=(drum,))
                drum_thread.start()
                running_threads.append(drum_thread)
            else:
                handle_set(drum)

    else:
        params = {
            "input": args.input if args.input else None,
            "input_format": args.input_format if args.input_format else None,
            "output": args.output,
            "output_format": args.output_format,
            "sound_folder": args.sound_folder,
            "sound_metadata": get_sound_metadata(args.sound_folder),
            "event_file": args.event_file if args.event_file else None,
            "parts": args.parts,
            "difficulty": args.difficulty,
            "merge_guitars": args.merge_guitars,
            "events": event.get_bonus_notes_by_timestamp(eamxml.get_raw_xml(open(args.event_file, "rb").read())) if args.event_file else {},
            "musicdb": args.music_db,
            "musicid": args.music_id,
            "input_split": {
                "drum": {
                    "nov": args.input_drum_nov,
                    "bsc": args.input_drum_bsc,
                    "adv": args.input_drum_adv,
                    "ext": args.input_drum_ext,
                    "mst": args.input_drum_mst,
                },
                "guitar": {
                    "nov": args.input_guitar_nov,
                    "bsc": args.input_guitar_bsc,
                    "adv": args.input_guitar_adv,
                    "ext": args.input_guitar_ext,
                    "mst": args.input_guitar_mst,
                },
                "bass": {
                    "nov": args.input_bass_nov,
                    "bsc": args.input_bass_bsc,
                    "adv": args.input_bass_adv,
                    "ext": args.input_bass_ext,
                    "mst": args.input_bass_mst,
                },
                "open": {
                    "nov": args.input_open_nov,
                    "bsc": args.input_open_bsc,
                    "adv": args.input_open_adv,
                    "ext": args.input_open_ext,
                    "mst": args.input_open_mst,
                }
            },
            "render_no_bgm": args.render_no_bgm,
            "render_auto_name": args.render_auto_name,
            "render_ext": args.render_ext,
            "render_quality": args.render_quality,
            "render_volume": args.render_volume,
            "render_volume_bgm": args.render_volume_bgm,
            "render_ignore_auto": args.render_ignore_auto,
            "dtx_pad_start": args.dtx_pad_start,
            "dtx_pad_end": args.dtx_pad_end,
            "dtx_fake_timesigs": args.dtx_fake_timesigs,
            "no_sounds": args.no_sounds,
            "generate_bgms": args.generate_bgms,
        }

        if not args.single_threaded:
            parse_thread = threading.Thread(target=process_file, args=(params,))
            parse_thread.start()
            running_threads.append(parse_thread)
        else:
            process_file(params)

    if not args.single_threaded:
        for thread in running_threads:
            thread.join()

    tmpfile.tmpcleanup()
