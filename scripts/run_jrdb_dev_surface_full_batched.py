#!/usr/bin/env python3
"""Run and resume full Cubberly sensor-only surface candidates in small batches.

Invokes cache_jrdb_dev_sensor_depth_candidates.py without reference labels.
Cached batches are hash checked before reuse; the merged CSV/JSON use exactly
the format expected by evaluate_jrdb_dev_surface_candidates_offline.py.
"""

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


SEQUENCE = "cubberly-auditorium-2019-04-22_0"
FRAMES = tuple(f"{frame:06d}" for frame in range(1296))
CAMERAS = (0, 2, 4, 6, 8)
PILOT_PREDICTIONS_SHA256 = "2e13fa212e647561765f0cc203ec60fd658e6377c6a7c655200700beddc56a16"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False,
                                     dir=path.parent, prefix=".jrdb-summary-", suffix=".tmp") as temp:
        json.dump(payload, temp, indent=2)
        temp.write("\n")
        name = temp.name
    try:
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def validate_chunk(part_csv, metadata, frames, prediction_sha):
    summary = metadata.get("sensor_summary")
    if (not isinstance(summary, dict) or
            summary.get("status") != "unvalidated_measured_surface_candidates" or
            summary.get("sequence") != SEQUENCE or summary.get("role") != "development_only" or
            summary.get("frames") != list(frames) or
            summary.get("raw_prediction_sha256") != prediction_sha or
            metadata.get("csv_sha256") != sha256(part_csv)):
        raise ValueError(f"Chunk metadata/CSV mismatch: {part_csv}")
    if summary.get("csv") != str(part_csv):
        raise ValueError(f"Chunk output path changed: {part_csv}")
    status = Counter()
    total = 0
    with part_csv.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fields = reader.fieldnames
        if not fields or not {"frame", "camera", "box_index", "surface_candidate_status"} <= set(fields):
            raise ValueError(f"Incomplete chunk CSV: {part_csv}")
        next_index = {}
        for row in reader:
            if row["frame"] not in frames or int(row["camera"]) not in CAMERAS:
                raise ValueError(f"Out-of-chunk frame/camera: {part_csv}")
            key = (row["frame"], row["camera"])
            index = int(row["box_index"])
            if index != next_index.get(key, 0):
                raise ValueError(f"Missing or duplicated box index at {key}: {part_csv}")
            next_index[key] = index + 1
            total += 1
            status[row["surface_candidate_status"]] += 1
    if total != summary.get("boxes") or dict(status) != summary.get("status_counts"):
        raise ValueError(f"Chunk boxes/statuses disagree with summary: {part_csv}")
    return fields, total, status, summary


def run_chunk(script, manifest, data_root, predictions, part_csv, meta_path, frames, prediction_sha):
    # An orphan CSV cannot be trusted after interruption: the runner owns its batch directory.
    if part_csv.exists() != meta_path.exists():
        part_csv.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
    if not part_csv.exists():
        command = [sys.executable, str(script), "--manifest", str(manifest),
                   "--data-root", str(data_root), "--predictions", str(predictions),
                   "--csv", str(part_csv), "--frames", *frames]
        print(f"Processing sensor frames {frames[0]}..{frames[-1]}", file=sys.stderr, flush=True)
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            part_csv.unlink(missing_ok=True)
            raise RuntimeError(f"Sensor batch failed at {frames[0]}: {result.stderr.strip()}")
        summary = json.loads(result.stdout)
        metadata = {"csv_sha256": sha256(part_csv), "sensor_summary": summary}
        save_atomic(meta_path, metadata)
        resumed = False
    else:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        resumed = True
    fields, total, status, summary = validate_chunk(part_csv, metadata, frames, prediction_sha)
    print(f"{'Reused' if resumed else 'Finished'} {frames[0]}..{frames[-1]}: {total} boxes",
          file=sys.stderr, flush=True)
    return fields, total, status, summary, resumed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--predictions", type=Path,
                        default=Path("outputs/local/cubberly_native_full.jsonl"))
    parser.add_argument("--expected-predictions-sha256", default=PILOT_PREDICTIONS_SHA256)
    parser.add_argument("--batch-frames", type=int, default=72)
    parser.add_argument("--batch-dir", type=Path, default=Path("outputs/local/cubberly_surface_batches"))
    parser.add_argument("--csv", type=Path, default=Path("outputs/local/cubberly_sensor_surface_full.csv"))
    parser.add_argument("--summary", type=Path, default=Path(
        "outputs/local/cubberly_sensor_surface_full_summary.json"))
    args = parser.parse_args()
    if not 1 <= args.batch_frames <= 200:
        parser.error("Choose 1..200 frames per batch")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if (manifest.get("sequence") != SEQUENCE or manifest.get("role") != "development_only" or
            manifest.get("frame_counts", {}).get("image_stitched") != len(FRAMES)):
        parser.error("Expected extracted 1,296-frame Cubberly development manifest")
    if args.csv.exists() and args.summary.exists():
        result = json.loads(args.summary.read_text(encoding="utf-8"))
        if result.get("candidate_csv_sha256") != sha256(args.csv):
            parser.error("Existing full CSV and summary disagree")
        print(json.dumps({"status": "already_complete", "csv": str(args.csv),
                          "summary": str(args.summary), "boxes": result.get("boxes")}, indent=2))
        return
    if args.summary.exists() and not args.csv.exists():
        parser.error("Summary exists but full CSV is missing; inspect before retrying")
    prediction_sha = sha256(args.predictions)
    if (len(args.expected_predictions_sha256) != 64 or
            prediction_sha != args.expected_predictions_sha256):
        parser.error("Raw predictions changed from the four-frame development pilot")
    script = Path(__file__).with_name("cache_jrdb_dev_sensor_depth_candidates.py").resolve()
    if not script.is_file():
        parser.error(f"Sensor-only script missing: {script}")
    args.batch_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    total_boxes = 0
    combined_status = Counter()
    first_fields = first_summary = None
    resumed_chunks = 0
    for start in range(0, len(FRAMES), args.batch_frames):
        frames = FRAMES[start:start + args.batch_frames]
        prefix = f"{frames[0]}_{frames[-1]}"
        csv_path = args.batch_dir / f"{prefix}.csv"
        meta_path = args.batch_dir / f"{prefix}.meta.json"
        fields, total, status, part, resumed = run_chunk(
            script, args.manifest, args.data_root, args.predictions, csv_path,
            meta_path, frames, prediction_sha)
        if first_fields is None:
            first_fields, first_summary = fields, part
        elif (fields != first_fields or part["settings"] != first_summary["settings"] or
                part["calibration_sha256"] != first_summary["calibration_sha256"] or
                part["range_coordinate"] != first_summary["range_coordinate"] or
                part["sensors"] != first_summary["sensors"]):
            raise ValueError(f"Batch settings, calibration or columns changed: {csv_path}")
        chunks.append(csv_path)
        total_boxes += total
        combined_status.update(status)
        resumed_chunks += resumed

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", delete=False,
                                     dir=args.csv.parent, prefix=".jrdb-merged-", suffix=".tmp") as temp:
        temp_path = Path(temp.name)
        writer = csv.DictWriter(temp, fieldnames=first_fields)
        writer.writeheader()
        for path in chunks:
            with path.open(encoding="utf-8", newline="") as source:
                writer.writerows(csv.DictReader(source))
    try:
        if args.csv.exists():
            if sha256(args.csv) != sha256(temp_path):
                raise ValueError("Existing merged CSV differs from verified batches")
        else:
            os.replace(temp_path, args.csv)
        summary = {key: first_summary[key] for key in first_summary if key not in (
            "frames", "boxes", "status_counts", "csv", "interpretation")}
        summary.update({"frames": list(FRAMES), "boxes": total_boxes,
                        "status_counts": dict(combined_status), "csv": str(args.csv),
                        "candidate_csv_sha256": sha256(args.csv),
                        "batch_count": len(chunks), "batch_frames": args.batch_frames,
                        "interpretation": "Sensor-only full Cubberly DEVELOPMENT cache, combined "
                            "from verified frame batches. Surface candidates are not person "
                            "distances or alerts. No JRDB reference labels were read. "
                            "Evaluate only with a separate offline reference process."})
        save_atomic(args.summary, summary)
    finally:
        temp_path.unlink(missing_ok=True)
    print(json.dumps({"status": "complete_sensor_only_development_cache", "csv": str(args.csv),
                      "summary": str(args.summary), "boxes": total_boxes,
                      "batch_count": len(chunks), "reused_batches": resumed_chunks}, indent=2))


if __name__ == "__main__":
    main()
