"""
Check mean wind direction and flow inclination
for two OpenFAST results
"DLC2p4output_U15.0_Seed1_Yaw-10_Flow+0.outb"
"DLC2p4output_U15.0_Seed1_Yaw+10_Flow+8.outb"
"""

import os
import numpy as np
from pyFAST.input_output import FASTOutputFile


def check_file(filepath):

    # Read OpenFAST output
    df = FASTOutputFile(filepath).toDataFrame()

    # Wind components
    Vx = df["Wind1VelX_[m/s]"]
    Vy = df["Wind1VelY_[m/s]"]
    Vz = df["Wind1VelZ_[m/s]"]

    # Mean values
    mean_Vx = np.mean(Vx)
    mean_Vy = np.mean(Vy)
    mean_Vz = np.mean(Vz)

    # Total mean wind speed
    mean_V = np.sqrt(mean_Vx**2 + mean_Vy**2 + mean_Vz**2)

    # Reconstruct yaw angle
    yaw_angle = np.degrees(np.arctan2(mean_Vy, mean_Vx))

    # Reconstruct flow angle
    flow_angle = np.degrees(
        np.arctan2(mean_Vz, np.sqrt(mean_Vx**2 + mean_Vy**2))
    )

    print("\n----------------------------------")
    print(f"File: {os.path.basename(filepath)}")
    print(f"Mean Wind Speed = {mean_V:.3f} m/s")
    print(f"Mean Yaw Angle  = {yaw_angle:.2f} deg")
    print(f"Mean Flow Angle = {flow_angle:.2f} deg")


def main():

    this_dir = os.path.dirname(os.path.abspath(__file__))

    output_dir = os.path.join(
        this_dir,
        "DLC2p4_OF_results_YawInclination"
    )

    # Example: two files for U=15 and Seed=1
    file1 = os.path.join(
        output_dir,
        "DLC2p4output_U15.0_Seed1_Yaw-10_Flow+0.outb"
    )

    file2 = os.path.join(
        output_dir,
        "DLC2p4output_U15.0_Seed1_Yaw+10_Flow+8.outb"
    )

    check_file(file1)
    check_file(file2)


if __name__ == "__main__":
    main()