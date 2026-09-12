#!/usr/bin/env python3
"""Inspect cached development detections in all five native JRDB camera views.

Reads only raw images and cached 2D boxes; never accesses JRDB reference labels.
"""

import argparse
import io
import json
import math
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw


CAMERAS = (0, 2, 4, 6, 8)
WIDTH, HEIGHT = 752, 480


def overlap(a, b):
    x1 = max(a[0], b[0]); y1 = max(a[1], b[1])
    x2 = min(a[2], b[2]); y2 = min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / (area_a + area_b - intersection) if area_a + area_b > intersection else 0.0


def validate_row(row):
    if not (isinstance(row.get("frame"), str) and row["frame"].isdigit() and
            row.get("camera") in CAMERAS and isinstance(row.get("detections"), list)):
        raise ValueError(f"Invalid frame/camera/detections row: {row!r}")
    for box in row["detections"]:
        if not isinstance(box, dict):
            raise ValueError(f"Invalid detection object in frame={row['frame']} camera={row['camera']}")
        coords = box.get("xyxy", [])
        confidence = box.get("confidence")
        if not (isinstance(coords, list) and len(coords) == 4 and
                all(isinstance(x, (int, float)) and math.isfinite(x)
                                         for x in coords) and
                0 <= coords[0] < coords[2] <= WIDTH + 1 and
                0 <= coords[1] < coords[3] <= HEIGHT + 1 and
                isinstance(confidence, (int, float)) and math.isfinite(confidence) and
                0 <= confidence <= 1):
            raise ValueError(f"Invalid pixel box/score in frame={row['frame']} camera={row['camera']}")


def draw_view(archive, sequence, frame, camera, detections):
    name = f"images/image_{camera}/{sequence}/{frame}.jpg"
    with Image.open(io.BytesIO(archive.read(name))) as image:
        result = image.convert("RGB")
    if result.size != (WIDTH, HEIGHT):
        raise ValueError(f"Unexpected native image size in {name}: {result.size}")
    pencil = ImageDraw.Draw(result)
    for entry in detections:
        x1, y1, x2, y2 = entry["xyxy"]
        pencil.rectangle((x1, y1, x2, y2), outline=(255, 230, 0), width=2)
        pencil.text((x1, max(20, y1) - 14), f"{entry['confidence']:.2f}", fill="white",
                    stroke_width=2, stroke_fill="black")
    description = (f"{sequence} | {frame} | camera {camera} | {len(detections)} boxes | "
                   "DEVELOPMENT: no ground truth")
    pencil.rectangle((0, 0, WIDTH - 1, 19), fill=(0, 0, 0))
    pencil.text((4, 3), description, fill="white")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--images-zip", type=Path, default=Path.home() / "Downloads/train_images.zip")
    parser.add_argument("--predictions", type=Path, default=Path("outputs/local/cubberly_native_pilot.jsonl"))
    parser.add_argument("--frames", nargs="+", default=["000070", "000086", "000087", "000143"])
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/local/cubberly_detection_review"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only":
        parser.error("This review is restricted to development data")
    sequence = manifest["sequence"]
    seen = {}
    by_camera = defaultdict(list)
    overlaps = Counter()
    with args.predictions.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            row = json.loads(line)
            validate_row(row)
            key = (row["frame"], row["camera"])
            if key in seen:
                raise ValueError(f"Duplicate frame/camera at prediction line {line_number}: {key}")
            seen[key] = row
            boxes = [item["xyxy"] for item in row["detections"]]
            by_camera[row["camera"]].append(len(boxes))
            overlaps[row["camera"]] += sum(overlap(boxes[i], boxes[j]) >= 0.5
                                             for i in range(len(boxes)) for j in range(i + 1, len(boxes)))
    unique_frames = sorted({frame for frame, _ in seen})
    if not unique_frames or len(seen) != len(unique_frames) * len(CAMERAS) or any(
            (frame, camera) not in seen for frame in unique_frames for camera in CAMERAS):
        raise ValueError("Incomplete five-camera predictions; inspect cache before review")
    samples = {}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.images_zip) as archive:
        for frame in args.frames:
            if not frame.isdecimal() or frame not in unique_frames:
                parser.error(f"Requested frame absent from cached predictions: {frame!r}")
            views = {}
            for camera in CAMERAS:
                view = draw_view(archive, sequence, frame, camera,
                                 seen[(frame, camera)]["detections"])
                target = args.output_dir / f"{sequence}_{frame}_camera{camera}.png"
                view.save(target)
                views[camera] = view
            sheet = Image.new("RGB", (WIDTH * 3, HEIGHT * 2), (0, 0, 0))
            for index, camera in enumerate(CAMERAS):
                sheet.paste(views[camera], ((index % 3) * WIDTH, (index // 3) * HEIGHT))
            target = args.output_dir / f"{sequence}_{frame}_all_five.png"
            sheet.save(target)
            samples[frame] = str(target)
    report = {
        "sequence": sequence, "frame_rows": len(unique_frames),
        "camera_frame_rows": len(seen),
        "per_camera": {str(camera): {"boxes": sum(by_camera[camera]),
                                     "empty_camera_frames": by_camera[camera].count(0),
                                     "median_boxes_per_camera_frame": statistics.median(by_camera[camera]),
                                     "same_camera_box_pairs_iou_at_least_0_5": overlaps[camera]}
                       for camera in CAMERAS},
        "example_review_sheets": samples,
        "note": "Visual quality-control candidates only: a zero-detection image may still contain people; IoU pairs are not validated duplicate humans. No independent labels, range or event metrics are inferred.",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
