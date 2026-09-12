# Cubberly development: blinded surface-association review

This is an offline quality-control task for the **development** sequence
`cubberly-auditorium-2019-04-22_0`. It does not measure alert accuracy or
create a held-out test result. The sensor-only cache must already exist; this
script reads annotation-linked files only to choose and later categorize cases.
Never import its review key, annotation CSV, or labels into the sensor-only
inference or alert pipeline.

## Why these cases

The full development threshold audit covers 32,006 IoU-linked
frame/camera/detector-box views. A candidate surface was available on 28,712
of the same views used for the paired nearest-return comparison. For centers
outside 3 m, 464 candidate surfaces were inside 3 m; for centers inside 3 m,
97 candidate surfaces were outside and another 332 views abstained. An
additional 1,035 unlinked detector boxes had candidates inside 3 m.
These are review *leads*. A measured surface and a geometric center are
different physical targets. An unlinked box has unknown status. Related
camera views and frames are not independent observations.

The sampling script selects at most 66 cases: 12 far-center/inside-candidate,
12 near-center/outside-candidate, 12 near-center/abstained, 18 unlinked/inside-
candidate, six agreeing near controls, and six agreeing far controls. It draws
one case per annotated person per 30-frame block where possible; unlinked
cases are grouped by camera, 30-frame block, and approximate image tile.
It can draw fewer if a pool has fewer cases. This deliberately enriched
sample is unsuitable for estimating error prevalence, confidence intervals,
person range, or event performance.

## Prepare the worklist

Run from the repository root after producing the full-sequence threshold
summary and its CSV on your workstation. Change a path flag if your saved
filename differs from the defaults:

```bash
python3 scripts/prepare_jrdb_dev_blinded_review.py \
  --threshold-summary outputs/local/cubberly_threshold_crossing_full_summary_v2.json \
  --threshold-review outputs/local/cubberly_threshold_crossing_full_review_v2.csv \
  --reference-csv outputs/local/cubberly_surface_reference_full.csv \
  --candidate-csv outputs/local/cubberly_sensor_surface_full.csv \
  > outputs/local/cubberly_blinded_review_summary.json
python3 -m json.tool outputs/local/cubberly_blinded_review_summary.json
```

The script checks input row counts and sensor/reference SHA256 hashes against
the supplied threshold summary and refuses to overwrite a packet. It writes
`reviewer_a.csv`, `reviewer_b.csv`, `review_key.csv`, and `frames.txt` under
`outputs/local/cubberly_blinded_review/`. Keep that directory local, outside
Git. If the review CSV or summary is named differently, pass the actual path;
do not relabel another result as this audit.

To make **detector-only** five-camera context sheets for the sampled frames:

```bash
python3 scripts/review_jrdb_native_detections.py \
  --predictions outputs/local/cubberly_native_full.jsonl \
  --frames $(cat outputs/local/cubberly_blinded_review/frames.txt) \
  --output-dir outputs/local/cubberly_blinded_review/native_sheets \
  > outputs/local/cubberly_blinded_review/native_sheets_summary.json
```

This uses the local `train_images.zip` via the existing script. To inspect
LiDAR association, inspect native images and *measured-point* projections,
including the five-camera overlay script where useful. Do not show 2D or 3D
label overlays, label distances, thresholds, strata, or `review_key.csv` to a
reviewer until their decisions are saved. An overlay alone does not identify
which point belongs to which person or establish timestamp synchronization.
The ±5 frame IDs in each sheet provide optional visual context, not seconds.

## Record independent judgments

Two reviewers can independently fill the A and B sheets with the same case
IDs, keeping each other's decisions hidden. If only one reviewer is available,
complete sheet A and report that limitation. For each case, inspect the marked
detector rectangle, the other native camera views, the measured LiDAR overlays,
and surrounding frames as needed. Fill these columns with `yes`, `no`, or
`uncertain`:

- `person_visible_in_box`: a person is visibly represented by this rectangle.
- `association_clear`: measured points can be associated with that particular
  visible person rather than another person or a background surface.
- `foreground_surface_clear`: the proposed foreground LiDAR surface is
  plausibly on that person, not just somewhere inside the 2D rectangle.
- `occlusion_or_edge_issue`: overlap, truncation, camera boundary, or
  viewpoint makes the preceding judgments unreliable.

Set `reviewer_confidence` to `high`, `medium`, or `low` and explain uncertain
cases in `reviewer_notes`. Do not guess a distance from a box or infer the
identity of an unlinked case. Uncertain is an acceptable result, particularly
for sparse, occluded, or cross-camera observations. Keep original sheets and
hashes unchanged after completion; reconcile independent reviewers only after
both have saved their judgments, noting disagreements and how each was
resolved. Then join by `case_id` to `review_key.csv` **offline** for failure
analysis; distinguish visibility/association from center-threshold discordance.

## Research gates after the review

Use reviewed failures to adjust or reject the sensor-side surface selection,
document abstention behavior, and fix a physically explicit distance target
(person surface or center). Next establish timestamp/frame alignment and
per-person temporal identity across views, decide entry/exit and alert
deduplication rules, and adjudicate independent positive and negative event
intervals. Freeze the development choices before evaluating untouched moving
recordings by event sensitivity, false alerts per time, alert latency, and
runtime under the actual intended hardware. Until then, report conditional
development diagnostics only.
