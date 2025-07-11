"""Read a TurbSim inp file
Change some parameters like Uref, seed number, .. and run Turbsim

"""


import os
from pyFAST.input_output import FASTInputFile
from rosco.toolbox.utilities import run_openfast
import subprocess

def main():
    this_dir = os.path.dirname(os.path.abspath(__file__))

    # --- Prepare and Run TurbSim
    # Define parameters
    URefs = [10.0, 20.0]         # Different wind speeds
    seeds = [1, 2]                  # Different random seeds

    for u in URefs:
        for seed in seeds:
            # Load existing TurbSim input:
            filename = 'TurbSim_DLC1p2NREL5MW_Land.inp'
            ts_in = FASTInputFile(filename)

            # Modify parameters
            ts_in['URef'] = u
            ts_in['RandSeed1'] = seed

            # Output filenames
            wind_directory = os.path.join(this_dir, 'Test_Cases/Wind/')
            out_name = f'TurbSim_U{int(u)}_Seed{seed}.inp'
            out_path = os.path.join(wind_directory, out_name)
            ts_in.write(out_path)

            # Define paths
            
            turbsim_infile = out_name

            # Run TurbSim
            run_openfast(wind_directory, fastcall='turbsim',
             fastfile=out_path, chdir=False)

            print(f"✅ TurbSim run complete: URef={u}, Seed={seed}")

if __name__ == "__main__":
    main()
