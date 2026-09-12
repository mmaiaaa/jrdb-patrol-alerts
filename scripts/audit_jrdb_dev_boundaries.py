#!/usr/bin/env python3
"""Audit candidate entry, exit, initial occupancy and negative intervals on development labels."""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


FIELDS = (
    "record_type", "sequence", "person_id", "start_frame", "end_frame",
    "length_frames", "start_status", "end_status", "review_from_frame",
    "review_through_frame", "frames_with_no_eval_near", "reviewer_decision", "reviewer_notes",
)


def runs_from_sorted_numbers(numbers):
    runs = []
    for number in sorted(numbers):
        if not runs or number != runs[-1][-1] + 1:
            runs.append([])
        runs[-1].append(number)
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/development_cubberly.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/jrdb2022/development"))
    parser.add_argument("--radius-m", type=float, default=3.0)
    parser.add_argument("--review-context-frames", type=int, default=5)
    parser.add_argument("--csv", type=Path, default=Path("outputs/local/cubberly_reference_review.csv"))
    args = parser.parse_args()
    if not math.isfinite(args.radius_m) or args.radius_m <= 0 or args.review_context_frames < 0:
        parser.error("Radius must be finite and positive; context must be nonnegative")
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("role") != "development_only":
        raise ValueError("This diagnostic accepts development-only manifests, not held-out data")
    sequence = manifest["sequence"]
    labels = json.loads((args.data_root / sequence / manifest["label_3d"]).read_text())["labels"]
    ids = [Path(filename).stem for filename in labels]
    if not ids or any(not stem.isdecimal() for stem in ids):
        raise ValueError("Expected numeric frame identifiers")
    numbers = sorted(int(stem) for stem in ids)
    if len(numbers) != len(set(numbers)) or numbers != list(range(numbers[0], numbers[-1] + 1)):
        raise ValueError("Non-contiguous or duplicate numeric frame identifiers; inspect before proceeding")
    width = len(ids[0])
    first, last = numbers[0], numbers[-1]
    observations = defaultdict(dict)
    near_by_frame = defaultdict(set)
    no_eval_near_frames = set()
    for filename, items in labels.items():
        number = int(Path(filename).stem)
        for item in items:
            person = str(item.get("label_id", ""))
            if not person.startswith("pedestrian:"):
                continue
            box = item.get("box") or {}
            try:
                x, y = float(box["cx"]), float(box["cy"])
            except (KeyError, ValueError, TypeError):
                state = "unknown"
            else:
                if not (math.isfinite(x) and math.isfinite(y)):
                    state = "unknown"
                elif (item.get("attributes") or {}).get("no_eval") is not False:
                    state = "unknown"
                    if math.hypot(x, y) <= args.radius_m:
                        no_eval_near_frames.add(number)
                elif math.hypot(x, y) <= args.radius_m:
                    state = "near"
                else:
                    state = "far"
            if number in observations[person]:
                raise ValueError(f"Duplicate {person} annotation at frame {number}")
            observations[person][number] = state
            if state == "near":
                near_by_frame[number].add(person)

    def frame(number):
        return f"{number:0{width}d}"

    rows = []
    starts = Counter()
    ends = Counter()
    for person, states in sorted(observations.items()):
        for run in runs_from_sorted_numbers(n for n, value in states.items() if value == "near"):
            start, end = run[0], run[-1]
            start_status = ("left_censored" if start == first else
                            "candidate_observed_entry" if states.get(start - 1) == "far" else
                            "first_seen_inside_or_unknown")
            end_status = ("right_censored" if end == last else
                          "candidate_observed_exit" if states.get(end + 1) == "far" else
                          "lost_or_unknown")
            starts[start_status] += 1
            ends[end_status] += 1
            rows.append({
                "record_type": "near_person_candidate_run", "sequence": sequence,
                "person_id": person, "start_frame": frame(start), "end_frame": frame(end),
                "length_frames": len(run), "start_status": start_status, "end_status": end_status,
                "review_from_frame": frame(max(first, start - args.review_context_frames)),
                "review_through_frame": frame(min(last, end + args.review_context_frames)),
                "frames_with_no_eval_near": "", "reviewer_decision": "", "reviewer_notes": "",
            })

    negative_runs = runs_from_sorted_numbers(n for n in numbers if not near_by_frame[n])
    for run in negative_runs:
        start, end = run[0], run[-1]
        rows.append({
            "record_type": "provisional_no_evaluable_person_near", "sequence": sequence,
            "person_id": "", "start_frame": frame(start), "end_frame": frame(end),
            "length_frames": len(run), "start_status": "", "end_status": "",
            "review_from_frame": frame(max(first, start - args.review_context_frames)),
            "review_through_frame": frame(min(last, end + args.review_context_frames)),
            "frames_with_no_eval_near": sum(n in no_eval_near_frames for n in run),
            "reviewer_decision": "", "reviewer_notes": "",
        })

    rows.sort(key=lambda row: (int(row["start_frame"]), row["record_type"], row["person_id"]))
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    # Manual adjudications may be entered into this queue after generation.
    # Refuse to overwrite them on an accidental rerun.
    with args.csv.open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "sequence": sequence, "radius_m": args.radius_m,
        "frames": len(numbers), "candidate_near_person_runs": sum(starts.values()),
        "candidate_start_statuses": dict(sorted(starts.items())),
        "candidate_end_statuses": dict(sorted(ends.items())),
        "provisional_no_evaluable_person_near_frames": sum(len(run) for run in negative_runs),
        "provisional_negative_intervals": len(negative_runs),
        "negative_intervals_containing_no_eval_near_frames": sum(
            bool(no_eval_near_frames.intersection(run)) for run in negative_runs
        ),
        "review_rows_csv": str(args.csv),
        "limitations": [
            "One-frame outside/inside transitions are candidates and can be caused by annotation noise.",
            "Initial occupancy is not an observed entry; disappearance is not an observed exit.",
            "No-evaluable-person-near frames need independent visual and LiDAR review before use as negatives.",
            "The review table has blank human-adjudication fields and is not ground truth.",
            "Frames are not seconds, and label-derived distances must never feed online alerts.",
        ],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
