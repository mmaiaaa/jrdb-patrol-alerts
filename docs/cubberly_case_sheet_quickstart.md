# Inspect the 66 blinded Cubberly development cases

The packet already contains `reviewer_a.csv` and, if a second independent
reviewer is available, `reviewer_b.csv`. Neither reviewer needs to open
`review_key.csv`, any JRDB label JSON, or a threshold audit during review.

From the repository root (with the JRDB Python environment active), render
one focused four-panel image per case:

```bash
python3 scripts/render_jrdb_blinded_review_cases.py \
  > outputs/local/cubberly_blinded_review/case_sheets_summary.json
python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('outputs/local/cubberly_blinded_review/case_sheets_summary.json').read_text())
print('Case sheets:', data['cases'])
print('Folder:', Path(data['sheets'][0]['sheet']).parent)
PY
```

The top-left panel marks the one detector rectangle to assess; the top-right
shows measured upper+lower LiDAR points projected **inside that box's inner
ROI**. Other returns appear grey; green points are the algorithm's selected
band, when one exists. The bottom panels show the same native camera two
frame IDs before and after, without annotations. A case with no green points
represents a sensor-side abstention, which is a legitimate outcome. The
script validates each selected box against the existing sensor-only CSV and
replays its selection from the recorded point cloud. It refuses to overwrite
existing sheets; keep all outputs under ignored `outputs/local/`.

Follow the field definitions in `docs/cubberly_blinded_review_protocol.md`.
Use `yes`, `no`, or `uncertain` for the four visual judgments. In particular,
`foreground_surface_clear=yes` requires convincing visual evidence that the
green points belong to the marked human, not merely overlap the 2D box.
Neither a green mark nor a nominal range proves identity or synchronization.
For partial edge cases, obscured persons, or questionable projection,
`uncertain` with a specific note is more informative than a guess. Report
how many cases could not be resolved. A second reviewer should fill sheet B
without seeing sheet A.

Do not calculate an accuracy percentage from these 66 deliberately enriched
cases. Keep the review results distinct from the held-out Memorial Court
sensor-only preflight; no Memorial reference labels have been inspected.
