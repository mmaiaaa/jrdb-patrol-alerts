#!/usr/bin/env python3
"""Probe projected LiDAR radial-distance mixtures within development detector boxes.

No value produced here is a verified person distance or an alert. No GT is read.
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from audit_jrdb_cubberly_projection import project, read_xyz
from review_jrdb_native_detections import CAMERAS, HEIGHT, WIDTH, validate_row

SEQUENCE = "cubberly-auditorium-2019-04-22_0"
FRAMES = ("000087", "000432", "000864", "001295")
BIN_WIDTH_M = 0.5
MAX_BIN_M = 30.0
HEADERS = ("frame", "camera", "box_index", "box_confidence", "xyxy", "projected_image_points",
           "points_inside_full_box", "points_inside_inner_box", "inner_bin_width_m",
           "inner_nonempty_bins", "inner_bins_with_at_least_3_points", "inner_bins_counts_json",
           "inner_points_at_or_beyond_30m")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_boxes(path, frames):
    selected = {}
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            row = json.loads(line)
            validate_row(row)
            if row["frame"] not in frames:
                continue
            key = (row["frame"], row["camera"])
            if key in selected:
                raise ValueError(f"Duplicate selected frame/camera at line {line_number}: {key}")
            selected[key] = row["detections"]
    absent = [(frame, camera) for frame in frames for camera in CAMERAS
              if (frame, camera) not in selected]
    if absent:
        raise ValueError(f"Missing selected predictions: {absent[:5]}")
    return selected


def points_in_rect(uv, rectangle):
    left, top, right, bottom = rectangle
    return ((uv[:, 0] >= left) & (uv[:, 0] < right) &
            (uv[:, 1] >= top) & (uv[:, 1] < bottom))


def one_box(frame, camera, box_index, detection, uv, ranges):
    x1, y1, x2, y2 = detection["xyxy"]
    full = points_in_rect(uv, (x1, y1, x2, y2))
    width, height = x2 - x1, y2 - y1
    # Probe the center, reducing (but never eliminating) neighboring background returns.
    inner = points_in_rect(uv, (x1 + 0.2 * width, y1 + 0.2 * height,
                                 x2 - 0.2 * width, y2 - 0.15 * height))
    radial = ranges[inner]
    finite = radial[np.isfinite(radial) & (radial >= 0) & (radial < MAX_BIN_M)]
    bin_ids = np.floor(finite / BIN_WIDTH_M).astype(np.int32)
    counts = np.bincount(bin_ids, minlength=int(MAX_BIN_M / BIN_WIDTH_M))
    nonempty = [(round(i * BIN_WIDTH_M, 1), int(n)) for i, n in enumerate(counts) if n]
    return {"frame": frame, "camera": camera, "box_index": box_index,
            "box_confidence": round(detection["confidence"], 4),
            "xyxy": json.dumps([round(v, 2) for v in detection["xyxy"]]),
            "projected_image_points": len(uv),
            "points_inside_full_box": int(full.sum()),
            "points_inside_inner_box": int(inner.sum()),
            "inner_bin_width_m": BIN_WIDTH_M,
            "inner_nonempty_bins": len(nonempty),
            "inner_bins_with_at_least_3_points": int((counts >= 3).sum()),
            "inner_bins_counts_json": json.dumps(nonempty, separators=(",", ":")),
            "inner_points_at_or_beyond_30m": int((radial >= MAX_BIN_M).sum())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--predictions", type=Path, default=Path("outputs/local/cubberly_native_full.jsonl"))
    parser.add_argument("--frames", nargs="+", default=list(FRAMES))
    parser.add_argument("--output", type=Path, default=Path("outputs/local/cubberly_box_depth_support.csv"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only" or manifest.get("sequence") != SEQUENCE:
        parser.error("Expected the Cubberly development-only manifest")
    if any(len(frame) != 6 or not frame.isdecimal() for frame in args.frames) or len(set(args.frames)) != len(args.frames):
        parser.error("--frames requires unique six-digit frame IDs")
    if args.output.exists():
        parser.error(f"Output exists and will not be replaced: {args.output}")
    root = args.data_root / SEQUENCE
    cal_path = root / "calibration/lidars.yaml"
    calibration = yaml.safe_load(cal_path.read_text())
    if any(f"sensor_{camera}" not in calibration for camera in CAMERAS):
        raise ValueError("Expected all five native camera calibrations")
    selected = load_boxes(args.predictions, args.frames)
    rows = []
    for frame in args.frames:
        cloud_path = root / "pointclouds/upper_velodyne" / SEQUENCE / f"{frame}.pcd"
        _, xyz = read_xyz(cloud_path)
        for camera in CAMERAS:
            uv, ranges, _ = project(xyz, calibration[f"sensor_{camera}"], (WIDTH, HEIGHT))
            for box_index, detection in enumerate(selected[(frame, camera)]):
                rows.append(one_box(frame, camera, box_index, detection, uv, ranges))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"sequence": SEQUENCE, "role": "development_only",
                      "frames": args.frames, "cameras": list(CAMERAS), "boxes_checked": len(rows),
                      "boxes_by_camera": dict(sorted(Counter(str(row["camera"]) for row in rows).items())),
                      "boxes_with_zero_projected_points_in_inner_box": sum(
                          row["points_inside_inner_box"] == 0 for row in rows),
                      "boxes_with_two_or_more_inner_bins_each_with_three_points": sum(
                          row["inner_bins_with_at_least_3_points"] >= 2 for row in rows),
                      "csv": str(args.output), "predictions_sha256": sha256_file(args.predictions),
                      "calibration_sha256": sha256_file(cal_path),
                      "interpretation": "The 0.5m bins are upper-LiDAR XY radii of returns projected into each box's center, not person distances or validated foreground points. Zero support can mean occlusion, sparsity or misalignment; multiple bins can reflect person thickness, other people or background. No GT, timestamp, range estimate or alert is produced."}, indent=2))


if __name__ == "__main__":
    main()
