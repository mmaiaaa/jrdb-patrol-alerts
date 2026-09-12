#!/usr/bin/env python3
"""Inspect JRDB 3D interpolation flags and available camera-0 2D pose metadata."""
import argparse
import json
import math
import zipfile
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/pilot_selection.json"))
    parser.add_argument("--pilot-root", type=Path, default=Path("data/jrdb2022/pilot"))
    parser.add_argument("--labels-zip", type=Path, default=Path.home() / "Downloads/labels.zip")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    sequence = manifest["sequence"]
    frames = json.loads((args.pilot_root / sequence / manifest["label_3d"]).read_text())["labels"]
    raw = Counter()
    near = Counter()
    examples = []
    for filename, entries in sorted(frames.items()):
        for entry in entries:
            if not str(entry.get("label_id", "")).startswith("pedestrian:"):
                continue
            interpolated = (entry.get("attributes") or {}).get("interpolated")
            raw[str(interpolated)] += 1
            box = entry.get("box") or {}
            try:
                distance = math.hypot(float(box["cx"]), float(box["cy"]))
            except (ValueError, TypeError, KeyError):
                distance = None
            if distance is not None and distance <= 3.0:
                near[str(interpolated)] += 1
            if interpolated is False and len(examples) < 20:
                examples.append({"frame": filename, "id": entry.get("label_id"), "distance_xy_m": distance})

    with zipfile.ZipFile(args.labels_zip) as archive:
        matches = [name for name in archive.namelist() if name.startswith(
            "labels/labels_2d_pose_coco/"
        ) and name.endswith(f"{sequence}_image0.json")]
        if len(matches) != 1:
            raise ValueError(f"Expected one camera-0 pose file for {sequence}; found {matches}")
        pose = json.loads(archive.read(matches[0]))

    report = {
        "sequence": sequence,
        "interpolated_flag_all_pedestrian_observations": dict(raw),
        "interpolated_flag_within_3m": dict(near),
        "first_noninterpolated_examples": examples,
        "camera_0_pose_member": matches[0],
        "pose_top_level_keys": sorted(pose.keys()),
    }
    for key in ("images", "annotations", "categories"):
        value = pose.get(key)
        report[f"pose_{key}_count"] = len(value) if isinstance(value, (list, dict)) else None
        first = value[0] if isinstance(value, list) and value else None
        report[f"pose_first_{key}_example"] = (
            {k: v for k, v in first.items() if k != "keypoints"}
            if isinstance(first, dict) else None
        )
    annotations = pose.get("annotations")
    if isinstance(annotations, list):
        report["pose_annotations_by_category_id"] = dict(Counter(
            str(item.get("category_id")) for item in annotations if isinstance(item, dict)
        ))
    report["note"] = (
        "This inspects a camera-0 pose file but does not establish complete person visibility, "
        "3D-to-2D identity matching, or independent encounter ground truth."
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
