#!/usr/bin/env python3
"""
Parametric Study: RC Beam Capacity vs Reinforcement Ratio & Concrete Strength

Sweeps reinforcement ratio ρ and concrete strength f'c to examine their
effects on flexural capacity, DCR, stirrup spacing, and deflection.

Uses the ACI 318-14 design engine (design_beam) from RCBeam_moment_capacity.py.

Output: output/parametric_study/*.png
"""

import sys
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.RCBeam_moment_capacity import design_beam

# ============================================================================
#  PARAMETER DEFINITIONS
# ============================================================================

# Sweep parameters
RHO_PCT = [0.5, 0.8, 1.0, 1.5, 2.0, 2.5]   # reinforcement ratio (%)
FC_VALS = [20, 40, 60]                        # concrete strength (MPa)

# Fixed beam geometry
b = 300.0       # width (mm)
h = 600.0       # height (mm)
p = 40.0        # cover (mm)
dl = 20.0       # longitudinal bar diameter (mm)
dt = 10.0       # transverse bar diameter (mm)
f_yl = 420.0    # longitudinal steel yield (MPa)
f_yt = 280.0    # transverse steel yield (MPa)
L_span = 6.0    # span length (m)
M_ue = 200.0    # design moment (kN-m) — constant
V_ue = 100.0    # design shear (kN) — constant

# Effective depth
d = h - (p + dt + dl / 2)  # = 540 mm

# Service load for deflection: M_ue = w * L² / 8 → w = 8 * M_ue / L²
w_service = 8 * M_ue / L_span ** 2  # kN/m

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "parametric_study")

# ============================================================================
#  RUN PARAMETRIC CASES
# ============================================================================

def run_parametric_study():
    """Run all combinations of ρ × f'c."""
    results = []
    
    print("=" * 70)
    print("  RC BEAM PARAMETRIC STUDY")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Section: {b:.0f} × {h:.0f} mm, d = {d:.1f} mm")
    print(f"  M_u = {M_ue:.0f} kN-m (constant), V_u = {V_ue:.0f} kN (constant)")
    print(f"  Service load: w = {w_service:.2f} kN/m")
    print("=" * 70)
    print(f"\n  {'ρ (%)':>8} {'f_c (MPa)':>10} {'As (mm2)':>10} {'φMn (kN-m)':>12} {'DCR':>8} {'s (mm)':>8} {'δ (mm)':>8}")
    print(f"  {'-'*8} {'-'*10} {'-'*10} {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
    
    for rho_pct in RHO_PCT:
        for fc in FC_VALS:
            # Compute steel area from reinforcement ratio
            A_s = rho_pct / 100.0 * b * d
            
            # Call design_beam with provided steel (capacity check mode)
            result = design_beam(
                name=f"ρ={rho_pct}%_fc={fc}",
                b=b, h=h, p=p, dl=dl, dt=dt,
                f_c=fc, f_yl=f_yl, f_yt=f_yt,
                M_ue=M_ue, V_ue=V_ue,
                L_span=L_span, w_service=w_service,
                A_s_provided=A_s,
                A_sp_provided=0.0,  # singly reinforced
            )
            
            phiMn = result["fM_n"] / 1e6  # convert N-mm to kN-m
            DCR = result["DCR"]
            s_final = result["s_final"]
            delta = result["delta_total"]
            Ie = result["Ie"]
            Ig = result["Ig"]
            IeIg_ratio = Ie / Ig
            
            results.append({
                "rho_pct": rho_pct,
                "fc": fc,
                "A_s": A_s,
                "phiMn_kNm": phiMn,
                "DCR": DCR,
                "s_final_mm": s_final,
                "delta_total_mm": delta,
                "IeIg_ratio": IeIg_ratio,
            })
            
            print(f"  {rho_pct:>8.1f} {fc:>10.0f} {A_s:>10.1f} {phiMn:>12.3f} {DCR:>8.4f} {s_final:>8.0f} {delta:>8.2f}  Ie/Ig={IeIg_ratio:.3f}")
    
    return results


# ============================================================================
#  PLOTTING
# ============================================================================

def plot_phiMn_vs_rho(results):
    """Plot 1: φMn (kN-m) vs ρ (%) for each f'c."""
    fig, ax = plt.subplots(figsize=(8, 5))
    
    colors = {20: '#2196F3', 40: '#FF5722', 60: '#4CAF50'}
    markers = {20: 'o', 40: 's', 60: '^'}
    
    for fc in FC_VALS:
        subset = [r for r in results if r["fc"] == fc]
        x = [r["rho_pct"] for r in subset]
        y = [r["phiMn_kNm"] for r in subset]
        ax.plot(x, y, '-', color=colors[fc], marker=markers[fc], markersize=8,
                linewidth=2, label=f"f'c = {fc} MPa")
    
    ax.axhline(M_ue, color='red', ls='--', lw=1.5, alpha=0.6, label=f'M_u = {M_ue} kN-m')
    
    ax.set_xlabel("Reinforcement Ratio ρ (%)", fontsize=11)
    ax.set_ylabel("Design Moment Capacity φMₙ (kN-m)", fontsize=11)
    ax.set_title("Flexural Capacity vs Reinforcement Ratio", fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, max(RHO_PCT) * 1.1)
    
    path = os.path.join(OUTPUT_DIR, "phiMn_vs_rho.png")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"  [V] Saved: {path}")
    plt.close(fig)


def plot_DCR_vs_rho(results):
    """Plot 2: DCR vs ρ (%) for each f'c."""
    fig, ax = plt.subplots(figsize=(8, 5))
    
    colors = {20: '#2196F3', 40: '#FF5722', 60: '#4CAF50'}
    markers = {20: 'o', 40: 's', 60: '^'}
    
    for fc in FC_VALS:
        subset = [r for r in results if r["fc"] == fc]
        x = [r["rho_pct"] for r in subset]
        y = [r["DCR"] for r in subset]
        ax.plot(x, y, '-', color=colors[fc], marker=markers[fc], markersize=8,
                linewidth=2, label=f"f'c = {fc} MPa")
    
    ax.axhline(1.0, color='red', ls='--', lw=1.5, alpha=0.6, label='DCR = 1.0 (limit)')
    # Shade the unsafe region (DCR > 1.0)
    x_span = ax.get_xlim()
    ax.fill_between([0, max(RHO_PCT) * 1.1], 1.0, 2.0, alpha=0.08, color='red')
    
    ax.set_xlabel("Reinforcement Ratio ρ (%)", fontsize=11)
    ax.set_ylabel("Demand-Capacity Ratio (DCR)", fontsize=11)
    ax.set_title("DCR vs Reinforcement Ratio", fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, max(RHO_PCT) * 1.1)
    ax.set_ylim(0, None)
    
    path = os.path.join(OUTPUT_DIR, "DCR_vs_rho.png")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"  [V] Saved: {path}")
    plt.close(fig)


def plot_IeIg_vs_rho(results):
    """Plot 3: Ie/Ig ratio vs ρ (%) for each f'c."""
    fig, ax = plt.subplots(figsize=(8, 5))
    
    colors = {20: '#2196F3', 40: '#FF5722', 60: '#4CAF50'}
    markers = {20: 'o', 40: 's', 60: '^'}
    
    for fc in FC_VALS:
        subset = [r for r in results if r["fc"] == fc]
        x = [r["rho_pct"] for r in subset]
        y = [r["IeIg_ratio"] for r in subset]
        ax.plot(x, y, '-', color=colors[fc], marker=markers[fc], markersize=8,
                linewidth=2, label=f"f'c = {fc} MPa")
    
    ax.axhline(1.0, color='gray', ls=':', lw=1.5, alpha=0.5, label='Ie/Ig = 1.0 (uncracked)')
    
    ax.set_xlabel("Reinforcement Ratio ρ (%)", fontsize=11)
    ax.set_ylabel("Effective Moment of Inertia Ratio Ie/Ig", fontsize=11)
    ax.set_title("Cracked Section Stiffness (Ie/Ig) vs Reinforcement Ratio", fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, max(RHO_PCT) * 1.1)
    ax.set_ylim(0, 1.1)
    
    path = os.path.join(OUTPUT_DIR, "IeIg_vs_rho.png")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"  [V] Saved: {path}")
    plt.close(fig)


def plot_deflection_vs_rho(results):
    """Plot 4: Total deflection (mm) vs ρ (%) for each f'c."""
    fig, ax = plt.subplots(figsize=(8, 5))
    
    colors = {20: '#2196F3', 40: '#FF5722', 60: '#4CAF50'}
    markers = {20: 'o', 40: 's', 60: '^'}
    
    for fc in FC_VALS:
        subset = [r for r in results if r["fc"] == fc]
        x = [r["rho_pct"] for r in subset]
        y = [r["delta_total_mm"] for r in subset]
        ax.plot(x, y, '-', color=colors[fc], marker=markers[fc], markersize=8,
                linewidth=2, label=f"f'c = {fc} MPa")
    
    # Allowable deflection L/240
    L_allow = L_span * 1000 / 240
    ax.axhline(L_allow, color='red', ls='--', lw=1.5, alpha=0.6,
               label=f'Allowable = L/240 = {L_allow:.1f} mm')
    
    ax.set_xlabel("Reinforcement Ratio ρ (%)", fontsize=11)
    ax.set_ylabel("Total Deflection (mm)", fontsize=11)
    ax.set_title("Total Deflection vs Reinforcement Ratio", fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, max(RHO_PCT) * 1.1)
    
    path = os.path.join(OUTPUT_DIR, "deflection_vs_rho.png")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"  [V] Saved: {path}")
    plt.close(fig)


# ============================================================================
#  MAIN
# ============================================================================

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Run all cases
    results = run_parametric_study()
    
    # Generate plots
    print(f"\nGenerating plots...")
    plot_phiMn_vs_rho(results)
    plot_DCR_vs_rho(results)
    plot_IeIg_vs_rho(results)
    plot_deflection_vs_rho(results)
    
    print(f"\n{'=' * 70}")
    print(f"  Parametric study complete!")
    print(f"  Cases: {len(RHO_PCT)} ρ values × {len(FC_VALS)} f'c values = {len(results)} total")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Plots:")
    print(f"    1. φMₙ (kN-m) vs ρ (%)")
    print(f"    2. DCR vs ρ (%)")
    print(f"    3. Ie/Ig ratio vs ρ (%)")
    print(f"    4. Deflection (mm) vs ρ (%)")
    print(f"{'=' * 70}")