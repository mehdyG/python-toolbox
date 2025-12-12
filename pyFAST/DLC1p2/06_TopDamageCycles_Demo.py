# -*- coding: utf-8 -*-
"""
Top Damage Cycles Demo – NREL 5MW / OpenFAST

Dieses Skript:
- liest EINEN OpenFAST-Output-Run (für eine gegebene Windgeschwindigkeit U_demo und Seed seed_demo),
- extrahiert Tower-Base-Moment und Blade-Root-Moment,
- macht eine Rainflow-Zählung für beide Kanäle,
- bestimmt die Top-N Zyklen mit dem größten Ermüdungsbeitrag (damage_contrib),
- plottet die Zeitreihen und markiert die Top-Zyklen im Zeitverlauf.

WICHTIG: Keine DEL- oder Lebensdauer-Berechnung – nur Rainflow & Top-Schadenszyklen.
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

# Datei, die analysiert werden soll (muss zum OpenFAST-Output passen)
U_demo = 15.0        # [m/s] Windgeschwindigkeit des Runs
seed_demo = 1        # Seed des Runs

# Name der Output-Datei (anpassen, falls dein Muster anders ist)
FILENAME = f"output_U{U_demo:.1f}_Seed{seed_demo}.outb"

# Kanalnamen (ggf. mit df.columns prüfen und anpassen)
TWR_CHANNEL   = "TwrBsMyt_[kN-m]"   # Tower base fore-aft bending
BLADE_CHANNEL = "RootMyb1_[kN-m]"   # Blade 1 flapwise root bending

# Ermüdungsexponenten (nur für damage_contrib-Gewichtung)
m_tower = 4
m_blade = 10

# Wie viele Top-Zyklen anzeigen
N_top = 5

# Start der "usable" Zeit (z.B. nach Einschwingvorgang)
t_start = 30.0   # Sekunden


# ---------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------

def rainflow_ranges(series):
    """
    Einfache Rainflow-Implementierung.
    Gibt Liste von (range, mean, count) zurück.
    range  = Spannweite des Zyklus
    mean   = Mittelwert des Zyklus
    count  = Anzahl (meist 0.5 für halbe Zyklen)
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
                # kein abgeschlossener Zyklus
                break

            rng = r1
            mean = 0.5 * (S0 + S1)
            cycles.append((rng, mean, 0.5))  # halber Zyklus
            stack.pop(-2)  # S1 entfernen

    # Rest als halbe Zyklen
    while len(stack) >= 2:
        S0, S1 = stack[-2], stack[-1]
        rng = abs(S1 - S0)
        mean = 0.5 * (S0 + S1)
        cycles.append((rng, mean, 0.5))
        stack.pop()

    return cycles


def analyze_top_damage_cycles(time, signal, m, label, N_top=5):
    """
    Führt Rainflow auf einer Zeitreihe aus,
    berechnet damage_contrib = count * range^m,
    gibt die Top-N Zyklen aus und plottet Signal + markierte Zyklen.

    time   : Zeitvektor
    signal : Momenten-Zeitreihe (bereits ohne Mittelwert, wenn gewünscht)
    m      : Wöhler-Exponent (z.B. 4 für Stahl, 10 für GFK)
    label  : String für Titel/Legende
    """
    # Rainflow-Zyklen
    cycles = rainflow_ranges(signal)
    df = pd.DataFrame(cycles, columns=["range", "mean", "count"])

    # Ermüdungsbeitrag pro Zyklus (ohne Normierung, kein DEL)
    df["damage_contrib"] = df["count"] * (df["range"] ** m)

    # Gesamtschaden für relative Beiträge
    total_damage = df["damage_contrib"].sum()

    # Top-N Zyklen nach Schaden
    df_top = df.sort_values("damage_contrib", ascending=False).head(N_top).copy()
    df_top["damage_frac"] = df_top["damage_contrib"] / total_damage

    print(f"\n===== Top {N_top} damage cycles for {label} =====")
    print(df_top[["range", "mean", "count", "damage_contrib", "damage_frac"]])

    # Zeitreihe + Top-Zyklen plotten
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(time, signal, label=f"{label} signal")

    colors = ["r", "g", "b", "c", "m", "y"]

    for (idx, row), color in zip(df_top.iterrows(), colors):
        rng = row["range"]
        mean = row["mean"]

        # Approx. min/max-Werte des Zyklus
        max_val = mean + rng / 2.0
        min_val = mean - rng / 2.0

        # Nächstgelegene Punkte in der Zeitreihe finden
        idx_min = int(np.argmin(np.abs(signal - min_val)))
        idx_max = int(np.argmin(np.abs(signal - max_val)))

        ax.plot(time[idx_min], signal[idx_min], "o", color=color)
        ax.plot(time[idx_max], signal[idx_max], "o", color=color)
        ax.plot(
            [time[idx_min], time[idx_max]],
            [signal[idx_min], signal[idx_max]],
            "--",
            color=color,
            label=f"Cycle range={rng:.1f}, dmg={row['damage_frac']*100:.1f}%",
        )

    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Moment [kN-m]")
    ax.set_title(f"Top damage cycles highlighted – {label}\nU={U_demo} m/s, Seed={seed_demo}")
    ax.legend()
    plt.tight_layout()


# ---------------------------------------------------------
# Hauptteil
# ---------------------------------------------------------

def main():
    filepath = os.path.join(RESULTS_DIR, FILENAME)

    if not os.path.exists(filepath):
        print(f"❌ Datei nicht gefunden: {filepath}")
        return

    print(f"📂 Lese {filepath}")
    of = FASTOutputFile(filepath)
    df = of.toDataFrame()

    # Rohdaten
    time = df["Time_[s]"].values
    tower_moment = df[TWR_CHANNEL].values
    blade_moment = df[BLADE_CHANNEL].values

    # Transienten abschneiden
    mask = time >= t_start
    time_cut = time[mask]
    tower_cut = tower_moment[mask]
    blade_cut = blade_moment[mask]

    # Mittelwert entfernen (optional, üblich bei Ermüdung)
    tower_cut = tower_cut - np.mean(tower_cut)
    blade_cut = blade_cut - np.mean(blade_cut)

    # Analyse: Blade Root
    analyze_top_damage_cycles(
        time_cut,
        blade_cut,
        m=m_blade,
        label="Blade root bending moment",
        N_top=N_top,
    )

    # Analyse: Tower Base
    analyze_top_damage_cycles(
        time_cut,
        tower_cut,
        m=m_tower,
        label="Tower base bending moment",
        N_top=N_top,
    )

    plt.show()


if __name__ == "__main__":
    main()
