"""
DLC 3.1 Startup - steady wind test
Vin, Vrated, Vout
ROSCO Startup Controller
"""

import os
import shutil
import subprocess
from pyFAST.input_output import FASTInputFile, FASTOutputFile
import matplotlib.pyplot as plt

def update_discon_startup(discon_file,
                          su_start_time,
                          su_fw_min_duration,
                          su_rot_speed_thresh,
                          su_rot_speed_corner_freq,
                          su_load_stages,
                          su_load_ramp_duration,
                          su_load_hold_duration):
    """
    Update ROSCO startup parameters directly inside DISCON.IN.
    """

    su_load_stages_n = len(su_load_stages)

    with open(discon_file, "r") as f:
        lines = f.readlines()

    new_lines = []

    for line in lines:
        if "SU_StartTime" in line:
            new_lines.append(f"{su_start_time:.10f}        ! SU_StartTime            - Time to start startup routine [s]\n")

        elif "SU_FW_MinDuration" in line:
            new_lines.append(f"{su_fw_min_duration:.10f}        ! SU_FW_MinDuration       - Free-wheel minimum duration [s]\n")

        elif "SU_RotorSpeedThresh" in line:
            new_lines.append(f"{su_rot_speed_thresh:.12f}        ! SU_RotorSpeedThresh     - Rotor speed threshhold to switch from freewheel to loads [rad/s]\n")

        elif "SU_RotorSpeedCornerFreq" in line:
            new_lines.append(f"{su_rot_speed_corner_freq:.12f}        ! SU_RotorSpeedCornerFreq - Cutoff Frequency for first order low-pass filter for rotor speed for startup [rad/s]\n")

        elif "SU_LoadStages_N" in line:
            new_lines.append(f"{su_load_stages_n:<22d}! SU_LoadStages_N           - Number of load stages for startup\n")

        elif "SU_LoadStages" in line and "SU_LoadStages_N" not in line:
            values = " ".join([f"{v:.4f}" for v in su_load_stages])
            new_lines.append(f"{values:<22s}! SU_LoadStages        - Loads as fraction of full generator torque during startup\n")

        elif "SU_LoadRampDuration" in line:
            values = " ".join([f"{v:.4f}" for v in su_load_ramp_duration])
            new_lines.append(f"{values:<22s}! SU_LoadRampDuration  - Ramp duration for each load stage [s]\n")

        elif "SU_LoadHoldDuration" in line:
            values = " ".join([f"{v:.4f}" for v in su_load_hold_duration])
            new_lines.append(f"{values:<22s}! SU_LoadHoldDuration  - Hold duration for each load stage [s]\n")

        else:
            new_lines.append(line)

    with open(discon_file, "w") as f:
        f.writelines(new_lines)


def main():

    this_dir = os.path.dirname(os.path.abspath(__file__))

    fast_dir = os.path.join(this_dir, "_NREL5MW_FASTfiles/5MW_Land_DLL_WTurb")

    controller_dir = (
        "/home/Mehdy/python-toolbox/pyFAST/DLC1p2/"
        "_NREL5MW_FASTfiles/5MW_Baseline/"
        "ServoData/Controllerbinaries"
    )

    fst_file = os.path.join(fast_dir, "5MW_Land_DLL_WTurb.fst")
    servodyn_file = os.path.join(fast_dir, "NRELOffshrBsline5MW_Onshore_ServoDyn.dat")
    elastodyn_file = os.path.join(fast_dir, "NRELOffshrBsline5MW_Onshore_ElastoDyn.dat")
    inflow_file = os.path.join(
        fast_dir,
        "../5MW_Baseline/NRELOffshrBsline5MW_InflowWind.dat"
    )

    FAST_EXE = "/home/Mehdy/miniconda3/envs/openfast_env/bin/openfast"

    output_dir = os.path.join(this_dir, "DLC3p1_Startup_SteadyWind_Results")
    os.makedirs(output_dir, exist_ok=True)

    # NREL 5MW typical values
    URefs = [11.4] #[3.0, 11.4, 25.0]   # Vin, Vrated, Vout

    # Your startup duration:
    # 200 freewheel + 60 ramp + 60 hold + 60 ramp + 60 hold = 440 s
    # plus 100 s after completed startup = 540 s
    # -----------------------------
    # ROSCO startup parameters
    # -----------------------------
    SU_StartTime = 0.0
    SU_FW_MinDuration = 100.0
    SU_RotorSpeedThresh = 0.55
    SU_RotorSpeedCornerFreq = 0.41888

    SU_LoadStages = [0.2, 1.0]
    #SU_LoadRampDuration = [30.0, 30.0]
    SU_LoadRampDuration = [60, 60]
    SU_LoadHoldDuration = [60.0, 60.0]

    startup_total_time = (
        SU_StartTime
        + SU_FW_MinDuration
        + sum(SU_LoadRampDuration)
        + sum(SU_LoadHoldDuration)
    )

    TMax = startup_total_time + 150.0

    backups = []
    for f in [fst_file, servodyn_file, elastodyn_file, inflow_file]:
        backup = f + ".bak_dlc31"
        shutil.copy2(f, backup)
        backups.append((f, backup))

    try:
        result_files = []

        for URef in URefs:

            output_name = f"DLC3p1_Startup_Steady_U{URef:.1f}.outb"
            output_path = os.path.join(output_dir, output_name)

            if os.path.exists(output_path):
                print(f"✅ Existing result found, skipping OpenFAST: {output_name}")
                result_files.append((URef, output_path))
            else:
                print(f"➡️ Running DLC 3.1 startup: U = {URef:.1f} m/s")

                # FST
                fst = FASTInputFile(fst_file)
                fst["TMax"] = TMax
                fst.write(fst_file)

                # InflowWind: steady wind
                inflow = FASTInputFile(inflow_file)
                inflow["WindType"] = 1
                inflow["HWindSpeed"] = URef
                inflow.write(inflow_file)

                # ServoDyn: ROSCO startup controller
                sd = FASTInputFile(servodyn_file)

                sd["DLL_FileName"] = '"' + os.path.join(controller_dir, "libdiscon21004.so") + '"'
                sd["DLL_InFile"] = '"' + os.path.join(controller_dir, "DISCON_Merged_NREL5MW_ROSCO_Startup.IN") + '"'

                sd["PCMode"] = 5
                sd["VSContrl"] = 5
                sd["GenModel"] = 1

                sd["GenTiStr"] = True
                sd["TimGenOn"] = 0.0
                sd["GenTiStp"] = True
                sd["TimGenOf"] = 9999.9

                sd["TPitManS(1)"] = 9999.9
                sd["TPitManS(2)"] = 9999.9
                sd["TPitManS(3)"] = 9999.9

                sd.write(servodyn_file)

                # ElastoDyn: parked initial condition
                ed = FASTInputFile(elastodyn_file)
                ed["BlPitch(1)"] = 90.0
                ed["BlPitch(2)"] = 90.0
                ed["BlPitch(3)"] = 90.0
                ed["RotSpeed"] = 0.0
                ed["Azimuth"] = 0.0
                ed.write(elastodyn_file)

                discon_file = os.path.join(
                    controller_dir,
                    "DISCON_Merged_NREL5MW_ROSCO_Startup.IN"
                )

                update_discon_startup(
                    discon_file,
                    SU_StartTime,
                    SU_FW_MinDuration,
                    SU_RotorSpeedThresh,
                    SU_RotorSpeedCornerFreq,
                    SU_LoadStages,
                    SU_LoadRampDuration,
                    SU_LoadHoldDuration
                )

                # Delete old default output
                default_out = os.path.join(fast_dir, "5MW_Land_DLL_WTurb.outb")
                if os.path.exists(default_out):
                    os.remove(default_out)

                subprocess.run(
                    [FAST_EXE, os.path.basename(fst_file)],
                    cwd=fast_dir,
                    check=True
                )

                if os.path.exists(default_out):
                    shutil.move(default_out, output_path)
                    result_files.append((URef, output_path))
                else:
                    print(f"❌ Output missing for U = {URef:.1f}")
                    continue

        # -----------------------------
        # Plot all results after all runs
        # -----------------------------
        for URef, output_path in result_files:

            df = FASTOutputFile(output_path).toDataFrame()

            channels = [
                "Wind1VelX_[m/s]",
                "BldPitch1_[deg]",
                "RotSpeed_[rpm]",
                "GenTq_[kN-m]",
                "GenPwr_[kW]",
                "TTDspFA_[m]",
            ]

            fig, axs = plt.subplots(len(channels), 1, figsize=(11, 12), sharex=True)

            for i, ch in enumerate(channels):
                if ch in df.columns:
                    axs[i].plot(df["Time_[s]"], df[ch])
                    axs[i].set_ylabel(ch)
                    axs[i].grid(True)

            axs[0].set_title(f"DLC 3.1 Startup - U = {URef:.1f} m/s")
            axs[-1].set_xlabel("Time [s]")

            plt.tight_layout()

            plot_path = os.path.join(
                output_dir,
                f"DLC3p1_Startup_Steady_U{URef:.1f}.png"
            )

            plt.savefig(plot_path, dpi=200)
            plt.show()

    finally:
        for f, backup in backups:
            shutil.copy2(backup, f)

    print("✅ DLC 3.1 steady startup runs finished.")


if __name__ == "__main__":
    main()