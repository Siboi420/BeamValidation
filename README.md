# RC Beam Designer — ACI 318-14

Python-based open-source framework for reinforced concrete beam design, experimental validation against 50 published beam tests, and SPBeam commercial software benchmarking.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![ACI 318-14](https://img.shields.io/badge/code-ACI%20318--14-orange.svg)](https://www.concrete.org/)

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the interactive web app
streamlit run scripts/app_beam_design.py

# 3. Validate against 50 experimental beams
python3 research/scripts/validate_beam_aci.py

# 4. Generate SPBeam comparison benchmark
python3 research/scripts/rc_beam_comparison.py

# 5. Run parametric study (ρ × f'c)
python3 research/scripts/rc_beam_parametric_study.py

# 6. Generate comparison summary + plots
python3 research/scripts/beam_comparison_summary.py
```

---

## 🛠️ Tools

| Tool | File | Purpose |
|------|------|---------|
| **Core Engine** | `scripts/RCBeam_moment_capacity.py` | Flexure (Ch. 9), shear (Ch. 22), deflection (Ch. 24) per ACI 318-14 |
| **Web App** | `scripts/app_beam_design.py` | Streamlit interface — beam diagrams, RC design, NAC validation viewer |
| **NAC Validation** | `research/scripts/validate_beam_aci.py` | Validates ACI 318-14 predictions against 50 NAC beams (Tošić et al., 2016) |
| **SPBeam Benchmark** | `research/scripts/rc_beam_comparison.py` | 10-case (2 beam types × 5 load steps) benchmark for SPBeam comparison |
| **Parametric Study** | `research/scripts/rc_beam_parametric_study.py` | Sweeps ρ [0.5–2.5%] × f'c [20, 40, 60] MPa — 4 PNG plots |
| **Comparison Summary** | `research/scripts/beam_comparison_summary.py` | Reads comparison CSV, generates statistics tables + scatter/bar plots |

---

## 📊 Key Results

### Experimental Validation — 50 NAC Beams

| Failure Mode | Code | n | Mean c | CoV (%) | Interpretation |
|-------------|------|---|--------|---------|----------------|
| Flexure | ACI 318-14 (nominal) | 18 | 1.109 | 5.85 | Slightly conservative |
| Flexure | EC2 (from paper) | 18 | 1.064 | 8.46 | Accurate |
| Shear — no stirrups | ACI 318-14 | 24 | 1.368 | 26.07 | Very conservative |
| Shear — with stirrups | ACI 318-14 | 8 | 1.089 | 21.53 | Accurate |

### SPBeam Comparison — 10-Case Benchmark

| Metric | Type-A Mean | Type-C Mean | Overall Verdict |
|--------|------------|------------|-----------------|
| **φM_n** | 1.003 (0.3% diff) | 1.008 (0.8% diff) | ✅ Excellent |
| **A_s** | 1.000 (0.0%) | 0.998 (0.2%) | ✅ Perfect |
| **φV_n @ d** | 1.008 (0.8%) | 0.950 (5.0%) | ✅ Good / ⚠️ Fair |
| **Stirrup s** | 1.051 (5.1%) | 1.104 (10.4%) | ✅ Good / ⚠️ Fair |

Detailed V_c equation (ACI Eq. 22.5.5.1) used for both Python and SPBeam to ensure methodological consistency.

---

## 📄 Research Paper

A comprehensive research paper is available at:

**[research/docs/research_paper_comprehensive.md](research/docs/research_paper_comprehensive.md)**

The paper covers:
- Framework architecture and ACI 318-14 methodology
- Experimental validation against 50 NAC beams
- SPBeam commercial software benchmark
- Parametric study (6 ρ values × 3 f'c values)
- 13 embedded figures (scatter plots, bar charts, comparison plots)

---

## 📂 Project Structure

```
├── scripts/                           # Core application code
│   ├── RCBeam_moment_capacity.py      # Design engine (single source of truth)
│   ├── app_beam_design.py             # Streamlit web application
│   └── beam_diagram_calculator.py     # Shear/moment diagram calculator
│
├── research/
│   ├── data/nac_study/                # NAC experimental database (Tošić et al., 2016)
│   │   ├── NAC_flexure_data.csv       #   18 flexural beams
│   │   ├── NAC_shear_no_stirrups.csv  #   24 shear beams (no stirrups)
│   │   ├── NAC_shear_with_stirrups.csv#    8 shear beams (with stirrups)
│   │   └── NAC_statistical_summary.csv#   Statistical summaries
│   │
│   ├── scripts/                       # Research & validation tools
│   │   ├── validate_beam_aci.py       #   NAC ACI 318-14 validation
│   │   ├── rc_beam_comparison.py      #   SPBeam benchmark generator
│   │   ├── rc_beam_parametric_study.py#   Parametric study
│   │   └── beam_comparison_summary.py #   SPBeam vs Python comparison
│   │
│   ├── output/                        # Generated results
│   │   ├── nac_validation/            #   Validation outputs (CSV, TXT, PNG)
│   │   ├── beam_comparison/           #   SPBeam benchmark (CSV, JSON, plots)
│   │   └── parametric_study/          #   Parametric study plots
│   │
│   └── docs/                          # Documentation & papers
│       └── research_paper_comprehensive.md
│
├── requirements.txt                   # Python dependencies
├── LICENSE                            # MIT License
└── README.md                          # This file
```

---

## 🔬 Design Engine Features

- **Dual operational modes:** Design mode (calculate required steel from M_u) and capacity-check mode (compute φM_n from provided steel)
- **Detailed V_c equation:** Matches SPBeam methodology for shear comparison
- **Critical section analysis:** Shear and moment computed at distance d from support per ACI §22.5
- **Strain compatibility:** Handles singly reinforced, doubly reinforced, and compression steel yielding/non-yielding cases
- **Layering detection:** Automatically detects bar overcrowding and redistributes into 2 layers
- **Equation output:** Step-by-step calculation trace with ACI section references

---

## 📜 License

MIT — free for personal, academic, and commercial use.

---

## 📚 Reference

Tošić, N., Marinković, S., & Ignjatović, I. (2016). "Efficiency of shear and flexural reinforcement in recycled aggregate concrete beams." *Construction and Building Materials*, 127, 932–944.