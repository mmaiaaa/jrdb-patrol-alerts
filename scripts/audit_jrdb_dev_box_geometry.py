#!/usr/bin/env python3
"""Development-only 3D label/upper-cloud geometry diagnostic; no range estimator.

Run from the repository root. This tool reads 3D labels solely for offline audit.
It compares two *hypotheses*, not identified coordinate conventions or GT scores.
"""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from audit_jrdb_cubberly_projection import read_xyz


DEFAULT_FRAMES = ("000087", "000432", "000864", "001295")
FIELDS = ("frame", "label_id", "center_xy_radius_m", "reported_num_points",
          "no_eval", "interpolated", "upper_points_in_box_if_label_upper",
          "upper_points_in_box_if_label_ego", "box_cx", "box_cy", "box_cz",
          "box_length", "box_width", "box_height", "box_rot_z")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def upper_to_ego(points, matrix):
    transform = np.asarray(matrix, dtype=np.float64)
    if transform.shape != (4, 4) or not np.isfinite(transform).all():
        raise ValueError("upper2ego must be a finite 4x4 matrix")
    if (not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-5) or
            not np.allclose(transform[:3, :3].T @ transform[:3, :3], np.eye(3), atol=0.05) or
            abs(np.linalg.det(transform[:3, :3]) - 1) > 0.05):
        raise ValueError("upper2ego is not approximately rigid")
    return points @ transform[:3, :3].T + transform[:3, 3]


def count_points_in_box(points, box):
    """Assume center-anchored, yaw-oriented box with x length and y width."""
    vals = [float(box[name]) for name in ("cx", "cy", "cz", "l", "w", "h", "rot_z")]
    cx, cy, cz, length, width, height, yaw = vals
    if not all(map(math.isfinite, vals)) or min(length, width, height) <= 0:
        raise ValueError("Invalid box coordinates or dimensions")
    dx, dy, dz = points[:, 0] - cx, points[:, 1] - cy, points[:, 2] - cz
    c, s = math.cos(yaw), math.sin(yaw)
    xlocal, ylocal = c * dx + s * dy, -s * dx + c * dy
    return int(np.count_nonzero((abs(xlocal) <= length / 2) &
                                (abs(ylocal) <= width / 2) &
                                (abs(dz) <= height / 2)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--frames", nargs="+", default=DEFAULT_FRAMES)
    parser.add_argument("--csv", type=Path, default=Path("outputs/local/cubberly_dev_box_geometry.csv"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only":
        parser.error("Only an explicitly development-only manifest may be inspected")
    sequence = manifest["sequence"]
    root = args.data_root / sequence
    label_path = root / manifest["label_3d"]
    calibration_path = root / "calibration/lidars.yaml"
    labels = json.loads(label_path.read_text())["labels"]
    transform = yaml.safe_load(calibration_path.read_text())["lidar"]["upper2ego"]
    if len(args.frames) != len(set(args.frames)) or not args.frames or any(
            not stem.isdecimal() or len(stem) != 6 for stem in args.frames):
        parser.error("Give distinct six-digit numeric frame IDs")

    rows = []
    skipped = Counter()
    counts_by_frame = {}
    for frame in args.frames:
        key = frame + ".pcd"
        if key not in labels:
            raise ValueError(f"Label frame is absent: {key}")
        cloud_path = root / "pointclouds/upper_velodyne" / sequence / key
        header, points = read_xyz(cloud_path)
        finite = points[np.isfinite(points).all(axis=1)]
        ego = upper_to_ego(finite, transform)
        counts_by_frame[frame] = {"upper_pcd_mode": header["DATA"],
                                  "points_declared": int(header["POINTS"]),
                                  "finite_upper_points": len(finite)}
        seen = set()
        for item in labels[key]:
            person = str(item.get("label_id", ""))
            if not person.startswith("pedestrian:"):
                continue
            if person in seen:
                raise ValueError(f"Duplicate label ID {person} in {key}")
            seen.add(person)
            box = item.get("box") or {}
            attrs = item.get("attributes") or {}
            try:
                count_upper = count_points_in_box(finite, box)
                count_ego = count_points_in_box(ego, box)
            except (KeyError, ValueError, TypeError, OverflowError):
                skipped["invalid_box"] += 1
                continue
            rows.append({"frame": frame, "label_id": person,
                         "center_xy_radius_m": round(math.hypot(float(box["cx"]), float(box["cy"])), 4),
                         "reported_num_points": attrs.get("num_points"),
                         "no_eval": attrs.get("no_eval"),
                         "interpolated": attrs.get("interpolated"),
                         "upper_points_in_box_if_label_upper": count_upper,
                         "upper_points_in_box_if_label_ego": count_ego,
                         "box_cx": box["cx"], "box_cy": box["cy"],
                         "box_cz": box["cz"], "box_length": box["l"],
                         "box_width": box["w"], "box_height": box["h"],
                         "box_rot_z": box["rot_z"]})
    if not rows:
        raise ValueError("No valid pedestrian boxes in selected development frames")
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    near = [row for row in rows if row["center_xy_radius_m"] <= 3.0 and row["no_eval"] is False]
    report = {"sequence": sequence, "role": "development_only", "frames": list(args.frames),
              "label_file_sha256": sha256(label_path), "calibration_sha256": sha256(calibration_path),
              "frame_clouds": counts_by_frame, "pedestrian_boxes_audited": len(rows),
              "invalid_boxes_skipped": dict(skipped), "evaluable_center_within_3m_boxes": len(near),
              "near_boxes_with_one_or_more_upper_points_if_label_upper": sum(
                  row["upper_points_in_box_if_label_upper"] > 0 for row in near),
              "near_boxes_with_one_or_more_upper_points_if_label_ego": sum(
                  row["upper_points_in_box_if_label_ego"] > 0 for row in near),
              "csv": str(args.csv), "interpretation": (
                  "Exploratory comparison of two coordinate hypotheses. Box occupancy is not "
                  "foreground association, person range, calibration validation, or detection "
                  "accuracy. Assumes label center is geometric center, l along local x, w along "
                  "local y, rot_z yaw. Only the upper LiDAR is counted; JRDB num_points might "
                  "count both sensors or follow other annotation rules. No labels may enter "
                  "the online inference pipeline. Matching frame IDs do not verify timing.")}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
