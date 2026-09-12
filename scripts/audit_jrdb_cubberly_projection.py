#!/usr/bin/env python3
"""Visual audit of upper LiDAR projection into native JRDB camera 0 (development only).

Needs numpy, Pillow, and PyYAML. No detector, reference event, or timing estimate is made.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw


DEFAULT_FRAMES = ("000086", "000087", "000143", "000144", "000222", "000223", "001295")


def read_pcd_header(source):
    lines = {}
    for _ in range(100):
        raw = source.readline()
        if not raw:
            raise ValueError("PCD DATA line not found")
        if source.tell() > 65536:
            raise ValueError("PCD header exceeds 64 KiB")
        line = raw.decode("ascii").strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(" ")
        lines[key.upper()] = value.strip()
        if key.upper() == "DATA":
            return lines
    raise ValueError("PCD header exceeds 100 lines")


def read_xyz(path):
    with path.open("rb") as source:
        header = read_pcd_header(source)
        fields = header.get("FIELDS", "").split()
        sizes = [int(v) for v in header.get("SIZE", "").split()]
        kinds = header.get("TYPE", "").split()
        counts = [int(v) for v in header.get("COUNT", " ".join("1" for _ in fields)).split()]
        if not fields or not (len(fields) == len(sizes) == len(kinds) == len(counts)):
            raise ValueError(f"Inconsistent PCD field descriptors in {path}")
        if len(set(fields)) != len(fields) or not {"x", "y", "z"}.issubset(fields):
            raise ValueError(f"PCD requires unique x/y/z fields in {path}")
        if any(count < 1 for count in counts):
            raise ValueError("Invalid PCD COUNT")
        points = int(header.get("POINTS", "0"))
        if points < 0:
            raise ValueError("Invalid PCD POINTS")
        mode = header["DATA"].lower()
        if mode == "binary":
            names, formats, offsets = [], [], []
            offset = 0
            for name, size, kind, count in zip(fields, sizes, kinds, counts):
                if (kind, size) not in {("F", 4), ("F", 8), ("I", 1), ("I", 2),
                                         ("I", 4), ("U", 1), ("U", 2), ("U", 4)}:
                    raise ValueError(f"Unsupported PCD TYPE/SIZE: {kind}/{size}")
                token = {"F": "f", "I": "i", "U": "u"}[kind]
                names.append(name)
                formats.append(np.dtype(f"<{token}{size}") if count == 1 else
                               np.dtype((f"<{token}{size}", (count,))))
                offsets.append(offset)
                offset += size * count
            if any(counts[fields.index(axis)] != 1 for axis in "xyz"):
                raise ValueError("x, y and z must be scalar PCD fields")
            remaining = path.stat().st_size - source.tell()
            if remaining < points * offset:
                raise ValueError("PCD binary payload shorter than POINTS * point_step")
            dtype = np.dtype({"names": names, "formats": formats,
                              "offsets": offsets, "itemsize": offset})
            data = np.fromfile(source, dtype=dtype, count=points)
            xyz = np.column_stack([data[axis].astype(np.float64) for axis in "xyz"])
        elif mode == "ascii":
            if any(counts[fields.index(axis)] != 1 for axis in "xyz"):
                raise ValueError("x, y and z must be scalar PCD fields")
            if points == 0:
                xyz = np.empty((0, 3), dtype=np.float64)
            else:
                data = np.loadtxt(source, dtype=np.float64, ndmin=2, max_rows=points)
                indices = [sum(counts[:fields.index(axis)]) for axis in "xyz"]
                if data.shape != (points, sum(counts)):
                    raise ValueError("ASCII PCD payload differs from POINTS/FIELDS")
                xyz = data[:, indices]
        else:
            raise ValueError(f"Unsupported PCD DATA {mode!r}; send the header for review")
        return header, xyz


def project(xyz, sensor, image_size):
    transform = np.asarray(sensor["upper2cam"], dtype=np.float64)
    intrinsic = np.asarray(sensor["distorted_img_K"], dtype=np.float64)
    distortion = np.asarray(sensor["D"], dtype=np.float64)
    if (transform.shape != (4, 4) or intrinsic.shape != (3, 3) or
            distortion.shape != (5,) or not np.isfinite(transform).all() or
            not np.isfinite(intrinsic).all() or not np.isfinite(distortion).all()):
        raise ValueError("Unexpected or nonfinite calibration matrix dimensions")
    rotation = transform[:3, :3]
    if (abs(np.linalg.det(rotation) - 1) > 0.05 or
            not np.allclose(rotation.T @ rotation, np.eye(3), atol=0.05)):
        raise ValueError("upper2cam rotation is not approximately rigid")
    cloud = xyz[np.isfinite(xyz).all(axis=1)]
    finite_count = len(cloud)
    camera = cloud @ rotation.T + transform[:3, 3]
    forward = camera[:, 2] > 0.1
    camera, cloud = camera[forward], cloud[forward]
    if not len(camera):
        return np.empty((0, 2)), np.empty((0,)), {"finite_xyz": finite_count, "in_front": 0, "inside_image": 0}
    xx, yy = camera[:, 0] / camera[:, 2], camera[:, 1] / camera[:, 2]
    with np.errstate(over="ignore", invalid="ignore"):
        r2 = xx * xx + yy * yy
        k1, k2, p1, p2, k3 = distortion
        radial = 1 + k1 * r2 + k2 * r2**2 + k3 * r2**3
        xd = xx * radial + 2 * p1 * xx * yy + p2 * (r2 + 2 * xx * xx)
        yd = yy * radial + p1 * (r2 + 2 * yy * yy) + 2 * p2 * xx * yy
    uv = np.column_stack([intrinsic[0, 0] * xd + intrinsic[0, 1] * yd + intrinsic[0, 2],
                          intrinsic[1, 1] * yd + intrinsic[1, 2]])
    width, height = image_size
    valid = (np.isfinite(uv).all(axis=1) & (uv[:, 0] >= 0) & (uv[:, 0] < width) &
             (uv[:, 1] >= 0) & (uv[:, 1] < height))
    return uv[valid], np.linalg.norm(cloud[valid, :2], axis=1), {
        "finite_xyz": finite_count, "in_front": len(camera), "inside_image": int(valid.sum()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--frames", nargs="+", default=DEFAULT_FRAMES)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/local/cubberly_projection"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only":
        parser.error("Diagnostic takes a development-only manifest, never the final test")
    sequence = manifest["sequence"]
    root = args.data_root / sequence
    calibration = yaml.safe_load((root / "calibration/lidars.yaml").read_text())
    sensor = calibration["sensor_0"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {"sequence": sequence, "sensor": "upper_velodyne / camera_0",
              "calibration": "calibration/lidars.yaml, sensor_0.upper2cam + distorted_img_K + D",
              "images": [], "timing": {"status": "not_verified", "note":
                  "Matching frame IDs and nominal data rate do not establish acquisition timestamps."},
              "interpretation": "Diagnostic raw-point registration only. No metric localization, GT box alignment, independent negatives, or event score is established."}
    for stem in args.frames:
        if not stem.isdecimal():
            parser.error("--frames accepts numeric frame IDs only")
        image_path = root / "images/image_0" / sequence / f"{stem}.jpg"
        cloud_path = root / "pointclouds/upper_velodyne" / sequence / f"{stem}.pcd"
        with Image.open(image_path) as image:
            rgb = image.convert("RGB")
        header = {}
        try:
            header, points = read_xyz(cloud_path)
            uv, ranges, counts = project(points, sensor, rgb.size)
        except ValueError as error:
            report["images"].append({"frame": stem, "pcd_data": header.get("DATA"),
                                     "status": "unsupported_or_invalid", "reason": str(error)})
            continue
        # Fixed subsampling only changes preview density; counts above use all points.
        if len(uv) > 8000:
            indices = np.linspace(0, len(uv) - 1, 8000, dtype=int)
            uv, ranges = uv[indices], ranges[indices]
        overlay = Image.new("RGBA", rgb.size, (0, 0, 0, 0))
        canvas = ImageDraw.Draw(overlay)
        for (u, v), distance in zip(uv, ranges):
            color = (255, 235, 20) if distance <= 3 else (25, 240, 240) if distance <= 10 else (255, 60, 195)
            canvas.ellipse((int(u) - 1, int(v) - 1, int(u) + 1, int(v) + 1), fill=(*color, 190))
        preview = Image.alpha_composite(rgb.convert("RGBA"), overlay).convert("RGB")
        ImageDraw.Draw(preview).text((5, 5), "Upper LiDAR XY <=3m yellow; <=10m cyan; farther magenta", fill="white",
                                      stroke_width=2, stroke_fill="black")
        target = args.output_dir / f"{sequence}_camera0_upper_{stem}.png"
        preview.save(target)
        report["images"].append({"frame": stem, "status": "diagnostic_overlay_generated",
                                 "pcd_data": header.get("DATA"), "pcd_fields": header.get("FIELDS"),
                                 "pcd_points_declared": int(header.get("POINTS", "0")),
                                 "finite_xyz_count": counts["finite_xyz"],
                                 "points_in_front": counts["in_front"],
                                 "projected_inside_camera": counts["inside_image"],
                                 "preview": str(target)})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
