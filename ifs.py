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

def extract(filename, path=None, silent=False):
    if not path:
        path = tmpfile.mkdtemp(prefix="ifs")

    # "progress" flag doesn't work properly.
    # It will still show the tqdm progress bar, just without
    # listing what files are being extracted.
    # To get around this, temporarily redirect stderr.
    # os.devnull doesn't work for this case, so use StringIO.

    if silent:
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

    IFS(filename).extract(progress=False, path=path)

    if silent:
        sys.stderr = old_stderr

    # Get file list
    return glob.glob(os.path.join(path, "*")), path

def create(foldername, output_filename, silent=False):
    if silent:
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

    IFS(foldername).repack(progress=False, path=output_filename)

    if silent:
        sys.stderr = old_stderr

    return output_filename