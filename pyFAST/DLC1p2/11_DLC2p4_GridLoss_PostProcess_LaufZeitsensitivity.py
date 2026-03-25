import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
from pCrunch import read, Crunch, FatigueParams
from pyFAST.input_output.fast_output_file import FASTOutputFile



# --------------------------------------------------
# Folder with DLC 2.4 OpenFAST results
# --------------------------------------------------
RESULTS_DIR = "/home/Mehdy/python-toolbox/pyFAST/DLC1p2/DLC2p4_OF_results"
filelist = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.outb")))

outputs = [read(fp) for fp in filelist]
print("Number of files:", len(outputs))
print("Example channels:", outputs[0].channels[:20])

fp = filelist[0]
df = FASTOutputFile(fp).toDataFrame()
print(df.head())

time = df["Time_[s]"].values

for dur in [5, 10, 20]:
    t1 = 200.0
    t2 = 200.0 + dur
    mask = (time >= t1) & (time <= t2)

    print(f"\nDuration = {dur}")
    print("Requested:", t1, "to", t2)
    print("Actual    :", time[mask].min(), "to", time[mask].max())
    print("Points     :", mask.sum())

# Debugging
#for i, out in enumerate(outputs[:5]):
#    time = out["Time"]
#    print(i, time.min(), time.max())



# --------------------------------------------------
# Choose fatigue channels
# Check names first from outputs[0].channels
# --------------------------------------------------
TWR_CH = "TwrBsMyt"     # or "TwrBsMyt_[kN-m]"
BLD_CH = "RootMyb1"     # or "RootMyb1_[kN-m]"

fc = {
    TWR_CH: FatigueParams(slope=4),
    BLD_CH: FatigueParams(slope=10),
}

# --------------------------------------------------
# Sensitivity durations [s]
# Fault starts at t = 200 s
# --------------------------------------------------
fault_time = 200.0
durations = [20, 10, 5]

results_list = []
i= 0

for dur in durations:
    print(f"\n=== Processing duration = {dur} s ===")

    # trim only the fault window
    t1 = fault_time
    t2 = fault_time + dur


    cruncher = Crunch(
        outputs,
        trim_data=[t1, t2],
        fatigue_channels=fc
    )

    # === Time Plots ======
    markers = ["o", "*", "s"]
    linestyles = ["-", "--", ":"]
    colors = ["blue", "red", "green"]

    time = outputs[0]["Time"]
    twr = outputs[0]["TwrBsMyt"]

    mask = (time >= t1) & (time <= t2)
    plt.plot(time[mask], twr[mask],
             marker=markers[i],
             linestyle=linestyles[i],
             color=colors[i],
             markevery=50,
             label=f"{dur}s")
    i = i+1

    #plt.plot(time[mask], twr[mask], label=f"{dur}s window")

    #===============================
 
    cruncher.process_outputs(cores=1)

    print("DELs:")
    print(cruncher.dels.head())

    # wind probability
    WIND_CH = "Wind1VelX"   # or "Wind1VelX_[m/s]"
    cruncher.set_probability_wind_distribution(
        WIND_CH,
        8.86,
        kind="weibull",
        weibull_k=2.0
    )

    dels_tot, dams_tot = cruncher.compute_total_fatigue(lifetime=20.0)

    print(f"\nTotal DELs for duration {dur} s:")
    print(dels_tot)

    print(f"\nTotal damage for duration {dur} s:")
    print(dams_tot)

    # save results in simple table form
    row = {"Duration_s": dur}

    for ch in dels_tot.index:
        row[f"DEL_{ch}"] = dels_tot.loc[ch]

    for ch in dams_tot.index:
        row[f"Damage_{ch}"] = dams_tot.loc[ch]

    results_list.append(row)

# === Time Plots Legends ======
plt.legend()
plt.xlabel("Time [s]")
plt.ylabel("TwrBsMyt")
plt.title("Check of time windows")
plt.grid()
plt.show()
# --------------------------------------------------
# Final comparison table
# --------------------------------------------------
df_results = pd.DataFrame(results_list)

print("\n==============================")
print("Sensitivity comparison table")
print("==============================")
print(df_results)

# optional: save to csv
csv_path = os.path.join(RESULTS_DIR, "DLC2p4_sensitivity_5_10_20s.csv")
df_results.to_csv(csv_path, index=False)
print(f"\nSaved results to: {csv_path}")

# --------------------------------------------------
# Find correct DEL column names automatically
# --------------------------------------------------
print("Available result columns:")
print(df_results.columns.tolist())
print(df_results.head())

# --------------------------------------------------
# Extract Tower and Blade values from the stored Series
# --------------------------------------------------
twr_del = []
bld_del = []
twr_dam = []
bld_dam = []

for i in range(len(df_results)):
    del_weighted = df_results.loc[i, "DEL_Weighted"]
    dam_weighted = df_results.loc[i, "Damage_Weighted"]

    twr_del.append(del_weighted["TwrBsMyt"])
    bld_del.append(del_weighted["RootMyb1"])

    twr_dam.append(dam_weighted["TwrBsMyt"])
    bld_dam.append(dam_weighted["RootMyb1"])

# --------------------------------------------------
# Plot DEL vs Duration
# --------------------------------------------------

plt.figure(figsize=(8, 5))
plt.plot(df_results["Duration_s"], twr_del, marker="o", label="TwrBsMyt")
plt.plot(df_results["Duration_s"], bld_del, marker="o", label="RootMyb1")

plt.xlabel("Fault duration [s]")
plt.ylabel("Weighted DEL")
plt.title("DLC 2.4 Grid Loss: DEL vs Duration")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

# --------------------------------------------------
# Plot Damage vs Duration
# --------------------------------------------------
plt.figure(figsize=(8, 5))
plt.plot(df_results["Duration_s"], twr_dam, marker="o", label="TwrBsMyt")
plt.plot(df_results["Duration_s"], bld_dam, marker="o", label="RootMyb1")

plt.xlabel("Fault duration [s]")
plt.ylabel("Weighted fatigue damage")
plt.title("DLC 2.4 Grid Loss: Damage vs Duration")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()