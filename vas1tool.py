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


def get_frequency(a1, a2, b1, b2=0):
    lookup1 = [
        0x8000, 0x879C, 0x8FAC, 0x9837, 0xA145, 0xAADC, 0xB504, 0xBFC8,
        0xCB2F, 0xD744, 0xE411, 0xF1A1
    ]

    lookup2 = [
        0x8000, 0x800e, 0x801d, 0x802c, 0x803b, 0x804a, 0x8058, 0x8067,
        0x8076, 0x8085, 0x8094, 0x80a3, 0x80b1, 0x80c0, 0x80cf, 0x80de,
        0x80ed, 0x80fc, 0x810b, 0x811a, 0x8129, 0x8138, 0x8146, 0x8155,
        0x8164, 0x8173, 0x8182, 0x8191, 0x81a0, 0x81af, 0x81be, 0x81cd,
        0x81dc, 0x81eb, 0x81fa, 0x8209, 0x8218, 0x8227, 0x8236, 0x8245,
        0x8254, 0x8263, 0x8272, 0x8282, 0x8291, 0x82a0, 0x82af, 0x82be,
        0x82cd, 0x82dc, 0x82eb, 0x82fa, 0x830a, 0x8319, 0x8328, 0x8337,
        0x8346, 0x8355, 0x8364, 0x8374, 0x8383, 0x8392, 0x83a1, 0x83b0,
        0x83c0, 0x83cf, 0x83de, 0x83ed, 0x83fd, 0x840c, 0x841b, 0x842a,
        0x843a, 0x8449, 0x8458, 0x8468, 0x8477, 0x8486, 0x8495, 0x84a5,
        0x84b4, 0x84c3, 0x84d3, 0x84e2, 0x84f1, 0x8501, 0x8510, 0x8520,
        0x852f, 0x853e, 0x854e, 0x855d, 0x856d, 0x857c, 0x858b, 0x859b,
        0x85aa, 0x85ba, 0x85c9, 0x85d9, 0x85e8, 0x85f8, 0x8607, 0x8617,
        0x8626, 0x8636, 0x8645, 0x8655, 0x8664, 0x8674, 0x8683, 0x8693,
        0x86a2, 0x86b2, 0x86c1, 0x86d1, 0x86e0, 0x86f0, 0x8700, 0x870f,
        0x871f, 0x872e, 0x873e, 0x874e, 0x875d, 0x876d, 0x877d, 0x878c,
    ]

    t1 = ((b1 + ((b2 + a2 & 0xffff) >> 7)) - a1) * 0x10000
    t2 = t1 >> 0x10
    t1 = t1 >> 0x1f
    t1 = (t2 // 6 + t1 >> 1) - t1
    t2 = t2 + t1 * -0xc
    t1 -= 2

    if t2 * 0x10000 < 0:
        t2 = t2 + 0xc
        t1 -= 1

    pitch = (((lookup1[t2] * lookup2[b2 + (a2 & 0x7f)]) >> 0x10) + (1 << (-t1 - 1 & 0x1f))) >> (-t1 & 0x1f) if t1 < 0 else 0x3fff

    return (44100 * (pitch & 0xffff)) >> 12


def read_vas1(input_filename, input_fre_filename, output_folder, force_hex=False, mix_audio=False, is_guitar=False, is_vas2=False):
    data = open(input_filename, "rb").read()

    entry_count = struct.unpack("<I", data[0x00:0x04])[0]
    entry_start = 0x04

    if entry_count <= 0:
        print("No files to extract")
        exit(1)

    default_leftcymbal = 0xfff0
    default_floortom = 0xfff1
    default_leftpedal = 0xfff2

    if input_fre_filename:
        fre_data = open(input_fre_filename, "rb").read()

        if len(fre_data) == 12:
            default_hihat = int.from_bytes(fre_data[0:2], byteorder="little")
            default_snare = int.from_bytes(fre_data[2:4], byteorder="little")
            default_bass = int.from_bytes(fre_data[4:6], byteorder="little")
            default_hightom = int.from_bytes(fre_data[6:8], byteorder="little")
            default_lowtom = int.from_bytes(fre_data[8:10], byteorder="little")
            default_rightcymbal = int.from_bytes(fre_data[10:12], byteorder="little")

        else:
            search_filename = os.path.splitext(os.path.basename(input_filename))[0].lower()
            found_fre = False

            for i in range(len(fre_data) // 0x18):
                filename = fre_data[i*0x18:i*0x18+12].decode('ascii').strip('\0')

                if filename == search_filename:
                    cur_fre_data = fre_data[i*0x18+12:(i+1)*0x18]
                    default_hihat = int.from_bytes(cur_fre_data[0:2], byteorder="little")
                    default_snare = int.from_bytes(cur_fre_data[2:4], byteorder="little")
                    default_bass = int.from_bytes(cur_fre_data[4:6], byteorder="little")
                    default_hightom = int.from_bytes(cur_fre_data[6:8], byteorder="little")
                    default_lowtom = int.from_bytes(cur_fre_data[8:10], byteorder="little")
                    default_rightcymbal = int.from_bytes(cur_fre_data[10:12], byteorder="little")
                    found_fre = True
                    break

            if not found_fre:
                print("Couldn't find default keysound entries for", input_filename)
                exit(1)

    else:
        default_hihat = 0
        default_snare = 0
        default_bass = 0
        default_hightom = 0
        default_lowtom = 0
        default_rightcymbal = 0

    entries = []
    found_count = {}
    cur_round = 0
    for i in range(entry_count):
        # sound_flag seems to be related to defaults. If something is set to default, it is 0x02. Else it's 0x04 (for GDXG). Always 0 for GDXH?
        # entry_unk4 seems to always be 255??
        metadata_offset, offset, filesize = struct.unpack("<III", data[entry_start+(i*0x0c):entry_start+(i*0x0c)+0x0c])
        metadata_unk1_1, volume, pan, sound_id, instrument_id, metadata_unk2_2, metadata_unk2_3, metadata_unk2_4, metadata_unk3, sample_rate = struct.unpack("<BBBBBBBBHH", data[entry_start+metadata_offset+(entry_count*0x0c):entry_start+metadata_offset+(entry_count*0x0c)+0x0c])

        if is_guitar and is_vas2:
            if instrument_id not in found_count:
                found_count[instrument_id] = 0

            elif instrument_id == 0x24:
                cur_round += 1

            cur_id = int("%01x%01x%02x" % (cur_round, (sound_id - 0x30) // 16, instrument_id), 16)

            found_count[instrument_id] += 1

        else:
            cur_id = i

        sample_rate = get_frequency(sound_id, metadata_unk2_2, instrument_id)

        print("%04x | %08x %08x %08x | %02x %02x %02x %02x  %02x %02x %02x %02x  %04x  %04x | %08x | %08x %d | %04x" % (i, metadata_offset, offset, filesize, metadata_unk1_1, volume, pan, sound_id, instrument_id, metadata_unk2_2, metadata_unk2_3, metadata_unk2_4, sample_rate, metadata_unk3, entry_start+metadata_offset+(entry_count*0x0c), sample_rate, sample_rate, cur_id))

        offset += ((entry_count * 0x0c) * 2) + 4

        entries.append((offset, filesize, cur_id, volume, pan + 64 if is_guitar else pan - 100))

    entries.append(len(data))

    if output_folder:
        basepath = output_folder
    else:
        basepath = os.path.splitext(os.path.basename(input_filename))[0]

    os.makedirs(basepath, exist_ok=True)

    filename_prefix = "g" if is_guitar else "d"

    metadata = {
        'type': "GDXG" if is_guitar else "GDXH",
        'version': 1,
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
        'gdx_type_unk1': 0,
        'gdx_volume_flag': 1,
        'entries': [],
    }

    for idx, entry_info in enumerate(entries[:-1]):
        entry, filesize, sound_id, volume, pan = entry_info

        output_filename = os.path.join(basepath, "%s_%04x.pcm" % (filename_prefix, sound_id))

        print("Extracting %s | %d %04x %d" % (output_filename, sound_id, volume, pan))
        with open(output_filename, "wb") as outfile:
            outfile.write(struct.pack(">IHHB", filesize, 0, sample_rate, 1))
            outfile.write(bytearray([0] * 7))
            outfile.write(bytearray([0] * 0x800))
            outfile.write(data[entry:entry+filesize])

        audio.get_wav_from_pcm(output_filename)
        os.remove(output_filename)

        entry_filename = "%s.%04d" % (os.path.basename(os.path.splitext(input_filename)[0]).lower(), sound_id)

        duration = len(pydub.AudioSegment.from_file(os.path.splitext(output_filename)[0] + ".wav")) / 1000

        metadata['entries'].append({
            'sound_id': sound_id,
            'filename': entry_filename,
            'volume': volume,
            'pan': pan,
            'extra': 255, # Unknown
            'flags': ['NoFilename'],
            'duration': duration,
        })

    open(os.path.join(basepath, "%s_metadata.json" % filename_prefix), "w").write(json.dumps(metadata, indent=4))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Input file', required=True)
    parser.add_argument('-r', '--input-fre', help='Input FRE file', default=None)
    parser.add_argument('-o', '--output', help='Output file', required=True)
    parser.add_argument('-m', '--mix', action='store_true', help='Mix output files using volume and pan parameters', required=False, default=False)
    parser.add_argument('-g', '--guitar', action='store_true', help='Is extracting guitar archive', required=False, default=False)
    parser.add_argument('-f', '--force-hex', action='store_true', help='Force hex filenames', required=False, default=False)
    parser.add_argument('-v', '--vas2', action='store_true', help='Force va2 mode', required=False, default=False)
    args = parser.parse_args()

    if args.input.lower().endswith(".va2"):
        args.vas2 = True

    if not args.guitar and not args.input_fre:
        print("Must specify an input FRE file with drum data")
        exit(1)

    read_vas1(args.input, args.input_fre, args.output, args.force_hex, args.mix, args.guitar, args.vas2)
