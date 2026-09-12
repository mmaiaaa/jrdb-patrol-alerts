# JRDB sequence roles — allocation pending

Status: proposed design record, 2026-09-12. This is **not** the frozen split. The local JRDB 2022 train archive inventory lists 27 sequences, all with matching filenames across stitched/camera-0 images and both LiDAR streams, and 27 3D JSON label files. The source-verified moving/stationary status applies to only four named recordings from [Figure 2 of the original JRDB paper](https://arxiv.org/html/1910.11792v4).

| Recording | Verified robot motion | Planned status before any alert outcomes |
|---|---|---|
| `bytes-cafe-2019-02-07_0` | Stationary | Debugged development pilot; never a final test recording. |
| `cubberly-auditorium-2019-04-22_0` | Moving, indoor | Next development recording; frame IDs and annotations may be inspected for task feasibility. |
| `memorial-court-2019-03-16_0` | Moving, outdoor | **Reserved candidate** for untouched evaluation. Do not inspect its label-derived encounter outcomes or tune on it while building the method. |
| `huang-lane-2019-02-12_0` | Stationary, outdoor | Unassigned. |
| Remaining 23 train recordings | Unverified here | Unassigned pending motion/source verification and recording-group mapping. |

The 27 train recordings occupy 21 parsed location-name prefixes. A prefix is only a preliminary grouping cue: adjacent named sites or repeated sessions can be related, so inspect metadata and images *without model scores* before claiming independent held-out locations. All repeated recordings, all camera views and the same video session must remain in one allocation. The strongest independent final comparison may use JRDB's separate test recordings if compatible accessible test labels and a preregistered custom event protocol are available. If using only the 27 train sequences, reserve several independent location groups, including verified moving groups, and label this a **custom** in-train final holdout, not the official JRDB benchmark test.

After cataloging motion and grouping for all candidate recordings, record and commit a development/validation/final manifest, exact preprocessing, reference rules and primary comparison **before** computing model scores on any final group. Use validation only to select all operating points and conventional baselines; don't choose an easier or more event-rich final set from labels. A sole outdoor moving holdout would confound environment with method generalization and give weak uncertainty; expanding independent final groups is a priority.

Current development order: profile Cubberly for provisional person-free intervals, extract only that verified-moving development recording, inspect a sample of entry/exit/negative windows, verify range/time, then produce *real sensor* predictions for a simple baseline. Keep Memorial Court and other eventual final groups closed until the protocol is frozen. Counts of provisional 3 m occupancy and negative intervals are eligibility diagnostics, **not** scored alerts or a selected final threshold.
