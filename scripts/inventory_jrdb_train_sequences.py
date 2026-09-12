#!/usr/bin/env python3
"""Inventory all available JRDB train sequences using ZIP metadata only."""
import argparse
import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


FIELDS = (
    "sequence_id", "location_group", "frames_stitched", "frames_camera_0",
    "frames_upper_lidar", "frames_lower_lidar", "all_four_frame_id_sets_match",
    "first_common_frame", "last_common_frame", "source_motion_status",
    "motion_status_source", "3d_label_zip_member",
)
PAPER = "https://arxiv.org/html/1910.11792v4"
SOURCE_STATUS = {
    "bytes-cafe-2019-02-07_0": "stationary",
    "cubberly-auditorium-2019-04-22_0": "moving",
    "memorial-court-2019-03-16_0": "moving",
    "huang-lane-2019-02-12_0": "stationary",
}


def location_group(sequence):
    match = re.fullmatch(r"(.+)-\d{4}-\d{2}-\d{2}_\d+", sequence)
    return match.group(1) if match else "unparsed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--csv", type=Path, default=Path("outputs/local/jrdb_train_sequence_inventory.csv"))
    args = parser.parse_args()

    streams = defaultdict(lambda: defaultdict(set))
    archive_paths = (
        ("stitched", args.downloads / "train_images.zip", "images/image_stitched/", ".jpg"),
        ("camera_0", args.downloads / "train_images.zip", "images/image_0/", ".jpg"),
        ("upper_lidar", args.downloads / "train_pointclouds.zip", "pointclouds/upper_velodyne/", ".pcd"),
        ("lower_lidar", args.downloads / "train_pointclouds.zip", "pointclouds/lower_velodyne/", ".pcd"),
    )
    for archive_path in sorted({entry[1] for entry in archive_paths}):
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.namelist():
                for stream, path, prefix, extension in archive_paths:
                    if path != archive_path or not member.startswith(prefix) or not member.endswith(extension):
                        continue
                    remaining = member[len(prefix):]
                    parts = remaining.split("/")
                    if len(parts) == 2 and parts[0] and parts[1]:
                        streams[parts[0]][stream].add(Path(parts[1]).stem)

    with zipfile.ZipFile(args.downloads / "labels.zip") as archive:
        labels = {}
        for member in archive.namelist():
            if member.startswith("labels/labels_3d/") and member.endswith(".json"):
                sequence = Path(member).stem
                if sequence in labels:
                    raise ValueError(f"Duplicate 3D label for {sequence}")
                labels[sequence] = member

    all_sequences = sorted(set(streams) | set(labels))
    rows = []
    for sequence in all_sequences:
        sets = [streams[sequence][name] for name in ("stitched", "camera_0", "upper_lidar", "lower_lidar")]
        common = set.intersection(*sets)
        same = all(sets[0] == other for other in sets[1:]) and bool(sets[0])
        status = SOURCE_STATUS.get(sequence, "unverified")
        rows.append({
            "sequence_id": sequence,
            "location_group": location_group(sequence),
            "frames_stitched": len(sets[0]),
            "frames_camera_0": len(sets[1]),
            "frames_upper_lidar": len(sets[2]),
            "frames_lower_lidar": len(sets[3]),
            "all_four_frame_id_sets_match": str(same).lower(),
            "first_common_frame": min(common) if common else "",
            "last_common_frame": max(common) if common else "",
            "source_motion_status": status,
            "motion_status_source": PAPER + " (Figure 2)" if status != "unverified" else "",
            "3d_label_zip_member": labels.get(sequence, ""),
        })

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    groups = Counter(row["location_group"] for row in rows)
    print(json.dumps({
        "train_sequences_with_any_data": len(rows),
        "sequences_with_3d_label_json": len(labels),
        "sequences_with_matching_four_stream_frame_ids": sum(
            row["all_four_frame_id_sets_match"] == "true" for row in rows
        ),
        "source_verified_motion_examples_present": {
            key: SOURCE_STATUS[key] for key in SOURCE_STATUS if key in all_sequences
        },
        "location_groups": dict(sorted(groups.items())),
        "csv": str(args.csv),
        "limitations": [
            "ZIP central-directory inventory; this does not read image pixels, point-cloud payloads, or label content.",
            "Motion labels are set only for four scenes explicitly named in the original JRDB paper.",
            "Location prefix is a proposed conservative grouping, not a verified independent session ID.",
            "No development/validation/final-test allocation is made from these counts.",
            "Matching filenames do not prove image-LiDAR timestamp or coordinate alignment.",
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
