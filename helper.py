import pykakasi
import imageio
import os
import shutil

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
