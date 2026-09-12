#!/usr/bin/env python3
"""Offline development prototype: measured-surface range candidates in detector boxes.

Inputs are cached raw-image detections, raw upper/lower PCD returns and camera /
LiDAR calibration. NEVER reads 2D/3D annotations, identities or reference CSVs.
Candidate surfaces are NOT validated human distances or alert predictions.
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
from audit_jrdb_dev_box_geometry import upper_to_ego
from audit_jrdb_box_depth_support import load_boxes, points_in_rect
from review_jrdb_native_detections import CAMERAS, WIDTH, HEIGHT


SEQUENCE = "memorial-court-2019-03-16_0"
FRAMES = tuple(f"{i:06d}" for i in range(1089))
BIN_WIDTH_M = 0.5
MAX_RANGE_M = 20.0
MIN_BIN_POINTS = 3
MIN_BAND_POINTS = 8
DOMINANCE_RATIO = 2.0
FIELDS = ("frame", "camera", "box_index", "confidence", "xyxy",
          "projected_points_in_camera", "inner_roi_projected_points",
          "supported_depth_bands", "supported_band_counts_json",
          "nearest_supported_surface_m", "surface_candidate_status",
          "surface_candidate_ego_xy_m", "candidate_band_points",
          "upper_points_in_inner_roi", "lower_points_in_inner_roi")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def project_ego_xy(upper_xyz, sensor, upper2ego):
    """Match project() camera distortion and preserve ego horizontal radii."""
    T = np.asarray(sensor["upper2cam"], dtype=np.float64)
    K = np.asarray(sensor["distorted_img_K"], dtype=np.float64)
    D = np.asarray(sensor["D"], dtype=np.float64)
    if (T.shape != (4, 4) or K.shape != (3, 3) or D.shape != (5,) or
            not all(np.isfinite(a).all() for a in (T, K, D)) or
            not np.allclose(T[:3, :3].T @ T[:3, :3], np.eye(3), atol=0.05) or
            abs(np.linalg.det(T[:3, :3]) - 1) > 0.05):
        raise ValueError("Invalid upper2cam camera calibration")
    xyz = upper_xyz[np.isfinite(upper_xyz).all(axis=1)]
    xyz_ego = upper_to_ego(xyz, upper2ego)
    camera = xyz @ T[:3, :3].T + T[:3, 3]
    forward = camera[:, 2] > 0.1
    camera, xyz_ego = camera[forward], xyz_ego[forward]
    if not len(camera):
        return np.empty((0, 2)), np.empty(0)
    xx = camera[:, 0] / camera[:, 2]
    yy = camera[:, 1] / camera[:, 2]
    with np.errstate(over="ignore", invalid="ignore"):
        r2 = xx**2 + yy**2
        k1, k2, p1, p2, k3 = D
        radial = 1 + k1*r2 + k2*r2**2 + k3*r2**3
        xd = xx*radial + 2*p1*xx*yy + p2*(r2 + 2*xx**2)
        yd = yy*radial + p1*(r2 + 2*yy**2) + 2*p2*xx*yy
    uv = np.column_stack((K[0, 0]*xd + K[0, 1]*yd + K[0, 2],
                          K[1, 1]*yd + K[1, 2]))
    valid = (np.isfinite(uv).all(axis=1) & (uv[:, 0] >= 0) & (uv[:, 0] < WIDTH) &
             (uv[:, 1] >= 0) & (uv[:, 1] < HEIGHT))
    return uv[valid], np.linalg.norm(xyz_ego[valid, :2], axis=1)


def surface_bands(radii):
    valid = radii[np.isfinite(radii) & (radii >= 0) & (radii < MAX_RANGE_M)]
    counts = np.bincount(np.floor(valid / BIN_WIDTH_M).astype(int),
                         minlength=int(MAX_RANGE_M / BIN_WIDTH_M))
    eligible_bins = np.flatnonzero(counts >= MIN_BIN_POINTS)
    bands = []
    for part in np.split(eligible_bins, np.where(np.diff(eligible_bins) != 1)[0] + 1):
        if len(part):
            lo, hi = part[0]*BIN_WIDTH_M, (part[-1] + 1)*BIN_WIDTH_M
            selected = valid[(valid >= lo) & (valid < hi)]
            bands.append((float(lo), float(hi), len(selected), float(np.median(selected))))
    return bands


def evaluate_box(frame, camera, index, detection, uv_upper, r_upper, uv_lower, r_lower):
    x1, y1, x2, y2 = detection["xyxy"]
    width, height = x2-x1, y2-y1
    inner = (x1 + 0.2*width, y1 + 0.2*height,
             x2 - 0.2*width, y2 - 0.15*height)
    mask_u = points_in_rect(uv_upper, inner)
    mask_l = points_in_rect(uv_lower, inner)
    combined = np.concatenate((r_upper[mask_u], r_lower[mask_l]))
    bands = surface_bands(combined)
    eligible = [b for b in bands if b[2] >= MIN_BAND_POINTS]
    if not eligible:
        status, chosen = "insufficient_supported_surface", None
    elif len(eligible) == 1:
        status, chosen = "single_supported_surface_candidate", eligible[0]
    else:
        ranked = sorted(eligible, key=lambda b: (-b[2], b[0]))
        if ranked[0][2] >= DOMINANCE_RATIO*ranked[1][2]:
            status, chosen = "dominant_surface_candidate", ranked[0]
        else:
            status, chosen = "ambiguous_surface_abstain", None
    return {"frame": frame, "camera": camera, "box_index": index,
            "confidence": round(detection["confidence"], 4),
            "xyxy": json.dumps([round(x, 2) for x in detection["xyxy"]]),
            "projected_points_in_camera": len(uv_upper) + len(uv_lower),
            "inner_roi_projected_points": len(combined),
            "upper_points_in_inner_roi": int(mask_u.sum()),
            "lower_points_in_inner_roi": int(mask_l.sum()),
            "supported_depth_bands": len(bands),
            "supported_band_counts_json": json.dumps(
                [[round(lo, 2), round(hi, 2), n] for lo, hi, n, _ in bands],
                separators=(",", ":")),
            "nearest_supported_surface_m": round(bands[0][3], 3) if bands else None,
            "surface_candidate_status": status,
            "surface_candidate_ego_xy_m": round(chosen[3], 3) if chosen else None,
            "candidate_band_points": chosen[2] if chosen else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/holdout_memorial_sensor_only.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/holdout_sensors"))
    parser.add_argument("--predictions", type=Path,
                        default=Path("outputs/local/memorial_court_holdout/memorial_native_full.jsonl"))
    parser.add_argument("--frames", nargs="+", default=FRAMES)
    parser.add_argument("--csv", type=Path,
                        default=Path("outputs/local/memorial_court_holdout/memorial_sensor_surface_full.csv"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if (
        manifest.get("sequence") != SEQUENCE
        or manifest.get("role") != "holdout_sensor_only_unscored"
    ):
        parser.error(
            "Only the preregistered Memorial Court sensor-only "
            "holdout manifest is accepted"
        )
    if (
        not args.frames
        or len(args.frames) != len(set(args.frames))
        or any(
            not s.isdecimal()
            or len(s) != 6
            or not 0 <= int(s) <= 1088
            for s in args.frames
        )
    ):
        parser.error(
            "--frames requires distinct Memorial Court six-digit "
            "IDs from 000000 to 001088"
        )
    if args.csv.exists():
        parser.error(f"Refusing to replace output: {args.csv}")
    root = args.data_root / SEQUENCE
    cal_path = root / "calibration/lidars.yaml"
    cal = yaml.safe_load(cal_path.read_text())
    transform = cal["lidar"]
    # Explicitly validate both transforms without consulting GT geometry.
    upper_to_ego(np.zeros((1, 3)), transform["lower2upper"])
    upper_to_ego(np.zeros((1, 3)), transform["upper2ego"])
    predicted = load_boxes(args.predictions, args.frames)
    output = []
    for frame in args.frames:
        upper_path = root / "pointclouds/upper_velodyne" / SEQUENCE / f"{frame}.pcd"
        lower_path = root / "pointclouds/lower_velodyne" / SEQUENCE / f"{frame}.pcd"
        _, upper = read_xyz(upper_path)
        _, lower = read_xyz(lower_path)
        lower_upper = upper_to_ego(lower, transform["lower2upper"])
        for camera in CAMERAS:
            sensor = cal[f"sensor_{camera}"]
            uv_u, radius_u = project_ego_xy(upper, sensor, transform["upper2ego"])
            uv_l, radius_l = project_ego_xy(lower_upper, sensor, transform["upper2ego"])
            for index, detection in enumerate(predicted[(frame, camera)]):
                output.append(evaluate_box(frame, camera, index, detection,
                                           uv_u, radius_u, uv_l, radius_l))
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)
    status = Counter(row["surface_candidate_status"] for row in output)
    print(json.dumps({"status": "unvalidated_measured_surface_candidates",
                      "sequence": SEQUENCE, "role": "holdout_sensor_only_unscored",
                      "frames": args.frames, "boxes": len(output),
                      "status_counts": dict(status), "csv": str(args.csv),
                      "raw_prediction_sha256": sha256(args.predictions),
                      "calibration_sha256": sha256(cal_path),
                      "sensors": "upper + lower (lower2upper); 5 native cameras",
                      "range_coordinate": "horizontal XY radius in ego coordinates after upper2ego",
                      "settings": {"bin_width_m": BIN_WIDTH_M,
                                   "min_points_per_bin": MIN_BIN_POINTS,
                                   "min_points_per_candidate_band": MIN_BAND_POINTS,
                                   "dominance_ratio": DOMINANCE_RATIO,
                                   "max_ego_xy_radius_m": MAX_RANGE_M},
                      "interpretation": "Raw-sensor surface diagnostics only. A LiDAR return "
                          "inside a 2D detection can be background, another person or a "
                          "different timestamp. Candidate radii are not verified person "
                          "distances, confidence intervals or patrol alerts. Reference "
                          "annotations were never read; use a separate offline evaluator."},
                     indent=2))


if __name__ == "__main__":
    main()
