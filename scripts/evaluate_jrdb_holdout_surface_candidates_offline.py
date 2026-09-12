#!/usr/bin/env python3
"""Offline, development-only reference comparison for measured surface candidates.

This is an EVALUATOR, not a runtime module: reads JRDB 2D/3D labels, matches
raw detector boxes to annotated 2D boxes, and compares sensor-derived surface
radii with annotated 3D centers. Never import this into an online pipeline.
"""

import argparse
import csv
import hashlib
import json
import math
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from audit_jrdb_dev_native_2d_3d_reprojection import xywh
from inspect_jrdb_dev_native_2d_reference import selected_image_labels
from review_jrdb_native_detections import overlap


SEQUENCE = "memorial-court-2019-03-16_0"
CAMERAS = (0, 2, 4, 6, 8)
MIN_IOU = 0.5
NEAR_RADIUS_M = 3.0
FIELDS = ("frame", "camera", "box_index", "label_id", "box_iou",
          "reference_ego_xy_center_radius_m", "reference_near_3m",
          "candidate_status", "candidate_ego_xy_surface_m",
          "nearest_supported_surface_m", "candidate_minus_center_m",
          "nearest_minus_center_m", "candidate_absolute_center_discrepancy_m",
          "nearest_absolute_center_discrepancy_m", "2d_occlusion", "2d_truncated",
          "2d_no_eval")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def optional_float(value, key):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (ValueError, TypeError) as error:
        raise ValueError(f"Invalid numeric candidate {key}: {value!r}") from error
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Invalid finite nonnegative candidate {key}: {value!r}")
    return number


def match_one_to_one(detections, annotations):
    """Maximum cardinality at IoU>=0.5; deterministic descending-IoU traversal.

    Does not optimize summed IoU across equally sized matchings. Reported
    matches are diagnostics, not an official JRDB detection benchmark.
    """
    adjacency = []
    scores = {}
    for di, row in enumerate(detections):
        candidates = []
        for ai, ann in enumerate(annotations):
            score = overlap(row["xyxy"], ann["xyxy"])
            if score >= MIN_IOU:
                scores[di, ai] = score
                candidates.append(ai)
        adjacency.append(sorted(candidates, key=lambda ai: (-scores[di, ai], ai)))
    assignment = {}

    def augment(di, visited):
        for ai in adjacency[di]:
            if ai in visited:
                continue
            visited.add(ai)
            if ai not in assignment or augment(assignment[ai], visited):
                assignment[ai] = di
                return True
        return False

    for di in range(len(detections)):
        augment(di, set())
    return sorted(((di, ai, scores[di, ai]) for ai, di in assignment.items()),
                  key=lambda hit: hit[0])


def rate_stats(rows, key):
    values = [float(r[key]) for r in rows if r[key] is not None]
    return {"available_pairs": len(values), "median_absolute_center_discrepancy_m":
            round(statistics.median(values), 3) if values else None,
            "mean_absolute_center_discrepancy_m": round(statistics.mean(values), 3)
            if values else None,
            "absolute_discrepancies_over_1m": sum(v > 1.0 for v in values)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path("manifests/holdout_memorial_scoring.json"))
    parser.add_argument("--data-root", type=Path,
                        default=Path("data/jrdb2022/holdout_reference"))
    parser.add_argument("--labels-zip", type=Path,
                        default=Path.home() / "Downloads/labels.zip")
    parser.add_argument("--candidates", type=Path,
                        default=Path("outputs/local/memorial_court_holdout/memorial_sensor_surface_full.csv"))
    parser.add_argument("--candidate-summary", type=Path,
                        default=Path("outputs/local/memorial_court_holdout/memorial_sensor_surface_summary.json"))
    parser.add_argument("--csv", type=Path,
                        default=Path("outputs/local/memorial_court_holdout/memorial_surface_reference_holdout.csv"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if (
        manifest.get("role") != "frozen_holdout_scoring"
        or manifest.get("sequence") != SEQUENCE
    ):
        parser.error(
            "Only the frozen Memorial Court scoring manifest "
            "is accepted"
        )

    if float(manifest.get("matching_2d_iou_threshold")) != MIN_IOU:
        parser.error("Frozen IoU threshold mismatch")

    if float(manifest.get("near_radius_m")) != NEAR_RADIUS_M:
        parser.error("Frozen 3 m boundary mismatch")

    if manifest.get("post_reference_tuning_allowed") is not False:
        parser.error("Holdout scoring manifest permits tuning")
    run = json.loads(args.candidate_summary.read_text())
    if (
        run.get("status") != "unvalidated_measured_surface_candidates"
        or run.get("sequence") != SEQUENCE
        or run.get("role") != "holdout_sensor_only_unscored"
    ):
        parser.error(
            "Candidate summary differs from frozen "
            "Memorial Court sensor run"
        )
    frames = run["frames"]
    if not frames or len(frames) != len(set(frames)) or any(
            not isinstance(frame, str) or len(frame) != 6 or not frame.isdecimal()
            for frame in frames):
        parser.error("Invalid candidate frame list")
    with args.candidates.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        required = {"frame", "camera", "box_index", "xyxy", "confidence",
                    "nearest_supported_surface_m", "surface_candidate_status",
                    "surface_candidate_ego_xy_m"}
        if not required.issubset(reader.fieldnames or []):
            parser.error("Incomplete measured-surface candidate CSV")
        raw = list(reader)
    if len(raw) != run.get("boxes"):
        parser.error("Candidate CSV and summary disagree on number of boxes")
    detections = defaultdict(list)
    for row in raw:
        frame = row["frame"]
        camera = int(row["camera"])
        if frame not in frames or camera not in CAMERAS:
            raise ValueError(f"Unexpected frame or camera in candidates: {frame}/{camera}")
        coords = json.loads(row["xyxy"])
        if (len(coords) != 4 or not all(isinstance(v, (float, int)) and
                not isinstance(v, bool) and math.isfinite(v) for v in coords)
                or not 0 <= coords[0] < coords[2] <= 753 or not
                0 <= coords[1] < coords[3] <= 481):
            raise ValueError(f"Invalid raw detector rectangle {frame}/{camera}")
        row["xyxy"] = coords
        row["nearest_supported_surface_m"] = optional_float(
            row["nearest_supported_surface_m"], "nearest_supported_surface_m")
        row["surface_candidate_ego_xy_m"] = optional_float(
            row["surface_candidate_ego_xy_m"], "surface_candidate_ego_xy_m")
        detections[frame, camera].append(row)
    for frame in frames:
        for camera in CAMERAS:
            boxes = detections[frame, camera]
            indices = [int(d["box_index"]) for d in boxes]
            if indices != list(range(len(boxes))):
                raise ValueError(f"Nonconsecutive detector box indices at {frame}/{camera}")
    root = args.data_root / SEQUENCE
    labels_3d_path = root / manifest["label_3d"]
    label_file = json.loads(labels_3d_path.read_text())["labels"]
    reference_3d = {}
    for frame in frames:
        points_key = frame + ".pcd"
        if points_key not in label_file:
            raise ValueError(f"Missing 3D reference frame {points_key}")
        d = {}
        for item in label_file[points_key]:
            person = item.get("label_id")
            if not isinstance(person, str) or not person.startswith("pedestrian:"):
                continue
            if (item.get("attributes") or {}).get("no_eval") is not False:
                continue
            box = item.get("box") or {}
            radius = math.hypot(float(box["cx"]), float(box["cy"]))
            if not math.isfinite(radius) or radius < 0:
                raise ValueError("Nonfinite 3D reference radius")
            if person in d:
                raise ValueError(f"Repeated annotated 3D ID {person} at {frame}")
            d[person] = radius
        reference_3d[frame] = d
    rows = []
    counts = Counter()
    digest_2d = hashlib.sha256()
    with zipfile.ZipFile(args.labels_zip) as archive:
        for camera in CAMERAS:
            member = f"labels/labels_2d_activity_social/{SEQUENCE}_image{camera}.json"
            content = archive.read(member)
            digest_2d.update(member.encode() + b"\0" + hashlib.sha256(content).digest())
            annotation_file = json.loads(content)
            for frame in frames:
                source_annotations = selected_image_labels(annotation_file, frame)
                if source_annotations is None:
                    raise ValueError(f"Missing native 2D labels: {frame} camera {camera}")
                references = []
                ids = set()
                for item in source_annotations:
                    if not isinstance(item, dict):
                        continue
                    person = item.get("label_id")
                    if not isinstance(person, str) or not person.startswith("pedestrian:"):
                        continue
                    attrs = item.get("attributes") or {}
                    if attrs.get("no_eval") is not False:
                        counts["2d_no_eval_or_unknown"] += 1
                        continue
                    if person in ids:
                        raise ValueError(f"Duplicate native 2D ID {person} at {frame}/{camera}")
                    ids.add(person)
                    x, y, w, h = xywh(item.get("box"))
                    references.append({"label_id": person,
                                       "xyxy": (x, y, x + w, y + h),
                                       "attrs": attrs})
                proposed = detections[frame, camera]
                matches = match_one_to_one(proposed, references)
                counts["detector_boxes"] += len(proposed)
                counts["evaluable_2d_labels"] += len(references)
                counts["matched_2d_boxes"] += len(matches)
                for di, ai, iou in matches:
                    detection = proposed[di]
                    ref = references[ai]
                    person = ref["label_id"]
                    if person not in reference_3d[frame]:
                        counts["matches_without_evaluable_3d"] += 1
                        continue
                    radius = reference_3d[frame][person]
                    near = radius <= NEAR_RADIUS_M
                    candidate = detection["surface_candidate_ego_xy_m"]
                    nearest = detection["nearest_supported_surface_m"]
                    row = {"frame": frame, "camera": camera,
                           "box_index": int(detection["box_index"]),
                           "label_id": person, "box_iou": round(iou, 4),
                           "reference_ego_xy_center_radius_m": round(radius, 4),
                           "reference_near_3m": near,
                           "candidate_status": detection["surface_candidate_status"],
                           "candidate_ego_xy_surface_m": candidate,
                           "nearest_supported_surface_m": nearest,
                           "candidate_minus_center_m": (
                               round(candidate - radius, 4) if candidate is not None else None),
                           "nearest_minus_center_m": (
                               round(nearest - radius, 4) if nearest is not None else None),
                           "candidate_absolute_center_discrepancy_m": (
                               round(abs(radius - candidate), 4) if candidate is not None else None),
                           "nearest_absolute_center_discrepancy_m": (
                               round(abs(radius - nearest), 4) if nearest is not None else None),
                           "2d_occlusion": ref["attrs"].get("occlusion"),
                           "2d_truncated": ref["attrs"].get("truncated"),
                           "2d_no_eval": False}
                    rows.append(row)
                    counts["matched_2d_and_evaluable_3d"] += 1
    if args.csv.exists():
        parser.error(f"Refusing to overwrite evaluator output: {args.csv}")
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    near = [r for r in rows if r["reference_near_3m"]]
    def describe(group):
        return {"matched_reference_pairs": len(group),
                "candidate_status_counts": dict(Counter(r["candidate_status"] for r in group)),
                "candidate_surface": rate_stats(group, "candidate_absolute_center_discrepancy_m"),
                "nearest_supported_surface": rate_stats(group, "nearest_absolute_center_discrepancy_m"),
                "median_candidate_minus_center_m": (
                    round(statistics.median(r["candidate_minus_center_m"] for r in group
                                            if r["candidate_minus_center_m"] is not None), 3)
                    if any(r["candidate_minus_center_m"] is not None for r in group) else None)}
    print(json.dumps({"status": "frozen_holdout_annotation_center_comparison",
                      "sequence": SEQUENCE, "role": "frozen_holdout_scoring",
                      "frames": frames, "matching_2d_iou_threshold": MIN_IOU,
                      "counts": dict(counts),
                      "all_matched_evaluable_3d": describe(rows),
                      "matched_3d_center_within_3m": describe(near),
                      "per_camera_3m": {str(cam): describe([r for r in near if r["camera"] == cam])
                                       for cam in CAMERAS},
                      "candidate_csv_sha256": sha256(args.candidates),
                      "candidate_summary_sha256": sha256(args.candidate_summary),
                      "label_3d_sha256": sha256(labels_3d_path),
                      "five_2d_members_combined_sha256": digest_2d.hexdigest(),
                      "csv": str(args.csv),
                      "interpretation": "Exploratory same-frame, same-camera, one-to-one "
                        "2D annotation matches. 3D ego-center XY radius is provisionally "
                        "assumed from previous geometric audits. Measured surface range "
                        "and person center are different quantities: absolute discrepancy "
                        "is not validated person-range error. Detection/annotation matches, "
                        "misses, occlusions, abstentions and camera frames are dependent; "
                        "do not report an event score or test-set result. No GT entered "
                        "the sensing script."}, indent=2))


if __name__ == "__main__":
    main()
