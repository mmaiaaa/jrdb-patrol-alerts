#!/usr/bin/env python3
"""Audit camera-0 pose coverage against pilot images and 3D labels (diagnostic only)."""
import argparse
import json
import math
import zipfile
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/pilot_selection.json"))
    parser.add_argument("--pilot-root", type=Path, default=Path("data/jrdb2022/pilot"))
    parser.add_argument("--labels-zip", type=Path, default=Path.home() / "Downloads/labels.zip")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    sequence = manifest["sequence"]
    root = args.pilot_root / sequence
    image_ids = {path.stem for path in (root / "images/image_0" / sequence).glob("*.jpg")}
    labels = json.loads((root / manifest["label_3d"]).read_text())["labels"]
    label_ids = {Path(name).stem for name in labels}

    member = f"labels/labels_2d_pose_coco/{sequence}_image0.json"
    with zipfile.ZipFile(args.labels_zip) as archive:
        pose = json.loads(archive.read(member))
    images = pose["images"]
    annotations = pose["annotations"]
    if not isinstance(images, list) or not isinstance(annotations, list):
        raise ValueError("Expected COCO-style lists for images and annotations")
    pose_images = {}
    duplicate_image_ids = 0
    for image in images:
        key = image.get("id")
        if key in pose_images:
            duplicate_image_ids += 1
        pose_images[key] = Path(image.get("file_name", "")).stem
    pose_frames = set(pose_images.values())

    fields = Counter()
    categories = Counter()
    visibility = Counter()
    keypoint_lengths = Counter()
    pose_tracks = set()
    annotated_frames = set()
    pose_frame_track_pairs = set()
    invalid_image_references = 0
    for item in annotations:
        fields.update(item.keys())
        categories[str(item.get("category_id"))] += 1
        frame = pose_images.get(item.get("image_id"))
        if frame is None:
            invalid_image_references += 1
            continue
        annotated_frames.add(frame)
        track = item.get("track_id")
        if track is not None:
            pose_tracks.add(str(track))
            pose_frame_track_pairs.add((frame, str(track)))
        points = item.get("keypoints")
        if isinstance(points, list):
            keypoint_lengths[str(len(points))] += 1
            if len(points) % 3 == 0:
                visibility.update(str(score) for score in points[2::3])

    near_3d_pairs = set()
    for frame_name, entries in labels.items():
        frame = Path(frame_name).stem
        for entry in entries:
            label_id = str(entry.get("label_id", ""))
            if not label_id.startswith("pedestrian:"):
                continue
            if (entry.get("attributes") or {}).get("no_eval") is not False:
                continue
            box = entry.get("box") or {}
            try:
                distance = math.hypot(float(box["cx"]), float(box["cy"]))
            except (ValueError, TypeError, KeyError):
                continue
            if distance <= 3.0:
                near_3d_pairs.add((frame, label_id.partition(":")[2]))

    matches = near_3d_pairs & pose_frame_track_pairs
    report = {
        "sequence": sequence,
        "image_file_frames": len(image_ids),
        "3d_label_frames": len(label_ids),
        "pose_image_rows": len(images),
        "pose_unique_frame_names": len(pose_frames),
        "pose_duplicate_image_ids": duplicate_image_ids,
        "image_frames_absent_from_pose_images": sorted(image_ids - pose_frames)[:20],
        "pose_image_frames_absent_from_image_files": sorted(pose_frames - image_ids)[:20],
        "pose_annotations": len(annotations),
        "pose_frames_with_annotations": len(annotated_frames),
        "pose_unique_track_ids": len(pose_tracks),
        "pose_invalid_image_references": invalid_image_references,
        "pose_annotation_fields_present_counts": dict(sorted(fields.items())),
        "pose_categories": dict(sorted(categories.items())),
        "keypoint_list_lengths": dict(sorted(keypoint_lengths.items())),
        "keypoint_visibility_values": dict(sorted(visibility.items())),
        "near_3m_no_eval_false_3d_frame_track_pairs": len(near_3d_pairs),
        "near_3m_pairs_with_same_numeric_pose_track_in_same_frame": len(matches),
        "example_matching_frame_ids": sorted({frame for frame, _ in matches})[:10],
        "caution": (
            "Matching numeric track IDs is a diagnostic, not proof that every unmatched 3D person "
            "was outside camera 0. Pose annotations can omit people; validate the ID convention "
            "and visibly inspect sample frames before defining reference events."
        ),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
