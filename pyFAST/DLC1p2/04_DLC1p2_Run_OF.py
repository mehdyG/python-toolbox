"""Run OF for different Uref, seed number 
    For DLC 1.2 Calculations
"""


import os
from pyFAST.input_output import FASTInputFile
from rosco.toolbox.utilities import run_openfast
import subprocess
import numpy as np

import matplotlib.pyplot as plt
from pyFAST.input_output import TurbSimFile



def main():
    this_dir = os.path.dirname(os.path.abspath(__file__))

    ######################   Read Turbsim Generated Files to run OF   #########################

    # Define parameters

    wind_dir = os.path.join(this_dir, 'Test_Cases/Wind/')
    fast_dir = os.path.join(this_dir, '_NREL5MW_FASTfiles/5MW_Land_DLL_WTurb')
    fst_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.fst')
    inflow_file = os.path.join(fast_dir, '../5MW_Baseline/NRELOffshrBsline5MW_InflowWind.dat')
    FAST_EXE  = os.path.join(this_dir, '../../../miniconda3/envs/openfast_env/bin/openfast') # Location of a FAST

    output_dir = os.path.join(this_dir, 'DLC1p2_OF_results')
    os.makedirs(output_dir, exist_ok=True)

    URefs = np.arange(3, 26, 2)     # V_cutin = 3 m/s to V_cut_out 0 25 m/s [3,5,...,25]
    seeds = [1, 2, 3, 4, 5, 6]      # Different random seeds für DLC 1.2 

    for u in URefs:

        ############# Initialization  #######################
        Elastdyn_filename = 'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat'
        Elastdyn_in_file_path = os.path.join(fast_dir, Elastdyn_filename)
        Elastdyn_in = FASTInputFile(inflow_file)
        Elastdyn_in['OoPDefl'] = init_OoPDefl

        for seed in seeds:
            filename = f'TurbSim_U{u}_Seed{seed}.bts'
            Turb_in_file_path = os.path.join(wind_dir, filename)
            
            if not os.path.exists(Turb_in_file_path):
                print(f"⚠️ File not found: {Turb_in_file_path}")
                continue
            
            # Modify inflow file
            inflow_in = FASTInputFile(inflow_file)
            inflow_in['WindType'] = 3
            inflow_in['FileName_BTS'] = '"' + Turb_in_file_path + '"'   
            inflow_in.write(inflow_file)

            output_filename = f'output_U{u:.1f}_Seed{seed}.outb'
            output_path = os.path.join(output_dir, output_filename)

            
            # Only run OpenFAST if output file doesn't exist
        
            if not os.path.exists(output_path):
                print(f'➡️ Running OpenFAST for URef = {u} m/s und Seed = {seed}')

                # Run OpenFAST
                run_openfast(fast_dir, fastfile=fst_file, fastcall=FAST_EXE, chdir=True)

                # # Output filename
                out_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.outb')

                if not os.path.exists(out_file):
                     print(f"❌ Output file not found for URef = {u} m/s und Seed = {seed}")
                     continue

                # Save individual output file
                os.rename(out_file, os.path.join(output_dir, output_filename))

    inflow_in = FASTInputFile(inflow_file)
    inflow_in['WindType'] = 1   
    inflow_in.write(inflow_file)

if __name__ == "__main__":
    main()
