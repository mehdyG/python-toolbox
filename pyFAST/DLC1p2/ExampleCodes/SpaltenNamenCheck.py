import os
import numpy as np
from pyFAST.input_output import FASTOutputFile
from pCrunch import AeroelasticOutput

RESULTS_DIR = r"DLC1p2_OF_results"

URefs = np.arange(3, 26, 2)
seeds = [1,2,3,4,5,6]
trim_t0, trim_t1 = 60.0, None

testfile = os.path.join(RESULTS_DIR, f"output_U{URefs[0]:.1f}_Seed{seeds[0]}.outb")

df = FASTOutputFile(testfile).toDataFrame()

# Wichtig: alles numerisch machen (sonst isnan-Fehler)
data = df.to_numpy(dtype=float)
chans = list(df.columns)

ao = AeroelasticOutput(data, chans)

print(" Channels:", chans)
