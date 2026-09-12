#!/usr/bin/env python3
"""Inspect JRDB native 2D reference-label schema and ID overlap on development frames.

This offline audit reads labels.zip and a development-only 3D label file. It does
not read model predictions, select a coordinate frame or score detector quality.
"""
import argparse
import json
import zipfile
from pathlib import Path


FRAMES = ("000087", "000432", "000864", "001295")
CAMERAS = (0, 2, 4, 6, 8)
SEQUENCE = "cubberly-auditorium-2019-04-22_0"


def selected_image_labels(payload, frame):
    if not isinstance(payload, dict) or not isinstance(payload.get("labels"), dict):
        return None
    matches = [value for key, value in payload["labels"].items()
               if Path(key).stem == frame]
    if len(matches) != 1 or not isinstance(matches[0], list):
        return None
    return matches[0]


def annotation_fields(items):
    if not items:
        return []
    annotation = items[0]
    if not isinstance(annotation, dict):
        return [f"unexpected first annotation type: {type(annotation).__name__}"]
    result = {"annotation_keys": sorted(annotation),
              "box_keys": sorted(annotation["box"]) if isinstance(annotation.get("box"), dict) else None,
              "attribute_keys": sorted(annotation["attributes"]) if isinstance(annotation.get("attributes"), dict) else None,
              "label_id_example": str(annotation.get("label_id", ""))[:50]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--labels-zip", type=Path, default=Path.home() / "Downloads/labels.zip")
    parser.add_argument("--frames", nargs="+", default=FRAMES)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only" or manifest.get("sequence") != SEQUENCE:
        parser.error("Expected Cubberly development-only manifest")
    if len(args.frames) != len(set(args.frames)) or not args.frames or any(
            not stem.isdecimal() or len(stem) != 6 for stem in args.frames):
        parser.error("Provide distinct six-digit frame IDs")
    path = args.data_root / SEQUENCE / manifest["label_3d"]
    source = json.loads(path.read_text())["labels"]
    ids_3d = {}
    for frame in args.frames:
        key = frame + ".pcd"
        if key not in source:
            raise ValueError(f"3D label frame missing: {frame}")
        ids_3d[frame] = {str(item.get("label_id")) for item in source[key]
                         if str(item.get("label_id", "")).startswith("pedestrian:")}
    views = []
    with zipfile.ZipFile(args.labels_zip) as archive:
        directory = set(archive.namelist())
        # Only native 2D pedestrian annotations; do not confuse head, pose,
        # stitched, action/social, detection-cache or held-out annotations.
        expected = [f"labels/labels_2d/{SEQUENCE}_image{camera}.json" for camera in CAMERAS]
        if not all(member in directory for member in expected):
            alternatives = sorted(name for name in directory
                                  if name.endswith(".json") and SEQUENCE in name and
                                  "labels_2d" in name and "pose" not in name)
            print(json.dumps({"sequence": SEQUENCE, "status": "native_member_not_found",
                              "expected": expected, "available_related_members": alternatives,
                              "note": "Report actual archive schema; no substitutions made."}, indent=2))
            return
        for camera, member in zip(CAMERAS, expected):
            payload = json.loads(archive.read(member))
            record = {"camera": camera, "member": member,
                      "top_level_keys": sorted(payload) if isinstance(payload, dict) else None,
                      "frame_entries": len(payload["labels"]) if isinstance(payload, dict) and
                         isinstance(payload.get("labels"), dict) else None,
                      "sample": None, "selected_frames": []}
            for frame in args.frames:
                items = selected_image_labels(payload, frame)
                if items is None:
                    record["selected_frames"].append({"frame": frame, "status": "missing_or_unexpected_schema"})
                    continue
                if record["sample"] is None and items:
                    record["sample"] = annotation_fields(items)
                ids_2d = {str(item.get("label_id")) for item in items
                          if isinstance(item, dict) and str(item.get("label_id", "")).startswith("pedestrian:")}
                record["selected_frames"].append({
                    "frame": frame, "status": "read", "annotation_rows": len(items),
                    "unique_pedestrian_ids_2d": len(ids_2d),
                    "same_frame_ids_in_2d_and_3d": sorted(ids_2d & ids_3d[frame]),
                })
            views.append(record)
    print(json.dumps({"sequence": SEQUENCE, "role": "development_only",
                      "status": "schema_inspection_only", "frames": args.frames, "views": views,
                      "interpretation": (
                          "Within-frame 2D/3D label-ID overlap is descriptive, not validated "
                          "sensor synchronization, box alignment or independent ground truth. "
                          "Do not use these references in online inference or select a frame "
                          "convention from ID counts alone.")}, indent=2))


if __name__ == "__main__":
    main()
