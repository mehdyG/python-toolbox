"""
Simple OpenFAST yaw/inclination verification
Using one TurbSim .bts file
"""

import os
import numpy as np
import matplotlib.pyplot as plt

from pyFAST.input_output import FASTInputFile, FASTOutputFile
from rosco.toolbox.utilities import run_openfast


def main():

    # -------------------------------------------------------------------------
    # Paths
    # -------------------------------------------------------------------------
    this_dir = os.path.dirname(os.path.abspath(__file__))

    fast_dir = os.path.join(
        this_dir,
        "_NREL5MW_FASTfiles/5MW_Land_DLL_WTurb"
    )

    fst_file = os.path.join(
        fast_dir,
        "5MW_Land_DLL_WTurb.fst"
    )

    inflow_file = os.path.join(
        fast_dir,
        "../5MW_Baseline/NRELOffshrBsline5MW_InflowWind.dat"
    )

    turbsim_file = os.path.join(
        this_dir,
        "Test_Cases/Wind/TurbSim_U13_Seed1.bts"
    )

    FAST_EXE = os.path.join(
        this_dir,
        "../../../miniconda3/envs/openfast_env/bin/openfast"
    )

    # -------------------------------------------------------------------------
    # Define wind turning angles
    # -------------------------------------------------------------------------
    PropagationDir = 30.0   # horizontal turning [deg]
    VFlowAng       = 10.0   # vertical inclination [deg]

    # -------------------------------------------------------------------------
    # Modify InflowWind.dat
    # -------------------------------------------------------------------------
    inflow = FASTInputFile(inflow_file)

    inflow["WindType"] = 3
    inflow["FileName_BTS"] = '"' + turbsim_file + '"'

    # Important parameters to test
    inflow["PropagationDir"] = PropagationDir
    inflow["VFlowAng"] = VFlowAng

    inflow.write(inflow_file)

    print("Running OpenFAST...")

    # -------------------------------------------------------------------------
    # Run OpenFAST
    # -------------------------------------------------------------------------
    run_openfast(
        fast_dir,
        fastfile=fst_file,
        fastcall=FAST_EXE,
        chdir=True
    )

    # -------------------------------------------------------------------------
    # Read output
    # -------------------------------------------------------------------------
    out_file = os.path.join(
        fast_dir,
        "5MW_Land_DLL_WTurb.outb"
    )

    df = FASTOutputFile(out_file).toDataFrame()

    time = df["Time_[s]"]

    # Wind components at point 1
    Vx = df["Wind1VelX_[m/s]"]
    Vy = df["Wind1VelY_[m/s]"]
    Vz = df["Wind1VelZ_[m/s]"]

    # Mean values
    mean_Vx = np.mean(Vx)
    mean_Vy = np.mean(Vy)
    mean_Vz = np.mean(Vz)

    print("\nMean wind components:")
    print(f"Vx = {mean_Vx:.3f} m/s")
    print(f"Vy = {mean_Vy:.3f} m/s")
    print(f"Vz = {mean_Vz:.3f} m/s")

    # Check angle reconstruction
    yaw_angle = np.degrees(np.arctan2(mean_Vy, mean_Vx))
    flow_angle = np.degrees(
        np.arctan2(mean_Vz, np.sqrt(mean_Vx**2 + mean_Vy**2))
    )

    print("\nReconstructed angles:")
    print(f"Yaw angle     = {yaw_angle:.2f} deg")
    print(f"Flow angle    = {flow_angle:.2f} deg")

    # -------------------------------------------------------------------------
    # Plot wind components
    # -------------------------------------------------------------------------
    plt.figure(figsize=(10, 5))
    plt.plot(time, Vx, label="Vx")
    plt.plot(time, Vy, label="Vy")
    plt.plot(time, Vz, label="Vz")

    plt.xlabel("Time [s]")
    plt.ylabel("Wind velocity [m/s]")
    plt.legend()
    plt.grid()
    plt.show()


if __name__ == "__main__":
    main()