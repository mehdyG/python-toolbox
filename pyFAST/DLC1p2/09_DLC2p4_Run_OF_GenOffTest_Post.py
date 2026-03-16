# Lies eine OpenFAST .outb Datei und plottet ALLES in EINER Figure (gestapelt, gleiche Zeitachse):
# - Generator Drehmoment (GenTq)
# - Generator Drehzahl (GenSpeed)
# - Rotor Drehmoment (RotTorq)
# - Rotor Drehzahl (RotSpeed)
# - Pitch (collective/avg) unten

import os
import matplotlib.pyplot as plt
from pyFAST.input_output.fast_output_file import FASTOutputFile

outb_path = "/home/Mehdy/python-toolbox/pyFAST/DLC1p2/DLC2p4_OF_results/DLC2p4output_U15.0_Seed1.outb"
assert os.path.isfile(outb_path), f"File not found: {outb_path}"

df = FASTOutputFile(outb_path).toDataFrame()

def pick_col(df, candidates):
    """Pick first matching column (exact case-insensitive), else 'contains'."""
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    for c in df.columns:
        cl = c.lower()
        if any(cand.lower() in cl for cand in candidates):
            return c
    return None

# Time
t_col = pick_col(df, ["Time", "Time_[s]", "Time (s)", "time"])
if t_col is None:
    raise KeyError("Time channel not found. Columns:\n" + "\n".join(df.columns))
t = df[t_col].to_numpy()

# Main signals
gentq_col  = pick_col(df, ["GenTq", "GenTq_[kN-m]", "GenTq_[N-m]"])
genspd_col = pick_col(df, ["GenSpeed", "GenSpd", "GenSpeed_[rpm]", "GenSpeed_[rad/s]"])
rottq_col  = pick_col(df, ["RotTorq", "RtTorq", "RotorTorque", "RotTorq_[kN-m]", "RotTorq_[N-m]"])
rotspd_col = pick_col(df, ["RotSpeed", "RtSpeed", "RotorSpeed", "RotSpeed_[rpm]", "RotSpeed_[rad/s]"])

missing = [name for name, col in [
    ("GenTq", gentq_col),
    ("GenSpeed", genspd_col),
    ("RotTorq", rottq_col),
    ("RotSpeed", rotspd_col),
] if col is None]
if missing:
    raise KeyError("Missing channels: " + ", ".join(missing) + "\nColumns:\n" + "\n".join(df.columns))

# Pitch: collective if possible
p1 = pick_col(df, ["BldPitch1", "Pitch1", "BldPitch1_[deg]"])
p2 = pick_col(df, ["BldPitch2", "Pitch2", "BldPitch2_[deg]"])
p3 = pick_col(df, ["BldPitch3", "Pitch3", "BldPitch3_[deg]"])
p0 = pick_col(df, ["Pitch", "BldPitch", "PCPitch", "Pitch_[deg]"])

if p1 and p2 and p3:
    pitch = (df[p1].to_numpy() + df[p2].to_numpy() + df[p3].to_numpy()) / 3.0
    pitch_label = "Pitch collective (avg) [deg]"
elif p1:
    pitch = df[p1].to_numpy()
    pitch_label = f"{p1}"
elif p0:
    pitch = df[p0].to_numpy()
    pitch_label = f"{p0}"
else:
    raise KeyError("Pitch channels not found. Columns:\n" + "\n".join(df.columns))

# One figure, stacked axes
fig, axes = plt.subplots(5, 1, sharex=True, figsize=(11, 10))

axes[0].plot(t, df[gentq_col].to_numpy())
axes[0].set_ylabel(gentq_col); axes[0].grid(True)

axes[1].plot(t, df[genspd_col].to_numpy())
axes[1].set_ylabel(genspd_col); axes[1].grid(True)

axes[2].plot(t, df[rottq_col].to_numpy())
axes[2].set_ylabel(rottq_col); axes[2].grid(True)

axes[3].plot(t, df[rotspd_col].to_numpy())
axes[3].set_ylabel(rotspd_col); axes[3].grid(True)

axes[4].plot(t, pitch)
axes[4].set_ylabel(pitch_label); axes[4].set_xlabel("Time [s]"); axes[4].grid(True)

fig.suptitle("DLC2.4: Gen/Rotor signals + Pitch vs Time", y=0.98)
plt.tight_layout()
plt.show()
