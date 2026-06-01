#!/usr/bin/env python3
"""
Streamlit Frontend for RC Beam Design (ACI 318-14) + Beam Diagram Calculator

Two-page app:
  1. Beam Diagram Calculator — compute M_u, V_u, deflection from support/loading
  2. RC Section Design — size reinforcement per ACI 318-14, with auto or manual loads

Usage:
    streamlit run scripts/app_beam_design.py
"""

import sys
import os
import io
import base64
import tempfile

import streamlit as st
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Ensure project root on sys.path ──
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.RCBeam_moment_capacity import (
    design_beam, save_equations, save_plot,
    compute_aci_flexure, compute_aci_shear,
)
from scripts.beam_diagram_calculator import (
    compute_beam_diagram,
    compute_deflection_from_diagram,
    SUPPORT_INFO,
)
# Import validation plot functions from the research module
RESEARCH_SCRIPTS = os.path.join(PROJECT_ROOT, "research", "scripts")
if RESEARCH_SCRIPTS not in sys.path:
    sys.path.insert(0, RESEARCH_SCRIPTS)
from validate_beam_aci import (
    plot_flexure_scatter,
    plot_shear_scatter,
    plot_flexure_bar,
    plot_shear_bar,
)

# ──────────────────────────────────────────────────────────────
#  PAGE CONFIG
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RC Beam Designer — ACI 318-14",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────
#  SESSION STATE INIT
# ──────────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "Beam Diagram"

if "auto_Mu" not in st.session_state:
    st.session_state.auto_Mu = None
if "auto_Vu" not in st.session_state:
    st.session_state.auto_Vu = None
if "auto_deflection" not in st.session_state:
    st.session_state.auto_deflection = None
if "auto_span" not in st.session_state:
    st.session_state.auto_span = None
if "auto_service_w" not in st.session_state:
    st.session_state.auto_service_w = None
if "diagram_fig" not in st.session_state:
    st.session_state.diagram_fig = None

# ──────────────────────────────────────────────────────────────
#  HELPER — Plot shear & moment diagrams
# ──────────────────────────────────────────────────────────────

def plot_diagrams(diagram):
    """Return a matplotlib figure with shear and moment diagrams."""
    x = diagram['x']
    M = diagram['M']
    V = diagram['V']
    L = diagram['L']
    support_type = diagram['support_type']

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 5), sharex=True)

    # Moment diagram
    ax1.fill_between(x, 0, M, alpha=0.3, color='royalblue')
    ax1.plot(x, M, 'b-', linewidth=2)
    ax1.axhline(0, color='gray', linewidth=0.5)
    ax1.set_ylabel("Moment (kN-m)", fontsize=11)
    ax1.set_title(f"{SUPPORT_INFO[support_type]['label']} — Shear & Moment Diagrams", fontsize=12)
    ax1.grid(True, alpha=0.3)
    Mmax = np.max(np.abs(M))
    ax1.annotate(f"M_max = {diagram['M_max']:.2f} kN-m",
                 xy=(diagram['x_M'], diagram['M_max'] if M[np.argmax(np.abs(M))] >= 0 else -diagram['M_max']),
                 fontsize=9, fontweight='bold', color='darkblue',
                 xytext=(10, 20), textcoords='offset points',
                 arrowprops=dict(arrowstyle='->', color='darkblue'))

    # Shear diagram
    ax2.fill_between(x, 0, V, alpha=0.3, where=(V >= 0), color='crimson')
    ax2.fill_between(x, 0, V, alpha=0.3, where=(V < 0), color='darkred')
    ax2.plot(x, V, 'r-', linewidth=2)
    ax2.axhline(0, color='gray', linewidth=0.5)
    ax2.set_xlabel("Position along beam (m)", fontsize=11)
    ax2.set_ylabel("Shear (kN)", fontsize=11)
    ax2.grid(True, alpha=0.3)
    ax2.annotate(f"V_max = {diagram['V_max']:.2f} kN",
                 xy=(diagram['x_V'], diagram['V_max']),
                 fontsize=9, fontweight='bold', color='darkred',
                 xytext=(10, 20), textcoords='offset points',
                 arrowprops=dict(arrowstyle='->', color='darkred'))

    plt.tight_layout()
    return fig


def run_beam_diagram_page():
    """Page 1: Beam Diagram Calculator."""
    st.title("📐 Beam Diagram Calculator")
    st.markdown("Define support type and loads to compute design moment, shear, and deflection.")

    col1, col2 = st.columns([1, 1])

    with col1:
        support_type = st.selectbox(
            "Support Type",
            options=list(SUPPORT_INFO.keys()),
            format_func=lambda k: SUPPORT_INFO[k]['label'],
            key="diag_support",
        )
        st.caption(SUPPORT_INFO[support_type]['description'])

        L = st.number_input("Span length, L (m)", min_value=0.5, max_value=30.0, value=6.0, step=0.5, key="diag_L")

        st.subheader("Loads")
        st.caption("Add UDL and/or point loads. Moments and shears are superposed.")

        # UDL input
        col_w1, col_w2 = st.columns([3, 1])
        with col_w1:
            w_udl = st.number_input("UDL, w (kN/m)", min_value=0.0, max_value=500.0, value=30.0, step=1.0, key="diag_w")
        with col_w2:
            add_udl = st.checkbox("Add UDL", value=True, key="diag_add_udl")

        # Point load input
        st.markdown("**Point Load**")
        col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
        with col_p1:
            P = st.number_input("P (kN)", min_value=0.0, max_value=5000.0, value=50.0, step=10.0, key="diag_P")
        with col_p2:
            a = st.number_input("a from left (m)", min_value=0.0, max_value=L, value=L/2, step=0.5, key="diag_a")
        with col_p3:
            add_pl = st.checkbox("Add PL", value=False, key="diag_add_pl")

        # Service load for deflection
        st.subheader("Deflection / Service Load")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            w_service = st.number_input("Service load, w_svc (kN/m)", min_value=0.0, max_value=500.0, value=20.0, step=1.0, key="diag_w_svc",
                                        help="Used for deflection check in RC design. Typically the service-level (unfactored) load.")
        with col_s2:
            st.markdown(" ")
            st.markdown(" ")

    # Compute button
    compute_btn = st.button("🔄 Compute", type="primary", key="diag_compute")

    with col2:
        if compute_btn:
            loads = []
            if add_udl and w_udl > 0:
                loads.append({'type': 'UDL', 'w': w_udl})
            if add_pl and P > 0:
                loads.append({'type': 'PL', 'P': P, 'a': a})

            if not loads:
                st.warning("Add at least one load.")
                return

            with st.spinner("Computing beam diagrams..."):
                diagram = compute_beam_diagram(support_type, L, loads)

                # Store for RC design page
                st.session_state.auto_Mu = diagram['M_max']
                st.session_state.auto_Vu = diagram['V_max']
                st.session_state.auto_span = L
                st.session_state.auto_service_w = w_service

                # Deflection placeholder (will be updated when RC page runs with actual Ie)
                st.session_state.auto_deflection = None
                st.session_state.diagram_fig = plot_diagrams(diagram)

            st.success("✅ Diagram computed! Switch to **RC Section Design** page to design reinforcement.")

            # Results summary
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.metric("Max Moment, M_u", f"{diagram['M_max']:.2f} kN-m")
            with col_r2:
                st.metric("Max Shear, V_u", f"{diagram['V_max']:.2f} kN")
            with col_r3:
                st.metric("Span Length", f"{L:.2f} m")

        # Display diagram if available
        if st.session_state.diagram_fig is not None:
            st.pyplot(st.session_state.diagram_fig)

    # Show current values summary
    if st.session_state.auto_Mu is not None:
        st.divider()
        st.subheader("📋 Current Load Values (passed to RC Design)")
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.info(f"**M_u** = {st.session_state.auto_Mu:.2f} kN-m")
        col_s2.info(f"**V_u** = {st.session_state.auto_Vu:.2f} kN")
        col_s3.info(f"**Span** L = {st.session_state.auto_span:.2f} m")

        if st.button("🔄 Send to RC Section Design →", key="goto_rc"):
            st.session_state.page = "RC Design"
            st.rerun()


def run_rc_design_page():
    """Page 2: RC Section Design (existing app)."""
    st.title("🏗️ RC Beam Moment & Shear Capacity Design")
    st.markdown("**ACI 318-14** — Flexure, Shear & Deflection Check")

    # ── Load Source Toggle ──
    has_auto = st.session_state.auto_Mu is not None

    if has_auto:
        load_source = st.radio(
            "Load Source",
            ["⚡ Auto (from Beam Diagram)", "✏️ Manual Override"],
            horizontal=True,
            key="load_source",
        )
    else:
        load_source = "✏️ Manual Override"
        st.info("💡 Go to **📐 Beam Diagram** page first to auto-compute loads, or enter them manually below.")

    manual_mode = (load_source == "✏️ Manual Override")

    # ── Sidebar Inputs ──
    st.sidebar.header("Section Geometry")
    b = st.sidebar.number_input("Width, b (mm)", min_value=100.0, max_value=2000.0, value=400.0, step=10.0)
    h = st.sidebar.number_input("Height, h (mm)", min_value=150.0, max_value=2000.0, value=600.0, step=10.0)
    p = st.sidebar.number_input("Cover, p (mm)", min_value=10.0, max_value=100.0, value=40.0, step=5.0)

    st.sidebar.header("Reinforcement")
    dl = st.sidebar.number_input("Longitudinal bar dia, dl (mm)", min_value=10.0, max_value=40.0, value=16.0, step=2.0)
    dt = st.sidebar.number_input("Transverse (stirrup) dia, dt (mm)", min_value=6.0, max_value=20.0, value=10.0, step=2.0)

    st.sidebar.header("Material Properties")
    f_c = st.sidebar.number_input("Concrete strength, f'c (MPa)", min_value=15.0, max_value=100.0, value=30.0, step=1.0)
    f_yl = st.sidebar.number_input("Longitudinal steel yield, fy (MPa)", min_value=250.0, max_value=600.0, value=420.0, step=10.0)
    f_yt = st.sidebar.number_input("Transverse steel yield, fyt (MPa)", min_value=250.0, max_value=600.0, value=280.0, step=10.0)

    st.sidebar.header("Design Loads")
    if manual_mode:
        M_ue = st.sidebar.number_input("Design moment, Mu (kN-m)", min_value=0.0, max_value=10000.0, value=100.0, step=1.0)
        V_ue = st.sidebar.number_input("Design shear, Vu (kN)", min_value=0.0, max_value=5000.0, value=50.0, step=1.0)
        L_span = st.sidebar.number_input("Span length, L (m)", min_value=1.0, max_value=30.0, value=6.0, step=0.5)
        w_service = st.sidebar.number_input("Service load, w (kN/m)", min_value=0.0, max_value=500.0, value=20.0, step=1.0)
        st.sidebar.caption("Manual entry: you provide M_u, V_u, span, and service load.")
    else:
        # Auto-populated from beam diagram
        M_ue = st.session_state.auto_Mu
        V_ue = st.session_state.auto_Vu
        L_span = st.session_state.auto_span
        w_service = st.session_state.auto_service_w if st.session_state.auto_service_w else 20.0

        st.sidebar.metric("Design Moment, Mu (kN-m)", f"{M_ue:.2f}")
        st.sidebar.metric("Design Shear, Vu (kN)", f"{V_ue:.2f}")
        st.sidebar.metric("Span Length, L (m)", f"{L_span:.2f}")
        st.sidebar.metric("Service Load, w (kN/m)", f"{w_service:.2f}")
        st.sidebar.caption("Values from Beam Diagram page. Switch to Manual Override to edit.")

    st.sidebar.header("Optional: Capacity Check Mode")
    use_override = st.sidebar.checkbox("Override reinforcement (capacity check)", value=False)

    A_s_provided = None
    A_sp_provided = None
    if use_override:
        A_s_provided = st.sidebar.number_input("Provided As (mm²)", min_value=0.0, value=1600.0, step=50.0)
        A_sp_provided = st.sidebar.number_input("Provided As' (mm²)", min_value=0.0, value=400.0, step=50.0)
        st.sidebar.caption("Overrides the design — computes actual capacity from given steel.")

    beam_name = st.sidebar.text_input("Beam name", value="B-1")
    run_button = st.sidebar.button("🚀 Run Design", type="primary")

    # ── Main Content ──
    if run_button:
        with st.spinner("Running design calculations..."):
            try:
                params = {
                    "name": beam_name,
                    "b": b, "h": h, "p": p,
                    "dl": dl, "dt": dt,
                    "f_c": f_c, "f_yl": f_yl, "f_yt": f_yt,
                    "M_ue": M_ue, "V_ue": V_ue,
                    "L_span": L_span, "w_service": w_service,
                }
                if use_override:
                    params["A_s_provided"] = A_s_provided
                    params["A_sp_provided"] = A_sp_provided

                result = design_beam(**params)

                # Generate outputs in temp dir
                with tempfile.TemporaryDirectory() as tmpdir:
                    save_equations(result, tmpdir)
                    save_plot(result, tmpdir)

                    with open(os.path.join(tmpdir, f"{beam_name}_equations.txt"), "r") as f:
                        equations_text = f.read()

                    with open(os.path.join(tmpdir, f"{beam_name}_section.png"), "rb") as f:
                        plot_bytes = f.read()

                # ── Compare auto vs. RC design deflection ──
                auto_deflection_available = (
                    not manual_mode
                    and st.session_state.auto_deflection is not None
                )

                # ── Top-level metrics ──
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        "Design Moment φMₙ",
                        f"{result['fM_n']/1e6:.2f} kN-m",
                        delta=f"DCR = {result['DCR']:.3f}",
                        delta_color="inverse",
                    )

                with col2:
                    st.metric(
                        "Design Shear φVₙ",
                        f"{result['phi_V_n']:.2f} kN",
                        delta=f"V DCR = {result['V_DCR']:.3f}",
                        delta_color="inverse",
                    )

                with col3:
                    defl_ok = result["deflection_adequate"]
                    st.metric(
                        "Total Deflection",
                        f"{result['delta_total']:.2f} mm",
                        delta=f"Allow {result['L_allowable']:.2f} mm {'✅' if defl_ok else '❌'}",
                    )

                # ── Beam Status ──
                flex_ok = result["DCR"] <= 1.0
                shear_ok = result["V_DCR"] <= 1.0
                all_ok = flex_ok and shear_ok and defl_ok

                if all_ok:
                    st.success("✅ **ALL CHECKS PASSED** — Section is adequate.")
                else:
                    failures = []
                    if not flex_ok:
                        failures.append("Flexure (DCR > 1.0)")
                    if not shear_ok:
                        failures.append("Shear (V DCR > 1.0)")
                    if not defl_ok:
                        failures.append("Deflection (exceeds allowable)")
                    st.error(f"❌ **FAILED:** {', '.join(failures)} — Section is inadequate.")

                # ── Layout: Plot + Key Parameters ──
                st.subheader("Cross-Section & Reinforcement")

                col_plot, col_params = st.columns([1, 1])

                with col_plot:
                    st.image(plot_bytes, caption=f"{beam_name} — Beam Cross-Section", use_container_width=True)

                with col_params:
                    st.markdown("**Reinforcement Summary**")
                    st.info(
                        f"- **Tension bars:** {int(result['n'])} × Ø{result['dl']:.0f} mm  "
                        f"(Aₛ = {result['A_s']:.1f} mm²)\n"
                        f"- **Compression bars:** {int(result['n_prime'])} × Ø{result['dl']:.0f} mm  "
                        f"(Aₛ' = {result['A_sp']:.1f} mm²)\n"
                        f"- **Stirrups:** Ø{result['dt']:.0f} mm @ {result['s_final']:.0f} mm c/c\n"
                        f"- **Layering required:** {'Yes' if result['layering_required'] else 'No'}\n"
                        f"- **Clear spacing:** {result['xx_dis']:.1f} mm"
                    )

                    if result['layering_required']:
                        st.warning(
                            f"⚠️ **Bar overcrowding!** Initial Clear spacing on the bottom layer = {result['xx_dis']:.1f} mm "            
                            f"< 25 mm minimum (ACI 318-14 Section 25.2.1).\n\n"
                            f"New distance between bars on the layer 1 = {result['xx_dis1']:.1f} mm \n\n"            
                            f"New distance between bars on the layer 2 = {result['xx_dis2']:.1f} mm \n\n"
                            f"Bars automatically redistributed into **2 layers** "
                            f"(d = {result['d']:.1f} mm)."
                        )
                    st.markdown("**Section Properties**")
                    st.info(
                        f"- **b = {result['b']:.0f} mm, h = {result['h']:.0f} mm**\n"
                        f"- **d = {result['d']:.1f} mm, d' = {result['d_prime']:.1f} mm**\n"
                        f"- **β₁ = {result['beta_1']:.3f}**\n"
                        f"- **c = {result['c']:.2f} mm, a = {result['a']:.2f} mm**\n"
                        f"- **ρ = {result['rho']:.4f}, ρ_comp = {result['rho_comp']:.4f}**\n"
                        f"- **Iₑ/I𝑔 = {result['Ie']/result['Ig']:.3f}**"
                    )

                # ── Detailed Results in Tabs ──
                tab1, tab2, tab3, tab4 = st.tabs(
                    ["📐 Flexure", "✂️ Shear", "📏 Deflection", "📜 Full Equations"]
                )

                with tab1:
                    st.subheader("Flexural Design (ACI 318-14 Chapter 9)")
                    cols = st.columns(3)
                    cols[0].metric("Nominal Mₙ", f"{result['M_n']/1e6:.3f} kN-m")
                    cols[1].metric("Design φMₙ", f"{result['fM_n']/1e6:.3f} kN-m")
                    cols[2].metric("DCR", f"{result['DCR']:.3f}", f"{'OK' if flex_ok else 'FAIL'}")

                    st.markdown("**Reinforcement Checks**")
                    st.markdown(
                        f"- Aₛ,min = {result['A_smin']:.2f} mm²  ← "
                        f"{'✅ Aₛ >= Aₛ,min' if result['A_s'] >= result['A_smin'] else '❌ Aₛ < Aₛ,min'}\n"
                        f"- Aₛ,max = {result['A_smax']:.2f} mm²  ← "
                        f"{'✅ Aₛ <= Aₛ,max' if result['A_s'] <= result['A_smax'] else '❌ Aₛ > Aₛ,max'}\n"
                        f"- Provided Aₛ = {result['A_s']:.2f} mm²\n"
                        f"- Provided Aₛ' = {result['A_sp']:.2f} mm²"
                    )

                with tab2:
                    st.subheader("Shear Design (ACI 318-14 Section 22.5)")
                    cols = st.columns(3)
                    cols[0].metric("Concrete V_c", f"{result['V_c']:.3f} kN")
                    cols[1].metric("Steel V_s", f"{result['V_s_actual']:.3f} kN")
                    cols[2].metric("Design φVₙ", f"{result['phi_V_n']:.3f} kN")

                    st.markdown("**Stirrup Design**")
                    st.markdown(
                        f"- Shear reinforcement required? {'Yes' if result['shear_reinforcement_required'] else 'No'}\n"
                        f"- Stirrup: Ø{result['dt']:.0f} mm, {result['A_v']:.2f} mm² (2 legs)\n"
                        f"- Required spacing: {result['s_req']:.1f} mm\n"
                        f"- Max spacing: {result['s_max']:.0f} mm\n"
                        f"- **Final spacing: s = {result['s_final']:.0f} mm**\n"
                        f"- Shear DCR = {result['V_DCR']:.3f}  ← "
                        f"{'✅ ADEQUATE' if result['V_DCR'] <= 1.0 else '❌ INADEQUATE'}"
                    )

                with tab3:
                    st.subheader("Deflection Check (ACI 318-14 Section 24.2)")
                    cols = st.columns(3)
                    cols[0].metric("Immediate δ", f"{result['delta_immediate']:.2f} mm")
                    cols[1].metric("Long-term δ", f"{result['delta_long_term']:.2f} mm")
                    cols[2].metric(
                        "Total δ",
                        f"{result['delta_total']:.2f} mm",
                        delta=f"Allow {result['L_allowable']:.2f} mm",
                        delta_color="inverse",
                    )

                    st.markdown("**Calculation Details**")
                    st.markdown(
                        f"- Span L = {result['L_span']:.2f} m\n"
                        f"- Service load w = {result['w_service']:.2f} kN/m\n"
                        f"- M_service = {result['M_service']:.3f} kN-m\n"
                        f"- M_cr = {result['Mcr']:.3f} kN-m  → Section "
                        f"{'**CRACKED**' if result['M_service'] > result['Mcr'] else '**UNCRACKED**'}\n"
                        f"- I𝑔 = {result['Ig']:.1f} × 10⁶ mm⁴, Icr = {result['Icr']:.1f} × 10⁶ mm⁴\n"
                        f"- Ie = {result['Ie']:.1f} × 10⁶ mm⁴  (Ie/I𝑔 = {result['Ie']/result['Ig']:.3f})\n"
                        f"- λ_Δ = {result['lambda_delta']:.3f}\n"
                        f"- Total δ = {result['delta_total']:.2f} mm ≤ L/240 = {result['L_allowable']:.2f} mm → "
                        f"{'✅ ADEQUATE' if result['deflection_adequate'] else '❌ INADEQUATE'}"
                    )

                with tab4:
                    st.subheader("Full Design Equations")
                    st.text(equations_text)

                # ── Download buttons ──
                st.divider()
                st.subheader("📥 Download Outputs")

                col_dl1, col_dl2, col_dl3 = st.columns(3)
                with col_dl1:
                    st.download_button(
                        label="📄 Download Equations (.txt)",
                        data=equations_text,
                        file_name=f"{beam_name}_equations.txt",
                        mime="text/plain",
                    )
                with col_dl2:
                    st.download_button(
                        label="🖼️ Download Section Plot (.png)",
                        data=plot_bytes,
                        file_name=f"{beam_name}_section.png",
                        mime="image/png",
                    )
                with col_dl3:
                    csv_lines = [
                        "Parameter,Value,Unit",
                        f"Beam Name,{beam_name},",
                        f"b,{result['b']:.0f},mm",
                        f"h,{result['h']:.0f},mm",
                        f"f_c,{result['f_c']:.1f},MPa",
                        f"f_yl,{result['f_yl']:.1f},MPa",
                        f"f_yt,{result['f_yt']:.1f},MPa",
                        f"M_ue,{result['M_ue']:.2f},kN-m",
                        f"V_ue,{result['V_ue']:.2f},kN",
                        f"d,{result['d']:.1f},mm",
                        f"d_prime,{result['d_prime']:.1f},mm",
                        f"As,{result['A_s']:.1f},mm2",
                        f"Asp,{result['A_sp']:.1f},mm2",
                        f"n,{int(result['n'])},bars",
                        f"n_prime,{int(result['n_prime'])},bars",
                        f"phiMn,{result['fM_n']/1e6:.3f},kN-m",
                        f"DCR,{result['DCR']:.3f},",
                        f"phiVn,{result['phi_V_n']:.3f},kN",
                        f"V_DCR,{result['V_DCR']:.3f},",
                        f"Stirrup_spacing,{result['s_final']:.0f},mm",
                        f"delta_immediate,{result['delta_immediate']:.2f},mm",
                        f"delta_long_term,{result['delta_long_term']:.2f},mm",
                        f"delta_total,{result['delta_total']:.2f},mm",
                        f"delta_allowable,{result['L_allowable']:.2f},mm",
                        f"deflection_adequate,{'Yes' if result['deflection_adequate'] else 'No'},",
                    ]
                    csv_data = "\n".join(csv_lines)
                    st.download_button(
                        label="📊 Download Summary (.csv)",
                        data=csv_data,
                        file_name=f"{beam_name}_summary.csv",
                        mime="text/csv",
                    )

            except Exception as e:
                st.error(f"❌ Design calculation failed:\n\n```\n{e}\n```")
                import traceback
                st.exception(e)

    else:
        # ── Welcome / placeholder ──
        st.info(
            "👈 Adjust beam parameters in the sidebar and click **🚀 Run Design** "
            "to perform flexural, shear, and deflection checks per **ACI 318-14**."
        )

        if has_auto:
            st.success(
                f"⚡ Auto loads from Beam Diagram: **M_u = {st.session_state.auto_Mu:.2f} kN-m**, "
                f"**V_u = {st.session_state.auto_Vu:.2f} kN**, "
                f"**L = {st.session_state.auto_span:.2f} m**"
            )

        st.markdown(
            """
        ### Features
        - **📐 Beam Diagram** — Compute M_u, V_u from support type and loads  
        - **🏗️ RC Section Design** — Flexure, shear, deflection per ACI 318-14  
        - **Auto / Manual Loads** — Switch between diagram values or manual entry  
        - **Capacity Check** — Evaluate a given bar arrangement  
        - **Cross-Section Plot** — Visual reinforcement layout  
        - **Full Equations** — Step-by-step engineering calculations  
        - **Downloads** — TXT (equations), PNG (plot), CSV (summary)
        """
        )


# -------------------------------------------------------------------
#  VALIDATION PAGE — NAC Experimental Data
# -------------------------------------------------------------------

DATA_DIR = os.path.join(PROJECT_ROOT, "research", "data", "nac_study")


@st.cache_data
def load_flexure_data():
    """Load NAC flexure data from CSV."""
    path = os.path.join(DATA_DIR, "NAC_flexure_data.csv")
    if not os.path.exists(path):
        return None
    import csv
    rows = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


@st.cache_data
def load_shear_data():
    """Load NAC shear data from CSV (no stirrups + with stirrups)."""
    all_rows = []
    for fname in ["NAC_shear_no_stirrups.csv", "NAC_shear_with_stirrups.csv"]:
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            import csv
            with open(path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    all_rows.append(row)
    return all_rows


def run_validation_page():
    """Page 3: Validation against NAC experimental database."""
    st.title("📊 Validation — NAC Experimental Database")
    st.markdown(
        "Compare ACI 318-14 predictions against actual beam test results "
        "from Tošić et al. (2016). "
        "Compute model factors and compare with EC2. "
        "Fill in ETABS/SPBeam results to complete the comparison."
    )

    # Database selector
    db_type = st.radio(
        "Select database",
        ["Flexure (18 beams)", "Shear (no stirrups)", "Shear (with stirrups)"],
        horizontal=True,
        key="val_db_type",
    )

    # Load data
    flexure_data = load_flexure_data()
    shear_data = load_shear_data()

    if db_type == "Flexure (18 beams)":
        if not flexure_data:
            st.warning("Flexure data not found. Run the extraction script first.")
            return
        run_flexure_validation(flexure_data)
    else:
        if not shear_data:
            st.warning("Shear data not found. Run the extraction script first.")
            return
        if db_type == "Shear (no stirrups)":
            shear_filtered = [r for r in shear_data if "A_sw_mm2" not in r or not r.get("A_sw_mm2")]
            if not shear_filtered:
                shear_filtered = [r for r in shear_data if "lambda_factor" not in r]
        else:
            shear_filtered = [r for r in shear_data if "A_sw_mm2" in r and r.get("A_sw_mm2")]
            if not shear_filtered:
                shear_filtered = [r for r in shear_data if "theta_deg" in r]
        run_shear_validation(shear_filtered, db_type)


def compute_interpretation(mean_c):
    if mean_c < 0.95:
        return "⚠️ Unconservative", "orange"
    elif mean_c < 1.10:
        return "✅ Accurate", "green"
    elif mean_c < 1.25:
        return "⚠️ Slightly conservative", "orange"
    else:
        return "❌ Very conservative", "red"


def run_flexure_validation(data):
    """Display flexure validation with interactive beam selection."""
    # Compute ACI predictions for all beams
    computed = []
    for row in data:
        try:
            b = float(row["b_w_mm"])
            d = float(row["d_mm"])
            rho = float(row["rho_l_pct"]) / 100.0
            f_yl = float(row["f_yl_MPa"])
            f_c = float(row["f_c_MPa"])
            M_test = float(row["M_E_test_kNm"])
            M_EC2 = float(row["M_R_pred_kNm"])
            c_EC2 = float(row["c_fl"])

            A_s = rho * b * d
            aci = compute_aci_flexure(b, d, A_s, f_c, f_yl)

            computed.append({
                "specimen": row["Specimen"],
                "b": b, "d": d, "rho": rho, "f_yl": f_yl, "f_c": f_c,
                "M_test": M_test,
                "M_EC2": M_EC2, "c_EC2": c_EC2,
                "M_ACI_nom": aci["M_n_kNm"],
                "c_ACI_nom": round(M_test / aci["M_n_kNm"], 4),
                "M_ACI_des": aci["phiM_n_kNm"],
                "c_ACI_des": round(M_test / aci["phiM_n_kNm"], 4),
                "beta_1": aci["beta_1"],
                "epsilon_t": aci["epsilon_t"],
                "phi": aci["phi"],
                "study": row["Study"],
            })
        except (ValueError, KeyError):
            continue

    if not computed:
        st.error("No valid data to display.")
        return

    # Beam selector
    specimen_list = [c["specimen"] for c in computed]
    selected = st.selectbox("Select beam to inspect", specimen_list, key="val_flex_select")

    beam = next(c for c in computed if c["specimen"] == selected)

    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.subheader("Beam Properties")
        st.info(
            f"**{beam['specimen']}** ({beam['study']})\n\n"
            f"- b = {beam['b']:.0f} mm, d = {beam['d']:.0f} mm\n"
            f"- ρ = {beam['rho']:.4f} ({beam['rho']*100:.2f}%)\n"
            f"- f'c = {beam['f_c']:.1f} MPa\n"
            f"- fy = {beam['f_yl']:.0f} MPa\n"
            f"- β₁ = {beam['beta_1']:.3f}\n"
            f"- ε_t = {beam['epsilon_t']:.5f}\n"
            f"- φ = {beam['phi']:.2f}"
        )

    with col2:
        st.subheader("Model Factor Comparison")
        st.markdown("**c = Test / Predicted** (c > 1.0 = conservative)")

        # Build comparison table
        comp_data = {
            "Method": ["EC2 (paper)", "ACI nominal", "ACI design"],
            "M_pred (kN-m)": [f"{beam['M_EC2']:.1f}", f"{beam['M_ACI_nom']:.2f}", f"{beam['M_ACI_des']:.2f}"],
            "c": [f"{beam['c_EC2']:.3f}", f"{beam['c_ACI_nom']:.3f}", f"{beam['c_ACI_des']:.3f}"],
        }
        st.table(comp_data)

        st.metric("Test Result (M_test)", f"{beam['M_test']:.1f} kN-m")

    # Statistics
    st.divider()
    st.subheader("📈 Database Statistics")

    c_ec2 = [c["c_EC2"] for c in computed]
    c_aci = [c["c_ACI_nom"] for c in computed]
    c_aci_des = [c["c_ACI_des"] for c in computed]

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        mean_ec2 = np.mean(c_ec2)
        cov_ec2 = np.std(c_ec2) / mean_ec2 * 100
        interp, color = compute_interpretation(mean_ec2)
        st.metric("EC2 Mean μ", f"{mean_ec2:.3f}", delta=f"CoV {cov_ec2:.1f}%", delta_color="off")
        st.caption(f"Interpretation: {interp}")
    with col_s2:
        mean_aci = np.mean(c_aci)
        cov_aci = np.std(c_aci) / mean_aci * 100
        interp, color = compute_interpretation(mean_aci)
        st.metric("ACI Nominal Mean μ", f"{mean_aci:.3f}", delta=f"CoV {cov_aci:.1f}%", delta_color="off")
        st.caption(f"Interpretation: {interp}")
    with col_s3:
        mean_aci_d = np.mean(c_aci_des)
        cov_aci_d = np.std(c_aci_des) / mean_aci_d * 100
        interp, color = compute_interpretation(mean_aci_d)
        st.metric("ACI Design Mean μ", f"{mean_aci_d:.3f}", delta=f"CoV {cov_aci_d:.1f}%", delta_color="off")
        st.caption(f"Interpretation: {interp}")

    # Charts: scatter + bar
    st.divider()
    st.subheader("📊 Charts")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        fig, ax = plt.subplots(figsize=(7, 6))
        plot_flexure_scatter(computed, ax=ax)
        st.pyplot(fig)
        plt.close(fig)
    
    with col_chart2:
        fig, ax = plt.subplots(figsize=(max(10, len(computed) * 0.5), 6))
        plot_flexure_bar(computed, ax=ax)
        st.pyplot(fig)
        plt.close(fig)
    
    # Full table
    with st.expander("📋 View all 18 beams"):
        table_data = []
        for c in computed:
            table_data.append({
                "Specimen": c["specimen"],
                "M_test": c["M_test"],
                "EC2": c["M_EC2"],
                "c_EC2": c["c_EC2"],
                "ACI_nom": c["M_ACI_nom"],
                "c_ACI": c["c_ACI_nom"],
                "ACI_des": c["M_ACI_des"],
                "c_ACI_des": c["c_ACI_des"],
            })
        st.table(table_data)

    # Download CSV
    csv_lines = ["Specimen,M_test,EC2,c_EC2,ACI_nom,c_ACI,ACI_des,c_ACI_des"]
    for c in computed:
        csv_lines.append(f"{c['specimen']},{c['M_test']},{c['M_EC2']},{c['c_EC2']},{c['M_ACI_nom']},{c['c_ACI_nom']},{c['M_ACI_des']},{c['c_ACI_des']}")
    st.download_button(
        "📥 Download validation data (.csv)",
        "\n".join(csv_lines),
        file_name="flexure_validation_results.csv",
        mime="text/csv",
    )


def run_shear_validation(data, db_label):
    """Display shear validation."""
    computed = []
    for row in data:
        try:
            b = float(row["b_w_mm"])
            d = float(row["d_mm"])
            f_c = float(row["f_c_MPa"])
            V_test = float(row["V_E_test_kN"])
            V_EC2 = float(row["V_R_pred_kN"])
            c_EC2 = float(row["c_sh"])

            # Check if stirrups
            if "A_sw_mm2" in row and row.get("A_sw_mm2"):
                A_sw = float(row["A_sw_mm2"])
                s = float(row["s_mm"])
                f_yw = float(row["f_yw_MPa"])
                A_v = 2 * A_sw
            else:
                A_v, s, f_yw = 0, 0, 0

            aci = compute_aci_shear(b, d, f_c, A_v=A_v, s=s, f_yw=f_yw)

            computed.append({
                "specimen": row["Specimen"],
                "b": b, "d": d, "f_c": f_c,
                "V_test": V_test,
                "V_EC2": V_EC2, "c_EC2": c_EC2,
                "V_ACI_nom": aci["V_n_kN"],
                "c_ACI_nom": round(V_test / aci["V_n_kN"], 4),
                "V_ACI_des": aci["phiV_n_kN"],
                "c_ACI_des": round(V_test / aci["phiV_n_kN"], 4),
                "V_c": aci["V_c_kN"],
                "V_s": aci["V_s_kN"],
                "study": row["Study"],
            })
        except (ValueError, KeyError):
            continue

    if not computed:
        st.error("No valid data to display.")
        return

    # Beam selector
    specimen_list = [c["specimen"] for c in computed]
    selected = st.selectbox("Select beam to inspect", specimen_list, key="val_shear_select")
    beam = next(c for c in computed if c["specimen"] == selected)

    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.subheader("Beam Properties")
        s_type = "with stirrups" if beam["V_s"] > 0 else "without stirrups"
        st.info(
            f"**{beam['specimen']}** ({beam['study']}) — {s_type}\n\n"
            f"- b = {beam['b']:.0f} mm, d = {beam['d']:.0f} mm\n"
            f"- f'c = {beam['f_c']:.1f} MPa\n"
            f"- V_c = {beam['V_c']:.1f} kN\n"
            f"- V_s = {beam['V_s']:.1f} kN"
        )

    with col2:
        st.subheader("Model Factor Comparison")
        comp_data = {
            "Method": ["EC2 (paper)", "ACI nominal", "ACI design"],
            "V_pred (kN)": [f"{beam['V_EC2']:.1f}", f"{beam['V_ACI_nom']:.1f}", f"{beam['V_ACI_des']:.1f}"],
            "c": [f"{beam['c_EC2']:.3f}", f"{beam['c_ACI_nom']:.3f}", f"{beam['c_ACI_des']:.3f}"],
        }
        st.table(comp_data)
        st.metric("Test Result (V_test)", f"{beam['V_test']:.1f} kN")

    # Statistics
    st.divider()
    st.subheader("📈 Database Statistics")
    c_ec2 = [c["c_EC2"] for c in computed]
    c_aci = [c["c_ACI_nom"] for c in computed]

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        m1, c1 = np.mean(c_ec2), np.std(c_ec2) / np.mean(c_ec2) * 100
        st.metric("EC2 Mean μ", f"{m1:.3f}", delta=f"CoV {c1:.1f}%")
    with col_s2:
        m2, c2 = np.mean(c_aci), np.std(c_aci) / np.mean(c_aci) * 100
        st.metric("ACI Nominal Mean μ", f"{m2:.3f}", delta=f"CoV {c2:.1f}%")

    # Charts: scatter + bar side by side
    st.divider()
    st.subheader("📊 Charts")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        fig, ax = plt.subplots(figsize=(7, 6))
        plot_shear_scatter(computed, ax=ax)
        st.pyplot(fig)
        plt.close(fig)
    
    with col_chart2:
        fig, ax = plt.subplots(figsize=(max(10, len(computed) * 0.55), 6))
        plot_shear_bar(computed, ax=ax)
        st.pyplot(fig)
        plt.close(fig)

    with st.expander(f"📋 View all {len(computed)} beams"):
        table_data = []
        for c in computed:
            table_data.append({
                "Specimen": c["specimen"],
                "V_test": c["V_test"],
                "EC2": c["V_EC2"],
                "c_EC2": c["c_EC2"],
                "ACI_nom": c["V_ACI_nom"],
                "c_ACI": c["c_ACI_nom"],
            })
        st.table(table_data)


# ──────────────────────────────────────────────────────────────
#  NAVIGATION — Updated with Validation Page
# ──────────────────────────────────────────────────────────────
st.sidebar.title("🏗️ Beam Design Suite")
st.sidebar.caption("ACI 318-14 | RC Beam Design")

page = st.sidebar.radio(
    "Navigate",
    ["📐 Beam Diagram", "🏗️ RC Section Design", "📊 Validation (NAC DB)"],
    index=0 if st.session_state.page == "Beam Diagram" else (1 if st.session_state.page == "RC Design" else 2),
    key="nav_radio",
)

page_map = {
    "📐 Beam Diagram": "Beam Diagram",
    "🏗️ RC Section Design": "RC Design",
    "📊 Validation (NAC DB)": "Validation",
}

# ──────────────────────────────────────────────────────────────
#  PAGE ROUTER
# ──────────────────────────────────────────────────────────────

if page == "📐 Beam Diagram":
    st.session_state.page = "Beam Diagram"
    run_beam_diagram_page()
elif page == "🏗️ RC Section Design":
    st.session_state.page = "RC Design"
    run_rc_design_page()
else:
    st.session_state.page = "Validation"
    run_validation_page()

# ──────────────────────────────────────────────────────────────
#  FOOTER
# ──────────────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.caption(
    "**RC Beam Designer** — ACI 318-14   |   "
    "Powered by `RCBeam_moment_capacity.py` & `beam_diagram_calculator.py`"
)
