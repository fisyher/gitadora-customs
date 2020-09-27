import argparse
import os

import audio
import tmpfile

def decode_at3(input, sample_rate, channels):
    data = bytearray(open(input, "rb").read())

    wav_header = bytearray()
    wav_header += bytearray("RIFF", "ascii")
    wav_header += int.to_bytes(len(data) + 0x3c, length=4, byteorder="little")
    wav_header += bytearray("WAVE", "ascii")

    wav_header += bytearray("fmt ", "ascii")
    wav_header += int.to_bytes(0x20, length=4, byteorder="little")

    format_id = 0x270
    byte_rate = 0x4099
    block_align = 0x180
    bits_per_sample = 0

    wav_header += int.to_bytes(format_id, length=2, byteorder="little")
    wav_header += int.to_bytes(channels, length=2, byteorder="little")
    wav_header += int.to_bytes(sample_rate, length=4, byteorder="little")
    wav_header += int.to_bytes(byte_rate, length=4, byteorder="little")
    wav_header += int.to_bytes(block_align, length=2, byteorder="little")
    wav_header += int.to_bytes(bits_per_sample, length=2, byteorder="little")

    wav_header += int.to_bytes(0x0e, length=2, byteorder="little")
    wav_header += int.to_bytes(0x01, length=2, byteorder="little")
    wav_header += int.to_bytes(0x1000, length=2, byteorder="little")
    wav_header += int.to_bytes(0x00, length=2, byteorder="little")
    wav_header += int.to_bytes(0x00, length=4, byteorder="little")
    wav_header += int.to_bytes(0x01, length=4, byteorder="little")

    wav_header += bytearray("data", "ascii")
    wav_header += int.to_bytes(len(data), length=4, byteorder="little")
    wav_header += data

    tmp_filename = tmpfile.mkstemp(suffix=".at3")
    with open(tmp_filename, "wb") as outfile:
        outfile.write(wav_header)

    sound = audio.get_audio_file(tmp_filename)

    tmpfile.tmpcleanup()
    return sound


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Input file', required=True)
    parser.add_argument('-o', '--output', help='Output file', required=True)
    parser.add_argument('-c', '--channels', help='Number of channels for input AT3', type=int, default=2)
    parser.add_argument('-r', '--rate', help='Sample rate for input AT3', type=int, default=44100)

    args = parser.parse_args()

    sound = decode_at3(args.input, args.rate, args.channels)
    format = os.path.splitext(args.output)[1].lstrip('.')
    sound.export(args.output, format=format)


    print("Saved to", args.output)
