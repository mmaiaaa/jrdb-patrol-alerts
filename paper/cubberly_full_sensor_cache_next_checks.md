# Cubberly full development cache: next checks

The batched **sensor-only** pass completed all 18 batches and produced 47,481 box rows over all 1,296 Cubberly development frames, with no reused batches. This matches the sum of the earlier five-camera cached detection totals (`12,559 + 9,426 + 13,581 + 7,476 + 4,439 = 47,481`). It confirms accounting consistency, not camera detection quality, person association, range correctness, or alerts.

Do the next computations in this order. The existing offline evaluator reads development 2D/3D labels **after** the sensor cache was fixed. The new `analyze_jrdb_dev_surface_discrepancies_v2.py` uses a set to check detector box uniqueness efficiently for tens of thousands of rows; the earlier four-frame script scanned all previous matches for each row. `--compact` keeps the full-sequence JSON short while writing the entire prioritized review CSV. Source, calibration, and candidate CSV hashes remain in the results.

```bash
python3 scripts/evaluate_jrdb_dev_surface_candidates_offline.py \
  --candidates outputs/local/cubberly_sensor_surface_full.csv \
  --candidate-summary outputs/local/cubberly_sensor_surface_full_summary.json \
  --csv outputs/local/cubberly_surface_reference_full.csv \
  > outputs/local/cubberly_surface_reference_full_summary.json

python3 scripts/analyze_jrdb_dev_surface_discrepancies_v2.py \
  --compact \
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

Each script writes its CSV only if that path does not exist. If an earlier command failed or its output already exists, inspect the file before changing a path or retrying; avoid mixing summaries from different sensor runs. To print a compact check rather than dumping all frame-wise results:

```bash
python3 - <<'PY'
import json
from pathlib import Path
root = Path('outputs/local')
for name in ('cubberly_surface_reference_full_summary.json',
             'cubberly_surface_paired_full_summary.json',
             'cubberly_threshold_crossing_full_summary.json'):
    result = json.loads((root / name).read_text())
    print(name)
    for field in ('status', 'counts', 'all_linked', 'center_within_3m',
                  'linked_view_status_counts', 'unique_near_frame_person_ids',
                  'unlinked_candidate_inside_3m_views_for_review'):
        if field in result:
            print(f'  {field}: {result[field]}')
PY
```

Numbers should be reported with denominators and selection conditions. Selected-versus-nearest surfaces must be compared on the same linked boxes; near-person annotation frame/person IDs and repeated camera views are different units. Do not call surface-versus-3D-center differences "distance accuracy," classifying annotated centers inside 3 m "alert recall," or unlinked close boxes "false alarms." Once the complete development worklists exist, prioritize boundary crossings, abstentions, occlusions, rare locations and unlinked candidates for native-resolution human review; define the human adjudication protocol and the actual person-distance target before freezing an alert algorithm. The Cubberly data remain development only, with untouched moving recordings needed for test claims.
