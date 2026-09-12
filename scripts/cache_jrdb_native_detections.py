#!/usr/bin/env python3
"""Cache development-only, five-camera person detections from raw JRDB image ZIP.

This is a 2D perception pilot, not a tracked/metric proximity alert system.
Needs numpy, opencv-python, torch, ultralytics and a local COCO YOLOv8 weight file.
"""

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
import zipfile
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch
import ultralytics
from ultralytics import YOLO


CAMERAS = (0, 2, 4, 6, 8)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state():
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True,
                                            stderr=subprocess.DEVNULL).strip())
        return {"head": head, "working_tree_dirty": dirty}
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {"head": None, "working_tree_dirty": None}


def frame_names(archive, sequence, start, count):
    prefix = f"images/image_0/{sequence}/"
    available = sorted(int(Path(name).stem) for name in archive.namelist()
                       if name.startswith(prefix) and name.endswith(".jpg") and
                       Path(name).stem.isdecimal())
    if not available or len(set(available)) != len(available):
        raise ValueError("Missing or duplicated image_0 frame IDs")
    selected = [n for n in available if n >= start][:count if count else None]
    if not selected or selected != list(range(selected[0], selected[-1] + 1)):
        raise ValueError("Selected frame IDs missing or nonconsecutive")
    if start != selected[0]:
        raise ValueError(f"Requested start {start}, first available selected frame {selected[0]}")
    names = [(frame, camera, f"images/image_{camera}/{sequence}/{frame:06}.jpg")
             for frame in selected for camera in CAMERAS]
    archive_names = set(archive.namelist())
    missing = [name for _, _, name in names if name not in archive_names]
    if missing:
        raise ValueError(f"Missing native camera frames; first: {missing[:3]}")
    return selected, names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--images-zip", type=Path, default=Path.home() / "Downloads/train_images.zip")
    parser.add_argument("--weights", type=Path, default=Path("yolov8n.pt"))
    parser.add_argument("--start-frame", type=int, default=70)
    parser.add_argument("--max-frames", type=int, default=80, help="0 = all remaining development frames")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.10)
    parser.add_argument("--iou", type=float, default=0.70)
    parser.add_argument("--device", default="0", help="0 = first NVIDIA GPU; cpu is allowed")
    parser.add_argument("--output", type=Path, default=Path("outputs/local/cubberly_native_pilot.jsonl"))
    args = parser.parse_args()
    if (args.start_frame < 0 or args.max_frames < 0 or args.imgsz < 32 or
            not math.isfinite(args.confidence) or not 0 < args.confidence <= 1 or
            not math.isfinite(args.iou) or not 0 < args.iou <= 1):
        parser.error("Invalid start/count/image size/confidence/IoU")
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only":
        parser.error("This exploratory inference script accepts only development data")
    if not args.weights.is_file():
        parser.error(f"Local weights missing: {args.weights}; obtain weights before running")
    if args.device != "cpu" and not torch.cuda.is_available():
        parser.error("CUDA is unavailable; use --device cpu or restore the GPU environment")
    if args.output.exists():
        parser.error(f"Output exists and will not be overwritten: {args.output}")
    sequence = manifest["sequence"]
    with zipfile.ZipFile(args.images_zip) as archive:
        selected, names = frame_names(archive, sequence, args.start_frame, args.max_frames)
        weight_sha = sha256_file(args.weights)
        model = YOLO(str(args.weights))
        if str(model.names[0]).lower() != "person":
            raise ValueError("Weight class 0 must be person; require a COCO person detector")
        summary = {
            "sequence": sequence, "role": "development_only", "source": "train_images.zip",
            "camera_ids": list(CAMERAS), "frames_first_last": [selected[0], selected[-1]],
            "frames_count": len(selected), "expected_camera_frames": len(names),
            "weight_file": str(args.weights), "weight_sha256": weight_sha,
            "settings": {"imgsz": args.imgsz, "confidence": args.confidence,
                         "iou": args.iou, "device": args.device, "class_id": 0,
                         "stream_order": "frame then camera", "batch_size": 1},
            "versions": {"python": platform.python_version(), "torch": torch.__version__,
                         "ultralytics": ultralytics.__version__, "opencv": cv2.__version__},
            "git": git_state(), "predictions": str(args.output),
            "scope": "Raw five-camera 2D boxes only. No timestamps, tracker, LiDAR range, complete alert metric or ground-truth access.",
        }
        counts = Counter()
        image_times_ms = []
        start_total = time.perf_counter()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as destination:
            for frame, camera, name in names:
                if args.device != "cpu":
                    torch.cuda.synchronize()
                tick = time.perf_counter()
                compressed = archive.read(name)
                image = cv2.imdecode(np.frombuffer(compressed, np.uint8), cv2.IMREAD_COLOR)
                if image is None or image.shape[:2] != (480, 752):
                    raise ValueError(f"Unreadable or unexpected native image dimensions: {name}")
                result = model.predict(image, imgsz=args.imgsz, conf=args.confidence,
                                       iou=args.iou, classes=[0], device=args.device,
                                       verbose=False, save=False)[0]
                boxes = result.boxes
                detections = []
                if boxes is not None and len(boxes):
                    raw = boxes.data.detach().cpu().numpy()
                    for x1, y1, x2, y2, conf, cls in raw[:, :6]:
                        if int(cls) != 0:
                            raise ValueError("Non-person detection returned despite classes=[0]")
                        detections.append({"xyxy": [float(x1), float(y1), float(x2), float(y2)],
                                           "confidence": float(conf)})
                if args.device != "cpu":
                    torch.cuda.synchronize()
                elapsed_ms = (time.perf_counter() - tick) * 1000
                destination.write(json.dumps({"frame": f"{frame:06}", "camera": camera,
                                              "detections": detections, "elapsed_ms": round(elapsed_ms, 3)}) + "\n")
                image_times_ms.append(elapsed_ms)
                counts[str(camera)] += len(detections)
        total_seconds = time.perf_counter() - start_total
    summary.update({"processed_camera_frames": len(image_times_ms),
                    "person_detections_by_camera": dict(sorted(counts.items())),
                    "total_elapsed_seconds": round(total_seconds, 3),
                    "processed_camera_frames_per_second": round(len(names) / total_seconds, 3),
                    "full_five_camera_sets_per_second": round(len(selected) / total_seconds, 3),
                    "median_camera_frame_ms": round(float(np.median(image_times_ms)), 3),
                    "timing_note": "Offline sequential five-view decode plus detector/copy in this workstation, not robot online latency; first-call warmup and ZIP access included."})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
