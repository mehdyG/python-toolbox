"""
Run OpenFAST startup simulations for IEC DLC 3.1 using NREL 5MW + ROSCO Option A.

Based on the DLC 2.4 grid-loss runner, but changed to:
- start from parked/idling initial conditions
- release HSS brake by time
- connect generator by time or speed
- use deterministic wind or TurbSim .bts files
- save output files by URef, seed, yaw, flow angle, and initial azimuth

IMPORTANT:
Check that your ServoDyn file actually contains the keys used below.
Some NREL 5MW ServoDyn files use older parameter sets.
"""

import os
import shutil
import numpy as np
from pyFAST.input_output import FASTInputFile
from rosco.toolbox.utilities import run_openfast


def set_if_exists(fast_input, key, value):
    """Set OpenFAST key only if it exists in the input file."""
    try:
        _ = fast_input[key]
        fast_input[key] = value
        return True
    except Exception:
        print(f"⚠️ Key not found, skipped: {key}")
        return False


def main():
    this_dir = os.path.dirname(os.path.abspath(__file__))

    wind_dir = os.path.join(this_dir, 'Test_Cases/Wind/')
    fast_dir = os.path.join(this_dir, '_NREL5MW_FASTfiles/5MW_Land_DLL_WTurb')

    fst_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.fst')
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

    FAST_EXE = os.path.join(
        this_dir,
        '../../../miniconda3/envs/openfast_env/bin/openfast'
    )

    output_dir = os.path.join(this_dir, 'DLC3p1_Startup_OF_results')
    os.makedirs(output_dir, exist_ok=True)

    # -----------------------------
    # DLC 3.1 simulation matrix
    # -----------------------------
    URefs = [5, 13]   # for test, then [3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25]

    # For deterministic NWP startup, use seeds = [None]
    # If you want TurbSim .bts turbulent startup, use [1,2,3,4,5,6]
    use_turbulence = True
    seeds = [None] if not use_turbulence else [1, 2] #, 3, 4, 5, 6]

    yaw_offsets = [0]       # screening first; later try [-10, 0, 10]
    flow_angles = [0]       # screening first; later try [-8, 0, 8]
    azimuths = [0]  #, 120, 240]

    # Startup timing for Option A
    TMAX = 600.0
    brake_release_time = 20.0   # THSSBrDp: time to release HSS brake [s]
    generator_on_time = 60.0    # TimGenOn: generator online time [s]

    # Parked / idling initial condition
    startup_pitch_deg = 90.0    # feathered. If no acceleration, try 20-45 deg.
    startup_rot_speed_rpm = 0.0
    startup_oop_defl_m = 0.0
    startup_ip_defl_m = 0.0

    # Backup files before modifying
    backups = []
    for f in [fst_file, inflow_file, servodyn_file, elastodyn_file]:
        backup = f + '.DLC3p1_backup'
        if not os.path.exists(backup):
            shutil.copy2(f, backup)
        backups.append((f, backup))

    try:
        # Modify fst file
        fst = FASTInputFile(fst_file)
        fst['TMax'] = TMAX
        fst.write(fst_file)

        for u in URefs:
            for seed in seeds:
                for yaw in yaw_offsets:
                    for flow in flow_angles:
                        for az in azimuths:

                            # -----------------------------
                            # ElastoDyn startup state
                            # -----------------------------
                            ed = FASTInputFile(elastodyn_file)
                            set_if_exists(ed, 'OoPDefl', startup_oop_defl_m)
                            set_if_exists(ed, 'IPDefl', startup_ip_defl_m)
                            set_if_exists(ed, 'BlPitch(1)', startup_pitch_deg)
                            set_if_exists(ed, 'BlPitch(2)', startup_pitch_deg)
                            set_if_exists(ed, 'BlPitch(3)', startup_pitch_deg)
                            set_if_exists(ed, 'RotSpeed', startup_rot_speed_rpm)
                            set_if_exists(ed, 'Azimuth', az)
                            ed.write(elastodyn_file)

                            # -----------------------------
                            # InflowWind
                            # -----------------------------
                            inflow = FASTInputFile(inflow_file)

                            if use_turbulence:
                                filename = f'TurbSim_U{u}_Seed{seed}.bts'
                                turb_file = os.path.join(wind_dir, filename)

                                if not os.path.exists(turb_file):
                                    print(f"⚠️ Wind file not found: {turb_file}")
                                    continue

                                inflow['WindType'] = 3
                                inflow['FileName_BTS'] = '"' + turb_file + '"'
                            else:
                                # Uniform steady wind, useful for IEC DLC 3.1 screening / NWP-style startup
                                inflow['WindType'] = 1
                                set_if_exists(inflow, 'HWindSpeed', float(u))

                            set_if_exists(inflow, 'PropagationDir', float(yaw))
                            set_if_exists(inflow, 'VFlowAng', float(flow))
                            inflow.write(inflow_file)

                            # -----------------------------
                            # ServoDyn startup Option A
                            # -----------------------------
                            sd = FASTInputFile(servodyn_file)

                            # HSS brake release time.
                            # At/after this time, brake is fully released.
                            set_if_exists(sd, 'THSSBrDp', brake_release_time)

                            # Timed generator start.
                            # OpenFAST docs/source: GenTiStr=True means generator starts using TimGenOn.
                            set_if_exists(sd, 'GenTiStr', True)
                            set_if_exists(sd, 'TimGenOn', generator_on_time)

                            # Keep generator from stopping during startup run
                            set_if_exists(sd, 'GenTiStp', True)
                            set_if_exists(sd, 'TimGenOf', 9999.9)

                            # Optional pitch maneuver keys, only if your ServoDyn file has them.
                            # If ROSCO controls pitch from t=0, these may be ignored or absent.
                            # Use only if your ServoDyn manual/file supports these parameters.
                            set_if_exists(sd, 'TPitManS(1)', brake_release_time)
                            set_if_exists(sd, 'TPitManS(2)', brake_release_time)
                            set_if_exists(sd, 'TPitManS(3)', brake_release_time)

                            sd.write(servodyn_file)

                            # -----------------------------
                            # Run OpenFAST
                            # -----------------------------
                            seed_txt = 'NoSeed' if seed is None else f'Seed{seed}'
                            output_filename = (
                                f'DLC3p1_Startup_U{u:.1f}_{seed_txt}'
                                f'_Yaw{yaw:+.0f}_Flow{flow:+.0f}_Az{az:.0f}.outb'
                            )
                            output_path = os.path.join(output_dir, output_filename)

                            if os.path.exists(output_path):
                                print(f"✅ Already exists: {output_filename}")
                                continue

                            print(
                                f"➡️ Running startup: U={u} m/s, {seed_txt}, "
                                f"Yaw={yaw} deg, Flow={flow} deg, Az={az} deg"
                            )

                            run_openfast(
                                fast_dir,
                                fastfile=fst_file,
                                fastcall=FAST_EXE,
                                chdir=True
                            )

                            out_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.outb')

                            if not os.path.exists(out_file):
                                print(f"❌ Output not found: {output_filename}")
                                continue

                            os.rename(out_file, output_path)

    finally:
        # Restore original files
        for f, backup in backups:
            if os.path.exists(backup):
                shutil.copy2(backup, f)

    print("✅ DLC 3.1 startup calculations finished.")


if __name__ == '__main__':
    main()
