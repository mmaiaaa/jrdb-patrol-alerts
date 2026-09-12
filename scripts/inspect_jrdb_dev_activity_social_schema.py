#!/usr/bin/env python3
"""Inspect actual JRDB-Act native-camera JSON schema on Cubberly development frames.

The 2022 labels.zip lacks labels/labels_2d/. This script *only* inspects the
explicit labels_2d_activity_social/ members. No metric or frame choice is made.
"""
import argparse
import json
import math
import zipfile
from pathlib import Path

from inspect_jrdb_dev_native_2d_reference import annotation_fields, selected_image_labels


SEQUENCE = "cubberly-auditorium-2019-04-22_0"
CAMERAS = (0, 2, 4, 6, 8)
FRAMES = ("000087", "000432", "000864", "001295")


def reference_ids(entries):
    return {str(item.get("label_id")) for item in entries
            if str(item.get("label_id", "")).startswith("pedestrian:")}


def near_reference_ids(entries):
    result = set()
    for item in entries:
        person = str(item.get("label_id", ""))
        if not person.startswith("pedestrian:") or (item.get("attributes") or {}).get("no_eval") is not False:
            continue
        box = item.get("box") or {}
        try:
            x, y = float(box["cx"]), float(box["cy"])
        except (TypeError, ValueError, KeyError):
            continue
        if math.isfinite(x) and math.isfinite(y) and math.hypot(x, y) <= 3.0:
            result.add(person)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--labels-zip", type=Path, default=Path.home() / "Downloads/labels.zip")
    parser.add_argument("--frames", nargs="+", default=FRAMES)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only" or manifest.get("sequence") != SEQUENCE:
        parser.error("Expected Cubberly development-only manifest")
    if not args.frames or len(args.frames) != len(set(args.frames)) or any(
            len(frame) != 6 or not frame.isdecimal() for frame in args.frames):
        parser.error("Provide distinct six-digit numeric development frame IDs")
    root = args.data_root / SEQUENCE
    labels = json.loads((root / manifest["label_3d"]).read_text())["labels"]
    ids3d, near3d = {}, {}
    for frame in args.frames:
        key = frame + ".pcd"
        if key not in labels:
            raise ValueError(f"Missing development reference frame {frame}")
        ids3d[frame] = reference_ids(labels[key])
        near3d[frame] = near_reference_ids(labels[key])
    directory = "labels/labels_2d_activity_social"
    expected = [f"{directory}/{SEQUENCE}_image{camera}.json" for camera in CAMERAS]
    views = []
    with zipfile.ZipFile(args.labels_zip) as archive:
        missing = sorted(set(expected) - set(archive.namelist()))
        if missing:
            raise ValueError(f"Expected JRDB-Act native-camera member(s) missing: {missing}")
        for camera, member in zip(CAMERAS, expected):
            payload = json.loads(archive.read(member))
            structure = {"camera": camera, "member": member,
                         "top_level_keys": sorted(payload) if isinstance(payload, dict) else None,
                         "labels_container_type": type(payload.get("labels")).__name__ if isinstance(payload, dict) else None,
                         "frame_key_count": len(payload["labels"]) if isinstance(payload, dict) and
                           isinstance(payload.get("labels"), dict) else None,
                         "first_nonempty_annotation_shape": None, "frames": []}
            for frame in args.frames:
                rows = selected_image_labels(payload, frame)
                if rows is None:
                    structure["frames"].append({"frame": frame, "status": "missing_or_unexpected_schema"})
                    continue
                if rows and structure["first_nonempty_annotation_shape"] is None:
                    shape = annotation_fields(rows)
                    example = rows[0] if isinstance(rows[0], dict) else {}
                    if isinstance(shape, dict):
                        shape["box_example"] = example.get("box") if isinstance(example.get("box"), dict) else None
                    structure["first_nonempty_annotation_shape"] = shape
                ids2d = reference_ids(item for item in rows if isinstance(item, dict))
                structure["frames"].append({
                    "frame": frame, "status": "read", "annotation_rows": len(rows),
                    "rows_with_dict_box": sum(isinstance(item, dict) and isinstance(item.get("box"), dict)
                                              for item in rows),
                    "unique_2d_pedestrian_ids": len(ids2d),
                    "2d_3d_common_ids": sorted(ids2d & ids3d[frame]),
                    "near_3d_ids_also_in_2d": sorted(ids2d & near3d[frame]),
                    "near_3d_ids_total_across_all_views": len(near3d[frame]),
                })
            views.append(structure)
    print(json.dumps({"sequence": SEQUENCE, "role": "development_only",
                      "status": "schema_only", "archive_directory": directory,
                      "frames": args.frames, "views": views,
                      "interpretation": (
                          "JRDB-Act files may reuse pedestrian boxes and track IDs, but the "
                          "actual schema and coverage must be checked before any comparison. "
                          "Same-frame ID overlap is not reprojection accuracy or visibility, "
                          "and these labels must never enter online inference.")}, indent=2))


if __name__ == "__main__":
    main()
