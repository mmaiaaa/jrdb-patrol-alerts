# JRDB research track: narrow question and reserved sensor-only recording

## Research question

In five-camera JRDB recordings from a moving robot, how do dominant LiDAR
depth-band selection and a nearest-return rule differ in **agreement with the
side of an annotated pedestrian center's 3 m threshold**, conditional on a
matched and evaluable 2D/3D annotation? How many near-center disagreements,
abstentions, and unlinked close candidates accompany the difference?

This evaluates a *center-based reference proxy*. A person surface and a
geometric center differ, so this is not person-distance accuracy, a safety
alert measure, event recall, or false-alert frequency. The only complete
sensor-only experiment currently covers Cubberly development (1,296 frames,
47,481 detector boxes, 32,006 linked annotated views). The 66-case blinded
review packet has been generated but its reviewer decisions are still blank.

## Current method and an important baseline issue

The existing Cubberly sensor cache uses fixed five-camera YOLOv8n boxes and
both Velodyne returns projected to native views. Its sensor-only selection
uses 0.5 m horizontal ego-XY bins, at least three returns per bin, at least
eight returns per eligible contiguous band, a 2:1 count dominance rule when
multiple bands qualify, and a 20 m maximum. If none qualifies, it abstains.
Offline evaluator matching uses same-camera 2D box IoU >=0.5 with an
evaluable 3D pedestrian center; annotation labels are never inference inputs.

**Baseline fairness:** `nearest_supported_surface_m` in the current cache is
the median of the *nearest band whose bins each have at least three returns*;
it does **not** require that band to have eight returns. The proposed method
does require eight. Preserve this originally reported baseline, and add a
second, support-matched nearest-eligible-band baseline to a new fixed run
before evaluating any reserved recording. Compute each baseline from the
actual LiDAR radii; existing band-count strings do not retain the exact
median. Do not describe the original nearest baseline as equal-support.

Predefine the following primary output for the next comparison: for each
method, report numbers of linked evaluable near/far center views whose
sensor candidate is inside, outside or unavailable at 3 m; report the paired
candidate-versus-baseline table on *identical* available detector boxes.
Always report selection coverage, unmatched detector boxes and no-eval
exclusions separately. Include a boundary stratum within 0.25 m of 3 m and
qualitative failure cases, without choosing parameters based on the
held-out outcome. Summarize by frame/person ID and by recording as well as
camera views; multiple camera views of a frame/person are correlated, and a
single new recording does not yield robust sequence-level uncertainty.

## Allocation and order of operations

1. **Development:** Cubberly, already inspected extensively. Finish the
   66-case blinded review, keeping the reviewer sheets separate from the
   annotation key until decisions are saved. Use these cases to decide whether
   the proposed method can be frozen without further changes. An enriched
   sample is not an unbiased error-rate estimate.
2. **Reserve:** `memorial-court-2019-03-16_0` is a different, verified-moving,
   **outdoor** recording in the dataset authors' Figure 2. This probes a
   combined location/environment shift from indoor Cubberly, not a clean
   same-environment replication. Do not select or discard it based on
   proximity labels or algorithm results. Reserve further independent groups
   before seeing their outcomes if a wider generalization claim is desired.
3. **Prepare sensors only:** Run `prepare_jrdb_holdout_sensors.py` in
   preflight mode now. It reads ZIP member metadata for this fixed recording,
   checks matching stream IDs, and never opens `labels.zip`. `--extract`
   stages only stitched/image-0 images, both LiDAR streams, and calibration,
   subject to sufficient disk space. Manifest status is
   `holdout_sensor_only_unscored`. Merely extracting sensors is **not** an
   evaluation or a freeze. Native cameras 2/4/6/8 remain in `train_images.zip`
   for the detector; existing Cubberly inference/evaluation scripts reject
   non-development manifests and must be generalized deliberately.
4. **Freeze before any Memorial score:** Record the exact method, fair
   baselines, detector weight hash, matching and exclusion rules, 3 m
   comparator, calibration assumptions, expected outputs and cross-sequence
   code version in Git. Then run sensor-only inference with the same settings
   on the reserved recording. The separate offline evaluator may open its
   2D/3D labels *once*, only after predictions and the protocol are frozen.
5. **Paper:** Limit claims to center-threshold agreement and the observed
   near/abstention trade-off. Report both recordings distinctly and explain
   indoor/outdoor domain shift, shared annotation provenance, possible
   interpolation and timing ambiguity. Do not turn this experiment into an
   event-level or robot-online claim. The JRDB authors note that annotations
   can be interpolated from a lower annotation rate; stratify on recorded
   interpolation flags if verified for this release.

Reference: [JRDB original paper, Figure 2 and annotation discussion](https://arxiv.org/html/1910.11792v4).
