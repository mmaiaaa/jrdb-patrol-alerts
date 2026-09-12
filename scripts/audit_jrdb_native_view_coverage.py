#!/usr/bin/env python3
"""Build visual audits of cameras with zero detector boxes in the Cubberly pilot.

Uses only the original JPEGs and the cached 2D predictions; no reference labels.
"""

import argparse
import io
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

from review_jrdb_native_detections import CAMERAS, HEIGHT, WIDTH, validate_row


THUMB_SIZE = (376, 240)
GRID_COLUMNS = 5
GRID_ROWS = 4
GRID_PAGE_SIZE = GRID_COLUMNS * GRID_ROWS


def load_cache(path):
    found = {}
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            row = json.loads(line)
            validate_row(row)
            key = (row["frame"], row["camera"])
            if key in found:
                raise ValueError(f"Duplicate frame/camera row at line {line_number}: {key}")
            found[key] = row
    frames = sorted({frame for frame, _ in found})
    if not frames or any((frame, camera) not in found for frame in frames for camera in CAMERAS):
        raise ValueError("Expected complete five-camera rows for every cached frame")
    return found, frames


def make_pages(archive, sequence, rows, frames, camera, output_dir, label):
    paths = []
    for offset in range(0, len(frames), GRID_PAGE_SIZE):
        subset = frames[offset:offset + GRID_PAGE_SIZE]
        sheet = Image.new("RGB", (THUMB_SIZE[0] * GRID_COLUMNS,
                                  THUMB_SIZE[1] * GRID_ROWS), (20, 20, 20))
        for index, frame in enumerate(subset):
            member = f"images/image_{camera}/{sequence}/{frame}.jpg"
            with Image.open(io.BytesIO(archive.read(member))) as source:
                if source.size != (WIDTH, HEIGHT):
                    raise ValueError(f"Unexpected native JPEG size: {member}, {source.size}")
                image = source.convert("RGB").resize(THUMB_SIZE)
            drawer = ImageDraw.Draw(image)
            drawer.rectangle((0, 0, THUMB_SIZE[0] - 1, 20), fill="black")
            count = len(rows[(frame, camera)]["detections"])
            drawer.text((6, 4), f"frame {frame} | camera {camera} | {count} boxes",
                        fill="white")
            sheet.paste(image, ((index % GRID_COLUMNS) * THUMB_SIZE[0],
                                (index // GRID_COLUMNS) * THUMB_SIZE[1]))
        path = output_dir / f"{sequence}_{label}_page{offset // GRID_PAGE_SIZE + 1:02}.png"
        sheet.save(path)
        paths.append(str(path))
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--images-zip", type=Path, default=Path.home() / "Downloads/train_images.zip")
    parser.add_argument("--predictions", type=Path, default=Path("outputs/local/cubberly_native_pilot.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/local/cubberly_view_coverage"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only" or manifest.get("sequence") != "cubberly-auditorium-2019-04-22_0":
        parser.error("Expected Cubberly development-only manifest")
    sequence = manifest["sequence"]
    rows, frames = load_cache(args.predictions)
    if len(rows) != len(frames) * len(CAMERAS):
        raise ValueError("Extra camera rows beyond complete five-view frames")
    camera2_empty = [frame for frame in frames if not rows[(frame, 2)]["detections"]]
    camera8_empty = [frame for frame in frames if not rows[(frame, 8)]["detections"]]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.images_zip) as archive:
        camera2_sheets = make_pages(archive, sequence, rows, camera2_empty, 2,
                                    args.output_dir, "camera2_zero_box")
        camera8_sheets = make_pages(archive, sequence, rows, camera8_empty, 8,
                                    args.output_dir, "camera8_zero_box")
    print(json.dumps({
        "sequence": sequence,
        "role": "development_only",
        "cached_frames": len(frames),
        "cached_camera_frames": len(rows),
        "empty_camera_frames": {str(camera): sum(not rows[(frame, camera)]["detections"]
                                           for frame in frames) for camera in CAMERAS},
        "camera2_empty_frame_ids": camera2_empty,
        "camera8_empty_frame_ids": camera8_empty,
        "camera2_contact_sheets": camera2_sheets,
        "camera8_empty_contact_sheets": camera8_sheets,
        "note": "Thumbnails are a review aid. A person may be too small, occluded or partly outside the frame; inspect original full-resolution JPEGs where uncertain. No ground truth, recall or event outcomes are computed.",
    }, indent=2))


if __name__ == "__main__":
    main()
