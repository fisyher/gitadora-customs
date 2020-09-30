import argparse
import os

import audio
import mdb
import tmpfile

def get_sanitized_filename(filename, invalid_chars='<>:;\"\\/|?*'):
    for c in invalid_chars:
        filename = filename.replace(c, "_")

    return filename


if __name__ == "__main__":
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

    instrument_phased, base_bgm = audio.get_isolated_bgm(args.input, args.instrument)

    music_id = int(os.path.basename(base_bgm)[3:7])

    song_info = mdb.get_song_info_from_csv("gitadora_music.csv", music_id)

    if song_info is None:
        song_info = mdb.get_song_info_from_mdb("mdb_ex.xml", music_id)

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
