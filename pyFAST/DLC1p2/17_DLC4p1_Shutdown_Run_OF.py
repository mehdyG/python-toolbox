"""
DLC 4.1 Shutdown - steady wind test
ROSCO Shutdown Controller
Simple version with FASTInputFile for DISCON.IN
"""

import os
import shutil
import subprocess
import matplotlib.pyplot as plt

from pyFAST.input_output import FASTInputFile, FASTOutputFile

def update_rosco_discon(discon_file, params):
    """
    Update ROSCO DISCON.IN parameters.
    Works for ROSCO-style lines:
    value(s)    ! ParameterName - description
    """

    with open(discon_file, "r") as f:
        lines = f.readlines()

    new_lines = []

    for line in lines:
        new_line = line

        for key, value in params.items():

            if "!" in line:
                comment_part = line.split("!", 1)[1].strip()

                # parameter name is first word after "!"
                label = comment_part.split()[0]

                if label == key:

                    if isinstance(value, list):
                        value_str = " ".join([f"{v:.6f}" for v in value])
                    elif isinstance(value, int):
                        value_str = f"{value:d}"
                    else:
                        value_str = f"{value:.10f}"

                    new_line = f"{value_str:<30s}! {comment_part}\n"
                    print(f"  {key} = {value}")
                    break

        new_lines.append(new_line)

    with open(discon_file, "w") as f:
        f.writelines(new_lines)

def plot_shutdown_result(output_path, plot_path, title):

    df = FASTOutputFile(output_path).toDataFrame()

    channels = [
        "Wind1VelX_[m/s]",
        "BldPitch1_[deg]",
        "BldPitch2_[deg]",
        "BldPitch3_[deg]",
        "RotSpeed_[rpm]",
        "GenSpeed_[rpm]",
        "GenTq_[kN-m]",
        "GenPwr_[kW]",
        "TwrBsMyt_[kN-m]",
        "RootMyb1_[kN-m]",
    ]

    existing_channels = [ch for ch in channels if ch in df.columns]

    fig, axs = plt.subplots(
        len(existing_channels),
        1,
        figsize=(12, 15),
        sharex=True
    )

    if len(existing_channels) == 1:
        axs = [axs]

    for i, ch in enumerate(existing_channels):
        axs[i].plot(df["Time_[s]"], df[ch])
        axs[i].set_ylabel(ch)
        axs[i].grid(True)

    axs[0].set_title(title)
    axs[-1].set_xlabel("Time [s]")

    plt.tight_layout()
    plt.savefig(plot_path, dpi=200)
    plt.show()


def main():

    # ==========================================================
    # Paths
    # ==========================================================

    this_dir = os.path.dirname(os.path.abspath(__file__))

    fast_dir = os.path.join(
        this_dir,
        "_NREL5MW_FASTfiles/5MW_Land_DLL_WTurb"
    )

    controller_dir = (
        "/home/Mehdy/python-toolbox/pyFAST/DLC1p2/"
        "_NREL5MW_FASTfiles/5MW_Baseline/"
        "ServoData/Controllerbinaries"
    )

    FAST_EXE = "/home/Mehdy/miniconda3/envs/openfast_env/bin/openfast"

    fst_file = os.path.join(
        fast_dir,
        "5MW_Land_DLL_WTurb.fst"
    )

    servodyn_file = os.path.join(
        fast_dir,
        "NRELOffshrBsline5MW_Onshore_ServoDyn.dat"
    )

    elastodyn_file = os.path.join(
        fast_dir,
        "NRELOffshrBsline5MW_Onshore_ElastoDyn.dat"
    )

    inflow_file = os.path.join(
        fast_dir,
        "../5MW_Baseline/NRELOffshrBsline5MW_InflowWind.dat"
    )

    discon_file = os.path.join(
        controller_dir,
        "DISCON_Merged_NREL5MW_ROSCO_Shutdown.IN"
    )

    rosco_lib = os.path.join(
        controller_dir,
        "libdiscon21004.so"
    )

    output_dir = os.path.join(
        this_dir,
        "DLC4p1_Shutdown_SteadyWind_Results"
    )

    os.makedirs(output_dir, exist_ok=True)

    # ==========================================================
    # User settings
    # ==========================================================

    DO_POSTPROCESS = True
    SKIP_EXISTING = True

    # First test
    URefs = [11.4]

    # Later for DLC 4.1 batch:
    # URefs = [4, 6, 8, 10, 11.4, 12, 14, 16, 18, 20, 22, 24]

    TMax = 600.0

    # ==========================================================
    # Shutdown scenarios
    # ==========================================================

    shutdown_scenarios = {

        "time_shutdown_100s": {

            # Shutdown active
            "SD_Mode": 1,

            # Trigger selection
            "SD_EnablePitch": 0,
            "SD_EnableYawError": 0,
            "SD_EnableGenSpeed": 0,
            "SD_EnableTime": 1,

            # Shutdown starts at this time
            "SD_Time": 100.0,

            # Method 1 = stages based on time
            "SD_Method": 1,
            "SD_Stage_N": 2,

            # Stage settings
            "SD_StageTime": [10.0, 30.0],
            "SD_StagePitch": [0.35, 1.5708],

            # 8 deg/s = 0.1396 rad/s
            "SD_MaxPitchRate": [0.1396, 0.1396],

            # Torque reduction rate
            "SD_MaxTorqueRate": [50000.0, 50000.0],
        },


        "pitch_threshold_shutdown": {

            "SD_Mode": 1,

            "SD_EnablePitch": 1,
            "SD_EnableYawError": 0,
            "SD_EnableGenSpeed": 0,
            "SD_EnableTime": 0,

            # Pitch threshold, rad
            # 25 deg = 0.4363 rad
            "SD_MaxPit": 0.4363,

            "SD_Time": 9999.9,

            "SD_Method": 1,
            "SD_Stage_N": 2,

            "SD_StageTime": [10.0, 30.0],
            "SD_StagePitch": [0.35, 1.5708],
            "SD_MaxPitchRate": [0.1396, 0.1396],
            "SD_MaxTorqueRate": [50000.0, 50000.0],
        },


        "genspeed_threshold_shutdown": {

            "SD_Mode": 1,

            "SD_EnablePitch": 0,
            "SD_EnableYawError": 0,
            "SD_EnableGenSpeed": 1,
            "SD_EnableTime": 0,

            # Generator speed threshold, rad/s
            # Change this based on your turbine/controller
            "SD_MaxGenSpd": 130.0,

            "SD_Time": 9999.9,

            "SD_Method": 1,
            "SD_Stage_N": 2,

            "SD_StageTime": [10.0, 30.0],
            "SD_StagePitch": [0.35, 1.5708],
            "SD_MaxPitchRate": [0.1396, 0.1396],
            "SD_MaxTorqueRate": [50000.0, 50000.0],
        },
    }

    # Choose here
    scenarios_to_run = [
        "time_shutdown_100s",
        # "pitch_threshold_shutdown",
        # "genspeed_threshold_shutdown",
    ]

    # ==========================================================
    # Backup files
    # ==========================================================

    backup_files = [
        fst_file,
        servodyn_file,
        elastodyn_file,
        inflow_file,
        discon_file,
    ]

    backups = []

    for f in backup_files:
        backup = f + ".bak_dlc41"
        shutil.copy2(f, backup)
        backups.append((f, backup))

    # ==========================================================
    # Run simulations
    # ==========================================================

    try:

        result_files = []

        for scenario_name in scenarios_to_run:

            sd_params = shutdown_scenarios[scenario_name]

            for URef in URefs:

                output_name = f"DLC4p1_{scenario_name}_U{URef:.1f}.outb"
                output_path = os.path.join(output_dir, output_name)

                if SKIP_EXISTING and os.path.exists(output_path):
                    print(f"✅ Existing result found, skipping OpenFAST: {output_name}")
                    result_files.append((scenario_name, URef, output_path))
                    continue

                print(f"➡️ Running DLC 4.1: {scenario_name}, U = {URef:.1f} m/s")

                # --------------------------------------------------
                # FST
                # --------------------------------------------------

                fst = FASTInputFile(fst_file)
                fst["TMax"] = TMax
                fst.write(fst_file)

                # --------------------------------------------------
                # InflowWind: steady wind first
                # --------------------------------------------------

                inflow = FASTInputFile(inflow_file)
                inflow["WindType"] = 1
                inflow["HWindSpeed"] = URef
                inflow.write(inflow_file)

                # --------------------------------------------------
                # ServoDyn: ROSCO controller
                # --------------------------------------------------

                sd = FASTInputFile(servodyn_file)

                sd["DLL_FileName"] = '"' + rosco_lib + '"'
                sd["DLL_InFile"] = '"' + discon_file + '"'

                sd["PCMode"] = 5
                sd["VSContrl"] = 5
                sd["GenModel"] = 1

                # Generator active from beginning
                sd["GenTiStr"] = True
                sd["TimGenOn"] = 0.0

                # Do not shut down generator manually in ServoDyn
                # ROSCO should control the shutdown
                sd["GenTiStp"] = True
                sd["TimGenOf"] = 9999.9

                # No manual pitch maneuver
                sd["TPitManS(1)"] = 9999.9
                sd["TPitManS(2)"] = 9999.9
                sd["TPitManS(3)"] = 9999.9

                sd.write(servodyn_file)

                # --------------------------------------------------
                # ElastoDyn: normal operating initial condition
                # --------------------------------------------------

                ed = FASTInputFile(elastodyn_file)

                ed["BlPitch(1)"] = 0.0
                ed["BlPitch(2)"] = 0.0
                ed["BlPitch(3)"] = 0.0

                # NREL 5MW rated rotor speed
                ed["RotSpeed"] = 12.1
                ed["Azimuth"] = 0.0

                ed.write(elastodyn_file)

                # --------------------------------------------------
                # DISCON.IN: shutdown parameters
                # --------------------------------------------------
                print("Updating DISCON shutdown parameters:")
                update_rosco_discon(discon_file, sd_params)

                # --------------------------------------------------
                # Delete old OpenFAST output
                # --------------------------------------------------

                default_out = os.path.join(
                    fast_dir,
                    "5MW_Land_DLL_WTurb.outb"
                )

                if os.path.exists(default_out):
                    os.remove(default_out)

                # --------------------------------------------------
                # Run OpenFAST
                # --------------------------------------------------

                subprocess.run(
                    [FAST_EXE, os.path.basename(fst_file)],
                    cwd=fast_dir,
                    check=True
                )

                # --------------------------------------------------
                # Move result
                # --------------------------------------------------

                if os.path.exists(default_out):
                    shutil.move(default_out, output_path)
                    result_files.append((scenario_name, URef, output_path))
                    print(f"✅ Result saved: {output_path}")
                else:
                    print(f"❌ Output missing: {output_name}")

        # ==========================================================
        # Post-processing
        # ==========================================================

        if DO_POSTPROCESS:

            for scenario_name, URef, output_path in result_files:

                plot_name = f"DLC4p1_{scenario_name}_U{URef:.1f}.png"
                plot_path = os.path.join(output_dir, plot_name)

                title = (
                    f"DLC 4.1 Shutdown - {scenario_name} - "
                    f"U = {URef:.1f} m/s"
                )

                plot_shutdown_result(output_path, plot_path, title)

    finally:

        # Restore original input files
        for f, backup in backups:
            shutil.copy2(backup, f)

        print("✅ Original input files restored.")

    print("✅ DLC 4.1 shutdown simulations finished.")


if __name__ == "__main__":
    main()