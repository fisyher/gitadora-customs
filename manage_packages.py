import argparse
import multiprocessing
import glob
import json
import os
import shutil
import string
import subprocess
import struct
import uuid
import pkgutil

from PIL import Image

from lxml import objectify
from lxml import etree
from lxml.builder import E

# Cheap hack to make the release for manage_packages.py cleaner
try:
    import tools.ifs as ifs
except:
    import ifs

try:
    import tools.tmpfile as tmpfile
except:
    import tmpfile


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    # Source: https://stackoverflow.com/a/13790741
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def backup_file(filename, backup_path="backups"):
    if not os.path.exists(filename):
        return

    backup_full_path = os.path.join(backup_path, filename)
    tmp_path = os.path.dirname(backup_full_path)

    if os.path.exists(backup_full_path):
        return

    os.makedirs(tmp_path, exist_ok=True)

    print("Backing up", filename, "to", backup_path)
    shutil.copy(filename, backup_full_path)


def read_mdb(filename):
    mdb = {
        'records': {},
        'courses': {},
    }

    if not os.path.exists(filename):
        return mdb

    mdb_xml = objectify.fromstring(open(filename, "rb").read())

    def read_entries(input, output):
        for record in input:
            if hasattr(record, 'course_id'):
                music_id = int(record.course_id.text)
            else:
                music_id = int(record.music_id.text)

            record_data = {}
            for k in record.__dict__.keys():
                record_data[k] = {}
                record_data[k]['type'] = getattr(record, k).get('__type')

                if k == "b_eemall":
                    record_data[k]['value'] = 0
                elif getattr(record, k).text:
                    record_data[k]['value'] = getattr(record, k).text
                else:
                    record_data[k]['value'] = ""

                if getattr(record, k).get('__count'):
                    expected_count = int(getattr(record, k).get('__count'))
                    record_data[k]['value'] = record_data[k]['value'].split(' ')

                    if len(record_data[k]['value']) != expected_count:
                        print(record_data[k])
                        print("Unexpected count in entry: {} items found, expected {}".format(len(record_data[k]['value']), expected_count))
                        exit(1)

            output[music_id] = record_data

    if hasattr(mdb_xml, 'mdb_data'):
        read_entries(mdb_xml.mdb_data, mdb['records'])

    if hasattr(mdb_xml, 'mdb_course'):
        read_entries(mdb_xml.mdb_course, mdb['courses'])

    return mdb


def get_next_id(mdb):
    next_id = 3000

    while next_id in mdb['records']:
        next_id += 1

    return next_id


def add_song_to_mdb(mdb, package, fresh=False, unsafe=False):
    xg_diff_list = [0] * 15
    if 'difficulty' in package:
        parts = ['guitar', 'drum', 'bass']
        difficulties = ['novice', 'basic', 'advanced', 'extreme', 'master']
        for part_idx in range(len(parts)):
            part = parts[part_idx]

            if part not in package['difficulty']:
                continue

            for difficulty_idx in range(len(difficulties)):
                difficulty = difficulties[difficulty_idx]

                if difficulty in package['difficulty'][part]:
                    xg_diff_list[(part_idx * 5) + difficulty_idx] = package['difficulty'][part][difficulty]

    new_record = {
        'pad_diff': {
            'type': "u16",
            'value': 0,
        },
        'seq_flag': {
            'type': "u16",
            'value': 0,
        },
        'xg_seq_flag': {
            'type': "u16",
            'value': 11,  # I know it's a bunch of flags, but what do they do exactly?
        },
        'first_ver': {
            'type': "u8",
            'value': [package.get('gf_ver', 2), package.get('dm_ver', 1)],
        },
        'first_classic_ver': {
            'type': "u8",
            'value': [0, 0],
        },
        'first_classic_ver': {
            'type': "u8",
            'value': [0, 0],
        },
        'b_eemall': {
            'type': "bool",
            'value': 1 if package.get('real_song', 1) not in [0, 1] else 1 - package.get('real_song', 1),
        },
        'order_kana': {
            'type': "u16",
            'value': 0,  # Can this be calculated somehow?
        },
        'category_kana': {
            'type': "s8",
            'value': 0,  # Can this be calculated somehow?
        },
        'artist_order_kana': {
            'type': "u16",
            'value': 0,  # Can this be calculated somehow?
        },
        'artist_category_kana': {
            'type': "s8",
            'value': 0,  # Can this be calculated somehow?
        },
        'secret': {
            'type': "u8",
            'value': [0, 0],
        },
        'xg_secret': {
            'type': "u8",
            'value': [0, 0],  # How would secrets work for customs anyway?
        },
        'b_session': {
            'type': "bool",
            'value': 0,
        },
        'gf_ofst': {
            'type': "s8",
            'value': 0,  # What is this exactly?
        },
        'dm_ofst': {
            'type': "s8",
            'value': 0,  # What is this exactly?
        },
        'chart_list': {
            'type': "u8",
            'value': [0] * 128,  # What is this exactly?
        },
        'origin': {
            'type': "u8",
            'value': 0,  # Not sure...
        },
        'is_remaster': {
            'type': "u8",
            'value': 0,  # Is this ever actually used for anything? :thinking:
        },
        'license_disp': {
            'type': "u8",
            'value': 0,  # Don't enable this, it will break shit
        },
        'default_music': {
            'type': "u8",
            'value': [1, 1],  # This makes it possible to play without proper eamuse support
        },
        'disable_area': {
            'type': "u8",
            'value': [0, 0, 0],  # You can force disable a song with this flag
        },
        'classics_diff_list': {
            'type': "u8",
            'value': [0] * 16
        },
        'bpm': {
            'type': "u16",
            'value': int(package.get('bpm', 0))
        },
        'bpm2': {
            'type': "u16",
            'value': int(package.get('bpm2', 0))
        },
        'b_long': {
            'type': "bool",
            'value': 1 if package.get('is_long', False) else 0
        },
        'xg_b_session': {
            'type': "bool",
            'value': 1 if package.get('session_enable', False) else 0
        },
        'speed': {
            'type': "u8",
            'value': package.get('speed', 0)
        },
        'life': {
            'type': "u8",
            'value': package.get('life', 0)
        },
        'music_type': {
            'type': "u8",
            'value': package.get('music_type', 0)
        },
        'genre': {
            'type': "u8",
            'value': package.get('genre', 0)
        },
        'type_category': {
            'type': "u32",
            'value': package.get('type_category', 0)
        },
        'xg_active_effect_type': {
            'type': "u8",
            'value': package.get('xg_active_effect_type', 0)
        },
        'xg_movie_disp_type': {
            'type': "u8",
            'value': package.get('xg_movie_disp_type', 0)
        },
        'xg_movie_disp_id': {
            'type': "s8",
            'value': -1 if 'files' in package and 'movie' in package['files'] else 8
        },
        'artist_title_ascii': {
            'type': "str",
            'value': "".join(filter(lambda x: x in set(string.printable), package.get('artist_ascii', "")[:15]))
        },
        'title_name': {
            'type': "str",
            'value': package.get('title', "")[:40]
        },
        'title_ascii': {
            'type': "str",
            'value': "".join(filter(lambda x: x in set(string.printable), package.get('title_ascii', "")[:15]))
        },
        'xg_diff_list': {
            'type': "u16",
            'value': xg_diff_list
        },
        'contain_stat': {
            'type': "u8",
            'value': [2 if 'guitar' in package['files'] else 0, 2 if 'drum' in package['files'] else 0]
        },
    }

    if 'extra' in package:
        for k in package['extra']:
            new_record[k] = {
                'type': package['extra'][k]['type'],
                'value': package['extra'][k]['value']
            }

    new_record['__hash'] = {
        'type': "str",
        'value': package['unique_id'],
    }

    # Check existing records for same hash
    # If same hash exists, delete old record and reuse the song id
    dupes = []
    for k in mdb['records']:
        if '__hash' in mdb['records'][k] and (fresh or mdb['records'][k]['__hash']['value'] == new_record['__hash']['value']):
            dupes.append(k)

    for k in dupes:
        print("Removing old object")
        del mdb['records'][k]

    music_id = package.get('music_id', None)

    if not music_id or not unsafe:
        music_id = get_next_id(mdb)

    package['music_id'] = music_id

    new_record['music_id'] = {
        'type': "s32",
        'value': package['music_id'],
    }

    mdb['records'][music_id] = new_record

    return mdb, dupes


def update_entry_orders(mdb):
    title_ascii_list = [""] + sorted([x for x in set([mdb['records'][k]['title_ascii']['value'] for k in mdb['records'] if 'title_ascii' in mdb['records'][k]]) if x])
    artist_title_ascii_list = [""] + sorted([x for x in set([mdb['records'][k]['artist_title_ascii']['value'] for k in mdb['records'] if 'artist_title_ascii' in mdb['records'][k]]) if x])

    for k in mdb['records']:
        order_ascii = title_ascii_list.index(mdb['records'][k]['title_ascii']['value']) + 1 if 'title_ascii' in mdb['records'][k] else 1
        mdb['records'][k]['order_ascii'] = {
            'type': "u16",
            'value': order_ascii
        }

        artist_order_ascii = artist_title_ascii_list.index(mdb['records'][k]['artist_title_ascii']['value']) + 1 if 'artist_title_ascii' in mdb['records'][k] else 1
        mdb['records'][k]['artist_order_ascii'] = {
            'type': "u16",
            'value': artist_order_ascii
        }

    return mdb


def save_mdb(mdb, output_filename):
    def remove_empty_counts(input):
        for x in input:
            for x2 in x:
                if x2.get('__count') in [None, 0, "0", "None"]:
                    del x2.attrib['__count']

    def get_tree_elements(input):
        return [
            [
                E(k2,
                    "{}".format(input[k][k2]['value'] if type(input[k][k2]['value']) != list else " ".join(["{}".format(x) for x in input[k][k2]['value']])),
                    __type=input[k][k2]['type'],
                    __count="{}".format(len(input[k][k2]['value'])) if type(input[k][k2]['value']) == list else "{}".format(input[k][k2]['count']) if 'count' in input[k][k2] else "0") for k2 in input[k]
            ] for k in input
        ]

    courses = get_tree_elements(mdb['courses'])
    remove_empty_counts(courses)

    records = get_tree_elements(mdb['records'])
    remove_empty_counts(records)

    mdb_tree = E.mdb(
        E.header(
            E.data(
                E.id("71 70 47 68 77 109 100 98", __type="s8", __count="8"),
                E.format("203", __type="s32"),
                E.chksum("0", __type="s32"),
                E.header_sz("64", __type="s16"),
                E.record_sz("300", __type="s16"),
                E.record_nr("{}".format(len(mdb['records'].keys())), __type="s16"),
                E.course_sz("40", __type="s16"),
                E.course_nr("{}".format(len(mdb['courses'].keys())), __type="s16"),
            )
        ),
        *[E.mdb_data(*x) for x in records],
        *[E.mdb_course(*x) for x in courses],
    )

    open(output_filename, "w", encoding="utf-8").write(etree.tostring(mdb_tree, encoding='unicode', pretty_print=True))


def add_packages_to_mdb(mdb_filename, packages, fresh, unsafe):
    if not os.path.exists(mdb_filename):
        print("Couldn't find", mdb_filename)
        return []

    mdb = read_mdb(mdb_filename)

    dupes = []
    for package in packages:
        mdb, dupe = add_song_to_mdb(mdb, package, fresh, unsafe)
        dupe += dupes

    mdb = update_entry_orders(mdb)
    save_mdb(mdb, mdb_filename)

    return list(set(dupes))


def get_package_info(packages_directory="packages"):
    packages = []

    for filename in glob.glob(os.path.join(packages_directory, "**\\package.json")):
        package = json.load(open(filename, "r", encoding="utf-8"))

        if 'unique_id' not in package:
            package['unique_id'] = str(uuid.uuid4()).replace("-","")
            json.dump(package, open(filename, "w", encoding="utf-8"), ensure_ascii=False, indent=4, separators=(', ', ': '))
            print("Added new unique_id to package info")

        package['__directory'] = os.path.dirname(filename)
        packages.append(package)

    return packages


def prepare_graphics_for_package(package):
    # Automatically generate all images possible that weren't provided by the user
    output_directory = tmpfile.mkdtemp("textgen")

    # TODO: mono for Linux?
    subprocess.call("\"{}\" solid \"{}\" \"{}\" \"{}\"".format(resource_path(os.path.join("tools", "gitadora-textgen.exe")), package['title'], package['artist'], output_directory), shell=True)

    def copy_file(entry_name, filename):
        if 'graphics' not in package:
            package['graphics'] = {}

        if entry_name in package['graphics'] and os.path.exists(os.path.join(package['__directory'], package['graphics'][entry_name])):
            return

        temp_filename = os.path.join(output_directory, filename)

        if os.path.exists(temp_filename):
            shutil.copy(temp_filename, os.path.join(package['__directory'], filename))
            package['graphics'][entry_name] = filename

            tmpfile.add_temp_file(os.path.join(package['__directory'], filename))

    copy_file("artist", "artist.png")
    copy_file("title", "title.png")
    copy_file("title_small", "title_small.png")

    if 'graphics' in package and 'jacket' in package['graphics'] and package['graphics']['jacket']:
        jacket_img = Image.open(os.path.join(package['__directory'], package['graphics']['jacket'])).convert("RGB")

        jacket_384 = jacket_img.resize((384, 384))
        jacket_384_filename = os.path.join(package['__directory'], "jacket_384.png")
        jacket_384.save(jacket_384_filename)
        package['graphics']['jacket'] = "jacket_384.png"
        tmpfile.add_temp_file(jacket_384_filename)

        jacket_64 = jacket_img.resize((64, 64))
        jacket_64_filename = os.path.join(package['__directory'], "jacket_64.png")
        jacket_64.save(jacket_64_filename)
        package['graphics']['jacket_small'] = "jacket_64.png"
        tmpfile.add_temp_file(jacket_64_filename)

        jacket_img.close()
        del jacket_img


def patch_sq3(filename, music_id):
    # Patch music ID in SQ3 file or else the game will crash
    data = open(filename, "rb").read()
    data = data[:0x14] + struct.pack("<I", music_id) + data[0x18:]
    open(filename, "wb").write(data)


def create_song_data_ifs_for_package(package, ifs_data_folder="data\\ifs_pack"):
    data_folder = ("d%04d" % package['music_id'])[:4]
    output_folder = os.path.join(ifs_data_folder, data_folder)
    seq_ifs_outputfile = os.path.join(output_folder, "m%04d_seq.ifs" % package['music_id'])
    bgm_ifs_outputfile = os.path.join(output_folder, "m%04d_bgm.ifs" % package['music_id'])

    os.makedirs(output_folder, exist_ok=True)

    seq_folder = tmpfile.mkdtemp("seq")
    bgm_folder = tmpfile.mkdtemp("bgm")

    if 'files' in package and 'drum' in package['files']:
        if 'guitar' not in package['files']:
            package['files']['guitar'] = package['files']['drum']

    elif 'files' in package and 'guitar' in package['files']:
        if 'drum' not in package['files']:
            package['files']['drum'] = package['files']['guitar']

    if 'files' in package and 'drum' in package['files']:
        if 'seq' in package['files']['drum']:
            shutil.copy(os.path.join(package['__directory'], package['files']['drum']['seq']), os.path.join(seq_folder, "d%04d.sq3" % package['music_id']))
            patch_sq3(os.path.join(seq_folder, "d%04d.sq3" % package['music_id']), package['music_id'])

        if 'sound' in package['files']['drum']:
            shutil.copy(os.path.join(package['__directory'], package['files']['drum']['sound']), os.path.join(seq_folder, "spu%04dd.va3" % package['music_id']))

    if 'files' in package and 'guitar' in package['files']:
        if 'seq' in package['files']['guitar']:
            shutil.copy(os.path.join(package['__directory'], package['files']['guitar']['seq']), os.path.join(seq_folder, "g%04d.sq3" % package['music_id']))
            patch_sq3(os.path.join(seq_folder, "g%04d.sq3" % package['music_id']), package['music_id'])

        if 'sound' in package['files']['guitar']:
            shutil.copy(os.path.join(package['__directory'], package['files']['guitar']['sound']), os.path.join(seq_folder, "spu%04dg.va3" % package['music_id']))

    if 'event' in package['files']:
        shutil.copy(os.path.join(package['__directory'], package['files']['event']), os.path.join(seq_folder, "event%04d.ev2" % package['music_id']))
    ifs.create(seq_folder, seq_ifs_outputfile)

    if 'bgm' in package['files']:
        for k in package['files']['bgm']:
            shutil.copy(os.path.join(package['__directory'], package['files']['bgm'][k]), os.path.join(bgm_folder, "bgm%04d%s.bin" % (package['music_id'], k)))
        if 'drum' in package['files'] and 'preview' in package['files']['drum']:
            shutil.copy(os.path.join(package['__directory'], package['files']['drum']['preview']), os.path.join(bgm_folder, "i%04ddm.bin" % package['music_id']))
        if 'guitar' in package['files'] and 'preview' in package['files']['guitar']:
            shutil.copy(os.path.join(package['__directory'], package['files']['drum']['preview']), os.path.join(bgm_folder, "i%04dgf.bin" % package['music_id']))
    ifs.create(bgm_folder, bgm_ifs_outputfile)


def create_graphic_ifs_for_packages(packages, key, base_filename, output_filename):
    output_directory = os.path.dirname(output_filename)

    os.makedirs(output_directory, exist_ok=True)

    _, ifs_path = ifs.extract(output_filename)

    for package in packages:
        if 'graphics' in package and key in package['graphics'] and package['graphics'][key]:
            convert_image_to_tex(os.path.join(package['__directory'], package['graphics'][key]), os.path.join(ifs_path, "%s%04d%s" % (base_filename, package['music_id'], os.path.splitext(package['graphics'][key])[1])))

    ifs.create(ifs_path, output_filename)


def read_notes_info(filename):
    seq_infos = {}

    if not os.path.exists(filename):
        return seq_infos

    seq_xml = objectify.fromstring(open(filename, "rb").read())

    if not hasattr(seq_xml, 'seq_info'):
        return seq_infos

    for info in seq_xml.seq_info:
        music_id = int(info.music_id.text)
        note_data = {
            'music_id': music_id,
            'data': {}
        }

        def read_data(data, part):
            output = {}

            for diff in range(0, 5):
                if hasattr(data, 'diff_level%d' % diff):
                    attr = getattr(data, 'diff_level%d' % diff)
                    notes = int(attr.notes_nr.text)

                    if hasattr(attr, 'fret'):
                        # Drum
                        note_data = [int(x) for x in attr.fret.text.split(' ')]
                        note_data = {
                            "r": note_data[0],
                            "g": note_data[1],
                            "b": note_data[2],
                            "y": note_data[3],
                            "p": note_data[4],
                            "open": note_data[5],
                        }
                    elif hasattr(attr, 'pad'):
                        # Drum
                        note_data = [int(x) for x in attr.pad.text.split(' ')]
                        note_data = {
                            "leftcymbal": note_data[0],
                            "hihat": note_data[1],
                            "leftpedal": note_data[2],
                            "snare": note_data[3],
                            "hightom": note_data[4],
                            "bass": note_data[5],
                            "lowtom": note_data[6],
                            "floortom": note_data[7],
                            "rightcymbal": note_data[8],
                        }

                else:
                    notes = 0
                    if part in ['guitar', 'bass']:
                        # Drum
                        note_data = [0] * 6
                        note_data = {
                            "r": note_data[0],
                            "g": note_data[1],
                            "b": note_data[2],
                            "y": note_data[3],
                            "p": note_data[4],
                            "open": note_data[5],
                        }
                    elif part == 'drum':
                        # Drum
                        note_data = [0] * 9
                        note_data = {
                            "leftcymbal": note_data[0],
                            "hihat": note_data[1],
                            "leftpedal": note_data[2],
                            "snare": note_data[3],
                            "hightom": note_data[4],
                            "bass": note_data[5],
                            "lowtom": note_data[6],
                            "floortom": note_data[7],
                            "rightcymbal": note_data[8],
                        }

                output[['nov', 'bsc', 'adv', 'ext', 'mst'][diff]] = {
                    'total': notes,
                    'notes': note_data
                }

            return output

        if hasattr(info, 'gf'):
            if hasattr(info.gf, 'seq_type0'):
                # Guitar
                note_data['data']['guitar'] = read_data(info.gf.seq_type0, 'guitar')

            if hasattr(info.gf, 'seq_type1'):
                # Bass
                note_data['data']['bass'] = read_data(info.gf.seq_type1, 'bass')

        if hasattr(info, 'dm'):
            # Drum
            note_data['data']['drum'] = read_data(info.dm, 'drum')

        seq_infos[music_id] = note_data

    return seq_infos


def save_notes_info(filename, notes_info):
    note_info_tree = E.seq_xg(
        *[E.seq_info(
            E.music_id("%d" % notes_info[x]['music_id'], __type="s32"),
            E.gf(
                E.seq_type0(
                    E.diff_level0(
                        E.notes_nr("%d" % notes_info[x]['data']['guitar']['nov']['total'], __type="s32"),
                        E.fret(" ".join(["%d" % n for n in [notes_info[x]['data']['guitar']['nov']['notes']['r'], notes_info[x]['data']['guitar']['nov']['notes']['g'], notes_info[x]['data']['guitar']['nov']['notes']['b'], notes_info[x]['data']['guitar']['nov']['notes']['y'], notes_info[x]['data']['guitar']['nov']['notes']['p'], notes_info[x]['data']['guitar']['nov']['notes']['open']]]), __type="s32", __count="6"),
                    ),
                    E.diff_level1(
                        E.notes_nr("%d" % notes_info[x]['data']['guitar']['bsc']['total'], __type="s32"),
                        E.fret(" ".join(["%d" % n for n in [notes_info[x]['data']['guitar']['bsc']['notes']['r'], notes_info[x]['data']['guitar']['bsc']['notes']['g'], notes_info[x]['data']['guitar']['bsc']['notes']['b'], notes_info[x]['data']['guitar']['bsc']['notes']['y'], notes_info[x]['data']['guitar']['bsc']['notes']['p'], notes_info[x]['data']['guitar']['bsc']['notes']['open']]]), __type="s32", __count="6"),
                    ),
                    E.diff_level2(
                        E.notes_nr("%d" % notes_info[x]['data']['guitar']['adv']['total'], __type="s32"),
                        E.fret(" ".join(["%d" % n for n in [notes_info[x]['data']['guitar']['adv']['notes']['r'], notes_info[x]['data']['guitar']['adv']['notes']['g'], notes_info[x]['data']['guitar']['adv']['notes']['b'], notes_info[x]['data']['guitar']['adv']['notes']['y'], notes_info[x]['data']['guitar']['adv']['notes']['p'], notes_info[x]['data']['guitar']['adv']['notes']['open']]]), __type="s32", __count="6"),
                    ),
                    E.diff_level3(
                        E.notes_nr("%d" % notes_info[x]['data']['guitar']['ext']['total'], __type="s32"),
                        E.fret(" ".join(["%d" % n for n in [notes_info[x]['data']['guitar']['ext']['notes']['r'], notes_info[x]['data']['guitar']['ext']['notes']['g'], notes_info[x]['data']['guitar']['ext']['notes']['b'], notes_info[x]['data']['guitar']['ext']['notes']['y'], notes_info[x]['data']['guitar']['ext']['notes']['p'], notes_info[x]['data']['guitar']['ext']['notes']['open']]]), __type="s32", __count="6"),
                    ),
                    E.diff_level4(
                        E.notes_nr("%d" % notes_info[x]['data']['guitar']['mst']['total'], __type="s32"),
                        E.fret(" ".join(["%d" % n for n in [notes_info[x]['data']['guitar']['mst']['notes']['r'], notes_info[x]['data']['guitar']['mst']['notes']['g'], notes_info[x]['data']['guitar']['mst']['notes']['b'], notes_info[x]['data']['guitar']['mst']['notes']['y'], notes_info[x]['data']['guitar']['mst']['notes']['p'], notes_info[x]['data']['guitar']['mst']['notes']['open']]]), __type="s32", __count="6"),
                    ),
                ),
                E.seq_type1(
                    E.diff_level0(
                        E.notes_nr("%d" % notes_info[x]['data']['bass']['nov']['total'], __type="s32"),
                        E.fret(" ".join(["%d" % n for n in [notes_info[x]['data']['bass']['nov']['notes']['r'], notes_info[x]['data']['bass']['nov']['notes']['g'], notes_info[x]['data']['bass']['nov']['notes']['b'], notes_info[x]['data']['bass']['nov']['notes']['y'], notes_info[x]['data']['bass']['nov']['notes']['p'], notes_info[x]['data']['bass']['nov']['notes']['open']]]), __type="s32", __count="6"),
                    ),
                    E.diff_level1(
                        E.notes_nr("%d" % notes_info[x]['data']['bass']['bsc']['total'], __type="s32"),
                        E.fret(" ".join(["%d" % n for n in [notes_info[x]['data']['bass']['bsc']['notes']['r'], notes_info[x]['data']['bass']['bsc']['notes']['g'], notes_info[x]['data']['bass']['bsc']['notes']['b'], notes_info[x]['data']['bass']['bsc']['notes']['y'], notes_info[x]['data']['bass']['bsc']['notes']['p'], notes_info[x]['data']['bass']['bsc']['notes']['open']]]), __type="s32", __count="6"),
                    ),
                    E.diff_level2(
                        E.notes_nr("%d" % notes_info[x]['data']['bass']['adv']['total'], __type="s32"),
                        E.fret(" ".join(["%d" % n for n in [notes_info[x]['data']['bass']['adv']['notes']['r'], notes_info[x]['data']['bass']['adv']['notes']['g'], notes_info[x]['data']['bass']['adv']['notes']['b'], notes_info[x]['data']['bass']['adv']['notes']['y'], notes_info[x]['data']['bass']['adv']['notes']['p'], notes_info[x]['data']['bass']['adv']['notes']['open']]]), __type="s32", __count="6"),
                    ),
                    E.diff_level3(
                        E.notes_nr("%d" % notes_info[x]['data']['bass']['ext']['total'], __type="s32"),
                        E.fret(" ".join(["%d" % n for n in [notes_info[x]['data']['bass']['ext']['notes']['r'], notes_info[x]['data']['bass']['ext']['notes']['g'], notes_info[x]['data']['bass']['ext']['notes']['b'], notes_info[x]['data']['bass']['ext']['notes']['y'], notes_info[x]['data']['bass']['ext']['notes']['p'], notes_info[x]['data']['bass']['ext']['notes']['open']]]), __type="s32", __count="6"),
                    ),
                    E.diff_level4(
                        E.notes_nr("%d" % notes_info[x]['data']['bass']['mst']['total'], __type="s32"),
                        E.fret(" ".join(["%d" % n for n in [notes_info[x]['data']['bass']['mst']['notes']['r'], notes_info[x]['data']['bass']['mst']['notes']['g'], notes_info[x]['data']['bass']['mst']['notes']['b'], notes_info[x]['data']['bass']['mst']['notes']['y'], notes_info[x]['data']['bass']['mst']['notes']['p'], notes_info[x]['data']['bass']['mst']['notes']['open']]]), __type="s32", __count="6"),
                    ),
                ),
            ),
            E.dm(
                E.diff_level0(
                    E.notes_nr("%d" % notes_info[x]['data']['drum']['nov']['total'], __type="s32"),
                    E.pad(" ".join(["%d" % n for n in [notes_info[x]['data']['drum']['nov']['notes']['leftcymbal'], notes_info[x]['data']['drum']['nov']['notes']['hihat'], notes_info[x]['data']['drum']['nov']['notes']['leftpedal'], notes_info[x]['data']['drum']['nov']['notes']['snare'], notes_info[x]['data']['drum']['nov']['notes']['hightom'], notes_info[x]['data']['drum']['nov']['notes']['bass'], notes_info[x]['data']['drum']['nov']['notes']['lowtom'], notes_info[x]['data']['drum']['nov']['notes']['floortom'], notes_info[x]['data']['drum']['nov']['notes']['rightcymbal']]]), __type="s32", __count="9"),
                ),
                E.diff_level1(
                    E.notes_nr("%d" % notes_info[x]['data']['drum']['bsc']['total'], __type="s32"),
                    E.pad(" ".join(["%d" % n for n in [notes_info[x]['data']['drum']['bsc']['notes']['leftcymbal'], notes_info[x]['data']['drum']['bsc']['notes']['hihat'], notes_info[x]['data']['drum']['bsc']['notes']['leftpedal'], notes_info[x]['data']['drum']['bsc']['notes']['snare'], notes_info[x]['data']['drum']['bsc']['notes']['hightom'], notes_info[x]['data']['drum']['bsc']['notes']['bass'], notes_info[x]['data']['drum']['bsc']['notes']['lowtom'], notes_info[x]['data']['drum']['bsc']['notes']['floortom'], notes_info[x]['data']['drum']['bsc']['notes']['rightcymbal']]]), __type="s32", __count="9"),
                ),
                E.diff_level2(
                    E.notes_nr("%d" % notes_info[x]['data']['drum']['adv']['total'], __type="s32"),
                    E.pad(" ".join(["%d" % n for n in [notes_info[x]['data']['drum']['adv']['notes']['leftcymbal'], notes_info[x]['data']['drum']['adv']['notes']['hihat'], notes_info[x]['data']['drum']['adv']['notes']['leftpedal'], notes_info[x]['data']['drum']['adv']['notes']['snare'], notes_info[x]['data']['drum']['adv']['notes']['hightom'], notes_info[x]['data']['drum']['adv']['notes']['bass'], notes_info[x]['data']['drum']['adv']['notes']['lowtom'], notes_info[x]['data']['drum']['adv']['notes']['floortom'], notes_info[x]['data']['drum']['adv']['notes']['rightcymbal']]]), __type="s32", __count="9"),
                ),
                E.diff_level3(
                    E.notes_nr("%d" % notes_info[x]['data']['drum']['ext']['total'], __type="s32"),
                    E.pad(" ".join(["%d" % n for n in [notes_info[x]['data']['drum']['ext']['notes']['leftcymbal'], notes_info[x]['data']['drum']['ext']['notes']['hihat'], notes_info[x]['data']['drum']['ext']['notes']['leftpedal'], notes_info[x]['data']['drum']['ext']['notes']['snare'], notes_info[x]['data']['drum']['ext']['notes']['hightom'], notes_info[x]['data']['drum']['ext']['notes']['bass'], notes_info[x]['data']['drum']['ext']['notes']['lowtom'], notes_info[x]['data']['drum']['ext']['notes']['floortom'], notes_info[x]['data']['drum']['ext']['notes']['rightcymbal']]]), __type="s32", __count="9"),
                ),
                E.diff_level4(
                    E.notes_nr("%d" % notes_info[x]['data']['drum']['mst']['total'], __type="s32"),
                    E.pad(" ".join(["%d" % n for n in [notes_info[x]['data']['drum']['mst']['notes']['leftcymbal'], notes_info[x]['data']['drum']['mst']['notes']['hihat'], notes_info[x]['data']['drum']['mst']['notes']['leftpedal'], notes_info[x]['data']['drum']['mst']['notes']['snare'], notes_info[x]['data']['drum']['mst']['notes']['hightom'], notes_info[x]['data']['drum']['mst']['notes']['bass'], notes_info[x]['data']['drum']['mst']['notes']['lowtom'], notes_info[x]['data']['drum']['mst']['notes']['floortom'], notes_info[x]['data']['drum']['mst']['notes']['rightcymbal']]]), __type="s32", __count="9"),
                ),
            )
        ) for x in sorted(notes_info.keys(), key=lambda x:int(x))]
    )

    if not os.path.exists(filename):
        os.makedirs(os.path.dirname(filename), exist_ok=True)

    open(filename, "w", encoding="utf-8").write(etree.tostring(note_info_tree, encoding='unicode', pretty_print=True))


def add_packages_to_notes_info(filename, packages, dupes):
    notes_info = read_notes_info(filename)

    # Remove dupes/removed songs
    for song_id in dupes:
        if song_id in notes_info:
            del notes_info[song_id]

    # Add new entries for packages
    for package in packages:
        if 'notes' in package:
            new_entry = {
                'music_id': package['music_id'],
                'data': {
                    'guitar': {
                        'nov': {
                            'total': 0,
                            'notes': {"r": 0, "g": 0, "b": 0, "y": 0, "p": 0, "open": 0}
                        },
                        'bsc': {
                            'total': 0,
                            'notes': {"r": 0, "g": 0, "b": 0, "y": 0, "p": 0, "open": 0}
                        },
                        'adv': {
                            'total': 0,
                            'notes': {"r": 0, "g": 0, "b": 0, "y": 0, "p": 0, "open": 0}
                        },
                        'ext': {
                            'total': 0,
                            'notes': {"r": 0, "g": 0, "b": 0, "y": 0, "p": 0, "open": 0}
                        },
                        'mst': {
                            'total': 0,
                            'notes': {"r": 0, "g": 0, "b": 0, "y": 0, "p": 0, "open": 0}
                        }
                    },
                    'bass': {
                        'nov': {
                            'total': 0,
                            'notes': {"r": 0, "g": 0, "b": 0, "y": 0, "p": 0, "open": 0}
                        },
                        'bsc': {
                            'total': 0,
                            'notes': {"r": 0, "g": 0, "b": 0, "y": 0, "p": 0, "open": 0}
                        },
                        'adv': {
                            'total': 0,
                            'notes': {"r": 0, "g": 0, "b": 0, "y": 0, "p": 0, "open": 0}
                        },
                        'ext': {
                            'total': 0,
                            'notes': {"r": 0, "g": 0, "b": 0, "y": 0, "p": 0, "open": 0}
                        },
                        'mst': {
                            'total': 0,
                            'notes': {"r": 0, "g": 0, "b": 0, "y": 0, "p": 0, "open": 0}
                        }
                    },
                    'drum': {
                        'nov': {
                            'total': 0,
                            'notes': {"leftcymbal": 0,  "hihat": 0,  "leftpedal": 0,  "snare": 0,  "hightom": 0,  "bass": 0,  "lowtom": 0,  "floortom": 0,  "rightcymbal": 0}
                        },
                        'bsc': {
                            'total': 0,
                            'notes': {"leftcymbal": 0,  "hihat": 0,  "leftpedal": 0,  "snare": 0,  "hightom": 0,  "bass": 0,  "lowtom": 0,  "floortom": 0,  "rightcymbal": 0}
                        },
                        'adv': {
                            'total': 0,
                            'notes': {"leftcymbal": 0,  "hihat": 0,  "leftpedal": 0,  "snare": 0,  "hightom": 0,  "bass": 0,  "lowtom": 0,  "floortom": 0,  "rightcymbal": 0}
                        },
                        'ext': {
                            'total': 0,
                            'notes': {"leftcymbal": 0,  "hihat": 0,  "leftpedal": 0,  "snare": 0,  "hightom": 0,  "bass": 0,  "lowtom": 0,  "floortom": 0,  "rightcymbal": 0}
                        },
                        'mst': {
                            'total': 0,
                            'notes': {"leftcymbal": 0,  "hihat": 0,  "leftpedal": 0,  "snare": 0,  "hightom": 0,  "bass": 0,  "lowtom": 0,  "floortom": 0,  "rightcymbal": 0}
                        }
                    }
                }
            }

            difficulties = ['nov', 'bsc', 'adv', 'ext', 'mst']
            if 'drum' in package['notes']:
                for difficulty in package['notes']['drum']:
                    idx = difficulties.index(difficulty)

                    parts = ["leftcymbal", "hihat", "leftpedal", "snare", "hightom", "bass", "lowtom", "floortom", "rightcymbal"]
                    for pidx in range(len(parts)):
                        if parts[pidx] in package['notes']['drum'][difficulty]['notes']:
                            new_entry['data']['drum'][difficulty]['notes'][parts[pidx]] = int(package['notes']['drum'][difficulty]['notes'][parts[pidx]])

                    new_entry['data']['drum'][difficulty]['total'] = int(package['notes']['drum'][difficulty]['total']) if 'total' in package['notes']['drum'][difficulty] else 0

            if 'guitar' in package['notes']:
                for difficulty in package['notes']['guitar']:
                    idx = difficulties.index(difficulty)

                    parts = ["r", "g", "b", "y", "p", "open"]
                    for pidx in range(len(parts)):
                        if parts[pidx] in package['notes']['guitar'][difficulty]['notes']:
                            new_entry['data']['guitar'][difficulty]['notes'][parts[pidx]] = int(package['notes']['guitar'][difficulty]['notes'][parts[pidx]])

                    new_entry['data']['guitar'][difficulty]['total'] = int(package['notes']['guitar'][difficulty]['total']) if 'total' in package['notes']['guitar'][difficulty] else 0

            if 'bass' in package['notes']:
                for difficulty in package['notes']['bass']:
                    idx = difficulties.index(difficulty)

                    parts = ["r", "g", "b", "y", "p", "open"]
                    for pidx in range(len(parts)):
                        if parts[pidx] in package['notes']['bass'][difficulty]['notes']:
                            new_entry['data']['bass'][difficulty]['notes'][parts[pidx]] = int(package['notes']['bass'][difficulty]['notes'][parts[pidx]])

                    new_entry['data']['bass'][difficulty]['total'] = int(package['notes']['bass'][difficulty]['total']) if 'total' in package['notes']['bass'][difficulty] else 0

        notes_info[package['music_id']] = new_entry

    # Save notes_info.xml again
    save_notes_info(filename, notes_info)


def read_phrase_address_list(filename):
    pal = {}

    if not os.path.exists(filename):
        return pal

    pal_xml = objectify.fromstring(open(filename, "rb").read())

    if not hasattr(pal_xml, 'scene_data') or not hasattr(pal_xml.scene_data, 'scene_m_data'):
        return pal

    for scene_data in pal_xml.scene_data.scene_m_data:
        music_id = int(scene_data.music_id.text)
        version = int(scene_data.version.text)
        data = []

        num = int(scene_data.num.text)
        for i in range(1, num + 1):
            address = int(getattr(scene_data, 'address%d' % i).text)
            address_type = int(getattr(scene_data, 'type%d' % i).text)

            data.append({
                'address': address,
                'address_type': address_type
            })

        pal[music_id] = {
            'music_id': music_id,
            'version': version,
            'addresses': data
        }

    return pal


def save_phrase_address_list(filename, pal):
    pal_tree = E.phrase_data(
        E.format("100", __type="s32"),
        E.total_musicnum("%d" % len(pal.keys()), __type="s32"),
        E.scene_data(
            *[E.scene_m_data(
                E.music_id("%d" % x, __type="s32"),
                E.version("%d" % pal[x]['version'], __type="s32"),
                E.num("%d" % len(pal[x]['addresses']), __type="s32"),
                *[E('address%d' % (idx + 1), "%d" % pal[x]['addresses'][idx]['address'] if idx < len(pal[x]['addresses']) else "0", __type="s32") for idx in range(16)],
                *[E('type%d' % (idx + 1), "%d" % pal[x]['addresses'][idx]['address_type'] if idx < len(pal[x]['addresses']) else "0", __type="s32") for idx in range(16)]
            ) for x in sorted(pal.keys(), key=lambda x:int(x))]
        )
    )

    if not os.path.exists(filename):
        os.makedirs(os.path.dirname(filename), exist_ok=True)

    open(filename, "w", encoding="utf-8").write(etree.tostring(pal_tree, encoding='unicode', pretty_print=True))


def add_packages_to_phrase_address_list(filename, packages, dupes):
    pal = read_phrase_address_list(filename)

    # Remove dupes/removed songs
    for song_id in dupes:
        if song_id in pal:
            del pal[song_id]

    # Add new phrase address info for pages
    for package in packages:
        if 'phrase_list' in package and 'phrases' in package['phrase_list']:
            new_entry = {
                'music_id': package['music_id'],
                'version': package['phrase_list']['version'] if 'version' in package['phrase_list'] else 1,
                'addresses': [{
                    'address': x['address'],
                    'address_type': x['type']
                } for x in sorted(package['phrase_list']['phrases'], key=lambda x:x['address'])]
            }

            pal[package['music_id']] = new_entry

    # Save notes_info.xml again
    save_phrase_address_list(filename, pal)


def install_packages(game_directory="", packages_directory="packages", game_data_folder="data", fresh=False, unsafe=False, new_only=False):
    packages = get_package_info(packages_directory)

    game_data_folder = os.path.join(game_directory, game_data_folder)

    dupes = []
    dupes += add_packages_to_mdb(os.path.join(game_data_folder, "product", "xml", "mdb_xg.xml"), packages, fresh, unsafe)
    dupes += add_packages_to_mdb(os.path.join(game_data_folder, "product", "xml", "mdb_mt.xml"), packages, fresh, unsafe)

    add_packages_to_notes_info(os.path.join(game_data_folder, "product", "xml", "notes_info.xml"), packages, dupes)
    add_packages_to_phrase_address_list(os.path.join(game_data_folder, "product", "xml", "phrase_address_list.xml"), packages, dupes)

    real_last_id = get_last_archive_id(os.path.join(game_directory, "libshare-pj.dll"))

    packages_split = {}
    for package in packages:
        data_folder = ("d%04d" % package['music_id'])[:4]
        ifs_data_folder = "data\\ifs_pack"
        output_folder = os.path.join(ifs_data_folder, data_folder)
        seq_ifs_outputfile = os.path.join(output_folder, "m%04d_seq.ifs" % package['music_id'])
        bgm_ifs_outputfile = os.path.join(output_folder, "m%04d_bgm.ifs" % package['music_id'])

        if new_only and os.path.exists(seq_ifs_outputfile) and os.path.exists(bgm_ifs_outputfile):
            print("Already exists, skipping package", package['__directory'])
            continue

        prepare_graphics_for_package(package)
        create_song_data_ifs_for_package(package, ifs_data_folder)

        # Copy movie file
        if 'files' in package and 'movie' in package['files']:
            shutil.copy(os.path.join(package['__directory'], package['files']['movie']), os.path.join("data", "product", "movie", "music", "mv%04d.wmv" % package['music_id']))

        # Split packages by music id so it's possible to insert images into the proper archives later
        package_key = int(("%04d" % package['music_id'])[:2])

        if package_key > real_last_id:
            package_key = real_last_id

        if package_key not in packages_split:
            packages_split[package_key] = []

        packages_split[package_key].append(package)

    for last_id in packages_split:
        create_graphic_texbin_for_packages(packages_split[last_id], "jacket_small", "img_jkb", os.path.join(game_data_folder, "product", "d3", "model", "tex_img_jkb%02d.bin" % last_id))
        create_graphic_texbin_for_packages(packages_split[last_id], "title_small", "img_idb", os.path.join(game_data_folder, "product", "d3", "model", "tex_img_idb%02d.bin" % last_id))
        create_graphic_ifs_for_packages(packages_split[last_id], "jacket", "img_jk", os.path.join(game_data_folder, "product", "jacket", "img_jk%02d.ifs" % last_id))
        create_graphic_ifs_for_packages(packages_split[last_id], "title", "img_id", os.path.join(game_data_folder, "product", "jacket", "img_idw%02d.ifs" % last_id))
        create_graphic_ifs_for_packages(packages_split[last_id], "artist", "img_at", os.path.join(game_data_folder, "product", "jacket", "img_atw%02d.ifs" % last_id))

    tmpfile.tmpcleanup()


def get_last_archive_id(dll_filename="libshare-pj.dll"):
    if not os.path.exists(dll_filename):
        return None

    dll_data = bytearray(open(dll_filename, "rb").read())

    # Find all img_at IFS filename
    # img_id and img_jk have some extras which make it harder to determine the last actual song-related archive ID
    idx = dll_data.find(bytearray("img_at", encoding="ascii"))
    last_id = int(dll_data[idx:dll_data.find(0x00, idx)].decode('utf-8')[-2:])

    return last_id


def patch_dll_for_customs(dll_filename="libshare-pj.dll"):
    if not os.path.exists(dll_filename):
        print("Couldn't find %s, aborting DLL patching step... (is the tool installed in the right directory?)" % dll_filename)
        return

    last_id = get_last_archive_id(dll_filename)

    if last_id is None:
        return

    dll_data = bytearray(open(dll_filename, "rb").read())

    # Patch the max song ID for the last archive
    patch_pattern = bytearray([0x80, 0x01, 0x00, 0x00, 0x00]) + struct.pack("<I", last_id * 100)

    idx = dll_data.find(patch_pattern)
    while idx != -1:
        dll_data[idx+len(patch_pattern):idx+len(patch_pattern)+4] = struct.pack("<I", 0xfff)
        idx = dll_data.find(patch_pattern, idx + 1)

    backup_file(dll_filename)
    open(dll_filename, "wb").write(dll_data)


def convert_image_to_tex(input_filename, output_filename):
    # Copy file to folder
    image_filename = shutil.copy(input_filename, output_filename)

    # Call gitadora-textool
    subprocess.call("\"{}\" \"{}\"".format(resource_path(os.path.join("tools", "gitadora-textool.exe")), image_filename), shell=True)

    # Delete file from tolder
    os.unlink(image_filename)


def create_graphic_texbin_for_packages(packages, key, base_filename, output_filename):
    output_filename = os.path.abspath(output_filename)
    texbin_directory = os.path.splitext(output_filename)[0]

    os.makedirs(texbin_directory, exist_ok=True)

    tmpfile.add_temp_folder(texbin_directory)

    subprocess.call("\"{}\" \"{}\"".format(resource_path(os.path.join("tools", "gitadora-texbintool.exe")), output_filename), shell=True)

    # Copy all images to texbin folder with appropriate filenames
    for package in packages:
        if 'graphics' in package and key in package['graphics']:
            image_filename = os.path.join(package['__directory'], package['graphics'][key])
            ext = os.path.splitext(image_filename)[-1]
            output_image_filename = os.path.join(texbin_directory, "%s%04d%s" % (base_filename, package['music_id'], ext))
            shutil.copy(image_filename, output_image_filename)

    # Create texbin
    subprocess.call("\"{}\" \"{}\"".format(resource_path(os.path.join("tools", "gitadora-texbintool.exe")), texbin_directory), shell=True)


def patch_graphics_for_customs(game_directory="", jacket_folder="data\\product\\jacket\\", customs_banner_image="customs_banner.png", customs_jacket_image="customs_jacket.png"):
    jacket_folder = os.path.join(game_directory, jacket_folder)
    ifs_input_path = os.path.join(jacket_folder, "img_id90.ifs")
    if os.path.exists(ifs_input_path):
        backup_file(ifs_input_path)
        _, ifs_path = ifs.extract(ifs_input_path)
        convert_image_to_tex(customs_banner_image, os.path.join(ifs_path, "img_id9112.png"))
        convert_image_to_tex(customs_banner_image, os.path.join(ifs_path, "img_id9162.png"))
        ifs.create(ifs_path, ifs_input_path)
    else:
        print("Couldn't find img_id90.ifs, can't patch customs banner image")

    ifs_input_path = os.path.join(jacket_folder, "img_jk90.ifs")
    if os.path.exists(ifs_input_path):
        backup_file(ifs_input_path)
        _, ifs_path = ifs.extract(ifs_input_path)
        convert_image_to_tex(customs_jacket_image, os.path.join(ifs_path, "img_jk9112.png"))
        convert_image_to_tex(customs_jacket_image, os.path.join(ifs_path, "img_jk9162.png"))
        ifs.create(ifs_path, ifs_input_path)
    else:
        print("Couldn't find img_jk90.ifs, can't patch customs jacket image")


def patch_game_for_customs(game_directory="", dll_filename="libshare-pj.dll", customs_banner_image="customs_banner.png", customs_jacket_image="customs_jacket.png"):
    dll_filename = os.path.join(game_directory, dll_filename)

    patch_dll_for_customs(dll_filename)
    patch_graphics_for_customs(game_directory, customs_banner_image=resource_path(os.path.join("tools", "customs_banner.png")), customs_jacket_image=resource_path(os.path.join("tools", "customs_jacket.png")))


if __name__ == "__main__":
    multiprocessing.freeze_support()  # pyinstaller fix

    parser = argparse.ArgumentParser()
    parser.add_argument('-g', '--game-dir', help='Input game directory', default="")
    parser.add_argument('-p', '--packages-dir', help='Input packages directory', default="packages")
    parser.add_argument('-u', '--unsafe', help='Enable unsafe mode', default=False, action='store_true')
    parser.add_argument('-s', '--sort', help='Sort music database only', default=False, action='store_true')
    parser.add_argument('-n', '--update-new', help='Process new folders only', default=False, action='store_true')
    args = parser.parse_args()

    if args.sort:
        game_data_folder = os.path.join(args.game_dir, "data")
        add_packages_to_mdb(os.path.join(game_data_folder, "product", "xml", "mdb_xg.xml"), [], False, False)
        add_packages_to_mdb(os.path.join(game_data_folder, "product", "xml", "mdb_mt.xml"), [], False, False)

    else:
        patch_game_for_customs(args.game_dir)
        install_packages(args.game_dir, args.packages_dir, unsafe=args.unsafe, new_only=args.update_new)
