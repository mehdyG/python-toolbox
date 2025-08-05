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
        print(f'➡️ Running OpenFAST for URef = {V} m/s')

        # Modify inflow file
        inflow_in = FASTInputFile(inflow_file)
        inflow_in['HWindSpeed'] = V
        inflow_in.write(inflow_file)

        # Run OpenFAST
        FAST_EXE  = os.path.join(this_dir, '../../../miniconda3/envs/openfast_env/bin/openfast') # Location of a FAST
        run_openfast(fast_dir, fastfile=fst_file, fastcall=FAST_EXE, chdir=True)

        # Output filename
        out_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.outb')

        if not os.path.exists(out_file):
            print(f"❌ Output file not found for URef = {V}")
            continue

        # Read results
        #out = FASTOutputFile(out_file)

        out = FASTOutputFile(out_file).toDataFrame()
        print(out.keys())
        time  = out['Time_[s]']
        Rot_speed = out['RotSpeed_[rpm]']
        V_wind = out['Wind1VelX_[m/s]']
        #input("Press Enter to continue...")

        # Compute steady-state values
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

        # Save individual output file
        os.rename(out_file, os.path.join(output_dir, f'output_U{V:.1f}.outb'))

    # ---------------------------
    # Save CSV
    # ---------------------------
    df = pd.DataFrame(result_list, columns=['WindSpeed (m/s)', 'MeanPower (kW)', 'MeanPitch (deg)', 'MeanGenSpeed (rpm)'])
    csv_path = os.path.join(output_dir, 'PowerCurve_und_SS_Results.csv')
    df.to_csv(csv_path, index=False)
    print(f'✅ Results saved to {csv_path}')

    # ---------------------------
    # Plot Power Curve
    # ---------------------------
    plt.figure(figsize=(8, 5))
    plt.plot(df['WindSpeed (m/s)'], df['MeanPower (kW)'], 'o-', label='Power Curve')
    plt.xlabel('Wind Speed (m/s)')
    plt.ylabel('Mean Power (kW)')
    plt.title('NREL 5MW Power Curve')
    plt.grid(True)
    plt.tight_layout()

    img_path = os.path.join(output_dir, 'PowerCurve.png')
    plt.savefig(img_path)
    print(f'📈 Power curve figure saved to {img_path}')
    plt.show()

if __name__ == "__main__":
    main()