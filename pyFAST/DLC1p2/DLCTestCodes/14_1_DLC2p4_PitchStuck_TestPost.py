import os
import matplotlib.pyplot as plt
from pyFAST.input_output import FASTOutputFile

this_dir = os.path.dirname(os.path.abspath(__file__))

outb_file = os.path.join(
    this_dir,
    "DLC2p4_PitchStuck_OF_results",
    "output_U13.0_Seed1_Yaw+0_Inc+0_PitchStuckB1.outb"
)

df = FASTOutputFile(outb_file).toDataFrame()

t = df["Time_[s]"]

b1 = df["BldPitch1_[deg]"]
b2 = df["BldPitch2_[deg]"]
b3 = df["BldPitch3_[deg]"]

rot_speed = df["RotSpeed_[rpm]"]
gen_power = df["GenPwr_[kW]"]

# Wind speed channel name may differ
if "Wind1VelX_[m/s]" in df.columns:
    wind_speed = df["Wind1VelX_[m/s]"]
elif "HorWindV_[m/s]" in df.columns:
    wind_speed = df["HorWindV_[m/s]"]
else:
    wind_speed = None
    print("⚠️ Wind speed channel not found. Available columns:")
    print(df.columns.tolist())

fault_time = 100.0

fig, axs = plt.subplots(6, 1, figsize=(12, 14), sharex=True)

axs[0].plot(t, b1)
axs[0].set_ylabel("Blade 1 [deg]")
axs[0].set_title("Blade 1 Pitch")

axs[1].plot(t, b2)
axs[1].set_ylabel("Blade 2 [deg]")
axs[1].set_title("Blade 2 Pitch")

axs[2].plot(t, b3)
axs[2].set_ylabel("Blade 3 [deg]")
axs[2].set_title("Blade 3 Pitch")

axs[3].plot(t, rot_speed)
axs[3].set_ylabel("RotSpeed [rpm]")
axs[3].set_title("Rotor Speed")

axs[4].plot(t, gen_power)
axs[4].set_ylabel("GenPwr [kW]")
axs[4].set_title("Generator Power")

if wind_speed is not None:
    axs[5].plot(t, wind_speed)
    axs[5].set_ylabel("Wind [m/s]")
else:
    axs[5].text(0.5, 0.5, "Wind speed channel not found", ha="center", va="center")
    axs[5].set_ylabel("Wind")

axs[5].set_title("Wind Speed")
axs[5].set_xlabel("Time [s]")

for ax in axs:
    ax.axvline(fault_time, linestyle="--", label="Fault time")
    ax.grid(True)
    ax.legend()

plt.tight_layout()
plt.show()