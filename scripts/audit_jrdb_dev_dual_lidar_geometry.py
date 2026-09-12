#!/usr/bin/env python3
"""Offline JRDB development audit: upper + lower returns inside annotated 3D boxes.

Reuses the previous development box-geometry helpers. This diagnostic reads GT
only offline and makes no automatic choice of annotation coordinate frame.
"""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from audit_jrdb_cubberly_projection import read_xyz
from audit_jrdb_dev_box_geometry import count_points_in_box, sha256, upper_to_ego


DEFAULT_FRAMES = ("000087", "000432", "000864", "001295")
FIELDS = ("frame", "label_id", "center_xy_radius_m", "reported_num_points", "no_eval",
          "interpolated", "upper_if_label_upper", "lower_if_label_upper",
          "combined_if_label_upper", "upper_if_label_ego", "lower_if_label_ego",
          "combined_if_label_ego")


def finite_xyz(path):
    header, xyz = read_xyz(path)
    if xyz.ndim != 2 or xyz.shape[1] != 3:
        raise ValueError(f"Unexpected x/y/z shape in {path}")
    return header, xyz[np.isfinite(xyz).all(axis=1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--frames", nargs="+", default=DEFAULT_FRAMES)
    parser.add_argument("--csv", type=Path,
                        default=Path("outputs/local/cubberly_dev_dual_lidar_geometry.csv"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only":
        parser.error("Only an explicitly development-only manifest may be inspected")
    if not args.frames or len(args.frames) != len(set(args.frames)) or any(
            not f.isdecimal() or len(f) != 6 for f in args.frames):
        parser.error("Provide distinct six-digit numeric frame IDs")
    sequence = manifest["sequence"]
    root = args.data_root / sequence
    label_path = root / manifest["label_3d"]
    calibration_path = root / "calibration/lidars.yaml"
    labels = json.loads(label_path.read_text())["labels"]
    calibration = yaml.safe_load(calibration_path.read_text())["lidar"]
    lower2upper = calibration["lower2upper"]
    upper2ego = calibration["upper2ego"]
    rows = []
    frame_clouds = {}
    skipped = Counter()
    for frame in args.frames:
        filename = frame + ".pcd"
        if filename not in labels:
            raise ValueError(f"Missing 3D labels for frame {frame}")
        upper_path = root / "pointclouds/upper_velodyne" / sequence / filename
        lower_path = root / "pointclouds/lower_velodyne" / sequence / filename
        upper_header, upper = finite_xyz(upper_path)
        lower_header, lower_native = finite_xyz(lower_path)
        # The helper applies any approximately rigid 4x4 matrix to xyz; first
        # move lower points to upper, then move both sets to the ego hypothesis.
        lower_upper = upper_to_ego(lower_native, lower2upper)
        upper_ego = upper_to_ego(upper, upper2ego)
        lower_ego = upper_to_ego(lower_upper, upper2ego)
        frame_clouds[frame] = {
            "upper_points_declared": int(upper_header["POINTS"]),
            "lower_points_declared": int(lower_header["POINTS"]),
            "finite_upper_points": len(upper), "finite_lower_points": len(lower_native),
        }
        seen_ids = set()
        for item in labels[filename]:
            person = str(item.get("label_id", ""))
            if not person.startswith("pedestrian:"):
                continue
            if person in seen_ids:
                raise ValueError(f"Duplicate label {person} in frame {frame}")
            seen_ids.add(person)
            box = item.get("box") or {}
            attrs = item.get("attributes") or {}
            try:
                count_uu = count_points_in_box(upper, box)
                count_lu = count_points_in_box(lower_upper, box)
                count_ue = count_points_in_box(upper_ego, box)
                count_le = count_points_in_box(lower_ego, box)
                radius = math.hypot(float(box["cx"]), float(box["cy"]))
            except (KeyError, ValueError, TypeError, OverflowError):
                skipped["invalid_box"] += 1
                continue
            row = {"frame": frame, "label_id": person,
                   "center_xy_radius_m": round(radius, 4),
                   "reported_num_points": attrs.get("num_points"),
                   "no_eval": attrs.get("no_eval"), "interpolated": attrs.get("interpolated"),
                   "upper_if_label_upper": count_uu, "lower_if_label_upper": count_lu,
                   "combined_if_label_upper": count_uu + count_lu,
                   "upper_if_label_ego": count_ue, "lower_if_label_ego": count_le,
                   "combined_if_label_ego": count_ue + count_le}
            rows.append(row)
    if not rows:
        raise ValueError("No valid pedestrian boxes in selected development frames")
    # Avoid replacing an annotated review worksheet from a previous run.
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    near = [r for r in rows if r["center_xy_radius_m"] <= 3 and r["no_eval"] is False]
    missing = [r for r in near if r["combined_if_label_upper"] == 0 or
               r["combined_if_label_ego"] == 0]
    report = {"sequence": sequence, "role": "development_only", "frames": args.frames,
              "label_file_sha256": sha256(label_path),
              "calibration_sha256": sha256(calibration_path),
              "frame_clouds": frame_clouds, "pedestrian_boxes_audited": len(rows),
              "invalid_boxes_skipped": dict(skipped),
              "evaluable_center_within_3m_boxes": len(near),
              "near_boxes_with_upper_plus_lower_points_if_label_upper": sum(
                  r["combined_if_label_upper"] > 0 for r in near),
              "near_boxes_with_upper_plus_lower_points_if_label_ego": sum(
                  r["combined_if_label_ego"] > 0 for r in near),
              "near_boxes_without_points_under_either_hypothesis": [
                  {k: r[k] for k in ("frame", "label_id", "reported_num_points",
                                      "combined_if_label_upper", "combined_if_label_ego")}
                  for r in missing],
              "csv": str(args.csv),
              "interpretation": (
                  "Offline, exploratory occupancy under two coordinate hypotheses; lower "
                  "points are transformed by lower2upper, then both point sets by upper2ego "
                  "for the ego hypothesis. Counts within annotation boxes cannot by themselves "
                  "identify the true annotation frame, validate calibration, or measure person "
                  "range. Rot_z/local-axis conventions and reported num_points preprocessing "
                  "remain unverified for this JRDB 2022 release. No 3D label or annotation "
                  "may enter the deployed inference pipeline; matching IDs do not prove timing.")}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
