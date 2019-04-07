# TODO: Remove unneeded code
# TODO: Add support for audio metadata
# TODO: Figure out differences between GF and DM VAS archives

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
import helper

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


def read_vas3(input_filename, output_folder, force_hex=False, mix_audio=False, is_guitar=False):
    data = open(input_filename, "rb").read()

    entry_count = struct.unpack("<I", data[0x00:0x04])[0]
    entry_start = 0x04

    if entry_count <= 0:
        print("No files to extract")
        exit(1)

    entries = []
    for i in range(entry_count):
        # sound_flag seems to be related to defaults. If something is set to default, it is 0x02. Else it's 0x04 (for GDXG). Always 0 for GDXH?
        # entry_unk4 seems to always be 255??
        metadata_offset, offset, filesize = struct.unpack("<III", data[entry_start+(i*0x0c):entry_start+(i*0x0c)+0x0c])
        metadata_unk1_1, volume, metadata_unk1_3, sound_id, sound_id2, metadata_unk2_2, metadata_unk2_3, metadata_unk2_4, metadata_unk3 = struct.unpack("<BBBBBBBBI", data[entry_start+metadata_offset+(entry_count*0x0c):entry_start+metadata_offset+(entry_count*0x0c)+0x0c])

        #output_filename = os.path.join(basepath, "{}.wav".format(entry['filename']))

        print("%04x | %08x %08x %08x | %02x %02x %02x %02x  %02x %02x %02x %02x  %08x | %08x" % (i, metadata_offset, offset, filesize, metadata_unk1_1, volume, metadata_unk1_3, sound_id, sound_id2, metadata_unk2_2, metadata_unk2_3, metadata_unk2_4, metadata_unk3, entry_start+metadata_offset+(entry_count*0x0c)))

        offset += ((entry_count * 0x0c) * 2) + 4

        entries.append((offset, filesize, sound_id))

    entries.append(len(data))

    if output_folder:
        basepath = output_folder
    else:
        basepath = os.path.splitext(os.path.basename(input_filename))[0]

    if not os.path.exists(basepath):
        os.makedirs(basepath)

    for idx, entry_info in enumerate(entries[:-1]):
        entry, filesize, sound_id = entry_info
        #filesize = entries[idx + 1] - entry

        output_filename = os.path.join(basepath, "%04x.pcm" % (idx))

        print("Extracting", output_filename)
        with open(output_filename, "wb") as outfile:
            outfile.write(struct.pack(">IHHB", filesize, 0, 22050 if is_guitar else 44100, 1))
            outfile.write(bytearray([0] * 7))
            outfile.write(bytearray([0] * 0x800))
            outfile.write(data[entry:entry+filesize])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Input file', required=True)
    parser.add_argument('-o', '--output', help='Output file', required=True)
    parser.add_argument('-m', '--mix', action='store_true', help='Mix output files using volume and pan parameters', required=False, default=False)
    parser.add_argument('-g', '--guitar', action='store_true', help='Is extracting guitar archive', required=False, default=False)
    parser.add_argument('-f', '--force-hex', action='store_true', help='Force hex filenames', required=False, default=False)
    args = parser.parse_args()

    read_vas3(args.input, args.output, args.force_hex, args.mix, args.guitar)