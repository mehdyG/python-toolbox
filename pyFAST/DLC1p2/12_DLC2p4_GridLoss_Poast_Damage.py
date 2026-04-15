import os
import re
import glob
import math
import numpy as np
import pandas as pd
from pCrunch import read, Crunch, FatigueParams
from pyFAST.input_output import FASTInputFile

# --------------------------------------------------
# User settings
# --------------------------------------------------
#/home/Mehdy/python-toolbox/pyFAST/DLC1p2
RESULTS_DIR = "DLC2p4_OF_results"

# fault window
t1 = 200.0
t2 = 220.0      # change to 210.0 or 220.0 if needed

# IEC fallback for loss of electrical network connection
events_per_year = 20
lifetime_years = 20

# Weibull parameters
A = 8.86        # scale parameter
k = 2.0         # shape parameter

# Tower Base geometry und Material
D = 6.0
t = 0.027
d = D - 2*t

I = np.pi/64 * (D**4 - d**4)
y = D/2

# kN·m → N·m berücksichtigen
load2stress_tower = (y / I) * 1e3

# -----------------------------------------
# Choose an S-N curve assumption
# Example: welded steel detail with
# Delta_sigma_C = 80 MPa at 2e6 cycles
# -----------------------------------------
m_tower = 4
sigma_c = 80e6      # [Pa]
N_ref = 2e6
C_tower = N_ref * sigma_c**m_tower

############## Blade Material und Geometry ###################
##############################################################

# --------------------------------------------------
# FILES
# --------------------------------------------------
#/home/Mehdy/python-toolbox/pyFAST/DLC1p2 ## Relative Address
blade_file = "_NREL5MW_FASTfiles/5MW_Baseline/NRELOffshrBsline5MW_Blade.dat"

# --------------------------------------------------
# READ FAST BLADE FILE
# --------------------------------------------------
blade = FASTInputFile(blade_file).toDataFrame()

# check names once:
print(blade.columns)

# Typical FAST distributed-property columns:
# "BldFlpStff" and "BldEdgStff"
EI_flap_root = float(blade["FlpStff_[Nm^2]"].iloc[0])   # [N m^2]
EI_edge_root = float(blade["EdgStff_[Nm^2]"].iloc[0])   # [N m^2]

# --------------------------------------------------
# GEOMETRY FROM THE ATTACHED PDF
# Root/inboard circular section chord = 3.386 m
# Use y = half thickness = 3.386 / 2
# --------------------------------------------------
y_blade_root = 3.386 / 2.0   # [m]

# --------------------------------------------------
# MATERIALS FROM THE ATTACHED PDF
# flapwise -> Carbon(UD)
# edgewise -> SNL(Triax)
# --------------------------------------------------
E_flap = 114.5e9   # Pa   Carbon(UD), Table 5 / 7
E_edge = 27.7e9    # Pa   SNL(Triax), Table 5

# Fatigue parameters from Table 24
m_flap = 14
m_edge = 10

C_flap_MPa = 1546.0   # Carbon(UD)
C_edge_MPa = 700.0    # SNL(Triax)

# Convert C from MPa to Pa for N = C / sigma^m form
C_flap = (C_flap_MPa * 1e6) ** m_flap
C_edge = (C_edge_MPa * 1e6) ** m_edge

# --------------------------------------------------
# SECTION PROPERTIES FROM FAST EI AND PDF E
# I = EI / E
# Z = I / y
# sigma = M / Z
# load2stress = 1/Z, and *1e3 because RootMyb1 is in kN-m
# --------------------------------------------------
I_flap_root = EI_flap_root / E_flap
I_edge_root = EI_edge_root / E_edge

Z_flap_root = I_flap_root / y_blade_root
Z_edge_root = I_edge_root / y_blade_root

load2stress_flap = 1e3 / Z_flap_root   # [Pa per kN-m]
load2stress_edge = 1e3 / Z_edge_root   # [Pa per kN-m]

print("y_blade_root [m]      =", y_blade_root)
print("I_flap_root [m^4]     =", I_flap_root)
print("I_edge_root [m^4]     =", I_edge_root)
print("Z_flap_root [m^3]     =", Z_flap_root)
print("Z_edge_root [m^3]     =", Z_edge_root)
print("load2stress_flap      =", load2stress_flap)
print("load2stress_edge      =", load2stress_edge)

# --------------------------------------------------
# pCrunch fatigue setup
# Use RootMyb1 for flapwise root bending
# Use RootMxb1 for edgewise root bending, if available in your outputs
# --------------------------------------------------

# --------------------------------------------------
# AFTER pCrunch DAMAGE TABLE IS CREATED:
# convert pCrunch scaled damage to Miner-style damage
# --------------------------------------------------
# Example:
# damage_df["BladeFlapDamage_real"] = damage_df["RootMyb1"] / C_flap
# damage_df["BladeEdgeDamage_real"] = damage_df["RootMxb1"] / C_edge

# fatigue channels
TWR_CH = "TwrBsMyt"
BLD_CH = "RootMyb1"


# -----------------------------------------
# Fatigue channels
# -----------------------------------------
fatigue_channels = {
    "TwrBsMyt": FatigueParams(
        slope=m_tower,
        load2stress=load2stress_tower
    ),
    "RootMyb1": FatigueParams(
        slope=m_flap,
        load2stress=load2stress_flap
    ),
    "RootMxb1": FatigueParams(
        slope=m_edge,
        load2stress=load2stress_edge
    ),
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

# pCrunch damage is proportional to sum(n * sigma^m)
# convert to Miner damage by dividing by C

damage_df["TowerDamage_real"] = damage_df["TwrBsMyt"] / C_tower
damage_df["BladeFlapDamage_real"] = damage_df["RootMyb1"] / C_flap
# damage_df["BladeEdgeDamage_real"] = damage_df["RootMxb1"] / C_edge

# --------------------------------------------------
# Mean over seeds for each wind speed
# --------------------------------------------------
mean_by_U = damage_df.groupby("U")[["TowerDamage_real", "BladeFlapDamage_real"]].mean().reset_index()

# Weibull weights for each wind speed bin
mean_by_U["Prob"] = mean_by_U["U"].apply(lambda u: weibull_bin_prob(u, A, k, du=2.0))

# normalize probabilities over the simulated bins only
mean_by_U["Prob_norm"] = mean_by_U["Prob"] / mean_by_U["Prob"].sum()

print("\nMean damage per event, averaged over seeds:")
print(mean_by_U)

# --------------------------------------------------
# Weighted mean damage per event over wind speeds
# --------------------------------------------------
tower_damage_per_event = (mean_by_U["TowerDamage_real"] * mean_by_U["Prob_norm"]).sum()
blade_damage_per_event = (mean_by_U["BladeFlapDamage_real"] * mean_by_U["Prob_norm"]).sum()

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