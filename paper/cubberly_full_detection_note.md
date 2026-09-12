# Full Cubberly detector cache (development results draft)

The raw-image detector has now been run on all **1,296 frames × five native cameras = 6,480 JPEGs** of the moving JRDB 2022 development recording `cubberly-auditorium-2019-04-22_0`. The cache begins at frame `000000` and ends at `001295`; a separate review found all 6,480 frame/camera entries. It is not a held-out comparison. No reference 3D labels, person tracks, distance-to-person, timestamps or alert events were inputs to this inference run.

The reported detector inputs were `yolov8n.pt`, SHA-256 `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`, class 0 (person), confidence 0.1, NMS IoU 0.7 and input image size 640. Code commit was `60ad21632c69ea1ccff6492d238a0c3b6dcd6f00`, with a clean working tree. Software was Python 3.12.14, PyTorch `2.13.0+cu126`, Ultralytics 8.4.150 and OpenCV 5.0.0. The prediction JSONL and run summaries are stored under ignored `outputs/local/` paths on the workstation.

| Native camera | Detection boxes | Frames with zero boxes | Median boxes per frame | Same-view pairs at IoU ≥ 0.5 |
| --- | ---: | ---: | ---: | ---: |
| 0 | 12,559 | 9 | 9 | 3,011 |
| 2 | 9,426 | 247 | 7 | 2,013 |
| 4 | 13,581 | 0 | 9 | 3,696 |
| 6 | 7,476 | 3 | 5 | 1,883 |
| 8 | 4,439 | 291 | 3 | 980 |

These are **47,481 boxes** and **11,583 overlapping box pairs**, not independent people, false positives or duplicated-person events. An empty image can contain an undetected person; a nonempty image can contain false detections. The full recording contains many camera-2 boxes: its 80 consecutive empty images in the original pilot were a local view of a mostly blank wall, not evidence that camera 2 failed for the sequence. The raw-image coverage review made example five-view sheets at frames `000000`, `000432`, `000864` and `001295`; those sheets must be inspected before reporting qualitative generalization claims.

The script reported 35.567 seconds for offline sequential decode, per-camera inference and transfer, corresponding to 182.191 camera images/s or 36.438 five-camera sets/s **averaged over this one run**; the median per-image time was 5.19 ms. The earlier short cold-start pilot took 13.927 seconds for 400 camera images, including an 11.097-second first image. Different startup states and workloads make these two totals unsuitable for estimating general deployment capacity. Neither run includes point-cloud decoding, cross-camera reconciliation, range estimation, tracking, alert-state updates, end-to-end latency or actual robot timing. Do not present camera sets/s as synchronized sensor FPS or claim real-time alerts from this measurement.

The next gate is a raw-sensor diagnostic that projects the contemporaneous upper-LiDAR cloud into **each** native view and overlays these points with the cached boxes on sampled development frames. Inspect alignment at the proposed camera/time pair before attempting foreground separation or metric person range. Points falling inside a box can belong to a wall or a person, and lidar XY radius is not itself a confirmed person distance. Keep reference boxes and IDs out of runtime inference. Independently specify and adjudicate ground-truth encounter boundaries, timestamps/exposure, and held-out location groups before scoring alerts.
