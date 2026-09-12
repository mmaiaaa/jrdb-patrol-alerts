# Cubberly four-frame surface/reference diagnostic

**Development only; September 12, 2026.** Sensor-derived upper-plus-lower LiDAR surface candidates were computed without annotations. A separate offline evaluator then matched detector boxes to native JRDB 2D labels at IoU ≥0.5 and, where available, looked up the same annotated person's 3D box-center XY radius. This does not measure online person range, false alerts, event detection, or generalization.

| Conditional group | Four-frame observation | What it does not establish |
| --- | --- | --- |
| Detector boxes | 142 | The number of distinct people; boxes can duplicate a person across cameras. |
| Evaluable 2D annotation boxes | 135 | An independently exhaustive set of visible people. |
| Detector-to-2D matches | 86 | A validated detection precision/recall score; these are same-frame IoU associations. |
| Matches also linked to evaluable 3D labels | 84 | Performance over all 142 detector boxes; 58 have no such linked reference. |
| Linked pairs yielding selected surface candidates | 70/84 (83.3%) | Person-range coverage; this is conditional on linked pairs only. |
| Linked near-center pairs yielding selected candidates | 16/18 (88.9%) | Near-person sensitivity; repeated camera views and sparse selected frames limit interpretation. |
| All matched selected surfaces versus center | 70 pairs: median absolute discrepancy 0.083 m; mean 0.296 m; 6 exceed 1 m | A range accuracy score: annotated box center differs physically from sensor surface. |
| Nearest supported surface versus center | 84 pairs: median absolute discrepancy 1.641 m; mean 2.080 m; 47 exceed 1 m | A fair head-to-head with 70 selected outputs: denominators differ. |
| Selected near-center surfaces versus center | 16 pairs: median 0.067 m; mean 0.183 m; 1 exceeds 1 m | An event or held-out result. |

The separate `scripts/analyze_jrdb_dev_surface_discrepancies.py` compares selected and nearest surfaces **only for exactly the same matched frame-camera-box**, stratifies by the annotated 3 m center criterion, reports unique frame/person IDs and per-frame counts, and creates a human-review worklist with blank reviewer fields. It checks the candidate CSV SHA-256 against the offline evaluator summary before joining them. The reference labels remain outside the sensing code. Its numbers remain *surface versus annotation-center discrepancies*.

The sample rows already reveal both a useful hypothesis and a failure: for `000087` camera 0, `pedestrian:7`, selected surface 5.647 m is closer to the annotated center 5.791 m than nearest supported surface 4.036 m on that same box; `pedestrian:9`, marked severely occluded, has selected surface 4.874 m versus annotated center 7.291 m, a roughly 2.417 m discrepancy. A good median can coexist with consequential mistakes in occlusions. Candidate 3 m radii for detector boxes lacking a linked reference must be reviewed; do not silently count them as true or false alerts. Review matched outliers and abstentions against native images and temporal context before using any numbers as evidence of range quality.

Next research gates: run sensor-only candidate generation on **all 1,296 development frames** with fixed settings, apply the offline evaluator and review worklist, independently adjudicate near-person onsets, exits and negative intervals, and only then freeze the complete tracking/range/alert policy before untouched moving-location evaluation. Verify source timing and actual sensor-to-camera association where source timestamps exist. These four selected frames cannot supply credible uncertainty bounds for general alert performance.

Example commands after installing the script in the repository:

```bash
python3 scripts/analyze_jrdb_dev_surface_discrepancies.py \
  > outputs/local/cubberly_surface_paired_summary.json
python3 -m json.tool outputs/local/cubberly_surface_paired_summary.json
head -12 outputs/local/cubberly_surface_priority_review.csv
```

The worklist is an assignment aid. All human-adjudication fields start empty; final decisions require checking original images, 3D annotations, neighboring frames and ambiguous overlaps.
