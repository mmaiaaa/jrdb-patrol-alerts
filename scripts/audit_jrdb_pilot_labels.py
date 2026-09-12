#!/usr/bin/env python3
"""Exploratory JRDB pilot annotation inventory; this does not define alert events."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/pilot_selection.json"))
    parser.add_argument("--pilot-root", type=Path, default=Path("data/jrdb2022/pilot"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    sequence = manifest["sequence"]
    path = args.pilot_root / sequence / manifest["label_3d"]
    frames = json.loads(path.read_text())["labels"]
    if not isinstance(frames, dict):
        raise ValueError("Expected labels to map frame filenames to annotation lists")

    categories = Counter()
    flags = Counter()
    radii = (2.0, 3.0, 5.0)  # Descriptive radii only; no alert threshold selected.
    near = {str(radius): Counter() for radius in radii}
    ids = set()
    frames_with_pedestrians = set()
    distance_disagreements = 0
    people = 0

    for frame, annotations in frames.items():
        if not isinstance(annotations, list):
            raise ValueError(f"Frame {frame} does not contain an annotation list")
        for item in annotations:
            label_id = str(item.get("label_id", ""))
            category = label_id.split(":", 1)[0] or "missing"
            categories[category] += 1
            if category != "pedestrian":
                continue
            people += 1
            ids.add(label_id)
            frames_with_pedestrians.add(frame)
            attributes = item.get("attributes") or {}
            no_eval = attributes.get("no_eval")
            interpolated = attributes.get("interpolated")
            points = attributes.get("num_points")
            flags[f"no_eval={no_eval}"] += 1
            flags[f"interpolated={interpolated}"] += 1
            flags[f"num_points_zero={points == 0 if points is not None else 'unknown'}"] += 1

            box = item.get("box") or {}
            try:
                x, y = float(box["cx"]), float(box["cy"])
                if not (math.isfinite(x) and math.isfinite(y)):
                    raise ValueError("Nonfinite center")
                distance = math.hypot(x, y)
            except (KeyError, ValueError, TypeError):
                flags["invalid_or_missing_xy_center"] += 1
                continue

            annotated_distance = attributes.get("distance")
            if isinstance(annotated_distance, (int, float)) and math.isfinite(annotated_distance):
                if abs(distance - annotated_distance) > 0.5:
                    distance_disagreements += 1

            for radius in radii:
                if distance > radius:
                    continue
                counts = near[str(radius)]
                counts["all_box_observations"] += 1
                if no_eval is False:
                    counts["no_eval_false"] += 1
                    if interpolated is False:
                        counts["no_eval_false_and_not_interpolated"] += 1
                    if isinstance(points, (int, float)) and points > 0:
                        counts["no_eval_false_and_num_points_positive"] += 1

    result = {
        "sequence": sequence,
        "source_label_file": str(path),
        "number_of_annotated_frames": len(frames),
        "category_observations": dict(sorted(categories.items())),
        "pedestrian_observations": people,
        "pedestrian_ids": len(ids),
        "frames_with_pedestrians": len(frames_with_pedestrians),
        "attribute_observations": dict(sorted(flags.items())),
        "box_xy_vs_attribute_distance_differences_over_0_5m": distance_disagreements,
        "descriptive_xy_radius_m": {r: dict(sorted(v.items())) for r, v in near.items()},
        "limitations": [
            "Counts are person-frame observations, not independent encounters or alerts.",
            "XY box center distance is exploratory; coordinate frames must be verified.",
            "Labels cover 360 degrees; camera-0 visibility is not yet assessed.",
            "no_eval, interpolation, and point-count fields are reported separately.",
            "Recording time, raw-sensor inference, and moving-robot status are not established here.",
        ],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
