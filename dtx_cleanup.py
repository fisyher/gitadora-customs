import argparse
import os
import string
import shutil

import audio

filename_lookup = {}
reverse_filename_lookup = {}


def add_filename(old, new):
    filename_lookup[old] = new
    reverse_filename_lookup[new] = old


def fixup_dtx(filename, input_folder, output_folder, no_convert, resources):
    output_lines = []
    difficulty = None
    has_drum = False
    has_guitar = False
    has_bass = False

    print(filename)

    for line in open(filename, encoding='shift-jis'):
        line_orig = line.strip()
        line = line_orig.upper()

        # Get DTX filename from line
        if not line.startswith('#'):
            output_lines.append(line_orig)
            continue

        line = line[1:]
        while line[0] not in [':', ' ']:
            line = line[1:]

        cmd = line_orig[1:len(line_orig)-len(line)].strip().upper()

        line = line.strip()
        value = line_orig[-len(line):].strip()

        while value and value[0] in [':', ' ']:
            value = value[1:]

        head = line_orig[:-len(line)]

        if cmd == "COMMENT":
            difficulty = value
            continue

        elif cmd == "DLEVEL":
            has_drum = True
            output_lines.append(line_orig)

        elif cmd == "GLEVEL":
            has_guitar = True
            output_lines.append(line_orig)

        elif cmd == "BLEVEL":
            has_bass = True
            output_lines.append(line_orig)

        elif cmd in ["PREIMAGE", "PREVIEW"]:
            idx = 2
            ext = os.path.splitext(value)[1]

            convert_audio = False
            if ext == ".wav" and not no_convert:
                convert_audio = True
                # Convert to .ogg instead
                ext = ".ogg"

            target_filename = "pre%s" % (ext)

            while target_filename in reverse_filename_lookup and reverse_filename_lookup[target_filename] != value:
                target_filename = "pre%d%s" % (idx, ext)
                idx += 1

            full_input_path = os.path.join(input_folder, value)

            if not os.path.exists(full_input_path) and resources and os.path.exists(resources):
                full_input_path = os.path.join(resources, value)

            full_target_path = os.path.join(output_folder, target_filename)
            if convert_audio:
                if not os.path.exists(full_target_path):
                    if os.path.exists(full_input_path):
                        print(full_input_path)
                        orig_audio = audio.get_audio_file(full_input_path)
                        orig_audio.export(full_target_path)
                        print(target_filename)

                    else:
                        print("Couldn't find", full_input_path)

            else:
                if os.path.exists(full_input_path):
                    shutil.copyfile(full_input_path, full_target_path)

                else:
                    print("Couldn't find", full_input_path)

            add_filename(value, target_filename)

            output_lines.append(head + target_filename)

        elif cmd.startswith("WAV") or cmd.startswith("AVI"):
            idx = 0
            ext = os.path.splitext(value)[1]

            convert_audio = False
            if ext == ".wav" and not no_convert:
                convert_audio = True
                # Convert to .ogg instead
                ext = ".ogg"

            target_filename = "%04d%s" % (idx, ext)

            while target_filename in reverse_filename_lookup and reverse_filename_lookup[target_filename] != value:
                target_filename = "%04d%s" % (idx, ext)
                idx += 1

            full_input_path = os.path.join(input_folder, value)
            full_target_path = os.path.join(output_folder, target_filename)
            if convert_audio:
                if not os.path.exists(full_target_path):
                    if os.path.exists(full_input_path):
                        print(full_input_path)
                        orig_audio = audio.get_audio_file(full_input_path)
                        orig_audio.export(full_target_path)
                        print(target_filename)

                    else:
                        print("Couldn't find", full_input_path)

            else:
                if os.path.exists(full_input_path):
                    shutil.copyfile(full_input_path, full_target_path)

                else:
                    print("Couldn't find", full_input_path)

            add_filename(value, target_filename)

            output_lines.append(head + target_filename)

        else:
            output_lines.append(line_orig)

    prefix = None

    if difficulty:
        prefix = {
            "BASIC": "bsc",
            "ADVANCED": "adv",
            "EXTREME": "ext",
            "MASTER": "mst",
        }[difficulty.upper()]

    if not prefix:
        print("Couldn't figure out what to prefix this file", filename)
        exit(1)

    output_filename = "_".join(list(filter(None, [prefix, *["drum" if has_drum else None, "guitar" if has_guitar else None, "bass" if has_bass else None]]))) + ".dtx"

    if not output_filename:
        print("Couldn't figure out what to name this file", filename)
        exit(1)

    open(os.path.join(output_folder, output_filename), "w", encoding='shift-jis').write("\n".join(output_lines))

    return output_filename


def process_folder(input_folder, output_folder, no_convert=False, resources=None):
    target_dtx_filenames = []

    set_filename = os.path.join(input_folder, "set.def")
    if os.path.exists(set_filename):
        # Process all files specified in the set.def
        for line in open(set_filename):
            line_orig = line.strip()
            line = line_orig.upper()

            # Get DTX filename from line
            if not line.startswith('#L'):
                continue

            line = line[2:]

            while line and line[0] in string.digits:
                line = line[1:]

            if not line.startswith("FILE"):
                continue

            line = line[4:]

            while line and line[0] in [':', ' ']:
                line = line[1:]

            filename = line_orig[len(line_orig) - len(line):]
            target_dtx_filenames.append(filename)

    os.makedirs(output_folder, exist_ok=True)

    target_dtx_filenames = list(set(target_dtx_filenames))

    set_data = open(set_filename, "r").read()
    for filename in target_dtx_filenames:
        new_filename = fixup_dtx(os.path.join(input_folder, filename), input_folder, output_folder, no_convert, resources)
        set_data = set_data.replace(filename, new_filename)

    open(os.path.join(output_folder, "set.def"), "w", encoding="shift-jis").write(set_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Input file', required=True)
    parser.add_argument('-o', '--output', help='Output file', required=True)
    parser.add_argument('-n', '--no-convert', help='Do NOT convert all audio to OGG', default=False, action='store_true')
    parser.add_argument('-r', '--resources', help='Folder containing additional resources to copy (optional)', default=None)
    args = parser.parse_args()

    process_folder(args.input, args.output, args.no_convert, args.resources)
