#!/usr/bin/env python3
"""Development-only, label-assisted review of exploratory 3 m crossings.

Run AFTER sensor-only surface generation and separate offline reference matching.
This cannot estimate event-level recall, false alerts or operational safety.
"""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


SEQUENCE = "cubberly-auditorium-2019-04-22_0"
RADIUS_M = 3.0
MARGIN_M = 0.25
HEADERS = ("review_reason", "frame", "camera", "box_index", "label_id",
           "reference_ego_xy_center_radius_m", "candidate_ego_xy_surface_m",
           "nearest_supported_surface_m", "reference_center_within_3m",
           "candidate_status", "box_iou", "2d_occlusion", "2d_truncated",
           "detector_box_xyxy", "human_decision", "human_notes")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path, required):
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"Missing required columns: {path}")
        return list(reader)


def finite_optional(value, name):
    if value is None or value == "":
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Invalid {name}: {value}")
    return number


def key(row):
    frame = row["frame"]
    camera, box_index = int(row["camera"]), int(row["box_index"])
    if (len(frame) != 6 or not frame.isdecimal() or camera not in (0, 2, 4, 6, 8)
            or box_index < 0):
        raise ValueError("Invalid frame, camera or box index")
    return (frame, camera, box_index)


def worklist_row(reason, detection, reference=None):
    reference = reference or {}
    return {"review_reason": reason, "frame": detection["frame"],
            "camera": detection["camera"], "box_index": detection["box_index"],
            "label_id": reference.get("label_id", ""),
            "reference_ego_xy_center_radius_m": reference.get(
                "reference_ego_xy_center_radius_m", ""),
            "candidate_ego_xy_surface_m": detection["surface_candidate_ego_xy_m"],
            "nearest_supported_surface_m": detection["nearest_supported_surface_m"],
            "reference_center_within_3m": reference.get("reference_near_3m", ""),
            "candidate_status": detection["surface_candidate_status"],
            "box_iou": reference.get("box_iou", ""),
            "2d_occlusion": reference.get("2d_occlusion", ""),
            "2d_truncated": reference.get("2d_truncated", ""),
            "detector_box_xyxy": detection["xyxy"],
            "human_decision": "", "human_notes": ""}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-csv", type=Path, default=Path(
        "outputs/local/cubberly_sensor_surface_candidates.csv"))
    parser.add_argument("--reference-csv", type=Path, default=Path(
        "outputs/local/cubberly_surface_reference_diagnostic.csv"))
    parser.add_argument("--reference-summary", type=Path, default=Path(
        "outputs/local/cubberly_surface_reference_summary.json"))
    parser.add_argument("--review-csv", type=Path, default=Path(
        "outputs/local/cubberly_threshold_crossing_review.csv"))
    args = parser.parse_args()
    if args.review_csv.exists():
        parser.error(f"Refusing to replace review worklist: {args.review_csv}")
    summary = json.loads(args.reference_summary.read_text(encoding="utf-8"))
    if (summary.get("sequence") != SEQUENCE or summary.get("role") != "development_only"
            or summary.get("status") != "development_annotation_center_discrepancy_only"):
        parser.error("Requires the Cubberly development reference summary")
    if digest(args.candidate_csv) != summary.get("candidate_csv_sha256"):
        parser.error("Sensor candidate CSV differs from the offline reference input")
    candidates = read(args.candidate_csv, {"frame", "camera", "box_index", "xyxy",
        "surface_candidate_status", "surface_candidate_ego_xy_m", "nearest_supported_surface_m"})
    refs = read(args.reference_csv, {"frame", "camera", "box_index", "label_id",
        "reference_ego_xy_center_radius_m", "reference_near_3m", "candidate_ego_xy_surface_m",
        "candidate_status", "nearest_supported_surface_m", "box_iou", "2d_occlusion",
        "2d_truncated"})
    counts = summary.get("counts", {})
    if (len(candidates) != counts.get("detector_boxes") or
            len(refs) != counts.get("matched_2d_and_evaluable_3d")):
        parser.error("CSV row counts disagree with offline reference summary")
    sensor = {}
    for row in candidates:
        k = key(row)
        if k in sensor:
            raise ValueError(f"Repeated detector box {k}")
        sensor[k] = row
    matched = set()
    groups = defaultdict(list)
    conditions = Counter()
    worklist = []
    ref_near_views = 0
    border_views = 0
    for row in refs:
        k = key(row)
        if k in matched or k not in sensor:
            raise ValueError(f"Repeated or unlinked reference box {k}")
        matched.add(k)
        raw = sensor[k]
        center = finite_optional(row["reference_ego_xy_center_radius_m"], "center")
        candidate = finite_optional(row["candidate_ego_xy_surface_m"], "candidate")
        if center is None or row["reference_near_3m"].lower() not in ("true", "false"):
            raise ValueError(f"Invalid reference near flag or center at {k}")
        near = center <= RADIUS_M
        if near != (row["reference_near_3m"].lower() == "true"):
            raise ValueError(f"Near flag contradicts reference center at {k}")
        if (row["candidate_status"] != raw["surface_candidate_status"] or
                candidate != finite_optional(raw["surface_candidate_ego_xy_m"], "raw candidate") or
                finite_optional(row["nearest_supported_surface_m"], "nearest") !=
                finite_optional(raw["nearest_supported_surface_m"], "raw nearest")):
            raise ValueError(f"Sensor/reference disagreement at {k}")
        ref_near_views += near
        border_views += abs(center - RADIUS_M) <= MARGIN_M
        if near and candidate is None:
            state = "near_center_abstained"
        elif near and candidate > RADIUS_M:
            state = "near_center_candidate_outside"
        elif not near and candidate is not None and candidate <= RADIUS_M:
            state = "far_center_candidate_inside"
        elif not near and candidate is None:
            state = "far_center_abstained"
        else:
            state = "same_side"
        conditions[state] += 1
        g = (k[0], row["label_id"])
        if not isinstance(g[1], str) or not g[1].startswith("pedestrian:"):
            raise ValueError(f"Unexpected label ID at {k}")
        groups[g].append((near, state))
        if state in ("near_center_abstained", "near_center_candidate_outside",
                     "far_center_candidate_inside"):
            worklist.append(worklist_row(state, raw, row))
    unlinked_inside = 0
    for k, raw in sensor.items():
        if k not in matched and (candidate := finite_optional(
                raw["surface_candidate_ego_xy_m"], "unlinked candidate")) is not None:
            if candidate <= RADIUS_M:
                unlinked_inside += 1
                worklist.append(worklist_row("unlinked_candidate_inside_3m", raw))
    if ref_near_views != summary["matched_3d_center_within_3m"]["matched_reference_pairs"]:
        parser.error("Near-reference count disagrees with offline evaluator")
    near_groups = {g: values for g, values in groups.items() if values[0][0]}
    far_groups = {g: values for g, values in groups.items() if not values[0][0]}
    if any(any(near != values[0][0] for near, _ in values) for values in groups.values()):
        raise ValueError("Same annotated frame/person has contradictory near flags")
    worklist.sort(key=lambda row: (row["review_reason"], row["frame"],
                                   int(row["camera"]), int(row["box_index"])))
    args.review_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.review_csv.open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(worklist)
    print(json.dumps({
        "status": "development_exploratory_threshold_discordance_only",
        "sequence": SEQUENCE, "role": "development_only", "radius_m": RADIUS_M,
        "linked_frame_camera_box_views": len(refs), "annotated_center_inside_3m_views": ref_near_views,
        "linked_center_within_0_25m_of_threshold_views": border_views,
        "linked_view_status_counts": dict(conditions),
        "unique_near_frame_person_ids": len(near_groups),
        "unique_near_ids_with_any_linked_view_candidate_inside_3m": sum(
            any(state == "same_side" for _, state in values) for values in near_groups.values()),
        "unique_near_ids_with_only_linked_views_abstaining": sum(
            all(state == "near_center_abstained" for _, state in values)
            for values in near_groups.values()),
        "unique_far_frame_person_ids": len(far_groups),
        "unique_far_ids_with_any_linked_view_candidate_inside_3m": sum(
            any(state == "far_center_candidate_inside" for _, state in values)
            for values in far_groups.values()),
        "unlinked_detector_boxes": len(sensor) - len(matched),
        "unlinked_candidate_inside_3m_views_for_review": unlinked_inside,
        "review_csv": str(args.review_csv),
        "candidate_csv_sha256": digest(args.candidate_csv),
        "reference_csv_sha256": digest(args.reference_csv),
        "interpretation": "Exploratory 3m threshold discordance conditional on IoU-matched "
            "2D labels and evaluable 3D centers. Sensor surfaces and annotated geometric "
            "centers differ physically; neither crossing proves a person alert error. "
            "Unlinked close candidates are unknowns, not false alerts. Grouped frame/person "
            "IDs include only linked native views, with correlated camera observations; "
            "this is not detection recall, event accuracy, or held-out performance. "
            "Never provide annotations to the sensor-only inference code."
    }, indent=2))


if __name__ == "__main__":
    main()
