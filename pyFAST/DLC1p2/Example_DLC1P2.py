"""Read a TurbSim inp file
Change some parameters like Uref, seed number, .. and run Turbsim

"""


import os
from pyFAST.input_output import FASTInputFile
from rosco.toolbox.utilities import run_openfast
import subprocess
import numpy as np



def main():
    this_dir = os.path.dirname(os.path.abspath(__file__))

    # Load existing TurbSim input:
    filename = 'TurbSim_DLC1p2NREL5MW_Land.inp'
    ts_in = FASTInputFile(filename)

    # Change input parameters based on NREL 5MW 
    ts_in['NumGrid_Z']      = 41            # Turbsim Guide: NumGrid_Z = GridHeight/mean_Chord
    ts_in['NumGrid_Y']      = 41            # Turbsim Guide: NumGrid_Y = GridWidth/mean_Chord
    ts_in['TimeStep']       = 0.05          # s 
    ts_in['AnalysisTime']   = 630           # s 30 s over to avoid initial transient effects 
    ts_in['UsableTime']     = 600           # s
    ts_in['HubHt']          = 90            # 90 m, 
    ts_in['GridHeight']     = 140           # GridHeight = 1.1 * Rotor diameter = 1.1 * 126 m =- 140 m
    ts_in['GridWidth']      = 140           # GridWidth = 1.1 * Rotor diameter
    ts_in['TurbModel']      = "IECKAI"      
    ts_in['NIECstandard']   = "1-Ed3"   
    ts_in['IECturbc']       = "B"           # IECturbc
    ts_in['IEC_WindType']   = "NTM"         
    ts_in['WindProfileType'] = "IEC"     
    ts_in['RefHt']          = 90            # Hub Height


    # --- Prepare and Run TurbSim
    # Define parameters
    URefs = np.arange(3, 26, 2)     # V_cutin = 3 m/s to V_cut_out 0 25 m/s [3,5,...,25]
    seeds = [1, 2, 3, 4, 5, 6]      # Different random seeds für DLC 1.2 

    for u in URefs:
        for seed in seeds:
            

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
