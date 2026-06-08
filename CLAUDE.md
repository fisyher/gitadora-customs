# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python 3 toolkit for creating and converting custom songs ("customs") for Konami's **GITADORA** arcade rhythm game (also handles some Jubeat formats). It reverse-engineers Konami's proprietary chart, audio, and archive formats so charts can be converted to/from the community DTX format (DTXMania) and installed back into the game.

There is no test suite, build step, or linter. Tools are standalone scripts run directly with `python <tool>.py`.

## Setup

```sh
python -m pip install -r requirements.txt              # full toolkit
python -m pip install -r requirements-manage_packages.txt   # just the package installer
```

Requires Python 3 and Git (Git is needed because `pykakasi` romaji conversion is pulled during install). `six` and `semidbm` sometimes need manual `pip install`.

Pinned deps live in `requirements.txt`. The current branch (`refactor-p314`) is a Python 3.14 compatibility refactor — `requirements.txt` is the file under active change.

## Bundled native binaries (Windows)

Several scripts shell out to vendored `.exe` tools that **must be in the working directory / on PATH**. There are no cross-platform fallbacks:
- `vgmstream_cli.exe`, `xa.exe` — audio decoding (`audio.py`)
- `adpcmwavetool.exe` — ADPCM WAV encode/decode (`adpcmwave.py`)
- `at3tool.py` wraps ATRAC3
- `tools/gitadora-tex*tool.exe`, `tools/gitadora-textgen.exe` — texture/jacket generation (`manage_packages.py`)
- `ffmpeg` (via `imageio-ffmpeg`) — checked at import time by `helper.check_ffmpeg()`

`build_release.bat` assembles a `releases/` distribution by copying scripts + binaries into `manage_packages/` and `work/` folders (no PyInstaller — it's disabled because `ifstools` uses multiprocessing `Pool`).

## Architecture

### seqtool.py — the chart converter (the "big boy")

The central tool. Everything routes through a **single intermediate JSON chart representation**: every input format is parsed *to* JSON, and every output format is rendered *from* JSON. So `DTX -> JSON -> SQ3`, `SQ3 -> JSON -> WAV`, etc. The JSON format is itself a plugin, so you can export to JSON, hand-edit, and re-import.

Pipeline in `process_file()` (`seqtool.py`):
1. `find_handler()` selects input + output plugins.
2. `input_handler.to_json(params)` → intermediate JSON string.
3. `filter_charts()` drops charts not matching `--parts` / `--difficulty`.
4. Optional metadata injection from a music DB (`mdb.py`, CSV or game XML MDB).
5. `output_handler.to_chart(params)` writes the final format (reads the JSON from `params['input']`).

`seqtool.py`'s `__main__` is large because it has two input paths: IFS archives (`--input-ifs-seq/-bgm`, which extract `.sq3/.sq2/.va3/.ev2` members and convert BGM `.bin`→`.wav`) vs. direct file input. Drum and guitar/bass chart sets are processed on **separate threads** by default (`--single-threaded` to disable); `tmpfile.tmpcleanup()` runs at the end.

### plugins/ — format handlers

Auto-discovered: `plugins/__init__.py` globs `*.py` into `__all__`, and `find_handler()` imports each and calls `get_class()`. **To add a format, drop a new module in `plugins/` exposing `get_class()`** — no registration needed.

Each plugin class implements static methods:
- `get_format_name()` → format string matched against `--input-format`/`--output-format`
- `is_format(filename)` → sniff an input file by extension/contents
- `to_json(params)` → parse to intermediate JSON (input formats)
- `to_chart(params)` → render JSON to final output (output formats)

Plugins may implement only one direction (e.g. `wav.py` is output-only — no `to_json`). The many `gsq*/dsq*/sq*` variants are version-specific binary chart formats; `plugins/sq.py` holds shared SQ parsing (`generate_json_from_data`) that `sq2.py`/`sq3.py` build on. `plugins/dtx.py` is by far the largest (DTXMania text charts).

### Chart data conventions (intermediate JSON)

- Parts indexed: `0=drum, 1=guitar, 2=bass, 3=open` (`game_type`).
- Difficulties indexed: `0=nov, 1=bsc, 2=adv, 3=ext, 4=mst`.
- Events carry an `is_metadata` flag; the metadata chart holds timing (bpm/barinfo/measure/beat) rather than playable notes. See `EVENT_ID_MAP` / `NOTE_MAPPING` in `plugins/sq3.py`.

### Supporting modules

- `ifs.py` — extract Konami IFS archives (wraps `ifstools`).
- `eamxml.py` — convert Konami binary XML (kbin) ↔ plain XML (`libeamxml.dll` if present, else `kbinxml`).
- `event.py` — parse bonus-note/event timing from event XML.
- `mdb.py` — read song metadata from game MDB XML or a custom CSV (`gitadora_music.csv`).
- `vas3tool.py` / `vas1tool.py` — VA3/VA1 keysound archive extract/create.
- `wavbintool.py` — Gitadora `.bin` audio ↔ WAV (loop points in WAV `SMPL` chunk).
- `audio.py`, `wavfile.py`, `adpcmwave.py`, `at3tool.py` — audio decode/encode/mix helpers.
- `tmpfile.py` — temp file/folder tracking under `./temp/`, cleaned by `tmpcleanup()`.

### manage_packages.py — the in-game installer

Separate from the conversion toolkit. Installs `packages/<name>/` song folders into a GITADORA game directory, backing up system files (music DB, etc.) before editing and generating jacket/banner textures. Run via `python manage_packages.py [-g GAME_DIR] [-p PACKAGES_DIR]` or `manage_packages.bat`. A release song folder contains `package.json`, `d/g0000.sq3`, `spu000d/g.va3`, `bgm000*.bin`, `event0000.ev2`, `i0000gf/dm.bin`, and a preview image (see README "Installing song packages").

## Common commands

```sh
# IFS (SQ3) -> DTX
python seqtool.py --input-ifs-bgm m_bgm.ifs --input-ifs-seq m_seq.ifs --ifs-target sq3 --output-format dtx --output out_dtx

# DTX -> SQ3 (generate the required BGM instrument combinations from the chart)
python seqtool.py --input-drum-ext out_dtx/d.dtx --input-format dtx --output-format sq3 --sound-folder out_dtx --output out_sq3 --generate-bgms

# SQ3 <-> JSON (hand-edit charts as JSON)
python seqtool.py --input d.sq3 --output-format json --output chart.json
python seqtool.py --input chart.json --input-format json --output-format sq3 --output d.sq3

# Render a chart to audio (one difficulty only for WAV)
python seqtool.py --input-ifs-bgm m_bgm.ifs --input-ifs-seq m_seq.ifs --ifs-target sq3 --output-format wav --output m.wav --parts drum bass --difficulty max
```

See `README.md` for the full per-tool argument reference (`eamxml.py`, `vas3tool.py`, `wavbintool.py`, `create_gst.py`, `seqtool.py`, `manage_packages.py`).

## Notes / gotchas

- The `.gitignore` excludes nearly every data extension this toolkit produces (`*.sq3`, `*.va3`, `*.bin`, `*.dtx`, `*.wav`, `*.json`, `*.csv`, `*.xml`…). Generated test artifacts won't show in git status — that's intentional.
- DTX only supports x/4 time signatures; `--dtx-fake-timesigs` works around this by rewriting everything to x/4 with adjusted BPM.
- WAV export rejects multiple difficulties at once.
- `seqtool.py:241` deletes an existing `set.def` in the DTX output dir on each run (acknowledged hack).
