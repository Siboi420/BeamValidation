#!/usr/bin/env python3
"""
RC Beam Moment & Shear Capacity Design per ACI 318-14

Supports multiple beams defined in a list. Each beam is designed
for flexural and shear capacity, with outputs saved per beam.

References:
  - ACI 318-14: Chapters 9, 21, 22
"""

import numpy as np
import matplotlib.pyplot as plt
import os


# ============================================================================
#  BEAM DEFINITIONS
# ============================================================================
# Add/remove entries as needed. Each beam must have a unique name.
#
# Parameters:
#   name, b, h, p, dl, dt, f_c, f_yl, f_yt, M_ue, V_ue  (required)
#   A_s_provided, A_sp_provided                           (optional — override)
#
# If A_s_provided is set, the script will use that steel area and compute
# the actual moment capacity (phiM_n_actual) based on it, rather than
# calculating the required steel from the design moment.

beams = [
    {
        "name": "B-1",
        "b": 400.0,      # width (mm)
        "h": 600.0,      # height (mm)
        "p": 40.0,       # cover (mm)
        "dl": 16.0,      # long. bar dia (mm)
        "dt": 10.0,      # trans. bar dia (mm)
        "f_c": 30,     # concrete strength (MPa)
        "f_yl": 420.0,   # long. yield (MPa)
        "f_yt": 280.0,   # trans. yield (MPa)
        "M_ue": 18.87,   # design moment (kN-m)
        "V_ue": 17.61,   # design shear (kN)
        "L_span": 8.0,   # span length (m) — for deflection check
        "w_service": 5.66,  # service load (kN/m) — for deflection check
        # "A_s_provided": 1600.0,   # optional: override tension steel (mm2)
        # "A_sp_provided": 400.0,   # optional: override compression steel (mm2)
    },

]

# ============================================================================
#  CONSTANTS
# ============================================================================
MINIMUM_SPACING = 25  # mm
EPSILON_CU = 0.003    # ultimate concrete strain


# ============================================================================
#  STANDALONE ACI 318-14 CALCULATION FUNCTIONS
#  (Require only section & reinforcement parameters — no beam geometry)
#  These are the single source of truth for ACI 318-14 calculations.
# ============================================================================

def _beta_1(f_c):
    """ACI 318-14 Section 22.2.2.4.3 — Stress block factor."""
    if f_c >= 55:
        return 0.65
    elif f_c > 28:
        return round(0.85 - 0.05 * (f_c - 28) / 7, 2)
    else:
        return 0.85


def _strength_reduction_factor(epsilon_t, epsilon_y):
    """ACI Table 21.2.2 — Determine φ based on net tensile strain."""
    if epsilon_t >= 0.005:
        return 0.90  # tension-controlled
    elif epsilon_t > epsilon_y:
        # Transition zone (spiral)
        return 0.65 + 0.25 * (epsilon_t - epsilon_y) / (0.005 - epsilon_y)
    else:
        return 0.65  # compression-controlled


def compute_aci_flexure(b, d, A_s, f_c, f_yl):
    """
    Compute ACI 318-14 flexural capacity for singly reinforced rectangular section.
    
    This is a standalone calculation — requires only cross-section parameters.
    Used by design_beam() and by external validation scripts.
    
    Parameters
    ----------
    b : float — beam width (mm)
    d : float — effective depth (mm)
    A_s : float — tension steel area (mm²)
    f_c : float — concrete compressive strength (MPa)
    f_yl : float — steel yield strength (MPa)
    
    Returns
    -------
    dict
        M_n_kNm : float — nominal moment capacity (kN-m)
        phiM_n_kNm : float — design moment capacity (kN-m)
        a_mm : float — stress block depth (mm)
        c_mm : float — neutral axis depth (mm)
        beta_1 : float — stress block factor
        epsilon_t : float — net tensile strain
        phi : float — strength reduction factor
        A_s_mm2 : float — steel area provided
    """
    epsilon_y = f_yl / 2e5
    beta_1 = _beta_1(f_c)
    
    # Singly reinforced — assume tension steel yields
    a = A_s * f_yl / (0.85 * f_c * b)
    c = a / beta_1
    
    # Check strain in tension steel
    epsilon_t = EPSILON_CU * (d - c) / c
    
    # Nominal moment capacity
    M_n = A_s * f_yl * (d - a / 2)  # N-mm
    
    # Strength reduction factor (ACI Table 21.2.2)
    phi = _strength_reduction_factor(epsilon_t, epsilon_y)
    phiM_n = phi * M_n
    
    return {
        "M_n_kNm": M_n / 1e6,
        "phiM_n_kNm": phiM_n / 1e6,
        "a_mm": a,
        "c_mm": c,
        "beta_1": beta_1,
        "epsilon_t": epsilon_t,
        "phi": phi,
        "A_s_mm2": A_s,
    }


def compute_aci_shear(b, d, f_c, A_v=0.0, s=0.0, f_yw=0.0,
                      A_s=None, V_u=None, M_u=None):
    """
    Compute ACI 318-14 shear capacity for a rectangular beam.
    
    Uses the DETAILED V_c equation (ACI 318-14 Eq. 22.5.5.1) when A_s, V_u,
    and M_u are provided, matching the method used by SPBeam and other
    commercial software. Falls back to the simplified equation if these
    parameters are omitted.
    
    Detailed:  V_c = [0.16·λ·√f'c + 17·ρ_w·(V_u·d/M_u)]·b_w·d ≤ 0.29·λ·√f'c·b_w·d
    Simplified: V_c = 0.17·λ·√f'c · b_w · d
    
    Parameters
    ----------
    b : float — beam width or web width (mm)
    d : float — effective depth (mm)
    f_c : float — concrete compressive strength (MPa)
    A_v : float — total stirrup area (mm²), usually 2 × area of one leg
    s : float — stirrup spacing (mm)
    f_yw : float — stirrup yield strength (MPa)
    A_s : float, optional — longitudinal tension steel area (mm²)
    V_u : float, optional — factored shear at critical section (kN)
    M_u : float, optional — factored moment at critical section (kN-m)
    
    Returns
    -------
    dict
        V_c_kN : float — concrete contribution (kN)
        V_s_kN : float — steel contribution (kN)
        V_n_kN : float — nominal shear capacity (kN)
        phiV_n_kN : float — design shear capacity (kN)
        phi_v : float — shear reduction factor (0.75)
    """
    lambda_factor = 1.0  # normal weight concrete
    phi_v = 0.75
    
    # Concrete shear strength — detailed equation if A_s/V_u/M_u are provided
    if A_s is not None and V_u is not None and M_u is not None and M_u > 0:
        # ACI 318-14 Eq. 22.5.5.1 (detailed)
        rho_w = A_s / (b * d)
        # V_u * d / M_u ratio, limited to ≤ 1.0 per ACI
        vu_d_over_mu = min(abs(V_u) * d / (abs(M_u) * 1000), 1.0)
        # Detailed V_c
        V_c = (0.16 * lambda_factor * np.sqrt(f_c) + 17 * rho_w * vu_d_over_mu) * b * d / 1000
        # Upper bound per ACI 318-14 §22.5.5.1
        V_c_max = 0.29 * lambda_factor * np.sqrt(f_c) * b * d / 1000
        V_c = min(V_c, V_c_max)
    else:
        # ACI 318-14 Eq. 22.5.5.1 (simplified)
        V_c = 0.17 * lambda_factor * np.sqrt(f_c) * b * d / 1000  # kN
    
    # Steel shear contribution
    if A_v > 0 and s > 0 and f_yw > 0:
        V_s = A_v * f_yw * d / s / 1000  # kN (ACI 318-14 Eq. 22.5.8.5.3)
    else:
        V_s = 0.0
    
    V_n = V_c + V_s  # kN
    phiV_n = phi_v * V_n  # kN
    
    return {
        "V_c_kN": V_c,
        "V_s_kN": V_s,
        "V_n_kN": V_n,
        "phiV_n_kN": phiV_n,
        "phi_v": phi_v,
    }


# ============================================================================
#  DESIGN FUNCTION
# ============================================================================

def design_beam(name, b, h, p, dl, dt, f_c, f_yl, f_yt, M_ue, V_ue,
                L_span=6.0, w_service=25.0,
                A_s_provided=None, A_sp_provided=None,
                M_ue_critical=None, V_ue_critical=None):
    """
    Design a single RC beam for flexure and shear per ACI 318-14.

    Parameters
    ----------
    A_s_provided : float, optional
        Override tension steel area (mm2). If provided, the script will
        compute the actual moment capacity from this steel area instead
        of calculating the required steel from the design moment.
    A_sp_provided : float, optional
        Override compression steel area (mm2). Used together with
        A_s_provided for capacity-check mode.

    Returns a dict with all computed results.
    """
    # -----------------------------------------------------------------------
    #  Material properties
    # -----------------------------------------------------------------------
    epsilon_y = f_yl / 2e5
    epsilon_s = 0.005  # tension-controlled strain

    # Stress block factor (ACI 318-14 Section 22.2.2.4.3)
    if f_c >= 55:
        beta_1 = 0.65
    elif f_c > 28:
        beta_1 = round(0.85 - 0.05 * (f_c - 28) / 7, 2)
    else:
        beta_1 = 0.85

    phi_flexure = _strength_reduction_factor(epsilon_s, epsilon_y)

    # -----------------------------------------------------------------------
    #  Effective depths
    # -----------------------------------------------------------------------
    d = h - (p + dt + dl / 2)
    d_prime = p + dt + dl / 2

    # -----------------------------------------------------------------------
    #  Reinforcement limits
    # -----------------------------------------------------------------------
    A_smin1 = 0.25 * np.sqrt(f_c) / f_yl * b * d
    A_smin2 = 1.4 / f_yl * b * d
    A_smin = max(A_smin1, A_smin2)

    A_sbal = 0.85 * f_c * beta_1 * (EPSILON_CU / (EPSILON_CU + epsilon_y)) * d
    A_smax = 0.75 * A_sbal

    # -----------------------------------------------------------------------
    #  Flexural design
    # -----------------------------------------------------------------------
    steel_overridden = A_s_provided is not None

    if steel_overridden:
        # ---------------------------------------------------------------
        #  CAPACITY CHECK MODE — user provided the steel area
        #  Compute actual moment capacity from the given reinforcement.
        # ---------------------------------------------------------------
        A_s = A_s_provided
        A_sp = A_sp_provided if A_sp_provided is not None else 0.0

        # Number of bars (for plotting)
        n = max(1, int(round(A_s / (dl**2 * np.pi / 4))))
        n_prime = max(0, int(round(A_sp / (dl**2 * np.pi / 4)))) if A_sp > 0 else 0
        if n_prime < 2 and A_sp > 0:
            n_prime = 2  # minimum 2 compression bars for stability

        # Solve for neutral axis depth (c) from strain compatibility
        # T = C_c + C_s  =>  A_s * f_y = 0.85 * f_c * b * beta_1 * c + A_s' * f_s'
        # Iterate or solve directly assuming f_s' = f_y (compression yields)
        # First, assume compression steel yields
        a_trial = A_s * f_yl / (0.85 * f_c * b)
        c_trial = a_trial / beta_1

        # Check if compression steel actually yields
        epsilon_s_prime = EPSILON_CU * (c_trial - d_prime) / c_trial
        if epsilon_s_prime >= epsilon_y and A_sp > 0:
            # Both tension and compression steel yield
            a = A_s * f_yl / (0.85 * f_c * b)
            c = a / beta_1
            Cc = 0.85 * f_c * b * a
            Cs = A_sp * (f_yl - 0.85 * f_c)
            M_n = Cc * (d - a / 2) + Cs * (d - d_prime)
        elif A_sp > 0:
            # Compression steel does NOT yield — solve quadratic for c
            # Cc = 0.85*f_c*b*beta_1*c
            # Cs = A_sp * (Es * eps_cu * (c - d')/c - 0.85*f_c)
            # T = A_s * f_y
            # T = Cc + Cs
            # => A_s*f_y = 0.85*f_c*b*beta_1*c + A_sp*(Es*eps_cu*(c-d')/c - 0.85*f_c)
            # Multiply both sides by c:
            # (A_s*f_y)*c = 0.85*f_c*b*beta_1*c^2 + A_sp*Es*eps_cu*(c-d') - 0.85*f_c*A_sp*c
            # => 0 = 0.85*f_c*b*beta_1*c^2 + (A_sp*Es*eps_cu - 0.85*f_c*A_sp - A_s*f_y)*c - A_sp*Es*eps_cu*d'
            Es = 2e5
            A = 0.85 * f_c * b * beta_1
            B = A_sp * Es * EPSILON_CU - 0.85 * f_c * A_sp - A_s * f_yl
            C = -A_sp * Es * EPSILON_CU * d_prime
            disc = B**2 - 4 * A * C
            if disc >= 0:
                c = (-B + np.sqrt(disc)) / (2 * A)
            else:
                c = c_trial  # fallback
            a = beta_1 * c
            epsilon_s_prime = EPSILON_CU * (c - d_prime) / c
            f_s_prime = min(Es * epsilon_s_prime, f_yl)
            Cc = 0.85 * f_c * b * a
            Cs = A_sp * (f_s_prime - 0.85 * f_c)
            M_n = Cc * (d - a / 2) + Cs * (d - d_prime)
        else:
            # No compression steel — singly reinforced
            a = A_s * f_yl / (0.85 * f_c * b)
            c = a / beta_1
            Cc = 0.85 * f_c * b * a
            M_n = Cc * (d - a / 2)

        fM_n = 0.9 * M_n
        DCR = M_ue / (fM_n / 1e6) if fM_n > 0 else 0.0

    else:
        # ---------------------------------------------------------------
        #  DESIGN MODE — calculate required steel from design moment
        # ---------------------------------------------------------------
        M_u_Nmm = M_ue * 1e6  # convert kN-m to N-mm

        # Solve quadratic for stress block depth 'a' from M_u / φ:
        #   M_u / φ = 0.85 * f_c * b * a * (d - a/2)
        #   (0.85*f_c*b/2)*a² - (0.85*f_c*b*d)*a + M_u/φ = 0
        A_coeff = 0.85 * f_c * b / 2
        B_coeff = -0.85 * f_c * b * d
        C_coeff = M_u_Nmm / phi_flexure

        disc = B_coeff**2 - 4 * A_coeff * C_coeff
        if disc >= 0:
            # Smaller root (valid stress block)
            a = (-B_coeff - np.sqrt(disc)) / (2 * A_coeff)
        else:
            # Discriminant negative → demand is very small, use minimum steel
            a = 0.0

        c = a / beta_1 if a > 0 else 0.0
        epsilon_t = EPSILON_CU * (d - c) / c if c > 0 else 0.02  # large if no compression block

        # Required tension steel from force equilibrium
        if a > 0:
            A_s_req = 0.85 * f_c * b * a / f_yl
        else:
            A_s_req = 0.0

        # Check if minimum reinforcement governs
        if A_s_req < A_smin or a <= 0:
            # Minimum steel controls
            bar_area = dl**2 * np.pi / 4
            n = max(2, int(np.ceil(A_smin / bar_area)))
            A_s = n * bar_area
            A_sp = 0.0  # no compression steel needed for min reinforcement

            # Recompute actual a, c from provided A_s
            a = A_s * f_yl / (0.85 * f_c * b)
            c = a / beta_1
            Cc = 0.85 * f_c * b * a
            M_n = Cc * (d - a / 2)
            epsilon_t = EPSILON_CU * (d - c) / c
            fM_n = M_n * _strength_reduction_factor(epsilon_t, epsilon_y)

            # Minimum 2 compression bars for stirrup stability
            bar_area = dl**2 * np.pi / 4
            n_prime = max(2, int(np.ceil(A_smin / bar_area)))
            A_sp = n_prime * bar_area

        elif a / beta_1 <= 0.375 * d:
            # Singly reinforced, tension-controlled (c/d ≤ 0.375 → ε_t ≥ 0.005)
            bar_area = dl**2 * np.pi / 4
            n = max(2, int(np.ceil(A_s_req / bar_area)))
            A_s = n * bar_area
            A_sp = 0.0

            # Recompute actual a, c, M_n from provided bars
            a = A_s * f_yl / (0.85 * f_c * b)
            c = a / beta_1
            Cc = 0.85 * f_c * b * a
            M_n = Cc * (d - a / 2)
            epsilon_t = EPSILON_CU * (d - c) / c
            fM_n = M_n * _strength_reduction_factor(epsilon_t, epsilon_y)

            # Minimum 2 compression bars for stirrup stability
            bar_area = dl**2 * np.pi / 4
            n_prime = max(2, int(np.ceil(A_smin / bar_area)))
            A_sp = n_prime * bar_area

        else:
            # Doubly reinforced — demand exceeds capacity of singly-reinforced max
            # Step 1: Max singly-reinforced capacity at ε_t = 0.005 (tension-controlled limit)
            c_max = 0.375 * d
            a_max = c_max * beta_1
            A_s_max_provided = 0.85 * f_c * b * a_max / f_yl
            M_n_max = 0.85 * f_c * b * a_max * (d - a_max / 2)

            # Step 2: Deficit to carry with compression steel
            M_u_deficit = M_u_Nmm / phi_flexure - M_n_max

            if M_u_deficit > 0:
                # Compression steel required
                Es = 2e5
                epsilon_s_prime = EPSILON_CU * (c_max - d_prime) / c_max
                f_s_prime = min(epsilon_s_prime * Es, f_yl)

                # Compression steel area
                A_sp_req = M_u_deficit / ((d - d_prime) * (f_s_prime - 0.85 * f_c))

                bar_area = dl**2 * np.pi / 4
                n_prime = max(2, int(np.ceil(A_sp_req / bar_area)))
                A_sp = n_prime * bar_area

                # Additional tension steel to balance compression steel
                A_s_additional = (A_sp * (f_s_prime - 0.85 * f_c)) / f_yl

                # Total tension steel = max singly-reinforced + additional for compression steel
                A_s_total_req = A_s_max_provided + A_s_additional

                bar_area = dl**2 * np.pi / 4
                n = max(2, int(np.ceil(A_s_total_req / bar_area)))
                A_s = n * bar_area

                # Recompute actual capacity from discrete bar areas
                # Solve force equilibrium for c (accounts for compression steel)
                # T = Cc + Cs  =>  A_s*f_y = 0.85*f_c*b*beta_1*c + A_sp*(Es*eps_cu*(c-d')/c - 0.85*f_c)
                A_coeff = 0.85 * f_c * b * beta_1
                B_coeff = A_sp * Es * EPSILON_CU - 0.85 * f_c * A_sp - A_s * f_yl
                C_coeff = -A_sp * Es * EPSILON_CU * d_prime
                disc = B_coeff**2 - 4 * A_coeff * C_coeff
                if disc >= 0:
                    c = (-B_coeff + np.sqrt(disc)) / (2 * A_coeff)
                else:
                    c = c_max  # fallback
                a = beta_1 * c
                Cc = 0.85 * f_c * b * a
                epsilon_s_prime = EPSILON_CU * (c - d_prime) / c
                f_s_prime = min(Es * epsilon_s_prime, f_yl)
                Cs = A_sp * (f_s_prime - 0.85 * f_c)
                M_n = Cc * (d - a / 2) + Cs * (d - d_prime)
                epsilon_t = EPSILON_CU * (d - c) / c
                fM_n = M_n * _strength_reduction_factor(epsilon_t, epsilon_y)
            else:
                # Demand is small enough to be singly reinforced with max steel
                bar_area = dl**2 * np.pi / 4
                n = max(2, int(np.ceil(A_s_req / bar_area)))
                A_s = n * bar_area
                A_sp = 0.0

                a = A_s * f_yl / (0.85 * f_c * b)
                c = a / beta_1
                Cc = 0.85 * f_c * b * a
                M_n = Cc * (d - a / 2)
                epsilon_t = EPSILON_CU * (d - c) / c
                fM_n = M_n * _strength_reduction_factor(epsilon_t, epsilon_y)

                # Minimum 2 compression bars for stirrup stability
                bar_area = dl**2 * np.pi / 4
                n_prime = max(2, int(np.ceil(A_smin / bar_area)))
                A_sp = n_prime * bar_area

        # Moment DCR
        DCR = M_ue / (fM_n / 1e6) if fM_n > 0 else 0.0

    # -----------------------------------------------------------------------
    #  Shear capacity (ACI 318-14 Section 22.5)
    # -----------------------------------------------------------------------
    lambda_factor = 1.0  # normal weight concrete
    phi_v = 0.75
    
    # Use detailed V_c equation when critical section loads are available
    if M_ue_critical is not None and V_ue_critical is not None and M_ue_critical > 0:
        # ACI 318-14 Eq. 22.5.5.1 (detailed) — matches SPBeam
        rho_w = A_s / (b * d)
        vu_d_over_mu = min(abs(V_ue_critical) * d / (abs(M_ue_critical) * 1000), 1.0)
        V_c = (0.16 * lambda_factor * np.sqrt(f_c) + 17 * rho_w * vu_d_over_mu) * b * d / 1000
        V_c_max = 0.29 * lambda_factor * np.sqrt(f_c) * b * d / 1000
        V_c = min(V_c, V_c_max)
    else:
        # Simplified equation — fallback when critical section data unavailable
        V_c = 0.17 * lambda_factor * np.sqrt(f_c) * b * d / 1000  # kN
    
    phi_V_c = phi_v * V_c

    shear_reinforcement_required = V_ue > 0.5 * phi_V_c

    A_v = 2 * (np.pi * dt**2 / 4)  # mm², 2-leg stirrup area

    # Min reinforcement spacing (ACI 318-14 Section 9.6.3.4)
    s_min_reinf = (A_v * f_yt) / (0.062 * np.sqrt(f_c) * b)
    s_min_reinf = min(s_min_reinf, (A_v * f_yt) / (0.35 * b))


    if V_ue > phi_V_c:
        V_s_req = (V_ue / phi_v) - V_c
        s_req = (A_v * f_yt * d / 1000) / V_s_req if V_s_req > 0 else s_min_reinf
    else:
        V_s_req = 0
        s_req = s_min_reinf

    # Max spacing (ACI 318-14 Section 9.7.6.2.2)
    if V_s_req > 0.33 * np.sqrt(f_c) * b * d / 1000:
        s_max = min(d / 4, 150)
    else:
        s_max = min(d / 2, 600)

    if shear_reinforcement_required:
        s_final = min(s_req, s_max, s_min_reinf)/50 * 50
        s_final = max(1, np.floor(s_final / 10) * 10)/50 * 50
    else:
        s_final = round(s_max/50) * 50

    V_s_actual = (A_v * f_yt * d / 1000) / s_final if (shear_reinforcement_required and s_final > 0) else 0
    phi_V_n = phi_v * (V_c + V_s_actual)
    V_DCR = V_ue / phi_V_n if phi_V_n > 0 else 0

    # -----------------------------------------------------------------------
    #  Bar spacing & layering (ACI 318-14 Section 25.2.1)
    # -----------------------------------------------------------------------
    xx_dis = (b - 2 * p - dt * 2 - dl) / (n - 1) if n > 1 else 0
    layering_required = xx_dis < MINIMUM_SPACING if n > 1 else False

    if layering_required and n > 1:
        # Redistribute bars into two layers and recalculate effective depth
        n1 = max(2, int(np.ceil(n / 2)))  # bottom layer (at least 2 bars)
        n2 = n - n1                       # top layer
        d1 = d                            # bottom layer at original effective depth
        d2 = d - dl - MINIMUM_SPACING     # top layer above + clear spacing
        d_eff = (n1 * d1 + n2 * d2) / n   # centroid of both layers

        # Check spacing per layer
        xx_dis1 = (b - 2 * p - dt * 2 - dl) / (n1 - 1) if n1 > 1 else 0
        xx_dis2 = (b - 2 * p - dt * 2 - dl) / (n2 - 1) if n2 > 1 else 0

        print(f"\n  ⚠ WARNING: Bar clear spacing = {xx_dis:.1f} mm < {MINIMUM_SPACING} mm minimum!")
        print(f"    Section: {b:.0f} mm x {h:.0f} mm with {int(n)} bars O{dl:.0f} mm.")
        print(f"    → Redistributed into {n1} + {n2} layers (new d = {d_eff:.1f} mm).")
        if xx_dis1 < MINIMUM_SPACING or xx_dis2 < MINIMUM_SPACING:
            print(f"    → ❌ Per-layer spacing still < {MINIMUM_SPACING} mm!")
            print(f"       Layer 1 ({n1} bars): {xx_dis1:.1f} mm | Layer 2 ({n2} bars): {xx_dis2:.1f} mm")
            print(f"       Section too narrow for {n} bars O{dl:.0f}. Increase beam width or use smaller bars.\n")
        else:
            print(f"    → ✅ Per-layer spacing: {xx_dis1:.1f} mm and {xx_dis2:.1f} mm (OK).\n")

        # Recompute moment capacity with corrected d
        d = d_eff
        a = A_s * f_yl / (0.85 * f_c * b)
        c = a / beta_1
        Cc = 0.85 * f_c * b * a

        if A_sp > 0 and not steel_overridden:
            # Doubly reinforced — recompute with new d
            Es = 2e5
            epsilon_s_prime = EPSILON_CU * (c - d_prime) / c
            f_s_prime = min(Es * epsilon_s_prime, f_yl)
            Cs = A_sp * (f_s_prime - 0.85 * f_c)
            M_n = Cc * (d - a / 2) + Cs * (d - d_prime)
        else:
            # Singly reinforced (or capacity check mode)
            M_n = Cc * (d - a / 2)

        epsilon_t = EPSILON_CU * (d - c) / c
        fM_n = M_n * _strength_reduction_factor(epsilon_t, epsilon_y)
        DCR = M_ue / (fM_n / 1e6) if fM_n > 0 else 0.0

    # -----------------------------------------------------------------------
    #  Deflection check (ACI 318-14 Section 24.2)
    # -----------------------------------------------------------------------
    # Material properties for deflection
    Ec = 4700 * np.sqrt(f_c)  # concrete modulus of elasticity (MPa)
    Es = 2e5                  # steel modulus (MPa)
    n_mod = Es / Ec           # modular ratio

    # Gross section properties
    Ig = b * h**3 / 12        # gross moment of inertia (mm4)
    yt = h / 2                # distance from centroid to tension face (mm)
    fr = 0.62 * np.sqrt(f_c)  # modulus of rupture (MPa)

    # Cracking moment
    Mcr = fr * Ig / yt / 1e6  # kN-m

    # Service moment (simply supported, uniform load)
    M_service = w_service * L_span**2 / 8  # kN-m

    # Cracked section analysis — neutral axis depth (k*d)
    # For a rectangular beam with tension steel only:
    rho = A_s / (b * d)
    k = np.sqrt(2 * rho * n_mod + (rho * n_mod)**2) - rho * n_mod
    kd = k * d  # depth to neutral axis (mm)

    # Cracked moment of inertia (transformed section)
    Icr = b * kd**3 / 3 + n_mod * A_s * (d - kd)**2  # mm4

    # Effective moment of inertia (Branson's formula, ACI Eq. 24.2.3.5a)
    if M_service > Mcr:
        Ie = (Mcr / M_service)**3 * Ig + (1 - (Mcr / M_service)**3) * Icr
    else:
        Ie = Ig

    # Immediate deflection (simply supported, uniform load)
    # delta_immediate = 5 * w * L^4 / (384 * E * I)
    L_mm = L_span * 1000  # span in mm
    w_N_per_mm = w_service * 1000 / 1000  # N/mm (kN/m -> N/mm)
    delta_immediate = 5 * w_N_per_mm * L_mm**4 / (384 * Ec * Ie)  # mm

    # Long-term deflection (creep + shrinkage, ACI 24.2.4)
    # Time-dependent factor lambda_delta
    # For 5+ years sustained load, xi = 2.0
    xi = 2.0
    # Compression reinforcement reduces creep
    if A_sp > 0:
        rho_comp = A_sp / (b * d)
    else:
        rho_comp = 0.0
    lambda_delta = xi / (1 + 50 * rho_comp)

    delta_long_term = lambda_delta * delta_immediate  # mm
    delta_total = delta_immediate + delta_long_term  # mm

    # Allowable deflection (ACI Table 24.2.2)
    # Roof/floor with no partitions: L/180
    # Floor with partitions: L/360
    # For general use, use L/240
    L_allowable = L_mm / 240  # mm
    deflection_adequate = delta_total <= L_allowable

    # -----------------------------------------------------------------------
    #  Return all results
    # -----------------------------------------------------------------------
    return {
        "name": name,
        "b": b, "h": h, "p": p, "dl": dl, "dt": dt,
        "f_c": f_c, "f_yl": f_yl, "f_yt": f_yt,
        "M_ue": M_ue, "V_ue": V_ue,
        "L_span": L_span, "w_service": w_service,
        "beta_1": beta_1,
        "d": d, "d_prime": d_prime,
        "A_smin": A_smin, "A_smax": A_smax,
        "A_s": A_s, "A_sp": A_sp,
        "n": n, "n_prime": n_prime,
        "Cc": Cc, "c": c, "a": a,
        "M_n": M_n, "fM_n": fM_n, "DCR": DCR,
        "V_c": V_c, "phi_V_c": phi_V_c,
        "shear_reinforcement_required": shear_reinforcement_required,
        "A_v": A_v, "V_s_req": V_s_req, "s_req": s_req,
        "s_max": s_max, "s_final": s_final,
        "V_s_actual": V_s_actual, "phi_V_n": phi_V_n, "V_DCR": V_DCR,
        "layering_required": layering_required,
        "xx_dis": xx_dis,
        "xx_dis1": xx_dis1 if layering_required else None, 
        "xx_dis2": xx_dis2 if layering_required else None,
        "epsilon_y": epsilon_y,
        "epsilon_s": epsilon_s,
        "lambda_factor": lambda_factor,
        "phi_v": phi_v,
        # Deflection results
        "Ec": Ec, "n_mod": n_mod,
        "Ig": Ig, "Icr": Icr, "Ie": Ie,
        "Mcr": Mcr, "M_service": M_service,
        "fr": fr, "k": k, "kd": kd,
        "delta_immediate": delta_immediate,
        "delta_long_term": delta_long_term,
        "delta_total": delta_total,
        "L_allowable": L_allowable,
        "deflection_adequate": deflection_adequate,
        "lambda_delta": lambda_delta,
        "rho": rho, "rho_comp": rho_comp,
        "phi_flexure": phi_flexure,
    }


# ============================================================================
#  OUTPUT FUNCTIONS
# ============================================================================

def save_equations(r, output_dir):
    """Save design equations to a text file."""
    txt_path = os.path.join(output_dir, f"{r['name']}_equations.txt")
    lines = []
    lines.append("=" * 52)
    lines.append(f"  {r['name']} — DESIGN EQUATIONS & RESULTS")
    lines.append("=" * 52)

    lines.append("")
    lines.append("  1. beta_1 (Stress block factor)")
    if r['f_c'] >= 55:
        lines.append(f"     f_c' >= 55 -> beta_1 = 0.65")
    elif r['f_c'] > 28:
        lines.append(f"     28 < f_c' < 55 -> beta_1 = 0.85 - 0.05*(f_c'-28)/7")
        lines.append(f"     beta_1 = 0.85 - 0.05*({r['f_c']:.1f}-28)/7 = {r['beta_1']:.3f}")
    else:
        lines.append(f"     f_c' <= 28 -> beta_1 = 0.85")

    lines.append("")
    lines.append("  2. A_s,min (Minimum reinforcement)")
    lines.append(f"     A_s,min1 = 0.25*sqrt(f_c')/f_y * b * d")
    A_smin1 = 0.25 * np.sqrt(r['f_c']) / r['f_yl'] * r['b'] * r['d']
    A_smin2 = 1.4 / r['f_yl'] * r['b'] * r['d']
    lines.append(f"              = 0.25*sqrt({r['f_c']:.1f})/{r['f_yl']:.1f} * {r['b']:.1f} * {r['d']:.2f} = {A_smin1:.3f} mm2")
    lines.append(f"     A_s,min2 = 1.4/f_y * b * d")
    lines.append(f"              = 1.4/{r['f_yl']:.1f} * {r['b']:.1f} * {r['d']:.2f} = {A_smin2:.3f} mm2")
    lines.append(f"     A_s,min  = max({A_smin1:.3f}, {A_smin2:.3f}) = {r['A_smin']:.3f} mm2")

    lines.append("")
    lines.append("  3. A_s,max (Maximum reinforcement)")
    lines.append(f"     A_s,bal = 0.85*f_c'*beta_1*(eps_cu/(eps_cu+eps_y))*d")
    lines.append(f"             = 0.85*{r['f_c']:.1f}*{r['beta_1']:.3f}*(0.003/(0.003+{r['epsilon_y']:.5f}))*{r['d']:.2f}")
    A_sbal = 0.85 * r['f_c'] * r['beta_1'] * (0.003 / (0.003 + r['epsilon_y'])) * r['d']
    lines.append(f"             = {A_sbal:.3f} mm2")
    lines.append(f"     A_s,max = 0.75*A_s,bal = 0.75*{A_sbal:.3f} = {r['A_smax']:.3f} mm2")

    lines.append("")
    lines.append("  4. Effective depths")
    lines.append(f"     d   = h - p - dt - dl/2 = {r['h']:.1f} - {r['p']:.1f} - {r['dt']:.1f} - {r['dl']:.1f}/2 = {r['d']:.2f} mm")
    lines.append(f"     d'  = p + dt + dl/2 = {r['p']:.1f} + {r['dt']:.1f} + {r['dl']:.1f}/2 = {r['d_prime']:.2f} mm")

    lines.append("")
    lines.append("  5. Neutral axis & stress block")
    lines.append(f"     a   = solved from M_u/phi = 0.85*f_c'*b*a*(d-a/2)")
    lines.append(f"     a   = {r['a']:.2f} mm")
    lines.append(f"     c   = a/beta_1 = {r['a']:.2f}/{r['beta_1']:.3f} = {r['c']:.2f} mm")

    lines.append("")
    lines.append("  6. Concrete compression force")
    lines.append(f"     C_c = 0.85*f_c'*b*a = 0.85*{r['f_c']:.1f}*{r['b']:.1f}*{r['a']:.2f} = {r['Cc']:.2f} N")

    lines.append("")
    lines.append("  7. Required tension reinforcement")
    lines.append(f"     A_s = C_c / f_y = {r['Cc']:.2f} / {r['f_yl']:.1f} = {r['A_s']:.3f} mm2")

    lines.append("")
    lines.append("  8. Nominal & design moment")
    lines.append(f"     M_n   = C_c*(d - a/2) = {r['Cc']:.2f}*({r['d']:.2f} - {r['a']:.2f}/2) = {r['M_n']:.2f} N-mm")
    lines.append(f"     phiM_n  = phi*M_n = {r['phi_flexure']:.2f}*{r['M_n']:.2f} = {r['fM_n']:.2f} N-mm")
    lines.append(f"            = {r['fM_n']/1e6:.3f} kN-m")

    lines.append("")
    lines.append("  9. Demand-Capacity Ratio (DCR)")
    lines.append(f"     DCR  = M_u / phiM_n = {r['M_ue']:.2f} / {r['fM_n']/1e6:.3f} = {r['DCR']:.3f}")
    lines.append(f"     -> DCR <= 1.0, section is {'ADEQUATE' if r['DCR'] <= 1.0 else 'INADEQUATE'}")

    lines.append("")
    lines.append("  SHEAR CAPACITY (ACI 318-14)")
    lines.append("-" * 52)
    lines.append(f"  Applied shear force, V_u          = {r['V_ue']:.2f} kN")
    lines.append(f"  Concrete shear strength, V_c")
    lines.append(f"    V_c = 0.17*lambda*sqrt(f_c')*b_w*d")
    lines.append(f"        = 0.17*{r['lambda_factor']:.1f}*sqrt({r['f_c']:.1f})*{r['b']:.1f}*{r['d']:.2f} / 1000")
    lines.append(f"        = {r['V_c']:.3f} kN")
    lines.append(f"  phiV_c = {r['phi_v']:.2f}*{r['V_c']:.3f} = {r['phi_V_c']:.3f} kN")
    lines.append(f"  0.5*phiV_c = {0.5*r['phi_V_c']:.3f} kN")
    lines.append(f"  Shear reinforcement required?     {'Yes' if r['shear_reinforcement_required'] else 'No'}")
    if r['shear_reinforcement_required']:
        lines.append(f"")
        lines.append(f"  Stirrup area (2-leg O{r['dt']:.0f}mm), A_v = 2*(pi*{r['dt']:.1f}2/4) = {r['A_v']:.2f} mm2")
        lines.append(f"  Required V_s = V_u/phi - V_c = {r['V_ue']:.2f}/{r['phi_v']:.2f} - {r['V_c']:.3f} = {r['V_s_req']:.3f} kN")
        if np.isfinite(r['s_req']):
            lines.append(f"  Required spacing, s_req = A_v*f_yt*d / V_s")
            lines.append(f"                         = {r['A_v']:.2f}*{r['f_yt']:.1f}*{r['d']:.2f} / {r['V_s_req']:.3f} / 1000")
            lines.append(f"                         = {r['s_req']:.1f} mm")
        lines.append(f"  Max spacing (ACI 9.7.6.2.2), s_max = {r['s_max']:.1f} mm")
        lines.append(f"  Final spacing, s = {r['s_final']:.0f} mm")
        lines.append(f"  Actual V_s = A_v*f_yt*d / s = {r['A_v']:.2f}*{r['f_yt']:.1f}*{r['d']:.2f}/{r['s_final']:.0f}/1000 = {r['V_s_actual']:.3f} kN")
    lines.append(f"  Design shear strength, phiV_n")
    lines.append(f"    phiV_n = phi*(V_c + V_s) = {r['phi_v']:.2f}*({r['V_c']:.3f} + {r['V_s_actual']:.3f}) = {r['phi_V_n']:.3f} kN")
    lines.append(f"  Shear DCR = V_u / phiV_n = {r['V_ue']:.2f} / {r['phi_V_n']:.3f} = {r['V_DCR']:.3f}")
    lines.append(f"  -> Shear DCR <= 1.0, shear capacity is {'ADEQUATE' if r['V_DCR'] <= 1.0 else 'INADEQUATE'}")

    lines.append("")
    lines.append("  DEFLECTION CHECK (ACI 318-14 Section 24.2)")
    lines.append("-" * 52)
    lines.append(f"  Span length, L                     = {r['L_span']:.2f} m")
    lines.append(f"  Service load, w                    = {r['w_service']:.2f} kN/m")
    lines.append(f"  Service moment, M_service          = {r['M_service']:.3f} kN-m")
    lines.append(f"  Concrete modulus, Ec               = {r['Ec']:.0f} MPa")
    lines.append(f"  Modular ratio, n = Es/Ec           = {r['n_mod']:.2f}")
    lines.append(f"")
    lines.append(f"  Gross moment of inertia, Ig        = {r['Ig']:.1f} mm4")
    lines.append(f"  Modulus of rupture, fr             = {r['fr']:.3f} MPa")
    lines.append(f"  Cracking moment, Mcr               = {r['Mcr']:.3f} kN-m")
    lines.append(f"  Reinforcement ratio, rho           = {r['rho']:.4f}")
    lines.append(f"  Neutral axis factor, k             = {r['k']:.4f}")
    lines.append(f"  Neutral axis depth, kd             = {r['kd']:.2f} mm")
    lines.append(f"  Cracked moment of inertia, Icr     = {r['Icr']:.1f} mm4")
    lines.append(f"  Effective moment of inertia, Ie    = {r['Ie']:.1f} mm4")
    lines.append(f"")
    lines.append(f"  Immediate deflection, delta_i      = {r['delta_immediate']:.2f} mm")
    lines.append(f"  Long-term factor, lambda_delta     = {r['lambda_delta']:.3f}")
    lines.append(f"  Long-term deflection, delta_lt     = {r['delta_long_term']:.2f} mm")
    lines.append(f"  Total deflection, delta_total      = {r['delta_total']:.2f} mm")
    lines.append(f"  Allowable deflection (L/240)       = {r['L_allowable']:.2f} mm")
    lines.append(f"  -> Deflection {'ADEQUATE' if r['deflection_adequate'] else 'INADEQUATE'} (delta_total={r['delta_total']:.2f} mm <= {r['L_allowable']:.2f} mm)")

    lines.append("")
    lines.append("=" * 52)

    with open(txt_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  [V] Equations saved -> {txt_path}")


def save_plot(r, output_dir):
    """Save beam cross-section plot."""
    plot_path = os.path.join(output_dir, f"{r['name']}_section.png")
    b, h, p, dl, dt = r['b'], r['h'], r['p'], r['dl'], r['dt']
    n, n_prime = r['n'], r['n_prime']
    d, d_prime = r['d'], r['d_prime']
    layering = r['layering_required']
    xx_dis = r['xx_dis']

    # Compression bars
    compression_bars = np.linspace((p + dt + dl / 2), (b - (p + dt + dl / 2)), int(n_prime)).tolist()
    yy_compression = np.repeat((h - d_prime), int(n_prime))

    first_bar_position = p + dt + dl / 2
    last_bar_position = b - (p + dt + dl / 2)

    fig, ax = plt.subplots(figsize=(3, 3))
    ax.set_xticks([])
    ax.set_yticks([])
    ax.plot([0, b, b, 0, 0], [0, 0, h, h, 0])
    ax.scatter(compression_bars, yy_compression, label="Compression bar")

    if layering:
        num_bars_layer1 = int(np.ceil(n / 2) - 1)
        num_bars_layer2 = int(n - num_bars_layer1)
        xx1 = np.linspace(first_bar_position, last_bar_position, num_bars_layer1)
        xx2 = np.linspace(first_bar_position, last_bar_position, num_bars_layer2) if num_bars_layer2 > 0 else []
        yy1 = np.repeat((h - d + dl + 25), len(xx1)) if len(xx1) > 0 else []
        yy2 = np.repeat((h - d), len(xx2)) if len(xx2) > 0 else []
        ax.scatter(xx1, yy1, label="Tension bar Layer 2")
        ax.scatter(xx2, yy2, label="Tension bar Layer 1")
    else:
        xx = np.linspace(first_bar_position, last_bar_position, int(n))
        yy = np.repeat((h - d), int(n))
        ax.scatter(xx, yy, label="Tension bar")

    ax.set_xlim(-100, b + 50)
    ax.set_ylim(-100, h + 50)
    ax.legend(loc='lower left', fontsize=5, markerscale=0.5)
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [V] Plot saved -> {plot_path}")


def print_summary(r):
    """Print a concise design summary to console."""
    print(f"\n  {'=' * 52}")
    print(f"  {r['name']} — FINAL DESIGN CHOICE")
    print(f"  {'=' * 52}")
    print(f"  Beam section          : {r['b']:.0f} mm x {r['h']:.0f} mm")
    print(f"  Concrete strength     : f_c' = {r['f_c']:.1f} MPa")
    print(f"  Longitudinal steel    : f_yl = {r['f_yl']:.1f} MPa")
    print(f"  Transversal steel     : f_yt = {r['f_yt']:.1f} MPa")
    print(f"")
    print(f"  FLEXURAL REINFORCEMENT")
    print(f"  ------------------------------")
    print(f"  Tension bars          : {int(r['n'])} O{r['dl']:.0f} mm  (A_s = {r['A_s']:.1f} mm2)")
    print(f"  Compression bars      : {int(r['n_prime'])} O{r['dl']:.0f} mm  (A_s' = {r['A_sp']:.1f} mm2)")
    print(f"  Effective depth, d    : {r['d']:.1f} mm")
    print(f"  Nominal moment, M_n   : {r['M_n']/1e6:.3f} kN-m")
    print(f"  Design moment, phiM_n : {r['fM_n']/1e6:.3f} kN-m")
    print(f"  Moment DCR            : {r['DCR']:.3f}  {'ADEQUATE' if r['DCR'] <= 1.0 else 'INADEQUATE'}")
    print(f"")
    print(f"  SHEAR REINFORCEMENT")
    print(f"  ------------------------------")
    print(f"  Stirrup legs          : 2-leg O{r['dt']:.0f} mm")
    print(f"  Stirrup spacing, s    : {r['s_final']:.0f} mm")
    print(f"  Concrete shear, V_c   : {r['V_c']:.3f} kN")
    print(f"  Steel shear, V_s      : {r['V_s_actual']:.3f} kN")
    print(f"  Design shear, phiV_n  : {r['phi_V_n']:.3f} kN")
    print(f"  Shear DCR             : {r['V_DCR']:.3f}  {'ADEQUATE' if r['V_DCR'] <= 1.0 else 'INADEQUATE'}")
    print(f"")
    print(f"  DEFLECTION CHECK")
    print(f"  ------------------------------")
    print(f"  Span, L               : {r['L_span']:.2f} m")
    print(f"  Service load, w       : {r['w_service']:.2f} kN/m")
    print(f"  Ie / Ig               : {r['Ie']/r['Ig']:.3f}")
    print(f"  Immediate deflection  : {r['delta_immediate']:.2f} mm")
    print(f"  Long-term deflection  : {r['delta_long_term']:.2f} mm")
    print(f"  Total deflection      : {r['delta_total']:.2f} mm")
    print(f"  Allowable (L/240)     : {r['L_allowable']:.2f} mm")
    print(f"  Deflection            : {'ADEQUATE' if r['deflection_adequate'] else 'INADEQUATE'}")
    print(f"  {'=' * 52}")


# ============================================================================
#  MAIN — Run design for all beams
# ============================================================================

if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output", "beam_design")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  RC BEAM DESIGN — ACI 318-14")
    print(f"  Running {len(beams)} beam(s)...")
    print("=" * 60)

    for beam in beams:
        print(f"\n  >>> Designing {beam['name']} ({beam['b']:.0f}x{beam['h']:.0f} mm) ...")
        results = design_beam(**beam)
        save_equations(results, output_dir)
        save_plot(results, output_dir)
        print_summary(results)
        print(f"\n  {beam['name']} — DONE")
        print(f"  {'=' * 60}")
