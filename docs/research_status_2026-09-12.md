# Research status — 2026-09-12

## Research question

Can a patrol robot issue reliable, timely **person-proximity alerts** from its own camera and LiDAR streams under changing camera visibility and robot motion? This experiment does not yet support a claim about unauthorized entry or security intrusion.

## Evidence completed

| Part | Status | Bound on the claim |
| --- | --- | --- |
| Research repository and workstation | Code/manifests and working CUDA RTX 2060 setup recorded | Functional GPU operation is not an online benchmark. |
| JRDB 2022 data audit | Four train archives inventoried and hashed; 27 train sequences have matching four-stream frame IDs | Matching IDs do not establish acquisition-time synchronization. |
| Stationary bytes-cafe feasibility pilot | 3D label flags and stitched/native pose inspected; exploratory proximity runs enumerated | Interpolation, visibility and censoring prevent treating these as independent reference alerts. |
| Moving Cubberly development scene | 1,296 four-stream frames extracted; 37 provisional near-person runs, 34 apparent exits, 3 right-censored; 238 provisional no-evaluable-near frames form 3 intervals | Boundaries and negatives are not independently adjudicated. |
| Raw-sensor registration | Seven upper-LiDAR/camera-0 compressed-cloud overlays generated and visually inspected | No quantitative projection residual, cross-camera registration or verified timing. |
| Five-native-camera detector pilot | 80 consecutive frames × 5 cameras cached from raw JPEGs; weights, settings, environment and code commit recorded | Only 2D boxes; no identities, measured ranges, alerts or held-out scores. |
| Detector visibility quality check | All 80 zero-box camera-2 frames viewed in contact sheets; camera 8 zero-box sheet reveals a possible partial-edge person | Visual triage at thumbnail resolution, not a complete independent person reference. |
| Manuscript | Feasibility, projection, detector and limitation notes drafted in parallel with code | No validated main results or journal-ready evaluation yet. |

## Gates ahead

1. Cache and check all 1,296 Cubberly development frames, then inspect camera/view variation and detector misses at full resolution.
2. Verify timing and per-camera geometry; implement and validate measured LiDAR range association, cross-camera duplication handling, tracking and alert logic without reference-label access at runtime.
3. Human-adjudicate reference encounter boundaries and genuine negative exposure; specify identity, occlusion, censoring, annotation eligibility and time units.
4. Assign independent location/session groups for development, validation and final holdout; reserve multiple moving groups if available. Keep proposed final scenes closed until the protocol is frozen.
5. Compare meaningful simple baselines with the proposed alert logic on identical cached predictions; tune only on development/validation. Report encounter-level recall/precision, false alerts per verified exposure, delay and uncertainty across independent sequences; then test the frozen method once.
6. Benchmark sustained end-to-end throughput and latency on the actual target after warmup; decide on hardware only from that workload and its required latency.

This work is past data access and basic pipeline feasibility, but the substantive scientific evaluation remains ahead. The next claim should be limited to reproducible **development-stage feasibility** until reference events, sensor-only range, baselines and independent evaluation are complete.
