"""Comparison helpers for verifying chart conversions.

Reusable utilities for the conversion verification suite (see run_all.py):
  - binary_compare:   raw byte comparison of two files
  - load_charts_json: load a seqtool JSON output (folder/output.json or file)
  - semantic_compare: compare two parsed-chart JSONs field-by-field
  - parse_sq3_events: split an .sq3 container into per-chart 0x40 event blocks
  - event_multiset_compare: match charts by identity and compare event content
                            ignoring on-disk ordering

These intentionally depend only on the standard library so they can run
without the full toolkit environment.
"""

import json
import os
import struct


def binary_compare(path_a, path_b):
    """Return (identical, len_a, len_b, num_differing_common_bytes)."""
    a = open(path_a, "rb").read()
    b = open(path_b, "rb").read()
    n = min(len(a), len(b))
    differing = sum(1 for i in range(n) if a[i] != b[i])
    return (a == b, len(a), len(b), differing)


def load_charts_json(path):
    """Load a seqtool JSON result.

    Accepts either the output folder (containing output.json, the form the
    JSON plugin writes) or a direct path to a .json file.
    """
    if os.path.isdir(path):
        path = os.path.join(path, "output.json")
    with open(path, "r") as f:
        return json.load(f)


def semantic_compare(json_a, json_b):
    """Compare two parsed-chart JSON structures.

    Returns (all_identical, list_of_per_chart_dicts). Each per-chart dict has
    game_type, difficulty, is_metadata, note_count, header_match, beat_data_match.
    """
    parts = {0: "drum", 1: "guitar", 2: "bass", 3: "open"}
    results = []
    top_ok = (
        json_a.get("format") == json_b.get("format")
        and json_a.get("musicid") == json_b.get("musicid")
        and len(json_a.get("charts", [])) == len(json_b.get("charts", []))
    )
    all_ok = top_ok

    for ca, cb in zip(json_a.get("charts", []), json_b.get("charts", [])):
        notes = [e for e in ca["beat_data"] if e["name"] == "note"]
        header_match = ca["header"] == cb["header"]
        beat_match = ca["beat_data"] == cb["beat_data"]
        all_ok = all_ok and header_match and beat_match
        results.append({
            "part": parts.get(ca["header"]["game_type"], "?"),
            "difficulty": ca["header"]["difficulty"],
            "is_metadata": ca["header"]["is_metadata"],
            "note_count": len(notes),
            "header_match": header_match,
            "beat_data_match": beat_match,
        })

    return all_ok, results


def parse_sq3_events(path):
    """Split an .sq3 (SEQP) container into charts of raw 0x40 event blocks.

    Returns a list of dicts: {key: (is_metadata, game_type, difficulty),
    events: [bytes, ...]}. Mirrors the on-disk layout the sq3 plugin reads:
    0x20 global header, then per chart a 0x10 file header + 0x20 SQ3T header
    + N * 0x40 event blocks.
    """
    data = open(path, "rb").read()
    if data[0:4] != b"SEQP":
        raise ValueError("%s is not a SEQP/SQ3 container" % path)

    num_charts = struct.unpack("<I", data[0x18:0x1c])[0]
    charts = []
    off = 0x20
    for _ in range(num_charts):
        sq3t = off + 0x10
        n_events = struct.unpack("<I", data[sq3t + 0x10:sq3t + 0x14])[0]
        is_metadata = data[sq3t + 0x15]
        difficulty = data[sq3t + 0x16]
        game_type = data[sq3t + 0x17]
        ev_start = sq3t + 0x20
        events = [
            bytes(data[ev_start + i * 0x40:ev_start + (i + 1) * 0x40])
            for i in range(n_events)
        ]
        charts.append({"key": (is_metadata, game_type, difficulty), "events": events})
        off = ev_start + n_events * 0x40
    return charts


def event_multiset_compare(path_a, path_b):
    """Compare two .sq3 files chart-by-chart, matched by identity.

    Returns (all_content_identical, list_of_per_chart_dicts). Each entry reports
    whether the matched chart's events are identical as an ordered list and as a
    multiset (order-independent). Useful to distinguish benign on-disk reordering
    from real content differences.
    """
    a = parse_sq3_events(path_a)
    b = parse_sq3_events(path_b)
    bm = {c["key"]: c["events"] for c in b}
    parts = {0: "drum", 1: "guitar", 2: "bass", 3: "open"}

    results = []
    all_ok = len(a) == len(b)
    for c in a:
        key = c["key"]
        eb = bm.get(key)
        if eb is None:
            results.append({"label": str(key), "matched": False})
            all_ok = False
            continue
        order_match = c["events"] == eb
        multiset_match = sorted(c["events"]) == sorted(eb)
        all_ok = all_ok and multiset_match
        label = "META" if key[0] else "%s d%d" % (parts.get(key[1], "?"), key[2])
        results.append({
            "label": label,
            "matched": True,
            "order_match": order_match,
            "multiset_match": multiset_match,
        })
    return all_ok, results
