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
    URefs = [3.0, 11.4, 25.0]   # Vin, Vrated, Vout

    # Your startup duration:
    # 200 freewheel + 60 ramp + 60 hold + 60 ramp + 60 hold = 440 s
    # plus 100 s after completed startup = 540 s
    TMax = 540.0

    backups = []
    for f in [fst_file, servodyn_file, elastodyn_file, inflow_file]:
        backup = f + ".bak_dlc31"
        shutil.copy2(f, backup)
        backups.append((f, backup))

    try:
        for URef in URefs:

            output_name = f"DLC3p1_Startup_Steady_U{URef:.1f}.outb"
            output_path = os.path.join(output_dir, output_name)

            if os.path.exists(output_path):
                print(f"✅ Existing result found, skipping OpenFAST: {output_name}")
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
                else:
                    print(f"❌ Output missing for U = {URef:.1f}")
                    continue

            # Plot result
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

            axs[0].set_title(f"DLC 3.1 Startup - Steady Wind U = {URef:.1f} m/s")
            axs[-1].set_xlabel("Time [s]")
            plt.tight_layout()

            plot_path = os.path.join(output_dir, f"DLC3p1_Startup_Steady_U{URef:.1f}.png")
            plt.savefig(plot_path, dpi=200)
            plt.show()

    finally:
        for f, backup in backups:
            shutil.copy2(backup, f)

    print("✅ DLC 3.1 steady startup runs finished.")


if __name__ == "__main__":
    main()