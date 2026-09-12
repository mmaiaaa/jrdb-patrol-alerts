Executable utilities and planned interfaces

Available now: `collect_environment.py`, a standard-library hardware/software snapshot utility. Run with Python 3.10+:

```bash
python3 scripts/collect_environment.py
```

It writes `outputs/local/hardware.json` by default and refuses to overwrite an existing report unless `--overwrite` is specified. Choose a different location with `--output PATH`; `--output -` prints JSON. The default report is excluded from Git until a reviewed research environment record is intentionally placed elsewhere.

The following script contracts are planned, not executable commands yet:

| Planned script | Inputs | Outputs |
|---|---|---|
| `audit_jrdb.py` | Explicit dataset root, one sequence, calibration and sensor selection | Alignment/geometry audit and missing-data report |
| `generate_reference_events.py` | Ground-truth tracks and frozen reference policy | Auditable event records with original timestamps |
| `run_perception.py` | Sensor observations and fixed perception configuration | Cached predictions and complete runtime record |
| `run_alerts.py` | Cached sensor predictions and one method configuration | Causal emitted-alert log |
| `evaluate_events.py` | Reference events, alert logs, fixed matching policy | Counts, rates, delays, and error assignments |
| `analyze_results.py` | Run records and per-group counts/exposure | Paired intervals and reproducible figures/tables |

Do not reuse the previous MOT evaluator by changing paths alone. JRDB units, timestamps, reference semantics, causal alert behavior, one-to-one matching, and exposure denominators require deliberate implementation and verification.
