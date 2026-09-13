#!/usr/bin/env python3

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

SOURCE = Path(
    "outputs/local/memorial_court_holdout/"
    "memorial_holdout_reporting.json"
)

OUT = Path("paper/generated")
OUT.mkdir(parents=True, exist_ok=True)

report = json.loads(SOURCE.read_text())

candidate = report["candidate_3m_decisions"]
nearest = report["nearest_3m_decisions"]
paired = report["paired_3m_decision_comparison"]

# ---------------------------------------------------------------------
# Figure 2A:
# Raw 3 m decision-error counts for available estimates.
# ---------------------------------------------------------------------

labels = [
    "Far reference\npredicted near",
    "Near reference\npredicted far",
]

depth_band = [
    candidate["reference_far__predicted_near"],
    candidate["reference_near__predicted_far"],
]

nearest_surface = [
    nearest["reference_far__predicted_near"],
    nearest["reference_near__predicted_far"],
]

x = np.arange(len(labels))
width = 0.36

fig, ax = plt.subplots(figsize=(6.8, 3.5))

bars1 = ax.bar(
    x - width / 2,
    depth_band,
    width,
    label="Depth-band",
)

bars2 = ax.bar(
    x + width / 2,
    nearest_surface,
    width,
    label="Nearest supported surface",
)

ax.set_ylabel("Number of matched reference cases")
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend(frameon=False)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

for bars in (bars1, bars2):
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{int(height)}",
            xy=(
                bar.get_x() + bar.get_width() / 2,
                height,
            ),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
        )

fig.tight_layout()

fig.savefig(
    OUT / "memorial_3m_decision_errors.pdf",
    bbox_inches="tight",
)

fig.savefig(
    OUT / "memorial_3m_decision_errors.png",
    dpi=300,
    bbox_inches="tight",
)

plt.close(fig)


# ---------------------------------------------------------------------
# Figure 2B:
# Direct paired disagreements between the two methods.
#
# This is especially important because both methods are evaluated on
# exactly the same cases here.
# ---------------------------------------------------------------------

categories = [
    "Depth-band only\nagreed",
    "Nearest only\nagreed",
]

values = [
    paired["candidate_only_agrees"],
    paired["nearest_only_agrees"],
]

fig, ax = plt.subplots(figsize=(5.4, 3.5))

bars = ax.bar(
    np.arange(len(categories)),
    values,
    width=0.55,
)

ax.set_ylabel(
    "Cases among method disagreements"
)

ax.set_xticks(
    np.arange(len(categories))
)

ax.set_xticklabels(categories)

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

for bar in bars:
    height = bar.get_height()

    ax.annotate(
        f"{int(height)}",
        xy=(
            bar.get_x() + bar.get_width() / 2,
            height,
        ),
        xytext=(0, 4),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=10,
    )

ax.text(
    0.5,
    0.93,
    "228 total method disagreements",
    transform=ax.transAxes,
    ha="center",
    va="top",
    fontsize=9,
)

fig.tight_layout()

fig.savefig(
    OUT / "memorial_paired_3m_disagreements.pdf",
    bbox_inches="tight",
)

fig.savefig(
    OUT / "memorial_paired_3m_disagreements.png",
    dpi=300,
    bbox_inches="tight",
)

plt.close(fig)

print("Generated:")
for path in (
    OUT / "memorial_3m_decision_errors.pdf",
    OUT / "memorial_3m_decision_errors.png",
    OUT / "memorial_paired_3m_disagreements.pdf",
    OUT / "memorial_paired_3m_disagreements.png",
):
    print(" ", path)

print()
print("Numerical check:")
print(
    "Depth-band far->near:",
    candidate["reference_far__predicted_near"],
)
print(
    "Nearest far->near:",
    nearest["reference_far__predicted_near"],
)
print(
    "Depth-band near->far:",
    candidate["reference_near__predicted_far"],
)
print(
    "Nearest near->far:",
    nearest["reference_near__predicted_far"],
)
print(
    "Depth-band only agrees:",
    paired["candidate_only_agrees"],
)
print(
    "Nearest only agrees:",
    paired["nearest_only_agrees"],
)
