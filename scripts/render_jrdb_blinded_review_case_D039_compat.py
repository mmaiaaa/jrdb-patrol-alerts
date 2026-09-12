#!/usr/bin/env python3
"""Render case-focused Cubberly review sheets from images and measured LiDAR.

Uses the blinded reviewer CSV and sensor-only cache. Never opens JRDB labels,
the selection key, or threshold/reference files. Colors indicate sensor-only
selected returns inside the detector ROI; they do not prove person identity.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

from audit_jrdb_cubberly_projection import read_xyz
from audit_jrdb_dev_box_geometry import upper_to_ego
from cache_jrdb_dev_sensor_depth_candidates import (
    MIN_BAND_POINTS, project_ego_xy, surface_bands, evaluate_box,
)
from review_jrdb_native_detections import CAMERAS, HEIGHT, WIDTH


SEQUENCE = "cubberly-auditorium-2019-04-22_0"
REQUIRED_REVIEW = {"case_id", "sequence", "frame", "camera", "detector_box_xyxy"}
REQUIRED_SENSOR = {"frame", "camera", "box_index", "xyxy", "confidence",
                   "surface_candidate_status", "surface_candidate_ego_xy_m",
                   "nearest_supported_surface_m", "inner_roi_projected_points"}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rectangle(value):
    coords = json.loads(value)
    if (not isinstance(coords, list) or len(coords) != 4 or
            not all(type(x) in (int, float) and math.isfinite(x) for x in coords) or
            not (0 <= coords[0] < coords[2] <= WIDTH + 1 and
                 0 <= coords[1] < coords[3] <= HEIGHT + 1)):
        raise ValueError(f"Invalid detector rectangle {value!r}")
    return coords


def match_case(review, available):
    """Associate by the exact cached 2-decimal rectangle; no key/GT access."""
    wanted = rectangle(review["detector_box_xyxy"])
    hits = [row for row in available if rectangle(row["xyxy"]) == wanted]
    if len(hits) != 1:
        raise ValueError(f"Expected one cached detection for {review['case_id']}, got {len(hits)}")
    return hits[0]


REPLAY_DISTANCE_TOLERANCE_M = 0.005
REPLAY_POINT_COUNT_TOLERANCE = 1


def cached_equal(expected, actual):
    # Categorical method outcome must remain exactly identical.
    name = "surface_candidate_status"
    left, right = expected[name], actual[name]

    if str(left if left is not None else "") != str(
        right if right is not None else ""
    ):
        raise ValueError(
            f"Sensor-only preview replay mismatch in "
            f"{name}: {left!r} vs {right!r}"
        )

    # Rendering compatibility only: permit a tiny numeric replay
    # drift without changing the frozen cached candidate.
    for name in (
        "surface_candidate_ego_xy_m",
        "nearest_supported_surface_m",
    ):
        left, right = expected[name], actual[name]

        left_blank = left in (None, "")
        right_blank = right in (None, "")

        if left_blank != right_blank:
            raise ValueError(
                f"Sensor-only preview replay mismatch in "
                f"{name}: {left!r} vs {right!r}"
            )

        if (
            not left_blank
            and abs(float(left) - float(right))
            > REPLAY_DISTANCE_TOLERANCE_M
        ):
            raise ValueError(
                f"Sensor-only preview replay mismatch in "
                f"{name}: {left!r} vs {right!r}"
            )

    name = "inner_roi_projected_points"

    left = int(expected[name])
    right = int(actual[name])

    if abs(left - right) > REPLAY_POINT_COUNT_TOLERANCE:
        raise ValueError(
            f"Sensor-only preview replay mismatch in "
            f"{name}: {left!r} vs {right!r}"
        )


def read_image(archive, frame, camera):
    member = f"images/image_{camera}/{SEQUENCE}/{frame}.jpg"
    with Image.open(io.BytesIO(archive.read(member))) as image:
        if image.size != (WIDTH, HEIGHT):
            raise ValueError(f"Unexpected native image dimensions: {member}")
        return image.convert("RGB")


def render(review, sensor, archive, root, calibration):
    frame, camera = review["frame"], int(review["camera"])
    xyxy = rectangle(review["detector_box_xyxy"])
    upper_path = root / "pointclouds/upper_velodyne" / SEQUENCE / f"{frame}.pcd"
    lower_path = root / "pointclouds/lower_velodyne" / SEQUENCE / f"{frame}.pcd"
    _, upper = read_xyz(upper_path)
    _, lower = read_xyz(lower_path)
    t = calibration["lidar"]
    upper_to_ego(np.zeros((1, 3)), t["lower2upper"])
    upper_to_ego(np.zeros((1, 3)), t["upper2ego"])
    lower_upper = upper_to_ego(lower, t["lower2upper"])
    sensor_cal = calibration[f"sensor_{camera}"]
    uv_u, radius_u = project_ego_xy(upper, sensor_cal, t["upper2ego"])
    uv_l, radius_l = project_ego_xy(lower_upper, sensor_cal, t["upper2ego"])
    replay = evaluate_box(frame, camera, int(sensor["box_index"]),
                          {"xyxy": xyxy, "confidence": float(sensor["confidence"])},
                          uv_u, radius_u, uv_l, radius_l)
    cached_equal(sensor, replay)
    uv = np.concatenate((uv_u, uv_l), axis=0)
    radii = np.concatenate((radius_u, radius_l))
    x1, y1, x2, y2 = xyxy
    inner = (x1 + .2*(x2-x1), y1 + .2*(y2-y1),
             x2 - .2*(x2-x1), y2 - .15*(y2-y1))
    inside = ((uv[:, 0] >= inner[0]) & (uv[:, 0] < inner[2]) &
              (uv[:, 1] >= inner[1]) & (uv[:, 1] < inner[3]))
    if abs(
        int(inside.sum())
        - int(sensor["inner_roi_projected_points"])
    ) > REPLAY_POINT_COUNT_TOLERANCE:
        raise ValueError(
            f"ROI point count changed for case "
            f"{review['case_id']}"
        )

    selected = np.zeros(
        len(radii),
        dtype=bool,
    )

    if sensor["surface_candidate_ego_xy_m"] not in (None, ""):
        value = float(
            sensor["surface_candidate_ego_xy_m"]
        )

        bands = [
            band
            for band in surface_bands(
                radii[inside]
            )
            if band[2] >= MIN_BAND_POINTS
        ]

        bands = sorted(
            bands,
            key=lambda band:
                abs(float(band[3]) - value),
        )

        if (
            not bands
            or abs(float(bands[0][3]) - value)
            > REPLAY_DISTANCE_TOLERANCE_M
        ):
            raise ValueError(
                f"Cannot recover sensor-selected band "
                f"for {review['case_id']}"
            )

        # Reject rather than guess if more than one valid band
        # lies within the compatibility tolerance.
        if (
            len(bands) > 1
            and abs(float(bands[1][3]) - value)
            <= REPLAY_DISTANCE_TOLERANCE_M
        ):
            raise ValueError(
                f"Ambiguous sensor-selected band "
                f"for {review['case_id']}"
            )

        lo, hi, _, _ = bands[0]

        selected = (
            inside
            & (radii >= lo)
            & (radii < hi)
        )

    original = read_image(archive, frame, camera)
    original_pen = ImageDraw.Draw(original)
    original_pen.rectangle(xyxy, outline=(255, 205, 30), width=4)
    original_pen.text((7, 10), f"{review['case_id']}  frame {frame}  camera {camera}  target box",
                      fill="white", stroke_width=2, stroke_fill="black")
    overlay = read_image(archive, frame, camera)
    dots = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    pen = ImageDraw.Draw(dots)
    # The raw cloud is for qualitative review only; all points feed replay above.
    inds = np.flatnonzero(inside & ~selected)
    if len(inds) > 2500:
        inds = inds[np.linspace(0, len(inds)-1, 2500, dtype=int)]
    for i in inds:
        u, v = uv[i]
        pen.ellipse((u-1, v-1, u+1, v+1), fill=(210, 210, 210, 160))
    for i in np.flatnonzero(selected):
        u, v = uv[i]
        pen.ellipse((u-2, v-2, u+2, v+2), fill=(20, 255, 100, 230))
    overlay = Image.alpha_composite(overlay.convert("RGBA"), dots).convert("RGB")
    op = ImageDraw.Draw(overlay)
    op.rectangle(xyxy, outline=(255, 205, 30), width=4)
    op.text((7, 10), "ROI: other returns grey; selected band green (if any)",
            fill="white", stroke_width=2, stroke_fill="black")
    sheet = Image.new("RGB", (WIDTH*2, HEIGHT*2), (12, 12, 12))
    sheet.paste(original, (0, 0))
    sheet.paste(overlay, (WIDTH, 0))
    prev_id, next_id = max(0, int(frame)-2), min(1295, int(frame)+2)
    for x_offset, number, label in ((0, prev_id, "context -2 frames"),
                                    (WIDTH, next_id, "context +2 frames")):
        context = read_image(archive, f"{number:06}", camera)
        ImageDraw.Draw(context).text((7, 10), label, fill="white",
                                     stroke_width=2, stroke_fill="black")
        sheet.paste(context, (x_offset, HEIGHT))
    return sheet, int(inside.sum()), int(selected.sum())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer-csv", type=Path,
                        default=Path("outputs/local/cubberly_blinded_review/reviewer_a.csv"))
    parser.add_argument("--sensor-csv", type=Path,
                        default=Path("outputs/local/cubberly_sensor_surface_full.csv"))
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--images-zip", type=Path,
                        default=Path.home() / "Downloads/train_images.zip")
    parser.add_argument("--output-dir", type=Path,
                        default=Path("outputs/local/cubberly_blinded_review/case_sheets"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only" or manifest.get("sequence") != SEQUENCE:
        parser.error("Expected Cubberly development manifest")
    with args.reviewer_csv.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not REQUIRED_REVIEW <= set(reader.fieldnames or ()):
            parser.error("Incomplete blinded reviewer CSV")
        cases = list(reader)
    if not cases:
        parser.error("Empty reviewer CSV")
    used_ids = set()
    wanted = defaultdict(list)
    for row in cases:
        case_id, frame = row["case_id"], row["frame"]
        if (not re.fullmatch(r"D[0-9]{3}", case_id) or case_id in used_ids or
                row["sequence"] != SEQUENCE or len(frame) != 6 or
                not frame.isdecimal() or not 0 <= int(frame) <= 1295 or
                not row["camera"].isdecimal() or int(row["camera"]) not in CAMERAS):
            parser.error(f"Invalid or duplicate reviewer case {row!r}")
        used_ids.add(case_id)
        wanted[(frame, int(row["camera"]))].append(row)
    raw = defaultdict(list)
    with args.sensor_csv.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not REQUIRED_SENSOR <= set(reader.fieldnames or ()):
            parser.error("Incomplete sensor-only CSV")
        for row in reader:
            key = (row["frame"], int(row["camera"]))
            if key in wanted:
                raw[key].append(row)
    root = args.data_root / SEQUENCE
    calibration_path = root / "calibration/lidars.yaml"
    calibration = yaml.safe_load(calibration_path.read_text(encoding="utf-8"))
    for camera in CAMERAS:
        if f"sensor_{camera}" not in calibration:
            raise ValueError(f"Missing camera {camera} calibration")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error("Refusing to overwrite case sheets")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = []
    with zipfile.ZipFile(args.images_zip) as archive:
        for row in cases:
            cached = match_case(row, raw[(row["frame"], int(row["camera"]))])
            sheet, points, selected = render(row, cached, archive, root, calibration)
            path = args.output_dir / f"{row['case_id']}.png"
            sheet.save(path)
            report.append({"case_id": row["case_id"], "frame": row["frame"],
                           "camera": int(row["camera"]), "sheet": str(path),
                           "roi_measured_points": points,
                           "selected_band_points": selected})
    print(json.dumps({"status": "development_blinded_sensor_visual_review",
                      "sequence": SEQUENCE, "cases": len(report),
                      "sensor_csv_sha256": digest(args.sensor_csv),
                      "reviewer_csv_sha256": digest(args.reviewer_csv),
                      "calibration_sha256": digest(calibration_path),
                      "images_zip": str(args.images_zip),
                      "sheets": report,
                      "interpretation": "Measured points projected into each candidate box, "
                      "and highlighted sensor-selected depth band. No reference "
                      "annotation or selection key was opened. These are review "
                      "aids, not adjudications or validated person distances."}, indent=2))


if __name__ == "__main__":
    main()
