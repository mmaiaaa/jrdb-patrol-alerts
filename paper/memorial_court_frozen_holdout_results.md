# Memorial Court Frozen Holdout Results

Sequence: `memorial-court-2019-03-16_0`

Method freeze:
`jrdb-method-freeze-2026-09-12`

The Memorial Court sensor outputs were generated and frozen before
reference annotations were opened. No detector, range-estimation,
matching, eligibility, abstention, or 3 m decision parameter was
changed after reference opening.

## Evaluation population

- detector boxes: 24,992
- evaluable native 2D labels: 18,390
- detector/2D matches at IoU >= 0.5: 13,349
- matches with evaluable 3D centers: 13,246
- unlinked detector boxes: 11,643
- unmatched evaluable 2D labels: 5,041
- 2D matches without evaluable 3D reference: 103

Unlinked detector boxes are not automatically false positives.

## Range coverage

Frozen depth-band method:

- available: 12,354 / 13,246
- unavailable/abstain: 892

Nearest-supported-surface baseline:

- available: 12,992 / 13,246
- unavailable: 254

The depth-band method is therefore deliberately more conservative.

## Paired continuous comparison

On the 12,354 cases where both methods returned a range:

- depth-band median absolute surface-to-center discrepancy: 0.0763 m
- nearest baseline median: 0.0874 m
- depth-band mean absolute discrepancy: 0.1757 m
- nearest baseline mean: 0.8527 m

Pairwise:

- depth-band lower discrepancy: 1,841
- nearest lower discrepancy: 5
- equal discrepancy: 10,508

Surface range and annotated person-center radius are different
physical quantities, so these values must not be described as direct
person-distance error.

## Frozen 3 m decision comparison

Reference distribution:

- center radius <= 3 m: 842
- center radius > 3 m: 12,404

Depth-band method:

- reference near -> predicted near: 820
- reference near -> predicted far: 10
- reference far -> predicted near: 179
- reference far -> predicted far: 11,345
- unavailable/abstain: 892

Nearest baseline:

- reference near -> predicted near: 835
- reference near -> predicted far: 7
- reference far -> predicted near: 422
- reference far -> predicted far: 11,728
- unavailable: 254

On the 12,354 paired available cases:

- both methods agreed with the reference: 11,940
- depth-band only agreed: 225
- nearest only agreed: 3
- neither agreed: 186

All 228 method disagreements were:

depth-band = far; nearest baseline = near.

Thus, among paired disagreements, supported-surface selection corrected
225 nearest-return near classifications while changing 3 cases in the
opposite direction.

This should be interpreted as evidence that supported-surface selection
can suppress spurious near assignments caused by nearer nuisance
returns, at the cost of lower coverage and conservative abstention.

## Limitations

- Observations are dependent across adjacent frames, cameras, and
  repeated appearances of the same people.
- Only one independent holdout recording has been scored.
- Surface range is compared with annotated 3D center radius.
- The 3 m reference distribution is strongly imbalanced toward
  farther-than-3-m observations.
- This is not an encounter-level alert experiment.
- No robot latency or temporal-alert performance is claimed.

## Provenance

Memorial detector predictions SHA-256:

`d2d86947287c3e05654c8ec9913445990bebcb3b36b1b9cc841e1d593df36f13`

Memorial sensor candidate CSV SHA-256:

`8d3bd65efdc9fc1033cc611a38c67653ada8971a0eef1b9f5332847aabce9e51`

Memorial reporting JSON SHA-256:

`d23e899bf7a7fa9e36b51057de1e381a0b1fba81a1092da08a760696d1bfdd10`
