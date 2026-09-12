# Cubberly: threshold review and full development run

The four selected development frames yielded 84 matched detector/2D/3D camera views. A sensor surface candidate and the annotated 3D center lie on the same side of the exploratory 3 m boundary for 68 views; 12 far-center views abstain. One far-center view has an inside candidate, one near-center view has an outside candidate, and two near-center views abstain. Those two abstentions are correlated views of `pedestrian:35` in frame `000432`. There are 13 unique **linked** near frame/person IDs, 12 of which have at least one linked camera view with an inside candidate. Seven linked views have annotated centers within 0.25 m of the boundary; small geometry changes could change their classification. Three close sensor candidates have no linked reference.

These numbers are reference-matched **development diagnostics**. A person surface and annotated box center are different physical quantities, and unlinked detections cannot be declared false alerts. They are not encounter recall, precision, independent range accuracy, or evidence from a held-out location. The serious review cases include `000432` camera 6 `pedestrian:1` (annotated center 7.567 m, candidate 2.515 m, severely occluded) and `000864` camera 8 `pedestrian:22` (annotated center 2.796 m, candidate 3.889 m, near the image edge).

Next, run the **unchanged sensor-side method across all 1,296 Cubberly development frames** using `scripts/run_jrdb_dev_surface_full_batched.py`. It creates 72-frame batch checkpoints, checks raw detector predictions against the pilot SHA-256, checks each batch CSV and metadata on resume, and merges into an evaluator-compatible CSV/JSON. It does not open JRDB 2D/3D labels. Progress is printed to stderr. The process may take time; completed batches are reusable if it is interrupted.

From `~/jrdb-patrol-alerts` with `.venv` active:

```bash
python3 scripts/run_jrdb_dev_surface_full_batched.py \
  > outputs/local/cubberly_surface_full_run_log.json
python3 -m json.tool outputs/local/cubberly_surface_full_run_log.json
```

The runner writes `outputs/local/cubberly_sensor_surface_full.csv`, `outputs/local/cubberly_sensor_surface_full_summary.json` and intermediate files in `outputs/local/cubberly_surface_batches/`. If restarted, repeat the same command; verified completed batches are reused. A source hash mismatch stops the run; do not bypass that check to claim direct comparability to the pilot.

After the runner finishes, **only the separate offline evaluator** may read development reference annotations:

```bash
python3 scripts/evaluate_jrdb_dev_surface_candidates_offline.py \
  --candidates outputs/local/cubberly_sensor_surface_full.csv \
  --candidate-summary outputs/local/cubberly_sensor_surface_full_summary.json \
  --csv outputs/local/cubberly_surface_reference_full.csv \
  > outputs/local/cubberly_surface_reference_full_summary.json

python3 scripts/analyze_jrdb_dev_surface_discrepancies.py \
  --candidate-csv outputs/local/cubberly_sensor_surface_full.csv \
  --reference-csv outputs/local/cubberly_surface_reference_full.csv \
  --reference-summary outputs/local/cubberly_surface_reference_full_summary.json \
  --review-csv outputs/local/cubberly_surface_priority_full.csv \
  > outputs/local/cubberly_surface_paired_full_summary.json

python3 scripts/audit_jrdb_dev_threshold_crossings.py \
  --candidate-csv outputs/local/cubberly_sensor_surface_full.csv \
  --reference-csv outputs/local/cubberly_surface_reference_full.csv \
  --reference-summary outputs/local/cubberly_surface_reference_full_summary.json \
  --review-csv outputs/local/cubberly_threshold_crossing_full_review.csv \
  > outputs/local/cubberly_threshold_crossing_full_summary.json
```

The four-frame pilot may overlap these 1,296 frames; do not treat the latter as an independent replication. Inspect all close unlinked candidates, threshold crossings, crowded/occluded matches, and near abstentions in native images and point clouds. Review person/frame outcomes separately from correlated camera-view outcomes. To support a patrol-alert claim later, define the actual surface-versus-center safety distance target, verify timing, add tracking and alert deduplication, adjudicate ground-truth entry/exit intervals and negative periods independently, freeze policy on development data, and then test on untouched moving locations. Do not infer deployment latency from the offline detector's workstation FPS.
