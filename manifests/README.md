Manifest conventions

The CSV files contain headers only at M0. There are no selected sequences, completed experiments, or result values. Add actual records as work is performed.

`sequences.csv`: one row per evaluated continuous segment and sensor selection. Record original IDs/timestamps and grouping rather than deriving new sequence names from convenient file order. `manifest_row_id` is a stable project identifier. Specify duration convention and exclusions in the audit record. A selected camera stream does not multiply exposure time.

`runs.csv`: one row per run attempt. Record the input commit and whether the working tree was clean, dataset/config hashes, model hashes, actual hardware record, command, seed when relevant, status, and outputs. Keep large outputs local; their content hashes provide an integrity record, not a substitute for an accessible reproduction recipe.

`event_results.csv`: one row per run, method, and recording group. Keep counts and monitored seconds so rates can be recomputed. Undefined values remain empty with an explanation in the corresponding run record. Do not fill uncomputed metrics with zero. Oracle and sensor runs must be identifiable through the run index.

Commit paths relative to the project or a documented external-data root. Avoid private absolute paths, usernames, signed download URLs, and access tokens.
