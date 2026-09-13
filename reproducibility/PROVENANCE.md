# Artifact Provenance

## YOLO weight

File:

    yolov8n.pt

SHA-256:

    f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36

The detector is the COCO-pretrained YOLOv8n model used
by the frozen experiment.

## JRDB calibration

The experiment consumes the JRDB-provided calibration
members:

    calibration/cameras.yaml
    calibration/lidars.yaml
    calibration/defaults.yaml

The individual file hashes used by the local audit are
recorded in:

    audit-2026-09-13/provenance/calibration-files.sha256

The range pipeline combines the upper and lower LiDAR
using the JRDB calibration transforms, including
lower2upper and upper2ego, and computes horizontal
ego-frame radius after the ego transform.

## Raw data

JRDB raw archives and labels are deliberately excluded
from Git. Archive hashes are recorded in:

    audit-2026-09-13/provenance/jrdb-source-archives.sha256

This allows local source data to be verified without
redistributing the dataset.
