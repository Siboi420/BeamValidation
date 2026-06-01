#!/usr/bin/env python3
"""
RC Beam Comparison: Python vs. Commercial Software Benchmark

5 Beam Types × 5 Load Steps = 25 Design Cases

Beam types represent common structural scenarios:
  1. Type-A: Simply Supported Floor Beam (office/residential)
  2. Type-B: Continuous Edge Beam (perimeter with torsion)
  3. Type-C: Cantilever Balcony Beam (overhang)
  4. Type-D: High-Strength Transfer Beam (heavy loads)
  5. Type-E: Deep Beam (short span, large depth)

Each beam has 5 loading steps ranging from service to ultimate.
Results are saved for comparison with SPBeam (commercial software).
"""

import sys
import os
import csv
import numpy as np
import json
from datetime import datetime

# Add parent directory to path to import the beam module
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


# Import the existing beam design function
from scripts.RCBeam_moment_capacity import design_beam

# ============================================================================
#  BEAM TYPE DEFINITIONS
# ============================================================================

# UDL steps (kN/m) — round numbers for direct use in commercial software
UDL_STEPS = {
    "A": [50.0, 57.5, 65.0, 72.5, 80.0],  # Simply supported, L=6m
    "C": [15.0, 18.0, 21.0, 24.0, 27.0],  # Cantilever, L=2.5m
}

beam_types = {
    "A": {
        "name": "Type-A: Simply Supported Floor Beam",
        "description": "Interior floor beam, 300×700 mm, f'c=28 MPa, 6m span",
        "b": 300.0, "h": 700.0, "p": 40.0, "dl": 22.2, "dt": 9.5,
        "f_c": 28.0, "f_yl": 420.0, "f_yt": 280.0,
        "L_span": 6.0, "w_service": 20.0,
        "support_type": "simply_supported",  # M = wL²/8, V = wL/2
    },
    "C": {
        "name": "Type-C: Cantilever Balcony Beam",
        "description": "Cantilever beam, 250×400 mm, f'c=28 MPa, 2.5m span",
        "b": 250.0, "h": 400.0, "p": 40.0, "dl": 15.9, "dt": 9.5,
        "f_c": 28.0, "f_yl": 420.0, "f_yt": 280.0,
        "L_span": 2.5, "w_service": 15.0,
        "support_type": "cantilever",  # M = wL²/2, V = wL
    },
}

# ============================================================================
#  GENERATE ALL BEAM CASES
# ============================================================================

def generate_beam_cases():
    """Generate 10 beam cases (2 types × 5 UDL steps).
    
    UDL input → M_u and V_u from statics.
    This approach matches how commercial software works — apply UDL to the beam.
    """
    all_cases = []
    
    for type_key, beam_type in beam_types.items():
        L = beam_type["L_span"]
        udl_values = UDL_STEPS[type_key]
        
        for step_idx, w in enumerate(udl_values):
            # Compute M_u and V_u from statics with UDL input
            if beam_type["support_type"] == "simply_supported":
                M_ue = w * L * L / 8.0   # kN-m
                V_ue = w * L / 2.0       # kN
            else:  # cantilever
                M_ue = w * L * L / 2.0   # kN-m (negative moment at support)
                V_ue = w * L             # kN
            
            case = {
                "case_id": f"{type_key}-S{step_idx + 1}",
                "beam_type": beam_type["name"],
                "description": beam_type["description"],
                "load_step": step_idx + 1,
                "load_label": f"w={w:.1f} kN/m",
                # Geometry
                "b": beam_type["b"],
                "h": beam_type["h"],
                "p": beam_type["p"],
                "dl": beam_type["dl"],
                "dt": beam_type["dt"],
                "f_c": beam_type["f_c"],
                "f_yl": beam_type["f_yl"],
                "f_yt": beam_type["f_yt"],
                # Loads (UDL based)
                "M_ue": M_ue,
                "V_ue": V_ue,
                "w_udl": w,              # INPUT UDL (kN/m) — use this in commercial software
                "L_span": beam_type["L_span"],
                "w_service": beam_type["w_service"],
            }
            all_cases.append(case)
    
    return all_cases

# ============================================================================
#  RUN PYTHON DESIGN FOR ALL CASES
# ============================================================================

def run_python_designs(all_cases):
    """Run the existing RC beam design function for all cases."""
    results = []
    
    print(f"\n{'=' * 90}")
    print(f"  RC BEAM COMPARISON BENCHMARK — Python vs Commercial Software")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Total cases: {len(all_cases)} (2 beam types × 5 load steps)")
    print(f"{'=' * 90}")
    
    for case in all_cases:
        cid = case["case_id"]
        print(f"\n  [{cid}] {case['beam_type']} — {case['load_label']}")
        print(f"  M_u = {case['M_ue']:.2f} kN-m, V_u = {case['V_ue']:.2f} kN")
        
        params = {
            "name": cid,
            "b": case["b"],
            "h": case["h"],
            "p": case["p"],
            "dl": case["dl"],
            "dt": case["dt"],
            "f_c": case["f_c"],
            "f_yl": case["f_yl"],
            "f_yt": case["f_yt"],
            "M_ue": case["M_ue"],
            "V_ue": case["V_ue"],
            "L_span": case["L_span"],
            "w_service": case["w_service"],
        }
        
        try:
            r = design_beam(**params)
            results.append({
                **case,
                "python_success": True,
                "py_A_s": r["A_s"],
                "py_A_sp": r["A_sp"],
                "py_fM_n": r["fM_n"] / 1e6,      # kN-m
                "py_M_n": r["M_n"] / 1e6,         # kN-m
                "py_DCR": r["DCR"],
                "py_phiV_n": r["phi_V_n"],         # kN
                "py_V_DCR": r["V_DCR"],
                "py_s_final": r["s_final"],
                "py_delta_total": r["delta_total"],
                "py_delta_allow": r["L_allowable"],
                "py_n": r["n"],
                "py_n_prime": r["n_prime"],
                "py_d": r["d"],
                "py_Ie": r["Ie"],
                "py_Ig": r["Ig"],
                "py_shear_reinf": r["shear_reinforcement_required"],
                "py_deflection_ok": r["deflection_adequate"],
                "python_error": None,
            })
            print(f"  ✅ φM_n = {r['fM_n']/1e6:.2f} kN-m, DCR = {r['DCR']:.3f}")
        except Exception as e:
            results.append({
                **case,
                "python_success": False,
                "python_error": str(e),
            })
            print(f"  ❌ ERROR: {e}")
    
    return results

# ============================================================================
#  GENERATE COMPARISON OUTPUT
# ============================================================================

def _load_existing_commercial_data(csv_path):
    """
    Load Commercial_* columns from an existing CSV to preserve user-entered values.
    
    Returns a dict: {case_id: [commercial_values_list]} matching the 7 blank fields
    in the CSV row generation.
    """
    if not os.path.exists(csv_path):
        return {}
    
    commercial_fields = [
        "Commercial_phiMn_kNm", "Commercial_DCR", "Commercial_phiVn_kN",
        "Commercial_V_DCR", "Commercial_As_mm2", "Commercial_Asp_mm2",
        "Commercial_stirrup_spacing_mm"
    ]
    
    existing = {}
    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return {}
        
        # Find column indices for commercial fields
        try:
            case_idx = headers.index("CaseID")
        except ValueError:
            return {}
        
        com_indices = []
        for field in commercial_fields:
            try:
                com_indices.append(headers.index(field))
            except ValueError:
                com_indices.append(-1)  # field not found
        
        for row in reader:
            if not row or len(row) <= case_idx:
                continue
            case_id = row[case_idx]
            values = []
            for idx in com_indices:
                if idx >= 0 and idx < len(row):
                    values.append(row[idx])
                else:
                    values.append("")
            existing[case_id] = values
    
    return existing


def generate_comparison_report(results):
    """Save a comprehensive comparison report."""
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output", "beam_comparison")
    os.makedirs(output_dir, exist_ok=True)
    
    txt_path = os.path.join(output_dir, "beam_comparison_report.txt")
    csv_path = os.path.join(output_dir, "beam_comparison_data.csv")
    json_path = os.path.join(output_dir, "beam_comparison_data.json")
    
    lines = []
    lines.append("=" * 100)
    lines.append("  RC BEAM COMPARISON BENCHMARK — PYTHON vs COMMERCIAL SOFTWARE")
    lines.append("=" * 100)
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Code Standard: ACI 318-14")
    lines.append(f"  Engine: RCBeam_moment_capacity.py (Python)")
    lines.append(f"  Total Cases: {len(results)}")
    lines.append("")
    lines.append("=" * 100)
    
    # Group results by beam type
    type_groups = {}
    for r in results:
        key = r["beam_type"]
        if key not in type_groups:
            type_groups[key] = []
        type_groups[key].append(r)
    
    for type_name, cases in type_groups.items():
        lines.append("")
        lines.append(f"  BEAM TYPE: {type_name}")
        lines.append(f"  Description: {cases[0]['description']}")
        lines.append(f"  Section: {cases[0]['b']:.0f} × {cases[0]['h']:.0f} mm")
        lines.append(f"  f'c = {cases[0]['f_c']:.0f} MPa,  fy = {cases[0]['f_yl']:.0f} MPa,  fyt = {cases[0]['f_yt']:.0f} MPa")
        # Add UDL info line
        lines.append(f"  {'UDL (kN/m)':>68}{'← Apply this UDL in commercial software':<40}")
        lines.append("-" * 100)
        
        # Header
        lines.append(f"  {'Case':<8} {'Load':<14} {'w':>7} {'Mu':>8} {'Vu':>8} {'φMn':>10} {'DCR':>8} {'φVn':>8} {'V_DCR':>8} {'s':>6} {'As':>8} {"As'":>8} {'Status':<8}")
        lines.append(f"  {'-'*8} {'-'*14} {'-'*7} {'-'*8} {'-'*8} {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*8} {'-'*8} {'-'*8}")
        
        for c in cases:
            if c["python_success"]:
                status = "✅" if c["py_DCR"] <= 1.0 and c["py_deflection_ok"] else "⚠️"
                lines.append(
                    f"  {c['case_id']:<8} {c['load_label']:<14} "
                    f"{c['w_udl']:>7.2f} "
                    f"{c['M_ue']:>8.1f} {c['V_ue']:>8.1f} "
                    f"{c['py_fM_n']:>10.1f} {c['py_DCR']:>8.3f} "
                    f"{c['py_phiV_n']:>8.1f} {c['py_V_DCR']:>8.3f} "
                    f"{c['py_s_final']:>6.0f} {c['py_n']*np.pi*(c['dl']**2)/4:>8.0f} "
                    f"{c['py_n_prime']*np.pi*(c['dl']**2)/4:>8.0f} "
                    f"{status:<8}"
                )
            else:
                lines.append(f"  {c['case_id']:<8} ERROR: {c['python_error']}")
        
        lines.append("")
        
        # Summary section for this beam type
        lines.append(f"  {'─' * 100}")
        lines.append(f"  KEY DESIGN PARAMETERS FOR {type_name}")
        lines.append(f"  {'─' * 100}")
        
        # Pick step 3 (design level) for detailed comparison
        design_case = [c for c in cases if c["load_step"] == 3][0]
        if design_case["python_success"]:
            r = design_case
            lines.append(f"  Design level (Step 3):")
            lines.append(f"    M_u = {r['M_ue']:.1f} kN-m,  V_u = {r['V_ue']:.1f} kN")
            lines.append(f"    Effective depth d = {r['py_d']:.1f} mm")
            lines.append(f"    Tension steel: {r['py_n']} × Ø{r['dl']} mm bars")
            lines.append(f"    Compression steel: {r['py_n_prime']} × Ø{r['dl']} mm bars")
            lines.append(f"    Stirrups: Ø{r['dt']} mm @ {r['py_s_final']:.0f} mm")
            lines.append(f"    Ie/Ig ratio: {r['py_Ie']/r['py_Ig']:.3f}")
            lines.append(f"    Total deflection: {r['py_delta_total']:.2f} mm (allow {r['py_delta_allow']:.2f} mm)")
            lines.append(f"    Deflection status: {'✅ ADEQUATE' if r['py_deflection_ok'] else '❌ INADEQUATE'}")
            
            # Suggested reinforcement
            n_total = r['py_n'] + r['py_n_prime']
            lines.append(f"")
            lines.append(f"  RECOMMENDED REINFORCEMENT FOR COMMERCIAL SOFTWARE COMPARISON:")
            lines.append(f"    Bottom bars: {r['py_n']} × Ø{r['dl']}")
            lines.append(f"    Top bars: {r['py_n_prime']} × Ø{r['dl']}")
            lines.append(f"    A_s = {r['py_n']*np.pi*(r['dl']**2)/4:.1f} mm²")
            lines.append(f"    A_s' = {r['py_n_prime']*np.pi*(r['dl']**2)/4:.1f} mm²")
            lines.append(f"    ρ = {r['py_n']*np.pi*(r['dl']**2)/4/(r['b']*r['py_d']):.4f}")
            lines.append(f"    ρ_max = 0.75ρ_bal = {0.75*0.85*r['f_c']*0.85*(0.003/(0.003+r['f_yl']/2e5))/r['f_yl']:.4f}")
            lines.append(f"    Shear reinf: {'Required' if r['py_shear_reinf'] else 'Not required (min. provided)'}")
        
        lines.append("")
        lines.append("─" * 100)
    
    # Add SPBeam verification guide
    lines.append("")
    lines.append("=" * 100)
    lines.append("  VERIFICATION GUIDE — SPBeam")
    lines.append("=" * 100)
    lines.append("")
    lines.append("  A. SPBeam Verification (Flexure & Shear):")
    lines.append("     - Define beam section with given b, h, cover, materials")
    lines.append("     - Apply the UDL (w column) as a distributed load")
    lines.append("     - Run analysis to verify M_u and V_u match")
    lines.append("     - Run concrete design per ACI 318-14")
    lines.append("     - Compare: required A_s, stirrup spacing, DCR")
    lines.append("")
    lines.append("  B. SPBeam Deflection Check:")
    lines.append("     - Define beam section with given b, h, cover, materials")
    lines.append("     - Input the design M_u and V_u from Python output")
    lines.append("     - Run design per ACI 318-14")
    lines.append("     - Compare: required A_s, A_s', stirrup spacing, deflection")
    lines.append("")
    lines.append("  C. Key parameters to match:")
    lines.append("     - Stress block factor β₁")
    lines.append("     - Tension-controlled strain limit ε_t = 0.005")
    lines.append("     - Strength reduction factor φ = 0.9")
    lines.append("     - Minimum reinforcement A_s,min")
    lines.append("     - Maximum reinforcement A_s,max = 0.75A_s,bal")
    lines.append("")
    lines.append("  D. Expected differences:")
    lines.append("     - Results should match within 1-3%")
    lines.append("     - Minor differences may arise from:")
    lines.append("       a) Slightly different cover assumptions")
    lines.append("       b) Bar rounding conventions")
    lines.append("       c) Minimum reinforcement handling")
    lines.append("       d) Deflection calculation assumptions")
    lines.append("")
    lines.append("  E. CSV columns to fill:")
    lines.append("     - Commercial_phiMn_kNm — Enter SPBeam moment capacity")
    lines.append("     - Commercial_DCR — Enter SPBeam demand-capacity ratio")
    lines.append("     - Commercial_As_mm2 — Enter required tension steel area")
    lines.append("     - Commercial_Asp_mm2 — Enter required compression steel area")
    lines.append("     - Commercial_stirrup_spacing_mm — Enter stirrup spacing")
    lines.append("=" * 100)
    
    with open(txt_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\n  [V] Report saved -> {txt_path}")
    
    # Save CSV for spreadsheet comparison
    # Load existing commercial data FIRST (before opening file for writing, which truncates it)
    existing_commercial = _load_existing_commercial_data(csv_path)
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        # Header
        csv_headers = [
            "CaseID", "BeamType", "Description", "LoadStep", "LoadLabel", "LoadFactor",
            "b", "h", "d", "f_c", "f_yl", "f_yt",
            "M_u_kNm", "V_u_kN", "w_UDL_kNm", "L_span_m",
            "Python_phiMn_kNm", "Python_DCR", "Python_phiVn_kN", "Python_V_DCR",
            "Python_As_mm2", "Python_Asp_mm2", "Python_n_bars", "Python_np_bars",
            "Python_stirrup_spacing_mm", "Python_delta_mm", "Python_delta_allow_mm",
            "Python_deflection_OK", "Python_shear_reinf_req",
            "Commercial_phiMn_kNm", "Commercial_DCR", "Commercial_phiVn_kN", "Commercial_V_DCR",
            "Commercial_As_mm2", "Commercial_Asp_mm2", "Commercial_stirrup_spacing_mm"
        ]
        writer.writerow(csv_headers)
        
        for r in results:
            if r["python_success"]:
                # Check if we have existing commercial data for this case
                com_vals = existing_commercial.get(r["case_id"], ["", "", "", "", "", "", ""])
                
                row = [
                    r["case_id"],
                    r["beam_type"],
                    r["description"],
                    str(r["load_step"]),
                    r["load_label"],
                    f"{r['w_udl']:.2f}",
                    f"{r['b']:.1f}", f"{r['h']:.1f}", f"{r['py_d']:.1f}",
                    f"{r['f_c']:.1f}", f"{r['f_yl']:.1f}", f"{r['f_yt']:.1f}",
                    f"{r['M_ue']:.2f}", f"{r['V_ue']:.2f}", f"{r['w_udl']:.2f}", f"{r['L_span']:.1f}",
                    f"{r['py_fM_n']:.2f}", f"{r['py_DCR']:.4f}",
                    f"{r['py_phiV_n']:.2f}", f"{r['py_V_DCR']:.4f}",
                    f"{r['py_n']*np.pi*(r['dl']**2)/4:.1f}",
                    f"{r['py_n_prime']*np.pi*(r['dl']**2)/4:.1f}",
                    f"{r['py_n']}", f"{r['py_n_prime']}",
                    f"{r['py_s_final']:.0f}",
                    f"{r['py_delta_total']:.2f}", f"{r['py_delta_allow']:.2f}",
                    "Yes" if r['py_deflection_ok'] else "No",
                    "Yes" if r['py_shear_reinf'] else "No",
                    # Commercial fields — preserved from previous run if available
                    com_vals[0], com_vals[1], com_vals[2], com_vals[3],
                    com_vals[4], com_vals[5], com_vals[6],
                ]
                writer.writerow(row)
    
    print(f"  [V] CSV data saved -> {csv_path}")
    
    # Save JSON for programmatic access
    json_results = []
    for r in results:
        if r["python_success"]:
            json_results.append({
                "case_id": r["case_id"],
                "beam_type": r["beam_type"],
                "load_step": r["load_step"],
                "load_label": r["load_label"],
                "w_udl_kNm": r["w_udl"],
                "section": {
                    "b_mm": r["b"],
                    "h_mm": r["h"],
                    "d_mm": r["py_d"],
                    "fc_MPa": r["f_c"],
                    "fy_MPa": r["f_yl"],
                    "fyt_MPa": r["f_yt"],
                },
                "loads": {
                    "Mu_kNm": r["M_ue"],
                    "Vu_kN": r["V_ue"],
                    "span_m": r["L_span"],
                },
                "python_results": {
                    "phiMn_kNm": r["py_fM_n"],
                    "flexure_DCR": r["py_DCR"],
                    "phiVn_kN": r["py_phiV_n"],
                    "shear_DCR": r["py_V_DCR"],
                    "As_mm2": r["py_n"] * np.pi * (r["dl"]**2) / 4,
                    "Asp_mm2": r["py_n_prime"] * np.pi * (r["dl"]**2) / 4,
                    "n_bars": r["py_n"],
                    "n_compression_bars": r["py_n_prime"],
                    "stirrup_spacing_mm": r["py_s_final"],
                    "deflection_mm": r["py_delta_total"],
                    "deflection_allowable_mm": r["py_delta_allow"],
                    "deflection_adequate": r["py_deflection_ok"],
                    "shear_reinforcement_required": r["py_shear_reinf"],
                },
                "commercial_results_placeholder": {
                    "phiMn_kNm": None,
                    "DCR": None,
                    "phiVn_kN": None,
                    "As_mm2": None,
                    "Asp_mm2": None,
                    "stirrup_spacing_mm": None,
                }
            })

    # Convert numpy types to native Python for JSON serialization
    def convert_json(obj):
        if isinstance(obj, dict):
            return {key: convert_json(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [convert_json(item) for item in obj]
        elif isinstance(obj, tuple):
            return list(convert_json(item) for item in obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj
    
    json_results = convert_json(json_results)
    
    with open(json_path, "w") as f:
        json.dump(json_results, f, indent=2)
    print(f"  [V] JSON data saved -> {json_path}")
    
    # Save individual equation files for each case
    for r in results:
        if r["python_success"]:
            case_output_dir = os.path.join(output_dir, r["case_id"])
            os.makedirs(case_output_dir, exist_ok=True)
            
            # Re-run design to generate equation file
            params = {
                "name": r["case_id"],
                "b": r["b"], "h": r["h"], "p": r["p"],
                "dl": r["dl"], "dt": r["dt"],
                "f_c": r["f_c"], "f_yl": r["f_yl"], "f_yt": r["f_yt"],
                "M_ue": r["M_ue"], "V_ue": r["V_ue"],
                "L_span": r["L_span"], "w_service": r["w_service"],
            }
            beam_result = design_beam(**params)
            
            # Save equation file
            from scripts.RCBeam_moment_capacity import save_equations, save_plot
            try:
                save_equations(beam_result, case_output_dir)
                save_plot(beam_result, case_output_dir)
            except:
                pass
    
    return txt_path, csv_path, json_path


# ============================================================================
#  MAIN
# ============================================================================

if __name__ == "__main__":
    print("Generating 10 RC beam comparison cases (2 types × 5 moment steps)...")
    
    # Generate all beam cases
    all_cases = generate_beam_cases()
    print(f"  → {len(all_cases)} cases created (Simply Supported + Cantilever)")
    
    # Run Python designs
    results = run_python_designs(all_cases)
    
    # Generate comparison report
    print("\n\nGenerating comparison report...")
    txt, csv, js = generate_comparison_report(results)
    
    # Summary
    successes = sum(1 for r in results if r["python_success"])
    failures = sum(1 for r in results if not r["python_success"])
    
    print(f"\n{'=' * 60}")
    print(f"  COMPLETED: {successes} succeeded, {failures} failed")
    print(f"  Output files:")
    print(f"    📄 Report   : {txt}")
    print(f"    📊 CSV data : {csv}")
    print(f"    📋 JSON data: {js}")
    print(f"  {'=' * 60}")
    print(f"\n  To compare with SPBeam:")
    print(f"    1. Create beam sections in SPBeam with given geometries")
    print(f"    2. Apply loads from each case")
    print(f"    3. Fill in the CSV columns under 'Commercial_*'")
    print(f"    4. Compare results with the Python calculations")