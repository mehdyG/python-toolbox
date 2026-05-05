"""
Run OpenFAST for DLC 2.4 / Yaw fault (yaw misalignment fault)

Yaw fault definition:
- Wind direction remains fixed (PropagationDir = 0)
- Nacelle yaw is fixed at yaw_error
- YawNeut = yaw_error (persistent fault, no restoring yaw moment)
"""

import os
import shutil
import numpy as np
from pyFAST.input_output import FASTInputFile
from rosco.toolbox.utilities import run_openfast


def safe_mkdir(path):
    os.makedirs(path, exist_ok=True)


def initialize_elastodyn(elastodyn_path, yaw_error):
    """
    Set nacelle initial yaw position
    """
    ed = FASTInputFile(elastodyn_path)

    if 'NacYaw' in ed.keys():
        ed['NacYaw'] = float(yaw_error)

    ed.write(elastodyn_path)


def set_inflow_case(inflow_file, bts_path, incl_deg):
    """
    Keep wind direction fixed.
    Inclination can vary.
    """
    inflow = FASTInputFile(inflow_file)

    inflow['WindType'] = 3
    inflow['FileName_BTS'] = '"' + bts_path + '"'

    if 'PropagationDir' in inflow.keys():
        inflow['PropagationDir'] = 0.0

    if 'VFlowAng' in inflow.keys():
        inflow['VFlowAng'] = float(incl_deg)

    inflow.write(inflow_file)


def set_yaw_fault(servodyn_file, yaw_error):
    """
    Persistent yaw fault:
    yaw system equilibrium = faulty yaw angle
    """
    sd = FASTInputFile(servodyn_file)

    if 'YawNeut' in sd.keys():
        sd['YawNeut'] = float(yaw_error)

    # Disable active yaw maneuver if present
    if 'TYawManS' in sd.keys():
        sd['TYawManS'] = 9999.9

    if 'YawManRat' in sd.keys():
        sd['YawManRat'] = 0.0

    sd.write(servodyn_file)


def restore_inflow_to_uniform(inflow_file):
    inflow = FASTInputFile(inflow_file)
    inflow['WindType'] = 1
    inflow.write(inflow_file)


def ensure_outlist_channels(input_file, channels):
    with open(input_file, "r") as f:
        lines = f.readlines()

    existing_text = "".join(lines)

    missing = []
    for ch in channels:
        if f'"{ch}"' not in existing_text:
            missing.append(ch)

    if not missing:
        return

    end_idx = None
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("END"):
            end_idx = i
            break

    if end_idx is None:
        raise RuntimeError(f"Could not find END in OutList of {input_file}")

    new_lines = [f'"{ch}"\n' for ch in missing]
    lines = lines[:end_idx] + new_lines + lines[end_idx:]

    with open(input_file, "w") as f:
        f.writelines(lines)


def main():
    this_dir = os.path.dirname(os.path.abspath(__file__))

    fast_dir = os.path.join(
        this_dir,
        '_NREL5MW_FASTfiles/5MW_Land_DLL_WTurb'
    )

    fst_file = os.path.join(
        fast_dir,
        '5MW_Land_DLL_WTurb.fst'
    )

    inflow_file = os.path.join(
        fast_dir,
        '../5MW_Baseline/NRELOffshrBsline5MW_InflowWind.dat'
    )

    servodyn_file = os.path.join(
        fast_dir,
        'NRELOffshrBsline5MW_Onshore_ServoDyn.dat'
    )

    elastodyn_file = os.path.join(
        fast_dir,
        'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat'
    )

    wind_dir = os.path.join(
        this_dir,
        'Test_Cases/Wind/'
    )

    FAST_EXE = os.path.join(
        this_dir,
        '../../../miniconda3/envs/openfast_env/bin/openfast'
    )

    output_dir = os.path.join(
        this_dir,
        'DLC2p4_YawFault_OF_results'
    )

    safe_mkdir(output_dir)

    # -----------------------------
    # Requested matrix
    # -----------------------------
    URefs = np.arange(3, 26, 2)
    seeds = list(range(1, 7))
    yaw_errors = np.arange(0, 351, 15)
    inclinations = [0.0, 8.0]
    # -----------------------------

    inflow_backup = inflow_file + '.bak_yawfault'
    servodyn_backup = servodyn_file + '.bak_yawfault'
    elastodyn_backup = elastodyn_file + '.bak_yawfault'

    if not os.path.exists(inflow_backup):
        shutil.copy2(inflow_file, inflow_backup)

    if not os.path.exists(servodyn_backup):
        shutil.copy2(servodyn_file, servodyn_backup)

    if not os.path.exists(elastodyn_backup):
        shutil.copy2(elastodyn_file, elastodyn_backup)

    try:
        for u in URefs:
            for seed in seeds:

                bts_filename = f'TurbSim_U{int(u)}_Seed{seed}.bts'
                bts_path = os.path.join(wind_dir, bts_filename)

                if not os.path.exists(bts_path):
                    print(f"⚠ BTS file not found: {bts_path}")
                    continue

                for yaw_error in yaw_errors:
                    for incl_deg in inclinations:

                        shutil.copy2(inflow_backup, inflow_file)
                        shutil.copy2(servodyn_backup, servodyn_file)
                        shutil.copy2(elastodyn_backup, elastodyn_file)

                        ensure_outlist_channels(
                            elastodyn_file,
                            ["YawPzn", "RotSpeed"]
                        )

                        initialize_elastodyn(
                            elastodyn_file,
                            yaw_error
                        )

                        set_inflow_case(
                            inflow_file,
                            bts_path,
                            incl_deg
                        )

                        set_yaw_fault(
                            servodyn_file,
                            yaw_error
                        )

                        output_filename = (
                            f'output_U{u:.1f}'
                            f'_Seed{seed}'
                            f'_YawErr{yaw_error:.0f}'
                            f'_Inc{incl_deg:.0f}.outb'
                        )

                        output_path = os.path.join(
                            output_dir,
                            output_filename
                        )

                        if os.path.exists(output_path):
                            print(f"⏭ Skipping existing case: {output_filename}")
                            continue

                        print(
                            f"➡ Running Yaw Fault: "
                            f"U={u:.1f} m/s | "
                            f"Seed={seed} | "
                            f"YawError={yaw_error:.0f}° | "
                            f"Inclination={incl_deg:.1f}°"
                        )

                        run_openfast(
                            fast_dir,
                            fastfile=fst_file,
                            fastcall=FAST_EXE,
                            chdir=True
                        )

                        out_file = os.path.join(
                            fast_dir,
                            '5MW_Land_DLL_WTurb.outb'
                        )

                        if not os.path.exists(out_file):
                            print(f"❌ Output missing: {output_filename}")
                            continue

                        os.rename(out_file, output_path)

    finally:
        if os.path.exists(inflow_backup):
            shutil.copy2(inflow_backup, inflow_file)

        if os.path.exists(servodyn_backup):
            shutil.copy2(servodyn_backup, servodyn_file)

        if os.path.exists(elastodyn_backup):
            shutil.copy2(elastodyn_backup, elastodyn_file)

        restore_inflow_to_uniform(inflow_file)

        print("\n✅ Original input files restored.\n")


if __name__ == "__main__":
    main()