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

labels = [
    "Far ref.\n→ near",
    "Near ref.\n→ far",
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
width = 0.34

# Sized for approximately one conference-paper column.
fig, ax = plt.subplots(figsize=(3.45, 2.55))

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
    label="Nearest",
)

ax.set_ylabel("Cases", fontsize=9)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=8)

ax.tick_params(
    axis="y",
    labelsize=8,
)

ax.legend(
    frameon=False,
    fontsize=8,
    loc="upper right",
)

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
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )

ax.set_ylim(
    0,
    max(nearest_surface) * 1.14,
)

fig.tight_layout(pad=0.5)

fig.savefig(
    OUT / "memorial_3m_decision_errors_paper.pdf",
    bbox_inches="tight",
)

fig.savefig(
    OUT / "memorial_3m_decision_errors_paper.png",
    dpi=600,
    bbox_inches="tight",
)

plt.close(fig)

print(
    "Generated:",
    OUT / "memorial_3m_decision_errors_paper.pdf",
)
print(
    "Generated:",
    OUT / "memorial_3m_decision_errors_paper.png",
)

print()
print("Values:")
print("Depth-band far->near:", depth_band[0])
print("Nearest far->near:", nearest_surface[0])
print("Depth-band near->far:", depth_band[1])
print("Nearest near->far:", nearest_surface[1])
