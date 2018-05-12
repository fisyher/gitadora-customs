import argparse
import io
import json
import math
import numpy
import os
import pydub
import struct
import sys
import wavfile
import pydub

import audio
import tmpfile

import adpcmwave

import imageio
imageio.plugins.ffmpeg.download()


GDX_SIZES = {
    'GDXH': 0x14,
    'GDXG': 0x18,
}

FLAG_MAP = {
    "DefaultSound": 0x04,
    "NoFilename": 0x0100
}

VOLUME_TABLE = [ 0, 14, 21, 28,  33,  37,  41,  44,
                47, 50, 53, 55,  57,  59,  61,  63,
                65, 66, 67, 68,  69,  70,  71,  71,
                72, 72, 73, 73,  74,  74,  75,  75,
                76, 76, 77, 77,  78,  78,  79,  79,
                80, 80, 81, 81,  82,  82,  82,  83,
                83, 83, 84, 84,  84,  85,  85,  85,
                86, 86, 86, 87,  87,  87,  88,  88,
                88, 88, 89, 89,  89,  89,  90,  90,
                90, 90, 91, 91,  91,  91,  92,  92,
                92, 92, 92, 93,  93,  93,  93,  93,
                94, 94, 94, 94,  95,  95,  95,  95,
                95, 96, 96, 96,  96,  96,  97,  97,
                97, 97, 97, 97,  98,  98,  98,  98,
                98, 98, 98, 98,  99,  99,  99,  99,
                99, 99, 99, 99, 100, 100, 100, 100 ]

def write_vas3(input_foldername, output_filename, metadata=None):
    if not input_foldername:
        input_foldername = ""

    if not output_filename:
        output_filename = ""

    if not metadata:
        metadata = json.load(open(os.path.join(input_foldername, "metadata.json"), "r"))

    with open(output_filename, "wb") as outfile:
        version = 2
        gdx_size = GDX_SIZES[metadata['type']] if metadata['type'] in GDX_SIZES else 0x14
        gdx_start = 0x40
        gdx_entry_start = gdx_start + gdx_size
        data_start = gdx_start + gdx_size + (len(metadata['entries']) * 0x40)

        data_start_padding = 16 - (data_start % 16)
        if data_start_padding != 16:
            data_start += data_start_padding

        outfile.write("VA3W".encode('ascii'))
        outfile.write(struct.pack("<B", 1))
        outfile.write(struct.pack("<B", 0))
        outfile.write(struct.pack("<B", 0))
        outfile.write(struct.pack("<B", version)) # TODO: Add support for saving old archives?
        outfile.write(struct.pack("<I", len(metadata['entries'])))
        outfile.write(struct.pack("<I", gdx_size)) # Change depending on archive version
        outfile.write(struct.pack("<I", gdx_start))
        outfile.write(struct.pack("<I", gdx_entry_start))
        outfile.write(struct.pack("<I", data_start))

        if outfile.tell() < gdx_start:
            outfile.write(bytearray([0] * (gdx_start - outfile.tell()))) # Padding

        outfile.write(metadata['type'].encode('ascii'))
        outfile.write(struct.pack("<H", metadata['defaults']['default_hihat']))
        outfile.write(struct.pack("<H", metadata['defaults']['default_snare']))
        outfile.write(struct.pack("<H", metadata['defaults']['default_bass']))
        outfile.write(struct.pack("<H", metadata['defaults']['default_hightom']))
        outfile.write(struct.pack("<H", metadata['defaults']['default_lowtom']))
        outfile.write(struct.pack("<H", metadata['defaults']['default_rightcymbal']))

        if metadata['type'] == "GDXH":
            outfile.write(struct.pack("<B", metadata['gdx_type_unk1']))
            outfile.write(struct.pack("<B", metadata['gdx_volume_flag']))
        elif metadata['type'] == "GDXG":
            outfile.write(struct.pack("<H", metadata['defaults']['default_leftcymbal']))
            outfile.write(struct.pack("<H", metadata['defaults']['default_floortom']))
            outfile.write(struct.pack("<H", metadata['defaults']['default_leftpedal']))
        else:
            print("Unknown type %s" % metadata['type'])
            exit(1)

        if outfile.tell() < gdx_entry_start:
            outfile.write(bytearray([0] * (gdx_entry_start - outfile.tell()))) # Padding

        defaults = [metadata['defaults'][x] for x in metadata['defaults']]
        data_section = bytearray()

        for entry in metadata['entries']:
            filename = entry['filename']

            if '.' not in filename: # Lame way to check if it has an extension
                # If the filename doesn't have an extension, search for one
                for ext in ['wav', 'ogg', 'mp3']:
                    new_filename = "{}.{}".format(filename, ext).replace("\\","/")

                    if os.path.exists(os.path.join(input_foldername, new_filename)):
                        filename = new_filename
                        break

            # Build full path
            filename = os.path.join(input_foldername, os.path.normpath(filename.replace("\\","/")))

            if not os.path.exists(filename):
                print("Could not find %s" % filename)
                continue

            # Set entry filename to just the filename without extension or path
            entry['filename'] = os.path.splitext(os.path.basename(filename))[0]

            if 'flags' not in entry:
                entry['flags'] = []

            if 'extra' not in entry:
                entry['extra'] = 255 # Normal?

            if "NoFilename" in entry['flags']:
                filename = "%04x" % entry['sound_id']

            # try:
            #     rate, raw_data, bits = wavfile.read(filename)
            # except:

            # Try using pysoundfile if wavfile failed
            # If this code works well enough, I can probably get rid of
            # wavfile for the was3tool since looping isn't required
            # TODO: Replace this with code to detect if it's a WAV, 16bit, mono, and 48000 and if so, use wavfile instead
            #print(filename)
            filename = audio.get_processed_wav(filename, channels=1, rate=48000, bits=16)

            rate, raw_data, bits = wavfile.read(filename)

            channels = 1 if len(raw_data.shape) == 1 else raw_data.shape[1]

            encoded_data = adpcmwave.encode_data(raw_data, channels)

            sound_flag = 0
            for flag in entry['flags']:
                if flag in FLAG_MAP:
                    sound_flag |= FLAG_MAP[flag]
                elif type(flag) == int:
                    sound_flag |= flag
                else:
                    print("Don't know how to handle flag {}, ignoring...".format(flag))

            if version >= 2:
                if entry['sound_id'] in defaults:
                    sound_flag |= 0x04
                elif len(defaults) > 0: # Is this right?
                    sound_flag |= 0x02 # Not a default?

            volume = entry['volume']

            if version < 2:
                volume = VOLUME_TABLE.index(min(VOLUME_TABLE, key=lambda x:abs(x-entry['volume'])))

            outfile.write(struct.pack("<I", len(data_section)))
            outfile.write(struct.pack("<I", len(encoded_data)))
            outfile.write(struct.pack("<H", channels))
            outfile.write(struct.pack("<H", 0x10)) # Will this ever not be 16 bit?
            outfile.write(struct.pack("<I", rate))
            outfile.write(struct.pack("<I", 0)) # This should always be 0 for v2 I think?
            outfile.write(struct.pack("<I", 0)) # This should always be 0 for v2 I think?
            outfile.write(struct.pack("<B", volume))
            outfile.write(struct.pack("<B", entry['pan']))
            outfile.write(struct.pack("<H", entry['sound_id']))
            outfile.write(struct.pack("<H", sound_flag))
            outfile.write(struct.pack("<H", entry['extra']))

            filename_bytes = entry['filename'].encode('ascii')
            outfile.write(filename_bytes[:0x20])

            if len(filename_bytes) < 0x20:
                outfile.write(bytearray([0] * (0x20 - len(filename_bytes))))

            data_section += encoded_data

            padding = 0x10 - (len(data_section) % 0x10)
            if padding != 0x10:
                data_section += bytearray([0] * padding)


        if outfile.tell() < data_start:
            outfile.write(bytearray([0] * (data_start - outfile.tell()))) # Padding

        outfile.write(data_section)


def read_vas3(input_filename, output_folder, force_hex=False, mix_audio=False):
    data = open(input_filename, "rb").read()

    if data[0:4].decode('ascii') != "VA3W":
        print("Not a valid VA3 file")
        exit(1)

    # v3 header is 1 0 0 2
    version_flag1, version_flag2, version_flag3, version_flag4, entry_count, gdx_size, gdx_start, entry_start, data_start = struct.unpack("<BBBBIIIII", data[0x04:0x1c])

    if entry_count <= 0:
        print("No files to extract")
        exit(1)

    gdx_magic = data[gdx_start:gdx_start+4].decode('ascii')
    if gdx_magic != "GDXH" and gdx_magic != "GDXG":
        print("Not a valid GDXH header")
        exit(1)

    default_hihat, default_snare, default_bass, default_hightom, default_lowtom, default_rightcymbal = struct.unpack("<HHHHHH", data[gdx_start+0x04:gdx_start+0x10])
    if gdx_magic == "GDXH":
        # Not used anywhere, can be ignored??
        # gdx_type_unk1 default is 0
        # gdx_type_unk2 default is 1
        default_leftcymbal = 0xfff0
        default_floortom = 0xfff1
        default_leftpedal = 0xfff2
        gdx_type_unk1 = data[gdx_start+0x10] # Not used anywhere?
        gdx_volume_flag = data[gdx_start+0x11] # How does this work with GDXG?
    elif gdx_magic == "GDXG":
        default_leftcymbal, default_floortom, default_leftpedal = struct.unpack("<HHH", data[gdx_start+0x10:gdx_start+0x16])
        gdx_type_unk1 = 0
        gdx_volume_flag = 1

    metadata = {
        'type': gdx_magic,
        'version': version_flag4,
        'defaults': {
            'default_hihat': default_hihat,
            'default_snare': default_snare,
            'default_bass': default_bass,
            'default_hightom': default_hightom,
            'default_lowtom': default_lowtom,
            'default_rightcymbal': default_rightcymbal,
            'default_leftcymbal': default_leftcymbal,
            'default_floortom': default_floortom,
            'default_leftpedal': default_leftpedal,
        },
        'gdx_type_unk1': gdx_type_unk1,
        'gdx_volume_flag': gdx_volume_flag,
        'entries': [],
    }

    entries = []
    for i in range(entry_count):
        # sound_flag seems to be related to defaults. If something is set to default, it is 0x02. Else it's 0x04 (for GDXG). Always 0 for GDXH?
        # entry_unk4 seems to always be 255??
        offset, filesize, channels, bits, rate, entry_unk1, entry_unk2, volume, pan, sound_id, sound_flag, entry_unk4  = struct.unpack("<IIHHIIIBBHHH", data[entry_start+(i*0x40):entry_start+(i*0x40)+0x20])
        filename = data[entry_start+(i*0x40)+0x20:entry_start+(i*0x40)+0x40].decode("ascii").strip('\0')

        if entry_unk1 != 0:
            filesize = entry_unk1

        # if entry_unk1 != 0 or entry_unk2 != 0:
        #     print("Unknown fields in entry: %08x %08x" % (entry_unk1, entry_unk2))
        #     exit(1)

        # Code for an older version of VA3 files?
        # I think there's some padding that it's trying to deal with here, but I'm not sure exactly.
        # Need a sample to verify this functionality.
        # entry_unk1 and entry_unk2 should always be 0 for v3
        # if entry_unk2 != 0 and (entry_unk2 == filesize or entry_unk2 == filesize + 0x20 or entry_unk2 == filesize * 4):
        #     entry_unk2 = 0

        # if version_flag4 == 0:
        #     if entry_unk2 > 0 and entry_unk2 >= 0x20:
        #         entry_unk2 -= 0x20
        #     if entry_unk1 > 0 and entry_unk1 >= 0x20:
        #         entry_unk1 -= 0x20

        # if entry_unk2 > filesize:
        #     entry_unk2 = filesize

        # if entry_unk1 != 0:
        #     valid_file = entry_unk1 == entry_unk2
        # else:
        #     valid_file = entry_unk2 == 0

        if gdx_volume_flag == 0:
             # ??
             # This code shouldn't be hit unless you're working
             # with some really old files I suspect
            volume = 3 * volume / 2
            print("Verify volume when gdx_volume_flag == 0")
            exit(1)
        else:
            volume = min(volume, 127)

        if version_flag1 == 1 and version_flag2 == 0 and version_flag3 == 0 and (version_flag4 == 0 or version_flag4 == 1):
            # v1 and v2 use a table for volume?
            # Need to find a sample to verify
            #volume2 = VOLUME_TABLE[min(volume, 0x7f)]
            #print(volume, volume2)
            #print("Verify when volume table is used (percentages or not?)")
            #exit(1)
            pass

        if sound_id >= 0xfff0:
            print("Verify when sound_id >= 0xfff0")
            exit(1)

        if sound_id == 0xfff0:
            sound_id = default_leftcymbal
        elif sound_id == 0xfff1:
            sound_id = default_floortom
        elif sound_id == 0xfff2:
            sound_id = default_leftpedal

        entries.append({
            'sound_id': sound_id,
            'filename': filename,
            'offset': offset,
            'filesize': filesize,
            'channels': channels,
            'bits': bits,
            'rate': rate,
            'volume': volume,
            'pan': pan,
        })

        metadata['entries'].append({
            'sound_id': sound_id,
            'filename': filename,
            'volume': volume,
            'pan': pan,
            'extra': entry_unk4, # Unknown flag, most likely always 255
            'flags': [],
        })

        if version_flag4 < 2:
            if (sound_flag & 0x02) != 0:
                metadata['entries'][-1]['flags'].append(0x02)

        # if (sound_flag & 0x04) != 0:
        #     metadata['entries'][-1]['flags'].append("DefaultSound") # Generate this by checking defaults in header
                #"DefaultSound" if (sound_flag & 0x04) != 0,

        if (sound_flag & 0x0100) != 0:
            metadata['entries'][-1]['flags'].append("NoFilename")

    if output_folder:
        basepath = output_folder
    else:
        basepath = os.path.splitext(os.path.basename(input_filename))[0]

    if not os.path.exists(basepath):
        os.makedirs(basepath)

    for entry in entries:
        #print("Extracting", entry['filename'])
        #print(entry)

        wave_data = bytearray(data[data_start+entry['offset']:data_start+entry['offset']+entry['filesize']])
        output = adpcmwave.decode_data(wave_data, entry['rate'], entry['channels'], entry['bits'])

        output_filename = os.path.join(basepath, "{}.wav".format(entry['filename']))

        if (sound_flag & 0x100) != 0 or force_hex:
            output_filename = os.path.join(basepath, "%04x.wav" % entry['sound_id'])

        output = numpy.ndarray((int(len(output) // 2 // entry['channels']), entry['channels']), numpy.int16, output, 0)

        wavfile.write(output_filename, entry['rate'], output)

        # If mixing is enabled, mix using AudioSegment
        if mix_audio:
            # audio_segment = pydub.AudioSegment(
            #     output_stream.getbuffer(),
            #     frame_rate=entry['rate'],
            #     sample_width=entry['bits'] // 8,
            #     channels=entry['channels']
            # )

            audio_segment = pydub.AudioSegment.from_file(output_filename)
            pan = (entry['pan'] - (128 / 2)) / (128 / 2)
            audio_segment = audio_segment.pan(pan)
            db = 20 * math.log10(entry['volume'] / 127)
            audio_segment += db
            audio_segment.export(output_filename, format="wav")

            entry['volume'] = 127
            entry['pan'] = 64

    open(os.path.join(basepath, "metadata.json"), "w").write(json.dumps(metadata, indent=4))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-x', '--extract', action='store_true', help='Extraction mode')
    group.add_argument('-c', '--create', action='store_true', help='Creation mode')
    parser.add_argument('-i', '--input', help='Input file', required=True)
    parser.add_argument('-o', '--output', help='Output file', required=True)
    parser.add_argument('-m', '--mix', action='store_true', help='Mix output files using volume and pan parameters', required=False, default=False)
    parser.add_argument('-f', '--force-hex', action='store_true', help='Force hex filenames', required=False, default=False)
    args = parser.parse_args()

    if args.create:
        write_vas3(args.input, args.output)
    elif args.extract:
        read_vas3(args.input, args.output, args.force_hex, args.mix)