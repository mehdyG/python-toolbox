"""Run OF for different Uref, seed number 
    For DLC 1.2 Calculations
"""


import os
from pyFAST.input_output import FASTInputFile, FASTOutputFile
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
    Servodyn_file = os.path.join(fast_dir, 'NRELOffshrBsline5MW_Onshore_ServoDyn.dat')
    FAST_EXE  = os.path.join(this_dir, '../../../miniconda3/envs/openfast_env/bin/openfast') # Location of a FAST

    output_dir = os.path.join(this_dir, 'DLC2p4_OF_results')
    os.makedirs(output_dir, exist_ok=True)
    SS_output_dir = os.path.join(this_dir, 'PowerCurve_und_SS_Results')

    URefs = np.arange(15, 16, 2)     #(3, 26, 2) V_cutin = 3 m/s to V_cut_out 0 25 m/s [3,5,...,25]
    seeds = [1]      #[1, 2, 3, 4, 5, 6] Different random seeds für DLC 1.2 

    for u in URefs:

        ############# Initialization  #######################
        
        ## Read Data from SS result files ##
        output_filename = f'output_U{u:.1f}.outb'
        SS_output_path = os.path.join(SS_output_dir, output_filename)
        SS_out = FASTOutputFile(SS_output_path).toDataFrame()

        time  = SS_out['Time_[s]']
        power = SS_out['GenPwr_[kW]']   #  kW
        pitch = SS_out['BldPitch1_[deg]']
        gen_speed = SS_out['GenSpeed_[rpm]']
        gen_torque = SS_out['GenTq_[kN-m]']
        OoPDefl =   SS_out['OoPDefl1_[m]']
        IPDefl = SS_out['IPDefl1_[m]']
        Rot_speed = SS_out['RotSpeed_[rpm]']
        ##### Mansche Andere output data zum Zukunft #####
        #### 'TTDspFA_[m]','TTDspSS_[m]', 'TTDspTwst_[deg]' ####

        N = len(time)
        last_n = int(0.05 * N)
        mean_power = np.mean(power[-last_n:])
        mean_pitch = np.mean(pitch[-last_n:])
        mean_speed = np.mean(gen_speed[-last_n:])
        mean_torque = np.mean(gen_torque[-last_n:])
        mean_OoPDefl = np.mean(OoPDefl[-last_n:])
        mean_IPDefl = np.mean(IPDefl[-last_n:])
        mean_Rot_speed = np.mean(Rot_speed[-last_n:])   # [rpm]    
        
        ## Replace SS Data in OF input files ##
        Elastdyn_filename = 'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat'
        Elastdyn_in_file_path = os.path.join(fast_dir, Elastdyn_filename)
        Elastdyn_in = FASTInputFile(Elastdyn_in_file_path)
        Elastdyn_in['OoPDefl'] = mean_OoPDefl       # Elastodyn_file: Initial out-of-plane blade-tip displacement (meters)
        Elastdyn_in['IPDefl'] = mean_IPDefl         # Elastodyn_file: Initial in-plane blade-tip deflection (meters)
        Elastdyn_in['BlPitch(1)'] = mean_pitch      # Elastodyn_file: Blade 1 initial pitch (degrees)
        Elastdyn_in['BlPitch(2)'] = mean_pitch
        Elastdyn_in['BlPitch(3)'] = mean_pitch
        Elastdyn_in['RotSpeed'] = mean_Rot_speed   # Elastodyn_file: Initial or fixed rotor speed (rpm)

        Elastdyn_in.write(Elastdyn_in_file_path)

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

            # Modify Servodyn file
            Servodyn_in = FASTInputFile(Servodyn_file)
            Servodyn_in['TimGenOf'] = 200.0

            output_filename = f'DLC2p4output_U{u:.1f}_Seed{seed}.outb'
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

    # Modify Servodyn file back
    #Servodyn_in = FASTInputFile(Servodyn_file)
    #Servodyn_in['TimGenOf'] = 9999.9

if __name__ == "__main__":
    main()
