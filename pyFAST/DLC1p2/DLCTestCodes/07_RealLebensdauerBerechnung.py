# -*- coding: utf-8 -*-
"""
Standalone: DLC 1.2 Fatigue Life (Miner) for Tower + Blade from OpenFAST .outb results

- Reads OpenFAST output files: output_U{U}_Seed{seed}.outb
- For each run: rainflow ranges -> damage sum S = sum(n * (ΔX)^m)
- Lifetime weighting via Weibull bins: P(U_k)
- Converts Tower base moment ranges to stress ranges using tower base section (D,t)
- Computes Miner damage D over LIFE_YEARS using an S-N curve defined by FAT class (Eurocode-style)
- Estimates fatigue life (years) as LIFE_YEARS / D

Blade:
- Option A: use an equivalent moment S-N (needs ΔM_ref at N_ref)  (simple but depends on your design data)
- Option B: if you have a strain channel at blade root, use strain-life S-N directly (better).

You MUST set paths + channel names below.
"""

import os
import re
import numpy as np
import pandas as pd
from pyFAST.input_output import FASTOutputFile

# =========================
# USER SETTINGS
# =========================

# Folder with OpenFAST outputs
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(THIS_DIR, "DLC1p2_OF_results")

# Tower geometry file (ElastoDyn tower file)
TOWER_FILE = os.path.join(THIS_DIR, "_NREL5MW_FASTfiles/5MW_Baseline/NRELOffshrBsline5MW_Onshore_ElastoDyn_Tower.dat")

# Wind speeds and seeds present in RESULTS_DIR
URefs  = np.arange(3, 26, 2)      # 3,5,7,...,25 m/s
seeds  = [1, 2, 3, 4, 5, 6]

# Output channel names (adjust to match df.columns!)
TIME_CH        = "Time_[s]"
TOWER_M_CH     = "TwrBsMyt_[kN-m]"   # example: tower base bending moment
BLADE_M_CH     = "RootMyb1_[kN-m]"   # example: blade root bending moment (flapwise)
# If you have strain at blade root (better for real life), set:
BLADE_EPS_CH   = None               # e.g. "BldRootStrain1_[-]" or similar

# Cut-in transient
t_start = 30.0   # seconds

# DLC 1.2 Weibull parameters (site)
A_weibull = 10.0
k_weibull = 2.0
dU = 2.0

# Simulation usable length per run (seconds)
T_sim = 600.0

# Design lifetime
LIFE_YEARS = 20.0
SECONDS_PER_YEAR = 365.0 * 24.0 * 3600.0
T_life = LIFE_YEARS * SECONDS_PER_YEAR

# Fatigue exponents
m_tower = 4.0
m_blade = 10.0

# ---- Tower S-N input (Eurocode-style FAT class) ----
# FAT means allowable stress range Δσ_C [MPa] at N_C cycles (commonly N_C=2e6)
FAT_TOWER = 71.0   # [MPa] choose based on your tower detail (weld type etc.)
N_C = 2e6          # cycles at which FAT is defined

# ---- Blade life options ----
# Option A: Moment S-N at blade root (needs your design allowable)
DO_BLADE_MOMENT_SN = False
Nref_blade = 1e6
dMref_blade = 2500.0   # [kN-m] allowable moment range at Nref_blade (YOU must set from design basis)

# Option B: Strain S-N if you have strain channel
DO_BLADE_STRAIN_SN = False
# Example strain S-N (placeholder): Δε^m * N = Cε  (YOU must set)
m_eps = 10.0
eps_ref = 2500e-6       # strain range (e.g. 2500 microstrain)
Nref_eps = 1e6

# =========================
# HELPERS
# =========================

def weibull_cdf(U, A, k):
    U = np.asarray(U, dtype=float)
    return 1.0 - np.exp(- (U / A) ** k)

def wind_bin_probability(U_center, dU, A, k):
    U_low = max(U_center - dU/2.0, 0.0)
    U_high = U_center + dU/2.0
    return weibull_cdf(U_high, A, k) - weibull_cdf(U_low, A, k)

def rainflow_ranges(series):
    """
    Simple rainflow counting on turning points (stack method).
    Returns list of (range, mean, count).
    """
    s = np.asarray(series, dtype=float)
    stack = []
    cycles = []
    for x in s:
        stack.append(x)
        while len(stack) >= 3:
            S0, S1, S2 = stack[-3], stack[-2], stack[-1]
            r1 = abs(S1 - S0)
            r2 = abs(S2 - S1)
            if r2 < r1:
                break
            rng = r1
            mean = 0.5 * (S0 + S1)
            cycles.append((rng, mean, 0.5))
            stack.pop(-2)
    while len(stack) >= 2:
        S0, S1 = stack[-2], stack[-1]
        rng = abs(S1 - S0)
        mean = 0.5 * (S0 + S1)
        cycles.append((rng, mean, 0.5))
        stack.pop()
    return cycles

def damage_sum_from_series(signal, m):
    """S = Σ n_i * (range_i)^m"""
    S = 0.0
    for rng, mean, count in rainflow_ranges(signal):
        S += count * (rng ** m)
    return S

def read_tower_base_diam_thick(tower_file):
    """
    Parses ElastoDyn Tower file: expects a table with columns TwrElev, TwrDiam, TwrThck.
    Returns base outer diameter D [m], thickness t [m].
    """
    with open(tower_file, "r", errors="ignore") as f:
        lines = f.read().splitlines()

    header_idx = None
    for i, l in enumerate(lines):
        if ("TwrElev" in l) and ("TwrDiam" in l) and ("TwrThck" in l):
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError("Tower file: could not find header with TwrElev, TwrDiam, TwrThck")

    data = []
    for j in range(header_idx + 1, len(lines)):
        parts = re.split(r"\s+", lines[j].strip())
        if len(parts) < 3:
            if len(data) > 0:
                break
            continue
        try:
            elev = float(parts[0]); diam = float(parts[1]); thck = float(parts[2])
        except:
            if len(data) > 0:
                break
            continue
        data.append((elev, diam, thck))

    if not data:
        raise RuntimeError("Tower file: header found but no numeric rows parsed.")

    data = np.array(data, dtype=float)
    idx0 = np.argmin(data[:, 0])  # minimum elevation as base
    D = data[idx0, 1]
    t = data[idx0, 2]
    return D, t

def hollow_circ_section_props(D_outer, t_wall):
    """Return I [m^4] and c [m] for hollow circular section."""
    D = float(D_outer)
    t = float(t_wall)
    d = max(D - 2*t, 1e-6)
    I = (np.pi/64.0) * (D**4 - d**4)
    c = D/2.0
    return I, c

# =========================
# MAIN
# =========================

def main():
    # ---- Tower base section (D,t) ----
    try:
        D_base, t_base = read_tower_base_diam_thick(TOWER_FILE)
        print(f"[OK] Read tower base geometry from file: D={D_base:.3f} m, t={t_base:.3f} m")
    except RuntimeError:
        # Fallback for NREL 5MW baseline land-based tower (Jonkman 2009)
        D_base = 6.0      # [m] outer diameter at base
        t_base = 0.027    # [m] wall thickness at base
        print("[WARN] Tower file has no TwrDiam/TwrThck table. Using NREL 5MW baseline values:")
        print(f"       D_base={D_base:.3f} m, t_base={t_base:.3f} m (NREL 5MW reference)")

    I_base, c_base = hollow_circ_section_props(D_base, t_base)

    # Conversion: Δσ [Pa] = ΔM [N·m] * c / I
    # Input moments are in kN·m => multiply by 1e3 to N·m
    K_tower = (c_base / I_base) * 1e3  # Pa per (kN·m)

    # Accumulate lifetime "damage sums" in the same space as S-N:
    # Tower: we accumulate S_sigma_life_MPa = Σ n * (Δσ[MPa])^m
    S_sigma_life_MPa = 0.0

    # Blade: either moment-space sum or strain-space sum
    S_blade_moment_life = 0.0
    S_blade_strain_life = 0.0

    missing = 0

    for U in URefs:
        P_U = wind_bin_probability(U, dU, A_weibull, k_weibull)
        N_runs = (P_U * T_life) / T_sim
        w_per_seed = N_runs / len(seeds)

        for seed in seeds:
            fn = os.path.join(RESULTS_DIR, f"output_U{U:.1f}_Seed{seed}.outb")
            if not os.path.exists(fn):
                missing += 1
                continue

            of = FASTOutputFile(fn)
            df = of.toDataFrame()

            # Basic check
            if TIME_CH not in df.columns:
                raise RuntimeError(f"{fn}: Time channel '{TIME_CH}' not found.")
            for ch in [TOWER_M_CH, BLADE_M_CH]:
                if ch and ch not in df.columns:
                    raise RuntimeError(f"{fn}: channel '{ch}' not found. Use print(df.columns) to see available.")

            time = df[TIME_CH].values
            mask = time >= t_start
            if np.sum(mask) < 10:
                continue

            # --- Tower moment -> stress ---
            tower_M = df[TOWER_M_CH].values[mask]
            tower_M = tower_M - np.mean(tower_M)
            S_M_tower = damage_sum_from_series(tower_M, m_tower)  # Σ n*(ΔM[kN-m])^m

            # Convert S_M to stress-space sum:
            # Δσ[Pa] = K * ΔM[kN-m]  => (Δσ)^m = (K^m)*(ΔM^m)
            # then convert Pa -> MPa: (MPa)^m = (Pa/1e6)^m
            S_sigma_run_MPa = (K_tower**m_tower) * S_M_tower / (1e6**m_tower)

            # Weight this run into lifetime sum
            S_sigma_life_MPa += w_per_seed * S_sigma_run_MPa

            # --- Blade ---
            if DO_BLADE_STRAIN_SN and BLADE_EPS_CH:
                eps = df[BLADE_EPS_CH].values[mask]
                eps = eps - np.mean(eps)
                S_eps_run = damage_sum_from_series(eps, m_eps)  # Σ n*(Δε)^m
                S_blade_strain_life += w_per_seed * S_eps_run
            elif DO_BLADE_MOMENT_SN:
                blade_M = df[BLADE_M_CH].values[mask]
                blade_M = blade_M - np.mean(blade_M)
                S_M_blade = damage_sum_from_series(blade_M, m_blade)  # Σ n*(ΔM)^m
                S_blade_moment_life += w_per_seed * S_M_blade

    if missing > 0:
        print(f"[INFO] Missing files skipped: {missing}")

    # =========================
    # Tower Miner Damage + Life
    # =========================
    # Eurocode-style: FAT_TOWER is Δσ_C [MPa] at N_C cycles.
    # Miner damage in stress-space:
    # D = (Σ n*(Δσ)^m) / ( (Δσ_C)^m * N_C )
    C_sigma = (FAT_TOWER ** m_tower) * N_C
    D_tower = S_sigma_life_MPa / C_sigma
    life_tower_years = LIFE_YEARS / D_tower if D_tower > 0 else np.inf

    print("\n================ Tower Fatigue Life (Miner) ================")
    print(f"Tower base section: D_outer={D_base:.4f} m, t={t_base:.4f} m")
    print(f"Assumed FAT class: FAT {FAT_TOWER:.1f} MPa at N_C={N_C:.2e} cycles")
    print(f"Miner damage over {LIFE_YEARS:.1f} years: D_tower = {D_tower:.3f}  -> {'FAIL' if D_tower>=1 else 'OK'}")
    print(f"Estimated fatigue life (tower): {life_tower_years:.1f} years")
    print("============================================================")

    # =========================
    # Blade Miner Damage + Life
    # =========================
    if DO_BLADE_STRAIN_SN and BLADE_EPS_CH:
        # strain S-N: Δε^m * N = (ε_ref^m)*Nref
        C_eps = (eps_ref ** m_eps) * Nref_eps
        D_blade = S_blade_strain_life / C_eps
        life_blade_years = LIFE_YEARS / D_blade if D_blade > 0 else np.inf

        print("\n================ Blade Fatigue Life (Strain S-N) ============")
        print(f"Using strain channel: {BLADE_EPS_CH}")
        print(f"Assumed ε-N reference: Δε_ref={eps_ref:.3e} at Nref={Nref_eps:.2e}, m={m_eps:.1f}")
        print(f"Miner damage over {LIFE_YEARS:.1f} years: D_blade = {D_blade:.3f}  -> {'FAIL' if D_blade>=1 else 'OK'}")
        print(f"Estimated fatigue life (blade): {life_blade_years:.1f} years")
        print("============================================================")
    elif DO_BLADE_MOMENT_SN:
        # moment S-N: (ΔM_ref^m)*Nref defines capacity
        C_M_blade = (dMref_blade ** m_blade) * Nref_blade
        D_blade = S_blade_moment_life / C_M_blade
        life_blade_years = LIFE_YEARS / D_blade if D_blade > 0 else np.inf

        print("\n================ Blade Fatigue Life (Moment S-N) ============")
        print("NOTE: This requires blade allowable moment-range from design basis.")
        print(f"Assumed ΔM_ref={dMref_blade:.1f} kN-m at Nref={Nref_blade:.2e}, m={m_blade:.1f}")
        print(f"Miner damage over {LIFE_YEARS:.1f} years: D_blade = {D_blade:.3f}  -> {'FAIL' if D_blade>=1 else 'OK'}")
        print(f"Estimated fatigue life (blade): {life_blade_years:.1f} years")
        print("============================================================")
    else:
        print("\n[INFO] Blade life not computed. Enable DO_BLADE_MOMENT_SN or DO_BLADE_STRAIN_SN.")

if __name__ == "__main__":
    main()
