import os, glob
from pCrunch import read, Crunch, FatigueParams

RESULTS_DIR = "/home/Mehdy/python-toolbox/pyFAST/DLC1p2/DLC1p2_OF_results"
filelist = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.outb")))

outputs = [read(fp) for fp in filelist]
print("n outputs:", len(outputs))

# IMPORTANT: check channel names as pCrunch sees them
print("Example channels:", outputs[0].channels[:20])

TWR_CH = "TwrBsMyt"    # or "TwrBsMyt_[kN-m]" depending on what you see above
BLD_CH = "RootMyb1"    # or "RootMyb1_[kN-m]"

fc = {
    TWR_CH: FatigueParams(slope=4),
    BLD_CH: FatigueParams(slope=10),
}

mycruncher = Crunch(outputs, trim_data=[60, 600], fatigue_channels=fc)
mycruncher.process_outputs(cores=1)

################ Checking which data are read and Processed ##############
print("DELs:")
print(mycruncher.dels.head())

#print("rows:", len(mycruncher.dels))          # should be 72
#print("index sample:", mycruncher.dels.index[:15])
#print("tail:")
#print(mycruncher.dels.tail())                # last 5 rows

import re
Uvals = sorted({float(re.search(r"_U([0-9.]+)_", s).group(1)) for s in mycruncher.dels.index})
print("Wind speeds:", Uvals)
print(mycruncher.dels.loc[mycruncher.dels.index.str.contains("_U15.0_")])

################# Set Probablity Distribution ####################

WIND_CH = "Wind1VelX"   # or "Wind1VelX_[m/s]" depending on outputs[0].channels

mycruncher.set_probability_wind_distribution(WIND_CH, 8.86, kind="weibull", weibull_k=2.0)
dels_tot, dams_tot = mycruncher.compute_total_fatigue(lifetime=20.0)  # DLC1.2 lifetime scaling
print(dels_tot)
