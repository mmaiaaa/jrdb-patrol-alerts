Person-Proximity Alert Reliability for Mobile Patrol Robots: An Event-Level Study on JRDB

**Working manuscript — M0, 12 September 2026.** This is a research draft with an implemented repository foundation and an unimplemented study. No JRDB results, improvement percentages, statistical significance, or deployment claims are available. Author names, affiliations, target journal, and submission format remain to be supplied. The title describes the intended subject and may change with the evidence.

**Abstract — provisional study description.**

Mobile patrol robots require alert decisions that remain useful when person observations are noisy, occluded, or fragmented across tracking identities. Standard detection and tracking metrics do not directly quantify the number of false or repeated notifications delivered to an operator. This study will investigate person-proximity alert reliability using robot-view observations from JRDB. We plan to define qualifying encounters from independently specified metric occupancy rules and compare conventional temporal alert policies with a causal encounter manager that maintains continuity across interrupted observations. The evaluation will report event recall, false alerts per monitored hour, response delay, and uncertainty in paired comparisons across independent recording groups. Ablation experiments will test whether encounter memory and calibrated position uncertainty provide benefits beyond simpler policies. Independent patrol recordings are proposed to assess transfer to a restricted-area monitoring task. **Results and evidence-based conclusions will be added only after the frozen evaluation is completed.**

**1. Introduction.**

A patrol robot's perception system must support decisions at the level of operational events. Detecting a person in successive images is an intermediate measurement; an operator may instead need one prompt notification that a relevant encounter has begun. The identity assigned to that person by a tracker can change during occlusion, and position estimates can fluctuate near a monitoring boundary. An alert policy tied directly to those outputs may therefore produce repeated notifications or fail to preserve an ongoing encounter. Conversely, suppressing alerts too aggressively can conceal the arrival of a different person.

These failure mechanisms motivate an evaluation of the complete observation-to-alert process. A method that improves tracking accuracy may not improve alert reliability if its remaining identity breaks occur at critical event boundaries. A method that reduces the number of notifications may also increase missed encounters or response delay. The proposed study will measure these outcomes together and will avoid interpreting fewer notifications as an improvement without corresponding evidence about recall and timing.

JRDB provides an appropriate setting for the perception component because it contains observations acquired from a mobile robot in indoor and outdoor human environments, with camera and LiDAR information and person annotations. Its original benchmark addresses detection and tracking from the robot's perspective. [JRDB paper](https://arxiv.org/abs/1910.11792)

The proposed primary task is robot-relative proximity monitoring. This task should be distinguished from recognizing an unauthorized intrusion: a person being near a robot does not establish a violation of an access policy. A moving robot can also create a close encounter by passing a stationary person. We will use explicit geometric and temporal rules to define reference encounters, and will describe their derivation rather than presenting them as native security labels.

The central research question is whether maintaining encounter continuity, while accounting for uncertain observations, improves the trade-off between false alerts, missed encounters, and response delay compared with well-tuned conventional temporal policies. The candidate contributions are an auditable event-level protocol, a precisely specified causal alert manager, and an empirical analysis of where its mechanisms help or fail. These are research objectives; novelty and effectiveness have not been established at this stage.

**2. Related work — initial positioning.**

Robot-based guard-patrol perception is an established research area. Prykhodchenko and colleagues describe a system combining complementary people detectors and adapting computation to the observed situation, with evaluation in a real facility. This work means that using a robot to detect people or combining sensors is not itself a sufficient novelty claim. Our intended emphasis is the continuity and operational evaluation of the emitted alerts. A full comparison of assumptions, implementation, and event outcomes remains necessary. [Guard-patrol perception study](https://home.deec.uc.pt/~rprocha/publications_ficheiros/PRC20-ICARSC20.html)

JRDB establishes a benchmark for robot-perspective human perception. Its use can improve the match between this study's data and its robotics setting, but changing a dataset does not establish an original method. [JRDB benchmark](https://jrdb.erc.monash.edu/)

JRDB-Traj extends this line of work toward end-to-end trajectory forecasting with imperfect preceding perception modules. It is relevant to the distinction between a task evaluated with perfect trajectories and one evaluated using sensor-derived predictions. Forecasting is outside the proposed primary proximity-alert task, and would require separate methodological and baseline treatment if added later. [JRDB-Traj](https://arxiv.org/abs/2311.02736)

The literature search must be extended to the closest alert-suppression, event-evaluation, multisensor localization, and occlusion/re-identification methods. Conventional persistence, hysteresis, and cooldown are baseline mechanisms, not claimed inventions. The current sources support initial positioning and do not constitute an exhaustive novelty review. See `related_work.csv` for the reading status of each starting source.

**3. Task definition and reference events — proposed.**

Let p_i(t) denote the annotated horizontal center of person i in a verified robot coordinate frame at timestamp t. A proximity observation satisfies ||p_i(t)|| ≤ r. A qualifying encounter additionally satisfies a fixed minimum occupancy duration. The planning examples r = 3.0 m and duration = 0.5 s are provisional, not final requirements or standards. They will be justified and frozen before final method comparison.

Reference events will be generated from labelled tracks using a dedicated policy independent of method-specific confirmation, cooldown, or uncertainty settings. Each record will contain the reference identity, original timestamps, physical-entry time when observed, fixed eligibility time, and event end. Rules will explicitly cover initial occupancy, field-of-view entry, brief annotation gaps, unknown intervals, re-entry, and incomplete endings. The reference policy will be inspected visually before performance results are used to select a method.

Offline reference generation may use subsequent labelled observations to determine whether a minimum-duration condition is satisfied. An online alert at time t may use only observations available by t. This distinction is essential: merging complete event trajectories after a recording has ended cannot undo an alert already received by an operator.

For a single-camera pilot, the eligible spatial region and annotation coverage will be fixed consistently across methods. Events will not be removed merely because a prediction has no associated detection or valid range. Camera or LiDAR coordinate axes will be transformed explicitly before applying horizontal distance, and original sensor timestamps will determine durations.

**4. Perception and alert methods — proposed.**

The pilot will use one reproducible pretrained person detector and tracker, together with a calibrated sensor-based localization procedure. The exact model, weights, streams, association method, and dependency versions remain open. Detector and tracker outputs will be cached so that alert-method comparisons operate on identical inputs.

A candidate localization route projects LiDAR into predicted person boxes and applies a documented foreground association procedure. Background surfaces, sparse points, and overlapping people can invalidate a naive range estimate, so the pilot must quantify localization error and missing estimates, particularly near the event boundary. Missing measurements will remain explicit rather than being replaced with annotated locations. Any experiment supplying annotated positions or identities to a prediction component will be labelled as oracle analysis.

The proposed alert manager will maintain encounter identity separately from the tracker ID. Its conceptual states are outside, candidate, active, and uncertain. Confirmation creates an active encounter and emits one alert; temporary missing observations retain bounded memory. Reassociation will use predefined time, geometry, and uncertainty gates and a one-to-one assignment. The system must not silently collapse two simultaneously present people into one encounter. Confirmed exit and a declared re-entry rule permit a later alert.

If position uncertainty is used, it will be estimated and calibrated on development observations. Object-detection confidence will not be treated as a calibrated probability of occupying the monitoring region. Ego-motion will be handled with independently obtained motion information where possible, or the limitations of a bounded local continuity model will be stated. Consecutive robot-relative positions will not be described as world-frame person velocity without the appropriate transformation.

Comparisons will include raw entry thresholding, time persistence, hysteresis with per-ID cooldown, and a tuned causal spatial/temporal memory baseline. The candidate uncertainty-aware method will be assessed against the strongest validation-selected conventional comparator. Ablations will remove uncertainty handling, encounter memory, and hysteresis separately. An alternative tracker will be a secondary robustness check after the primary alert experiment works.

**5. Experimental design — proposed.**

Acquisition checkpoint (12 September 2026; development pilot): The JRDB 2022 train archives yielded sequence `bytes-cafe-2019-02-07_0` with 1726 native `image_0` frames, 1726 upper and 1726 lower LiDAR frames, one 3D-label JSON, and three calibration YAML files. The workstation uses an RTX 2060 with 6 GB VRAM; CUDA matrix multiplication and torchvision GPU NMS passed on PyTorch 2.13.0. Timestamp, 3D projection, detector accuracy, and inference-speed validation remain pending.

The exact JRDB release, selected sequences, independent recording groups, and sensor streams will be published in the manifest. Development data will support implementation and uncertainty fitting; validation data will select operating points; an untouched final test will support the primary empirical claim. The official release split will be distinguished from any custom location/session holdout. Different sequence names will not be assumed to establish location independence.

All compared alert methods will receive the same sensor predictions, reference events, eligibility rules, and evaluation implementation. Simpler baselines will receive a meaningful tuning budget. Configurations will be selected to reduce false alerts per monitored hour subject to justified recall and delay requirements, with infeasible methods reported as such. The numerical requirements, primary comparison, matching gates, and statistical analysis will be frozen before final-test inspection.

Alerts and reference events will be matched one to one under fixed compatibility gates, maximizing valid match cardinality before deterministic cost. A second notification for an already matched encounter will be counted as an extra alert. Suppression of a distinct person will generate a missed reference event. The evaluator will distinguish duplicate alerts from other localization, detection, or timing errors.

Primary reporting will include reference-event count, monitored time, true and false alerts, event recall, timely-detection rate, and response delay. Signed delay will be measured from physical entry and fixed eligibility time, with misses reported alongside delay among matches. Precision and F1 will be secondary summaries. Camera views will not multiply recording exposure. Negative recordings will remain in false-alert-rate calculations even when their sequence-level recall is undefined.

Paired confidence intervals will be computed by resampling independent recording groups, using the same sampled groups for every method and recomputing counts and exposure in each replicate. Per-group results will accompany pooled estimates. The adequacy of recording groups, events, and negative exposure remains to be assessed; a large frame count does not alone establish statistical precision.

Runtime measurements will include all selected views, localization, tracking, alert logic, and the declared I/O and queue policy. We will distinguish cached alert-method computation from complete sensor-to-alert delay. Workstation throughput will not be used as evidence of onboard performance without measurement on the relevant platform.

**6. Results — not yet available.**

No entry in the table below is a measurement. Replace pending cells with values generated from documented runs only after the protocol and pipeline are implemented.

| Method | Test groups / monitored time | Event recall | False alerts/hour | Timely recall | Delay / uncertainty |
|---|---|---|---|---|---|
| Raw threshold | Pending | Pending | Pending | Pending | Pending |
| Time persistence | Pending | Pending | Pending | Pending | Pending |
| Hysteresis and per-ID cooldown | Pending | Pending | Pending | Pending | Pending |
| Causal spatial/temporal memory | Pending | Pending | Pending | Pending | Pending |
| Candidate uncertainty-aware method | Pending | Pending | Pending | Pending | Pending |

Planned supporting analyses include ablations, localization/uncertainty quality, errors by occlusion and robot movement, distinct-person suppression, runtime, and representative failures. Effect sizes, confidence intervals, and the operational trade-offs must be reported even when the result is null or unfavorable.

**7. Discussion and limitations — questions for the measured study.**

The discussion should determine whether any reduction in false alerts survives common recall and timing requirements, whether the gain is explained by simple temporal logic, and which observations cause missed encounters or false merges. It should separate evidence from real sensor inputs, perfect-track diagnostics, and simulated corruption experiments.

Robot-relative proximity is a monitoring proxy, not an independently established security violation. Stronger intrusion claims require a mapped restricted area, compatible localization/sensors, an access/event policy, and independently annotated patrol recordings. A camera-cart recording or offline replay is useful but differs from a deployed autonomous patrol robot. These distinctions must remain visible in the final claims.

The final discussion must state actual recording duration and independent-group coverage. Short recording exposure cannot establish low false-alert frequency over days. If independent patrol validation cannot be collected, the paper's external-validity claim must remain limited accordingly.

**8. Conclusion — intentionally pending.**

Write the conclusion after the empirical questions above are answered. It should state what was measured, the magnitude and uncertainty of the principal effect, its recall/delay costs, and the settings in which the result applies. It must not promise effectiveness, novelty, reliability, or real-time deployment on the basis of this plan.

**Evidence ledger.**

| Claim or manuscript element | Current evidence | Required next evidence |
|---|---|---|
| JRDB is a robot-perspective human-perception dataset | Official dataset/paper sources linked above | Exact downloaded release and manifest |
| Patrol people detection is established prior work | Author publication page inspected | Full reading of closest methods |
| Proposed alert method reduces false alerts | None | Frozen held-out comparison and intervals |
| Recall and delay remain operationally acceptable | None | Justified requirements and measured feasibility |
| Uncertainty or memory causes a benefit | None | Fair ablations and calibrated estimates |
| The method transfers to actual patrol security | None | Independent compatible-sensor patrol evaluation |
| Complete pipeline runs in real time onboard | None | End-to-end measurements on intended hardware |

Bibliographic starting entries are in `references.bib`. Author metadata, target-journal style, complete related work, and measured study details remain unfinished.

### Pilot annotation audit (preliminary)

In the stationary indoor bytes-cafe-2019-02-07_0 sequence, 1,726 frame identifiers align across camera 0, both LiDAR streams, and the 3D annotation file. The file contains 39,567 pedestrian-frame observations from 37 pedestrian IDs. Exploratory 3D box-center distance calculations identify 14,518 observations within 3 m, all marked no_eval=false and with a positive LiDAR point count. These are repeated frame observations, not independently labeled proximity encounters. The interpolated attribute is true for 39,550 of 39,567 observations; its distribution in this JRDB 2022 file requires investigation before establishing the reference-event protocol. Camera-0 visibility, coordinate transforms, and recording time remain to be validated. No detector or alert performance is claimed from this audit.
