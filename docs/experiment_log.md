Research and experiment log

2026-09-12 — M0 research foundation

Prepared the repository structure, draft event protocol, configuration proposals, empty data/run manifests, review-criterion map, manuscript workflow, and a standard-library hardware collector. Drafted the initial manuscript separately as the next logical commit.

No JRDB sequence was downloaded or selected. No inference, localization, event extraction, performance measurement, statistical analysis, or physical-robot experiment was performed. No result is carried over from MOT. Local commits use a clearly identified Codex scaffolding author; researcher authorship details are not invented.

GitHub upload is pending an authenticated connection. Local commit history is the initial provenance record and can be pushed unchanged.

M0 manuscript increment: drafted motivation, initial source-grounded positioning, proposed task/method/evaluation prose, result placeholders, and an evidence ledger. The input foundation commit is `4fff48f`. The environment utility and JSON/CSV syntax were checked in the workspace; these are scaffold checks, not measurements of the user's laptop or scientific pipeline validation.

Use this entry shape for every actual experiment:

```text
Run ID:
Date/time and operator:
Question / hypothesis:
Code input commit and clean working tree:
Dataset release and sequence-manifest hash:
Split / recording groups / selected sensor streams:
Configuration and model hashes:
Environment record / dependency lock:
Seed(s), if applicable:
Exact command:
Expected outcome or comparison:
Observed outcome, counts, exposure, and errors:
Output paths and checksums:
Interpretation and remaining uncertainty:
Paper claim/table/figure affected:
Follow-up decision:
```

Use `manifests/runs.csv` for the machine-readable index. Do not give simulated/oracle analyses the same provenance label as sensor experiments. Record failed runs rather than silently discarding them.
