#!/usr/bin/env python3
"""Offline, same-track JRDB development projection check against native 2D labels.

2D and 3D labels are *reference data*, used only by this audit. This is not an
independent detector evaluation or a source for runtime person range estimates.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from audit_jrdb_cubberly_projection import project
from audit_jrdb_dev_box_geometry import upper_to_ego
from inspect_jrdb_dev_native_2d_reference import selected_image_labels


SEQUENCE = "cubberly-auditorium-2019-04-22_0"
FRAMES = ("000087", "000432", "000864", "001295")
CAMERAS = (0, 2, 4, 6, 8)
SIZE = (752, 480)
FIELDS = ("frame", "camera", "label_id", "3d_xy_radius_m", "2d_box_xywh",
          "2d_no_eval", "2d_occlusion", "2d_truncated", "upper_center_uv",
          "upper_center_status", "upper_outside_box_px", "ego_center_uv",
          "ego_center_status", "ego_outside_box_px")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def xywh(raw):
    """Validate the JRDB paper's [x, y, width, height] 2D box convention."""
    if isinstance(raw, dict):
        if not {"x", "y", "w", "h"}.issubset(raw):
            raise ValueError("2D dictionary box lacks x/y/w/h")
        values = [raw[k] for k in ("x", "y", "w", "h")]
    elif isinstance(raw, (list, tuple)) and len(raw) == 4:
        values = raw
    else:
        raise ValueError("2D box is neither a four-number sequence nor x/y/w/h dictionary")
    if any(isinstance(v, bool) for v in values):
        raise ValueError("Boolean value in 2D box")
    try:
        x, y, width, height = (float(v) for v in values)
    except (TypeError, ValueError) as exc:
        raise ValueError("Non-numeric 2D box") from exc
    if not all(map(math.isfinite, (x, y, width, height))) or width <= 0 or height <= 0:
        raise ValueError("Nonfinite or nonpositive 2D box")
    return x, y, width, height


def compare_center(point, box, sensor):
    uv, _, _ = project(point.reshape((1, 3)), sensor, SIZE)
    if not len(uv):
        return "outside_camera_image", None, None
    u, v = (float(coord) for coord in uv[0])
    x, y, width, height = box
    du = max(x - u, 0., u - (x + width))
    dv = max(y - v, 0., v - (y + height))
    miss = math.hypot(du, dv)
    return ("inside_2d_box" if miss == 0 else "outside_2d_box",
            [round(u, 2), round(v, 2)], round(miss, 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--labels-zip", type=Path, default=Path.home() / "Downloads/labels.zip")
    parser.add_argument("--frames", nargs="+", default=FRAMES)
    parser.add_argument("--csv", type=Path,
                        default=Path("outputs/local/cubberly_native_2d_3d_reprojection.csv"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only" or manifest.get("sequence") != SEQUENCE:
        parser.error("This audit accepts only the Cubberly development manifest")
    if not args.frames or len(args.frames) != len(set(args.frames)) or any(
            not frame.isdecimal() or len(frame) != 6 for frame in args.frames):
        parser.error("Provide distinct six-digit numeric frames")
    root = args.data_root / SEQUENCE
    label_path = root / manifest["label_3d"]
    calibration_path = root / "calibration/lidars.yaml"
    three_d = json.loads(label_path.read_text())["labels"]
    calibration = yaml.safe_load(calibration_path.read_text())
    sensors = {cam: calibration[f"sensor_{cam}"] for cam in CAMERAS}
    transform = np.asarray(calibration["lidar"]["upper2ego"], dtype=np.float64)
    upper_to_ego(np.zeros((1, 3)), transform)  # Validate before inversion.
    ego2upper = np.linalg.inv(transform)
    near = {}
    for frame in args.frames:
        if frame + ".pcd" not in three_d:
            raise ValueError(f"3D reference frame absent: {frame}")
        persons = {}
        for item in three_d[frame + ".pcd"]:
            person = str(item.get("label_id", ""))
            if not person.startswith("pedestrian:") or (item.get("attributes") or {}).get("no_eval") is not False:
                continue
            box = item.get("box") or {}
            try:
                coords = np.array([box[k] for k in ("cx", "cy", "cz")], dtype=float)
            except (KeyError, TypeError, ValueError):
                continue
            if not np.isfinite(coords).all() or np.linalg.norm(coords[:2]) > 3.0:
                continue
            if person in persons:
                raise ValueError(f"Duplicate 3D ID at {frame}: {person}")
            persons[person] = coords
        near[frame] = persons
    rows = []
    unsupported = []
    box_types = Counter()
    area_ratios = []
    matched_ids = {frame: set() for frame in args.frames}
    digest = hashlib.sha256()
    with zipfile.ZipFile(args.labels_zip) as archive:
        for camera in CAMERAS:
            member = f"labels/labels_2d_activity_social/{SEQUENCE}_image{camera}.json"
            raw = archive.read(member)
            digest.update(member.encode() + b"\0" + hashlib.sha256(raw).digest())
            payload = json.loads(raw)
            for frame in args.frames:
                annotations = selected_image_labels(payload, frame)
                if annotations is None:
                    raise ValueError(f"Expected one 2D annotation list for {member}: {frame}")
                seen = set()
                for item in annotations:
                    if not isinstance(item, dict):
                        continue
                    person = str(item.get("label_id", ""))
                    if person not in near[frame]:
                        continue
                    if person in seen:
                        raise ValueError(f"Duplicate native 2D ID {person} at {member}: {frame}")
                    seen.add(person)
                    matched_ids[frame].add(person)
                    try:
                        box = xywh(item.get("box"))
                    except ValueError as exc:
                        unsupported.append({"frame": frame, "camera": camera, "label_id": person,
                                            "box_type": type(item.get("box")).__name__,
                                            "box_example": str(item.get("box"))[:120], "reason": str(exc)})
                        continue
                    box_types[type(item["box"]).__name__] += 1
                    coords = near[frame][person]
                    upper = compare_center(coords, box, sensors[camera])
                    ego = compare_center(upper_to_ego(coords.reshape((1, 3)), ego2upper)[0],
                                         box, sensors[camera])
                    attrs = item.get("attributes") or {}
                    try:
                        area = float(attrs.get("area"))
                    except (TypeError, ValueError):
                        area = None
                    if area is not None and math.isfinite(area) and area > 0:
                        area_ratios.append((box[2] * box[3]) / area)
                    rows.append({"frame": frame, "camera": camera, "label_id": person,
                                 "3d_xy_radius_m": round(float(np.linalg.norm(coords[:2])), 3),
                                 "2d_box_xywh": json.dumps([round(n, 2) for n in box]),
                                 "2d_no_eval": attrs.get("no_eval"),
                                 "2d_occlusion": attrs.get("occlusion"),
                                 "2d_truncated": attrs.get("truncated"),
                                 "upper_center_status": upper[0],
                                 "upper_center_uv": json.dumps(upper[1]),
                                 "upper_outside_box_px": upper[2],
                                 "ego_center_status": ego[0],
                                 "ego_center_uv": json.dumps(ego[1]),
                                 "ego_outside_box_px": ego[2]})
    if unsupported:
        print(json.dumps({"status": "unsupported_2d_box_schema", "sequence": SEQUENCE,
                          "unsupported_count": len(unsupported), "examples": unsupported[:12],
                          "note": "No comparison CSV written; inspect the actual box representation."}, indent=2))
        return
    # Report plausible xywh coordinates and their relation to the source's
    # declared area before publishing a numerical comparison.
    if len(area_ratios) >= 5 and not (0.5 <= statistics.median(area_ratios) <= 2.0):
        print(json.dumps({"status": "unverified_xywh_semantics", "sequence": SEQUENCE,
                          "same_track_pairs": len(rows), "box_types": dict(box_types),
                          "sample_boxes": [
                              {k: row[k] for k in ("frame", "camera", "label_id", "2d_box_xywh")}
                              for row in rows[:5]],
                          "median_xywh_area_divided_by_reported_area": statistics.median(area_ratios),
                          "note": "No comparison CSV written. Confirm list order and area convention."}, indent=2))
        return
    if not rows:
        raise ValueError("No valid same-track near 2D/3D annotation pairs")
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    summary = {name: dict(Counter(row[f"{name}_center_status"] for row in rows))
               for name in ("upper", "ego")}
    clean = [row for row in rows if row["2d_no_eval"] is False]
    print(json.dumps({"status": "exploratory_reference_projection", "sequence": SEQUENCE,
                      "role": "development_only", "frames": args.frames,
                      "label_3d_sha256": sha256(label_path), "calibration_sha256": sha256(calibration_path),
                      "five_2d_members_combined_sha256": digest.hexdigest(),
                      "near_3d_id_counts_by_frame": {f: len(near[f]) for f in args.frames},
                      "near_3d_ids_found_in_any_native_2d_view": {
                          f: sorted(matched_ids[f]) for f in args.frames},
                      "same_track_frame_camera_pairs": len(rows),
                      "box_format": "four-number xywh sequence or x/y/w/h dictionary",
                      "source_box_types": dict(box_types),
                      "sample_2d_boxes": [
                          {k: row[k] for k in ("frame", "camera", "label_id", "2d_box_xywh")}
                          for row in rows[:5]],
                      "area_ratio_count": len(area_ratios),
                      "median_xywh_area_divided_by_reported_area": (
                          statistics.median(area_ratios) if area_ratios else None),
                      "projection_statuses_all_pairs": summary,
                      "2d_no_eval_false_pairs": len(clean),
                      "projection_statuses_2d_no_eval_false": {
                          h: dict(Counter(row[f"{h}_center_status"] for row in clean))
                          for h in ("upper", "ego")},
                      "csv": str(args.csv),
                      "interpretation": (
                          "Both 2D and 3D boxes are dataset annotations, which may share "
                          "provenance. Inside-box counts are exploratory agreement, not "
                          "independent calibration accuracy or algorithm performance. "
                          "Check sampled camera images, occlusion and time alignment before "
                          "provisionally selecting any coordinate convention. GT must never "
                          "enter the online detector, person-range estimate or alerts.")}, indent=2))


if __name__ == "__main__":
    main()
