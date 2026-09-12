#!/usr/bin/env python3
"""Preflight and optionally extract one paper-verified moving JRDB development recording."""
import argparse
import json
import math
import shutil
import stat
import tempfile
import zipfile
from contextlib import ExitStack
from pathlib import Path, PurePosixPath


SEQUENCE = "cubberly-auditorium-2019-04-22_0"
STREAMS = {
    "image_stitched": ("images", f"images/image_stitched/{SEQUENCE}/", ".jpg"),
    "image_0": ("images", f"images/image_0/{SEQUENCE}/", ".jpg"),
    "upper_lidar": ("pointclouds", f"pointclouds/upper_velodyne/{SEQUENCE}/", ".pcd"),
    "lower_lidar": ("pointclouds", f"pointclouds/lower_velodyne/{SEQUENCE}/", ".pcd"),
}
CALIBRATION = {"calibration/cameras.yaml", "calibration/lidars.yaml", "calibration/defaults.yaml"}


def safe_member(member):
    raw = member.filename
    path = PurePosixPath(raw)
    return (bool(path.parts) and not path.is_absolute() and ".." not in path.parts
            and "\\" not in raw and not stat.S_ISLNK(member.external_attr >> 16))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--extract", action="store_true", help="Extract only after preflight")
    args = parser.parse_args()

    filenames = {
        "images": "train_images.zip", "pointclouds": "train_pointclouds.zip",
        "calibration": "train_calibration.zip", "labels": "labels.zip",
    }
    with ExitStack() as stack:
        archives = {key: stack.enter_context(zipfile.ZipFile(args.downloads / name))
                    for key, name in filenames.items()}
        selected = {}
        frame_sets = {}
        for stream, (archive_key, prefix, extension) in STREAMS.items():
            members = [m for m in archives[archive_key].infolist()
                       if m.filename.startswith(prefix) and m.filename.endswith(extension)]
            selected[stream] = (archive_key, members)
            frame_sets[stream] = {Path(m.filename).stem for m in members}
        labels3d = f"labels/labels_3d/{SEQUENCE}.json"
        pose = f"labels/labels_2d_pose_stitched_coco/{SEQUENCE}.json"
        selected["label_3d"] = ("labels", [m for m in archives["labels"].infolist() if m.filename == labels3d])
        selected["pose_stitched"] = ("labels", [m for m in archives["labels"].infolist() if m.filename == pose])
        selected["calibration"] = ("calibration", [m for m in archives["calibration"].infolist()
                                                   if m.filename in CALIBRATION])
        if (any(not frames for frames in frame_sets.values()) or
            not all(frame_sets["image_stitched"] == frames for frames in frame_sets.values()) or
            len(selected["label_3d"][1]) != 1 or len(selected["pose_stitched"][1]) != 1 or
            len(selected["calibration"][1]) != len(CALIBRATION)):
            raise SystemExit("Missing or mismatched streams, 3D label, stitched pose, or calibration")
        frames = sorted(frame_sets["image_stitched"])
        if not all(stem.isdecimal() for stem in frames):
            raise SystemExit("Non-numeric frame ID; inspect before deriving intervals")
        payload = json.loads(archives["labels"].read(labels3d))
        labels = payload["labels"]
        label_frames = {Path(name).stem for name in labels}
        if label_frames != set(frames):
            raise SystemExit("3D annotation frames differ from sensor filenames")
        near = set()
        no_eval_near = set()
        for frame_name, entries in labels.items():
            for item in entries:
                if not str(item.get("label_id", "")).startswith("pedestrian:"):
                    continue
                box = item.get("box") or {}
                try:
                    x, y = float(box["cx"]), float(box["cy"])
                except (ValueError, TypeError, KeyError):
                    continue
                if not (math.isfinite(x) and math.isfinite(y) and math.hypot(x, y) <= 3.0):
                    continue
                if (item.get("attributes") or {}).get("no_eval") is False:
                    near.add(Path(frame_name).stem)
                else:
                    no_eval_near.add(Path(frame_name).stem)

        contents = [(archives[key], member) for key, members in selected.values() for member in members]
        names = [member.filename for _, member in contents]
        if len(names) != len(set(names)) or not all(safe_member(member) for _, member in contents):
            raise SystemExit("Duplicate or unsafe selected ZIP member")
        output = args.data_root / SEQUENCE
        report = {
            "sequence": SEQUENCE,
            "role": "development_only",
            "moving_source": "https://arxiv.org/html/1910.11792v4 (Figure 2)",
            "frame_counts": {key: len(frames) for key, frames in frame_sets.items()},
            "label_3d": labels3d,
            "pose_stitched": pose,
            "all_frame_ids_match": True,
            "pilot_radius_m": 3.0,
            "frames_with_evaluable_3m_person": len(near),
            "frames_without_evaluable_3m_person": len(frames) - len(near),
            "frames_with_3m_person_marked_no_eval": len(no_eval_near),
            "uncompressed_selected_bytes": sum(m.file_size for _, m in contents),
            "output": str(output),
            "manifest": str(args.manifest),
            "extracted": False,
            "cautions": [
                "Candidate person-free frames are not independently verified negatives.",
                "This is a development recording only; no held-out recordings are inspected.",
                "Frame IDs do not establish timestamps or calibrated LiDAR/image projection.",
                "No images, labels or clouds should be added to Git.",
            ],
        }
        if args.extract:
            if output.exists() or args.manifest.exists():
                raise SystemExit("Destination or manifest exists; inspect before retrying")
            args.data_root.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(args.data_root).free < report["uncompressed_selected_bytes"] + 2_000_000_000:
                raise SystemExit("Insufficient free space for extracted files plus 2 GB margin")
            with tempfile.TemporaryDirectory(prefix=".jrdb-dev-stage-", dir=args.data_root) as temp:
                stage = Path(temp)
                for archive, member in contents:
                    destination = stage.joinpath(*PurePosixPath(member.filename).parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, destination.open("xb") as target:
                        shutil.copyfileobj(source, target, length=1024 * 1024)
                stage.rename(output)
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            report["extracted"] = True
            args.manifest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
