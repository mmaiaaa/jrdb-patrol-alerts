# Cubberly surface pilot: threshold crossings and next development run

The four-frame **development** audit now compares selected and nearest supported LiDAR surfaces for the **same 70 linked frame-camera-box views**. Their median absolute differences from annotated 3D geometric-center XY radius are 0.083 m and 1.254 m, respectively. The selected surface is more than 0.25 m closer in 33/70 paired views, the nearest is never more than 0.25 m closer, and 37/70 differ by at most 0.25 m. For the 16 matched views whose annotated centers are within 3 m and have a selected candidate, the two medians are both 0.067 m; selected is materially closer in just 1/16. A center/surface difference is not an independently validated measurement error.

The 18 linked near-center camera views represent only **13 distinct frame/person IDs**. Two near abstentions at frame `000432`, cameras 6 and 8, both concern `pedestrian:35` (annotated center 0.880 m); they are correlated views, not two separate missed people. Six selected candidates have >1 m center discrepancy. A particularly concerning threshold crossing is frame `000432`, camera 6, `pedestrian:1`: annotated center 7.567 m, selected surface 2.515 m, with a severely occluded 2D annotation. At frame `000864`, camera 8, `pedestrian:22` has a 2.796 m annotated center and a 3.889 m candidate; its box sits at the view edge. Three detector boxes without a linked evaluable 3D reference also have selected candidates inside 3 m; they are **unknown**, pending image review.

The accompanying `scripts/audit_jrdb_dev_threshold_crossings.py` reads only saved sensor output plus the separate offline evaluator's saved CSV/JSON. It lists center/candidate boundary disagreements, near-center abstentions and unlinked close candidates, groups correlated camera views under each frame/person ID, counts center labels within 0.25 m of the boundary, and writes a review sheet whose human-decision fields are blank. A 3 m crossing is a diagnostic of differing physical quantities and/or possible surface-person misassociation, **not a validated alert false positive or missed encounter**. Do not use labels in the sensor-side candidate script. Inspect the original camera frames and registered LiDAR at the listed rows.

To analyze these four frames after installation:

```bash
python3 scripts/audit_jrdb_dev_threshold_crossings.py \
  > outputs/local/cubberly_threshold_crossing_summary.json
python3 -m json.tool outputs/local/cubberly_threshold_crossing_summary.json
head -15 outputs/local/cubberly_threshold_crossing_review.csv
```

The next coverage gate is the **complete Cubberly development sequence** with existing, unchanged sensor settings and cached detector predictions. These commands require all 1,296 local point-cloud frames, `outputs/local/cubberly_native_full.jsonl`, and the development label ZIP already used for this pilot. They create new filenames; each analysis script refuses to overwrite its review CSV. Run each block only after the preceding one has succeeded.

```bash
python3 scripts/cache_jrdb_dev_sensor_depth_candidates.py \
  --frames $(seq -f '%06g' 0 1295) \
  --csv outputs/local/cubberly_sensor_surface_full.csv \
  > outputs/local/cubberly_sensor_surface_full_summary.json

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

These are still *development-only diagnostics*. Before any held-out moving-scene evaluation, adjudicate a person/alert reference protocol independently, inspect missing matches and timing, decide whether center or surface distance is the actual alert target, implement temporal identity/deduplication, and freeze thresholds on development data. Do not describe matched-box 3 m crossings as event sensitivity or the workstation's offline throughput as robot latency.
