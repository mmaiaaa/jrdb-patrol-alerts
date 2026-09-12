#!/usr/bin/env python3
"""Inspect stitched JRDB pose coverage; optionally draw a diagnostic overlay."""
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
    parser.add_argument("--diagnostic-overlay", action="store_true",
                        help="Draw keypoints on native JPEG despite mismatched pose width metadata; visual inspection only")
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

    metadata_width = source.get("width")
    coordinate_counts = Counter()
    selected_frame_x = []
    for annotation_frame, entries in annotated.items():
        for entry in entries:
            points = entry.get("keypoints")
            if not isinstance(points, list) or len(points) % 3:
                coordinate_counts["malformed_keypoint_lists"] += 1
                continue
            for x, y, v in zip(points[::3], points[1::3], points[2::3]):
                if v not in (1, 2):
                    continue
                if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                    coordinate_counts["non_numeric_visible_or_occluded"] += 1
                    continue
                if not (math.isfinite(x) and math.isfinite(y)):
                    coordinate_counts["non_finite_visible_or_occluded"] += 1
                    continue
                if annotation_frame == frame:
                    selected_frame_x.append(x)
                if x < 0 or y < 0:
                    coordinate_counts["negative_x_or_y"] += 1
                elif x >= image.width or y >= image.height:
                    coordinate_counts["outside_jpeg_dimensions"] += 1
                elif isinstance(metadata_width, (int, float)) and x >= metadata_width:
                    coordinate_counts["inside_jpeg_beyond_metadata_width"] += 1
                else:
                    coordinate_counts["inside_metadata_width_and_jpeg"] += 1

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
        "pose_image_metadata_sizes": dict(Counter(
            f"{row.get('width')}x{row.get('height')}" for row in images
        )),
        "near_3m_3d_observations": sum(map(len, nearby.values())),
        "near_3m_same_frame_numeric_pose_track_matches": sum(matches_by_frame.values()),
        "selected_frame": frame,
        "selected_frame_annotations": len(annotated[frame]),
        "selected_frame_pose_metadata_size": [source.get("width"), source.get("height")],
        "selected_frame_jpeg_size": list(image.size),
        "selected_frame_visible_or_occluded_x_min_max": [min(selected_frame_x), max(selected_frame_x)] if selected_frame_x else None,
        "visible_or_occluded_keypoint_coordinate_counts": dict(sorted(coordinate_counts.items())),
        "overlay_path": None,
        "note": "A 752-wide pose row for a 3760-wide stitched JPEG is a metadata discrepancy, not proof of the keypoint coordinate convention. No visibility event labels are defined here.",
    }
    mismatched_size = (source.get("width"), source.get("height")) != image.size
    if mismatched_size and not args.diagnostic_overlay:
        report["overlay_status"] = "skipped_dimension_mismatch"
        print(json.dumps(report, indent=2))
        return
    if mismatched_size and not coordinate_counts["inside_jpeg_beyond_metadata_width"]:
        raise ValueError("No keypoint evidence beyond pose metadata width; cannot draw diagnostic overlay")

    draw = ImageDraw.Draw(image)
    if mismatched_size:
        draw.rectangle((0, 0, min(image.width - 1, 700), 23), fill="black")
        draw.text((5, 5), "DIAGNOSTIC ONLY: pose width 752 != stitched JPEG width 3760", fill="white")
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
    report["overlay_status"] = (
        "generated_diagnostic_despite_metadata_mismatch" if mismatched_size
        else "generated_metadata_dimensions_match"
    )
    report["overlay_path"] = str(overlay)
    report["overlay_visible_or_occluded_keypoints"] = drawn_keypoints
    report["overlay_interpretation"] = "Visual registration check only; no validated reference labels or performance results."
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
