#!/usr/bin/env python3
"""Stage the paper-verified moving Memorial Court sensor streams without labels.

Preflight reads ZIP directory metadata only. Even --extract never opens a label
archive. Analysis settings and the eventual final reference remain separate.
"""

import argparse
import json
import shutil
import stat
import tempfile
import zipfile
from contextlib import ExitStack
from pathlib import Path, PurePosixPath


SEQUENCE = "memorial-court-2019-03-16_0"
STREAMS = {
    "image_stitched": ("images", "images/image_stitched", ".jpg"),
    "image_0": ("images", "images/image_0", ".jpg"),
    "image_2": ("images", "images/image_2", ".jpg"),
    "image_4": ("images", "images/image_4", ".jpg"),
    "image_6": ("images", "images/image_6", ".jpg"),
    "image_8": ("images", "images/image_8", ".jpg"),
    "upper_lidar": ("pointclouds", "pointclouds/upper_velodyne", ".pcd"),
    "lower_lidar": ("pointclouds", "pointclouds/lower_velodyne", ".pcd"),
}
CALIBRATION = ("calibration/cameras.yaml", "calibration/lidars.yaml",
               "calibration/defaults.yaml")


def safe(member):
    raw = member.filename
    parts = PurePosixPath(raw)
    return (not parts.is_absolute() and bool(parts.parts) and
            ".." not in parts.parts and "\\" not in raw and
            not stat.S_ISLNK(member.external_attr >> 16) and not member.is_dir())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--data-root", type=Path,
                        default=Path("data/jrdb2022/holdout_sensors"))
    parser.add_argument("--manifest", type=Path,
                        default=Path("manifests/holdout_memorial_sensor_only.json"))
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()
    destination = args.data_root / SEQUENCE
    if args.extract and (destination.exists() or args.manifest.exists()):
        parser.error("Destination or manifest already exists; refusing overwrite")

    with ExitStack() as stack:
        archive_names = {"images": "train_images.zip",
                         "pointclouds": "train_pointclouds.zip",
                         "calibration": "train_calibration.zip"}
        archives = {name: stack.enter_context(zipfile.ZipFile(args.downloads / filename))
                    for name, filename in archive_names.items()}
        selected = []
        frame_sets = {}
        for stream, (archive_key, base, extension) in STREAMS.items():
            prefix = f"{base}/{SEQUENCE}/"
            members = [m for m in archives[archive_key].infolist()
                       if m.filename.startswith(prefix) and
                       m.filename.endswith(extension)]
            frames = [m.filename[len(prefix):-len(extension)] for m in members]
            if (not frames or len(set(frames)) != len(frames) or
                    any(len(f) != 6 or not f.isdecimal() for f in frames)):
                parser.error(f"Incomplete or duplicate six-digit frame IDs: {stream}")
            frame_sets[stream] = set(frames)
            selected.extend((archive_key, m) for m in members)
        if any(ids != frame_sets["image_0"] for ids in frame_sets.values()):
            parser.error("Image and upper/lower LiDAR frame IDs differ")
        cal = archives["calibration"]
        cal_members = [m for m in cal.infolist() if m.filename in CALIBRATION]
        if (len(cal_members) != len(CALIBRATION) or
                {m.filename for m in cal_members} != set(CALIBRATION)):
            parser.error("Expected three unique calibration YAML members")
        selected.extend(("calibration", m) for m in cal_members)
        names = [m.filename for _, m in selected]
        if len(names) != len(set(names)) or any(not safe(m) for _, m in selected):
            parser.error("Unsafe or duplicate selected ZIP member")
        frame_ids = sorted(frame_sets["image_0"])
        report = {
            "sequence": SEQUENCE,
            "role": "holdout_sensor_only_unscored",
            "motion_source": "https://arxiv.org/html/1910.11792v4 (Figure 2d)",
            "archives": archive_names,
            "frame_counts": {name: len(frames) for name, frames in frame_sets.items()},
            "first_last_frame": [frame_ids[0], frame_ids[-1]],
            "all_sensor_frame_ids_match": True,
            "uncompressed_selected_bytes": sum(m.file_size for _, m in selected),
            "output": str(destination), "manifest": str(args.manifest),
            "extracted": False,
            "reference_archive_opened": False,
            "reference_annotations_inspected": False,
            "notes": [
                "No 2D or 3D labels are opened, extracted, counted or scored.",
                "Only preparation; final protocol must be frozen before inference/evaluation.",
                "This outdoor scene tests a different location and environment.",
                "Matching frame IDs do not establish acquisition-time synchronization.",
                "Source bytes must stay outside Git.",
            ],
        }
        if args.extract:
            args.data_root.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(args.data_root).free < (report["uncompressed_selected_bytes"]
                                                        + 2_000_000_000):
                parser.error("Need selected uncompressed bytes plus 2 GB free")
            with tempfile.TemporaryDirectory(prefix=".jrdb-heldout-stage-",
                                             dir=args.data_root) as temp:
                stage = Path(temp)
                for key, member in selected:
                    path = stage.joinpath(*PurePosixPath(member.filename).parts)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with archives[key].open(member) as source, path.open("xb") as target:
                        shutil.copyfileobj(source, target, length=1024*1024)
                stage.rename(destination)
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            report["extracted"] = True
            args.manifest.write_text(json.dumps(report, indent=2) + "\n",
                                     encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
