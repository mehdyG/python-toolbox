import os
import re
import glob
import math
import numpy as np
import pandas as pd
from pCrunch import read, Crunch, FatigueParams

# --------------------------------------------------
# User settings
# --------------------------------------------------
RESULTS_DIR = "/home/Mehdy/python-toolbox/pyFAST/DLC1p2/DLC2p4_OF_results"

# fault window
t1 = 200.0
t2 = 205.0      # change to 210.0 or 220.0 if needed

# IEC fallback for loss of electrical network connection
events_per_year = 20
lifetime_years = 20

# Weibull parameters
A = 8.86        # scale parameter
k = 2.0         # shape parameter

# fatigue channels
TWR_CH = "TwrBsMyt"
BLD_CH = "RootMyb1"

fatigue_channels = {
    TWR_CH: FatigueParams(slope=4),
    BLD_CH: FatigueParams(slope=10),
}

# --------------------------------------------------
# Helper: Weibull bin probability around each discrete wind speed
# --------------------------------------------------
def weibull_cdf(u, A, k):
    return 1.0 - math.exp(-(u / A) ** k)

def weibull_bin_prob(u, A, k, du=2.0):
    u1 = max(0.0, u - du / 2.0)
    u2 = u + du / 2.0
    return weibull_cdf(u2, A, k) - weibull_cdf(u1, A, k)

# --------------------------------------------------
# Read files
# --------------------------------------------------
filelist = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.outb")))
print("Number of files:", len(filelist))

# extract U and Seed from file name
rows = []
for fp in filelist:
    base = os.path.basename(fp)
    m = re.search(r"_U([0-9.]+)_Seed([0-9]+)\.outb$", base)
    if m is None:
        print("Skipped:", base)
        continue

    U = float(m.group(1))
    seed = int(m.group(2))
    rows.append({"file": fp, "U": U, "Seed": seed})

files_df = pd.DataFrame(rows)
print("\nFiles found:")
print(files_df.head())

# --------------------------------------------------
# Read outputs fresh
# --------------------------------------------------
outputs = [read(fp) for fp in files_df["file"]]

# --------------------------------------------------
# Crunch
# --------------------------------------------------
cruncher = Crunch(
    outputs,
    trim_data=[t1, t2],
    fatigue_channels=fatigue_channels
)

cruncher.process_outputs(cores=1)

# --------------------------------------------------
# Find the damage table from pCrunch
# --------------------------------------------------
damage_table = None

if hasattr(cruncher, "damage"):
    damage_table = cruncher.damage
elif hasattr(cruncher, "damages"):
    damage_table = cruncher.damages
else:
    raise AttributeError("Could not find damage table in cruncher. Check: dir(cruncher)")

print("\nDamage table head:")
print(damage_table.head())

# --------------------------------------------------
# Attach file info to damage table
# Assumption: rows are in same order as outputs/filelist
# --------------------------------------------------
damage_df = damage_table.copy()
damage_df = damage_df.reset_index(drop=True)
damage_df["U"] = files_df["U"].values
damage_df["Seed"] = files_df["Seed"].values
damage_df["file"] = files_df["file"].values

print("\nDamage with U and Seed:")
print(damage_df[[TWR_CH, BLD_CH, "U", "Seed"]].head())

# --------------------------------------------------
# Mean over seeds for each wind speed
# --------------------------------------------------
mean_by_U = damage_df.groupby("U")[[TWR_CH, BLD_CH]].mean().reset_index()

# Weibull weights for each wind speed bin
mean_by_U["Prob"] = mean_by_U["U"].apply(lambda u: weibull_bin_prob(u, A, k, du=2.0))

# normalize probabilities over the simulated bins only
mean_by_U["Prob_norm"] = mean_by_U["Prob"] / mean_by_U["Prob"].sum()

print("\nMean damage per event, averaged over seeds:")
print(mean_by_U)

# --------------------------------------------------
# Weighted mean damage per event over wind speeds
# --------------------------------------------------
tower_damage_per_event = (mean_by_U[TWR_CH] * mean_by_U["Prob_norm"]).sum()
blade_damage_per_event = (mean_by_U[BLD_CH] * mean_by_U["Prob_norm"]).sum()

print("\nWeighted damage per event:")
print("Tower :", tower_damage_per_event)
print("Blade :", blade_damage_per_event)

# --------------------------------------------------
# Scale to yearly and lifetime damage
# --------------------------------------------------
tower_damage_per_year = tower_damage_per_event * events_per_year
blade_damage_per_year = blade_damage_per_event * events_per_year

tower_damage_lifetime = tower_damage_per_year * lifetime_years
blade_damage_lifetime = blade_damage_per_year * lifetime_years

print("\nLifetime DLC 2.4 grid-loss damage:")
print("Tower :", tower_damage_lifetime)
print("Blade :", blade_damage_lifetime)

# --------------------------------------------------
# Save outputs
# --------------------------------------------------
mean_by_U_path = os.path.join(RESULTS_DIR, "DLC2p4_damage_mean_by_U.csv")
summary_path = os.path.join(RESULTS_DIR, "DLC2p4_damage_summary.csv")

mean_by_U.to_csv(mean_by_U_path, index=False)

summary_df = pd.DataFrame({
    "Channel": [TWR_CH, BLD_CH],
    "Damage_per_event_weighted": [tower_damage_per_event, blade_damage_per_event],
    "Events_per_year": [events_per_year, events_per_year],
    "Lifetime_years": [lifetime_years, lifetime_years],
    "Damage_per_year": [tower_damage_per_year, blade_damage_per_year],
    "Damage_lifetime": [tower_damage_lifetime, blade_damage_lifetime],
})

summary_df.to_csv(summary_path, index=False)

print("\nSaved:")
print(mean_by_U_path)
print(summary_path)