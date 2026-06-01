#!/usr/bin/env python3
"""
Beam Diagram Calculator — Statics & Deflection for Common Support/Load Configurations

Computes M_u, V_u, and deflection for various beam configurations using
closed-form elastic equations (superposition for combined loading).

Support Types:
  - Simply Supported (SS)
  - Cantilever (CANT)
  - Fixed-Fixed (FF)
  - Propped Cantilever (PC)

Load Types:
  - Uniformly distributed load (UDL) — full span or partial
  - Point load (PL) — at any position
"""

import numpy as np

# ============================================================================
#  ELASTIC MODULUS CONSTANTS
# ============================================================================
# For deflection calculation without needing concrete section properties,
# we output M/EI values. The RC design module has its own Ec and Ie.

# ============================================================================
#  SINGLE-LOAD CASES — Return (M_max, V_max, x_M, x_V)
# ============================================================================

def ss_udl(L, w):
    """Simply supported, full-span UDL w (kN/m)."""
    M_max = w * L**2 / 8          # kN-m, at midspan
    V_max = w * L / 2             # kN, at supports
    x_M = L / 2
    x_V = 0
    return M_max, V_max, x_M, x_V

def ss_point(L, P, a):
    """Simply supported, point load P (kN) at distance a (m) from left support.
    b = L - a
    """
    b = L - a
    M_max = P * a * b / L         # kN-m, under the load
    V_left = P * b / L            # kN
    V_right = P * a / L           # kN
    V_max = max(V_left, V_right)
    x_M = a
    x_V = 0                       # max shear at left support if V_left > V_right
    if V_right > V_left:
        x_V = L
    return M_max, V_max, x_M, x_V

def cant_udl(L, w):
    """Cantilever, full-span UDL w (kN/m). Fixed at left (x=0)."""
    M_max = w * L**2 / 2          # kN-m, at fixed support
    V_max = w * L                 # kN, at fixed support
    x_M = 0
    x_V = 0
    return M_max, V_max, x_M, x_V

def cant_point(L, P, a):
    """Cantilever, point load P (kN) at distance a (m) from fixed support.
    Free end at x=L.
    """
    M_max = P * a                 # kN-m, at fixed support
    V_max = P                     # kN, constant along beam
    x_M = 0
    x_V = 0
    return M_max, V_max, x_M, x_V

def ff_udl(L, w):
    """Fixed-fixed, full-span UDL w (kN/m)."""
    M_end = w * L**2 / 12         # kN-m, at supports
    M_mid = w * L**2 / 24         # kN-m, at midspan
    M_max = max(abs(M_end), abs(M_mid))
    V_max = w * L / 2             # kN, at supports
    x_M = 0                       # max at support (negative)
    x_V = 0
    return M_max, V_max, x_M, x_V

def ff_point(L, P, a):
    """Fixed-fixed, point load P (kN) at distance a (m) from left support.
    b = L - a
    """
    b = L - a
    M_left = P * a * b**2 / L**2
    M_right = P * a**2 * b / L**2
    M_under = 2 * P * a**2 * b**2 / L**3
    M_max = max(abs(M_left), abs(M_right), abs(M_under))
    V_left = P * b**2 * (L + 2 * a) / L**3
    V_right = P * a**2 * (L + 2 * b) / L**3
    V_max = max(V_left, V_right)
    x_M = 0 if abs(M_left) >= abs(M_right) else L
    x_V = 0 if V_left >= V_right else L
    return M_max, V_max, x_M, x_V

def pc_udl(L, w):
    """Propped cantilever, full-span UDL w (kN/m). Fixed at left, pinned at right."""
    M_fixed = w * L**2 / 8        # kN-m, at fixed support
    M_span = w * L**2 / 14.2      # approximate positive moment
    M_max = max(abs(M_fixed), abs(M_span))
    V_fixed = 5 * w * L / 8       # kN
    V_prop = 3 * w * L / 8        # kN
    V_max = max(V_fixed, V_prop)
    x_M = 0
    x_V = 0
    return M_max, V_max, x_M, x_V


# ============================================================================
#  SHEAR & MOMENT DIAGRAM GENERATORS (for plotting)
# ============================================================================

def generate_ss_udl_diagram(L, w, n_pts=200):
    """Return (x_array, V_array, M_array) for a simply-supported UDL beam."""
    x = np.linspace(0, L, n_pts)
    V = w * (L / 2 - x)
    M = w * x * (L - x) / 2
    return x, V, M

def generate_ss_point_diagram(L, P, a, n_pts=200):
    """Return (x_array, V_array, M_array) for SS with a point load."""
    b = L - a
    x = np.linspace(0, L, n_pts)
    V = np.where(x <= a, P * b / L, -P * a / L)
    M = np.where(x <= a, P * b * x / L, P * a * (L - x) / L)
    return x, V, M

def generate_cant_udl_diagram(L, w, n_pts=200):
    """Return (x_array, V_array, M_array) for cantilever with UDL."""
    x = np.linspace(0, L, n_pts)
    V = w * (L - x)
    M = -w * (L - x)**2 / 2
    return x, V, M

def generate_cant_point_diagram(L, P, a, n_pts=200):
    """Return (x_array, V_array, M_array) for cantilever with a point load."""
    x = np.linspace(0, L, n_pts)
    V = np.where(x <= a, P, 0)
    M = np.where(x <= a, -P * (a - x), 0)
    return x, V, M

def generate_ff_udl_diagram(L, w, n_pts=200):
    """Return (x_array, V_array, M_array) for fixed-fixed with UDL."""
    x = np.linspace(0, L, n_pts)
    V = w * (L / 2 - x)
    M = w * L**2 / 12 - w * x * (L - x) / 2
    return x, V, M

def generate_ff_point_diagram(L, P, a, n_pts=200):
    """Return (x_array, V_array, M_array) for fixed-fixed with a point load."""
    b = L - a
    x = np.linspace(0, L, n_pts)
    # Reactions
    R_left = P * b**2 * (L + 2 * a) / L**3
    R_right = P * a**2 * (L + 2 * b) / L**3
    M_left = -P * a * b**2 / L**2
    M_right = -P * a**2 * b / L**2
    # Shear
    V = np.where(x <= a, R_left, -R_right)
    # Moment
    M = np.where(x <= a, M_left + R_left * x, M_left + R_left * x - P * (x - a))
    return x, V, M

def generate_pc_udl_diagram(L, w, n_pts=200):
    """Return (x_array, V_array, M_array) for propped cantilever with UDL."""
    x = np.linspace(0, L, n_pts)
    V_left = 5 * w * L / 8
    V_right = 3 * w * L / 8
    V = V_left - w * x
    M = -w * L**2 / 8 + V_left * x - w * x**2 / 2
    return x, V, M


# ============================================================================
#  COMBINATION CALCULATOR — Multiple loads, superposition
# ============================================================================

def compute_beam_diagram(support_type, L, loads):
    """
    Compute max M_u, V_u and generate diagram data for a beam with multiple loads.
    
    Parameters
    ----------
    support_type : str
        'SS' = simply supported, 'CANT' = cantilever (fixed left),
        'FF' = fixed-fixed, 'PC' = propped cantilever (fixed left, pinned right)
    L : float
        Span length (m)
    loads : list of dict
        Each dict: {'type': 'UDL' or 'PL', 'w': float (kN/m) or 'P': float (kN),
                     'a': float (position from left, m), 'span': 'full' or (start,end) for partial UDL}
    
    Returns
    -------
    dict with M_max, V_max, x_M, x_V, M_diagram, V_diagram, x_diagram
    """
    n_pts = 500
    x_fine = np.linspace(0, L, n_pts)
    M_total = np.zeros(n_pts)
    V_total = np.zeros(n_pts)
    
    M_max_candidates = [0.0]
    V_max_candidates = [0.0]
    
    for load in loads:
        if load['type'] == 'UDL':
            w = load['w']
            if support_type == 'SS':
                x, V, M = generate_ss_udl_diagram(L, w, n_pts)
                M_s, V_s, _, _ = ss_udl(L, w)
            elif support_type == 'CANT':
                x, V, M = generate_cant_udl_diagram(L, w, n_pts)
                M_s, V_s, _, _ = cant_udl(L, w)
            elif support_type == 'FF':
                x, V, M = generate_ff_udl_diagram(L, w, n_pts)
                M_s, V_s, _, _ = ff_udl(L, w)
            elif support_type == 'PC':
                x, V, M = generate_pc_udl_diagram(L, w, n_pts)
                M_s, V_s, _, _ = pc_udl(L, w)
            else:
                continue
            M_total += M
            V_total += V
            M_max_candidates.append(abs(M_s))
            V_max_candidates.append(abs(V_s))
            
        elif load['type'] == 'PL':
            P = load['P']
            a = load['a']
            if support_type == 'SS':
                x, V, M = generate_ss_point_diagram(L, P, a, n_pts)
                M_s, V_s, _, _ = ss_point(L, P, a)
            elif support_type == 'CANT':
                x, V, M = generate_cant_point_diagram(L, P, a, n_pts)
                M_s, V_s, _, _ = cant_point(L, P, a)
            elif support_type == 'FF':
                x, V, M = generate_ff_point_diagram(L, P, a, n_pts)
                M_s, V_s, _, _ = ff_point(L, P, a)
            else:
                continue
            M_total += M
            V_total += V
            M_max_candidates.append(abs(M_s))
            V_max_candidates.append(abs(V_s))
    
    M_max = np.max(np.abs(M_total))
    V_max = np.max(np.abs(V_total))
    x_M = x_fine[np.argmax(np.abs(M_total))]
    x_V = x_fine[np.argmax(np.abs(V_total))]
    
    return {
        'x': x_fine,
        'M': M_total,
        'V': V_total,
        'M_max': M_max,
        'V_max': V_max,
        'x_M': x_M,
        'x_V': x_V,
        'L': L,
        'support_type': support_type,
    }


def compute_deflection_from_diagram(support_type, L, loads, Ec, Ie):
    """
    Compute max deflection using double-integration (M/EI) method.
    
    Simplified approach: for common cases, use closed-form formulas.
    For complex loading, uses numerical integration.
    
    Returns max deflection in mm.
    """
    # For UDL-only cases, use closed-form
    udl_loads = [ld for ld in loads if ld['type'] == 'UDL']
    pl_loads = [ld for ld in loads if ld['type'] == 'PL']
    
    delta = 0.0
    L_mm = L * 1000
    
    # UDL contributions
    for ld in udl_loads:
        w = ld['w']  # kN/m
        w_Nmm = w * 1000 / 1000  # N/mm
        if support_type == 'SS':
            delta += 5 * w_Nmm * L_mm**4 / (384 * Ec * Ie)
        elif support_type == 'CANT':
            delta += w_Nmm * L_mm**4 / (8 * Ec * Ie)
        elif support_type == 'FF':
            delta += w_Nmm * L_mm**4 / (384 * Ec * Ie)
        elif support_type == 'PC':
            delta += 0.0054 * w_Nmm * L_mm**4 / (Ec * Ie)
    
    # Point load contributions
    for ld in pl_loads:
        P = ld['P'] * 1000  # kN to N
        a = ld['a'] * 1000  # m to mm
        b = L_mm - a
        if support_type == 'SS':
            # Max deflection under point load for SS
            delta += P * a * b * (L_mm**2 - a**2 - b**2) / (6 * Ec * Ie * L_mm)
            # Actually the max deflection occurs at sqrt((L²-b²)/3) if a > b
            # This is approximate; use under-load deflection
        elif support_type == 'CANT':
            delta += P * a**2 * (3 * L_mm - a) / (6 * Ec * Ie)
        elif support_type == 'FF':
            delta += P * a**2 * b**2 / (3 * Ec * Ie * L_mm)
        elif support_type == 'PC':
            # Approximate
            delta += P * a * b * (L_mm + b) / (6 * Ec * Ie) * np.sqrt(b / (2 * L_mm + 3 * b)) if b > 0 else 0
    
    return delta  # mm


# ============================================================================
#  SUPPORT TYPE LABELS
# ============================================================================

SUPPORT_INFO = {
    'SS': {
        'label': 'Simply Supported',
        'description': 'Pinned at both ends. M_max at midspan for UDL, under load for point load.',
        'default_loads': [{'type': 'UDL', 'w': 30.0}],
    },
    'CANT': {
        'label': 'Cantilever',
        'description': 'Fixed at left end, free at right. M_max at fixed support.',
        'default_loads': [{'type': 'UDL', 'w': 15.0}],
    },
    'FF': {
        'label': 'Fixed-Fixed',
        'description': 'Fixed at both ends. M_max at supports for UDL.',
        'default_loads': [{'type': 'UDL', 'w': 40.0}],
    },
    'PC': {
        'label': 'Propped Cantilever',
        'description': 'Fixed at left, pinned at right. M_max at fixed support.',
        'default_loads': [{'type': 'UDL', 'w': 30.0}],
    },
}