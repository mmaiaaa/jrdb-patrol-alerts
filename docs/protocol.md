Study protocol — DRAFT, NOT FROZEN

Protocol identifier: `jrdb-patrol-v0`. Prepared 2026-09-12. All unmeasured quantities and unresolved choices below remain proposals. This document is a versioned development protocol, not a registered or completed study.

**Question and claim.**

Can a causal encounter manager reduce false and duplicate proximity alerts caused by localization noise and fragmented person tracks while preserving timely encounter recall? The primary output is a timestamped alert per qualifying person encounter. Detector and tracker accuracy are supporting outcomes.

H1: the proposed method reduces false alerts per monitored hour relative to the strongest validation-selected conventional temporal baseline while satisfying the same predeclared recall and delay requirements.

H2: any benefit remains measurable in occluded and moving-camera recording groups and is not explained by suppressing distinct people or waiting longer.

H3, secondary: the conclusion transfers to an alternative tracker and, where collected, independent patrol recordings. Treat these as separate evaluations, not an excuse to retune on the final holdout.

A reduction in duplicate alerts alone does not establish H1 or H2. A null result is publishable evidence only to the extent that the task, comparison, precision, and insight warrant it. Conventional hysteresis or cooldown logic alone is not a claimed algorithmic invention.

**Task semantics.**

The proposed primary event is sustained person occupancy of a robot-relative metric region. An illustrative radius is 3.0 m and an illustrative minimum duration is 0.5 s. These are not final values or safety standards. Their justification and feasibility must be recorded before protocol freeze.

Use horizontal person-center distance in a verified robot frame unless the policy is explicitly changed to body-surface or footprint distance. A camera-frame vector must be transformed correctly before applying a horizontal distance rule. The robot moving near a stationary person is also a proximity encounter; the task does not infer intent or who initiated the approach.

Before generating final reference events, specify boundary inclusivity, timestamp alignment, observed entry versus initial occupancy, gaps/unknown labels, eligibility time, closing/re-entry rules, selected field of view, and right-censored endings. Minimum task duration is independent of the predictor's confirmation settings. Unknown range in predictions remains unknown; it is not replaced by annotated range.

Reference-event generation is a separate module with a fixed policy. Ground-truth labels and identities are used for references and evaluation, never online association. Reference construction may inspect the full labelled sequence to determine whether a duration condition was met. Online alerts may use only the available past and present.

**Data, selection, and pilot.**

JRDB provides robot-view imagery, LiDAR, and person annotations suitable for a metric encounter task. [Dataset documentation](https://jrdb.erc.monash.edu/dataset/)

Begin with one development sequence and one annotated native camera view, paired labels, calibration, timestamps, and the required point clouds. Verify projection overlays and frame alignment, including occlusion and image-edge cases. Record camera geometry and actual annotation coverage. Do not assume that the selected download package contains all required calibration or motion information.

Record the exact dataset release, source, sequence, recording group, selected stream, frame range, duration, archive/file hashes, and exclusions in `manifests/sequences.csv`. No sequence has been selected at M0. The actual event count and exposure are unknown.

Treat a pilot inspected for debugging as development data. Use metadata and a predetermined sampling plan for selection, not the observed performance of the proposed method. If the pilot cannot produce trustworthy metric events, stop expansion and resolve the geometry/range problem or explicitly narrow the scope.

**Splits and independence.**

Use development for implementation/error-model fitting, validation for selecting an operating point, and an untouched final test for primary claims. Confirm the selected release's official split. If a custom location/session holdout is used, label it distinctly and do not treat its metrics as official leaderboard results.

Repeated locations or sessions can induce dependence across sequence names. Keep the same recording group together where a location-generalization claim is intended. Never randomly split frames or treat multiple camera views of one time interval as independent data. Document pretrained model data and any fine-tuning exposure.

Publish split identifiers and decision history before evaluating the final test. A protocol modification after test inspection is exploratory unless a new holdout is used. A Git timestamp documents the record; it is not proof that no test information was observed or a substitute for preregistration.

**Perception and proposed method.**

Use one reproducible pretrained detector/tracker and a sensor-derived metric localization procedure for the pilot. Point association inside predicted image boxes must handle ground/background points, sparse returns, overlapping people, and synchronization. Measure range error and missing-estimate rates near the event boundary. Document whether the estimator predicts a surface or a center and any development-fitted bias correction.

The alert manager's conceptual states are outside, candidate, active, and uncertain. Active encounters emit once; uncertain retains bounded memory during lost observations. Confirmed exit and the reference-independent prediction re-entry rule permit later alerts.

Encounter identity is distinct from the raw tracker ID. Use a conservative one-to-one geometry/time association when a track resumes, and measure suppression of distinct people. If uncertainty is used, calibrate position/association uncertainty and assess empirical coverage; detector confidence is not a calibrated proximity probability.

Use independently obtained ego-motion for temporal position comparison when available. Otherwise acknowledge the limits of bounded robot-relative continuity during turns. Consecutive robot-relative positions do not directly give a person's world velocity.

The exact detector, tracker, localization algorithm, uncertainty model, and gating parameters are unresolved. Do not call these components implemented or novel at M0.

**Comparisons and ablations.**

| ID | Method | Implementation status |
|---|---|---|
| B0 | Raw entry threshold per predicted identity | Planned |
| B1 | Time-based persistence before alerting | Planned |
| B2 | Hysteresis and per-ID cooldown | Planned |
| B3 | Causal spatial/temporal encounter memory | Planned |
| P0 | Proposed uncertainty-aware encounter memory | Planned |

All methods receive the same cached sensor predictions, reference events, monitored region, and scoring protocol. Give meaningful tuning budgets to the simpler methods. Select the primary comparator on validation data, and fix it before final testing. Ablate uncertainty, encounter memory, and hysteresis separately. Add an alternative tracker only after the alert comparison is functioning.

Perfect-track and corrupted-reference experiments are diagnostics, explicitly marked oracle or simulated. Corruption levels should be grounded in development errors where possible. Their seeds do not create additional independent real recording groups.

**Primary decision rule.**

Select configurations on validation data to minimize false alerts/hour subject to justified minimum recall and maximum delay limits. Illustrative values discussed during planning are 90% recall and a 1 s response deadline, but they are not frozen requirements. Fix the exact definition of timely recall, any noninferiority margin, and the handling of infeasible configurations before the final comparison. Report both absolute constraints and paired effect estimates.

If no method meets the constraints, report infeasibility; do not relax them based on the final-test result. Report trade-off curves as secondary analysis without selecting a new winning test operating point.

**Evaluation.**

Match reference encounters to emitted alerts one to one using predefined time and localization/identity-compatibility gates. Optimize valid match cardinality before deterministic cost. Predicted IDs need not equal annotated IDs. Duplicate alerts count as unmatched alerts after a reference event is matched. Distinct-person suppression creates misses.

Main outputs are event recall, precision, false alerts per monitored hour, duplicate alerts, missed encounters, timely-detection rate over all eligible events, and signed delay from physical entry and fixed eligibility time. Report delay among matches together with misses so the method cannot appear fast simply by missing difficult events. F1 and tracking metrics are secondary.

Exposure counts synchronized monitored time once, not once per camera or person. Retain negative sequences for false-alert rates even when their recall is undefined. Report actual minutes, event counts, uncertain/ignored intervals, and recording groups. A rate normalized to hours is not evidence of day-long reliability when observations are short.

Measure complete pipeline throughput and latency, all selected views, queue growth/drop policy, memory, failed inputs, and actual processed counts. Separate cached alert-method time from sensor-to-alert time and research-workstation measurements from intended onboard hardware.

**Statistics and diagnostic strata.**

Use paired resampling at the independent recording-group level and recompute pooled counts/exposure for each bootstrap replicate. Choose sequence-level resampling only when independence at that level is defensible. Report 95% intervals for primary paired effects and per-group results. The final bootstrap settings, independent group definition, and sample-size/exposure justification remain unresolved.

Predefine relevant strata such as moving/stationary robot, occlusion, crowding, and indoor/outdoor recording. Show counts and avoid presenting many exploratory subgroup findings as independent confirmatory claims. Small numbers of independent groups limit inference regardless of frame count.

**Verification before freeze.**

- Geometry and original-timestamp audits with recorded examples.
- Reference-event audit, including initial occupancy and truncated recordings.
- Evaluator cases: two close people, one ID break, genuine re-entry, unknown range, exact boundaries, missing frames, a greedy-assignment failure, and seam duplication if panoramic.
- Causality check: appending future frames cannot change an alert already issued for a prefix.
- Reproduction from cached predictions without ground-truth access by the predictor.
- Frozen method/configuration hashes, split manifest, reference policy, matching, exclusions, tuning budget, and primary comparison.

No scientific verification item above is marked complete at M0.

**Independent security validation.**

A stronger patrol-security claim requires a fixed restricted region, consistent localization/sensors, a declared event/access policy, and independently annotated recordings. Include passes outside the region, entry/re-entry, turns, occlusions, distinct nearby people, and long negative recordings. Keep pilot and final sessions separate and report annotation agreement. A camera cart experiment or offline replay should be identified as such; a diagram does not establish robot deployment.

**Reporting.**

Use the manuscript's evidence ledger to connect every empirical claim to an input commit, run IDs, table/figure, and appropriate uncertainty. Preserve failed and null experiments. Complete the related-work assessment before making an originality claim. Draft prose may describe planned methods; results and conclusions must follow completed evidence.
