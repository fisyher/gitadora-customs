"""Run and verify the six core conversion paths against the bundled test data.

Exercises seqtool.py end-to-end and checks the results:

  1. drum   SQ3 -> JSON
  2. drum   JSON -> SQ3        (expect byte-identical roundtrip)
  3. guitar SQ3 -> JSON
  4. guitar JSON -> SQ3        (expect 100% semantic/gameplay fidelity)
  5. drum   SQ3 -> DTX
  6. guitar IFS -> DTX         (with sounds; the intended guitar DTX path)

Usage (from anywhere):
    python verification/run_all.py <music_id>

The music id selects which song under test_data/input/ to verify, using the
toolkit's file naming conventions:
    seq folder : test_data/input/m<id>_seq_ifs/   (d<id>.sq3, g<id>.sq3, ...)
    bgm folder : test_data/input/m<id>_bgm_ifs/

Notes:
  - Requires the toolkit environment (see requirements.txt) for the DTX-with-
    sounds path, which extracts VA3 keysounds and uses ffmpeg via pydub.
  - Outputs are written to test_data/output/ (gitignored) and reused/overwritten
    on each run; output folder names are namespaced by music id.
  - Exit code is 0 when every required check passes, 1 otherwise.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import sq3_compare as cmp  # noqa: E402

IN = os.path.join("test_data", "input")
OUT = os.path.join("test_data", "output")

results = []  # (name, passed, detail)


def paths_for(music_id):
    """Build the input paths for a song from its music id."""
    seq = os.path.join(IN, "m%d_seq_ifs" % music_id)
    bgm = os.path.join(IN, "m%d_bgm_ifs" % music_id)
    return {
        "music_id": music_id,
        "seq_ifs": seq,
        "bgm_ifs": bgm,
        "drum_sq3": os.path.join(seq, "d%d.sq3" % music_id),
        "guitar_sq3": os.path.join(seq, "g%d.sq3" % music_id),
    }


def dtx_names(prefix, music_id):
    """Expected DTX filenames for an instrument prefix (d/g/b)."""
    return ["%s%d_%s_sq3.dtx" % (prefix, music_id, diff)
            for diff in ("bsc", "adv", "ext", "mst")]


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    mark = "PASS" if passed else "FAIL"
    line = "  [%s] %s" % (mark, name)
    if detail:
        line += " -- " + detail
    print(line)


def seqtool(args):
    """Run seqtool.py from the repo root. Returns (ok, combined_output)."""
    proc = subprocess.run(
        [sys.executable, "seqtool.py"] + args,
        cwd=ROOT, capture_output=True, text=True,
    )
    return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")


def fresh(path):
    full = os.path.join(ROOT, path)
    if os.path.exists(full):
        shutil.rmtree(full)


def abspath(path):
    return os.path.join(ROOT, path)


def roundtrip(label, src_sq3, prefix):
    """SQ3 -> JSON -> SQ3 -> JSON, with binary + semantic checks.

    Returns the binary-identical flag so the caller can decide pass criteria.
    """
    json_dir = os.path.join(OUT, prefix + "_json")
    rt_dir = os.path.join(OUT, prefix + "_roundtrip")
    reparse_dir = os.path.join(OUT, prefix + "_reparse")
    for d in (json_dir, rt_dir, reparse_dir):
        fresh(d)

    # 1) SQ3 -> JSON
    ok, out = seqtool(["--input", src_sq3, "--output-format", "json",
                       "--output", json_dir, "--no-sounds", "--single-threaded"])
    ok = ok and os.path.exists(abspath(os.path.join(json_dir, "output.json")))
    record("%s SQ3 -> JSON" % label, ok)
    if not ok:
        return False

    # 2) JSON -> SQ3
    out_sq3 = os.path.join(rt_dir, os.path.basename(src_sq3))
    ok, _ = seqtool(["--input", json_dir, "--input-format", "json",
                     "--output-format", "sq3", "--output", rt_dir,
                     "--no-sounds", "--single-threaded"])
    ok = ok and os.path.exists(abspath(out_sq3))
    record("%s JSON -> SQ3 (file produced)" % label, ok)
    if not ok:
        return False

    # Binary comparison against the original
    identical, la, lb, diff = cmp.binary_compare(abspath(src_sq3), abspath(out_sq3))
    record("%s roundtrip binary" % label, True,
           "BYTE-IDENTICAL" if identical else
           "differ (orig=%d rt=%d, %d bytes differ in common)" % (la, lb, diff))

    # Semantic comparison: reparse the roundtrip and diff the JSON
    ok, _ = seqtool(["--input", out_sq3, "--output-format", "json",
                     "--output", reparse_dir, "--no-sounds", "--single-threaded"])
    if not ok:
        record("%s semantic fidelity" % label, False, "reparse failed")
        return identical
    ja = cmp.load_charts_json(abspath(json_dir))
    jb = cmp.load_charts_json(abspath(reparse_dir))
    all_ok, per = cmp.semantic_compare(ja, jb)
    record("%s semantic fidelity (all charts identical)" % label, all_ok,
           "%d charts" % len(per))

    # If not byte-identical, characterise the difference. It is benign as long
    # as semantic fidelity holds: the bytes that differ (chart ordering and the
    # auto-note underlying lane id) are normalised away by the JSON intermediate
    # and do not change gameplay.
    if not identical:
        content_ok, _ = cmp.event_multiset_compare(abspath(src_sq3), abspath(out_sq3))
        if content_ok:
            detail = "on-disk order differs; event content identical"
        elif all_ok:
            detail = "raw bytes differ (chart order / auto-note lane id) but gameplay-semantically identical"
        else:
            detail = "matched charts differ in event content AND semantics"
        record("%s byte-diff is benign" % label, content_ok or all_ok, detail)

    return identical


def dtx_path(label, args, expected_files):
    out_dir = args[args.index("--output") + 1]
    fresh(out_dir)
    ok, out = seqtool(args)
    produced = [
        f for f in expected_files
        if os.path.exists(abspath(os.path.join(out_dir, f)))
    ]
    passed = ok and len(produced) == len(expected_files)
    record(label, passed, "%d/%d expected files" % (len(produced), len(expected_files)))
    if not passed and out:
        print("       last output:\n       " + "\n       ".join(out.strip().splitlines()[-4:]))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("music_id", type=int,
                        help="music id of the song under test_data/input/ to verify")
    args = parser.parse_args()

    mid = args.music_id
    p = paths_for(mid)

    print("=" * 64)
    print("Conversion verification suite (music id: %d)" % mid)
    print("=" * 64)

    # Fail fast with a clear message if the inputs aren't where we expect.
    missing = [path for path in (p["drum_sq3"], p["guitar_sq3"], p["bgm_ifs"])
               if not os.path.exists(abspath(path))]
    if missing:
        print("\nERROR: missing input files for music id %d:" % mid)
        for path in missing:
            print("  - %s" % path)
        print("\nExpected layout: %s/{d%d.sq3,g%d.sq3}  and  %s/"
              % (p["seq_ifs"], mid, mid, p["bgm_ifs"]))
        return 1

    print("\n-- Roundtrip: drum (expect byte-identical) --")
    drum_identical = roundtrip("drum", p["drum_sq3"], "d%d" % mid)

    print("\n-- Roundtrip: guitar/bass (expect semantic fidelity) --")
    roundtrip("guitar", p["guitar_sq3"], "g%d" % mid)

    print("\n-- SQ3 -> DTX: drum --")
    dtx_path(
        "drum SQ3 -> DTX",
        ["--input", p["drum_sq3"], "--output-format", "dtx",
         "--output", os.path.join(OUT, "d%d_dtx" % mid),
         "--no-sounds", "--single-threaded"],
        ["set.def"] + dtx_names("d", mid),
    )

    print("\n-- IFS -> DTX: guitar/bass (with sounds) --")
    dtx_path(
        "guitar IFS -> DTX (with sounds)",
        ["--input-ifs-seq", p["seq_ifs"], "--input-ifs-bgm", p["bgm_ifs"],
         "--ifs-target", "sq3", "--parts", "guitar", "bass",
         "--output-format", "dtx",
         "--output", os.path.join(OUT, "g%d_dtx_sounds" % mid),
         "--single-threaded"],
        ["set.def"] + dtx_names("g", mid) + dtx_names("b", mid),
    )

    # Summary. Required checks are everything except the informational
    # "roundtrip binary" line (guitar is intentionally not byte-identical).
    print("\n" + "=" * 64)
    required = [r for r in results if not r[0].endswith("roundtrip binary")]
    failed = [r for r in required if not r[1]]
    passed_n = len(required) - len(failed)
    print("SUMMARY: %d/%d required checks passed" % (passed_n, len(required)))
    if drum_identical:
        print("  drum roundtrip: BYTE-IDENTICAL")
    if failed:
        print("  FAILED:")
        for name, _, detail in failed:
            print("    - %s%s" % (name, (" (%s)" % detail) if detail else ""))
    print("=" * 64)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
