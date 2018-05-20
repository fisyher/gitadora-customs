import argparse
import glob
import os
import pydub

import ifs
import mdb
import tmpfile
import wavbintool

def get_sanitized_filename(filename, invalid_chars='<>:;\"\\/|?*'):
    for c in invalid_chars:
        filename = filename.replace(c, "_")

    return filename

parser = argparse.ArgumentParser()
parser.add_argument('--input', help='Input file/folder', required=True)
parser.add_argument('--output', help='Output filename')
parser.add_argument('--artist', help='Artist tag')
parser.add_argument('--title', help='Title tag')
parser.add_argument('--album', help='Album tag')
parser.add_argument('--format', help='Output format', default='mp3')
parser.add_argument('--quality', help='Output quality', default='320k')
parser.add_argument('--mix-phase', help='Mix using inverted phase BGM', default=False, action='store_true')
parser.add_argument('--mix-base-volume', help='Reduce volume of base audio')
parser.add_argument('--mix-guitar-volume', help='Reduce volume of guitar audio')
parser.add_argument('--mix-drum-volume', help='Reduce volume of drum audio')
args = parser.parse_args()

if args.mix_phase:
    if not args.mix_base_volume:
        args.mix_base_volume = -2
    if not args.mix_guitar_volume:
        args.mix_guitar_volume = -2
    if not args.mix_drum_volume:
        args.mix_drum_volume = -1
else:
    if not args.mix_base_volume:
        args.mix_base_volume = 0
    if not args.mix_guitar_volume:
        args.mix_guitar_volume = -7
    if not args.mix_drum_volume:
        args.mix_drum_volume = -3.5

if os.path.isfile(args.input):
    filenames_bgm, ifs_path = ifs.extract(args.input)
else:
    filenames_bgm = glob.glob(args.input + "/bgm*.bin")
    ifs_path = args.input

tmpfile.add_temp_folder(ifs_path)

if args.mix_phase:
    # Get guitar+bass BGM
    bgms = [x for x in filenames_bgm if x.endswith("___k.bin")]
    base_bgm = bgms[0] if len(bgms) > 0 else None
    base_bgm_out = base_bgm.replace(".bin", ".wav") if len(bgms) > 0 else None

# Get drum BGM
bgms = [x for x in filenames_bgm if x.endswith("d__k.bin")]

if len(bgms) == 0:
    bgms = [x for x in filenames_bgm if x.endswith("d_bk.bin")]

drum_bgm = bgms[0] if len(bgms) > 0 else None
drum_bgm_out = drum_bgm.replace(".bin", ".wav") if len(bgms) > 0 else None

# Get guitar+bass BGM
bgms = [x for x in filenames_bgm if x.endswith("_gbk.bin")]
guitar_bgm = bgms[0] if len(bgms) > 0 else None
guitar_bgm_out = guitar_bgm.replace(".bin", ".wav") if len(bgms) > 0 else None

if args.mix_phase and not base_bgm:
    print("Couldn't find base BGM")
    tmpfile.tmpcleanup()
    exit(1)

if not drum_bgm:
    print("Couldn't find drum BGM")
    tmpfile.tmpcleanup()
    exit(1)

if not guitar_bgm:
    print("Couldn't find guitar BGM")
    tmpfile.tmpcleanup()
    exit(1)

tmpfile.add_temp_file(drum_bgm_out)
tmpfile.add_temp_file(guitar_bgm_out)

music_id = int(os.path.basename(drum_bgm)[3:7])

song_info = mdb.get_song_info_from_csv("gitadora_music.csv", music_id)

if song_info is None:
    song_info = mdb.get_song_info_from_mdb("mdb_xg.xml", music_id)

if args.mix_phase:
    wavbintool.parse_bin(base_bgm, base_bgm_out)

wavbintool.parse_bin(drum_bgm, drum_bgm_out)
wavbintool.parse_bin(guitar_bgm, guitar_bgm_out)

if args.mix_phase:
    base_audio = pydub.AudioSegment.from_file(base_bgm_out).invert_phase()

drum_audio = pydub.AudioSegment.from_file(drum_bgm_out)
guitar_audio = pydub.AudioSegment.from_file(guitar_bgm_out)

if args.mix_phase:
    drum_phased = drum_audio.overlay(base_audio)
    guitar_phased = guitar_audio.overlay(base_audio)

    drum_phased += args.mix_drum_volume
    guitar_phased += args.mix_guitar_volume
    base_audio += args.mix_base_volume

    mixed_audio = base_audio.overlay(drum_phased)
    mixed_audio = mixed_audio.overlay(guitar_phased)
else:
    drum_audio += args.mix_drum_volume
    guitar_audio += args.mix_guitar_volume

    mixed_audio = drum_audio.overlay(guitar_audio)

output_filename = args.output if args.output else None

artist = args.artist if args.artist else song_info.get('artist') if song_info else None
title = args.title if args.title else song_info.get('title') if song_info else None
album = args.album if args.album else ""

tags = {
    "artist": artist,
    "title": title,
    "album": album,
}

if not args.format:
    format = os.path.splitext(args.output)[-1].strip('.')
else:
    format = args.format

if not output_filename:
    # Automatically generate filename based on song info
    if artist and artist.strip() and title and title.strip():
        output_filename = "[%04d] %s - %s.%s" % (music_id, artist, title, format)
    elif title and title.strip():
        output_filename = "[%04d] %s.%s" % (music_id, title, format)
    else:
        output_filename = "%04d.%s" % (music_id, format)

output_filename = get_sanitized_filename(output_filename)
mixed_audio.export(output_filename, format=format, bitrate=args.quality, tags=tags)

print("Saved to", output_filename)

tmpfile.tmpcleanup()
