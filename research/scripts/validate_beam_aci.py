#!/usr/bin/env python3
"""
Unified RC Beam Validation: ACI 318-14 vs Experimental Data vs EC2 vs SPBeam

This script validates ACI 318-14 predictions against 50 NAC experimental beams
from the published research paper, using the EXACT SAME calculation engine as
the main beam design app (RCBeam_moment_capacity.py).

Reference:
  Tošić, N., Marinković, S., Ignjatović, I. (2016).
  Construction and Building Materials, 127, 932-944.

Methodology:
  - Reads experimental data (M_test, V_test) from research/data/nac_study/*.csv files
  - Computes ACI 318-14 capacity using compute_aci_flexure() and compute_aci_shear()
    imported from scripts.RCBeam_moment_capacity (SINGLE SOURCE OF TRUTH)
  - Includes EC2 predictions from the paper
  - Leaves blank columns for SPBeam results (user fills in)
  
Output:
  research/output/nac_validation/flexure_validation.csv
  research/output/nac_validation/shear_validation.csv
  research/output/nac_validation/validation_report.txt
"""

import sys
import os
import numpy as np
import csv
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# IMPORT from the actual beam design engine (single source of truth)
from scripts.RCBeam_moment_capacity import compute_aci_flexure, compute_aci_shear

# ============================================================================
#  MAIN VALIDATION
# ============================================================================

def validate_flexure():
    """Validate ACI flexural capacity against NAC experimental data."""
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "nac_study", "NAC_flexure_data.csv")
    
    if not os.path.exists(csv_path):
        print(f"  ❌ File not found: {csv_path}")
        return None
    
    results = []
    
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                b = float(row["b_w_mm"])
                d = float(row["d_mm"])
                rho_l = float(row["rho_l_pct"]) / 100.0  # convert % to decimal
                f_yl = float(row["f_yl_MPa"])
                f_c = float(row["f_c_MPa"])
                M_test = float(row["M_E_test_kNm"])
                M_EC2 = float(row["M_R_pred_kNm"])
                c_EC2 = float(row["c_fl"])
                
                # Compute A_s from reinforcement ratio
                A_s = rho_l * b * d
                
                # Compute ACI capacity using the SAME engine as the main app
                aci = compute_aci_flexure(b, d, A_s, f_c, f_yl)
                
                # Model factors
                c_ACI_nom = M_test / aci["M_n_kNm"]      # no φ factor (matches EC2 method)
                c_ACI_design = M_test / aci["phiM_n_kNm"]  # with φ factor
                
                results.append({
                    "Study": row["Study"],
                    "Specimen": row["Specimen"],
                    "b_mm": b,
                    "d_mm": d,
                    "rho_l_pct": rho_l * 100,
                    "f_yl_MPa": f_yl,
                    "f_c_MPa": f_c,
                    "M_test_kNm": M_test,
                    # EC2 (from paper)
                    "M_EC2_pred_kNm": M_EC2,
                    "c_EC2": c_EC2,
                    # ACI — computed by the same engine as the main app
                    "M_ACI_nom_kNm": aci["M_n_kNm"],
                    "c_ACI_nom": round(c_ACI_nom, 4),
                    "M_ACI_design_kNm": aci["phiM_n_kNm"],
                    "c_ACI_design": round(c_ACI_design, 4),
                    # Additional ACI params
                    "beta_1": aci["beta_1"],
                    "A_s_mm2": aci["A_s_mm2"],
                    "a_mm": aci["a_mm"],
                    "c_mm": aci["c_mm"],
                    "epsilon_t": aci["epsilon_t"],
                    "phi_factor": aci["phi"],
                    # SPBeam comparison (user fills)
                    "M_SPBeam_kNm": "",
                })
            except (ValueError, KeyError) as e:
                print(f"  ⚠️ Error processing row: {row.get('Specimen', '?')} — {e}")
    
    return results


def validate_shear():
    """Validate ACI shear capacity against NAC experimental data."""
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "nac_study", "NAC_shear_no_stirrups.csv")
    csv_stirrups = os.path.join(os.path.dirname(__file__), "..", "data", "nac_study", "NAC_shear_with_stirrups.csv")
    
    results = []
    
    # --- Beams without stirrups ---
    if os.path.exists(csv_path):
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    b = float(row["b_w_mm"])
                    d = float(row["d_mm"])
                    f_c = float(row["f_c_MPa"])
                    V_test = float(row["V_E_test_kN"])
                    
                    # Use the SAME engine as the main app
                    aci = compute_aci_shear(b, d, f_c)
                    
                    c_ACI_nom = V_test / aci["V_n_kN"]
                    c_ACI_design = V_test / aci["phiV_n_kN"]
                    
                    results.append({
                        "Type": "No Stirrups",
                        "Study": row["Study"],
                        "Specimen": row["Specimen"],
                        "b_mm": b,
                        "d_mm": d,
                        "a_d_ratio": float(row["a_d_ratio"]),
                        "f_c_MPa": f_c,
                        "V_test_kN": V_test,
                        "V_EC2_pred_kN": float(row["V_R_pred_kN"]),
                        "c_EC2": float(row["c_sh"]),
                        "V_ACI_nom_kNm": aci["V_n_kN"],
                        "c_ACI_nom": round(c_ACI_nom, 4),
                        "V_ACI_design_kNm": aci["phiV_n_kN"],
                        "c_ACI_design": round(c_ACI_design, 4),
                        "V_c_kN": aci["V_c_kN"],
                        "V_s_kN": aci["V_s_kN"],
                        "V_SPBeam_kN": "",
                    })
                except (ValueError, KeyError) as e:
                    print(f"  ⚠️ Error processing row: {row.get('Specimen', '?')} — {e}")
    
    # --- Beams with stirrups ---
    if os.path.exists(csv_stirrups):
        with open(csv_stirrups, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    b = float(row["b_w_mm"])
                    d = float(row["d_mm"])
                    A_sw = float(row["A_sw_mm2"])  # per leg
                    s = float(row["s_mm"])
                    f_yw = float(row["f_yw_MPa"])
                    f_c = float(row["f_c_MPa"])
                    V_test = float(row["V_E_test_kN"])
                    
                    # Use the SAME engine: A_v = total stirrup area (2-leg)
                    aci = compute_aci_shear(b, d, f_c, A_v=2*A_sw, s=s, f_yw=f_yw)
                    
                    c_ACI_nom = V_test / aci["V_n_kN"]
                    c_ACI_design = V_test / aci["phiV_n_kN"]
                    
                    results.append({
                        "Type": "With Stirrups",
                        "Study": row["Study"],
                        "Specimen": row["Specimen"],
                        "b_mm": b,
                        "d_mm": d,
                        "a_d_ratio": float(row["a_d_ratio"]),
                        "f_c_MPa": f_c,
                        "V_test_kN": V_test,
                        "V_EC2_pred_kN": float(row["V_R_pred_kN"]),
                        "c_EC2": float(row["c_sh"]),
                        "V_ACI_nom_kNm": aci["V_n_kN"],
                        "c_ACI_nom": round(c_ACI_nom, 4),
                        "V_ACI_design_kNm": aci["phiV_n_kN"],
                        "c_ACI_design": round(c_ACI_design, 4),
                        "V_c_kN": aci["V_c_kN"],
                        "V_s_kN": aci["V_s_kN"],
                        "V_SPBeam_kN": "",
                    })
                except (ValueError, KeyError) as e:
                    print(f"  ⚠️ Error processing row: {row.get('Specimen', '?')} — {e}")
    
    return results


# ============================================================================
#  OUTPUT FUNCTIONS
# ============================================================================

def save_flexure_csv(results, output_dir):
    """Save flexure validation results to CSV."""
    if not results:
        return None
    
    path = os.path.join(output_dir, "flexure_validation.csv")
    
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Study", "Specimen", "b_mm", "d_mm", "rho_l_pct", "f_yl_MPa", "f_c_MPa",
            "M_test_kNm",
            "EC2_pred_kNm", "c_EC2",
            "ACI_nom_kNm", "c_ACI_nom",
            "ACI_design_kNm", "c_ACI_design",
            "beta_1", "A_s_mm2", "a_mm", "c_mm", "epsilon_t", "phi",
            "SPBeam_pred_kNm"
        ])
        for r in results:
            writer.writerow([
                r["Study"], r["Specimen"], r["b_mm"], r["d_mm"], r["rho_l_pct"],
                r["f_yl_MPa"], r["f_c_MPa"],
                r["M_test_kNm"],
                r["M_EC2_pred_kNm"], r["c_EC2"],
                r["M_ACI_nom_kNm"], r["c_ACI_nom"],
                r["M_ACI_design_kNm"], r["c_ACI_design"],
                r["beta_1"], r["A_s_mm2"], r["a_mm"], r["c_mm"], r["epsilon_t"], r["phi_factor"],
                "",  # SPBeam — user fills
            ])
    
    print(f"  [V] Flexure validation -> {path}")
    return path


def save_shear_csv(results, output_dir):
    """Save shear validation results to CSV."""
    if not results:
        return None
    
    path = os.path.join(output_dir, "shear_validation.csv")
    
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Type", "Study", "Specimen", "b_mm", "d_mm", "a_d_ratio", "f_c_MPa",
            "V_test_kN",
            "EC2_pred_kN", "c_EC2",
            "ACI_nom_kN", "c_ACI_nom",
            "ACI_design_kN", "c_ACI_design",
            "V_c_kN", "V_s_kN",
            "SPBeam_pred_kN"
        ])
        for r in results:
            writer.writerow([
                r["Type"], r["Study"], r["Specimen"], r["b_mm"], r["d_mm"],
                r["a_d_ratio"], r["f_c_MPa"],
                r["V_test_kN"],
                r["V_EC2_pred_kN"], r["c_EC2"],
                r["V_ACI_nom_kNm"], r["c_ACI_nom"],
                r["V_ACI_design_kNm"], r["c_ACI_design"],
                r["V_c_kN"], r["V_s_kN"],
                "",  # SPBeam — user fills
            ])
    
    print(f"  [V] Shear validation -> {path}")
    return path


def save_report(flexure_results, shear_results, output_dir):
    """Generate the full validation report."""
    path = os.path.join(output_dir, "validation_report.txt")
    
    lines = []
    lines.append("=" * 100)
    lines.append("  RC BEAM VALIDATION — ACI 318-14 vs EXPERIMENTAL DATA vs EC2")
    lines.append("  Reference: Tošić et al. (2016) — Construction and Building Materials 127, 932-944")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("  Engine: RCBeam_moment_capacity.py (compute_aci_flexure / compute_aci_shear)")
    lines.append("=" * 100)
    
    # === FLEXURE ===
    lines.append("")
    lines.append("=" * 100)
    lines.append("  SECTION 1: FLEXURAL CAPACITY VALIDATION (18 NAC Beams)")
    lines.append("=" * 100)
    lines.append("")
    lines.append("  Model factor c = M_test / M_pred (c > 1.0 means code is conservative)")
    lines.append("")
    
    if flexure_results:
        c_EC2_vals = [r["c_EC2"] for r in flexure_results]
        c_ACI_nom_vals = [r["c_ACI_nom"] for r in flexure_results]
        c_ACI_design_vals = [r["c_ACI_design"] for r in flexure_results]
        
        lines.append(f"  {'Specimen':<25} {'M_test':>8} {'EC2_pred':>10} {'c_EC2':>8} {'ACI_nom':>10} {'c_ACI':>8} {'ACI_des':>10} {'c_ACI_des':>10}")
        lines.append(f"  {'-'*25} {'-'*8} {'-'*10} {'-'*8} {'-'*10} {'-'*8} {'-'*10} {'-'*10}")
        
        for r in flexure_results:
            lines.append(
                f"  {r['Specimen']:<25} {r['M_test_kNm']:>8.1f} "
                f"{r['M_EC2_pred_kNm']:>10.1f} {r['c_EC2']:>8.3f} "
                f"{r['M_ACI_nom_kNm']:>10.2f} {r['c_ACI_nom']:>8.3f} "
                f"{r['M_ACI_design_kNm']:>10.2f} {r['c_ACI_design']:>8.3f}"
            )
        
        lines.append("")
        lines.append("  STATISTICAL SUMMARY")
        lines.append(f"  {'Code':<25} {'Mean μ':>10} {'Std Dev σ':>10} {'CoV (%)':>10} {'Min':>8} {'Max':>8}")
        lines.append(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
        lines.append(
            f"  {'EC2 (from paper)':<25} {np.mean(c_EC2_vals):>10.4f} "
            f"{np.std(c_EC2_vals):>10.4f} {np.std(c_EC2_vals)/np.mean(c_EC2_vals)*100:>10.2f} "
            f"{min(c_EC2_vals):>8.3f} {max(c_EC2_vals):>8.3f}"
        )
        lines.append(
            f"  {'ACI 318-14 (nominal)':<25} {np.mean(c_ACI_nom_vals):>10.4f} "
            f"{np.std(c_ACI_nom_vals):>10.4f} {np.std(c_ACI_nom_vals)/np.mean(c_ACI_nom_vals)*100:>10.2f} "
            f"{min(c_ACI_nom_vals):>8.3f} {max(c_ACI_nom_vals):>8.3f}"
        )
        lines.append(
            f"  {'ACI 318-14 (design φ)':<25} {np.mean(c_ACI_design_vals):>10.4f} "
            f"{np.std(c_ACI_design_vals):>10.4f} {np.std(c_ACI_design_vals)/np.mean(c_ACI_design_vals)*100:>10.2f} "
            f"{min(c_ACI_design_vals):>8.3f} {max(c_ACI_design_vals):>8.3f}"
        )
    
    # === SHEAR ===
    lines.append("")
    lines.append("=" * 100)
    lines.append("  SECTION 2: SHEAR CAPACITY VALIDATION")
    lines.append("=" * 100)
    
    if shear_results:
        ns_results = [r for r in shear_results if r["Type"] == "No Stirrups"]
        s_results = [r for r in shear_results if r["Type"] == "With Stirrups"]
        
        for cat, cat_label, rows in [("NS", "without", ns_results), ("S", "with", s_results)]:
            if not rows:
                continue
            lines.append("")
            lines.append(f"  2{cat}. Beams {cat_label} stirrups")
            lines.append("  " + "-" * 90)
            lines.append(f"  {'Specimen':<25} {'V_test':>8} {'EC2_pred':>10} {'c_EC2':>8} {'ACI_nom':>10} {'c_ACI':>8}")
            lines.append(f"  {'-'*25} {'-'*8} {'-'*10} {'-'*8} {'-'*10} {'-'*8}")
            
            for r in rows:
                lines.append(
                    f"  {r['Specimen']:<25} {r['V_test_kN']:>8.1f} "
                    f"{r['V_EC2_pred_kN']:>10.1f} {r['c_EC2']:>8.3f} "
                    f"{r['V_ACI_nom_kNm']:>10.2f} {r['c_ACI_nom']:>8.3f}"
                )
            
            c_EC2 = [r["c_EC2"] for r in rows]
            c_ACI = [r["c_ACI_nom"] for r in rows]
            
            lines.append("")
            lines.append(f"  {'Code':<25} {'Mean μ':>10} {'Std Dev σ':>10} {'CoV (%)':>10} {'Min':>8} {'Max':>8}")
            lines.append(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
            lines.append(
                f"  {'EC2 (from paper)':<25} {np.mean(c_EC2):>10.4f} "
                f"{np.std(c_EC2):>10.4f} {np.std(c_EC2)/np.mean(c_EC2)*100:>10.2f} "
                f"{min(c_EC2):>8.3f} {max(c_EC2):>8.3f}"
            )
            lines.append(
                f"  {'ACI 318-14 (nominal)':<25} {np.mean(c_ACI):>10.4f} "
                f"{np.std(c_ACI):>10.4f} {np.std(c_ACI)/np.mean(c_ACI)*100:>10.2f} "
                f"{min(c_ACI):>8.3f} {max(c_ACI):>8.3f}"
            )
    
    # === SUMMARY TABLE ===
    lines.append("")
    lines.append("=" * 100)
    lines.append("  SECTION 3: SUMMARY — ACI vs EC2 vs EXPERIMENT")
    lines.append("=" * 100)
    lines.append("")
    lines.append(f"  {'Database':<20} {'Code':<25} {'n':>5} {'Mean μ':>10} {'CoV (%)':>10} {'Interpretation'}")
    lines.append(f"  {'-'*20} {'-'*25} {'-'*5} {'-'*10} {'-'*10} {'-'*30}")
    
    def add_summary_row(database, code, n, mean, cov):
        if mean < 0.95:
            interp = "⚠️ Unconservative"
        elif mean < 1.10:
            interp = "✅ Accurate"
        elif mean < 1.25:
            interp = "⚠️ Slightly conservative"
        else:
            interp = "❌ Very conservative"
        lines.append(f"  {database:<20} {code:<25} {n:>5} {mean:>10.3f} {cov:>10.2f} {interp}")
    
    if flexure_results:
        add_summary_row("Flexure", "EC2 (paper)", len(flexure_results),
                        np.mean([r["c_EC2"] for r in flexure_results]),
                        np.std([r["c_EC2"] for r in flexure_results]) / np.mean([r["c_EC2"] for r in flexure_results]) * 100)
        add_summary_row("Flexure", "ACI 318-14 (nom)", len(flexure_results),
                        np.mean([r["c_ACI_nom"] for r in flexure_results]),
                        np.std([r["c_ACI_nom"] for r in flexure_results]) / np.mean([r["c_ACI_nom"] for r in flexure_results]) * 100)
        add_summary_row("Flexure", "ACI 318-14 (des)", len(flexure_results),
                        np.mean([r["c_ACI_design"] for r in flexure_results]),
                        np.std([r["c_ACI_design"] for r in flexure_results]) / np.mean([r["c_ACI_design"] for r in flexure_results]) * 100)
    
    if shear_results:
        ns = [r for r in shear_results if r["Type"] == "No Stirrups"]
        sw = [r for r in shear_results if r["Type"] == "With Stirrups"]
        if ns:
            add_summary_row("Shear (no stir.)", "EC2 (paper)", len(ns),
                            np.mean([r["c_EC2"] for r in ns]),
                            np.std([r["c_EC2"] for r in ns]) / np.mean([r["c_EC2"] for r in ns]) * 100)
            add_summary_row("Shear (no stir.)", "ACI 318-14 (nom)", len(ns),
                            np.mean([r["c_ACI_nom"] for r in ns]),
                            np.std([r["c_ACI_nom"] for r in ns]) / np.mean([r["c_ACI_nom"] for r in ns]) * 100)
        if sw:
            add_summary_row("Shear (w/ stir.)", "EC2 (paper)", len(sw),
                            np.mean([r["c_EC2"] for r in sw]),
                            np.std([r["c_EC2"] for r in sw]) / np.mean([r["c_EC2"] for r in sw]) * 100)
            add_summary_row("Shear (w/ stir.)", "ACI 318-14 (nom)", len(sw),
                            np.mean([r["c_ACI_nom"] for r in sw]),
                            np.std([r["c_ACI_nom"] for r in sw]) / np.mean([r["c_ACI_nom"] for r in sw]) * 100)
    
    lines.append("")
    lines.append("=" * 100)
    lines.append("  ENGINE: RCBeam_moment_capacity.py (compute_aci_flexure / compute_aci_shear)")
    lines.append("  Same code used by: app_beam_design.py (Streamlit) & rc_beam_comparison.py")
    lines.append("=" * 100)
    lines.append("")
    lines.append("  Note: EC2 and ACI-nominal use NO partial safety factors.")
    lines.append("        ACI-design uses φ = 0.9 (flexure) and φ = 0.75 (shear).")
    lines.append("=" * 100)
    
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"  [V] Validation report -> {path}")
    return path


# ============================================================================
#  SCATTER PLOT FUNCTIONS (shared with Streamlit app)
# ============================================================================

def _r2_score(y_true, y_pred):
    """Compute R² coefficient of determination manually (no sklearn dependency)."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1 - ss_res / ss_tot if ss_tot > 0 else 0


def plot_flexure_scatter(computed, ax=None):
    """
    Create scatter plot: M_test vs M_pred for flexure validation.
    
    Parameters
    ----------
    computed : list of dict — must have 'M_test', 'M_EC2', 'M_ACI_nom', 'M_ACI_des'
    ax : matplotlib Axes, optional — if None, creates new figure
    
    Returns
    -------
    fig : matplotlib Figure (only if ax was None)
    """
    import matplotlib.pyplot as plt
    
    x = np.array([c["M_test"] for c in computed])
    y_ec2 = np.array([c["M_EC2"] for c in computed])
    y_aci = np.array([c["M_ACI_nom"] for c in computed])
    y_aci_des = np.array([c["M_ACI_des"] for c in computed])
    
    own_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=(7, 6))
        own_fig = True
    
    ax.scatter(x, y_ec2, marker='s', s=60, color='#2196F3', alpha=0.7, label='EC2', zorder=3)
    ax.scatter(x, y_aci, marker='o', s=60, color='#FF5722', alpha=0.7, label='ACI nominal', zorder=3)
    ax.scatter(x, y_aci_des, marker='^', s=60, color='#4CAF50', alpha=0.7, label='ACI design', zorder=3)
    
    max_v = max(max(x), max(y_ec2), max(y_aci))
    line = np.linspace(0, max_v * 1.1, 100)
    ax.plot(line, line, 'k--', lw=1.5, alpha=0.5, label='Perfect agreement (y=x)')
    
    # Highlight c < 0.85 zone (unconservative predictions)
    # c = test/pred → pred = test/c. For c=0.85: pred = test/0.85 ≈ 1.176*test
    hx = np.linspace(0, max_v * 1.1, 100)
    ax.fill_between(hx, hx, hx / 0.85, alpha=0.08, color='red', label='c < 0.85 (unconservative)')
    ax.plot(hx, hx / 0.85, 'r--', lw=1, alpha=0.4)
    
    # Red rings around unconservative points
    for i in range(len(computed)):
        ec2_c = computed[i].get("c_EC2", 1)
        aci_c = computed[i].get("c_ACI_nom", 1)
        des_c = computed[i].get("c_ACI_des", 1)
        if (ec2_c is not None and ec2_c < 0.85) or (aci_c is not None and aci_c < 0.85) or (des_c is not None and des_c < 0.85):
            ax.scatter([x[i]], [y_ec2[i]], marker='s', s=120, facecolors='none',
                       edgecolors='red', linewidths=2.5, zorder=5)
            ax.scatter([x[i]], [y_aci[i]], marker='o', s=120, facecolors='none',
                       edgecolors='red', linewidths=2.5, zorder=5)
            ax.scatter([x[i]], [y_aci_des[i]], marker='^', s=120, facecolors='none',
                       edgecolors='red', linewidths=2.5, zorder=5)
    
    ax.set_xlabel('M_test (kN-m)', fontsize=11)
    ax.set_ylabel('M_pred (kN-m)', fontsize=11)
    ax.set_title('Flexure: Experimental vs Predicted Moment', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    ax.set_xlim(0, max_v * 1.1)
    ax.set_ylim(0, max_v * 1.1)
    ax.set_aspect('equal')
    
    r2_ec2 = _r2_score(x, y_ec2)
    r2_aci = _r2_score(x, y_aci)
    r2_des = _r2_score(x, y_aci_des)
    ax.annotate(f'R²(EC2) = {r2_ec2:.3f}\nR²(ACI) = {r2_aci:.3f}\nR²(ACI des) = {r2_des:.3f}',
                xy=(0.05, 0.85), xycoords='axes fraction', fontsize=9,
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.9))
    
    if own_fig:
        return fig
    return None


def plot_shear_scatter(computed, ax=None):
    """
    Create scatter plot: V_test vs V_pred for shear validation.
    
    Parameters
    ----------
    computed : list of dict — must have 'V_test', 'V_EC2', 'V_ACI_nom'
    ax : matplotlib Axes, optional — if None, creates new figure
    
    Returns
    -------
    fig : matplotlib Figure (only if ax was None)
    """
    import matplotlib.pyplot as plt
    
    x = np.array([c["V_test"] for c in computed])
    y_ec2 = np.array([c["V_EC2"] for c in computed])
    y_aci = np.array([c["V_ACI_nom"] for c in computed])
    
    own_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=(7, 6))
        own_fig = True
    
    ax.scatter(x, y_ec2, marker='s', s=60, color='#2196F3', alpha=0.7, label='EC2', zorder=3)
    ax.scatter(x, y_aci, marker='o', s=60, color='#FF5722', alpha=0.7, label='ACI nominal', zorder=3)
    
    max_v = max(max(x), max(y_ec2), max(y_aci))
    line = np.linspace(0, max_v * 1.1, 100)
    ax.plot(line, line, 'k--', lw=1.5, alpha=0.5, label='Perfect agreement (y=x)')
    
    # Highlight c < 0.85 zone (unconservative predictions)
    hx = np.linspace(0, max_v * 1.1, 100)
    ax.fill_between(hx, hx, hx / 0.85, alpha=0.08, color='red', label='c < 0.85 (unconservative)')
    ax.plot(hx, hx / 0.85, 'r--', lw=1, alpha=0.4)
    
    # Red rings around unconservative points
    for i in range(len(computed)):
        ec2_c = computed[i].get("c_EC2", 1)
        aci_c = computed[i].get("c_ACI_nom", 1)
        if (ec2_c is not None and ec2_c < 0.85) or (aci_c is not None and aci_c < 0.85):
            ax.scatter([x[i]], [y_ec2[i]], marker='s', s=120, facecolors='none',
                       edgecolors='red', linewidths=2.5, zorder=5)
            ax.scatter([x[i]], [y_aci[i]], marker='o', s=120, facecolors='none',
                       edgecolors='red', linewidths=2.5, zorder=5)
    
    ax.set_xlabel('V_test (kN)', fontsize=11)
    ax.set_ylabel('V_pred (kN)', fontsize=11)
    ax.set_title('Shear: Experimental vs Predicted Strength', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    ax.set_xlim(0, max_v * 1.1)
    ax.set_ylim(0, max_v * 1.1)
    ax.set_aspect('equal')
    
    r2_ec2 = _r2_score(x, y_ec2)
    r2_aci = _r2_score(x, y_aci)
    ax.annotate(f'R²(EC2) = {r2_ec2:.3f}\nR²(ACI) = {r2_aci:.3f}',
                xy=(0.05, 0.85), xycoords='axes fraction', fontsize=9,
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.9))
    
    if own_fig:
        return fig
    return None

def plot_flexure_bar(computed, ax=None, max_beams=18):
    """
    Create grouped bar chart: M_test vs ACI vs EC2 for each beam.
    Includes ACI design (with φ) as 4th bar.
    
    Parameters
    ----------
    computed : list of dict — must have 'specimen', 'M_test', 'M_EC2', 'M_ACI_nom', 'M_ACI_des'
    ax : matplotlib Axes, optional
    max_beams : int — limit beams displayed (default 18)
    
    Returns
    -------
    fig : matplotlib Figure (only if ax was None)
    """
    import matplotlib.pyplot as plt
    
    sorted_data = sorted(computed, key=lambda c: c["M_test"], reverse=True)[:max_beams]
    n = len(sorted_data)
    
    labels = [c["specimen"] for c in sorted_data]
    x_test = np.array([c["M_test"] for c in sorted_data])
    x_ec2 = np.array([c["M_EC2"] for c in sorted_data])
    x_aci = np.array([c["M_ACI_nom"] for c in sorted_data])
    x_aci_des = np.array([c["M_ACI_des"] for c in sorted_data])
    
    own_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=(max(10, n * 0.55), 6))
        own_fig = True
    
    x_pos = np.arange(n)
    width = 0.20
    
    ax.bar(x_pos - 1.5*width, x_test, width, label='Test', color='#333333', alpha=0.9, edgecolor='black', linewidth=0.5)
    ax.bar(x_pos - 0.5*width, x_ec2, width, label='EC2', color='#2196F3', alpha=0.85, edgecolor='black', linewidth=0.5)
    ax.bar(x_pos + 0.5*width, x_aci, width, label='ACI nom', color='#FF5722', alpha=0.85, edgecolor='black', linewidth=0.5)
    ax.bar(x_pos + 1.5*width, x_aci_des, width, label='ACI des', color='#4CAF50', alpha=0.85, edgecolor='black', linewidth=0.5)
    
    ax.set_ylabel('Moment (kN-m)', fontsize=11)
    ax.set_title('Flexure: Test vs EC2 vs ACI — All Beams', fontsize=12, fontweight='bold')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    ax.legend(fontsize=8)
    ax.grid(True, axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    if own_fig:
        return fig
    return None


def plot_shear_bar(computed, ax=None, max_beams=24):
    """
    Create grouped bar chart: V_test vs ACI vs EC2 for each beam.
    Includes ACI design (with φ) as 4th bar.
    
    Parameters
    ----------
    computed : list of dict — must have 'specimen', 'V_test', 'V_EC2', 'V_ACI_nom', 'V_ACI_des'
    ax : matplotlib Axes, optional
    max_beams : int — limit beams displayed
    
    Returns
    -------
    fig : matplotlib Figure (only if ax was None)
    """
    import matplotlib.pyplot as plt
    
    sorted_data = sorted(computed, key=lambda c: c["V_test"], reverse=True)[:max_beams]
    n = len(sorted_data)
    
    labels = [c["specimen"] for c in sorted_data]
    x_test = np.array([c["V_test"] for c in sorted_data])
    x_ec2 = np.array([c["V_EC2"] for c in sorted_data])
    x_aci = np.array([c["V_ACI_nom"] for c in sorted_data])
    x_aci_des = np.array([c["V_ACI_des"] for c in sorted_data])
    
    own_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=(max(10, n * 0.55), 6))
        own_fig = True
    
    x_pos = np.arange(n)
    width = 0.20
    
    ax.bar(x_pos - 1.5*width, x_test, width, label='Test', color='#333333', alpha=0.9, edgecolor='black', linewidth=0.5)
    ax.bar(x_pos - 0.5*width, x_ec2, width, label='EC2', color='#2196F3', alpha=0.85, edgecolor='black', linewidth=0.5)
    ax.bar(x_pos + 0.5*width, x_aci, width, label='ACI nom', color='#FF5722', alpha=0.85, edgecolor='black', linewidth=0.5)
    ax.bar(x_pos + 1.5*width, x_aci_des, width, label='ACI des', color='#4CAF50', alpha=0.85, edgecolor='black', linewidth=0.5)
    
    ax.set_ylabel('Shear (kN)', fontsize=11)
    ax.set_title('Shear: Test vs EC2 vs ACI — All Beams', fontsize=12, fontweight='bold')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    ax.legend(fontsize=8)
    ax.grid(True, axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    if own_fig:
        return fig
    return None


# ============================================================================
#  MAIN
# ============================================================================

if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output", "nac_validation")
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 70)
    print("  RC BEAM ACI 318-14 VALIDATION AGAINST EXPERIMENTAL DATA")
    print("  Engine: RCBeam_moment_capacity.py (compute_aci_flexure / compute_aci_shear)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Validate flexure
    print("\n[1/3] Validating flexural capacity...")
    flexure_results = validate_flexure()
    if flexure_results:
        print(f"  → {len(flexure_results)} beams processed")
        save_flexure_csv(flexure_results, output_dir)
    else:
        print("  ❌ No flexure data found")
    
    # Validate shear
    print("\n[2/3] Validating shear capacity...")
    shear_results = validate_shear()
    if shear_results:
        ns = len([r for r in shear_results if r["Type"] == "No Stirrups"])
        ws = len([r for r in shear_results if r["Type"] == "With Stirrups"])
        print(f"  → {ns} without stirrups, {ws} with stirrups")
        save_shear_csv(shear_results, output_dir)
    else:
        print("  ❌ No shear data found")
    
    # Generate report
    print("\n[3/3] Generating validation report...")
    save_report(flexure_results, shear_results, output_dir)
    
    print(f"\n{'=' * 70}")
    print(f"  All outputs in: {output_dir}")
    print(f"{'=' * 70}")
    print(f"\n  Files:")
    print(f"    📄 flexure_validation.csv — 18 NAC beams")
    print(f"    📄 shear_validation.csv   — NAC shear beams")
    print(f"    📄 validation_report.txt  — Full statistics")
    print(f"\n  Engine: uses compute_aci_flexure() / compute_aci_shear()")
    print(f"          from RCBeam_moment_capacity.py")