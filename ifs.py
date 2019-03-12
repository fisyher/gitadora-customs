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

    return output_filename
