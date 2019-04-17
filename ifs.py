import argparse
import glob
import io
import os
import sys

# Cheap hack to make the release for manage_packages.py cleaner
try:
    import tools.tmpfile as tmpfile
except:
    import tmpfile

from ifstools.ifs import IFS

def extract(filename, path=None, progress=False):
    if not path:
        path = tmpfile.mkdtemp(prefix="ifs")

    ifs = IFS(filename)
    ifs.extract(progress=progress, path=path)

    # Get file list
    return glob.glob(os.path.join(path, "*")), path

def create(foldername, output_filename, progress=False):
    ifs = IFS(foldername)
    ifs.repack(progress=progress, path=output_filename, use_cache=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pack', action='store_true', help='pack all files in input folder to output ifs file')
    group.add_argument('-u', '--unpack', action='store_true', help='unpack input ifs file to output folder')
    parser.add_argument('-i', '--input', help='Input file/folder', required=True)
    parser.add_argument('-o', '--output', help='Output file/folder', required=True)
    parser.add_argument('-s', '--silent', help='Turns off progress meter', type=bool, default=False)
    args = parser.parse_args()
    if args.pack:
        create(args.input, args.output, args.silent)
    elif args.unpack:
        extract(args.input, args.output, args.silent)	
