"""
Simple ROSCO Startup Test
NREL 5MW + ROSCO Startup Controller
"""

import os
import shutil
from pyFAST.input_output import FASTInputFile, FASTOutputFile
import subprocess
import matplotlib.pyplot as plt


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
        print("Running startup simulation...")

        subprocess.run(
            [FAST_EXE, os.path.basename(fst_file)],
            cwd=fast_dir,
            check=True
        )

        # -----------------------------
        # Postprocess
        # -----------------------------
        out_file = os.path.join(
            fast_dir,
            "5MW_Land_DLL_WTurb.outb"
        )

        df = FASTOutputFile(out_file).toDataFrame()

        channels = [
            "BldPitch1_[deg]",
            "RotSpeed_[rpm]",
            "GenPwr_[kW]",
            "GenTq_[kN-m]",
            "TTDspFA_[m]"
        ]

        for ch in channels:
            if ch not in df.columns:
                print(f"Missing channel: {ch}")
                continue

            plt.figure(figsize=(10, 4))
            plt.plot(df["Time_[s]"], df[ch])
            plt.xlabel("Time [s]")
            plt.ylabel(ch)
            plt.title(ch)
            plt.grid(True)
            plt.tight_layout()
            plt.show()

    finally:
        # restore original files
        shutil.copy2(servodyn_file + ".bak", servodyn_file)
        shutil.copy2(elastodyn_file + ".bak", elastodyn_file)

    print("Done.")


if __name__ == "__main__":
    main()
