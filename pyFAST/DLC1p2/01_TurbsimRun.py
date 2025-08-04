"""Read a TurbSim inp file
Change some parameters like Uref, seed number, .. and run Turbsim

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

    ####################################################################
    #################### Turbsim Running################################
    ####################################################################

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

            # Expected TurbSim output filename (.bts)
            bts_name = out_name.replace('.inp', '.bts')
            bts_path = os.path.join(wind_directory, bts_name)

            # Check if BTS file already exists
            if not os.path.isfile(bts_path):
                # Save input file
                ts_in.write(out_path)

                # Run TurbSim
                run_openfast(wind_directory, fastcall='turbsim',
                            fastfile=out_path, chdir=False)

                print(f"✅ TurbSim run complete: URef={u}, Seed={seed}")

            #else:
                #print(f'Skipping: {bts_name} already exists.')

    ####################################################################
    #################### Turbsim Postprocessing#########################
    ####################################################################

    this_dir = os.path.dirname(os.path.abspath(__file__))
    wind_dir = os.path.join(this_dir, 'Test_Cases/Wind/')

    URefs = [15, 21]        # Choose which wind speeds you want to show
    seeds = [1, 2, 3]           # Choose which seeds to compare

    # --- Loop over selected wind speeds
    for URef in URefs:
        plt.figure(figsize=(10, 5))
        
        for seed in seeds:
            filename = f'TurbSim_U{URef}_Seed{seed}.bts'
            file_path = os.path.join(wind_dir, filename)
            
            if not os.path.exists(file_path):
                print(f"⚠️ File not found: {file_path}")
                continue
            
            # Read BTS file
            ts = TurbSimFile(file_path)

            # Extract wind at hub center (middle of grid)
            
            nz = ts['u'].shape[2]
            ny = ts['u'].shape[3]
            z_idx = nz // 2
            y_idx = ny // 2

            # Extract time series at center point
            u_series = ts['u'][0, :, z_idx, y_idx]  # Shape: (12187,)
            dt = ts['dt']
            time = np.linspace(0, dt * (len(u_series) - 1), len(u_series))

            # Statistics
            mean_u = np.mean(u_series)
            std_u = np.std(u_series)
            TI = std_u / mean_u

            # Plot
            plt.plot(time, u_series, label=f'Seed {seed} | Mean={mean_u:.2f} m/s | TI={TI:.2%}')

        plt.title(f'Wind Speed Time Series at Hub Height (URef = {URef} m/s)')
        plt.xlabel('Time [s]')
        plt.ylabel('Wind Speed [m/s]')
        plt.grid(True)
        plt.legend()
        plt.tight_layout()

        # 🔽 Save figure to file
        output_dir = './results'  # or any folder you want
        os.makedirs(output_dir, exist_ok=True)
        filename = f'wind_timeseries_U{URef}.png'
        plt.savefig(os.path.join(output_dir, filename), dpi=300)

        plt.show()



if __name__ == "__main__":
    main()
