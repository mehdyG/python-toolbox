"""
Simple ROSCO Startup Test
NREL 5MW + ROSCO Startup Controller
"""

import os
import shutil
from pyFAST.input_output import FASTInputFile, FASTOutputFile
import subprocess
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main():

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

    fst_file = os.path.join(fast_dir, "5MW_Land_DLL_WTurb.fst")

    servodyn_file = os.path.join(
        fast_dir,
        "NRELOffshrBsline5MW_Onshore_ServoDyn.dat"
    )

    elastodyn_file = os.path.join(
        fast_dir,
        "NRELOffshrBsline5MW_Onshore_ElastoDyn.dat"
    )

    FAST_EXE = "/home/Mehdy/miniconda3/envs/openfast_env/bin/openfast"

    # -----------------------------
    # Backup files
    # -----------------------------
    shutil.copy2(servodyn_file, servodyn_file + ".bak")
    shutil.copy2(elastodyn_file, elastodyn_file + ".bak")

    try:

        # -----------------------------
        # ServoDyn → connect ROSCO startup controller
        # -----------------------------
        sd = FASTInputFile(servodyn_file)

        sd["DLL_FileName"] = (
            '"' + os.path.join(
                controller_dir,
                "libdiscon21004.so"
            ) + '"'
        )

        sd["DLL_InFile"] = (
            '"' + os.path.join(
                controller_dir,
                "DISCON_Merged_NREL5MW_ROSCO_Startup.IN"
            ) + '"'
        )

        sd['PCMode'] = 5
        sd['VSContrl'] = 5

        sd['TPitManS(1)'] = 9999.9
        sd['TPitManS(2)'] = 9999.9
        sd['TPitManS(3)'] = 9999.9
        sd['BlPitchF(1)'] = 0.0
        
        sd['GenTiStr'] = True
        sd['TimGenOn'] = 0.0

        sd['GenTiStp'] = True
        sd['TimGenOf'] = 9999.9

        sd.write(servodyn_file)

        # -----------------------------
        # Initial parked condition
        # -----------------------------
        ed = FASTInputFile(elastodyn_file)

        ed["BlPitch(1)"] = 90.0
        ed["BlPitch(2)"] = 90.0
        ed["BlPitch(3)"] = 90.0

        ed["RotSpeed"] = 0.0
        ed["Azimuth"] = 0.0

        ed.write(elastodyn_file)

        # -----------------------------
        # Run OpenFAST
        # -----------------------------

        out_file = os.path.join(
            fast_dir,
            "5MW_Land_DLL_WTurb.outb"
        )

        if os.path.exists(out_file):
            print("✅ Output file exists. Skipping OpenFAST run and loading results.")

        else:
            print("➡️ Running OpenFAST...")

            subprocess.run(
                [FAST_EXE, os.path.basename(fst_file)],
                cwd=fast_dir,
                check=True
            )

        # -----------------------------
        # Postprocess
        # -----------------------------

        df = FASTOutputFile(out_file).toDataFrame()
        #print(df.columns)
        dbg2_file = os.path.join(
            fast_dir,
            "5MW_Land_DLL_WTurb.RO.dbg2"
        )

        dbg = pd.read_csv(
            dbg2_file,
            sep=r"\s+",
            skiprows=1,   # adjust if needed
            engine="python"
        )

        #print(dbg.columns.tolist())


        fig, axs = plt.subplots(7, 1, figsize=(10, 12), sharex=True)

        # OpenFAST .outb variables
        axs[0].plot(df["Time_[s]"], df["Wind1VelX_[m/s]"])
        axs[0].set_ylabel("WindVelX\n(m/s)")

        axs[1].plot(df["Time_[s]"], df["BldPitch1_[deg]"])
        axs[1].set_ylabel("BldPitch1\n(deg)")

        axs[2].plot(df["Time_[s]"], df["GenTq_[kN-m]"])
        axs[2].set_ylabel("GenTq\n(kN-m)")

        axs[3].plot(df["Time_[s]"], df["RotSpeed_[rpm]"])
        axs[3].set_ylabel("RotSpeed\n(rpm)")

        axs[4].plot(df["Time_[s]"], df["GenPwr_[kW]"])
        axs[4].set_ylabel("GenPwr\n(kW)")

        # ROSCO .dbg2 variables
        axs[5].plot(dbg["Time"], dbg["SU_Stage"])
        axs[5].set_ylabel("SU_Stage\n(-)")

        axs[6].plot(dbg["Time"], dbg["PRC_R_Torque"])
        axs[6].set_ylabel("PRC_R_Torque\n(-)")

        for ax in axs:
            ax.grid(True)

        axs[0].set_title("Startup")
        axs[-1].set_xlabel("Time [s]")

        plt.tight_layout()
        plt.show()

    finally:
        # restore original files
        shutil.copy2(servodyn_file + ".bak", servodyn_file)
        shutil.copy2(elastodyn_file + ".bak", elastodyn_file)

    print("Done.")


if __name__ == "__main__":
    main()
