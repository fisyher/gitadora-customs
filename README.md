# Installing

If you just want to use `manage_packages.py`, then install the required packages using
`python -m pip install -r requirements-manage_packages.txt`

If you want to run the whole toolkit, then install the required packages using
`python -m pip install -r requirements.txt`

You will need Git installed to install the requirements for the full toolkit.
This is due to the code that automatically turns Japanese titles into romaji during package creation.
You may also need to install `six` and `semidbm` manually through pip.

# Tools

## eamxml.py
This tool is used to convert between regular XML and Konami's binary XML formats.
The default is to look for libeamxml.dll (a tool I wrote, but probably won't release unless required) and then look for mon's kbinxml if that couldn't be found.
If you have kbinxml installed, you shouldn't have any issues.
```
usage: eamxml.py [-h] (-e | -d) -i INPUT -o OUTPUT

optional arguments:
  -h, --help            show this help message and exit
  -e, --encode          Encode mode
  -d, --decode          Decode mode
  -i INPUT, --input INPUT
                        Input file
  -o OUTPUT, --output OUTPUT
                        Output file
```

Convert binary XML to regular XML:
`python eamxml.py -d -i file_encoded.bin -o file_decoded.xml`

Convert regular XML to binary XML:
`python eamxml.py -e -i file_decoded.xml -o file_encoded.bin`


## vas3tool.py
VA3 archives contain the keysounds and other system sounds for Gitadora (also Jubeat).
A metadata.json is required to create your own VA3 archive.
This can be gotten by either extracting an existing VA3 file or when creating a SQ3 conversion using seqtool.py.
```
usage: vas3tool.py [-h] (-e | -d) -i INPUT -o OUTPUT [-m] [-f]

optional arguments:
  -h, --help            show this help message and exit
  -x, --extract         Extraction mode
  -c, --create          Creation mode
  -i INPUT, --input INPUT
                        Input file
  -o OUTPUT, --output OUTPUT
                        Output file
  -m, --mix             Mix output files using volume and pan parameters
  -f, --force-hex       Force hex filenames
```

Extract .VA3 archive:
`python vas3tool.py -x -i drums.va3 -o drums`

Create .VA3 archive:
`python vas3tool.py -c -i drums -o drums.va3`

`--mix` can be used to mix the volume and pan levels of the audio based on the levels specified in the metadata of the archive.
`--force-hex` can be used to force the filenames to use hex IDs only.

## wavbintool.py
This tool can handle the .BIN audio found in Gitadora (also Jubeat).
```
usage: wavbintool.py [-h] (-e | -d) -i INPUT -o OUTPUT [-c CHANNELS] [-r RATE]
                     [-s SILENCE] [-ls LOOP_START] [-le LOOP_END]

optional arguments:
  -h, --help            show this help message and exit
  -e, --encode          Encode mode
  -d, --decode          Decode mode
  -i INPUT, --input INPUT
                        Input file
  -o OUTPUT, --output OUTPUT
                        Output file
  -c CHANNELS, --channels CHANNELS
                        Number of channels for input WAV
  -r RATE, --rate RATE  Sample rate for input WAV
  -ls LOOP_START, --loop-start LOOP_START
                        Loop start point (in bytes)
  -le LOOP_END, --loop-end LOOP_END
                        Loop end point (in bytes)
```

Convert BIN to WAV:
`python wavbintool.py -d -i bgm.bin -o bgm.wav`

Convert WAV to BIN:
`python wavbintool.py -e -i bgm.wav -o bgm.bin`

There are various parameters available.
`--rate` can set the output rate of the WAV (usually 48000Hz)
`--channels` can force between mono (1) or stereo (2) files
`--loop-start` can set the start loop point
`--loop-end` can set the end loop point

Loop point information will be displayed in the terminal if converting a BIN to WAV that has loop information.
The loop information is also stored in the WAV in the `SMPL` section if you use a compatible music player.
`foo_input_wave_loop` can be used to loop the WAV files properly in foobar2000 (the `.wav` extension *MUST* be renamed `.wavloop` for it to work).
When converting a WAV file with the `SMPL` chunk, it will automatically read the first loop point so you do not need to specify the `--loop-start` or `--loop-end` manually.

## create_gst.py
Who doesn't like GSTs? This is useful for making your own GST version of a song using the BGM IFS file from Gitadora.
```
usage: create_gst.py [-h] --input INPUT [--output OUTPUT] [--artist ARTIST]
                     [--title TITLE] [--album ALBUM] [--format FORMAT]
                     [--quality QUALITY] [--mix-phase]
                     [--mix-base-volume MIX_BASE_VOLUME]
                     [--mix-guitar-volume MIX_GUITAR_VOLUME]
                     [--mix-drum-volume MIX_DRUM_VOLUME]

optional arguments:
  -h, --help            show this help message and exit
  --input INPUT         Input file/folder
  --output OUTPUT       Output filename
  --artist ARTIST       Artist tag
  --title TITLE         Title tag
  --album ALBUM         Album tag
  --format FORMAT       Output format
  --quality QUALITY     Output quality
  --mix-phase           Mix using inverted phase BGM
  --mix-base-volume MIX_BASE_VOLUME
                        Reduce volume of base audio
  --mix-guitar-volume MIX_GUITAR_VOLUME
                        Reduce volume of guitar audio
  --mix-drum-volume MIX_DRUM_VOLUME
                        Reduce volume of drum audio
```

Create WAV from BGM IFS:
`python create_gst.py --input m1823_bgm.ifs --output m1823.wav`

Create WAV from BGM IFS using phase inversion to isolate instruments (better mixing):
`python create_gst.py --input m1823_bgm.ifs --output m1823.wav --mix-phase`

You can also use the `--mix-base-volume`, `--mix-guitar-volume`, and `--mix-drum-volume` parameters to better control the volumes when mixed.
If anyone comes up with defaults better than what I use, please feel free to mention it and I might make those settings the defaults instead.

`--title`, `--artist`, `--album` are used to control the tags and can be used for automatically naming the files.

`--quality` is the quality string passed to pydub (for MP3, '320k' etc)
`--format` is the format string passed to pydub ('WAV', 'MP3', 'OGG', etc)

## manage_packages.py
This is the package manager to be used for installing new songs into Gitadora.
I am considering making it a full blown song manager which would allow you to add/remove songs and list all songs (installed and default).
For now, this will just install new songs and make backups of system files before editing.
If a full blown song manager is something people want then please say something and I'll prioritize it.

```
usage: manage_packages.py [-h] [-g GAME_DIR] [-p PACKAGES_DIR]

optional arguments:
  -h, --help            show this help message and exit
  -g GAME_DIR, --game-dir GAME_DIR
                        Input game directory
  -p PACKAGES_DIR, --packages-dir PACKAGES_DIR
                        Input packages directory
```

You can put `manage_packages.py` and the tools folder inside the Gitadora directory (the same folder with the EXEs/DLLs and the data folder available) and it will automatically find all of the required files from there.
A `packages` folder must also be available somewhere. It will default to looking for `packages` in the same folder as `manage_packages.py`, or you can specify a folder where the packages are located.

If the `packages` folder is in the same folder as `manage_packages.py`, and everything is placed in the Gitadora folder:
`python manage_packages.py` (OR just run `manage_packages.bat`)

If you would like to specify a game directory or packages folder (both are optional):
`python mangae_packages.py -g "C:\path\to\gitadora\" -p "C:\path\to\packages\"`

## seqtool.py
The big boy. This tool is used to convert between different chart formats.

About the workflow for this tool:
All data is converted to an intermediate JSON format before being converted to its final output format.
SQ3 -> JSON -> DTX
SQ3 -> JSON -> WAV
DTX -> JSON -> SQ3
JSON -> (JSON) -> SQ3
etc

The JSON format plugin is available, so you can use JSON as an input and output format.
This makes it possible to make manual edits to stuff before converting to the final output format.
For example, if you would like to add down wails to a DTX -> SQ3 conversion then convert to JSON, manually edit the appropriate spots, then convert the JSON to SQ3.

The following plugins are available:
DTX (input, output)
SQ3 (input, output)
SQ2 (input, output)
JSON (input, output)
WAV (output)

```
usage: seqtool.py [-h] [--input INPUT] [--input-format INPUT_FORMAT]
                  [--sound-folder SOUND_FOLDER] [--event-file EVENT_FILE]
                  [--input-drum-nov INPUT_DRUM_NOV]
                  [--input-drum-bsc INPUT_DRUM_BSC]
                  [--input-drum-adv INPUT_DRUM_ADV]
                  [--input-drum-ext INPUT_DRUM_EXT]
                  [--input-drum-mst INPUT_DRUM_MST]
                  [--input-guitar-nov INPUT_GUITAR_NOV]
                  [--input-guitar-bsc INPUT_GUITAR_BSC]
                  [--input-guitar-adv INPUT_GUITAR_ADV]
                  [--input-guitar-ext INPUT_GUITAR_EXT]
                  [--input-guitar-mst INPUT_GUITAR_MST]
                  [--input-bass-nov INPUT_BASS_NOV]
                  [--input-bass-bsc INPUT_BASS_BSC]
                  [--input-bass-adv INPUT_BASS_ADV]
                  [--input-bass-ext INPUT_BASS_EXT]
                  [--input-bass-mst INPUT_BASS_MST]
                  [--input-open-nov INPUT_OPEN_NOV]
                  [--input-open-bsc INPUT_OPEN_BSC]
                  [--input-open-adv INPUT_OPEN_ADV]
                  [--input-open-ext INPUT_OPEN_EXT]
                  [--input-open-mst INPUT_OPEN_MST]
                  [--input-ifs-seq INPUT_IFS_SEQ]
                  [--input-ifs-bgm INPUT_IFS_BGM] [--ifs-target {sq3,sq2}]
                  --output OUTPUT --output-format OUTPUT_FORMAT
                  [--parts [{drum,guitar,bass,all} [{drum,guitar,bass,all} ...]]]
                  [--difficulty [{nov,bsc,adv,ext,mst,all,max,min} [{nov,bsc,adv,ext,mst,all,max,min} ...]]]
                  [--merge-guitars] [--no-sounds] [--generate-bgms]
                  [--music-db MUSIC_DB] [--music-id MUSIC_ID]
                  [--render-auto-name] [--render-ext RENDER_EXT]
                  [--render-quality RENDER_QUALITY]
                  [--render-volume RENDER_VOLUME]
                  [--render-volume-bgm RENDER_VOLUME_BGM]
                  [--render-volume-auto RENDER_VOLUME_AUTO] [--render-no-bgm]
                  [--render-ignore-auto] [--dtx-pad-start DTX_PAD_START]
                  [--dtx-pad-end DTX_PAD_END] [--dtx-fake-timesigs]

optional arguments:
  -h, --help            show this help message and exit
  --output OUTPUT       Output file/folder
  --output-format OUTPUT_FORMAT
                        Output file format
  --parts [{drum,guitar,bass,all} [{drum,guitar,bass,all} ...]]
  --difficulty [{nov,bsc,adv,ext,mst,all,max,min} [{nov,bsc,adv,ext,mst,all,max,min} ...]]
  --merge-guitars       Merge guitar charts
  --no-sounds           Don't convert sound files
  --generate-bgms       Generate BGMs for various combination of instruments
                        as needed (SQ2/SQ3)
  --music-db MUSIC_DB   Music database file to read metadata about song
  --music-id MUSIC_ID   Force a music ID
  --render-auto-name    Automatically name output file
  --render-ext RENDER_EXT
                        Force extension when rendering audio file
  --render-quality RENDER_QUALITY
                        Force quality (320k, etc) when rendering audio file
  --render-volume RENDER_VOLUME
                        Force volume of selected part during rendering
  --render-volume-bgm RENDER_VOLUME_BGM
                        Force volume of BGM during rendering
  --render-volume-auto RENDER_VOLUME_AUTO
                        Force volume of auto notes during rendering
  --render-no-bgm       Mute BGM during render
  --render-ignore-auto  Mute auto notes during render
  --dtx-pad-start DTX_PAD_START
                        Pad the start of the song by x measures
  --dtx-pad-end DTX_PAD_END
                        Pad the end of the song by x measures
  --dtx-fake-timesigs   Fake time signatures when converting to DTX to work
                        around x/4 limitation

input:
  --input INPUT         Input file/folder
  --input-format INPUT_FORMAT
                        Input file format
  --sound-folder SOUND_FOLDER
                        Input folder containing sounds
  --event-file EVENT_FILE
                        Input file containing event information (for SQ2/SQ3)

input_dtx:
  --input-drum-nov INPUT_DRUM_NOV
                        DTX novice drum chart input (for creation)
  --input-drum-bsc INPUT_DRUM_BSC
                        DTX basic drum chart input (for creation)
  --input-drum-adv INPUT_DRUM_ADV
                        DTX advanced drum chart input (for creation)
  --input-drum-ext INPUT_DRUM_EXT
                        DTX extreme drum chart input (for creation)
  --input-drum-mst INPUT_DRUM_MST
                        DTX master drum chart input (for creation)
  --input-guitar-nov INPUT_GUITAR_NOV
                        DTX novice guitar chart input (for creation)
  --input-guitar-bsc INPUT_GUITAR_BSC
                        DTX basic guitar chart input (for creation)
  --input-guitar-adv INPUT_GUITAR_ADV
                        DTX advanced guitar chart input (for creation)
  --input-guitar-ext INPUT_GUITAR_EXT
                        DTX extreme guitar chart input (for creation)
  --input-guitar-mst INPUT_GUITAR_MST
                        DTX master guitar chart input (for creation)
  --input-bass-nov INPUT_BASS_NOV
                        DTX novice bass chart input (for creation)
  --input-bass-bsc INPUT_BASS_BSC
                        DTX basic bass chart input (for creation)
  --input-bass-adv INPUT_BASS_ADV
                        DTX advanced bass chart input (for creation)
  --input-bass-ext INPUT_BASS_EXT
                        DTX extreme bass chart input (for creation)
  --input-bass-mst INPUT_BASS_MST
                        DTX master bass chart input (for creation)
  --input-open-nov INPUT_OPEN_NOV
                        DTX novice open chart input (for creation)
  --input-open-bsc INPUT_OPEN_BSC
                        DTX basic open chart input (for creation)
  --input-open-adv INPUT_OPEN_ADV
                        DTX advanced open chart input (for creation)
  --input-open-ext INPUT_OPEN_EXT
                        DTX extreme open chart input (for creation)
  --input-open-mst INPUT_OPEN_MST
                        DTX master open chart input (for creation)

input_ifs:
  --input-ifs-seq INPUT_IFS_SEQ
                        Input file/folder for SEQ (IFS)
  --input-ifs-bgm INPUT_IFS_BGM
                        Input file/folder for BGM (IFS)
  --ifs-target {sq3,sq2}
                        Target specific chart type within IFS
```

There are a lot of ways you could use this tool, but I'll cover the most common use cases.

Convert from IFS (SQ3) to DTX:
`python seqtool.py --input-ifs-bgm m1825_bgm.ifs --input-ifs-seq m1825_seq.ifs --ifs-target sq3 --output-format dtx --output m1825_dtx_sq3`

Convert from IFS (SQ2) to DTX:
`python seqtool.py --input-ifs-bgm m1825_bgm.ifs --input-ifs-seq m1825_seq.ifs --ifs-target sq2 --output-format dtx --output m1825_dtx_sq2`

Convert from DTX to SQ3:
`python seqtool.py --input-drum-ext m1825_dtx_sq3\d1825_ext.dtx --input-format dtx --output-format sq3 --sound-folder m1825_dtx_sq3 --output m1825_sq3`

Convert from DTX to SQ3 using BGMs generated based on the input chart data:
`python seqtool.py --input-drum-ext m1825_dtx_sq3\d1825_ext.dtx --input-format dtx --output-format sq3 --sound-folder m1825_dtx_sq3 --output m1825_sq3 --generate-bgms`
This option is useful if you are converting from a custom DTX to SQ3 because it will generate all required BGM instrument combinations based on the available charts.
The downside is that it takes longer to generate 5 different BGMs.

Convert from extracted IFS folder to DTX:
`python seqtool.py --input-ifs-bgm m1825_bgm_ifs --input-ifs-seq m1825_seq_ifs --ifs-target sq3 --output-format dtx --output m1825_dtx_sq3`

Convert from SQ3 to DTX:
`python seqtool.py --input m1825_seq\d1825.sq3 --output-format dtx --output m1825_dtx_sq3`

Convert from SQ3 to JSON:
`python seqtool.py --input m1825_seq\d1825.sq3 --output-format json --output m1825_sq3.json`

Convert from JSON to SQ3:
`python seqtool.py --input m1825_sq3.json --input-format json --output-format sq3 --output d1825.sq3`

Convert from IFS (SQ3, drum and bass charts only, maximum difficulty available) to WAV:
`python seqtool.py --input-ifs-bgm m1825_bgm.ifs --input-ifs-seq m1825_seq.ifs --ifs-target sq3 --output-format wav --output m1825.wav --parts drum bass --difficulty max`

When generating SQ3s from DTX:
```
  --dtx-pad-start DTX_PAD_START
                        Pad the start of the song by x measures
  --dtx-pad-end DTX_PAD_END
                        Pad the end of the song by x measures
```
These can be used to add padding to the beginning and end of charts.
Without this option, the charts will start immediately and end immediately in-game.
BGMs are fixed appropriately when using these options.

When generating DTX:
```
  --dtx-fake-timesigs   Fake time signatures when converting to DTX to work
                        around x/4 limitation
```
This option can be used to fake the time signature. DTX is limited to x/4 time signature, whereas Gitadora has more time signatures available. This option converts everything to x/4 and increases the BPM appropriately in order to fix the way the lines look in DTXMania.


When rendering WAVs:
```
  --render-auto-name    Automatically name output file
  --render-ext RENDER_EXT
                        Force extension when rendering audio file
  --render-quality RENDER_QUALITY
                        Force quality (320k, etc) when rendering audio file
  --render-volume RENDER_VOLUME
                        Force volume of selected part during rendering
  --render-volume-bgm RENDER_VOLUME_BGM
                        Force volume of BGM during rendering
  --render-volume-auto RENDER_VOLUME_AUTO
                        Force volume of auto notes during rendering
  --render-no-bgm       Mute BGM during render
  --render-ignore-auto  Mute auto notes during render
```
I think these are fairly self explanatory so just play around with them.


General options:
```
  --parts [{drum,guitar,bass,all} [{drum,guitar,bass,all} ...]]
  --difficulty [{nov,bsc,adv,ext,mst,all,max,min} [{nov,bsc,adv,ext,mst,all,max,min} ...]]
  --merge-guitars       Merge guitar charts
  --no-sounds           Don't convert sound files
  --music-db MUSIC_DB   Music database file to read metadata about song
  --music-id MUSIC_ID   Force a music ID
```
`--parts` and `--difficulty` can be used to filter the instruments and difficulties that you convert to.
These options should work on any input and output format to my knowledge.

`--merge-guitars` is useful for merging the guitar and bass charts when converting to DTX.
Some songs may break when using this option if they have a ton of guitar and bass files, though.

`--no-sounds` can be used to avoid parsing sound data (useful for testing conversions)

`--music-id` can be used to force a music ID when converting to SQ2/SQ3.
Only use this if you know what you're doing

`--music-db` can be used to specify which file contains the music database you want to use (either a custom CSV format, or the XML MDB from the Gitadora folder can be used)
If the music database file can be found and parsed then the DTX, WAV, etc will automatically be named and tagged appropriately.
You can use `--music-db` and `--music-id` in combination to force a specific song's info to be loaded (if you wanted to for some reason).



# Preparing converted song for release
When you're ready to release a converted song, zip the entire folder containing the following files:
- package.json
- d/g0000.sq3
- spu000d/g.va3
- bgm000*.bin
- pre.jpg/pre.png/preview image filename
- event0000.ev2
- i0000gf/dm.bin

# Installing song packages
Extract the zip file into its own folder inside the `packages` folder.
For example, if you have `senpai.zip`, then extract the contents to `packages\senpai\`.
If done correctly, you should have the following:
```
packages\senpai\package.json
packages\senpai\bgm0000___k.bin
packages\senpai\bgm0000__bk.bin
packages\senpai\bgm0000_gbk.bin
packages\senpai\bgm0000d__k.bin
packages\senpai\bgm0000d_bk.bin
packages\senpai\d0000.sq3
packages\senpai\event0000.ev2
packages\senpai\i0000dm.bin
packages\senpai\i0000gf.bin
packages\senpai\pre.jpg
packages\senpai\spu0000d.va3
```