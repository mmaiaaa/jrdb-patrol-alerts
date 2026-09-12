#!/usr/bin/env python3
"""Inspect stitched JRDB pose coverage and draw one local annotation overlay."""
import argparse
import io
import json
import math
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/pilot_selection.json"))
    parser.add_argument("--pilot-root", type=Path, default=Path("data/jrdb2022/pilot"))
    parser.add_argument("--labels-zip", type=Path, default=Path.home() / "Downloads/labels.zip")
    parser.add_argument("--images-zip", type=Path, default=Path.home() / "Downloads/train_images.zip")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/local"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    sequence = manifest["sequence"]
    labels = json.loads((args.pilot_root / sequence / manifest["label_3d"]).read_text())["labels"]

    with zipfile.ZipFile(args.labels_zip) as archive:
        candidates = [name for name in archive.namelist() if name.startswith(
            "labels/labels_2d_pose_stitched_coco/"
        ) and Path(name).name.startswith(sequence) and name.endswith(".json")]
        if len(candidates) != 1:
            raise ValueError(f"Expected one stitched pose JSON for {sequence}; found {candidates}")
        member = candidates[0]
        payload = json.loads(archive.read(member))

    images = payload["images"]
    annotations = payload["annotations"]
    id_to_frame = {item["id"]: Path(item["file_name"]).stem for item in images}
    if len(id_to_frame) != len(images):
        raise ValueError("Duplicate stitched COCO image ID")
    image_frames = set(id_to_frame.values())
    annotated = defaultdict(list)
    annotation_fields = Counter()
    category_counts = Counter()
    missing_image_ids = 0
    for item in annotations:
        annotation_fields.update(item.keys())
        category_counts[str(item.get("category_id"))] += 1
        frame = id_to_frame.get(item.get("image_id"))
        if frame is None:
            missing_image_ids += 1
        else:
            annotated[frame].append(item)

    nearby = defaultdict(set)
    for frame_name, entries in labels.items():
        frame = Path(frame_name).stem
        for item in entries:
            label_id = str(item.get("label_id", ""))
            if not label_id.startswith("pedestrian:"):
                continue
            if (item.get("attributes") or {}).get("no_eval") is not False:
                continue
            box = item.get("box") or {}
            try:
                radius = math.hypot(float(box["cx"]), float(box["cy"]))
            except (KeyError, ValueError, TypeError):
                continue
            if radius <= 3.0:
                nearby[frame].add(label_id.partition(":")[2])

    matches_by_frame = {}
    for frame, entries in annotated.items():
        tracks = {str(item["track_id"]) for item in entries if item.get("track_id") is not None}
        matches_by_frame[frame] = len(tracks & nearby[frame])
    if not annotated:
        raise ValueError("Stitched pose file has no annotations to overlay")
    frame = max(sorted(annotated), key=lambda key: (matches_by_frame[key], len(annotated[key])))
    image_member = f"images/image_stitched/{sequence}/{frame}.jpg"
    with zipfile.ZipFile(args.images_zip) as archive:
        image = Image.open(io.BytesIO(archive.read(image_member))).convert("RGB")

    source_rows = [row for row in images if id_to_frame[row["id"]] == frame]
    if len(source_rows) != 1:
        raise ValueError("Selected frame has ambiguous pose image metadata")
    source = source_rows[0]
    if (source.get("width"), source.get("height")) != image.size:
        raise ValueError(f"Image dimension mismatch: pose row={source} JPEG={image.size}")

    draw = ImageDraw.Draw(image)
    drawn_keypoints = 0
    for item in annotated[frame]:
        coords = item.get("keypoints", [])
        if not isinstance(coords, list) or len(coords) % 3:
            continue
        for x, y, visibility in zip(coords[::3], coords[1::3], coords[2::3]):
            if visibility not in (1, 2):
                continue
            try:
                x, y = float(x), float(y)
            except (ValueError, TypeError):
                continue
            if not (math.isfinite(x) and math.isfinite(y) and 0 <= x < image.width and 0 <= y < image.height):
                continue
            color = "#10ff32" if visibility == 2 else "#ffb300"
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), outline=color, width=2)
            drawn_keypoints += 1
        visible = [(float(x), float(y)) for x, y, v in zip(
            coords[::3], coords[1::3], coords[2::3]
        ) if v == 2 and isinstance(x, (int, float)) and isinstance(y, (int, float))
                   and math.isfinite(x) and math.isfinite(y) and 0 <= x < image.width and 0 <= y < image.height]
        if visible:
            x, y = min(visible, key=lambda point: point[1])
            draw.text((x, max(0, y - 13)), str(item.get("track_id", "?")), fill="yellow", stroke_width=2, stroke_fill="black")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    overlay = args.output_dir / f"{sequence}_stitched_pose_{frame}.png"
    image.save(overlay)
    report = {
        "sequence": sequence,
        "stitched_pose_member": member,
        "stitched_pose_images": len(images),
        "stitched_pose_unique_frames": len(image_frames),
        "3d_label_frames_absent_from_pose_images_first_20": sorted(
            {Path(name).stem for name in labels} - image_frames
        )[:20],
        "stitched_pose_annotations": len(annotations),
        "stitched_pose_frames_with_annotations": len(annotated),
        "annotations_with_unresolved_image_id": missing_image_ids,
        "annotation_field_counts": dict(sorted(annotation_fields.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "near_3m_3d_observations": sum(map(len, nearby.values())),
        "near_3m_same_frame_numeric_pose_track_matches": sum(matches_by_frame.values()),
        "overlay_frame": frame,
        "overlay_annotations": len(annotated[frame]),
        "overlay_visible_or_occluded_keypoints": drawn_keypoints,
        "overlay_path": str(overlay),
        "note": "Pose labels are incomplete for visibility; numeric ID matching and keypoint alignment require visual verification. Do not commit the overlay or raw JRDB data.",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
