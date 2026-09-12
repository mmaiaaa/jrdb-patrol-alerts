# JRDB Method Freeze — 2026-09-12

## Purpose

This commit freezes the JRDB range-comparison protocol before
inspection of outcomes from any additional JRDB recording.

Cubberly was used for method development and diagnostic review.
No parameters may be changed in response to results from the
subsequent cross-recording evaluation.

## Development recording

cubberly-auditorium-2019-04-22_0

## Frozen comparison

The comparison consists of:

1. the existing depth-band / surface-candidate method;
2. the existing nearest-return / nearest-supported-surface baseline;
3. the fixed 3.0 m decision boundary.

All numerical parameters, ROI definitions, calibration handling,
surface-band construction, minimum-support rules, ambiguity rules,
and candidate-selection rules are frozen exactly as implemented in
the source files captured by this commit and its freeze manifest.

The 3.0 m criterion is evaluated exactly as implemented by the
current offline evaluation. No temporal persistence, alert timing,
or robot-latency mechanism is added to this experiment.

## Candidate abstentions

A candidate-method abstention remains an abstention.

An abstention must not be replaced with the nearest-return baseline
or another imputed distance merely to increase coverage.

Coverage and abstention counts must therefore be reported separately
from the comparison among cases where a candidate distance exists.

## Annotation eligibility

The existing annotation-eligibility and matching rules are frozen.

Ground-truth/reference cases must not be removed merely because the
candidate method abstained or because a detector/range estimate was
unavailable.

Any annotation ignore/exclusion rules already implemented in the
frozen evaluator must be applied identically to every recording.

## Unlinked detector boxes

Detector boxes that cannot be linked to an eligible reference
annotation remain a separate diagnostic/coverage category.

They are not automatically relabeled as false positives.

Unlinked boxes may be described and counted but are not converted
into an accuracy claim without independent annotation establishing
their status.

## Human blinded review

The enriched Cubberly diagnostic sample contains 66 fixed cases.

The human reviewer completed all 66 cases before the cross-recording
evaluation was opened.

Human-review results are descriptive evidence only. Because this was
an enriched diagnostic sample, its counts must not be converted into
a population accuracy percentage.

Completed reviewer workbook SHA-256:

ceff3fbb2187c96d0fc3582792d0e6eaaadece2a4e71179c1f7916846a97e9b8

Review summary:

- visible person: 59 yes, 7 uncertain
- association: 37 clear, 29 uncertain
- among the 59 visibly-person cases:
  - 37 clear associations
  - 22 uncertain associations
- foreground surface: 43 clear, 23 uncertain
- occlusion/image-edge issue: 40 yes, 26 no
- reviewer confidence: 17 high, 32 medium, 17 low

No accuracy percentage is inferred from these counts.

## D039 rendering reproducibility note

A replay audit of all 66 selected cases found exact sensor replay for
65 cases.

D039 was the sole rendering discrepancy:

- cached candidate: 2.797 m
- replayed candidate: 2.795 m
- cached inner-ROI points: 311
- replayed inner-ROI points: 310

The candidate status remained unchanged and the same physical
foreground depth band was uniquely identified. This was treated only
as a blinded-case-sheet rendering compatibility issue.

It does not change the frozen range-estimation algorithm or introduce
a new evaluation tolerance.

## Cross-recording reporting

For every subsequent recording, report at minimum:

- recording identity;
- eligible reference count;
- candidate coverage;
- candidate abstentions;
- nearest-baseline coverage;
- candidate versus nearest comparison on paired eligible cases;
- near/far disagreements around the fixed 3.0 m boundary;
- unlinked detector boxes separately;
- recording-specific results rather than only a pooled total.

The paper must discuss both benefits and failure modes.

The study does not claim temporal security alerts or robot/system
latency because those experiments have not been conducted.

## Freeze rule

After this commit/tag, the method implementation and comparison rules
must not be changed based on outcomes from the new JRDB recordings.

Any later bug fix must be documented explicitly and must trigger a
rerun of every recording under the corrected implementation.
