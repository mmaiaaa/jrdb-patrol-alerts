#!/usr/bin/env python3
"""Extract one JRDB train sequence with a metadata preflight."""
import argparse
import json
import shutil
import stat
import tempfile
import zipfile
from contextlib import ExitStack
from pathlib import Path, PurePosixPath


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--extract", action="store_true", help="Write selected files after preflight")
    args = parser.parse_args()
    seq = args.sequence
    if seq in ("", ".", "..") or "/" in seq or "\\" in seq:
        parser.error("Sequence must be a single JRDB sequence name")

    names = {
        "image": "train_images.zip",
        "cloud": "train_pointclouds.zip",
        "calibration": "train_calibration.zip",
        "label": "labels.zip",
    }
    with ExitStack() as stack:
        archives = {
            key: stack.enter_context(zipfile.ZipFile(args.downloads / filename))
            for key, filename in names.items()
        }
        prefixes = {
            "image": f"images/image_0/{seq}/",
            "upper": f"pointclouds/upper_velodyne/{seq}/",
            "lower": f"pointclouds/lower_velodyne/{seq}/",
        }
        selected = {}
        for stream, prefix in prefixes.items():
            archive = archives["image" if stream == "image" else "cloud"]
            extension = ".jpg" if stream == "image" else ".pcd"
            selected[stream] = sorted(
                (item for item in archive.infolist()
                 if item.filename.startswith(prefix) and item.filename.endswith(extension)),
                key=lambda item: item.filename,
            )
        labels = [item for item in archives["label"].infolist()
                  if item.filename == f"labels/labels_3d/{seq}.json"]
        calibration = [item for item in archives["calibration"].infolist()
                       if item.filename in (
                           "calibration/cameras.yaml", "calibration/lidars.yaml",
                           "calibration/defaults.yaml")]
        frames = {key: {Path(item.filename).stem for item in items}
                  for key, items in selected.items()}
        common = set.intersection(*frames.values())
        report = {
            "release": "JRDB 2022 train download (operator reported)",
            "sequence": seq,
            "camera_view": "image_0",
            "frame_counts": {key: len(items) for key, items in selected.items()},
            "common_filename_frame_ids": len(common),
            "label_3d": labels[0].filename if len(labels) == 1 else None,
            "calibration_files": [item.filename for item in calibration],
            "selected_uncompressed_bytes": sum(item.file_size for items in selected.values()
                                               for item in items)
            + sum(item.file_size for item in labels + calibration),
            "note": "Shared filename IDs do not establish timestamp or 3D projection accuracy.",
        }
        print(json.dumps(report, indent=2))
        if any(not items for items in selected.values()) or len(labels) != 1 or len(calibration) != 3 or not common:
            raise SystemExit("Missing sequence stream, 3D label, calibration, or common frame ID; inspect archive paths.")
        if not args.extract:
            return

        root = Path.cwd() / "data/jrdb2022/pilot"
        output = root / seq
        manifest = Path.cwd() / "manifests/pilot_selection.json"
        if output.exists() or manifest.exists():
            raise SystemExit("Pilot or manifest already exists; inspect before retrying.")
        root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(root).free < report["selected_uncompressed_bytes"] + 2_000_000_000:
            raise SystemExit("Less than pilot size + 2 GB of free space.")
        contents = [(archives["image"], item) for item in selected["image"]]
        contents += [(archives["cloud"], item)
                     for key in ("upper", "lower") for item in selected[key]]
        contents += [(archives["calibration"], item) for item in calibration]
        contents += [(archives["label"], item) for item in labels]
        paths_seen = set()
        for _, item in contents:
            raw = item.filename
            path = PurePosixPath(raw)
            if (not path.parts or path.is_absolute() or ".." in path.parts or
                    "\\" in raw or stat.S_ISLNK(item.external_attr >> 16) or raw in paths_seen):
                raise SystemExit(f"Unsafe or duplicated ZIP member: {raw}")
            paths_seen.add(raw)
        with tempfile.TemporaryDirectory(prefix=".pilot-stage-", dir=root) as temp:
            stage = Path(temp)
            for archive, item in contents:
                destination = stage.joinpath(*PurePosixPath(item.filename).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, destination.open("xb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
            stage.rename(output)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open("x", encoding="utf-8") as target:
            json.dump(report, target, indent=2)
            target.write("\n")
        print(f"Extracted to {output}; wrote {manifest}. ZIP CRC checked on extracted entries.")


if __name__ == "__main__":
    main()
