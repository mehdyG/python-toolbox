import os
import numpy as np
import pandas as pd
from pyFAST.input_output import FASTOutputFile
import matplotlib.pyplot as plt

# -----------------------------
# Einstellungen
# -----------------------------

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(THIS_DIR, 'DLC1p2_OF_results')

# Gleiche URefs & Seeds wie im Run-Script
URefs = np.arange(3, 26, 2)        # [3,5,...,25]
seeds = [1, 2, 3, 4, 5, 6]


# Channel-Namen (ggf. anpassen!)
TWR_CHANNEL   = 'TwrBsMyt_[kN-m]'   # Tower base fore-aft bending
BLADE_CHANNEL = 'RootMyb1_[kN-m]'   # Blade 1 root flapwise

# Fatigue-Exponenten
m_tower = 4
m_blade = 10

# Equivalent number of cycles for DEL
N_eq = 1e7

# Lebensdauer & Windverteilung (DLC 1.2)
LIFE_YEARS = 20
SECONDS_PER_YEAR = 365 * 24 * 3600
T_life = LIFE_YEARS * SECONDS_PER_YEAR

T_sim = 600.0   # Sekunden usable pro Simulation

# Weibull-Parameter
A_weibull = 10.0   # scale
k_weibull = 2.0    # shape (ähnlich Rayleigh)

# Binbreite für URefs [3,5,7,...,25]
dU = 2.0

# --- Demo Settings ---
U_demo = 15.0    # Wind speed to analyze in detail
seed_demo = 1    # Which seed to inspect

demo_time = None
demo_signals_blade = {}
demo_signals_tower = {}   # optional

# -----------------------------
# Hilfsfunktionen
# -----------------------------

def weibull_cdf(U, A, k):
    """Weibull CDF F(U) = 1 - exp(-(U/A)^k)"""
    U = np.asarray(U, dtype=float)
    return 1.0 - np.exp(- (U / A)**k)


def wind_bin_probability(U_center, dU, A, k):
    """
    Wahrscheinlichkeit für eine Windgeschwindigkeits-Bin
    mit Mittelpunkt U_center und Breite dU.
    """
    U_low  = U_center - dU / 2.0
    U_high = U_center + dU / 2.0
    U_low = max(U_low, 0.0)
    return weibull_cdf(U_high, A, k) - weibull_cdf(U_low, A, k)


# ---------- eingebaute Rainflow-Implementierung ----------

def rainflow_ranges(series):
    """
    Einfache Rainflow-Auswertung.
    Gibt Liste von (range, mean, count) zurück.
    """
    s = np.asarray(series, dtype=float)
    stack = []
    cycles = []

    for x in s:
        stack.append(x)
        # Versuche, komplette Zyklen zu finden
        while len(stack) >= 3:
            S0, S1, S2 = stack[-3], stack[-2], stack[-1]
            r1 = abs(S1 - S0)
            r2 = abs(S2 - S1)

            if r2 < r1:
                # noch kein geschlossener Zyklus
                break

            # geschlossener Zyklus über S0-S1
            rng = r1
            mean = 0.5 * (S0 + S1)
            cycles.append((rng, mean, 0.5))   # halber Zyklus

            # S1 entfernen
            stack.pop(-2)

    # Rest als halbe Zyklen
    while len(stack) >= 2:
        S0, S1 = stack[-2], stack[-1]
        rng = abs(S1 - S0)
        mean = 0.5 * (S0 + S1)
        cycles.append((rng, mean, 0.5))
        stack.pop()

    return cycles


def calc_damage_from_timeseries(signal, m):
    """
    Fatigue-Damage aus Zeitreihe mittels Rainflow.
    damage_sum = sum(count * range^m)
    """
    damage_sum = 0.0
    for rng, mean, count in rainflow_ranges(signal):
        damage_sum += count * (rng ** m)
    return damage_sum


def DEL_from_damage(damage_sum, m, N_eq):
    """
    DEL aus Summendamage:
        DEL = (damage_sum / N_eq)^(1/m)
    """
    return (damage_sum / N_eq) ** (1.0 / m)


# -----------------------------
# Hauptteil: Dateien einlesen & DEL pro Run
# -----------------------------

rows_tower = []
rows_blade = []

damage_tower = {}  # key: (U, seed) -> damage_sum (für 600 s)
damage_blade = {}

for U in URefs:
    for seed in seeds:
        filename = f'output_U{U:.1f}_Seed{seed}.outb'
        filepath = os.path.join(RESULTS_DIR, filename)

        if not os.path.exists(filepath):
            print(f"⚠️ Datei fehlt: {filepath}")
            continue

        print(f"📂 Lese {filepath}")
        of = FASTOutputFile(filepath)
        df = of.toDataFrame()
        #print(df.columns)     # 👈 HIER EINFÜGEN
        #break 

        # 👉 einmalig zum Checken kannst du auskommentieren:
        # print(df.columns); break

        time = df['Time_[s]'].values
        tower_moment = df[TWR_CHANNEL].values
        blade_moment = df[BLADE_CHANNEL].values

        # Transienten abschneiden: z.B. erste 30 s weg
        t_start = 30.0
        mask = time >= t_start

        tower_moment = tower_moment[mask]
        blade_moment = blade_moment[mask]

        # --- DEMO: Zeitreihen für U_demo speichern ---
        if abs(U - U_demo) < 1e-6:
            if demo_time is None:
                demo_time = mask  # gleiche Zeitbasis für alle Seeds
            demo_signals_blade[seed] = blade_moment.copy()
            demo_signals_tower[seed] = tower_moment.copy()


        # Mittelwert entfernen (üblich bei Fatigue)
        tower_moment = tower_moment - np.mean(tower_moment)
        blade_moment = blade_moment - np.mean(blade_moment)

        # Rainflow & Damage
        dmg_t = calc_damage_from_timeseries(tower_moment, m_tower)
        dmg_b = calc_damage_from_timeseries(blade_moment, m_blade)

        # DEL pro 600s-Run (nur Info)
        DEL_t = DEL_from_damage(dmg_t, m_tower, N_eq)
        DEL_b = DEL_from_damage(dmg_b, m_blade, N_eq)

        damage_tower[(U, seed)] = dmg_t
        damage_blade[(U, seed)] = dmg_b

        rows_tower.append({'Uref': U, 'seed': seed, 'DEL_tower_run': DEL_t})
        rows_blade.append({'Uref': U, 'seed': seed, 'DEL_blade_run': DEL_b})

df_tower = pd.DataFrame(rows_tower)
df_blade = pd.DataFrame(rows_blade)

print("\n=== DEL pro Run - Tower Base ===")
print(df_tower)

print("\n=== DEL pro Run - Blade Root ===")
print(df_blade)


# -----------------------------
# DLC 1.2: Lebensdauer-DEL & DEL pro Windgeschwindigkeit
# -----------------------------

n_seeds = len(seeds)

damage_tower_life = 0.0
damage_blade_life = 0.0

P_bins = []               # Weibull-Bin-Wahrscheinlichkeit pro U
DEL_tower_bins = []       # DEL pro U (Tower)
DEL_blade_bins = []       # DEL pro U (Blade)

for U in URefs:
    # Weibull-Wahrscheinlichkeit der Bin
    P_U = wind_bin_probability(U, dU, A_weibull, k_weibull)
    P_bins.append(P_U)

    # Anzahl 600s-Runs über Lebensdauer
    N_runs = (P_U * T_life) / T_sim
    weight_per_seed = N_runs / n_seeds

    dmg_t_U = 0.0
    dmg_b_U = 0.0

    for seed in seeds:
        key = (U, seed)
        if key not in damage_tower or key not in damage_blade:
            continue

        dmg_t_U += weight_per_seed * damage_tower[key]
        dmg_b_U += weight_per_seed * damage_blade[key]

    # für gesamte Lebensdauer
    damage_tower_life += dmg_t_U
    damage_blade_life += dmg_b_U

    # DEL pro Windgeschwindigkeit (für Plot)
    DEL_t_bin = DEL_from_damage(dmg_t_U, m_tower, N_eq)
    DEL_b_bin = DEL_from_damage(dmg_b_U, m_blade, N_eq)

    DEL_tower_bins.append(DEL_t_bin)
    DEL_blade_bins.append(DEL_b_bin)

# Gesamt-Lebensdauer-DEL
DEL_tower_life = DEL_from_damage(damage_tower_life, m_tower, N_eq)
DEL_blade_life = DEL_from_damage(damage_blade_life, m_blade, N_eq)

print("\n================ DLC 1.2 Lebensdauer-DEL =================")
print(f"Tower base bending moment DEL (life):  {DEL_tower_life:.3f} kN-m")
print(f"Blade root bending moment DEL (life):  {DEL_blade_life:.3f} kN-m")
print("=========================================================")


# -----------------------------
# Plots: Weibull + DEL pro Windgeschwindigkeit
# -----------------------------

U_array = np.array(URefs, dtype=float)
P_bins = np.array(P_bins, dtype=float)
DEL_tower_bins = np.array(DEL_tower_bins, dtype=float)
DEL_blade_bins = np.array(DEL_blade_bins, dtype=float)

# Plot 1: Blade Root
fig1, ax1 = plt.subplots()
ax1.bar(U_array, P_bins, width=1.5, alpha=0.3, align='center')
ax1.set_xlabel('Wind speed U [m/s]')
ax1.set_ylabel('Weibull bin probability [-]')

ax2 = ax1.twinx()
ax2.plot(U_array, DEL_blade_bins, marker='o')
ax2.set_ylabel('Blade root DEL [kN-m]')
plt.title('DLC 1.2: Weibull & Blade Root DEL per wind speed')
plt.tight_layout()

# Plot 2: Tower Base
fig2, ax3 = plt.subplots()
ax3.bar(U_array, P_bins, width=1.5, alpha=0.3, align='center')
ax3.set_xlabel('Wind speed U [m/s]')
ax3.set_ylabel('Weibull bin probability [-]')

ax4 = ax3.twinx()
ax4.plot(U_array, DEL_tower_bins, marker='o')
ax4.set_ylabel('Tower base DEL [kN-m]')
plt.title('DLC 1.2: Weibull & Tower Base DEL per wind speed')
plt.tight_layout()


# -----------------------------
# DEMO: Rainflow-Auswertung für U_demo und seed_demo
# -----------------------------
if demo_time is not None and seed_demo in demo_signals_blade:

    sig_demo = demo_signals_blade[seed_demo]

    # 1) Rainflow-Zyklen berechnen
    df_cycles, dmg_sum_demo, DEL_demo = analyze_rainflow_demo(sig_demo, m_blade, N_eq)

    print(f"\n===== Rainflow demo for Blade root, U={U_demo} m/s, Seed={seed_demo} =====")
    print(df_cycles.head(20))  # Zeige erste 20 Zyklen
    print(f"\nDamage sum for this 600s run: {dmg_sum_demo:.3e}")
    print(f"DEL for this run: {DEL_demo:.3f} kN-m")

    # 2) Time-series Plot für alle Seeds
    fig_ts, axes = plt.subplots(len(demo_signals_blade), 1, sharex=True, figsize=(8, 8))
    if len(demo_signals_blade) == 1:
        axes = [axes]

    for ax, seed in zip(axes, sorted(demo_signals_blade.keys())):
        ax.plot(demo_time, demo_signals_blade[seed])
        ax.set_ylabel(f'Seed {seed}')
    axes[-1].set_xlabel('Time [s]')
    fig_ts.suptitle(f'Blade root time series at U = {U_demo:.1f} m/s')
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    # 3) Damage contribution plot
    df_sorted = df_cycles.sort_values("range")
    fig_dmg, axd = plt.subplots()
    axd.bar(np.arange(len(df_sorted)), df_sorted["damage_contrib"])
    axd.set_xlabel("Cycle index (sorted by range)")
    axd.set_ylabel("Damage contribution")
    plt.title(f'Blade root rainflow contributions\nU={U_demo}, Seed={seed_demo}')
    plt.tight_layout()

plt.show()
