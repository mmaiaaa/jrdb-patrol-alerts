#!/usr/bin/env python3
"""Sample a bounded, blinded Cubberly development quality-control worklist.

Reference labels are read OFFLINE to stratify cases. The two review sheets
contain only source frame, camera and detector box; a separate key retains
the strata and reference metadata. This does not produce ground truth itself.
"""

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path


SEQUENCE = "cubberly-auditorium-2019-04-22_0"
QUOTAS = {
    "far_center_candidate_inside": 12,
    "near_center_candidate_outside": 12,
    "near_center_abstained": 12,
    "unlinked_candidate_inside_3m": 18,
    "control_near": 6,
    "control_far": 6,
}
REVIEW_FIELDS = ("case_id", "sequence", "frame", "camera", "detector_box_xyxy",
                 "context_from_frame", "context_through_frame", "person_visible_in_box",
                 "association_clear", "foreground_surface_clear", "occlusion_or_edge_issue",
                 "reviewer_confidence", "reviewer_notes")
KEY_FIELDS = ("case_id", "reason", "frame", "camera", "box_index", "label_id",
              "reference_center_m", "candidate_surface_m", "nearest_surface_m",
              "2d_occlusion", "2d_truncated", "box_iou", "selection_group")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_csv(path, required):
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not required <= set(reader.fieldnames or ()):
            raise ValueError(f"Missing required columns in {path}")
        return list(reader)


def identity(row):
    return row["frame"], int(row["camera"]), int(row["box_index"])


def number(value):
    if value in (None, ""):
        return None
    out = float(value)
    if not math.isfinite(out) or out < 0:
        raise ValueError(f"Invalid distance {value!r}")
    return out


def group_for(row):
    block = int(row["frame"]) // 30
    if row["label_id"]:
        return f"annotated:{row['label_id']}:block_{block}"
    xyxy = json.loads(row["detector_box_xyxy"])
    if len(xyxy) != 4:
        raise ValueError("Expected four detector box coordinates")
    cx, cy = (xyxy[0] + xyxy[2]) / 2, (xyxy[1] + xyxy[3]) / 2
    if not math.isfinite(cx) or not math.isfinite(cy):
        raise ValueError("Nonfinite detector box")
    return f"unlinked:cam_{row['camera']}:block_{block}:tile_{int(cx//100)}_{int(cy//120)}"


def draw(pool, limit, seed):
    rng = random.Random(seed)
    groups = defaultdict(list)
    for row in pool:
        groups[group_for(row)].append(row)
    names = sorted(groups)
    rng.shuffle(names)
    selected = []
    for name in names[:limit]:
        selected.append(rng.choice(groups[name]))
    # If there are fewer groups than the quota, fill from remaining rows.
    if len(selected) < limit:
        chosen = {identity(row) for row in selected}
        remainder = [row for row in pool if identity(row) not in chosen]
        rng.shuffle(remainder)
        selected.extend(remainder[:limit-len(selected)])
    return selected, len(groups)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold-summary", type=Path, default=Path(
        "outputs/local/cubberly_threshold_crossing_full_summary_v2.json"))
    parser.add_argument("--threshold-review", type=Path, default=Path(
        "outputs/local/cubberly_threshold_crossing_full_review_v2.csv"))
    parser.add_argument("--reference-csv", type=Path, default=Path(
        "outputs/local/cubberly_surface_reference_full.csv"))
    parser.add_argument("--candidate-csv", type=Path, default=Path(
        "outputs/local/cubberly_sensor_surface_full.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path(
        "outputs/local/cubberly_blinded_review"))
    parser.add_argument("--seed", type=int, default=20260912)
    args = parser.parse_args()
    names = ("reviewer_a.csv", "reviewer_b.csv", "review_key.csv", "frames.txt")
    if any((args.output_dir / name).exists() for name in names):
        parser.error("Refusing to replace an existing review packet")
    summary = json.loads(args.threshold_summary.read_text(encoding="utf-8"))
    if (summary.get("sequence") != SEQUENCE or summary.get("role") != "development_only" or
            summary.get("status") != "development_exploratory_threshold_discordance_only"):
        parser.error("Expected full Cubberly development threshold summary")
    if (sha256(args.reference_csv) != summary.get("reference_csv_sha256") or
            sha256(args.candidate_csv) != summary.get("candidate_csv_sha256")):
        parser.error("Source CSV hash differs from threshold audit")
    raw = load_csv(args.candidate_csv, {"frame", "camera", "box_index", "xyxy",
                                       "surface_candidate_ego_xy_m"})
    refs = load_csv(args.reference_csv, {"frame", "camera", "box_index", "label_id",
        "reference_ego_xy_center_radius_m", "candidate_ego_xy_surface_m", "2d_occlusion",
        "2d_truncated", "box_iou"})
    reviewed = load_csv(args.threshold_review, {"frame", "camera", "box_index", "review_reason",
        "label_id", "reference_ego_xy_center_radius_m", "candidate_ego_xy_surface_m"})
    if len(raw) != summary.get("linked_frame_camera_box_views", 0) + summary.get(
            "unlinked_detector_boxes", 0):
        parser.error("Sensor row count differs from threshold summary")
    if len(refs) != summary.get("linked_frame_camera_box_views"):
        parser.error("Reference row count differs from threshold summary")
    sensor = {identity(row): row for row in raw}
    reference = {identity(row): row for row in refs}
    if len(sensor) != len(raw) or len(reference) != len(refs):
        raise ValueError("Duplicate detector or reference keys")
    pools = defaultdict(list)
    reviewed_keys = set()
    for row in reviewed:
        k = identity(row)
        if k in reviewed_keys or k not in sensor:
            raise ValueError(f"Repeated or unknown threshold review row {k}")
        reviewed_keys.add(k)
        reason = row["review_reason"]
        if reason not in QUOTAS or reason.startswith("control_"):
            raise ValueError(f"Unexpected threshold review reason: {reason}")
        ref = reference.get(k, {})
        if ref.get("label_id", "") != row["label_id"]:
            raise ValueError(f"Mismatched reference identity in review row {k}")
        if (number(row["candidate_ego_xy_surface_m"]) !=
                number(sensor[k]["surface_candidate_ego_xy_m"])):
            raise ValueError(f"Review candidate changed at {k}")
        pools[reason].append(make_case(reason, sensor[k], ref))
    expected = summary["linked_view_status_counts"]
    for reason in QUOTAS:
        if reason.startswith("control_"):
            continue
        count = (summary["unlinked_candidate_inside_3m_views_for_review"]
                 if reason == "unlinked_candidate_inside_3m" else expected[reason])
        if len(pools[reason]) != count:
            raise ValueError(f"Worklist count differs from summary: {reason}")
    for ref in refs:
        k = identity(ref)
        candidate = number(ref["candidate_ego_xy_surface_m"])
        center = number(ref["reference_ego_xy_center_radius_m"])
        if candidate is None or center is None or abs(center - 3.0) <= 0.25:
            continue
        if (candidate <= 3.0) == (center <= 3.0):
            reason = "control_near" if center <= 3.0 else "control_far"
            pools[reason].append(make_case(reason, sensor[k], ref))
    selected = []
    meta = {}
    for reason, quota in QUOTAS.items():
        picked, group_count = draw(pools[reason], quota, f"{args.seed}:{reason}")
        meta[reason] = {"population_rows": len(pools[reason]),
                        "temporal_spatial_groups": group_count,
                        "sampled_rows": len(picked)}
        selected.extend(picked)
    random.Random(args.seed).shuffle(selected)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sheets = []
    key_rows = []
    for i, row in enumerate(selected, start=1):
        case_id = f"D{i:03d}"
        frame_number = int(row["frame"])
        sheets.append({"case_id": case_id, "sequence": SEQUENCE,
                       "frame": row["frame"], "camera": row["camera"],
                       "detector_box_xyxy": row["detector_box_xyxy"],
                       "context_from_frame": f"{max(0, frame_number-5):06d}",
                       "context_through_frame": f"{min(1295, frame_number+5):06d}",
                       **{field: "" for field in REVIEW_FIELDS[7:]}})
        key_rows.append({"case_id": case_id, **{field: row.get(field, "")
                         for field in KEY_FIELDS if field != "case_id"}})
    for suffix in ("a", "b"):
        with (args.output_dir / f"reviewer_{suffix}.csv").open("x", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
            writer.writeheader(); writer.writerows(sheets)
    with (args.output_dir / "review_key.csv").open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=KEY_FIELDS)
        writer.writeheader(); writer.writerows(key_rows)
    (args.output_dir / "frames.txt").write_text(
        "\n".join(sorted({row["frame"] for row in selected})) + "\n", encoding="utf-8")
    print(json.dumps({"status": "development_blinded_quality_review_packet",
                      "sequence": SEQUENCE, "role": "development_only", "seed": args.seed,
                      "review_sheet_rows": len(selected),
                      "distinct_review_frames": len({row["frame"] for row in selected}),
                      "strata": meta, "output_dir": str(args.output_dir),
                      "reference_csv_sha256": sha256(args.reference_csv),
                      "candidate_csv_sha256": sha256(args.candidate_csv),
                      "interpretation": "Deterministic case diversity sample, not a random sample "
                          "of independent encounters or an unbiased error estimator. "
                          "Reviewer sheets hide selection strata and annotations; "
                          "the separate review key is for later analysis. "
                          "Unknown is an appropriate human response."}, indent=2))


def make_case(reason, detector, ref):
    frame, camera, index = identity(detector)
    case = {"reason": reason, "frame": frame, "camera": camera, "box_index": index,
            "detector_box_xyxy": detector["xyxy"], "label_id": ref.get("label_id", ""),
            "reference_center_m": ref.get("reference_ego_xy_center_radius_m", ""),
            "candidate_surface_m": detector["surface_candidate_ego_xy_m"],
            "nearest_surface_m": detector.get("nearest_supported_surface_m", ""),
            "2d_occlusion": ref.get("2d_occlusion", ""),
            "2d_truncated": ref.get("2d_truncated", ""),
            "box_iou": ref.get("box_iou", "")}
    case["selection_group"] = group_for(case)
    return case


if __name__ == "__main__":
    main()
