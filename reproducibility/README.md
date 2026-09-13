# JRDB Supported Depth-Band Experiment — Reproducibility

## Frozen protocol

Development recording:

    cubberly-auditorium-2019-04-22_0

Independent holdout:

    memorial-court-2019-03-16_0

Method-freeze commit:

    3f9a8daadb832a6c6ea9251869b83be2a28c2746

Method-freeze tag:

    jrdb-method-freeze-2026-09-12

No method parameter was changed after reference annotations were opened.

## Detector

Implementation:

    scripts/cache_jrdb_native_detections.py

Model:

    COCO-pretrained YOLOv8n
    person class only
    confidence = 0.10
    NMS IoU = 0.70
    imgsz = 640
    cameras = 0,2,4,6,8
    batch size = 1

Frozen weight SHA-256:

    f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36

## Camera-LiDAR projection and range association

Projection / geometry source:

    scripts/audit_jrdb_cubberly_projection.py
    scripts/audit_jrdb_dev_box_geometry.py
    scripts/audit_jrdb_box_depth_support.py
    scripts/review_jrdb_native_detections.py

Supported depth-band source:

    scripts/cache_jrdb_dev_sensor_depth_candidates.py
    scripts/cache_jrdb_holdout_sensor_depth_candidates.py

Frozen method:

    horizontal ego-frame range sqrt(x^2 + y^2)
    maximum range = 20 m
    inner ROI = +20% left, -20% right,
                +20% top, -15% bottom
    bin width = 0.5 m
    minimum supported-bin points = 3
    contiguous supported bins form bands
    minimum candidate-band points = 8
    dominance ratio = 2.0
    otherwise abstain
    selected range = median range of selected band
    decision boundary = 3.0 m

The nearest-supported-surface baseline is the median
of the nearest contiguous supported band formed from
bins with >=3 points. It does not use the 8-point
candidate threshold or 2x dominance rule.

## 2D-to-3D reference linking

Source:

    scripts/evaluate_jrdb_dev_surface_candidates_offline.py
    scripts/evaluate_jrdb_holdout_surface_candidates_offline.py

Frozen matching:

    native cameras = 0,2,4,6,8
    one-to-one detector/2D annotation matching
    minimum IoU = 0.5
    no-eval annotations excluded
    reference range = horizontal ego-frame radius
                      of annotated 3D center
    near/far boundary = 3.0 m

Detector boxes that cannot be linked to an evaluable
2D annotation are reported as unlinked rather than
false positives.

## Important measurement interpretation

The algorithm estimates a visible LiDAR surface range.
The reference is the horizontal radius of an annotated
3D box center.

Therefore the reported continuous quantity is an
absolute surface-to-center discrepancy, not a
person-distance error.

## Data

JRDB raw images, point clouds, calibration archives and
reference labels are not redistributed in this repository.

Their identities and SHA-256 values are recorded under:

    reproducibility/audit-2026-09-13/provenance/

## Audit

The audit records:

- frozen Git revision
- source-file hashes
- model-weight hash
- raw detector-cache hashes
- sensor-candidate hash
- calibration provenance
- environment versions
- manifests
- holdout scoring reproduction
- final result arithmetic

Large raw data and local generated outputs remain outside Git.
