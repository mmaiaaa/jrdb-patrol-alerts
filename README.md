JRDB Patrol Alerts

Status: **M0 — research foundation prepared; no JRDB experiments have been run in this project.**

This project investigates whether a causal encounter manager can reduce false and duplicate person-proximity alerts for a mobile patrol robot while preserving timely event recall. JRDB is the primary proposed dataset. Detection and tracking are components; the research outcome is the quality of the alerts delivered to an operator.

The working scope is robot-relative proximity monitoring. Fixed-site intrusion detection requires localization, a defined restricted region, and independently specified security-event labels. Neither proximity nor an ordinary human action establishes hostile intent.

**Start here.**

1. Read [the study protocol](docs/protocol.md) and [open decisions](docs/decisions.md).
2. Collect hardware information with `python3 scripts/collect_environment.py`.
3. Choose one JRDB development sequence and record its provenance in [the data manifest](manifests/sequences.csv).
4. Complete the geometry and reference-event pilot before expanding the dataset.
5. Record each experiment, including failures, and update the paper in the same milestone.

The working manuscript is [paper/manuscript.md](paper/manuscript.md). It contains drafted motivation and planned methods; empirical results remain explicitly pending.

**Project contents.**

| Location | Purpose |
|---|---|
| `docs/protocol.md` | Hypotheses, task semantics, comparisons, statistics, and freeze requirements |
| `docs/milestones.md` | Completion criteria and corresponding manuscript updates |
| `docs/decisions.md` | Accepted decisions, unresolved choices, and changes after freeze |
| `docs/experiment_log.md` | Human-readable research record |
| `docs/rubric.md` | Evidence needed under the seven review criteria |
| `docs/github_workflow.md` | First push and milestone-by-milestone Git workflow |
| `configs/` | Draft task and method configuration; not a frozen protocol |
| `manifests/` | Sequence membership, experiment provenance, and result headers |
| `scripts/` | Executable utilities and planned script contracts |
| `src/patrol_alerts/` | Package reserved for the upcoming implementation |
| `paper/` | Versioned manuscript, references, and literature notes |
| `data/` | Local-only dataset storage; raw data is excluded from Git |
| `outputs/` | Local predictions/caches; selected small tables and figures may be versioned |

**What works now.**

The environment collector runs with Python 3.10+ and only the standard library. It records selected CPU, memory, GPU, disk, Python, and OS information without collecting usernames, network addresses, tokens, or a complete environment-variable dump. Its report is local by default:

```bash
python3 scripts/collect_environment.py
```

There is no detector runner, JRDB adapter, range estimator, alert implementation, or event evaluator yet. Their contracts and milestone order are documented; this repository must not be presented as a completed system.

**Research record.**

Use a distinct run ID for every configuration or dataset change. Record the input code commit, clean/dirty working-tree state, data manifest, sensor selection, model hashes, configuration hash, seeds where applicable, failures, and completed metrics. Commit the resulting small tables and manuscript update in a later results commit. Do not overwrite a failed run with a successful rerun under the same identifier.

Cache perception outputs when only alert parameters change. Do not count replicated frames, camera views, or simulated corruptions as independent recording sessions. Methods must consume only observations available at the time an alert is issued.

**Data and publication.**

Obtain JRDB through its [official access process](https://jrdb.erc.monash.edu/). Keep the exact release and selected streams consistent. This repository contains no JRDB media, labels, credentials, pretrained weights, or results from the previous MOT study. Dataset redistribution terms and software/manuscript licensing must be resolved before public release; no open-source license is selected yet.

Prefer a private GitHub repository while the study is developing, with a publication release after the artifact and data-sharing choices are ready. The local project name is `jrdb-patrol-alerts`; the remote owner and URL are not yet configured.
