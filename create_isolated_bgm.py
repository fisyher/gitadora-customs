import argparse
import fnmatch
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
parser.add_argument('--instrument', help='Target instrument to isolate', required=True, choices=["guitar", "bass", "drum"])
parser.add_argument('--artist', help='Artist tag')
parser.add_argument('--title', help='Title tag')
parser.add_argument('--album', help='Album tag')
parser.add_argument('--format', help='Output format', default='mp3')
parser.add_argument('--quality', help='Output quality', default='320k')
args = parser.parse_args()

if os.path.isfile(args.input):
    filenames_bgm, ifs_path = ifs.extract(args.input)
    tmpfile.add_temp_folder(ifs_path)
    args.input = ifs_path

else:
    filenames_bgm = glob.glob(args.input + "/bgm*.bin") + glob.glob(args.input + "/bgm*.wav")
    ifs_path = args.input

# Find matching BGMs for each isolation type
isolation_bgms_bin = {
    "drum": ("bgm*___k.bin", "bgm*d__k.bin"),
    "guitar": ("bgm*__bk.bin", "bgm*_gbk.bin"),
    "bass": ("bgm*___k.bin", "bgm*__bk.bin"),
}

isolation_bgms_wav = {
    "drum": ("bgm*___k.wav", "bgm*d__k.wav"),
    "guitar": ("bgm*__bk.wav", "bgm*_gbk.wav"),
    "bass": ("bgm*___k.wav", "bgm*__bk.wav"),
}

filenames_bgm_basename = [os.path.basename(x) for x in filenames_bgm]

base_bgm = None
instrument_bgm = None
for isolated_bgms in [isolation_bgms_bin, isolation_bgms_wav]:
    base_bgm_pattern, instrument_bgm_pattern = isolated_bgms[args.instrument]

    if not base_bgm:
        results = fnmatch.filter(filenames_bgm_basename, base_bgm_pattern)

        if len(results) > 0:
            base_bgm = results[0]

    if not instrument_bgm:
        results = fnmatch.filter(filenames_bgm_basename, instrument_bgm_pattern)

        if len(results) > 0:
            instrument_bgm = results[0]

    if base_bgm and instrument_bgm:
        break

base_bgm = os.path.join(args.input, base_bgm)
instrument_bgm = os.path.join(args.input, instrument_bgm)

if base_bgm.endswith(".bin"):
    base_bgm_out = base_bgm.replace(".bin", ".wav")
    wavbintool.parse_bin(base_bgm, base_bgm_out)
    tmpfile.add_temp_file(base_bgm_out)
    base_bgm = base_bgm_out

if instrument_bgm.endswith(".bin"):
    instrument_bgm_out = instrument_bgm.replace(".bin", ".wav")
    wavbintool.parse_bin(instrument_bgm, instrument_bgm_out)
    tmpfile.add_temp_file(instrument_bgm_out)
    instrument_bgm = instrument_bgm_out

music_id = int(os.path.basename(base_bgm)[3:7])

song_info = mdb.get_song_info_from_csv("gitadora_music.csv", music_id)

if song_info is None:
    song_info = mdb.get_song_info_from_mdb("mdb_ex.xml", music_id)

base_audio = pydub.AudioSegment.from_file(base_bgm).invert_phase()
instrument_audio = pydub.AudioSegment.from_file(instrument_bgm)
instrument_phased = instrument_audio.overlay(base_audio)

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
        output_filename = "[%04d] %s - %s (%s).%s" % (music_id, artist, title, args.instrument, format)
    elif title and title.strip():
        output_filename = "[%04d] %s (%s).%s" % (music_id, title, args.instrument, format)
    else:
        output_filename = "%04d.%s" % (music_id, format)

output_filename = get_sanitized_filename(output_filename)
instrument_phased.export(output_filename, format=format, bitrate=args.quality, tags=tags)

print("Saved to", output_filename)

tmpfile.tmpcleanup()
