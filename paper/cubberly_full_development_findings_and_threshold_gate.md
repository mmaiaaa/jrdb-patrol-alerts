# Cubberly full-development surface diagnostic and next gate

The sensor-only cache covers all 1,296 Cubberly development frames and contains 47,481 five-camera detector boxes. After a separate 2D-IoU ≥0.5 and same-ID 3D annotation join, **32,006** boxes have an evaluable 3D center reference (67.4% of detector boxes). Of those linked box views, 28,712 (89.7%) have a selected LiDAR surface candidate. The remaining 15,475 detector boxes have no evaluable 3D-linked match under this particular association procedure; this is an unknown pool, not a set of false detections.

On the **same 28,712 linked candidate views**, median absolute measured-surface-to-annotated-center XY difference is 0.092 m for the selected surface versus 1.956 m for the nearest supported return. Selection is more than 0.25 m closer in 17,612 views, while nearest is more than 0.25 m closer in 83; 11,017 differ by no more than 0.25 m. Nonetheless **1,597 selected candidates (5.6%)** are more than 1 m from the annotated center. Discrepancies are **not measured person-distance errors**: surface and geometric center differ physically, annotation and returns share source data, and 2D and 3D labels may share provenance.

Of 3,971 linked camera views with annotated centers ≤3 m, 3,639 (91.6%) yield selected surface candidates. They correspond to **2,952 distinct frame/person IDs** over 1,054 frames containing at least one linked near ID; neither percentage is proximity recall. For the identical 3,639 near-center candidate views, selected-versus-nearest median differences are 0.082 versus 0.086 m. The selected surface is materially closer in 207 views, nearest in 27, and 3,405 differ by ≤0.25 m. This suggests the full-sample numerical advantage is largely outside the near subset, an inference to verify with a threshold comparison and a review of distant-person foreground overlap.

The existing paired review list includes **332 linked near-center abstentions**, 1,597 linked selected-surface discrepancies over 1 m, and **1,035 selected candidates inside 3 m without an evaluable 3D-linked reference**. The 16,276 nearest-band improvement rows are repeated camera-box observations, not independent encounters. Review cases sampled from these pools before interpreting any rate. The four-frame pilot is contained within this development run, so these full numbers are not an independent replication.

Next, run the new `scripts/audit_jrdb_dev_threshold_crossings_v2.py` on the *unchanged* full CSVs. In addition to the existing candidate-center boundary worklist, it compares selected and nearest surfaces on the **same linked camera-box views** and reports counts by annotated-center side and by whether the center falls within 0.25 m of the exploratory 3 m boundary. All outputs remain descriptive center-threshold concordance, **not alert false-positive or missed-encounter metrics**.

```bash
python3 scripts/audit_jrdb_dev_threshold_crossings_v2.py \
  --candidate-csv outputs/local/cubberly_sensor_surface_full.csv \
  --reference-csv outputs/local/cubberly_surface_reference_full.csv \
  --reference-summary outputs/local/cubberly_surface_reference_full_summary.json \
  --review-csv outputs/local/cubberly_threshold_crossing_full_review_v2.csv \
  > outputs/local/cubberly_threshold_crossing_full_summary_v2.json

python3 - <<'PY'
import json
p = 'outputs/local/cubberly_threshold_crossing_full_summary_v2.json'
r = json.load(open(p))
for key in ('linked_frame_camera_box_views', 'linked_view_status_counts',
            'paired_center_threshold_concordance',
            'unique_near_frame_person_ids',
            'unlinked_candidate_inside_3m_views_for_review'):
    print(f'{key}: {r.get(key)}')
PY
```

Full camera-image review and source timing checks are still pending. A practical next annotation task is to inspect all genuinely conflicting threshold cases plus a **prespecified stratified random sample** of unlinked close boxes, near abstentions and >1 m discrepancies, keeping repeated camera views and adjacent frames together. Preserve blank human-decision fields until someone reviews the native images, LiDAR and surrounding frames. Define the actual person-distance target, complete tracking/deduplication and independent event labels, freeze the method on development data, and then evaluate on untouched moving locations before making a patrol-alert performance claim.
