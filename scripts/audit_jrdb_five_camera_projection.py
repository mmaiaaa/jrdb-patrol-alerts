#!/usr/bin/env python3
"""Visual QA: project measured upper-LiDAR points over raw Cubberly detections.

Development only. This script uses no JRDB reference boxes, tracks, or event labels.
Its color-coded cloud points are not person ranges or alert predictions.
"""

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

from audit_jrdb_cubberly_projection import project, read_xyz
from review_jrdb_native_detections import CAMERAS, HEIGHT, WIDTH, validate_row

DEFAULT_FRAMES = ("000087", "000432", "000864", "001295")
SEQUENCE = "cubberly-auditorium-2019-04-22_0"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_detections(path, frames):
    wanted = set(frames)
    selected = {}
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            row = json.loads(line)
            validate_row(row)
            if row["frame"] not in wanted:
                continue
            key = (row["frame"], row["camera"])
            if key in selected:
                raise ValueError(f"Duplicate selected frame/camera row at line {line_number}: {key}")
            selected[key] = row["detections"]
    missing = [(frame, camera) for frame in frames for camera in CAMERAS
               if (frame, camera) not in selected]
    if missing:
        raise ValueError(f"Cached detections missing selected views; first: {missing[:5]}")
    return selected


def overlay(rgb, uv, ranges, detections, frame, camera):
    dots = Image.new("RGBA", rgb.size, (0, 0, 0, 0))
    canvas = ImageDraw.Draw(dots)
    # Fixed subsampling changes preview density only; numeric counts use all points.
    if len(uv) > 8000:
        indices = np.linspace(0, len(uv) - 1, 8000, dtype=int)
        uv, ranges = uv[indices], ranges[indices]
    for (u, v), radial_m in zip(uv, ranges):
        color = (255, 215, 25) if radial_m <= 3 else (20, 240, 245) if radial_m <= 10 else (255, 55, 180)
        canvas.ellipse((int(u) - 1, int(v) - 1, int(u) + 1, int(v) + 1), fill=(*color, 200))
    output = Image.alpha_composite(rgb.convert("RGBA"), dots).convert("RGB")
    pen = ImageDraw.Draw(output)
    for det in detections:
        pen.rectangle(det["xyxy"], outline="black", width=4)
        pen.rectangle(det["xyxy"], outline="white", width=2)
        x1, y1, _, _ = det["xyxy"]
        pen.text((x1, max(37, y1) - 14), f"{det['confidence']:.2f}", fill="white",
                 stroke_width=2, stroke_fill="black")
    pen.rectangle((0, 0, WIDTH - 1, 31), fill="black")
    pen.text((5, 3), f"{frame} | camera {camera} | {len(detections)} boxes | upper-LiDAR points",
             fill="white")
    pen.text((5, 17), "Upper-LiDAR XY <=3m: yellow; <=10m: cyan; farther: pink",
             fill="white")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--images-zip", type=Path, default=Path.home() / "Downloads/train_images.zip")
    parser.add_argument("--predictions", type=Path, default=Path("outputs/local/cubberly_native_full.jsonl"))
    parser.add_argument("--frames", nargs="+", default=list(DEFAULT_FRAMES))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/local/cubberly_five_camera_projection"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only" or manifest.get("sequence") != SEQUENCE:
        parser.error("Expected the Cubberly development-only manifest")
    if any(len(frame) != 6 or not frame.isdecimal() for frame in args.frames) or len(set(args.frames)) != len(args.frames):
        parser.error("--frames requires unique six-digit frame IDs")

    root = args.data_root / SEQUENCE
    calibration_path = root / "calibration/lidars.yaml"
    calibration = yaml.safe_load(calibration_path.read_text())
    for camera in CAMERAS:
        if f"sensor_{camera}" not in calibration:
            raise ValueError(f"Missing sensor_{camera} in {calibration_path}")
    detections = selected_detections(args.predictions, args.frames)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {"sequence": SEQUENCE, "role": "development_only", "frames": args.frames,
              "source_predictions": str(args.predictions),
              "predictions_sha256": sha256_file(args.predictions),
              "calibration": str(calibration_path),
              "calibration_sha256": sha256_file(calibration_path),
              "camera_previews": [],
              "interpretation": "Diagnostic measured upper-LiDAR projection and raw 2D boxes. Points in a box may be on foreground or background surfaces; no person range, tracking, alert, timing or ground-truth metric is computed."}
    with zipfile.ZipFile(args.images_zip) as archive:
        for frame in args.frames:
            cloud_path = root / "pointclouds/upper_velodyne" / SEQUENCE / f"{frame}.pcd"
            header, xyz = read_xyz(cloud_path)
            for camera in CAMERAS:
                member = f"images/image_{camera}/{SEQUENCE}/{frame}.jpg"
                with Image.open(io.BytesIO(archive.read(member))) as source:
                    if source.size != (WIDTH, HEIGHT):
                        raise ValueError(f"Unexpected native JPEG dimensions: {member}: {source.size}")
                    rgb = source.convert("RGB")
                uv, ranges, counts = project(xyz, calibration[f"sensor_{camera}"], rgb.size)
                preview = overlay(rgb, uv, ranges, detections[(frame, camera)], frame, camera)
                filename = f"{SEQUENCE}_{frame}_camera{camera}_upper_detections.png"
                path = args.output_dir / filename
                preview.save(path)
                report["camera_previews"].append({"frame": frame, "camera": camera,
                                                  "boxes": len(detections[(frame, camera)]),
                                                  "pcd_points_declared": int(header.get("POINTS", "0")),
                                                  "projected_points_inside_camera": counts["inside_image"],
                                                  "preview": str(path)})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
