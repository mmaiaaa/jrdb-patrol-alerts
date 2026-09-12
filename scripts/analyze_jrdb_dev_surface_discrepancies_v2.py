#!/usr/bin/env python3
"""Audit a JRDB development-only surface/annotation comparison of any length.

Reads the sensor-only candidate CSV and the *separate* offline evaluator CSV.
All numbers are conditional diagnostics against annotated 3D center radii,
not person-range accuracy, independent calibration, or event performance.
"""

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


SEQUENCE = "cubberly-auditorium-2019-04-22_0"
REVIEW_FIELDS = (
    "priority", "frame", "camera", "box_index", "label_id", "box_iou",
    "reference_near_3m", "reference_ego_xy_center_radius_m", "candidate_status",
    "candidate_ego_xy_surface_m", "nearest_supported_surface_m",
    "candidate_minus_center_m", "candidate_absolute_center_discrepancy_m",
    "nearest_absolute_center_discrepancy_m", "2d_occlusion", "2d_truncated",
    "detection_xyxy", "reviewer_decision", "reviewer_notes",
)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError(f"Missing CSV header: {path}")
        return list(reader), set(reader.fieldnames)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def numeric(value, field):
    if value == "" or value is None:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid {field}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"Nonfinite {field}: {value!r}")
    return result


def row_key(row):
    frame = row["frame"]
    camera, index = int(row["camera"]), int(row["box_index"])
    if not (len(frame) == 6 and frame.isdecimal() and camera in (0, 2, 4, 6, 8)
            and index >= 0):
        raise ValueError(f"Invalid detector key {frame}/{camera}/{index}")
    return (frame, camera, index)


def describe(values):
    return {"pairs": len(values),
            "median_m": round(statistics.median(values), 3) if values else None,
            "mean_m": round(statistics.mean(values), 3) if values else None}


def compare(rows):
    # Same exact frame/camera/detector box on both sides of this comparison.
    paired = [row for row in rows if row["candidate"] is not None and
              row["nearest"] is not None]
    candidate = [abs(row["candidate"] - row["center"]) for row in paired]
    nearest = [abs(row["nearest"] - row["center"]) for row in paired]
    return {"matched_reference_pairs": len(rows),
            "candidate_available_pairs": sum(row["candidate"] is not None for row in rows),
            "nearest_available_pairs": sum(row["nearest"] is not None for row in rows),
            "paired_pairs": len(paired),
            "candidate_absolute_center_discrepancy_m": describe(candidate),
            "nearest_absolute_center_discrepancy_m": describe(nearest),
            "paired_candidate_better_by_more_than_0_25m": sum(
                a + 0.25 < b for a, b in zip(candidate, nearest)),
            "paired_nearest_better_by_more_than_0_25m": sum(
                b + 0.25 < a for a, b in zip(candidate, nearest)),
            "paired_difference_within_0_25m": sum(
                abs(a - b) <= 0.25 for a, b in zip(candidate, nearest))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-csv", type=Path, default=Path(
        "outputs/local/cubberly_surface_reference_diagnostic.csv"))
    parser.add_argument("--reference-summary", type=Path, default=Path(
        "outputs/local/cubberly_surface_reference_summary.json"))
    parser.add_argument("--candidate-csv", type=Path, default=Path(
        "outputs/local/cubberly_sensor_surface_candidates.csv"))
    parser.add_argument("--review-csv", type=Path, default=Path(
        "outputs/local/cubberly_surface_priority_review.csv"))
    parser.add_argument("--compact", action="store_true",
                        help="Omit verbose per-frame comparisons from full-sequence JSON")
    args = parser.parse_args()
    if args.review_csv.exists():
        parser.error(f"Refusing to overwrite review worklist: {args.review_csv}")

    summary = json.loads(args.reference_summary.read_text(encoding="utf-8"))
    if (summary.get("sequence") != SEQUENCE or summary.get("role") != "development_only"
            or summary.get("status") != "development_annotation_center_discrepancy_only"):
        parser.error("Expected Cubberly development-only reference summary")
    if sha256(args.candidate_csv) != summary.get("candidate_csv_sha256"):
        parser.error("Candidate CSV differs from reference evaluator input")

    candidates, candidate_fields = read_csv(args.candidate_csv)
    references, reference_fields = read_csv(args.reference_csv)
    required_candidate = {"frame", "camera", "box_index", "xyxy", "surface_candidate_status",
                          "surface_candidate_ego_xy_m", "nearest_supported_surface_m"}
    required_reference = {"frame", "camera", "box_index", "label_id", "box_iou",
                          "reference_ego_xy_center_radius_m", "reference_near_3m",
                          "candidate_status", "candidate_ego_xy_surface_m",
                          "nearest_supported_surface_m", "2d_occlusion", "2d_truncated"}
    if not required_candidate <= candidate_fields or not required_reference <= reference_fields:
        parser.error("One or both CSV inputs lack required columns")
    if len(candidates) != summary.get("counts", {}).get("detector_boxes"):
        parser.error("Candidate count differs from evaluator summary")
    if len(references) != summary.get("counts", {}).get("matched_2d_and_evaluable_3d"):
        parser.error("Linked reference count differs from evaluator summary")

    by_detection = {}
    for row in candidates:
        key = row_key(row)
        if key in by_detection:
            raise ValueError(f"Duplicate detector key: {key}")
        by_detection[key] = row
    linked = []
    linked_keys = set()
    worklist = []
    per_frame = defaultdict(list)
    for ref in references:
        key = row_key(ref)
        if key not in by_detection:
            raise ValueError(f"Reference detector key absent from sensor CSV: {key}")
        raw = by_detection[key]
        center = numeric(ref["reference_ego_xy_center_radius_m"], "reference center")
        candidate = numeric(ref["candidate_ego_xy_surface_m"], "candidate surface")
        nearest = numeric(ref["nearest_supported_surface_m"], "nearest surface")
        if center is None or center < 0:
            raise ValueError(f"Invalid 3D center radius at {key}")
        if ref["reference_near_3m"].lower() not in ("true", "false"):
            raise ValueError(f"Invalid near-3m field at {key}")
        near = ref["reference_near_3m"].lower() == "true"
        if near != (center <= 3.0):
            raise ValueError(f"Near-3m flag disagrees with center radius at {key}")
        if (raw["surface_candidate_status"] != ref["candidate_status"] or
                numeric(raw["surface_candidate_ego_xy_m"], "raw candidate") != candidate or
                numeric(raw["nearest_supported_surface_m"], "raw nearest") != nearest):
            raise ValueError(f"Raw/evaluator candidate disagreement at {key}")
        if candidate is not None and candidate < 0 or nearest is not None and nearest < 0:
            raise ValueError(f"Negative candidate radius at {key}")
        if key in linked_keys:
            raise ValueError(f"Duplicate reference detector key: {key}")
        linked_keys.add(key)
        item = {"key": key, "center": center, "candidate": candidate,
                "nearest": nearest, "near": near, "ref": ref, "raw": raw}
        linked.append(item)
        per_frame[key[0]].append(item)
        deviation = abs(candidate - center) if candidate is not None else None
        if near and candidate is None:
            priority = "1_near_reference_abstained"
        elif deviation is not None and deviation > 1.0:
            priority = "2_candidate_over_1m_from_center"
        elif candidate is not None and nearest is not None and (
                abs(nearest - center) - deviation) > 1.0:
            priority = "3_nearest_band_over_1m_worse"
        else:
            continue
        worklist.append(make_review_row(priority, item))
    for key, raw in by_detection.items():
        if key in linked_keys:
            continue
        candidate = numeric(raw["surface_candidate_ego_xy_m"], "unlinked candidate")
        if candidate is not None and candidate <= 3.0:
            worklist.append(make_review_row("4_unlinked_candidate_within_3m",
                                            {"key": key, "raw": raw, "ref": {}}))
    worklist.sort(key=lambda row: (row["priority"], row["frame"],
                                   int(row["camera"]), int(row["box_index"])))
    args.review_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.review_csv.open("x", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(worklist)

    near_rows = [r for r in linked if r["near"]]
    result = {"status": "development_paired_center_discrepancy_triage_only",
              "sequence": SEQUENCE, "role": "development_only",
              "input_frame_ids": ([] if args.compact else sorted(per_frame)),
              "linked_frame_count": len(per_frame),
              "detector_boxes": len(candidates),
              "matched_2d_and_evaluable_3d_pairs": len(linked),
              "unlinked_detector_boxes": len(candidates) - len(linked),
              "all_linked": compare(linked), "center_within_3m": compare(near_rows),
              "unique_near_frame_label_ids": len({
                  (r["key"][0], r["ref"]["label_id"]) for r in near_rows}),
              "near_linked_frame_count": len({r["key"][0] for r in near_rows}),
              "near_pairs_by_frame": ({} if args.compact else dict(sorted(
                  Counter(r["key"][0] for r in near_rows).items()))),
              "per_frame": ({} if args.compact else
                            {frame: compare(rows) for frame, rows in sorted(per_frame.items())}),
              "per_frame_omitted": args.compact,
              "review_priority_counts": dict(Counter(r["priority"] for r in worklist)),
              "review_csv": str(args.review_csv),
              "reference_csv_sha256": sha256(args.reference_csv),
              "candidate_csv_sha256": sha256(args.candidate_csv),
              "interpretation": "Paired discrepancies use the SAME matched frame-camera-box "
                  "for candidate and nearest surfaces. GT center and measured surface are "
                  "different physical quantities; low discrepancy is not person-range accuracy. "
                  "Unlinked candidates are review leads, not false positives. Multiple camera "
                  "views of one person and adjacent frames are dependent. Do not treat this "
                  "development recording as an event, held-out, or system-level result."}
    print(json.dumps(result, indent=2))


def make_review_row(priority, item):
    raw, ref = item["raw"], item["ref"]
    values = {"priority": priority, "frame": item["key"][0],
              "camera": item["key"][1], "box_index": item["key"][2],
              "label_id": ref.get("label_id", ""), "box_iou": ref.get("box_iou", ""),
              "reference_near_3m": ref.get("reference_near_3m", ""),
              "reference_ego_xy_center_radius_m": ref.get(
                  "reference_ego_xy_center_radius_m", ""),
              "candidate_status": raw["surface_candidate_status"],
              "candidate_ego_xy_surface_m": raw["surface_candidate_ego_xy_m"],
              "nearest_supported_surface_m": raw["nearest_supported_surface_m"],
              "candidate_minus_center_m": ref.get("candidate_minus_center_m", ""),
              "candidate_absolute_center_discrepancy_m": ref.get(
                  "candidate_absolute_center_discrepancy_m", ""),
              "nearest_absolute_center_discrepancy_m": ref.get(
                  "nearest_absolute_center_discrepancy_m", ""),
              "2d_occlusion": ref.get("2d_occlusion", ""),
              "2d_truncated": ref.get("2d_truncated", ""),
              "detection_xyxy": raw["xyxy"],
              "reviewer_decision": "", "reviewer_notes": ""}
    return values


if __name__ == "__main__":
    main()
