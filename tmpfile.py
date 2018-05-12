# This is kind of an in between for tempfile and the program
# because it's hard/annoying to track all temp file references
# in the program itself

import tempfile
import os
import shutil

temp_filenames = []
temp_foldernames = []

def add_temp_file(filename):
    temp_filenames.append(filename)

def add_temp_folder(filename):
    temp_foldernames.append(filename)

def mkstemp(suffix=""):
    fid, filename = tempfile.mkstemp(suffix=suffix)
    os.fdopen(fid, "w").close() # Fix bug with Windows

    #print("Made temp file", filename)
    temp_filenames.append(filename)

    return filename

def mkdtemp(prefix=None):
    foldername = tempfile.mkdtemp(prefix=prefix)
    #print("Made temp folder", foldername)
    temp_foldernames.append(foldername)
    return foldername

def tmpcleanup():
    for filename in temp_filenames:
        if os.path.exists(filename):
            #print("Removing temp file", filename)
            os.remove(filename)

    for foldername in temp_foldernames:
        if os.path.exists(foldername):
            #print("Removing temp folder", foldername)
            shutil.rmtree(foldername)