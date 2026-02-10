# -*- coding: utf-8 -*-
"""
DLC 1.2 – Wichtigste Windgeschwindigkeiten (Damage-/DEL-Beitrag) – Standalone Script

Was dieses Script macht:
1) Liest OpenFAST .outb Dateien: output_U{U}_Seed{seed}.outb
2) Für jeden Run: Rainflow -> Damage sum S = Σ n_i * (ΔM_i)^m  (für Tower & Blade)
3) DLC 1.2 Gewichtung über Weibull-Bins -> Lifetime Damage pro Windgeschwindigkeit U_k
4) Ausgabe:
   - Lifetime DEL (Tower/Blade)
   - Ranking "welche Wind speed dominiert" (nach Damage-Beitrag)
   - Plot: Damage-Anteil [%] pro U für Tower & Blade

Hinweis:
- Das ist NUR "wichtigste Wind Speeds". Keine Event-Klassifikation.
- Channel-Namen müssen zu deinen Outputs passen. Wenn Fehler: einmal print(df.columns).
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pyFAST.input_output import FASTOutputFile


# =========================
# USER SETTINGS
# =========================
RESULTS_DIR = r"/home/Mehdy/python-toolbox/pyFAST/DLC1p2/DLC1p2_OF_results"

# Must match your output filenames:
URefs = np.arange(3, 26, 2)       # 3,5,...,25 m/s
seeds = [1, 2, 3, 4, 5, 6]

# Output channels (adjust if needed!)
TIME_CH        = "Time_[s]"
TOWER_M_CH     = "TwrBsMyt_[kN-m]"
BLADE_M_CH     = "RootMyb1_[kN-m]"

# Transient cut
t_start = 30.0   # seconds

# Fatigue exponents (commonly used for damage weighting)
m_tower = 4.0
m_blade = 10.0

# DEL reference cycles (choose and state it in reports)
N_eq = 1e7

# Weibull site parameters (DLC 1.2 site wind distribution)
A_weibull = 10.0
k_weibull = 2.0
dU = 2.0

# Run duration used in simulation (usable part)
T_sim = 600.0  # seconds

# Design life
LIFE_YEARS = 20.0
SECONDS_PER_YEAR = 365.0 * 24.0 * 3600.0
T_life = LIFE_YEARS * SECONDS_PER_YEAR


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

def rainflow_ranges(signal):
    """
    Simple rainflow implementation (stack method).
    Returns list of (range, mean, count).
    """
    s = np.asarray(signal, dtype=float)
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

def damage_sum_from_timeseries(signal, m):
    """S = Σ n_i * (ΔX_i)^m"""
    S = 0.0
    for rng, mean, count in rainflow_ranges(signal):
        S += count * (rng ** m)
    return S

def DEL_from_damage(S, m, N_eq):
    return (S / N_eq) ** (1.0 / m)


# =========================
# MAIN
# =========================
def main():
    # Store per-run damage sums (short-term, 600s after cut)
    S_run_tower = {}  # (U, seed) -> S
    S_run_blade = {}

    missing = 0

    # ---- 1) Read all runs and compute short-term damage sums ----
    for U in URefs:
        for seed in seeds:
            fn = os.path.join(RESULTS_DIR, f"output_U{U:.1f}_Seed{seed}.outb")
            if not os.path.exists(fn):
                missing += 1
                continue

            of = FASTOutputFile(fn)
            df = of.toDataFrame()

            # Basic channel checks
            for ch in [TIME_CH, TOWER_M_CH, BLADE_M_CH]:
                if ch not in df.columns:
                    raise RuntimeError(
                        f"\nChannel '{ch}' not found in {os.path.basename(fn)}.\n"
                        f"Run once:\n  print(df.columns)\n"
                        f"and update TIME_CH/TOWER_M_CH/BLADE_M_CH accordingly."
                    )

            time = df[TIME_CH].values
            mask = time >= t_start
            if np.sum(mask) < 20:
                continue

            # Extract & detrend (mean remove)
            tower = df[TOWER_M_CH].values[mask]
            blade = df[BLADE_M_CH].values[mask]
            tower = tower - np.mean(tower)
            blade = blade - np.mean(blade)

            S_t = damage_sum_from_timeseries(tower, m_tower)
            S_b = damage_sum_from_timeseries(blade, m_blade)

            S_run_tower[(U, seed)] = S_t
            S_run_blade[(U, seed)] = S_b

    if missing > 0:
        print(f"[INFO] Missing files skipped: {missing}")

    # ---- 2) Lifetime weighting per wind speed bin ----
    rows = []

    S_life_tower_total = 0.0
    S_life_blade_total = 0.0

    S_life_tower_byU = {}
    S_life_blade_byU = {}
    P_byU = {}

    for U in URefs:
        P_U = wind_bin_probability(U, dU, A_weibull, k_weibull)
        P_byU[U] = P_U

        # lifetime number of runs at this bin
        N_runs = (P_U * T_life) / T_sim
        w_per_seed = N_runs / len(seeds)

        S_life_t_U = 0.0
        S_life_b_U = 0.0

        for seed in seeds:
            key = (U, seed)
            if key in S_run_tower:
                S_life_t_U += w_per_seed * S_run_tower[key]
            if key in S_run_blade:
                S_life_b_U += w_per_seed * S_run_blade[key]

        S_life_tower_byU[U] = S_life_t_U
        S_life_blade_byU[U] = S_life_b_U

        S_life_tower_total += S_life_t_U
        S_life_blade_total += S_life_b_U

        # Helpful per-bin DEL-equivalent (not a physical "run DEL", but shows scale)
        DEL_bin_t = DEL_from_damage(S_life_t_U, m_tower, N_eq) if S_life_t_U > 0 else 0.0
        DEL_bin_b = DEL_from_damage(S_life_b_U, m_blade, N_eq) if S_life_b_U > 0 else 0.0

        rows.append({
            "U [m/s]": U,
            "P_bin [-]": P_U,
            "S_life_tower": S_life_t_U,
            "S_life_blade": S_life_b_U,
            "DEL_equiv_tower": DEL_bin_t,
            "DEL_equiv_blade": DEL_bin_b,
        })

    dfU = pd.DataFrame(rows)

    # ---- 3) Lifetime DEL (overall) ----
    DEL_tower_life = DEL_from_damage(S_life_tower_total, m_tower, N_eq)
    DEL_blade_life = DEL_from_damage(S_life_blade_total, m_blade, N_eq)

    print("\n================ DLC 1.2 Lifetime DEL =================")
    print(f"Tower lifetime DEL: {DEL_tower_life:.3f} kN-m  (m={m_tower:g}, N_eq={N_eq:.1e})")
    print(f"Blade lifetime DEL: {DEL_blade_life:.3f} kN-m  (m={m_blade:g}, N_eq={N_eq:.1e})")
    print("========================================================")

    # ---- 4) Contribution per U (which wind speeds dominate?) ----
    dfU["Tower damage share [%]"] = np.where(
        S_life_tower_total > 0, 100.0 * dfU["S_life_tower"] / S_life_tower_total, 0.0
    )
    dfU["Blade damage share [%]"] = np.where(
        S_life_blade_total > 0, 100.0 * dfU["S_life_blade"] / S_life_blade_total, 0.0
    )

    print("\n===== Top Wind Speeds by Tower Damage Share =====")
    print(dfU.sort_values("Tower damage share [%]", ascending=False)[
        ["U [m/s]", "P_bin [-]", "Tower damage share [%]", "DEL_equiv_tower"]
    ].head(8).to_string(index=False))

    print("\n===== Top Wind Speeds by Blade Damage Share =====")
    print(dfU.sort_values("Blade damage share [%]", ascending=False)[
        ["U [m/s]", "P_bin [-]", "Blade damage share [%]", "DEL_equiv_blade"]
    ].head(8).to_string(index=False))

    # ---- 5) Plots: damage share vs U ----
    U_arr = dfU["U [m/s]"].values

    # Tower plot
    plt.figure()
    plt.bar(U_arr, dfU["Tower damage share [%]"].values)
    plt.xlabel("Wind speed U [m/s]")
    plt.ylabel("Tower damage share [%]")
    plt.title("DLC 1.2: Which wind speeds dominate Tower fatigue?")
    plt.tight_layout()

    # Blade plot
    plt.figure()
    plt.bar(U_arr, dfU["Blade damage share [%]"].values)
    plt.xlabel("Wind speed U [m/s]")
    plt.ylabel("Blade damage share [%]")
    plt.title("DLC 1.2: Which wind speeds dominate Blade fatigue?")
    plt.tight_layout()

    # Optional: show Weibull bin probabilities too
    plt.figure()
    plt.bar(U_arr, dfU["P_bin [-]"].values)
    plt.xlabel("Wind speed U [m/s]")
    plt.ylabel("Weibull bin probability [-]")
    plt.title("Weibull probability mass per wind-speed bin")
    plt.tight_layout()

    plt.show()


if __name__ == "__main__":
    main()
