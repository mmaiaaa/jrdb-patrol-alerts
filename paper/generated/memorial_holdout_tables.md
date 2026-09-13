# Memorial Court Frozen Holdout — Paper Tables

## Table 1. Range availability and discrepancy

| Method | Available | Coverage | Median discrepancy (m) | Mean discrepancy (m) | >1 m discrepancies |
|---|---:|---:|---:|---:|---:|
| Depth-band candidate | 12354/13246 | 93.27% | 0.076 | 0.176 | 313 |
| Nearest supported surface | 12992/13246 | 98.08% | 0.090 | 0.931 | 2384 |

## Table 2. Frozen 3 m decisions

| Method | Near→Near | Near→Far | Far→Near | Far→Far | Unavailable/abstain |
|---|---:|---:|---:|---:|---:|
| Depth-band candidate | 820 | 10 | 179 | 11345 | 892 |
| Nearest supported surface | 835 | 7 | 422 | 11728 | 254 |

## Table 3. Paired method comparison

- Paired cases: **12354**
- Depth-band lower discrepancy: **1841**
- Nearest lower discrepancy: **5**
- Equal discrepancy: **10508**
- Depth-band only agrees with reference at 3 m: **225**
- Nearest only agrees with reference at 3 m: **3**
- Total method disagreements at 3 m: **228**

## Table 4. Detector/reference linkage

- detector boxes: **24992**
- matched 2d boxes: **13349**
- unlinked detector boxes: **11643**
- evaluable 2d labels: **18390**
- unmatched evaluable 2d labels: **5041**
- matches without evaluable 3d: **103**
- reference within or equal 3m: **842**
- reference farther than 3m: **12404**

> Important: surface range and annotated 3D center radius are different physical quantities. These discrepancy values must not be described as direct person-distance error.
