# -*- coding: utf-8 -*-
"""
DLC 1.2 Postprocessing für NREL 5MW (OpenFAST).
Dieses Skript:
- liest alle .outb Dateien aus DLC1p2_OF_results ein (U=3..25 m/s, mehrere Seeds),
- führt Rainflow-Auswertung durch und berechnet DEL pro Run (Tower Base & Blade Root),
- integriert die Ermüdung über eine Weibull-Windverteilung zu Lebensdauer-DEL (DLC 1.2),
- plottet Weibull-Verteilung und DEL pro Windgeschwindigkeits-Bin für Tower und Blade.

Voraussetzungen: pyFAST, numpy, pandas, matplotlib.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pyFAST.input_output import FASTOutputFile

# ---------------------------------------------------------
# Einstellungen
# ---------------------------------------------------------

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(THIS_DIR, "DLC1p2_OF_results")

# Windgeschwindigkeiten und Seeds (müssen zu deinen Dateinamen passen)
URefs = np.arange(3, 26, 2)      # 3, 5, 7, ..., 25 m/s
seeds = [1, 2, 3, 4, 5, 6]

# Kanalnamen aus den OpenFAST-Ausgabedateien (ggf. anpassen!)
TWR_CHANNEL   = "TwrBsMyt_[kN-m]"   # Tower base fore-aft bending moment
BLADE_CHANNEL = "RootMyb1_[kN-m]"   # Blade 1 flapwise root bending moment

# Material-Fatigue-Exponenten
m_tower = 4    # Stahl / Turm
m_blade = 10   # GFK / Blade

# Äquivalente Zyklenzahl für DEL
N_eq = 1e7

# Designlebensdauer
LIFE_YEARS = 20
SECONDS_PER_YEAR = 365 * 24 * 3600
T_life = LIFE_YEARS * SECONDS_PER_YEAR

# Simulationslänge pro Run (usable Zeit nach Transienten)
T_sim = 600.0  # Sekunden

# Weibull-Parameter der Standort-Windverteilung
A_weibull = 10.0   # scale
k_weibull = 2.0    # shape (Rayleigh-ähnlich)

# Windgeschwindigkeits-Binbreite (zu URefs passend)
dU = 2.0


# ---------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------

def weibull_cdf(U, A, k):
    """Weibull CDF F(U) = 1 - exp(-(U/A)^k)."""
    U = np.asarray(U, dtype=float)
    return 1.0 - np.exp(- (U / A) ** k)


def wind_bin_probability(U_center, dU, A, k):
    """
    Wahrscheinlichkeit, dass die mittlere Windgeschwindigkeit
    in einer Bin um U_center (± dU/2) liegt.
    """
    U_low  = max(U_center - dU / 2.0, 0.0)
    U_high = U_center + dU / 2.0
    return weibull_cdf(U_high, A, k) - weibull_cdf(U_low, A, k)


def rainflow_ranges(series):
    """
    Einfache Rainflow-Implementierung.
    Gibt Liste von (range, mean, count) zurück.
    """
    s = np.asarray(series, dtype=float)
    stack = []
    cycles = []

    for x in s:
        stack.append(x)
        # versuche, abgeschlossene Zyklen zu finden
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
            cycles.append((rng, mean, 0.5))  # halber Zyklus

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
    Ermüdungssumme aus der Zeitreihe:
        damage_sum = sum(count * range^m)
    """
    damage_sum = 0.0
    for rng, mean, count in rainflow_ranges(signal):
        damage_sum += count * (rng ** m)
    return damage_sum


def DEL_from_damage(damage_sum, m, N_eq):
    """
    Damage Equivalent Load:
        DEL = (damage_sum / N_eq)^(1/m)
    """
    return (damage_sum / N_eq) ** (1.0 / m)


# ---------------------------------------------------------
# Hauptschleife: .outb-Dateien einlesen & DEL pro Run
# ---------------------------------------------------------

rows_tower = []
rows_blade = []

damage_tower = {}  # key: (U, seed) -> damage_sum (für 600 s)
damage_blade = {}

for U in URefs:
    for seed in seeds:
        filename = f"output_U{U:.1f}_Seed{seed}.outb"
        filepath = os.path.join(RESULTS_DIR, filename)

        if not os.path.exists(filepath):
            print(f"⚠️ Datei fehlt: {filepath}")
            continue

        print(f"📂 Lese {filepath}")
        of = FASTOutputFile(filepath)
        df = of.toDataFrame()

        time = df["Time_[s]"].values
        tower_moment = df[TWR_CHANNEL].values
        blade_moment = df[BLADE_CHANNEL].values

        # Transienten abschneiden (z.B. erste 30 s)
        t_start = 30.0
        mask = time >= t_start

        tower_moment = tower_moment[mask]
        blade_moment = blade_moment[mask]

        # Mittelwert entfernen (für reine Spannungsamplituden)
        tower_moment = tower_moment - np.mean(tower_moment)
        blade_moment = blade_moment - np.mean(blade_moment)

        # Rainflow & Damage
        dmg_t = calc_damage_from_timeseries(tower_moment, m_tower)
        dmg_b = calc_damage_from_timeseries(blade_moment, m_blade)

        # DEL pro 600-s-Run (nur Info)
        DEL_t = DEL_from_damage(dmg_t, m_tower, N_eq)
        DEL_b = DEL_from_damage(dmg_b, m_blade, N_eq)

        damage_tower[(U, seed)] = dmg_t
        damage_blade[(U, seed)] = dmg_b

        rows_tower.append({"Uref": U, "seed": seed, "DEL_tower_run": DEL_t})
        rows_blade.append({"Uref": U, "seed": seed, "DEL_blade_run": DEL_b})

df_tower = pd.DataFrame(rows_tower)
df_blade = pd.DataFrame(rows_blade)

print("\n=== DEL pro Run - Tower Base ===")
print(df_tower)

print("\n=== DEL pro Run - Blade Root ===")
print(df_blade)


# ---------------------------------------------------------
# DLC 1.2 Lebensdauer-DEL über Windverteilung
# ---------------------------------------------------------

n_seeds = len(seeds)

damage_tower_life = 0.0
damage_blade_life = 0.0

P_bins = []         # Weibull-Bin-Wahrscheinlichkeit pro U
DEL_tower_bins = [] # DEL-Beitrag pro U (Tower)
DEL_blade_bins = [] # DEL-Beitrag pro U (Blade)

for U in URefs:
    # Wahrscheinlichkeit der Windgeschwindigkeits-Bin
    P_U = wind_bin_probability(U, dU, A_weibull, k_weibull)
    P_bins.append(P_U)

    # Anzahl 600s-Simulationen über Lebensdauer
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

    # Über Gesamtlebensdauer aufsummieren
    damage_tower_life += dmg_t_U
    damage_blade_life += dmg_b_U

    # DEL-Beitrag dieser Windgeschwindigkeit (für Plot)
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


# ---------------------------------------------------------
# Plots: Weibull-Verteilung + DEL pro Windgeschwindigkeit
# ---------------------------------------------------------

U_array = np.array(URefs, dtype=float)
P_bins = np.array(P_bins, dtype=float)
DEL_tower_bins = np.array(DEL_tower_bins, dtype=float)
DEL_blade_bins = np.array(DEL_blade_bins, dtype=float)

# Plot 1: Blade Root
fig1, ax1 = plt.subplots()
ax1.bar(U_array, P_bins, width=1.5, alpha=0.3, align="center")
ax1.set_xlabel("Wind speed U [m/s]")
ax1.set_ylabel("Weibull bin probability [-]")

ax2 = ax1.twinx()
ax2.plot(U_array, DEL_blade_bins, marker="o")
ax2.set_ylabel("Blade root DEL [kN-m]")

plt.title("DLC 1.2: Weibull & Blade Root DEL per wind speed")
plt.tight_layout()

# Plot 2: Tower Base
fig2, ax3 = plt.subplots()
ax3.bar(U_array, P_bins, width=1.5, alpha=0.3, align="center")
ax3.set_xlabel("Wind speed U [m/s]")
ax3.set_ylabel("Weibull bin probability [-]")

ax4 = ax3.twinx()
ax4.plot(U_array, DEL_tower_bins, marker="o")
ax4.set_ylabel("Tower base DEL [kN-m]")

plt.title("DLC 1.2: Weibull & Tower Base DEL per wind speed")
plt.tight_layout()

plt.show()
