Milestones and corresponding paper updates

Each milestone ends with a checked local commit and, once GitHub is connected, a push. Preserve partial or failed work as such; do not describe it as a completed experiment.

| Milestone | Completion evidence | Paper update | Intended commit scope |
|---|---|---|---|
| M0 Foundation | Repository, research question, draft protocol, records, working manuscript | Motivation and proposed study | Research foundation; manuscript draft |
| M1 Environment and acquisition | Actual hardware report, tested dependency lock, one development sequence manifest | Hardware and selected data | Record pilot environment and dataset provenance |
| M2 Geometry and references | Projection/timestamp audit, agreed event policy, independent reference labels, edge cases | Task definition and annotation procedure | Implement adapter and audited reference events |
| M3 Sensor baseline | Real predictions and range-quality results on development data | Implemented pipeline and baseline | Add first sensor baseline with reproducible run |
| M4 Alert methods | Strong temporal baselines, candidate method, causal tests, development diagnostics | Method specification and ablation plan | Implement alert methods and validate semantics |
| M5 Protocol freeze | Complete manifests, configurations, matcher, comparator, operating point, statistical plan | Final experimental design | Freeze protocol before final-test evaluation |
| M6 Held-out evaluation | Unmodified test run, grouped confidence intervals, failures, runtime | Results and evidence-based discussion | Add final-test results and regenerated tables |
| M7 Patrol transfer | Independent sessions, annotation audit, compatible sensors, frozen transfer/adaptation protocol | External validity and deployment limits | Add independent patrol validation |
| M8 Submission artifact | Fresh-environment reproduction, claim audit, complete literature, release review | Abstract, conclusion, submission formatting | Prepare reproducible manuscript release |

M0 creates no evidence that the method improves performance. M2 is the first feasibility decision: do not expand downloads if metric reference events are untrustworthy. M3 determines whether localization/perception can support the task. M4 determines whether conventional baselines already solve it. M6 may disconfirm the hypothesis; report that outcome rather than redefining the task on the test set.

Commit completed logical changes rather than every keystroke. An experiment's record should identify the code commit that was run; its resulting tables and manuscript changes belong in a subsequent commit. This avoids circular provenance where the recorded input commit contains outputs that did not yet exist.

Repository publication and journal submission are distinct milestones. A public artifact does not establish novelty or adequate scientific evidence.
