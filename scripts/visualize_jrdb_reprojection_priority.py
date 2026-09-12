#!/usr/bin/env python3
"""Render development-only native-image review sheets for projection exceptions.

Reference 2D boxes and annotated 3D centers from an offline CSV are drawn for
human diagnostic review. Do not use these annotations in a detector, range
estimator, online association, or alert generator.
"""

import argparse
import csv
import io
import json
import math
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw


SEQUENCE = "cubberly-auditorium-2019-04-22_0"
SIZE = (752, 480)
ALLOWED_CAMERAS = {"0", "2", "4", "6", "8"}
FIELDS = ("frame", "camera", "label_id", "review_priority", "image_edge_box",
          "paired_outcome", "2d_box_xywh", "2d_occlusion", "2d_truncated",
          "upper_center_uv", "upper_center_status", "ego_center_uv",
          "ego_center_status", "reviewer_decision", "reviewer_notes")


def native_image(archive, camera, frame):
    member = f"images/image_{camera}/{SEQUENCE}/{frame}.jpg"
    with Image.open(io.BytesIO(archive.read(member))) as image:
        if image.size != SIZE:
            raise ValueError(f"Unexpected native image dimensions: {member}: {image.size}")
        return image.convert("RGB")


def parse_uv(value, label):
    decoded = json.loads(value)
    if decoded is None:
        return None
    if not isinstance(decoded, list) or len(decoded) != 2 or any(
            not isinstance(v, (int, float)) or isinstance(v, bool) or
            not math.isfinite(v) for v in decoded):
        raise ValueError(f"Invalid {label}: {value}")
    return decoded


def annotation_sheet(archive, row):
    frame = int(row["frame"])
    camera = row["camera"]
    images = [(label, native_image(archive, camera, f"{value:06d}")) for label, value in
              (("previous", max(0, frame - 1)), ("review", frame),
               ("next", min(1295, frame + 1)))]
    x, y, w, h = json.loads(row["2d_box_xywh"])
    if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in (x, y, w, h)) or w <= 0 or h <= 0:
        raise ValueError(f"Invalid annotated box: {row['frame']} camera {camera}")
    middle = images[1][1]
    pencil = ImageDraw.Draw(middle)
    pencil.rectangle((x, y, x + w, y + h), outline="#f33f4e", width=4)
    for name, color in (("upper", "#ffe82a"), ("ego", "#16ebff")):
        point = parse_uv(row[f"{name}_center_uv"], name)
        if point is not None:
            u, v = point
            pencil.ellipse((u - 7, v - 7, u + 7, v + 7), outline="black", fill=color, width=2)
            pencil.text((min(u + 9, 688), max(v - 18, 28)), name, fill=color,
                        stroke_width=2, stroke_fill="black")
    sheet = Image.new("RGB", (SIZE[0] * 3, SIZE[1] + 90), (14, 16, 19))
    for index, (label, image) in enumerate(images):
        sheet.paste(image, (index * SIZE[0], 60))
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 6), f"DEVELOPMENT REFERENCE REVIEW | {row['frame']} | camera {camera} | {row['label_id']}", fill="white")
    draw.text((12, 29), f"2D box red; label-upper yellow: {row['upper_center_status']}; label-ego cyan: {row['ego_center_status']}", fill="white")
    for i, (label, _) in enumerate(images):
        draw.text((i * SIZE[0] + 12, SIZE[1] + 67), f"{label}: {max(0, min(1295, frame + i - 1)):06d}", fill="white")
    draw.text((SIZE[0] + 245, SIZE[1] + 67), f"occlusion={row['2d_occlusion']} | truncated={row['2d_truncated']}", fill="white")
    return sheet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--review-queue", type=Path,
                        default=Path("outputs/local/cubberly_reprojection_review_queue.csv"))
    parser.add_argument("--images-zip", type=Path,
                        default=Path.home() / "Downloads/train_images.zip")
    parser.add_argument("--priority", default="1_evaluable_ego_miss_unclipped")
    parser.add_argument("--max-rows", type=int, default=30)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("outputs/local/cubberly_reprojection_priority_review"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("sequence") != SEQUENCE or manifest.get("role") != "development_only":
        parser.error("Only the Cubberly development manifest is permitted")
    if not args.priority.startswith(("1_", "2_", "3_", "4_")) or not 1 <= args.max_rows <= 200:
        parser.error("Choose a review-queue priority and --max-rows from 1 to 200")
    with args.review_queue.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not set(FIELDS[:-2]).issubset(reader.fieldnames or []):
            parser.error("Review queue lacks required projection fields")
        selected = [r for r in reader if r["review_priority"] == args.priority]
    if not selected:
        parser.error(f"No rows at review priority {args.priority}")
    if len(selected) > args.max_rows:
        parser.error(f"{len(selected)} rows at selected priority; use --max-rows {len(selected)} "
                     "or filter the review CSV first")
    if args.output_dir.exists() and list(args.output_dir.glob("*.png")):
        parser.error("PNG output directory exists; use a new --output-dir")
    for row in selected:
        if row["camera"] not in ALLOWED_CAMERAS or not row["frame"].isdigit() or not 0 <= int(row["frame"]) <= 1295:
            raise ValueError(f"Invalid development frame or camera: {row['frame']} {row['camera']}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    review_log = args.output_dir / "human_review_template.csv"
    with zipfile.ZipFile(args.images_zip) as archive:
        for index, row in enumerate(selected, 1):
            filename = f"{index:02d}_{row['frame']}_camera{row['camera']}_{row['label_id'].replace(':', '_')}.png"
            path = args.output_dir / filename
            annotation_sheet(archive, row).save(path)
            row["review_image"] = str(path)
    with review_log.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=(*FIELDS, "review_image"), extrasaction="ignore")
        writer.writeheader()
        for row in selected:
            row["reviewer_decision"] = ""
            row["reviewer_notes"] = ""
            writer.writerow(row)
    print(json.dumps({"status": "development_human_review_sheets_generated",
                      "sequence": SEQUENCE, "priority": args.priority,
                      "sheets": len(selected), "distinct_frames": len({r['frame'] for r in selected}),
                      "distinct_tracks": len({r['label_id'] for r in selected}),
                      "occlusion_counts": dict(Counter(r["2d_occlusion"] for r in selected)),
                      "human_review_template": str(review_log),
                      "note": "Reference labels are diagnostic overlays only. Blank review decisions "
                              "require human inspection; no detector, range or event scores."}, indent=2))


if __name__ == "__main__":
    main()
