#!/usr/bin/env python3
"""
Generate SPBeam vs Python comparison summary from beam_comparison_data.csv.

Reads the CSV, computes statistics, generates tables and scatter plots.

Output: research/output/beam_comparison/comparison_plots/
"""

import sys
import os
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "..", "output", "beam_comparison", "beam_comparison_data.csv")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "output", "beam_comparison", "comparison_plots")
SUMMARY_PATH = os.path.join(SCRIPT_DIR, "..", "output", "beam_comparison", "comparison_summary.txt")

PARAMS = [
    ("phiMn",  "Commercial_phiMn_kNm",      "Python_phiMn_kNm",         "φMₙ (kN-m)"),
    ("As",     "Commercial_As_mm2",          "Python_As_mm2",            "Aₛ (mm²)"),
    ("phiVn",  "Commercial_phiVn_at_d_kN",   "Python_phiVn_kN",          "φVₙ at d (kN)"),
    ("s",      "Commercial_stirrup_spacing_mm", "Python_stirrup_spacing_mm", "Stirrup s (mm)"),
]

COLORS = {"Type-A": "#2196F3", "Type-C": "#FF5722"}
MARKERS = {"Type-A": "o", "Type-C": "s"}

# ---------------------------------------------------------------------------
#  Load data
# ---------------------------------------------------------------------------

def load_data(csv_path):
    rows = []
    if not os.path.exists(csv_path):
        print(f"ERROR: CSV not found: {csv_path}")
        return rows
    
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Skip cases where commercial data is empty
                com_phiMn = row.get("Commercial_phiMn_kNm", "").strip()
                if not com_phiMn:
                    continue
                
                beam_type = row.get("BeamType", "")
                is_type_c = "Cantilever" in beam_type
                
                rows.append({
                    "case_id": row.get("CaseID", "?"),
                    "beam_type": beam_type,
                    "type_key": "Type-C" if is_type_c else "Type-A",
                    "label": row.get("LoadLabel", ""),
                    "Python_phiMn": float(row.get("Python_phiMn_kNm", 0)),
                    "Python_phiVn": float(row.get("Python_phiVn_kN", 0)),
                    "Python_As": float(row.get("Python_As_mm2", 0)),
                    "Python_s": float(row.get("Python_stirrup_spacing_mm", 0)),
                    "Python_DCR": float(row.get("Python_DCR", 0)),
                    "SP_phiMn": float(row.get("Commercial_phiMn_kNm", 0)),
                    "SP_phiVn": float(row.get("Commercial_phiVn_at_d_kN", 0)),
                    "SP_As": float(row.get("Commercial_As_mm2", 0)),
                    "SP_s": float(row.get("Commercial_stirrup_spacing_mm", 0)),
                })
            except (ValueError, KeyError):
                continue
    return rows

# ---------------------------------------------------------------------------
#  Generate summary
# ---------------------------------------------------------------------------

def generate_summary(data):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    lines = []
    lines.append("=" * 90)
    lines.append("  SPBEAM vs PYTHON — COMPARISON SUMMARY")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Cases with SPBeam data: {len(data)}")
    lines.append("=" * 90)
    
    # Overall statistics
    lines.append("\n\nSECTION 1: OVERALL STATISTICS (Python / SPBeam ratio)")
    lines.append("=" * 90)
    lines.append(f"\n  {'Metric':<18} {'Mean':>8} {'Std Dev':>8} {'CoV (%)':>8} {'Min':>8} {'Max':>8}  Verdict")
    lines.append(f"  {'-'*18} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}  {'-'*20}")
    
    for key, sp_col, py_col, label in PARAMS:
        ratios = []
        for d in data:
            py_val = d[f"Python_{key}"]
            sp_val = d[f"SP_{key}"]
            if sp_val > 0 and py_val > 0:
                ratios.append(py_val / sp_val)
        
        if ratios:
            mean_r = np.mean(ratios)
            std_r = np.std(ratios)
            cov_r = std_r / mean_r * 100 if mean_r > 0 else 0
            if 0.97 <= mean_r <= 1.03:
                verdict = "✅ Excellent"
            elif 0.90 <= mean_r <= 1.10:
                verdict = "✅ Good"
            elif 0.85 <= mean_r <= 1.15:
                verdict = "⚠️ Fair"
            else:
                verdict = "❌ Check"
            lines.append(
                f"  {label:<18} {mean_r:>8.4f} {std_r:>8.4f} {cov_r:>8.1f} "
                f"{min(ratios):>8.4f} {max(ratios):>8.4f}  {verdict}"
            )
        else:
            lines.append(f"  {label:<18} {'—':>8} {'—':>8} {'—':>8} {'—':>8} {'—':>8}  No data")
    
    # Per-case table
    lines.append("\n\nSECTION 2: PER-CASE COMPARISON")
    lines.append("=" * 90)
    lines.append(f"\n  {'Case':<8} {'φM_n(Py/SP)':>14} {'A_s(Py/SP)':>14} {'φV_n(Py/SP)':>14} {'s(Py/SP)':>14}")
    lines.append(f"  {'-'*8} {'-'*14} {'-'*14} {'-'*14} {'-'*14}")
    
    for d in data:
        r_phi = d["Python_phiMn"] / d["SP_phiMn"] if d["SP_phiMn"] else 0
        r_as = d["Python_As"] / d["SP_As"] if d["SP_As"] else 0
        r_phiV = d["Python_phiVn"] / d["SP_phiVn"] if d["SP_phiVn"] else 0
        r_s = d["Python_s"] / d["SP_s"] if d["SP_s"] else 0
        lines.append(
            f"  {d['case_id']:<8} {r_phi:>14.4f} {r_as:>14.4f} {r_phiV:>14.4f} {r_s:>14.4f}"
        )
    
    # Type-A vs Type-C breakdown
    lines.append("\n\nSECTION 3: GROUPED BY BEAM TYPE")
    lines.append("=" * 90)
    
    for type_key in ["Type-A", "Type-C"]:
        subset = [d for d in data if d["type_key"] == type_key]
        if not subset:
            continue
        lines.append(f"\n  {type_key} ({len(subset)} cases)")
        lines.append(f"  {'-'*80}")
        lines.append(f"  {'Metric':<18} {'Mean':>8} {'Std Dev':>8} {'CoV (%)':>8}")
        lines.append(f"  {'-'*18} {'-'*8} {'-'*8} {'-'*8}")
        
        for key, sp_col, py_col, label in PARAMS:
            ratios = []
            for d in subset:
                py_val = d[f"Python_{key}"]
                sp_val = d[f"SP_{key}"]
                if sp_val > 0 and py_val > 0:
                    ratios.append(py_val / sp_val)
            if ratios:
                mean_r = np.mean(ratios)
                std_r = np.std(ratios)
                cov_r = std_r / mean_r * 100 if mean_r > 0 else 0
                lines.append(
                    f"  {label:<18} {mean_r:>8.4f} {std_r:>8.4f} {cov_r:>8.1f}"
                )
    
    lines.append(f"\n\n{'=' * 90}")
    lines.append("  COMPARISON METHODOLOGY")
    lines.append("=" * 90)
    lines.append("")
    lines.append("  Design code: ACI 318-14")
    lines.append("  Python engine: RCBeam_moment_capacity.py (design_beam)")
    lines.append(f"  Python V_c equation: Detailed (ACI Eq. 22.5.5.1) matching SPBeam")
    lines.append(f"  Data source: {CSV_PATH}")
    lines.append("")
    lines.append("  Ratio = Python / SPBeam")
    lines.append("  Ratio > 1.0 = Python reports higher value (more conservative)")
    lines.append("  Ratio < 1.0 = SPBeam reports higher value")
    lines.append("=" * 90)
    
    with open(SUMMARY_PATH, "w") as f:
        f.write("\n".join(lines))
    print(f"  [V] Summary -> {SUMMARY_PATH}")
    
    return data

# ---------------------------------------------------------------------------
#  Plot generation
# ---------------------------------------------------------------------------

def plot_scatter(data, key, sp_col, py_col, label, ylabel):
    """Scatter plot: Python vs SPBeam, one point per case."""
    fig, ax = plt.subplots(figsize=(6, 6))
    
    x_vals = []
    y_vals = []
    colors_list = []
    
    for d in data:
        sp = d[f"SP_{key}"]
        py = d[f"Python_{key}"]
        if sp > 0 and py > 0:
            x_vals.append(sp)
            y_vals.append(py)
            colors_list.append(COLORS.get(d["type_key"], "#999999"))
    
    x = np.array(x_vals)
    y = np.array(y_vals)
    
    ax.scatter(x, y, c=colors_list, s=60, alpha=0.8, zorder=3,
              edgecolors='black', linewidth=0.5)
    
    # Perfect agreement line
    max_v = max(max(x), max(y)) * 1.1
    line = np.linspace(0, max_v, 100)
    ax.plot(line, line, 'k--', lw=1, alpha=0.5, label='Perfect agreement')
    
    # ±5% bands
    ax.plot(line, line * 1.05, 'gray', ls=':', lw=0.8, alpha=0.4)
    ax.plot(line, line * 0.95, 'gray', ls=':', lw=0.8, alpha=0.4)
    
    # Legend
    from matplotlib.lines import Line2D
    custom_lines = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor=COLORS["Type-A"],
               markersize=10, label='Type-A (Simply Supported)'),
        Line2D([0], [0], marker='s', color='w', markerfacecolor=COLORS["Type-C"],
               markersize=10, label='Type-C (Cantilever)'),
    ]
    ax.legend(handles=custom_lines, fontsize=8)
    
    ax.set_xlabel(f"SPBeam {ylabel}", fontsize=11)
    ax.set_ylabel(f"Python {ylabel}", fontsize=11)
    ax.set_title(f"SPBeam vs Python — {label}", fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, max_v)
    ax.set_ylim(0, max_v)
    ax.set_aspect('equal')
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, f"scatter_{key}.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  [V] Plot -> {path}")

def plot_bar_comparison(data):
    """Grouped bar chart: Python vs SPBeam side by side."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    axes = axes.flatten()
    
    param_config = [
        ("phiMn", "SP_phiMn", "Python_phiMn", "φMₙ (kN-m)", 0),
        ("As", "SP_As", "Python_As", "Aₛ (mm²)", 1),
        ("phiVn", "SP_phiVn", "Python_phiVn", "φVₙ (kN)", 2),
        ("s", "SP_s", "Python_s", "Stirrup s (mm)", 3),
    ]
    
    case_ids = [d["case_id"] for d in data]
    x_pos = np.arange(len(data))
    width = 0.35
    
    for key, sp_key, py_key, ylabel, idx in param_config:
        ax = axes[idx]
        sp_vals = [d[sp_key] for d in data]
        py_vals = [d[py_key] for d in data]
        
        bars1 = ax.bar(x_pos - width/2, sp_vals, width, label='SPBeam',
                       color='#FF5722', alpha=0.85, edgecolor='black', linewidth=0.5)
        bars2 = ax.bar(x_pos + width/2, py_vals, width, label='Python',
                       color='#2196F3', alpha=0.85, edgecolor='black', linewidth=0.5)
        
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(ylabel, fontsize=11, fontweight='bold')
        ax.set_xticks(x_pos)
        ax.set_xticklabels(case_ids, rotation=45, ha='right', fontsize=8)
        ax.legend(fontsize=8)
        ax.grid(True, axis='y', alpha=0.3)
    
    plt.suptitle("SPBeam vs Python — All Parameters", fontsize=13, fontweight='bold')
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "comparison_bars.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  [V] Plot -> {path}")

# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("  SPBeam vs Python — Comparison Summary Generator")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    data = load_data(CSV_PATH)
    
    if not data:
        print("  No data to compare. Fill in the Commercial_* columns first.")
        sys.exit(1)
    
    print(f"\n  Loaded {len(data)} cases with SPBeam data\n")
    
    generate_summary(data)
    
    # Generate scatter plots
    print("\nGenerating plots...")
    for key, sp_col, py_col, label in PARAMS:
        plot_scatter(data, key, sp_col, py_col, label, label)
    
    plot_bar_comparison(data)
    
    print(f"\n{'=' * 60}")
    print(f"  Done! Outputs:")
    print(f"    📄 Summary    : {SUMMARY_PATH}")
    print(f"    📊 Plots dir : {OUTPUT_DIR}")
    print(f"{'=' * 60}")