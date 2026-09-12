#!/usr/bin/env python3
"""Show near JRDB 3D development labels projected in five native camera views.

Rows compare two coordinate-frame hypotheses. Reference labels are for OFFLINE
visual review only; this cannot validate timestamps or compute detector range.
"""
import argparse
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

from audit_jrdb_cubberly_projection import project
from audit_jrdb_dev_box_geometry import upper_to_ego


SEQUENCE = "cubberly-auditorium-2019-04-22_0"
FRAMES = ("000087", "000432", "000864", "001295")
CAMERAS = (0, 2, 4, 6, 8)
SIZE = (752, 480)
EDGES = tuple((a, b) for a in range(8) for b in range(a + 1, 8)
              if (a ^ b) in (1, 2, 4))


def corners(box):
    """Assumed center + local x length / local y width / z height, rot_z yaw."""
    values = [float(box[k]) for k in ("cx", "cy", "cz", "l", "w", "h", "rot_z")]
    if not all(map(math.isfinite, values)) or min(values[3:6]) <= 0:
        raise ValueError("Nonfinite or nonpositive label box")
    cx, cy, cz, length, width, height, yaw = values
    signs = np.array([[sx, sy, sz] for sz in (-1, 1)
                      for sy in (-1, 1) for sx in (-1, 1)], dtype=np.float64)
    offsets = signs * [length / 2, width / 2, height / 2]
    c, s = math.cos(yaw), math.sin(yaw)
    rotation = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    points = offsets @ rotation.T + [cx, cy, cz]
    return np.vstack(([cx, cy, cz], points))


def visible_projection(xyz_upper, sensor):
    """Preserve index identity while reusing the tested native-camera projection."""
    output = []
    for point in xyz_upper:
        uv, _, _ = project(point[None, :], sensor, SIZE)
        output.append(tuple(map(float, uv[0])) if len(uv) == 1 else None)
    return output


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--images-zip", type=Path, default=Path.home() / "Downloads/train_images.zip")
    parser.add_argument("--frames", nargs="+", default=FRAMES)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("outputs/local/cubberly_3d_frame_hypotheses"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only" or manifest.get("sequence") != SEQUENCE:
        parser.error("Use the Cubberly development-only manifest")
    if len(args.frames) != len(set(args.frames)) or not args.frames or any(
            not f.isdecimal() or len(f) != 6 for f in args.frames):
        parser.error("Give distinct six-digit frame IDs")
    root = args.data_root / SEQUENCE
    calibration_path = root / "calibration/lidars.yaml"
    label_path = root / manifest["label_3d"]
    calibration = yaml.safe_load(calibration_path.read_text())
    sensors = {camera: calibration[f"sensor_{camera}"] for camera in CAMERAS}
    upper2ego = np.asarray(calibration["lidar"]["upper2ego"], dtype=np.float64)
    # Verify the transform before inverting; helper checks approximate rigidity.
    upper_to_ego(np.zeros((1, 3)), upper2ego)
    ego2upper = np.linalg.inv(upper2ego)
    labels = json.loads(label_path.read_text())["labels"]
    if args.output_dir.exists() and any(args.output_dir.glob("*.png")):
        parser.error("Output directory already has PNGs; choose a new --output-dir")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with zipfile.ZipFile(args.images_zip) as archive:
        for frame in args.frames:
            key = frame + ".pcd"
            if key not in labels:
                raise ValueError(f"Missing development 3D labels for {key}")
            selected = []
            seen_ids = set()
            for item in labels[key]:
                person = str(item.get("label_id", ""))
                box = item.get("box") or {}
                if (not person.startswith("pedestrian:") or
                        (item.get("attributes") or {}).get("no_eval") is not False):
                    continue
                if person in seen_ids:
                    raise ValueError(f"Duplicate pedestrian label {person} in {key}")
                seen_ids.add(person)
                try:
                    shape = corners(box)
                except (KeyError, ValueError, TypeError, OverflowError):
                    continue
                if math.hypot(float(box["cx"]), float(box["cy"])) <= 3.0:
                    selected.append((person, shape))
            views = {}
            for camera in CAMERAS:
                path = f"images/image_{camera}/{SEQUENCE}/{frame}.jpg"
                with Image.open(io.BytesIO(archive.read(path))) as source:
                    if source.size != SIZE:
                        raise ValueError(f"Unexpected native size for {path}: {source.size}")
                    views[camera] = source.convert("RGB")
            sheet = Image.new("RGB", (SIZE[0] * len(CAMERAS), SIZE[1] * 2), "black")
            visible = {"label_upper": {}, "label_ego": {}}
            for row_index, hypothesis in enumerate(("label_upper", "label_ego")):
                for col_index, camera in enumerate(CAMERAS):
                    tile = views[camera].copy()
                    draw = ImageDraw.Draw(tile)
                    center_count = 0
                    for person, shape in selected:
                        # Shape is expressed in assumed label coordinates.
                        upper_shape = shape if hypothesis == "label_upper" else upper_to_ego(shape, ego2upper)
                        projected = visible_projection(upper_shape, sensors[camera])
                        for a, b in EDGES:
                            pa, pb = projected[a + 1], projected[b + 1]
                            if pa is not None and pb is not None:
                                draw.line([pa, pb], fill="#ffdd22" if row_index == 0 else "#00e5fa", width=3)
                        center = projected[0]
                        if center is not None:
                            center_count += 1
                            x, y = center
                            draw.ellipse([x - 5, y - 5, x + 5, y + 5], fill="white", outline="black", width=1)
                            draw.text((max(1, x + 5), max(28, y - 11)), person.split(":", 1)[1],
                                      fill="white", stroke_width=2, stroke_fill="black")
                    draw.rectangle((0, 0, SIZE[0], 25), fill="black")
                    draw.text((6, 6), f"{frame} camera {camera} | {hypothesis} | centers {center_count}",
                              fill="white")
                    sheet.paste(tile, (col_index * SIZE[0], row_index * SIZE[1]))
                    visible[hypothesis][str(camera)] = center_count
            output = args.output_dir / f"{SEQUENCE}_{frame}_upper_vs_ego_diagnostic.png"
            sheet.save(output)
            results.append({"frame": frame, "near_evaluable_label_count": len(selected),
                            "label_ids": [person for person, _ in selected],
                            "projected_centers_in_native_views": visible,
                            "diagnostic_png": str(output)})
    print(json.dumps({"sequence": SEQUENCE, "role": "development_only",
                      "label_sha256": sha256(label_path), "calibration_sha256": sha256(calibration_path),
                      "images_archive": args.images_zip.name, "frames": results,
                      "interpretation": (
                          "GT box edges and centers are drawn solely for visual offline frame-hypothesis "
                          "inspection, never fed to detection/ranging. Local length/width/yaw conventions "
                          "are assumed. A projected center may be absent due to field of view or clipping. "
                          "Visual alignment is not proof of timestamp sync, foreground person identity, "
                          "metric range error or event performance.")}, indent=2))


if __name__ == "__main__":
    main()
