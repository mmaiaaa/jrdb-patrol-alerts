# Cubberly raw-image detector pilot (development; draft)

This note records a preliminary detector-cache run on the **moving** JRDB 2022 training recording `cubberly-auditorium-2019-04-22_0`. It uses frames `000070`–`000149` from each of the five native cameras (0, 2, 4, 6, 8), for 80 five-view sets and 400 native JPEGs. Cubberly is development data. The detector run did not read ground-truth labels, camera timestamps, or LiDAR range. No independent person-level or alert-level evaluation follows from these counts.

## Reproducibility record

- Cached detections: `outputs/local/cubberly_native_pilot.jsonl`; run summary: `outputs/local/cubberly_native_pilot_summary.json`. Both are local outputs and are not committed to Git.
- Input code commit, as recorded by the run: `857cfa6b6f60b62023760daec17e96c3c41aec9d`; working tree clean. This identifies code provenance, not the SHA-256 of the downloaded image archive.
- Model: COCO-pretrained `yolov8n.pt`, SHA-256 `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`. Inference was class 0 (person), confidence 0.1, IoU 0.7, image size 640, device 0, batch size 1, frame-then-camera order.
- Recorded software: Python 3.12.14, PyTorch `2.13.0+cu126`, Ultralytics 8.4.150, OpenCV 5.0.0. Workstation: RTX 2060 (6 GB). This was offline decoding and inference on the workstation, not a deployed robot.

## Observations and immediate quality check

The cache contains 400 camera-frame rows. The counts of **detection boxes**, by camera 0/2/4/6/8, were 245/0/444/449/171. Boxes are not unique people, matched tracks, or independent encounters. In particular, camera 2 reported no person boxes for any of its 80 frames; this must be checked against the actual images before interpreting scene coverage or detector sensitivity. Low-confidence overlapping boxes may also describe the same person and deserve review.

The recorded end-to-end elapsed time was 13.927 s, or 28.722 camera images/s and 5.744 complete five-camera sets/s averaged over this **short cold run**. The first cached camera row alone took 11.097 s, approximately 79.7% of the reported elapsed time. The summary's 5.279 ms median camera-image time is a different statistic; neither gives a validated sustained five-view throughput, camera-to-alert latency, or latency on a robot. A later repeated, synchronized and warmed benchmark should report distributions for decode, detector, association and alert stages separately.

Run `scripts/review_jrdb_native_detections.py` against the cached JSONL and the source image archive. It checks that each cached frame has all five camera entries, counts empty images and strongly overlapping pairs of boxes, and renders native camera views with detector boxes for frames 000070, 000086, 000087 and 000143. Inspect camera 2 on all four samples, and compare the other cameras at the candidate boundary 000086/000087 and later at 000143. These images are diagnostic and are kept in `outputs/local/`; they are not independently annotated reference events.

## Work needed before an alert result

Confirm visually whether camera 2 sees people and diagnose its zero-box cache if so; validate projection/association of native detections to measured LiDAR range without using reference 3D labels in the alert pipeline. Establish frame timing, inspect raw sensor alignment and tracker behavior, and independently review development encounter starts, censored ends and candidate negative intervals. Then freeze alert logic and thresholds on development recordings before applying an agreed, location-separated, untouched final evaluation. Report encounter-level detection, false alerts per verified exposure time, event latency, uncertainty across independent recordings, and comparable baselines. None of those results has yet been measured here.
