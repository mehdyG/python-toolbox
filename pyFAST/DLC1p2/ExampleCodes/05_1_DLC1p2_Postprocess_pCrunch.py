import os, re, math, glob
import numpy as np
import pandas as pd
from pyFAST.input_output import FASTOutputFile
from pCrunch import AeroelasticOutput, FatigueParams

def strip_units(ch):
    return re.sub(r"_\[[^\]]+\]$", "", ch)

def weibull_cdf(u, A, k):
    u = np.maximum(u, 0.0)
    return 1.0 - np.exp(-(u/A)**k)

RESULTS_DIR = r"/home/Mehdy/python-toolbox/pyFAST/DLC1p2/DLC1p2_OF_results"

# Channels WITHOUT units (weil du strip_units nutzt)
WIND_CH = "Wind1VelX"
TWR_CH  = "TwrBsMyt"
BLD_CH  = "RootMyb1"

fatigue_channels = {
    TWR_CH: FatigueParams(slope=4, load2stress=3.5e5),
    BLD_CH: FatigueParams(slope=10, load2stress=2.1e5),
}

t0, t1 = 60.0, 600.0

# Weibull (deine Werte)
A_weibull, k_weibull = 10.0, 2.0
dU = 2.0  # bin width wie bei dir (3,5,7,...)

rows = []
outfiles = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.outb")))

for fp in outfiles:
    # Wind speed aus Dateiname holen (output_U3.0_Seed1.outb)
    m = re.search(r"_U([0-9.]+)_Seed([0-9]+)", os.path.basename(fp))
    U = float(m.group(1)) if m else np.nan
    seed = int(m.group(2)) if m else -1

    df = FASTOutputFile(fp).toDataFrame()
    data  = df.to_numpy(dtype=float)
    chans = [strip_units(c) for c in df.columns]

    ao = AeroelasticOutput(data, chans, trim_data=[t0, t1], fatigue_channels=fatigue_channels)
    ao.process()
    d = ao.dels  # dict: {'TwrBsMyt':..., 'RootMyb1':...}

    rows.append({"U": U, "seed": seed, "DEL_Twr": float(d[TWR_CH]), "DEL_Bld": float(d[BLD_CH])})

res = pd.DataFrame(rows)

# 1) Seeds pro Wind-Bin mitteln (DLC1.2: gleiche Wahrscheinlichkeit pro Seed innerhalb Bin)
byU = res.groupby("U")[["DEL_Twr","DEL_Bld"]].mean().reset_index()

# 2) Weibull-Bin-Wahrscheinlichkeiten (Integrale über Bin-Grenzen)
Uvals = byU["U"].to_numpy()
p = weibull_cdf(Uvals + dU/2, A_weibull, k_weibull) - weibull_cdf(Uvals - dU/2, A_weibull, k_weibull)
p = p / p.sum()  # normalisieren

# 3) Lifetime-DEL über Verteilung (klassisch: (Σ p * DEL^m)^(1/m))
m_twr, m_bld = 4, 10
DEL_life_twr = (np.sum(p * (byU["DEL_Twr"].to_numpy()**m_twr)))**(1.0/m_twr)
DEL_life_bld = (np.sum(p * (byU["DEL_Bld"].to_numpy()**m_bld)))**(1.0/m_bld)

print("Lifetime DEL (Tower TwrBsMyt):", DEL_life_twr)
print("Lifetime DEL (Blade RootMyb1):", DEL_life_bld)

