import os
import numpy as np
import pandas as pd
from pyFAST.input_output import FASTOutputFile
import rainflow

# -----------------------------
# Einstellungen
# -----------------------------

# Ordner, in dem dieses Script liegt
THIS_DIR = os.path.dirname(os.path.abspath(__file__))

# Ordner mit den DLC 1.2 OpenFAST-Ergebnissen
RESULTS_DIR = os.path.join(THIS_DIR, 'DLC1p2_OF_results')

# Gleiche URefs & Seeds wie im Run-Script
URefs = np.arange(3, 26, 2)        # [3,5,...,25]
seeds = [1, 2, 3, 4, 5, 6]

# Channel-Namen (ggf. anpassen!)
TWR_CHANNEL   = 'TwrBsMyt_[kN-m]'   # Tower base fore-aft bending moment
BLADE_CHANNEL = 'RootMyb1_[kN-m]'   # Blade 1 root flapwise bending moment

# Fatigue-Exponenten (Material)
m_tower = 4
m_blade = 10

# Equivalent number of cycles for DEL (z.B. 1e7)
N_eq = 1e7

# Lebensdauer & Windverteilung für DLC 1.2 (kannst du anpassen)
LIFE_YEARS = 20
SECONDS_PER_YEAR = 365 * 24 * 3600
T_life = LIFE_YEARS * SECONDS_PER_YEAR

T_sim = 600.0   # Sekunden usable pro Simulation (DLC1.2 Runlänge)

# Weibull-Parameter für Windgeschwindigkeit
A_weibull = 10.0   # scale
k_weibull = 2.0    # shape


# -----------------------------
# Hilfsfunktionen
# -----------------------------

def weibull_cdf(U, A, k):
    """Weibull CDF F(U) = 1 - exp(-(U/A)^k)"""
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


def calc_damage_from_timeseries(signal, m):
    """
    Berechnet den Summendamage-Parameter:
        D_sum = sum( n_i * (range_i^m) )
    aus einer Zeitreihe 'signal' mittels Rainflow-Zählung.
    """
    damage_sum = 0.0
    # rainflow.count_cycles gibt (range, mean, count)
    for rng, mean, count in rainflow.count_cycles(signal):
        damage_sum += count * (rng ** m)
    return damage_sum


def DEL_from_damage(damage_sum, m, N_eq):
    """
    Berechnet DEL aus Summendamage:
        DEL = (damage_sum / N_eq)^(1/m)
    """
    return (damage_sum / N_eq) ** (1.0 / m)


# -----------------------------
# Haupt-Teil: Datei-Loop & DEL pro Run
# -----------------------------

# Tabellen für Ergebnisse
rows_tower = []
rows_blade = []

# optional: für Lebensdauer-DLC-Später: Damage-Speicher
damage_tower = {}  # key: (U, seed) -> damage_sum
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

        # --- Zeit & Signale holen ---
        time = df['Time_[s]'].values
        tower_moment = df[TWR_CHANNEL].values
        blade_moment = df[BLADE_CHANNEL].values

        # Transienten abschneiden: z.B. erste 30 s weg
        t_start = 30.0
        mask = time >= t_start

        tower_moment = tower_moment[mask]
        blade_moment = blade_moment[mask]
        time_cut = time[mask]

        # Mittelwert entfernen (optional, aber üblich für Fatigue)
        tower_moment = tower_moment - np.mean(tower_moment)
        blade_moment = blade_moment - np.mean(blade_moment)

        # --- Rainflow & Damage ---
        dmg_t = calc_damage_from_timeseries(tower_moment, m_tower)
        dmg_b = calc_damage_from_timeseries(blade_moment, m_blade)

        # DEL pro 600s-Run
        DEL_t = DEL_from_damage(dmg_t, m_tower, N_eq)
        DEL_b = DEL_from_damage(dmg_b, m_blade, N_eq)

        # speichern
        damage_tower[(U, seed)] = dmg_t
        damage_blade[(U, seed)] = dmg_b

        rows_tower.append({
            'Uref': U,
            'seed': seed,
            'DEL_tower_run': DEL_t
        })

        rows_blade.append({
            'Uref': U,
            'seed': seed,
            'DEL_blade_run': DEL_b
        })

# DataFrames zur Übersicht
df_tower = pd.DataFrame(rows_tower)
df_blade = pd.DataFrame(rows_blade)

print("\n=== DEL pro Run - Tower Base ===")
print(df_tower)

print("\n=== DEL pro Run - Blade Root ===")
print(df_blade)


# -----------------------------
# DLC 1.2: Lebensdauer-DEL über alle U & Seeds
# -----------------------------

# Bin-Breite für URefs [3,5,7,...,25] -> ~2m/s
dU = 2.0
n_seeds = len(seeds)

damage_tower_life = 0.0
damage_blade_life = 0.0

for U in URefs:
    # Wahrscheinlichkeit der Windgeschwindigkeits-Bin
    P_U = wind_bin_probability(U, dU, A_weibull, k_weibull)

    # Anzahl 600s-Simulationen über Lebensdauer
    N_runs = (P_U * T_life) / T_sim

    # pro Seed gleicher Anteil
    weight_per_seed = N_runs / n_seeds

    for seed in seeds:
        key = (U, seed)
        if key not in damage_tower or key not in damage_blade:
            continue

        damage_tower_life += weight_per_seed * damage_tower[key]
        damage_blade_life += weight_per_seed * damage_blade[key]

# Lebensdauer-DEL (DLC 1.2) für Tower & Blade
DEL_tower_life = DEL_from_damage(damage_tower_life, m_tower, N_eq)
DEL_blade_life = DEL_from_damage(damage_blade_life, m_blade, N_eq)

print("\n================ DLC 1.2 Lebensdauer-DEL =================")
print(f"Tower base bending moment DEL (life):  {DEL_tower_life:.3f} kN-m")
print(f"Blade root bending moment DEL (life):  {DEL_blade_life:.3f} kN-m")
print("=========================================================")
