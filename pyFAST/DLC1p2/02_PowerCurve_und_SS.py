import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pyFAST.input_output import FASTInputFile, FASTOutputFile
from rosco.toolbox.utilities import run_openfast

def main():

    # ---------------------------
    # Configuration
    # ---------------------------
    this_dir = os.path.dirname(os.path.abspath(__file__))
    fast_dir = os.path.join(this_dir, '_NREL5MW_FASTfiles/5MW_Land_DLL_WTurb')
    fst_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.fst')
    inflow_file = os.path.join(fast_dir, '../5MW_Baseline/NRELOffshrBsline5MW_InflowWind.dat')

    wind_speeds = np.arange(3, 26, 1)  # Wind speeds from 3 to 25 m/s
    result_list = []

    output_dir = os.path.join(this_dir, 'PowerCurve_und_SS_Results')
    os.makedirs(output_dir, exist_ok=True)

    # ---------------------------
    # Run for each wind speed
    # ---------------------------
    for V in wind_speeds:
        
        # Modify inflow file
        inflow_in = FASTInputFile(inflow_file)
        inflow_in['HWindSpeed'] = V
        inflow_in.write(inflow_file)

        # Run OpenFAST
        FAST_EXE  = os.path.join(this_dir, '../../../miniconda3/envs/openfast_env/bin/openfast') # Location of a FAST
        

        output_filename = f'output_U{V:.1f}.outb'
        output_path = os.path.join(output_dir, output_filename)

        # Only run OpenFAST if output file doesn't exist
        
        if not os.path.exists(output_path):
            print(f'➡️ Running OpenFAST for URef = {V} m/s')

            # Run OpenFAST
            run_openfast(fast_dir, fastfile=fst_file, fastcall=FAST_EXE, chdir=True)

            # # Output filename
            out_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.outb')

            # if not os.path.exists(out_file):
            #     print(f"❌ Output file not found for URef = {V}")
            #     continue

            # Save individual output file
            os.rename(out_file, os.path.join(output_dir, f'output_U{V:.1f}.outb'))

        # Read results
        out = FASTOutputFile(output_path).toDataFrame()
        #print(out.keys())
        
        # Rot_speed = out['RotSpeed_[rpm]']
        # V_wind = out['Wind1VelX_[m/s]']
        #input("Press Enter to continue...")

        # Compute steady-state values
        time  = out['Time_[s]']
        power = out['GenPwr_[kW]']   #  kW
        pitch = out['BldPitch1_[deg]']
        gen_speed = out['GenSpeed_[rpm]']
        gen_torque = out['GenTq_[kN-m]']

        #### time plotting of variables for debugging###

        #plt.plot(time, gen_speed,
        #         marker='o', linestyle='-', label='User OpenFAST gen_speed[rpm]')
        #plt.show()

        # Compute means over last 5% of simulation
        N = len(time)
        last_n = int(0.05 * N)
        mean_power = np.mean(power[-last_n:])
        mean_pitch = np.mean(pitch[-last_n:])
        mean_speed = np.mean(gen_speed[-last_n:])
        mean_torque = np.mean(gen_torque[-last_n:])

        # Save result
        result_list.append([V, mean_power, mean_pitch, mean_speed, mean_torque])

    
    # ---------------------------
    # Save CSV
    # ---------------------------
    df_user = pd.DataFrame(result_list, columns=['WindSpeed (m/s)', 'MeanPower (kW)', 'MeanPitch (deg)', 'MeanGenSpeed (rpm)', 'MeanGenTorque (kN-m)'])
    csv_path = os.path.join(output_dir, 'PowerCurve_und_SS_Results.csv')
    df_user.to_csv(csv_path, index=False)
    print(f'✅ Results saved to {csv_path}')
    

if __name__ == "__main__":
    main()