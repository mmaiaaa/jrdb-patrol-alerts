#!/usr/bin/env python3
"""List exploratory contiguous 3D person-proximity runs; not evaluated events."""
import argparse
import csv
import json
import math
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path


FIELDS = (
    "sequence", "person_id", "start_frame", "end_frame", "frame_count",
    "minimum_box_center_xy_m", "maximum_box_center_xy_m",
    "frames_with_positive_lidar_points", "frames_marked_interpolated",
    "frames_with_same_frame_stitched_pose_id",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/pilot_selection.json"))
    parser.add_argument("--pilot-root", type=Path, default=Path("data/jrdb2022/pilot"))
    parser.add_argument("--labels-zip", type=Path, default=Path.home() / "Downloads/labels.zip")
    parser.add_argument("--radius-m", type=float, default=3.0)
    parser.add_argument("--csv", type=Path, default=Path("outputs/local/pilot_candidate_runs.csv"))
    args = parser.parse_args()
    if not math.isfinite(args.radius_m) or args.radius_m <= 0:
        parser.error("--radius-m must be positive and finite")

    manifest = json.loads(args.manifest.read_text())
    sequence = manifest["sequence"]
    path = args.pilot_root / sequence / manifest["label_3d"]
    frames = json.loads(path.read_text())["labels"]
    per_person = defaultdict(list)
    seen = set()
    for frame_name, annotations in sorted(frames.items()):
        stem = Path(frame_name).stem
        if not stem.isdecimal():
            raise ValueError(f"Non-numeric 3D frame identifier: {frame_name}")
        number = int(stem)
        for item in annotations:
            person = str(item.get("label_id", ""))
            if not person.startswith("pedestrian:"):
                continue
            attributes = item.get("attributes") or {}
            if attributes.get("no_eval") is not False:
                continue
            box = item.get("box") or {}
            try:
                x, y = float(box["cx"]), float(box["cy"])
            except (KeyError, ValueError, TypeError):
                continue
            if not math.isfinite(x) or not math.isfinite(y):
                continue
            radius = math.hypot(x, y)
            if radius > args.radius_m:
                continue
            key = (stem, person)
            if key in seen:
                raise ValueError(f"Duplicate pedestrian ID {person} in frame {stem}")
            seen.add(key)
            per_person[person].append({
                "number": number, "frame": stem, "radius": radius,
                "positive_points": isinstance(attributes.get("num_points"), (int, float)) and attributes["num_points"] > 0,
                "interpolated": attributes.get("interpolated") is True,
            })

    with zipfile.ZipFile(args.labels_zip) as archive:
        matches = [name for name in archive.namelist() if name.startswith(
            "labels/labels_2d_pose_stitched_coco/"
        ) and Path(name).name.startswith(sequence) and name.endswith(".json")]
        if len(matches) != 1:
            raise ValueError(f"Expected one stitched pose file for {sequence}; got {matches}")
        pose = json.loads(archive.read(matches[0]))
    frame_by_id = {row["id"]: Path(row["file_name"]).stem for row in pose["images"]}
    pose_pairs = {(frame_by_id[item["image_id"]], str(item["track_id"]))
                  for item in pose["annotations"]
                  if item.get("image_id") in frame_by_id and item.get("track_id") is not None}

    runs = []
    for person, entries in sorted(per_person.items()):
        current = []
        for entry in sorted(entries, key=lambda row: row["number"]):
            if current and entry["number"] != current[-1]["number"] + 1:
                runs.append((person, current))
                current = []
            current.append(entry)
        if current:
            runs.append((person, current))

    rows = []
    for person, items in sorted(runs, key=lambda pair: (pair[1][0]["number"], pair[0])):
        radii = [item["radius"] for item in items]
        rows.append({
            "sequence": sequence,
            "person_id": person,
            "start_frame": items[0]["frame"],
            "end_frame": items[-1]["frame"],
            "frame_count": len(items),
            "minimum_box_center_xy_m": f"{min(radii):.4f}",
            "maximum_box_center_xy_m": f"{max(radii):.4f}",
            "frames_with_positive_lidar_points": sum(item["positive_points"] for item in items),
            "frames_marked_interpolated": sum(item["interpolated"] for item in items),
            "frames_with_same_frame_stitched_pose_id": sum(
                (item["frame"], person.partition(":")[2]) in pose_pairs for item in items
            ),
        })

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    lengths = [int(row["frame_count"]) for row in rows]
    summary = {
        "sequence": sequence,
        "radius_m": args.radius_m,
        "radius_role": "Exploratory candidate generation; not a frozen alert threshold",
        "candidate_contiguous_runs": len(rows),
        "persons_with_at_least_one_run": len(per_person),
        "eligible_person_frame_observations": sum(lengths),
        "run_length_frames_min_median_max": [min(lengths), statistics.median(lengths), max(lengths)] if lengths else None,
        "candidate_runs_csv": str(args.csv),
        "cautions": [
            "Frame IDs are ordered integers; this script does not establish timestamps or seconds.",
            "Consecutive within-radius labels form candidate runs, not verified independently annotated encounters.",
            "All included labels can be interpolated; inspect onset/offset frames manually.",
            "Stitched pose match is supportive only; absence does not mean a person is invisible.",
            "This stationary recording is a pilot and cannot establish moving-patrol performance.",
        ],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
