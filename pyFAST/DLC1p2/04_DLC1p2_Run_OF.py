"""
Run OpenFAST for DLC 1.2
Different URef, seed, PropagationDir and VFlowAng
"""

import os
import numpy as np

from pyFAST.input_output import FASTInputFile, FASTOutputFile
from rosco.toolbox.utilities import run_openfast


def main():

    this_dir = os.path.dirname(os.path.abspath(__file__))

    # -------------------------------------------------------------------------
    # Paths
    # -------------------------------------------------------------------------
    wind_dir = os.path.join(this_dir, "Test_Cases/Wind/")
    fast_dir = os.path.join(this_dir, "_NREL5MW_FASTfiles/5MW_Land_DLL_WTurb")
    fst_file = os.path.join(fast_dir, "5MW_Land_DLL_WTurb.fst")

    inflow_file = os.path.join(
        fast_dir,
        "../5MW_Baseline/NRELOffshrBsline5MW_InflowWind.dat"
    )

    FAST_EXE = os.path.join(
        this_dir,
        "../../../miniconda3/envs/openfast_env/bin/openfast"
    )

    output_dir = os.path.join(this_dir, "DLC1p2_OF_results_YawInclination")
    os.makedirs(output_dir, exist_ok=True)

    SS_output_dir = os.path.join(this_dir, "PowerCurve_und_SS_Results")

    # -------------------------------------------------------------------------
    # DLC 1.2 parameters
    # -------------------------------------------------------------------------
    URefs = np.arange(3, 26, 2)
    seeds = [1, 2, 3, 4, 5, 6]

    yaw_offsets = [-10, 0, 10]     # PropagationDir [deg]
    flow_angles = [0, 8]           # VFlowAng [deg]

    # -------------------------------------------------------------------------
    # Main loop
    # -------------------------------------------------------------------------
    for u in URefs:

        # ---------------------------------------------------------------------
        # Read steady-state result for initialization
        # ---------------------------------------------------------------------
        ss_output_filename = f"output_U{u:.1f}.outb"
        ss_output_path = os.path.join(SS_output_dir, ss_output_filename)

        if not os.path.exists(ss_output_path):
            print(f"⚠️ SS file not found: {ss_output_path}")
            continue

        SS_out = FASTOutputFile(ss_output_path).toDataFrame()

        time = SS_out["Time_[s]"]
        pitch = SS_out["BldPitch1_[deg]"]
        OoPDefl = SS_out["OoPDefl1_[m]"]
        IPDefl = SS_out["IPDefl1_[m]"]
        Rot_speed = SS_out["RotSpeed_[rpm]"]

        N = len(time)
        last_n = int(0.05 * N)

        mean_pitch = np.mean(pitch[-last_n:])
        mean_OoPDefl = np.mean(OoPDefl[-last_n:])
        mean_IPDefl = np.mean(IPDefl[-last_n:])
        mean_Rot_speed = np.mean(Rot_speed[-last_n:])

        # ---------------------------------------------------------------------
        # Write initial conditions to ElastoDyn
        # ---------------------------------------------------------------------
        elastodyn_filename = "NRELOffshrBsline5MW_Onshore_ElastoDyn.dat"
        elastodyn_file = os.path.join(fast_dir, elastodyn_filename)

        elastodyn = FASTInputFile(elastodyn_file)

        elastodyn["OoPDefl"] = mean_OoPDefl
        elastodyn["IPDefl"] = mean_IPDefl
        elastodyn["BlPitch(1)"] = mean_pitch
        elastodyn["BlPitch(2)"] = mean_pitch
        elastodyn["BlPitch(3)"] = mean_pitch
        elastodyn["RotSpeed"] = mean_Rot_speed

        elastodyn.write(elastodyn_file)

        # ---------------------------------------------------------------------
        # Run all DLC 1.2 cases
        # ---------------------------------------------------------------------
        for seed in seeds:

            turbsim_filename = f"TurbSim_U{u}_Seed{seed}.bts"
            turbsim_file = os.path.join(wind_dir, turbsim_filename)

            if not os.path.exists(turbsim_file):
                print(f"⚠️ TurbSim file not found: {turbsim_file}")
                continue

            for yaw in yaw_offsets:
                for flow in flow_angles:

                    output_filename = (
                        f"output_U{u:.1f}_Seed{seed}"
                        f"_Yaw{yaw:+.0f}_Flow{flow:+.0f}.outb"
                    )

                    output_path = os.path.join(output_dir, output_filename)

                    if os.path.exists(output_path):
                        print(f"✅ Already exists: {output_filename}")
                        continue

                    # ---------------------------------------------------------
                    # Modify InflowWind.dat
                    # ---------------------------------------------------------
                    inflow = FASTInputFile(inflow_file)

                    inflow["WindType"] = 3
                    inflow["FileName_BTS"] = '"' + turbsim_file + '"'

                    inflow["PropagationDir"] = yaw
                    inflow["VFlowAng"] = flow

                    inflow.write(inflow_file)

                    print(
                        f"➡️ Running OpenFAST: "
                        f"URef={u} m/s, Seed={seed}, "
                        f"Yaw={yaw} deg, Flow={flow} deg"
                    )

                    # ---------------------------------------------------------
                    # Run OpenFAST
                    # ---------------------------------------------------------
                    run_openfast(
                        fast_dir,
                        fastfile=fst_file,
                        fastcall=FAST_EXE,
                        chdir=True
                    )

                    # ---------------------------------------------------------
                    # Save output
                    # ---------------------------------------------------------
                    out_file = os.path.join(
                        fast_dir,
                        "5MW_Land_DLL_WTurb.outb"
                    )

                    if not os.path.exists(out_file):
                        print(
                            f"❌ Output file not found: "
                            f"URef={u}, Seed={seed}, Yaw={yaw}, Flow={flow}"
                        )
                        continue

                    os.rename(out_file, output_path)

    # -------------------------------------------------------------------------
    # Reset InflowWind.dat
    # -------------------------------------------------------------------------
    inflow = FASTInputFile(inflow_file)
    inflow["WindType"] = 1
    inflow["PropagationDir"] = 0.0
    inflow["VFlowAng"] = 0.0
    inflow.write(inflow_file)

    print("✅ DLC 1.2 calculations finished.")


if __name__ == "__main__":
    main()