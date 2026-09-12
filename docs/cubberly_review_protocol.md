# Cubberly moving development review

Status: development procedure, **not a frozen event definition or result**. The verified moving sequence is `cubberly-auditorium-2019-04-22_0`. Its 1,296 image/point-cloud frame IDs match the 3D label frame IDs; this is a filename check, not a timestamp or coordinate-calibration check. The preliminary 3 m rule finds 1,058 frames with an evaluable nearby person and 238 without one. Those 238 frames can be grouped into much fewer contiguous intervals and are not verified person-free exposure.

## Generate the review queue

Run `python3 scripts/audit_jrdb_dev_boundaries.py > outputs/local/cubberly_boundary_summary.json`. The script reads only the development manifest and local 3D labels and writes `outputs/local/cubberly_reference_review.csv`. It refuses to overwrite an existing CSV so manual decisions cannot be lost by rerunning it; use `--csv` with a new filename for another exploratory setting. It does not produce online predictions or scored reference events. The radius is an exploratory candidate-generation setting. Keep this CSV local until the image-sharing terms are checked, and commit only the script and de-identified methodology.

The candidate-run rows separate `left_censored` (already near in frame 0), `candidate_observed_entry` (same identity evaluably far in the immediately preceding frame), and `first_seen_inside_or_unknown` (previous observation missing or ignored). Similarly, `candidate_observed_exit` requires the same identity evaluably far in the next frame, `right_censored` reaches the last frame, and `lost_or_unknown` has no confirmed exit. These are *one-frame diagnostics*, not manual entry/exit verdicts. The negative-interval rows mean no **evaluable label** is near; they do not prove that there is no nearby person. Inspect `frames_with_no_eval_near` before treating any interval as a negative candidate.

## Human and sensor review

Before examining detector output, inspect each near-person run's first and last several frames, all 3 m boundary transitions, all provisional negative intervals, and a documented sample of interiors of long runs. Check stitched imagery, a native camera image where relevant, the label record and `no_eval`/interpolation flags, upper/lower LiDAR, and any available timing information. Record frame IDs and reason for each decision. If the 3D box center or sensor frame is ambiguous, mark **unresolved**; a visually close person alone cannot verify 3 m. Label a frame with no evaluable person as **unverified negative** until coverage and metric interpretation are checked. Keep a separate category for people already inside at start and those still inside at end.

Use reviewer decisions such as `confirmed_candidate`, `initial_occupancy`, `loss_or_occlusion`, `reentry_possible`, `unresolved`, and `exclude_with_reason`, with explanatory notes; these are proposed annotation codes, not inferred truth. Have a second reviewer independently judge disputed boundaries and a representative sample if feasible; record disagreement and adjudication. Keep reviewers blind to the proposed alert method. Do not change candidate definitions based on which method performs better.

## Gates before scoring

1. Validate robot-relative coordinate conventions, image/LiDAR alignment, and the intended person-center distance with recorded overlays and points; establish actual acquisition timestamps or label exposure only in frames.
2. Specify sustained duration, allowable gaps, treatment of unknown/no-eval observations, initial occupancy, re-entry and right censoring. Write and version the event builder; keep it separate from online inference.
3. Reserve recording groups for validation and a genuinely untouched test before tuning; Cubberly is **development only**. Assess negatives on recordings with enough independent exposure, not by counting frames as events.
4. Run a detector and a tracker on the raw stitched or native images, infer metric distance from contemporaneous sensor data without reading reference boxes or IDs, then cache predictions for all alert methods. Benchmark real end-to-end latency on the RTX 2060.
5. Compare raw threshold, persistence, hysteresis/cooldown, and proposed encounter memory under the same detections, reference policy and validation tuning budget. Freeze configurations before the held-out evaluation and report group-level uncertainty.

JRDB person-near-robot events do not establish unauthorized access or actual security intrusions. A security intrusion claim would require separate region/access policy and independent annotations.
