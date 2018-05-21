# Audio-related helper functions

import os
import subprocess
import pydub
import tmpfile

import helper

helper.check_ffmpeg()


def get_audio_file(filename):
    filename = helper.getCaseInsensitivePath(filename)
    if not filename or not os.path.exists(filename):
        return None

    if filename.lower().endswith('.xa'):
        filename = get_wav_from_xa(filename)

    return pydub.AudioSegment.from_file(filename)

def get_duration(filename):
    filename = helper.getCaseInsensitivePath(filename)
    sound_file = get_audio_file(filename)

    if not sound_file:
        return 0

    return len(sound_file) / 1000

def clip_audio(input_filename, output_filename, duration):
    filename = helper.getCaseInsensitivePath(input_filename)
    sound_file = get_audio_file(filename)[:duration * 1000]
    sound_file.export(output_filename)
    print("Generated", output_filename, len(sound_file) / 1000, duration)

def merge_bgm(bgm_info, input_foldername, output_filename=None):
    longest_duration = bgm_info['end']

    # Find maximum duration of BGM
    channels = 1
    for bgm in bgm_info['data']:
        filename = helper.getCaseInsensitivePath(os.path.join(input_foldername, bgm['filename']))
        print(filename)
        bgm['file'] = pydub.AudioSegment.from_file(filename)
        duration = bgm['timestamp'] + len(bgm['file']) / 1000

        if bgm['file'].channels > channels:
            channels = bgm['file'].channels

        if duration > longest_duration:
            longest_duration = duration

    output = pydub.AudioSegment.silent(duration=longest_duration * 1000, frame_rate=48000)
    output.set_channels(channels)

    for bgm in bgm_info['data']:
        output = output.overlay(bgm['file'], position=bgm['timestamp'] * 1000)

    if output_filename:
        temp_filename = output_filename
    else:
        temp_filename = tmpfile.mkstemp(suffix=".wav")

    output.export(temp_filename, format="wav")

    return temp_filename

def get_wav_from_xa(input_filename):
    input_filename = helper.getCaseInsensitivePath(input_filename)

    prefix = ""
    if os.name != "nt":
        prefix = "wine"

    cmd = "{} xa.exe -d \"{}\"".format(prefix, input_filename.replace("/","\\"))
    subprocess.call(cmd, shell=True)

    temp_filename = os.path.splitext(input_filename)[0] + ".wav"
    tmpfile.add_temp_file(temp_filename)

    return temp_filename

def get_processed_wav(input_filename, output_filename=None, channels=1, bits=16, rate=48000):
    input_filename = helper.getCaseInsensitivePath(input_filename)

    output = get_audio_file(input_filename)

    if not output:
        return None

    made_change = False
    if output.sample_width != bits // 8:
        made_change = True
        output = output.set_sample_width(bits // 8)

    if output.channels != channels:
        made_change = True
        output = output.set_channels(channels)

    if output.frame_rate != rate:
        made_change = True
        output = output.set_frame_rate(rate)

    if not made_change and input_filename.lower().endswith('.wav'):
        # This file is already the exact requirements, just return the original
        return input_filename

    if output_filename == None:
        output_filename = tmpfile.mkstemp()

    #print("Converted {} to {}".format(input_filename, output_filename))
    output.export(output_filename, format="wav")

    return output_filename
