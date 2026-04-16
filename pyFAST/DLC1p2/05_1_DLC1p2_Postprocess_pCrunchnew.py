import os
import re
import glob
import math
import numpy as np
import pandas as pd
from pCrunch import read, Crunch, FatigueParams
from pyFAST.input_output import FASTInputFile

# =========================================================
# SETTINGS
# =========================================================
RESULTS_DIR = "/home/Mehdy/python-toolbox/pyFAST/DLC1p2/DLC1p2_OF_results"
BLADE_FILE  = "/home/Mehdy/python-toolbox/pyFAST/DLC1p2/_NREL5MW_FASTfiles/5MW_Baseline/NRELOffshrBsline5MW_Blade.dat"

# DLC 1.2 usable record
t1 = 60.0
t2 = 600.0

# Weibull parameters
A = 8.86
k = 2.0
lifetime_years = 20.0

# =========================================================
# TOWER PROPERTIES
# =========================================================
# Use tower-root geometry directly
D_tower = 6.0       # m
t_tower = 0.027     # m
d_tower = D_tower - 2.0 * t_tower

I_tower = np.pi / 64.0 * (D_tower**4 - d_tower**4)
y_tower = D_tower / 2.0
Z_tower = I_tower / y_tower

# TwrBsMyt is in kN-m -> convert to Pa
load2stress_tower = 1e3 / Z_tower

# Tower fatigue
m_tower = 4
sigma_ref_tower = 80e6   # Pa
N_ref_tower = 2e6
C_tower = N_ref_tower * sigma_ref_tower**m_tower

# =========================================================
# BLADE PROPERTIES
# =========================================================
blade_df = FASTInputFile(BLADE_FILE).toDataFrame()
print("Blade file columns:")
print(blade_df.columns)

# Root blade stiffness from FAST blade file
EI_flap_root = float(blade_df["FlpStff_[Nm^2]"].iloc[0])
EI_edge_root = float(blade_df["EdgStff_[Nm^2]"].iloc[0])

# Root/inboard circular chord from blade reference model: 3.386 m
# use y = thickness/2 = 3.386/2
y_blade_root = 3.386 / 2.0

# Material assumptions from blade reference model
# flapwise -> Carbon(UD)
# edgewise -> SNL(Triax)
E_flap = 114.5e9   # Pa
E_edge = 27.7e9    # Pa

# Section properties from EI/E
I_flap_root = EI_flap_root / E_flap
I_edge_root = EI_edge_root / E_edge

Z_flap_root = I_flap_root / y_blade_root
Z_edge_root = I_edge_root / y_blade_root

# RootMyb1 / RootMxb1 are in kN-m
load2stress_flap = 1e3 / Z_flap_root
load2stress_edge = 1e3 / Z_edge_root

# Blade fatigue parameters
m_flap = 14
m_edge = 10

# C values from blade reference model fatigue table
# Carbon(UD): b=14, C=1546 MPa
# SNL(Triax): b=10, C=700 MPa
C_flap = (1546e6) ** m_flap
C_edge = (700e6) ** m_edge

print("\nComputed section/material properties:")
print("Tower Z [m^3]           =", Z_tower)
print("Tower load2stress       =", load2stress_tower)
print("Blade flap Z [m^3]      =", Z_flap_root)
print("Blade flap load2stress  =", load2stress_flap)
print("Blade edge Z [m^3]      =", Z_edge_root)
print("Blade edge load2stress  =", load2stress_edge)

# =========================================================
# FATIGUE CHANNELS
# =========================================================
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

# =========================================================
# WEIBULL HELPERS
# =========================================================
def weibull_cdf(u, A, k):
    return 1.0 - math.exp(-(u / A) ** k)

def weibull_bin_prob(u, A, k, du=2.0):
    u1 = max(0.0, u - du / 2.0)
    u2 = u + du / 2.0
    return weibull_cdf(u2, A, k) - weibull_cdf(u1, A, k)

# =========================================================
# READ FILES
# =========================================================
filelist = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.outb")))
print("\nNumber of files:", len(filelist))

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

outputs = [read(fp) for fp in files_df["file"]]

print("\nExample channels from pCrunch:")
print(outputs[0].channels[:25])

# =========================================================
# CRUNCH
# =========================================================
cruncher = Crunch(
    outputs,
    trim_data=[t1, t2],
    fatigue_channels=fatigue_channels
)

cruncher.process_outputs(cores=1)

# Damage table
if hasattr(cruncher, "damage"):
    damage_table = cruncher.damage
elif hasattr(cruncher, "damages"):
    damage_table = cruncher.damages
else:
    raise AttributeError("Could not find damage table in cruncher")

damage_df = damage_table.copy().reset_index(drop=True)
damage_df["U"] = files_df["U"].values
damage_df["Seed"] = files_df["Seed"].values
damage_df["file"] = files_df["file"].values

print("\nDamage table head:")
print(damage_df.head())

# =========================================================
# CONVERT pCrunch DAMAGE -> REAL MINER DAMAGE
# =========================================================
damage_df["TowerDamage_real"]     = damage_df["TwrBsMyt"] / C_tower
damage_df["BladeFlapDamage_real"] = damage_df["RootMyb1"] / C_flap
damage_df["BladeEdgeDamage_real"] = damage_df["RootMxb1"] / C_edge

# =========================================================
# MEAN OVER SEEDS
# =========================================================
mean_by_U = damage_df.groupby("U")[[
    "TowerDamage_real",
    "BladeFlapDamage_real",
    "BladeEdgeDamage_real"
]].mean().reset_index()

# Weibull weighting
mean_by_U["Prob"] = mean_by_U["U"].apply(lambda u: weibull_bin_prob(u, A, k, du=2.0))
mean_by_U["Prob_norm"] = mean_by_U["Prob"] / mean_by_U["Prob"].sum()

print("\nMean damage over seeds:")
print(mean_by_U)

# =========================================================
# WEIGHT OVER WIND SPEEDS
# =========================================================
tower_damage_per_10min = (mean_by_U["TowerDamage_real"]     * mean_by_U["Prob_norm"]).sum()
blade_flap_damage_per_10min = (mean_by_U["BladeFlapDamage_real"] * mean_by_U["Prob_norm"]).sum()
blade_edge_damage_per_10min = (mean_by_U["BladeEdgeDamage_real"] * mean_by_U["Prob_norm"]).sum()

print("\nWeighted damage of one simulated DLC 1.2 record:")
print("Tower      :", tower_damage_per_10min)
print("Blade flap :", blade_flap_damage_per_10min)
print("Blade edge :", blade_edge_damage_per_10min)

# =========================================================
# SCALE TO 20-YEAR LIFETIME
# =========================================================
record_length = t2 - t1                 # 540 s here
seconds_per_year = 365.0 * 24.0 * 3600.0
n_records_per_year = seconds_per_year / record_length

tower_damage_lifetime = tower_damage_per_10min * n_records_per_year * lifetime_years
blade_flap_damage_lifetime = blade_flap_damage_per_10min * n_records_per_year * lifetime_years
blade_edge_damage_lifetime = blade_edge_damage_per_10min * n_records_per_year * lifetime_years

print("\nDLC 1.2 lifetime damage:")
print("Tower      :", tower_damage_lifetime)
print("Blade flap :", blade_flap_damage_lifetime)
print("Blade edge :", blade_edge_damage_lifetime)

# =========================================================
# SAVE
# =========================================================
mean_by_U_path = os.path.join(RESULTS_DIR, "DLC1p2_damage_mean_by_U.csv")
summary_path   = os.path.join(RESULTS_DIR, "DLC1p2_damage_summary.csv")
perfile_path   = os.path.join(RESULTS_DIR, "DLC1p2_damage_per_file.csv")

mean_by_U.to_csv(mean_by_U_path, index=False)
damage_df.to_csv(perfile_path, index=False)

summary_df = pd.DataFrame({
    "Channel": ["Tower", "BladeFlap", "BladeEdge"],
    "Damage_per_record_weighted": [
        tower_damage_per_10min,
        blade_flap_damage_per_10min,
        blade_edge_damage_per_10min
    ],
    "Record_length_s": [record_length, record_length, record_length],
    "Lifetime_years": [lifetime_years, lifetime_years, lifetime_years],
    "Damage_lifetime": [
        tower_damage_lifetime,
        blade_flap_damage_lifetime,
        blade_edge_damage_lifetime
    ],
})

summary_df.to_csv(summary_path, index=False)

print("\nSaved:")
print(mean_by_U_path)
print(perfile_path)
print(summary_path)