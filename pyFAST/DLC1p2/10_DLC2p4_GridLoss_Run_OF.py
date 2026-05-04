"""
Run OF for different Uref, seed number
For DLC 2.4 GridLoss Calculations
with PropagationDir and VFlowAng
"""

import os
from pyFAST.input_output import FASTInputFile, FASTOutputFile
from rosco.toolbox.utilities import run_openfast
import numpy as np


def main():
    this_dir = os.path.dirname(os.path.abspath(__file__))

    wind_dir = os.path.join(this_dir, 'Test_Cases/Wind/')
    fast_dir = os.path.join(this_dir, '_NREL5MW_FASTfiles/5MW_Land_DLL_WTurb')
    fst_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.fst')
    inflow_file = os.path.join(fast_dir, '../5MW_Baseline/NRELOffshrBsline5MW_InflowWind.dat')
    Servodyn_file = os.path.join(fast_dir, 'NRELOffshrBsline5MW_Onshore_ServoDyn.dat')
    FAST_EXE = os.path.join(this_dir, '../../../miniconda3/envs/openfast_env/bin/openfast')

    # Modify fst file
    fst_file_in = FASTInputFile(fst_file)
    fst_file_in['TMax'] = 260.0
    fst_file_in.write(fst_file)

    output_dir = os.path.join(this_dir, 'DLC2p4_OF_results_YawInclination')
    os.makedirs(output_dir, exist_ok=True)

    SS_output_dir = os.path.join(this_dir, 'PowerCurve_und_SS_Results')

    URefs = [5, 7, 9, 11, 13, 15, 17, 19, 21]
    seeds = [1, 2, 3, 4, 5, 6]

    yaw_offsets = [-10, 0, 10]   # PropagationDir [deg]
    flow_angles = [0, 8]         # VFlowAng [deg]

    for u in URefs:

        # Read SS result file
        output_filename = f'output_U{u:.1f}.outb'
        SS_output_path = os.path.join(SS_output_dir, output_filename)

        if not os.path.exists(SS_output_path):
            print(f"⚠️ SS file not found: {SS_output_path}")
            continue

        SS_out = FASTOutputFile(SS_output_path).toDataFrame()

        time = SS_out['Time_[s]']
        pitch = SS_out['BldPitch1_[deg]']
        OoPDefl = SS_out['OoPDefl1_[m]']
        IPDefl = SS_out['IPDefl1_[m]']
        Rot_speed = SS_out['RotSpeed_[rpm]']

        N = len(time)
        last_n = int(0.05 * N)

        mean_pitch = np.mean(pitch[-last_n:])
        mean_OoPDefl = np.mean(OoPDefl[-last_n:])
        mean_IPDefl = np.mean(IPDefl[-last_n:])
        mean_Rot_speed = np.mean(Rot_speed[-last_n:])

        # Replace SS data in ElastoDyn file
        Elastdyn_filename = 'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat'
        Elastdyn_in_file_path = os.path.join(fast_dir, Elastdyn_filename)

        Elastdyn_in = FASTInputFile(Elastdyn_in_file_path)
        Elastdyn_in['OoPDefl'] = mean_OoPDefl
        Elastdyn_in['IPDefl'] = mean_IPDefl
        Elastdyn_in['BlPitch(1)'] = mean_pitch
        Elastdyn_in['BlPitch(2)'] = mean_pitch
        Elastdyn_in['BlPitch(3)'] = mean_pitch
        Elastdyn_in['RotSpeed'] = mean_Rot_speed
        Elastdyn_in.write(Elastdyn_in_file_path)

        for seed in seeds:

            filename = f'TurbSim_U{u}_Seed{seed}.bts'
            Turb_in_file_path = os.path.join(wind_dir, filename)

            if not os.path.exists(Turb_in_file_path):
                print(f"⚠️ File not found: {Turb_in_file_path}")
                continue

            for yaw in yaw_offsets:
                for flow in flow_angles:

                    # Modify InflowWind file
                    inflow_in = FASTInputFile(inflow_file)
                    inflow_in['WindType'] = 3
                    inflow_in['FileName_BTS'] = '"' + Turb_in_file_path + '"'
                    inflow_in['PropagationDir'] = yaw
                    inflow_in['VFlowAng'] = flow
                    inflow_in.write(inflow_file)

                    # Modify ServoDyn file for GridLoss
                    Servodyn_in = FASTInputFile(Servodyn_file)
                    Servodyn_in['TimGenOf'] = 200.0
                    Servodyn_in.write(Servodyn_file)

                    output_filename = (
                        f'DLC2p4output_U{u:.1f}_Seed{seed}'
                        f'_Yaw{yaw:+.0f}_Flow{flow:+.0f}.outb'
                    )

                    output_path = os.path.join(output_dir, output_filename)

                    if os.path.exists(output_path):
                        print(f"✅ Already exists: {output_filename}")
                        continue

                    print(
                        f'➡️ Running OpenFAST for '
                        f'URef={u} m/s, Seed={seed}, '
                        f'Yaw={yaw} deg, Flow={flow} deg'
                    )

                    run_openfast(
                        fast_dir,
                        fastfile=fst_file,
                        fastcall=FAST_EXE,
                        chdir=True
                    )

                    out_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.outb')

                    if not os.path.exists(out_file):
                        print(
                            f"❌ Output file not found for "
                            f"URef={u}, Seed={seed}, Yaw={yaw}, Flow={flow}"
                        )
                        continue

                    os.rename(out_file, output_path)

    # Reset InflowWind file
    inflow_in = FASTInputFile(inflow_file)
    inflow_in['WindType'] = 1
    inflow_in['PropagationDir'] = 0.0
    inflow_in['VFlowAng'] = 0.0
    inflow_in.write(inflow_file)

    # Reset ServoDyn file
    Servodyn_in = FASTInputFile(Servodyn_file)
    Servodyn_in['TimGenOf'] = 9999.9
    Servodyn_in.write(Servodyn_file)

    # Reset fst file
    fst_file_in = FASTInputFile(fst_file)
    fst_file_in['TMax'] = 600.0
    fst_file_in.write(fst_file)

    print("✅ DLC 2.4 GridLoss calculations finished.")


if __name__ == "__main__":
    main()