#!/usr/bin/env python3

import csv
import json
from pathlib import Path

ROOT = Path("outputs/local/memorial_court_holdout")

EVAL_JSON = ROOT / "memorial_holdout_evaluation_summary.json"
REPORT_JSON = ROOT / "memorial_holdout_reporting.json"

OUT_DIR = Path("paper/generated")
OUT_DIR.mkdir(parents=True, exist_ok=True)

eval_summary = json.loads(EVAL_JSON.read_text())
report = json.loads(REPORT_JSON.read_text())

# ---------------------------------------------------------------------
# Validate that we are using exactly the frozen Memorial Court result.
# ---------------------------------------------------------------------

assert eval_summary["sequence"] == "memorial-court-2019-03-16_0"
assert eval_summary["role"] == "frozen_holdout_scoring"
assert eval_summary["matching_2d_iou_threshold"] == 0.5

assert report["sequence"] == "memorial-court-2019-03-16_0"
assert report["threshold_m"] == 3.0

n = report["matched_evaluable_3d_pairs"]

candidate = report["candidate_3m_decisions"]
nearest = report["nearest_3m_decisions"]
paired = report["paired_range_discrepancy"]
paired_decisions = report["paired_3m_decision_comparison"]
linkage = report["detector_linkage"]
coverage = report["coverage"]
reference = report["reference_distribution"]

# ---------------------------------------------------------------------
# Table 1: coverage and continuous discrepancy
# ---------------------------------------------------------------------

all_eval = eval_summary["all_matched_evaluable_3d"]

table1 = [
    {
        "method": "Depth-band candidate",
        "matched_reference_pairs": n,
        "available_estimates": coverage["candidate_available"],
        "unavailable_or_abstain":
            coverage["candidate_abstain_or_unavailable"],
        "coverage_percent":
            100.0 * coverage["candidate_available"] / n,
        "median_abs_center_discrepancy_m":
            all_eval["candidate_surface"][
                "median_absolute_center_discrepancy_m"
            ],
        "mean_abs_center_discrepancy_m":
            all_eval["candidate_surface"][
                "mean_absolute_center_discrepancy_m"
            ],
        "absolute_discrepancies_over_1m":
            all_eval["candidate_surface"][
                "absolute_discrepancies_over_1m"
            ],
    },
    {
        "method": "Nearest supported surface",
        "matched_reference_pairs": n,
        "available_estimates": coverage["nearest_available"],
        "unavailable_or_abstain":
            coverage["nearest_unavailable"],
        "coverage_percent":
            100.0 * coverage["nearest_available"] / n,
        "median_abs_center_discrepancy_m":
            all_eval["nearest_supported_surface"][
                "median_absolute_center_discrepancy_m"
            ],
        "mean_abs_center_discrepancy_m":
            all_eval["nearest_supported_surface"][
                "mean_absolute_center_discrepancy_m"
            ],
        "absolute_discrepancies_over_1m":
            all_eval["nearest_supported_surface"][
                "absolute_discrepancies_over_1m"
            ],
    },
]

# ---------------------------------------------------------------------
# Table 2: frozen 3 m decision table
# ---------------------------------------------------------------------

table2 = [
    {
        "method": "Depth-band candidate",
        "reference_near_predicted_near":
            candidate.get("reference_near__predicted_near", 0),
        "reference_near_predicted_far":
            candidate.get("reference_near__predicted_far", 0),
        "reference_far_predicted_near":
            candidate.get("reference_far__predicted_near", 0),
        "reference_far_predicted_far":
            candidate.get("reference_far__predicted_far", 0),
        "abstain_or_unavailable":
            candidate.get("abstain_or_unavailable", 0),
        "available":
            candidate["available"],
    },
    {
        "method": "Nearest supported surface",
        "reference_near_predicted_near":
            nearest.get("reference_near__predicted_near", 0),
        "reference_near_predicted_far":
            nearest.get("reference_near__predicted_far", 0),
        "reference_far_predicted_near":
            nearest.get("reference_far__predicted_near", 0),
        "reference_far_predicted_far":
            nearest.get("reference_far__predicted_far", 0),
        "abstain_or_unavailable":
            nearest.get("abstain_or_unavailable", 0),
        "available":
            nearest["available"],
    },
]

# ---------------------------------------------------------------------
# Table 3: paired comparison
# ---------------------------------------------------------------------

table3 = [
    {
        "paired_cases": paired["pairs"],
        "depth_band_lower_discrepancy":
            paired["candidate_lower_discrepancy"],
        "nearest_lower_discrepancy":
            paired["nearest_lower_discrepancy"],
        "equal_discrepancy":
            paired["equal_discrepancy"],
        "depth_band_only_agrees_at_3m":
            paired_decisions["candidate_only_agrees"],
        "nearest_only_agrees_at_3m":
            paired_decisions["nearest_only_agrees"],
        "both_agree_at_3m":
            paired_decisions["both_agree_with_reference"],
        "neither_agrees_at_3m":
            paired_decisions["neither_agrees"],
        "method_3m_disagreements":
            paired_decisions["candidate_far__nearest_near"],
    }
]

# ---------------------------------------------------------------------
# Table 4: detector/reference linkage
# ---------------------------------------------------------------------

table4 = [
    {
        "detector_boxes": linkage["detector_boxes"],
        "matched_2d_boxes": linkage["matched_2d_boxes"],
        "unlinked_detector_boxes": linkage["unlinked_detector_boxes"],
        "evaluable_2d_labels": linkage["evaluable_2d_labels"],
        "unmatched_evaluable_2d_labels":
            linkage["unmatched_evaluable_2d_labels"],
        "matches_without_evaluable_3d":
            linkage["matches_without_evaluable_3d"],
        "reference_within_or_equal_3m":
            reference["near_or_equal_3m"],
        "reference_farther_than_3m":
            reference["farther_than_3m"],
    }
]


def write_csv(path, rows):
    fields = list(rows[0].keys())

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


write_csv(
    OUT_DIR / "memorial_table1_range_comparison.csv",
    table1,
)

write_csv(
    OUT_DIR / "memorial_table2_3m_decisions.csv",
    table2,
)

write_csv(
    OUT_DIR / "memorial_table3_paired_comparison.csv",
    table3,
)

write_csv(
    OUT_DIR / "memorial_table4_linkage.csv",
    table4,
)


# ---------------------------------------------------------------------
# Human-readable Markdown version
# ---------------------------------------------------------------------

md = []

md.append("# Memorial Court Frozen Holdout — Paper Tables\n")

md.append("## Table 1. Range availability and discrepancy\n")
md.append(
    "| Method | Available | Coverage | Median discrepancy (m) | "
    "Mean discrepancy (m) | >1 m discrepancies |"
)
md.append("|---|---:|---:|---:|---:|---:|")

for r in table1:
    md.append(
        f"| {r['method']} "
        f"| {r['available_estimates']}/{r['matched_reference_pairs']} "
        f"| {r['coverage_percent']:.2f}% "
        f"| {r['median_abs_center_discrepancy_m']:.3f} "
        f"| {r['mean_abs_center_discrepancy_m']:.3f} "
        f"| {r['absolute_discrepancies_over_1m']} |"
    )

md.append("\n## Table 2. Frozen 3 m decisions\n")
md.append(
    "| Method | Near→Near | Near→Far | Far→Near | Far→Far | "
    "Unavailable/abstain |"
)
md.append("|---|---:|---:|---:|---:|---:|")

for r in table2:
    md.append(
        f"| {r['method']} "
        f"| {r['reference_near_predicted_near']} "
        f"| {r['reference_near_predicted_far']} "
        f"| {r['reference_far_predicted_near']} "
        f"| {r['reference_far_predicted_far']} "
        f"| {r['abstain_or_unavailable']} |"
    )

md.append("\n## Table 3. Paired method comparison\n")
r = table3[0]

md.append(f"- Paired cases: **{r['paired_cases']}**")
md.append(
    f"- Depth-band lower discrepancy: "
    f"**{r['depth_band_lower_discrepancy']}**"
)
md.append(
    f"- Nearest lower discrepancy: "
    f"**{r['nearest_lower_discrepancy']}**"
)
md.append(
    f"- Equal discrepancy: "
    f"**{r['equal_discrepancy']}**"
)
md.append(
    f"- Depth-band only agrees with reference at 3 m: "
    f"**{r['depth_band_only_agrees_at_3m']}**"
)
md.append(
    f"- Nearest only agrees with reference at 3 m: "
    f"**{r['nearest_only_agrees_at_3m']}**"
)
md.append(
    f"- Total method disagreements at 3 m: "
    f"**{r['method_3m_disagreements']}**"
)

md.append("\n## Table 4. Detector/reference linkage\n")
r = table4[0]

for key, value in r.items():
    md.append(
        f"- {key.replace('_', ' ')}: **{value}**"
    )

md.append(
    "\n> Important: surface range and annotated 3D center radius are "
    "different physical quantities. These discrepancy values must not "
    "be described as direct person-distance error."
)

(OUT_DIR / "memorial_holdout_tables.md").write_text(
    "\n".join(md) + "\n",
    encoding="utf-8",
)

print("Generated:")
for p in sorted(OUT_DIR.glob("memorial_*")):
    print(" ", p)

print()
print(
    (OUT_DIR / "memorial_holdout_tables.md").read_text()
)
