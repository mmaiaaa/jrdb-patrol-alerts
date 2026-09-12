#!/usr/bin/env python3
"""Inspect JRDB ZIP metadata without extracting dataset content."""
import json
import shutil
import sys
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath


def inspect(archive_path):
    path = Path(archive_path).expanduser()
    if not path.is_file():
        raise ValueError(f"Missing file: {path}")

    first = Counter()
    two = Counter()
    extensions = Counter()
    samples = {
        key: [] for key in
        ("camera", "pointcloud", "calibration", "labels", "timing")
    }
    unsafe = []
    count = total = 0
    terms = {
        "camera": ("image", "camera", "rgb", "stitched"),
        "pointcloud": ("pointcloud", "lidar", "velodyne"),
        "calibration": ("calib", "intrinsic", "extrinsic"),
        "labels": ("label", "annot", "3d", "2d"),
        "timing": ("timestamp", "time_sync", "sync"),
    }

    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue

            name = item.filename.replace("\\", "/")
            parts = PurePosixPath(name).parts
            if name.startswith("/") or ".." in parts or (
                parts and parts[0].endswith(":")
            ):
                if len(unsafe) < 5:
                    unsafe.append(name)

            count += 1
            total += item.file_size
            first[parts[0] if parts else ""] += 1
            two["/".join(parts[:2])] += 1
            extensions[PurePosixPath(name).suffix.lower()] += 1

            lowered = name.lower()
            for key, words in terms.items():
                if any(word in lowered for word in words):
                    if len(samples[key]) < 4:
                        samples[key].append(name)

    return {
        "archive": path.name,
        "compressed_bytes": path.stat().st_size,
        "uncompressed_bytes": total,
        "file_count": count,
        "top_level": first.most_common(10),
        "first_two_levels": two.most_common(15),
        "extensions": extensions.most_common(12),
        "path_examples": samples,
        "unsafe_path_examples": unsafe,
        "note": "Metadata inventory only; no full CRC or sensor alignment check.",
    }


def main():
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: python scripts/audit_jrdb_archives.py ARCHIVE.zip [...]"
        )

    records = [inspect(name) for name in sys.argv[1:]]
    report = {
        "archives": records,
        "uncompressed_total_bytes": sum(
            item["uncompressed_bytes"] for item in records
        ),
        "home_free_bytes": shutil.disk_usage(Path.home()).free,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
