import struct
import sys
import os

import tmpfile

def dump_fcn(input_filename, output_folder=None):
    if not output_folder:
        output_folder = tmpfile.mkdtemp()
        tmpfile.add_temp_folder(output_folder)

    with open(input_filename, "rb") as infile:
        first_val = struct.unpack("<I", infile.read(4))[0]

        if first_val & 0x08000000:
            filetable_size, unk1, filesize = struct.unpack("<III", infile.read(12))
            file_count =  first_val & 0x00ffffff
            filetable_size &= 0x00ffffff
        else:
            unk1, filetable_size, unk2 = struct.unpack("<III", infile.read(12))
            filesize = first_val
            file_count = filetable_size // 0x28

        for i in range(file_count):
            infile.seek(0x10 + (i * 0x28))

            filename = infile.read(0x20).decode('shift-jis').strip()
            filename = os.path.join(output_folder, filename)

            offset, datalen = struct.unpack("<II", infile.read(8))

            infile.seek(0x10 + filetable_size + offset)

            print("Extracting", filename)
            with open(filename, "wb") as outfile:
                outfile.write(infile.read(datalen))

    return output_folder


if __name__ == "__main__":
    basepath = os.path.splitext(sys.argv[1])[0]

    os.makedirs(basepath, exist_ok=True)

    dump_fcn(sys.argv[1], basepath)
