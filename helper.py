import pykakasi
import imageio
import os
import shutil


def getCaseInsensitivePath(path):
    """
    Source: http://code.activestate.com/recipes/576571-case-insensitive-filename-on-nix-systems-return-th/
    Get a case insensitive path on a case sensitive system
    """

    if path == "" or os.path.exists(path):
        return path

    f = os.path.basename(path) # f may be a directory or a file
    d = os.path.dirname(path)

    suffix = ""
    if not f: # dir ends with a slash?
        if len(d) < len(path):
            suffix = path[:len(path)-len(d)]

        f = os.path.basename(d)
        d = os.path.dirname(d)

    if not os.path.exists(d):
        d, found = getCaseInsensitivePath(d, True)

        if not found:
            return path

    # at this point, the directory exists but not the file

    try: # we are expecting 'd' to be a directory, but it could be a file
        files = os.listdir(d)
    except:
        return path

    f_low = f.lower()

    try:
        f_nocase = [fl for fl in files if fl.lower() == f_low][0]
    except:
        f_nocase = None

    if f_nocase:
        return os.path.join(d, f_nocase) + suffix

    else:
        return path # cant find the right one, just return the path as is.


def romanize(text):
    kakasi = pykakasi.kakasi()
    kakasi.setMode("H","a")
    kakasi.setMode("K","a")
    kakasi.setMode("J","a")
    kakasi.setMode("C", True)
    conv = kakasi.getConverter()
    new_text = conv.do(text)
    return new_text.upper() if text != new_text else text



def check_ffmpeg():
    try:
        if not os.path.exists("ffmpeg.exe"):
            exe_path = imageio.plugins.ffmpeg.get_exe()
            ext = os.path.splitext(exe_path)[-1]
            filename = "ffmpeg" + ext

            shutil.copy(exe_path, filename)

    except:
        imageio.plugins.ffmpeg.download(directory=".")

        for platform in imageio.plugins.ffmpeg.FNAME_PER_PLATFORM:
            filename = imageio.plugins.ffmpeg.FNAME_PER_PLATFORM[platform]
            path = os.path.join("ffmpeg", filename)
            ext = os.path.splitext(filename)[-1]

            if os.path.exists(path):
                shutil.copy(path, "ffmpeg" + ext)
