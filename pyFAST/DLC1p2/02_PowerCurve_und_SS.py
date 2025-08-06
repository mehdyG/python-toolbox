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

        # Compute means over last 30% of simulation
        N = len(time)
        last_n = int(0.3 * N)
        mean_power = np.mean(power[-last_n:])
        mean_pitch = np.mean(pitch[-last_n:])
        mean_speed = np.mean(gen_speed[-last_n:])

        # Save result
        result_list.append([V, mean_power, mean_pitch, mean_speed])

    
    # ---------------------------
    # Save CSV
    # ---------------------------
    df_user = pd.DataFrame(result_list, columns=['WindSpeed (m/s)', 'MeanPower (kW)', 'MeanPitch (deg)', 'MeanGenSpeed (rpm)'])
    csv_path = os.path.join(output_dir, 'PowerCurve_und_SS_Results.csv')
    df_user.to_csv(csv_path, index=False)
    print(f'✅ Results saved to {csv_path}')

    # # ---------------------------
    # # Plot Power Curve
    # # ---------------------------
    # plt.figure(figsize=(8, 5))
    # plt.plot(df['WindSpeed (m/s)'], df['MeanPower (kW)'], 'o-', label='Power Curve')
    # plt.xlabel('Wind Speed (m/s)')
    # plt.ylabel('Mean Power (kW)')
    # plt.title('NREL 5MW Power Curve')
    # plt.grid(True)
    # plt.tight_layout()

    

#     # Replace this with your actual OpenFAST simulation results
# user_data = {
#     'WindSpeed (m/s)': list(range(3, 26)),
#     'MeanPower (kW)': [0, 80, 290, 610, 980, 1480, 2180, 2980, 3880, 4580, 4880, 4980, 5000, 5000, 5000, 5000, 5000, 5000, 5000, 5000, 5000, 5000, 5000],
#     'MeanPitch (deg)': [0]*23,
#     'MeanGenSpeed (rpm)': [0, 250, 400, 600, 800, 950, 1050, 1150, 1190, 1200, 1210, 1215, 1215, 1215, 1215, 1215, 1215, 1215, 1215, 1215, 1215, 1215, 1215]
# }


    #df_user = pd.DataFrame(user_data)

    # NREL 5MW Reference data (digitized)
    nrel_wind_speeds = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13] + list(range(14, 26))
    nrel_power_output = [0, 100, 300, 600, 1000, 1500, 2200, 3000, 3900, 4600, 4900] + [5000]*12
    nrel_gen_speed = [0, 200, 350, 500, 700, 900, 1050, 1150, 1190, 1200, 1210] + [1215]*12
    nrel_pitch = [0]*11 + [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24]

    df_nrel = pd.DataFrame({
        'WindSpeed (m/s)': nrel_wind_speeds,
        'Power (kW)': nrel_power_output,
        'GenSpeed (rpm)': nrel_gen_speed,
        'Pitch (deg)': nrel_pitch
    })

    # Power Curve
    plt.figure(figsize=(8, 5))
    plt.plot(df_user['WindSpeed (m/s)'], df_user['MeanPower (kW)'], 'o-', label='User OpenFAST')
    plt.plot(df_nrel['WindSpeed (m/s)'], df_nrel['Power (kW)'], 's--', label='NREL 5MW Reference')
    plt.xlabel('Wind Speed (m/s)')
    plt.ylabel('Power Output (kW)')
    plt.title('Power Curve Comparison')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig('PowerCurve_with_NREL.png')

    # Generator Speed
    plt.figure(figsize=(8, 5))
    plt.plot(df_user['WindSpeed (m/s)'], df_user['MeanGenSpeed (rpm)'], 'o-', label='User OpenFAST')
    plt.plot(df_nrel['WindSpeed (m/s)'], df_nrel['GenSpeed (rpm)'], 's--', label='NREL 5MW Reference')
    plt.xlabel('Wind Speed (m/s)')
    plt.ylabel('Generator Speed (rpm)')
    plt.title('Generator Speed Comparison')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig('GenSpeedCurve_with_NREL.png')

    # Blade Pitch
    plt.figure(figsize=(8, 5))
    plt.plot(df_user['WindSpeed (m/s)'], df_user['MeanPitch (deg)'], 'o-', label='User OpenFAST')
    plt.plot(df_nrel['WindSpeed (m/s)'], df_nrel['Pitch (deg)'], 's--', label='NREL 5MW Reference')
    plt.xlabel('Wind Speed (m/s)')
    plt.ylabel('Blade Pitch (deg)')
    plt.title('Blade Pitch Comparison')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig('PitchCurve_with_NREL.png')

    plt.show()
    

if __name__ == "__main__":
    main()